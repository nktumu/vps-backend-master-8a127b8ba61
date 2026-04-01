#!/usr/bin/env python
# VERITAS: Copyright (c) 2022 Veritas Technologies LLC. All rights reserved.
#
# THIS SOFTWARE CONTAINS CONFIDENTIAL INFORMATION AND TRADE SECRETS OF VERITAS
# TECHNOLOGIES LLC.  USE, DISCLOSURE OR REPRODUCTION IS PROHIBITED WITHOUT THE
# PRIOR EXPRESS WRITTEN PERMISSION OF VERITAS TECHNOLOGIES LLC.
#
# The Licensed Software and Documentation are deemed to be commercial computer
# software as defined in FAR 12.212 and subject to restricted rights as defined
# in FAR Section 52.227-19 "Commercial Computer Software - Restricted Rights"
# and DFARS 227.7202, Rights in "Commercial Computer Software or Commercial
# Computer Software Documentation," as applicable, and any successor
# regulations, whether delivered by Veritas as on premises or hosted services.
# Any use, modification, reproduction release, performance, display or
# disclosure of the Licensed Software and Documentation by the U.S. Government
# shall be solely in accordance with the terms of this Agreement.
# Product version __version__

import argparse
import getpass
import json
import os
import pathlib
import platform
import subprocess

import requests

SERVER = os.getenv("STASH_SERVER", default="stash.veritas.com")
USERNAME = os.getenv("STASH_USERNAME")

TOKEN_FILE = pathlib.Path.home() / ".vupc-stash-rest-token"

STASH_PROJECT = "VUPC"
STASH_REPO = "vps-backend"
MAX_COMMENT_LEN = 10 * 1024

ALL_PRS_URL = f"https://{SERVER}/rest/api/1.0/projects/{STASH_PROJECT}/repos/{STASH_REPO}/pull-requests"

# treat commits with these many builds as not requiring further
# investigation
MAX_BUILDS = 3


class TestFailure(Exception):
    def __init__(self, returncode, output, errors):
        self.returncode = returncode
        self.output = output
        self.errors = errors


def is_valid(token):
    r = requests.get(ALL_PRS_URL, auth=(token["username"], token["password"]))
    return r.status_code != 401


def stash_auth():
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE) as in_stream:
            token = json.load(in_stream)
        if is_valid(token):
            return (token["username"], token["password"])

    if USERNAME is None:
        raise Exception("set STASH_USERNAME")

    password = getpass.getpass(f"Enter password for {USERNAME}: ")
    r = requests.get(
        f"https://{SERVER}/rest/auth-token/1.0/user/get-rest-token",
        auth=(USERNAME, password),
    )
    r.raise_for_status()
    resp = r.json()

    token = {
        "username": USERNAME,
        "password": resp["token"],
        "expiry": resp["expiry"],
    }
    with open(TOKEN_FILE, "w") as out_stream:
        json.dump(token, out_stream)
    return (USERNAME, resp["token"])


def session():
    s = requests.session()
    s.headers.update({"X-Atlassian-Token": "nocheck", "Accept": "application/json"})
    s.auth = stash_auth()
    return s


def report_build_status(s, result_key, commit_id, result, url=f"https://{SERVER}"):
    status_url = f"https://{SERVER}/rest/build-status/1.0/commits/{commit_id}"
    postdata = {"state": result, "key": result_key, "url": url}
    r = s.post(status_url, json=postdata)
    r.raise_for_status()


def run_make():
    p = subprocess.Popen(["make"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (output, err) = p.communicate()
    if p.returncode != 0:
        print(f"build failed, return code: {p.returncode}")
        print(output.decode("utf-8"))
        print(err.decode("utf-8"))
        raise TestFailure(p.returncode, output, err)
    return output


def get_commit_id():
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"])
    return commit.decode("utf-8").strip()


def report_progress(s, result_key, commit_id):
    return report_build_status(s, result_key, commit_id, "INPROGRESS")


def remove_existing_comments(s, comment_ident, pr_url):
    activities_url = f"{pr_url}/activities"
    matched_comments = []
    for activity in paged_results(s, activities_url):
        if activity["action"] != "COMMENTED":
            continue
        if activity["commentAction"] != "ADDED":
            continue
        comment = activity["comment"]
        if comment_ident not in comment["text"]:
            continue
        matched_comments.append({"id": comment["id"], "version": comment["version"]})

    for comment in matched_comments:
        comment_url = f"{pr_url}/comments/{comment['id']}"
        # report, but otherwise ignore errors, we don't care if old
        # comments stay around
        r = s.delete(comment_url, params={"version": comment["version"]})
        if r.status_code not in [200, 204]:
            print(f"failed to delete existing comment: {r.text}")


def post_logs(s, comment_ident, comment_text, pr_url):
    if pr_url is None:
        return
    comments_url = f"{pr_url}/comments"
    try:
        remove_existing_comments(s, comment_ident, pr_url)
    except Exception as e:
        print("error while removing existing comments", e)
    r = s.post(comments_url, json={"text": comment_text})
    if r.status_code == 400:
        print(f"failed to post comment:\n{r.text}")
    r.raise_for_status()


def ident_for(commit_id, result_key):
    return f"ID: Commit: {commit_id} Platform: {result_key}"


def format_comment(comment_ident, output):
    output = output.decode("utf-8")[-MAX_COMMENT_LEN:]
    return f"""
{comment_ident}

```
{output}
```
"""


def format_failure_comment(comment_ident, ex):
    output = ex.output.decode("utf-8")[-MAX_COMMENT_LEN:]
    errors = ex.errors.decode("utf-8")[-MAX_COMMENT_LEN:]
    return f"""
{comment_ident}

```
{output}
```

```
{errors}
```
"""


def report_success(s, result_key, commit_id, pr_url, output):
    comment_ident = ident_for(commit_id, result_key)
    comment_text = format_comment(comment_ident, output)
    post_logs(s, comment_ident, comment_text, pr_url)
    return report_build_status(s, result_key, commit_id, "SUCCESSFUL")


def report_failure(s, result_key, commit_id, pr_url, ex):
    comment_ident = ident_for(commit_id, result_key)
    comment_text = format_failure_comment(comment_ident, ex)
    post_logs(s, comment_ident, comment_text, pr_url)
    return report_build_status(s, result_key, commit_id, "FAILED")


def paged_results(s, url):
    offset = None
    while True:
        if offset is None:
            params = None
        else:
            params = {"start": offset}
        r = s.get(url, params=params)
        r.raise_for_status()

        response = r.json()
        yield from response["values"]

        if response["isLastPage"]:
            break
        offset = response["nextPageStart"]


def get_all_prs(s):
    all_prs = dict(
        (pr["links"]["self"][0]["href"], {}) for pr in paged_results(s, ALL_PRS_URL)
    )

    for pr_url in all_prs:
        commits_url = f"{pr_url}/commits"
        r = s.get(commits_url, params={"limit": 1})
        r.raise_for_status()

        commit_id = r.json()["values"][0]["id"]
        all_prs[pr_url]["commit"] = commit_id

    return all_prs


def identify_pull_request(s, commit_id):
    all_prs = get_all_prs(s)
    for pr_url, pr_info in all_prs.items():
        if commit_id == pr_info["commit"]:
            return pr_url
    print(f"no PR found for commit id {commit_id}, logs will not be posted")
    return None


def get_unbuilt_commits(s, result_key, done_statuses):
    all_head_commits = [pr_info["commit"] for pr_info in get_all_prs(s).values()]
    unbuilt_commits = set(all_head_commits)

    multi_stat_url = f"https://{SERVER}/rest/build-status/1.0/commits/stats"
    r = s.post(multi_stat_url, json=all_head_commits)
    r.raise_for_status()
    response = r.json()

    for commit, commit_state in response.items():
        if commit_state["successful"] + commit_state["failed"] == MAX_BUILDS:
            unbuilt_commits.remove(commit)

    # unbuilt_commits don't have enough successful builds. check if
    # the current platform is what's missing.
    commits_to_build = set()
    for commit in unbuilt_commits:
        commit_stat_url = f"https://{SERVER}/rest/build-status/1.0/commits/{commit}"
        existing_builds = [
            build
            for build in paged_results(s, commit_stat_url)
            if build["key"] == result_key and build["state"] in done_statuses
        ]
        if not existing_builds:
            commits_to_build.add(commit)

    return commits_to_build


def checkout_commit(commit_id):
    subprocess.check_call(["git", "remote", "update"])
    subprocess.check_call(["git", "checkout", commit_id])
    subprocess.check_call(["git", "clean", "-dfx", "-e", "data/master-servers"])


def main():
    parser = argparse.ArgumentParser(description="report build status")
    parser.add_argument(
        "--no-report",
        action="store_false",
        dest="report",
        help="don't report results to stash",
    )
    parser.add_argument(
        "--build-all-the-things",
        action="store_true",
        dest="all_unbuilt",
        help="run for all unbuilt PRs rather than just what's checked out",
    )
    parser.add_argument(
        "--also-inprogress",
        action="store_true",
        dest="also_inprogress",
        help="Treat INPROGRESS build status as unbuilt",
    )
    args = parser.parse_args()

    s = session()
    result_key = platform.system()

    if args.all_unbuilt:
        if args.also_inprogress:
            done_statuses = set(["SUCCESSFUL", "FAILED"])
        else:
            done_statuses = set(["SUCCESSFUL", "FAILED", "INPROGRESS"])

        unbuilt_commits = get_unbuilt_commits(s, result_key, done_statuses)
        need_checkout = True
        print("Will build the following commits:")
        for commit_id in unbuilt_commits:
            print(f"  {commit_id}")
    else:
        unbuilt_commits = [get_commit_id()]
        need_checkout = False

    for commit_id in unbuilt_commits:
        if need_checkout:
            checkout_commit(commit_id)
        pr_url = identify_pull_request(s, commit_id)
        print(f"running build for commit {commit_id} on platform {result_key}")
        if args.report:
            report_progress(s, result_key, commit_id)
        try:
            output = run_make()
            if args.report:
                report_success(s, result_key, commit_id, pr_url, output)
        except TestFailure as ex:
            if args.report:
                report_failure(s, result_key, commit_id, pr_url, ex)


if __name__ == "__main__":
    main()
