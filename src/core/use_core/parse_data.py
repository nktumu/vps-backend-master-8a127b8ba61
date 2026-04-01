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
"""
This should be run on the remote server from within ~/data_converter.

This contains methods for parsing run sets at every level of the hierarchy:
- parse_run_set() calls...
  - parse_vmstat_detail()
  - parse_throughput_average()
  - parse_run(), which calls...
    - parse_top_5()
"""
import pandas as pd

import pathlib
import re
import sys
from typing import Tuple


def parse_run_set(dir_path: pathlib.Path) -> pd.DataFrame:
    print(dir_path)
    print("Starting parse_run_set()")
    print()
    for item in dir_path.iterdir():
        if item.name.startswith("eagapp"):
            print(item)
    print()
    print()
    return pd.concat(
        (
            parse_run(dir)
            for dir in dir_path.iterdir()
            if dir.name.startswith("eagapp") and "autosupport" not in dir.name
        ),
        axis=0,
    )


def parse_run(dir_path: pathlib.Path) -> pd.DataFrame:
    if not dir_path.is_dir():
        raise ValueError("Must provide a valid directory path.")
    operation, num_streams, dedup_ratio, run_timestamp = get_data_from_eagapp_dir_name(
        dir_path.name
    )

    top_df = parse_top_5(dir_path / "top.5")
    top_df["operation"] = operation
    top_df["num_streams"] = num_streams
    top_df["dedup_ratio"] = dedup_ratio
    top_df["run_timestamp"] = run_timestamp

    return top_df


def get_data_from_eagapp_dir_name(dir_name: str) -> Tuple[int, float, pd.Timestamp]:
    regex = r"eagapp[a-z\d]+_([a-z]+)_(\d+)str_(\d+)ded_[a-z]*(?:\d_)?(\d+)"
    print("eagapp dir name: " + dir_name)
    m = re.match(regex, dir_name)
    operation, num_streams_str, dedup_ratio_int_str, run_timestamp_str = m.groups()
    return (
        operation,
        int(num_streams_str),
        float(int(dedup_ratio_int_str) / 100),
        pd.Timestamp(run_timestamp_str),
    )


def parse_top_5(top_5_path):
    """top.5 looks like a bunch of top snapshots stacked on top of each other."""
    print(f"Parsing {top_5_path}")
    print()
    top_data_column_names = [
        "snapshot_index",
        "spoold_mem_fraction",
        "spad_mem_fraction",
        "total_mem",
        "free_mem",
        "used_mem",
        "buff_cache_mem",
        "total_swap",
        "free_swap",
        "used_swap",
        "avail_mem",
    ]
    df = pd.DataFrame(columns=top_data_column_names, dtype=int)
    df["spoold_mem_fraction"] = df["spoold_mem_fraction"].astype(float)
    df["spad_mem_fraction"] = df["spad_mem_fraction"].astype(float)

    mem_regex = r"KiB Mem :\s+(\d+)[\+\s]total,\s+(\d+)[\+\s]free,\s+(\d+)[\+\s]used,\s+(\d+)[\+\s]buff/cache"
    swap_regex = r"KiB Swap:\s+(\d+)[\+\s]total,\s+(\d+)[\+\s]free,\s+(\d+)[\+\s]used\.\s+(\d+)[\+\s]avail Mem"
    with open(top_5_path, "r") as f:
        record = {}
        snapshot_index = 0
        for line in f:
            if line.startswith("KiB Mem"):
                # "KiB Mem" lines are used to delineate the start of a new record.
                if record:
                    # We need to turn the record into a data frame for Pandas to
                    # respect dtypes.
                    df = df.append(pd.DataFrame(record, index=[0]), ignore_index=True)
                record = dict.fromkeys(top_data_column_names)
                snapshot_index += 1

                # Actually parsing the line.
                m = re.match(mem_regex, line)
                total, free, used, buff_cache = [int(x) for x in m.groups()]
                record["snapshot_index"] = snapshot_index
                record["total_mem"] = total
                record["free_mem"] = free
                record["used_mem"] = used
                record["buff_cache_mem"] = buff_cache
            elif line.startswith("KiB Swap"):
                m = re.match(swap_regex, line)
                total, free, used, avail = [int(x) for x in m.groups()]
                record["total_swap"] = total
                record["free_swap"] = free
                record["used_swap"] = used
                record["avail_mem"] = avail
            elif " spoold" in line:
                record["spoold_mem_fraction"] = float(line.split()[-3]) / 100
            elif " spad" in line:
                record["spad_mem_fraction"] = float(line.split()[-3]) / 100

        return df


if __name__ == "__main__":
    input_path = sys.argv[1]
    output_name = sys.argv[2]

    parse_run_set(pathlib.Path(input_path)).to_csv(output_name, index=False)
