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

import os
import re


def parse_vmstat(filename):
    vmstat = {}
    with open(filename) as in_stream:
        headers = None
        for line in in_stream:
            parts = line.split()
            # verify that format is as expected
            assert parts[5] == ":::"
            assert parts[7] == ":-"

            if "procs" in line:
                continue

            if "swpd" in line:
                headers = parts[8:]
                continue

            timestamp = int(parts[6])
            vals = [int(s) for s in parts[8:]]
            vmstat[timestamp] = dict(zip(headers, vals))
            vmstat[timestamp]["filename"] = filename
    return vmstat


def parse_top(filename):
    proc_counts = {}

    with open(filename) as top_stream:
        for line in top_stream:
            parts = line.split()
            process = parts[-1]
            if process not in ["bpdbm", "java", "vnetd", "NB_dbsrv"]:
                continue
            timestamp = int(parts[6])
            if timestamp not in proc_counts:
                proc_counts[timestamp] = {"filename": filename, "cpu": 0}
            if process not in proc_counts[timestamp]:
                proc_counts[timestamp][process] = 0
            proc_counts[timestamp][process] += int(parts[-4])

    return proc_counts


MEM_RE = re.compile("([0-9]+)([mg]?)")


def convert_mem(str_mem):
    match_obj = MEM_RE.match(str_mem)
    val = int(match_obj.group(1))
    unit = match_obj.group(2)
    if unit == "":
        return val
    elif unit == "m":
        return val * 1024
    elif unit == "g":
        return val * 1024 * 1024


def parse_top_memory(filename, process_names):
    memories = {}

    with open(filename) as top_stream:
        for line in top_stream:
            parts = line.split()
            process = parts[-1]
            if process not in process_names:
                continue
            timestamp = int(parts[6])
            if timestamp not in memories:
                memories[timestamp] = {"filename": filename, "mem": 0}
            if process not in memories[timestamp]:
                memories[timestamp][process] = 0
            memories[timestamp][process] += convert_mem(parts[13])

    return memories


def parse_meminfo(filename):
    data = {}
    with open(filename) as meminfo_stream:
        fields = []
        for line in meminfo_stream:
            parts = line.split(",")
            if not fields:
                fields = parts
                continue
            values = [int(p) for p in parts]
            ts = values[0]
            data[ts] = dict(zip(fields, values))
    return data


def parse_all(basedir, pattern, parse_func, *args):
    full_result = {}
    for dirpath, _dirnames, filenames in os.walk(basedir):
        if pattern not in filenames:
            continue
        this_file = os.path.join(dirpath, pattern)
        this_result = parse_func(this_file, *args)
        full_result.update(this_result)
    return full_result


def parse_all_vmstat(basedir):
    return parse_all(basedir, "vmstat.txt", parse_vmstat)


def parse_all_top(basedir):
    return parse_all(basedir, "top.txt", parse_top)


def parse_all_process_memories(basedir, processes):
    return parse_all(basedir, "top.txt", parse_top_memory, processes)


def parse_memory_overhead(basedir):
    return parse_all(basedir, "meminfo.txt", parse_meminfo)
