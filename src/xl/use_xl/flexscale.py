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

import bisect
import collections
import enum
import logging
from typing import List, Dict

from use_core import model_basis
from use_core import utils
from use_core import timers

from use_xl.xlutils import make_all_rows_same_length

MIN_NODES = 4
MAX_NODES = 16

STREAMS_PER_NODE_MAX = 50

STORAGE_PER_NODE = {  # TiB
    "14 TB Gen10": 102,
    "16 TB Gen11": 116,
    "20 TB Gen11": 145,
}


TableSpec = collections.namedtuple("TableSpec", ["rows", "name_only"], defaults=[False])
HeadingSpec = collections.namedtuple(
    "HeadingSpec", ["rows", "format_type", "merge_type"]
)
NumberSpec = collections.namedtuple("NumberSpec", ["rows", "format", "start_col"])


class FormatType(enum.Enum):
    sheet_heading = enum.auto()
    section_heading = enum.auto()
    highlighted_row = enum.auto()
    highlighted_column = enum.auto()


class MergeType(enum.Enum):
    none = enum.auto()
    full_width = enum.auto()
    col3 = enum.auto()


TOTALS_TABLES = {
    "capacity_maximums": TableSpec(rows=(46, 48)),
    "clusters_nodes": TableSpec(rows=(39, 43)),
    "node_capacity_totals": TableSpec(rows=(51, 63)),
    "NumberOfNodesPerClusterPerYear": TableSpec(rows=(51, 63), name_only=True),
    "nodes": TableSpec(rows=(98, 99)),
    "summary": TableSpec(rows=(3, 13)),
    "totals_capacity": TableSpec(rows=(16, 18)),
    "totals_network": TableSpec(rows=(34, 37)),
    "totals_throughput": TableSpec(rows=(22, 24)),
}

TOTALS_HEADINGS = {
    "sheet": HeadingSpec(
        rows=(1, 1), format_type=FormatType.sheet_heading, merge_type=MergeType.col3
    ),
    "summary": HeadingSpec(
        rows=(3, 4), format_type=FormatType.section_heading, merge_type=MergeType.none
    ),
    "totals_capacity": HeadingSpec(
        rows=(14, 14),
        format_type=FormatType.section_heading,
        merge_type=MergeType.full_width,
    ),
    "totals_throughput": HeadingSpec(
        rows=(20, 20),
        format_type=FormatType.section_heading,
        merge_type=MergeType.full_width,
    ),
    "totals_streams": HeadingSpec(
        rows=(27, 27),
        format_type=FormatType.section_heading,
        merge_type=MergeType.full_width,
    ),
    "totals_network": HeadingSpec(
        rows=(32, 32),
        format_type=FormatType.section_heading,
        merge_type=MergeType.full_width,
    ),
    "clusters_nodes": HeadingSpec(
        rows=(38, 38),
        format_type=FormatType.section_heading,
        merge_type=MergeType.full_width,
    ),
    "capacity_maximums": HeadingSpec(
        rows=(45, 45),
        format_type=FormatType.section_heading,
        merge_type=MergeType.full_width,
    ),
    "extra_capacity": HeadingSpec(
        rows=(65, 65),
        format_type=FormatType.section_heading,
        merge_type=MergeType.full_width,
    ),
}

TOTALS_NUMBERS = {
    "totals": NumberSpec(rows=(5, 7), format="0.00", start_col=3),
    "total_per_cluster": NumberSpec(rows=(17, 17), format="0.00", start_col=3),
    "total_tb_per_hr": NumberSpec(rows=(23, 23), format="0.00", start_col=3),
}

RESULTS_TABLES = {
    "results": TableSpec(rows=(3, 13)),
    "totals": TableSpec(rows=(15, 16)),
}

RESULTS_HEADINGS = {
    "sheet": HeadingSpec(
        rows=(2, 2), format_type=FormatType.sheet_heading, merge_type=MergeType.col3
    ),
    "results": HeadingSpec(
        rows=(3, 4),
        format_type=FormatType.section_heading,
        merge_type=MergeType.none,
    ),
    "heading_col": HeadingSpec(
        rows=(3, 25),
        format_type=FormatType.highlighted_column,
        merge_type=MergeType.none,
    ),
    "totals": HeadingSpec(
        rows=(14, 14),
        format_type=FormatType.section_heading,
        merge_type=MergeType.full_width,
    ),
    "assumptions": HeadingSpec(
        rows=(17, 17),
        format_type=FormatType.section_heading,
        merge_type=MergeType.full_width,
    ),
}

RESULTS_NUMBERS = {
    "total_required": NumberSpec(rows=(5, 6), format="0.00", start_col=3),
    "max_usable": NumberSpec(rows=(15, 15), format="0.00", start_col=3),
    "pct_used": NumberSpec(rows=(16, 16), format="0.00%", start_col=3),
    "assumptions1": NumberSpec(rows=(18, 19), format="0%", start_col=4),
    "assumptions2": NumberSpec(rows=(22, 24), format="0%", start_col=4),
}

logger = logging.getLogger(__name__)


def _avg_dedup(workload_storage_usage, year) -> float:
    """Return average dedupe rate across all workloads."""
    weighted_volumes = []
    volumes = []
    for wname, winfo in sorted(workload_storage_usage.items()):
        year_info = winfo[year]
        weekly_volume = year_info["volume"]
        dedup_rate = year_info["workload"].dedupe_ratio
        volumes.append(weekly_volume)
        weighted_volumes.append(weekly_volume * dedup_rate)
    return utils.Size.sum(weighted_volumes) / utils.Size.sum(volumes)


def _throughput_maximums(dedup_rate) -> Dict[int, List[float]]:
    """Return suitable per-node throughput maximums for the given dedup rate."""
    assert dedup_rate >= 0

    throughput_maximums = model_basis.get_flexscale_throughput()
    idx = bisect.bisect_left(throughput_maximums, (dedup_rate, []))
    (_, data) = throughput_maximums[idx - 1]

    return dict(zip(range(MIN_NODES, MAX_NODES + 1), data))


def _parallel_streams_maximums() -> Dict[int, int]:
    """Return maximum parallel streams per node."""
    return dict(
        (nodes, nodes * STREAMS_PER_NODE_MAX)
        for nodes in range(MIN_NODES, MAX_NODES + 1)
    )


@timers.record_time("writing write_flex_scale_data")
def write_flex_scale_data(sheet, mresult, workload_storage_usage):
    sheet.clear_contents()

    columns = {"capacity": [], "volume": [], "network_bw": []}

    result = []
    heading_row = ["Workload"]
    for yr in range(1, mresult.num_years + 1):
        heading_row.extend(
            [
                f"Year {yr} Weekly Volume (GiB)",
                f"Year {yr} Network Rate (GiB/s)",
                f"Year {yr} Capacity (TiB)",
            ]
        )
        columns["volume"].append((yr - 1) * 3 + 2)
        columns["network_bw"].append((yr - 1) * 3 + 3)
        columns["capacity"].append((yr - 1) * 3 + 4)
    result.append(heading_row)

    for wname, util in sorted(workload_storage_usage.items()):
        row_data = [wname]
        for y in range(1, mresult.num_years + 1):
            weekly_volume = util[y]["volume"].to_float("GiB")
            network_bw = util[y]["network_bw"].to_float("GiB")
            capacity = (
                util[y]["workload"].total_storage_for_year(y).to_float("TiB")
                * util[y]["workload"].num_instances
            )
            row_data.extend([weekly_volume, network_bw, capacity])
        result.append(row_data)

    workload_table_start = 1
    workload_table_end = len(result)
    workload_table_last_col = len(result[0])

    avg_dedup = _avg_dedup(workload_storage_usage, mresult.planning_year)
    throughput_maximums = _throughput_maximums(avg_dedup)
    parallel_streams_maximums = _parallel_streams_maximums()
    throughput_maximums_table = [
        [
            "# Nodes",
            "Max throughput",
            "Max parallel streams + instant access",
        ]
    ]
    for nodes, max_throughput in throughput_maximums.items():
        throughput_maximums_table.append(
            [nodes, max_throughput, parallel_streams_maximums[nodes]]
        )
    throughput_table_start = workload_table_end + 1
    throughput_table_end = throughput_table_start + len(throughput_maximums_table) - 1
    throughput_table_last_col = len(throughput_maximums_table[0])

    result.extend(throughput_maximums_table)

    nw_throughput_table = [
        ["# Nodes", "10 GB network", "25 GB network"],
        [4, 7.44, 18.64],
        [5, 9.3, 23.3],
        [6, 11.16, 27.96],
        [7, 13.02, 32.62],
        [8, 14.88, 37.28],
        [9, 16.74, 41.94],
        [10, 18.6, 46.6],
        [11, 20.46, 51.26],
        [12, 22.32, 55.92],
        [13, 24.18, 60.58],
        [14, 26.04, 65.24],
        [15, 27.9, 69.9],
        [16, 29.76, 74.56],
    ]
    nw_throughput_table_start = throughput_table_end + 1
    nw_throughput_table_end = nw_throughput_table_start + len(nw_throughput_table) - 1
    nw_throughput_table_last_col = len(nw_throughput_table[0])

    result.extend(nw_throughput_table)

    result.append(["Average dedupe ratio", avg_dedup])
    avg_dedup_table_end = nw_throughput_table_end + 1

    addl_space_full_table = []
    header_row = [
        "Workload",
        "% Total Savings from Compression alone",
        "% common data within workload type",
        *range(MIN_NODES, MAX_NODES + 1),
    ]
    addl_space_full_table.append(header_row)
    addl_space_full_table_start = avg_dedup_table_end + 1
    for wname, winfo in sorted(workload_storage_usage.items()):
        wkload = winfo[0]["workload"]

        row_data = [
            wname,
            "='Flex Scale Sizing Results'!$D$23",
            "='Flex Scale Sizing Results'!$D$24",
        ]
        savings_col_ref = "INDIRECT(ADDRESS(ROW(), 2))"
        common_col_ref = "INDIRECT(ADDRESS(ROW(), 3))"
        for nodes in range(MIN_NODES, MAX_NODES + 1):
            savings_factor = f"{wkload.initial_dedupe_ratio}*{savings_col_ref}"
            size_factor = f"{wkload.workload_size/1024/1024/1024}"
            formula = f"={nodes}*{savings_factor}*{size_factor}*{common_col_ref}"
            row_data.append(formula)
        addl_space_full_table.append(row_data)
    addl_space_full_table_end = (
        addl_space_full_table_start + len(addl_space_full_table) - 1
    )
    addl_space_full_table_last_col = len(addl_space_full_table[0])

    result.extend(addl_space_full_table)

    addl_space_incr_table = []
    header_row = [
        "Workload",
        "% Total Savings from Compression alone",
        *range(MIN_NODES, MAX_NODES + 1),
    ]
    addl_space_incr_table.append(header_row)
    addl_space_incr_table_start = addl_space_full_table_end + 1
    for wname, winfo in sorted(workload_storage_usage.items()):
        wkload = winfo[0]["workload"]

        row_data = [
            wname,
            "='Flex Scale Sizing Results'!$D$23",
        ]
        savings_col_ref = "INDIRECT(ADDRESS(ROW(), 2))"
        for nodes in range(MIN_NODES, MAX_NODES + 1):
            savings_factor = f"{wkload.dedupe_ratio}*{savings_col_ref}"
            size_factor = f"{wkload.workload_size/1024/1024/1024}"
            change_rate_factor = wkload.change_rate
            retention_factor = wkload.retention["local"].incremental
            formula = f"={nodes}*{savings_factor}*{size_factor}*{change_rate_factor}*{retention_factor}"
            row_data.append(formula)
        addl_space_incr_table.append(row_data)
    addl_space_incr_table_end = (
        addl_space_incr_table_start + len(addl_space_incr_table) - 1
    )
    addl_space_incr_table_last_col = len(addl_space_incr_table[0])

    result.extend(addl_space_incr_table)

    available_storage_table_header = ["# Nodes"]
    for appliance_model in sorted(STORAGE_PER_NODE):
        available_storage_table_header.extend(
            [f"Total TiB {appliance_model}", f"Usable TiB {appliance_model}"]
        )
    available_storage_table = [available_storage_table_header]
    for nodes in range(MIN_NODES, MAX_NODES + 1):
        row_data = [nodes]
        for appliance_model, model_per_node_storage in sorted(STORAGE_PER_NODE.items()):
            row_data.extend(
                [
                    model_per_node_storage * nodes,
                    "=INDIRECT(ADDRESS(ROW(), COLUMN()-1)) * flex_scale_capacity_threshold",
                ]
            )
        available_storage_table.append(row_data)
    available_storage_table_start = addl_space_incr_table_end + 1
    available_storage_table_end = (
        available_storage_table_start + len(available_storage_table) - 1
    )
    available_storage_table_last_col = len(available_storage_table[0])

    result.extend(available_storage_table)

    make_all_rows_same_length(result)

    # Unlike writing to Range.value, writing to Range.formula requires that the
    # full range be provided.  So you can use `Range("A1").value = result`, but
    # not `Range("A1").formula = result`.  It is unclear why this difference
    # exists, but it is trivial enough to produce the full range here.

    full_range = sheet.range((1, 1), (len(result), len(result[0])))
    full_range.formula = result

    sheet.range(
        (workload_table_start, 1), (workload_table_end, workload_table_last_col)
    ).name = "flex_scale_data"
    for fld, col_nums in columns.items():
        for yr in range(1, mresult.num_years + 1):
            range_name = f"flex_scale_{fld}_{yr}"
            sheet.range(
                (2, col_nums[yr - 1]), (workload_table_end, col_nums[yr - 1])
            ).name = range_name

    sheet.range(
        (throughput_table_start, 1), (throughput_table_end, throughput_table_last_col)
    ).name = "flex_scale_throughput"

    sheet.range(
        (nw_throughput_table_start, 1),
        (nw_throughput_table_end, nw_throughput_table_last_col),
    ).name = "flex_scale_nw_throughput"

    sheet.range(
        (nw_throughput_table_start + 1, 2), (nw_throughput_table_end, 2)
    ).name = "flex_scale_nw_throughput_10g"
    sheet.range(
        (nw_throughput_table_start + 1, 3), (nw_throughput_table_end, 3)
    ).name = "flex_scale_nw_throughput_25g"

    sheet.range((avg_dedup_table_end, 2)).name = "average_dedup_rate"

    sheet.range(
        (addl_space_full_table_start, 1),
        (addl_space_full_table_end, addl_space_full_table_last_col),
    ).name = "flex_scale_addl_space_full"

    sheet.range(
        (addl_space_incr_table_start, 1),
        (addl_space_incr_table_end, addl_space_incr_table_last_col),
    ).name = "flex_scale_addl_space_incr"

    sheet.range(
        (available_storage_table_start, 1),
        (available_storage_table_end, available_storage_table_last_col),
    ).name = "flex_scale_available_storage"


def _write_flex_scale_tables(tables, prefix, sheet, mresult):
    for name, table_spec in tables.items():
        first_row, last_row = table_spec.rows
        last_col = (mresult.num_years + 1) * 2
        if table_spec.name_only:
            first_col = 1
            sheet.range((first_row, first_col), (last_row, last_col)).name = name
            continue

        dst_range = f"{prefix}_{name}"
        src_range = f"{prefix}_src_{name}"
        src_formula = sheet.range(src_range).formula2

        old_dst_range = sheet.range(dst_range)
        old_dst_range.clear()

        first_row, last_row = table_spec.rows
        first_col = old_dst_range.column
        for yr in range(2, mresult.num_years + 1):
            new_dst_col = yr * 2 + 1
            new_dst_range = sheet.range(
                (first_row, new_dst_col), (last_row, new_dst_col + 1)
            )
            new_dst_range.formula2 = src_formula

        last_col = max(last_col, first_col)
        sheet.range((first_row, first_col), (last_row, last_col)).name = dst_range

    sheet.autofit()


def _format_flex_scale_headings(formats, sheet, mresult):
    last_col = (mresult.num_years + 1) * 2
    for name, format_spec in formats.items():
        (first_row, last_row) = format_spec.rows

        if format_spec.merge_type == MergeType.full_width:
            first_col = 1
        elif format_spec.merge_type == MergeType.col3:
            first_col = 3

        if format_spec.merge_type != MergeType.none:
            r = sheet.range((first_row, first_col), (last_row, last_col))
            # clear up existing merge, in case num_years has changed
            r.unmerge()
            r.merge()

        if format_spec.format_type == FormatType.highlighted_column:
            r = sheet.range((first_row, 1), (last_row, 1))
        else:
            r = sheet.range((first_row, 1), (last_row, last_col))
        f = r.font
        if format_spec.format_type == FormatType.sheet_heading:
            f.bold = True
            f.size = 20
            r.color = (217, 225, 242)
        elif format_spec.format_type == FormatType.section_heading:
            f.bold = True
            r.color = (128, 128, 128)
        elif format_spec.format_type == FormatType.highlighted_row:
            r.color = (242, 242, 242)
        elif format_spec.format_type == FormatType.highlighted_column:
            f.bold = True


def _format_flex_scale_numbers(formats, sheet, mresult):
    last_col = (mresult.num_years + 1) * 2
    for name, format_spec in formats.items():
        (first_row, last_row) = format_spec.rows
        r = sheet.range((first_row, format_spec.start_col), (last_row, last_col))
        r.number_format = format_spec.format


@timers.record_time("writing write_flex_scale_totals")
def write_flex_scale_totals(sheet, mresult):
    _write_flex_scale_tables(TOTALS_TABLES, "flexscale_totals", sheet, mresult)
    _format_flex_scale_headings(TOTALS_HEADINGS, sheet, mresult)
    _format_flex_scale_numbers(TOTALS_NUMBERS, sheet, mresult)


@timers.record_time("writing write_flex_scale_results")
def write_flex_scale_results(sheet, mresult):
    _write_flex_scale_tables(RESULTS_TABLES, "flexscale_results", sheet, mresult)
    _format_flex_scale_headings(RESULTS_HEADINGS, sheet, mresult)
    _format_flex_scale_numbers(RESULTS_NUMBERS, sheet, mresult)
