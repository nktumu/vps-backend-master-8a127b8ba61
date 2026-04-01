#!/usr/bin/env python3
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

import pathlib
import tarfile

import requests

ROOT = pathlib.Path(".")
RAW_DATA_DIR = ROOT / "data" / "master-servers"

DOWNLOADS = [
    {
        "src": "https://use.rsv.ven.veritas.com/use/perf_data/master-servers/Backup_Baseline.tgz",
        "local_path": RAW_DATA_DIR / "Backup_Baseline.tgz",
        "marker_dir": RAW_DATA_DIR / "Backup_Baseline",
    },
    {
        "src": "https://use.rsv.ven.veritas.com/use/perf_data/master-servers/Mixed_WOrkloads.tgz",
        "local_path": RAW_DATA_DIR / "Mixed_WOrkloads.tgz",
        "marker_dir": RAW_DATA_DIR / "Mixed_WOrkloads",
    },
]


# download data
def download_data(spec):
    if spec["local_path"].exists():
        return

    RAW_DATA_DIR.mkdir(exist_ok=True)
    download_file = spec["local_path"].with_suffix(".tmp")
    with open(download_file, "wb") as out_stream:
        r = requests.get(spec["src"], stream=True, verify="root-certs.pem")
        r.raise_for_status()
        total_bytes = int(r.headers["Content-Length"])
        so_far = 0
        for chunk in r.iter_content(chunk_size=1 * 1024 * 1024):
            out_stream.write(chunk)
            so_far += len(chunk)
            print(f"downloaded {so_far} of {total_bytes} bytes")

    download_file.rename(spec["local_path"])


# extract archive
def extract_archive(spec):
    if spec["marker_dir"].exists():
        return

    print("extracting archive")
    with tarfile.open(spec["local_path"], "r") as tar:
        tar.extractall(path=RAW_DATA_DIR)


if __name__ == "__main__":
    for spec in DOWNLOADS:
        download_data(spec)
        extract_archive(spec)
