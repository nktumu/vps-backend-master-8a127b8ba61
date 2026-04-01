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

import fnmatch
import os
import os.path
import subprocess
import sys
import zipfile

from use_core import package_version

EXCLUDE_DIRS = [
    ".git",
    ".pytest_cache",
    "__pycache__",
    "data",
    "database",
    "devtools",
    "doc",
    "images",
    "json_data",
    "json_test_data",
    "notebooks",
    "resources",
    "server",
    "test",
    "tools",
]
EXCLUDE_FILES = [
    ".coverage",
    ".dockerignore",
    ".gitignore",
    "Makefile",
    "build-models.py",
    "build-package.py",
    "compile-constants-csv.py",
    "dev-environment.yml",
    "Dockerfile",
    "*.docx",
    "Pipfile",
    "Pipfile.lock",
    "postman_collection.json",
    "pytest_sanitize.cfg",
    "readme.md",
    "report.py",
    "setup.cfg",
    "test_add_sku1.json",
    "test_add_sku2.json",
]

EXTERNAL_EXCLUDE_DIRS = EXCLUDE_DIRS
EXTERNAL_EXCLUDE_FILES = EXCLUDE_FILES + [
    "root-certs.pem",
]

STAMP_FILENAME = ".sourcestamp"

PREFIX = "vps-backend/"

VERS = f"{package_version.package_product_name}-{package_version.package_version}"

FILENAME_MAPS = {
    "documentation.pdf": f"{VERS}-documentation.pdf",
    "quick_start.pdf": f"{VERS}-quick_start.pdf",
    "troubleshooting.pdf": f"{VERS}-troubleshooting.pdf",
    "whats_new.pdf": f"{VERS}-whats_new.pdf",
}

STANDARD_FILENAME_MAPS = {
    "USE-1.0.xlsm": f"{VERS}.xlsm",
    "models.json": "models.json",
    "sku.json": "sku.json",
    "workload-attributes.json": "workload-attributes.json",
    "USE-1.0-teradata.xlsm": None,
    "models-teradata.json": None,
    "sku-teradata.json": None,
    "workload-attributes-teradata.json": None,
}

TERADATA_FILENAME_MAPS = {
    "USE-1.0.xlsm": None,
    "models.json": None,
    "sku.json": None,
    "workload-attributes.json": None,
    "USE-1.0-teradata.xlsm": f"{VERS}.xlsm",
    "models-teradata.json": "models.json",
    "sku-teradata.json": "sku.json",
    "workload-attributes-teradata.json": "workload-attributes.json",
}


def apply_exclusions(in_list, excl_list):
    for excl in excl_list:
        removals = [
            candidate for candidate in in_list if fnmatch.fnmatch(candidate, excl)
        ]
        for removal in removals:
            in_list.remove(removal)


class InternalExcluder:
    def apply_dir_exclusions(self, dirs):
        apply_exclusions(dirs, EXCLUDE_DIRS)

    def apply_file_exclusions(self, files):
        apply_exclusions(files, EXCLUDE_FILES)


class ExternalExcluder:
    def apply_dir_exclusions(self, dirs):
        apply_exclusions(dirs, EXTERNAL_EXCLUDE_DIRS)

    def apply_file_exclusions(self, files):
        apply_exclusions(files, EXTERNAL_EXCLUDE_FILES)


def build_archive_name(src_file, name_map):
    for suffix, target in name_map.items():
        if not src_file.endswith(suffix):
            continue
        if not target:
            return None
        dirname = os.path.dirname(src_file)
        return os.path.join(PREFIX, dirname, target)
    return PREFIX + src_file


def update_product_version(src_file, file_contents):
    pattern_str = "__version__"
    replace_str = VERS
    file_contents = file_contents.replace(
        str.encode(pattern_str), str.encode(replace_str)
    )
    return file_contents


def sourcestamp():
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"])
    with open(STAMP_FILENAME, "wb") as stamp_stream:
        stamp_stream.write(revision)


def package(target_file, excluder, name_mapper):
    target_stream = zipfile.ZipFile(target_file, "w", zipfile.ZIP_DEFLATED)
    root_path = "."
    for dirpath, dirs, files in os.walk(root_path):
        excluder.apply_dir_exclusions(dirs)
        excluder.apply_file_exclusions(files)
        for filename in files:
            src_file = os.path.join(dirpath, filename)
            archived_name = build_archive_name(
                os.path.relpath(src_file, root_path), name_mapper
            )
            if not archived_name:
                continue
            with open(src_file, "rb") as src_stream:
                file_contents = src_stream.read()
            if src_file.endswith((".ps1", ".py", ".sh", "Makefile")):
                file_contents = update_product_version(src_file, file_contents)
            target_stream.writestr(archived_name, file_contents)
    target_stream.close()


PACKAGES = [
    (f"{VERS}.zip", ExternalExcluder(), FILENAME_MAPS | STANDARD_FILENAME_MAPS),
    (
        f"{VERS}-internal.zip",
        InternalExcluder(),
        FILENAME_MAPS | STANDARD_FILENAME_MAPS,
    ),
    (
        f"{VERS}-teradata.zip",
        ExternalExcluder(),
        FILENAME_MAPS | TERADATA_FILENAME_MAPS,
    ),
    (
        f"{VERS}-internal-teradata.zip",
        InternalExcluder(),
        FILENAME_MAPS | TERADATA_FILENAME_MAPS,
    ),
]


def do_package():
    sourcestamp()
    for (target_basename, excluder, filename_maps) in PACKAGES:
        target_file = os.path.join("..", target_basename)
        if os.path.exists(target_file):
            raise Exception(f"refusing to overwrite existing file {target_file}")
        package(target_file, excluder, filename_maps)
        print(f"wrote {target_file}")


def do_ensureclean():
    b_output = subprocess.check_output(
        ["git", "clean", "-d", "-x", "-e", "data/master-servers", "--dry-run"]
    )
    s_output = b_output.decode("utf-8")
    if s_output:
        print(s_output)
        print("Working directory is not clean, not building package")
        sys.exit(1)


def do_ensureclean_force():
    b_output = subprocess.check_output(
        ["git", "clean", "-d", "-x", "-f", "-e", "data/master-servers"]
    )
    s_output = b_output.decode("utf-8")
    print(s_output)


WORK_FUNCS = {
    "package": do_package,
    "ensureclean": do_ensureclean,
    "ensureclean-force": do_ensureclean_force,
}


def main(args):
    return WORK_FUNCS[args[0]]()


if __name__ == "__main__":
    main(sys.argv[1:])
