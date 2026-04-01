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

import xlsxwriter
from xlsxwriter.worksheet import Worksheet

from use_core import constants
from use_core import package_version
from use_core.policy import (
    NumberPolicyNoUpperBound,
    DecimalPolicy,
    ChoicePolicy,
)

LIMITATIONS_TEXT = [
    "This workbook can only size a single site correctly.  "
    "Scenarios involving multiple sites require separate sizing "
    "for each site.",
    "The performance data used in Flex Scale sizing does not include "
    "cloud replication.  The calculated #nodes and #clusters do not "
    "account for MSDP-C resource requirements.",
]

# A note on the philosophy of the Excel formulae in this module.  The
# goal is that the cells for year 1 can be copied as-is into the
# columns for other years and everything would work correctly.  The
# following two techniques make this work:
#
# - use references to "current" column where applicable.  The COLUMN
#   function provides the number of the current column.  Combining
#   this with the ADDRESS and INDIRECT functions gets us most of the
#   way.
#
# - figure out what year the current column refers to, so that
#   corresponding values can be looked up from data tables.  The
#   `year_for_current_col` helper function has the formula that deals
#   with this.
#
# Once the formulae are constructed, the remaining piece is simply to
# set appropriate names for all the relevant ranges.  The year 1
# columns are labeled as the "source" (in the `_create_names`
# function).  After sizing, the other columns are cleared, and the
# "src" formulae are copied over.


def year_for_current_col():
    """
    Return year number for current column.

    This is based on the layout of the flexscale sheets, which has two
    columns per year, starting from column C.
    """
    return "(COLUMN() - 3) / 2 + 1"


def row_in_col(row_num, col_offset=0):
    """
    Return reference to cell in current column at the specified row.

    If a column offset (col_offset) is provided, the reference will be
    to the column at that offset from current column.
    """
    return f"INDIRECT(ADDRESS({row_num},COLUMN()+{col_offset}))"


def _create_names(book, tables, prefix, sheet_name):
    for name, (first_row, last_row) in tables.items():
        src_range_name = f"{prefix}_src_{name}"
        src_range_start = xlsxwriter.utility.xl_rowcol_to_cell(
            first_row, 2, row_abs=True, col_abs=True
        )
        src_range_end = xlsxwriter.utility.xl_rowcol_to_cell(
            last_row - 1, 3, row_abs=True, col_abs=True
        )
        dst_range_name = f"{prefix}_{name}"
        dst_range_start = xlsxwriter.utility.xl_rowcol_to_cell(
            first_row, 4, row_abs=True, col_abs=True
        )
        dst_range_end = xlsxwriter.utility.xl_rowcol_to_cell(
            last_row - 1, 11, row_abs=True, col_abs=True
        )
        book.define_name(
            src_range_name,
            f"='{sheet_name}'!{src_range_start}:{src_range_end}",
        )
        book.define_name(
            dst_range_name,
            f"='{sheet_name}'!{dst_range_start}:{dst_range_end}",
        )


def flex_scale_totals_writer(writer, sheet: Worksheet):
    """
    Write out the contents of the Flex Scale Totals sheet.

    This function is a CustomDataProvider.
    """
    wipe_tables = {}
    wrapped_text = writer.workbook.add_format()
    wrapped_text.set_text_wrap()

    row = 0
    sheet.write(row, 2, "NetBackup Flex Scale Sizing Per Year")

    row += 2
    first_row = row
    sheet.merge_range(
        first_row=row,
        first_col=0,
        last_row=row + 1,
        last_col=1,
        data="Capacity Calculations",
    )
    for yr in range(1, 6):
        sheet.merge_range(
            first_row=row,
            first_col=yr * 2,
            last_row=row,
            last_col=1 + yr * 2,
            data=f'=_xlfn.CONCAT("Year ", {year_for_current_col()})',
        )
        sheet.write_row(
            row + 1,
            yr * 2,
            ["Capacity\nWorkload (TiB)", ""],
            wrapped_text,
        )

    row += 2

    def flex_scale_data_for_year(fld):
        year = year_for_current_col()
        range_name = f'_xlfn.CONCAT("flex_scale_{fld}_", {year})'
        return f"INDIRECT({range_name})"

    def workload_volume_for_year():
        return flex_scale_data_for_year("volume")

    def network_bw_for_year():
        return flex_scale_data_for_year("network_bw")

    def capacity_for_year():
        return flex_scale_data_for_year("capacity")

    # total number of nodes will be the product of #clusters and
    # #nodes/cluster.  The final #nodes/cluster will be the
    # combination that results in the maximum total nodes.
    total_clusters = f"{row_in_col(40)}:{row_in_col(43)}"
    clusters_per_node = f"{row_in_col(40, 1)}:{row_in_col(43, 1)}"
    total_nodes = f"{total_clusters}*{clusters_per_node}"

    for content in [
        [
            "Total Capacity Required (TiB)",
            f"=VLOOKUP({row_in_col(9)},NumberOfNodesPerClusterPerYear,COLUMN(),0)*{row_in_col(8)}",
        ],
        [
            "Total TiB/hr Required",
            f"=SUM({workload_volume_for_year()}) / (window_duration_full+window_duration_incremental) / 1024",
        ],
        ["Total Network GiB/s Required", f"=SUM({network_bw_for_year()})"],
        [
            "Total # Clusters",
            f"=MAX({row_in_col(16)}, {row_in_col(22)}, {row_in_col(35)}, $E$29)",
        ],
        [
            "# Nodes/cluster",
            f"=OFFSET({row_in_col(39, 1)},_xlfn.XMATCH(MAX({total_nodes}),{total_nodes},0,1),0)",
        ],
    ]:
        sheet.merge_range(
            first_row=row, first_col=0, last_row=row, last_col=1, data=content[0]
        )
        for yr in range(1, 6):
            sheet.write_dynamic_array_formula(row, yr * 2, row, yr * 2, content[1])
        row += 1

    sheet.merge_range(
        first_row=row,
        first_col=0,
        last_row=row + 3,
        last_col=1,
        data="# Nodes based on",
    )
    for yr in range(1, 6):
        col = yr * 2
        for dst_row, src_row, param in [
            (row, 40, "Capacity"),
            (row + 1, 41, "Backup Throughput"),
            (row + 2, 42, "Parallel Ops"),
            (row + 3, 43, "Network Bandwidth"),
        ]:
            sheet.write(
                dst_row,
                col,
                f'=IF({row_in_col(src_row)}<{row_in_col(8)},"",IF({row_in_col(src_row, 1)}<{row_in_col(9)},"","{param}"))',
            )

    row += 4
    last_row = row

    wipe_tables["summary"] = (first_row, last_row)

    sheet.write(row, 0, "Totals Based on Capacity")
    row += 1
    sheet.merge_range(
        first_row=row,
        first_col=0,
        last_row=row,
        last_col=1,
        data="Maximum Capacity Threshold",
    )
    sheet.write(row, 2, "='Flex Scale Sizing Results'!D18")

    row += 1
    first_row = row
    for content in [
        [
            "# Clusters for Capacity",
            f"=IF({row_in_col(47)}<=$B$63,1,ROUNDUP({row_in_col(47)}/$B$63,0))",
        ],
        ["Total Capacity/Cluster", f"={row_in_col(5)}/{row_in_col(8)}"],
        [
            "# Nodes/cluster for Capacity",
            f"=INDEX(_xlfn._xlws.FILTER(NumberOfNodesPerClusterPerYear,{row_in_col(51)}:{row_in_col(63)}<$B51:$B63),1,1)",
        ],
    ]:
        sheet.merge_range(
            first_row=row, first_col=0, last_row=row, last_col=1, data=content[0]
        )
        for yr in range(1, 6):
            sheet.write(row, yr * 2, content[1])
        row += 1
    last_row = row
    wipe_tables["totals_capacity"] = (first_row, last_row)

    row += 1
    sheet.write(row, 0, "Totals Based on Backup Throughput")
    row += 1
    sheet.merge_range(
        first_row=row,
        first_col=0,
        last_row=row,
        last_col=1,
        data="Max Throughput Threshold",
    )
    sheet.write(row, 2, "='Flex Scale Sizing Results'!D19")
    row += 1

    first_row = row
    for content in [
        [
            "# Clusters for TB/hr",
            f"=IF({row_in_col(6)}<=$C$26,1,ROUNDUP({row_in_col(6)}/$C$26,0))",
        ],
        ["Total TB/hr/cluster", f"={row_in_col(6)}/{row_in_col(8)}"],
        ["# Nodes/cluster for Throughput", f"={row_in_col(99)}"],
    ]:
        sheet.merge_range(
            first_row=row, first_col=0, last_row=row, last_col=1, data=content[0]
        )
        for yr in range(1, 6):
            sheet.write(row, yr * 2, content[1])
        row += 1
    last_row = row
    wipe_tables["totals_throughput"] = (first_row, last_row)

    for content in [
        ["Avg weighted DD Savings", "=average_dedup_rate"],
        [
            "Max Throughput per Cluster",
            "=MAX(OFFSET(flex_scale_throughput, 1, 1, ROWS(flex_scale_throughput)-1, 1))",
        ],
    ]:
        sheet.merge_range(
            first_row=row, first_col=0, last_row=row, last_col=1, data=content[0]
        )
        sheet.write(row, 2, content[1])
        row += 1

    sheet.write(row, 0, "Totals Based on Max Parallel Streams and Instant Access")
    row += 1

    max_nstreams_column = (
        "OFFSET(flex_scale_throughput, 1, 2, ROWS(flex_scale_throughput) - 1, 1)"
    )
    max_nstreams_per_cluster = f"MAX({max_nstreams_column})"

    for content in [
        [
            "Max Required Parallel Streams (PS) & Instant Access (IA)",
            "='Flex Scale Sizing Results'!D20",
        ],
        [
            "# Clusters for Max PS and IA",
            f"=MAX(1, ROUNDUP(E28 / {max_nstreams_per_cluster}, 0))",
        ],
        ["Max # PS & IA / cluster", "=E28/E29"],
        [
            "#Nodes/cluster for Max PS and IA",
            f"=_xlfn.XMATCH(E30, {max_nstreams_column},1,2) + 3",
        ],
    ]:
        sheet.merge_range(
            first_row=row, first_col=0, last_row=row, last_col=3, data=content[0]
        )
        sheet.write(row, 4, content[1])
        row += 1

    sheet.write(row, 0, "Totals Based on Network Throughput")
    row += 1
    sheet.merge_range(
        first_row=row,
        first_col=0,
        last_row=row,
        last_col=1,
        data="Maximum Network Threshold",
    )
    sheet.write(row, 2, "=flex_scale_network_threshold")
    sheet.merge_range(
        first_row=row, first_col=3, last_row=row, last_col=4, data="Per Node GiB/s:"
    )
    sheet.write_row(
        row,
        5,
        [
            "='Flex Scale Sizing Results'!D21",
            '=IF(F33="10 Gb",(20*C33)/8.583690987,(50*C33)/8.583690987)',
            None,
            "Cluster Max",
            "=G33*16",
        ],
    )
    row += 1
    first_row = row
    for content in [
        ["Max Throughput Requirement", f"=SUM({network_bw_for_year()})"],
        [
            "#Clusters for Network Throughput",
            f"=MAX(1,ROUNDUP({row_in_col(34)}/$J$33,0))",
        ],
        ["Total NW throughput/cluster", f"={row_in_col(34)}/{row_in_col(35)}"],
        [
            "#Nodes/cluster for NW throughput",
            f'=_xlfn.XMATCH({row_in_col(36)}, INDIRECT(IF($F$33="10 Gb", "flex_scale_nw_throughput_10g", "flex_scale_nw_throughput_25g")), 1, 2) + 3',
        ],
    ]:
        sheet.merge_range(
            first_row=row, first_col=0, last_row=row, last_col=1, data=content[0]
        )
        for yr in range(1, 6):
            sheet.write(row, yr * 2, content[1])
        row += 1
    last_row = row
    wipe_tables["totals_network"] = (first_row, last_row)

    sheet.write(row, 0, "Total Clusters and Nodes Based on Individual Values")
    row += 1
    first_row = row
    for yr in range(1, 6):
        sheet.write_row(row, yr * 2, ["#clusters", "#nodes"])
    row += 1
    for content in [
        ["Capacity", f"={row_in_col(16)}", f"={row_in_col(18, -1)}"],
        ["Backup Throughput", f"={row_in_col(22)}", f"={row_in_col(24, -1)}"],
        ["Parallel Ops", "=$E$29", "=$E$31"],
        ["Network Bandwidth", f"={row_in_col(35)}", f"={row_in_col(37, -1)}"],
    ]:
        sheet.merge_range(
            first_row=row, first_col=0, last_row=row, last_col=1, data=content[0]
        )
        for yr in range(1, 6):
            sheet.write_row(row, yr * 2, content[1:])
        row += 1
    last_row = row
    wipe_tables["clusters_nodes"] = (first_row, last_row)

    row += 1
    sheet.write(row, 0, "Capacity Maximum Calculations")
    row += 1
    first_row = row
    for content in [
        ["NonFS Total Capacity Reqd", f"=SUM({capacity_for_year()})"],
        ["Total incl Extra assuming 16 nodes", f"={row_in_col(46)}+$B$79+$C$79"],
        ["NonFS Capacity/cluster", f"={row_in_col(46)}/{row_in_col(8)}"],
    ]:
        sheet.merge_range(
            first_row=row, first_col=0, last_row=row, last_col=1, data=content[0]
        )
        for yr in range(1, 6):
            sheet.write(row, yr * 2, content[1])
        row += 1
    last_row = row
    wipe_tables["capacity_maximums"] = (first_row, last_row)

    row += 1
    heading_row = ["# Nodes", "Max Capacity (TiB) to Size For", "Total Required"]
    heading_row.extend([""] * 9)
    sheet.write_row(row, 0, heading_row)
    row += 1
    first_row = row

    usable_tib_col_heading = (
        '_xlfn.CONCAT("Usable TiB", " ", flex_scale_appliance_model)'
    )
    usable_tib_col = f"_xlfn.XMATCH({usable_tib_col_heading}, OFFSET(flex_scale_available_storage, 0, 0, 1))"

    for n in range(4, 17):
        row_data = [n]
        row_data.append(
            f"=VLOOKUP(INDIRECT(ADDRESS(ROW(), COLUMN()-1,1)),flex_scale_available_storage,{usable_tib_col},FALSE)"
        )
        for yr in range(1, 6):
            row_data.append(f"={row_in_col(48)}+(B{row+17}+C{row+17})/{row_in_col(16)}")
            row_data.append("")
        sheet.write_row(row, 0, row_data)
        row += 1
    last_row = row
    wipe_tables["node_capacity_totals"] = (first_row, last_row)
    range_start = xlsxwriter.utility.xl_rowcol_to_cell(
        first_row, 0, row_abs=True, col_abs=True
    )
    range_end = xlsxwriter.utility.xl_rowcol_to_cell(
        last_row - 1, 11, row_abs=True, col_abs=True
    )
    writer.workbook.define_name(
        "NumberOfNodesPerClusterPerYear",
        f"='Flex Scale Totals'!{range_start}:{range_end}",
    )
    assert row == 63

    row += 1
    sheet.write(row, 0, "Total Extra Capacity Required Calculations")
    row += 1
    sheet.write_row(row, 0, ["# Nodes", "Full", "Incremental"])
    row += 1

    def range_for_node(table_name):
        column_for_node = f"MATCH({n},OFFSET({table_name}, 0, 0, 1)) - 1"
        num_data_rows = f"ROWS({table_name})-1"
        return f"OFFSET({table_name}, 1, {column_for_node}, {num_data_rows}, 1)"

    for n in range(4, 17):
        range_for_node_full = range_for_node("flex_scale_addl_space_full")
        range_for_node_incr = range_for_node("flex_scale_addl_space_incr")

        sheet.write_row(
            row,
            0,
            [
                n,
                f"=SUM({range_for_node_full})/1024",
                f"=SUM({range_for_node_incr})/1024",
            ],
        )
        row += 1

    row += 1
    assert row == 80

    row = 97

    header_row = [None, None]
    row_data = [None, None]
    first_row = row
    for yr in range(1, 6):
        header_row.extend([f'=_xlfn.CONCAT("Year ", {year_for_current_col()})', None])
        max_throughput_col = (
            "OFFSET(flex_scale_throughput,1,1,ROWS(flex_scale_throughput)-1,1)"
        )
        row_data.extend(
            [
                f"=_xlfn.XMATCH({row_in_col(23)}, {max_throughput_col},1,2) +3",
                None,
            ]
        )
    sheet.write_row(row, 0, header_row)
    row += 1
    sheet.write_row(row, 0, row_data)
    row += 1
    last_row = row
    wipe_tables["nodes"] = (first_row, last_row)

    _create_names(writer.workbook, wipe_tables, "flexscale_totals", "Flex Scale Totals")


def flex_scale_results_writer(writer, sheet: Worksheet):
    """
    Write out the contents of the Flex Scale Sizing Results sheet.

    This function is a CustomDataProvider.
    """
    wipe_tables = {}
    wrapped_text = writer.workbook.add_format()
    wrapped_text.set_text_wrap()

    row = 0
    # The extra new lines in the text here is to provide some padding above the
    # text that can be filled in by the buttons that are added to the sheet.
    sheet.write_row(
        row,
        0,
        [
            "\n\n\n\nPackage Date",
            package_version.package_timestamp,
            "\n\n\n\nPackage Version",
            package_version.package_version,
        ],
    )

    row += 1
    sheet.write(row, 2, "NetBackup Flex Scale Sizing Per Year")

    row += 1
    first_row = row
    sheet.merge_range(
        first_row=row,
        first_col=0,
        last_row=row + 1,
        last_col=1,
        data="Capacity Calculations",
    )
    for yr in range(1, 6):
        sheet.merge_range(
            first_row=row,
            first_col=yr * 2,
            last_row=row,
            last_col=1 + yr * 2,
            data=f'=_xlfn.CONCAT("Year ", {year_for_current_col()})',
        )
        sheet.write_row(
            row + 1,
            yr * 2,
            ["Capacity\nWorkload (TiB)", ""],
            wrapped_text,
        )

    row += 2

    def totals_ref(row_offset=0):
        return f'=INDIRECT(ADDRESS(ROW()+{row_offset}, COLUMN(),,,"Flex Scale Totals"))'

    for content in [
        ["Total Capacity Required (TiB)", totals_ref()],
        ["Total TiB/hr Required", totals_ref()],
        ["Total # Clusters", totals_ref(row_offset=1)],
        ["# Nodes/cluster", totals_ref(row_offset=1)],
    ]:
        sheet.merge_range(
            first_row=row, first_col=0, last_row=row, last_col=1, data=content[0]
        )
        for yr in range(1, 6):
            sheet.write(row, yr * 2, content[1])
        row += 1

    assert row == 8

    row += 1
    sheet.merge_range(
        first_row=row,
        first_col=0,
        last_row=row + 3,
        last_col=1,
        data="Driving factor(s) for\n#Nodes and #Clusters:",
        cell_format=wrapped_text,
    )
    for yr in range(1, 6):
        col = yr * 2
        for dst_row, src_row, param in [
            (row, 40, "Capacity"),
            (row + 1, 41, "Backup Throughput"),
            (row + 2, 42, "Parallel Ops"),
            (row + 3, 43, "Network Bandwidth"),
        ]:
            sheet.write(dst_row, col, totals_ref())
    row += 4
    assert row == 13
    last_row = row
    wipe_tables["results"] = (first_row, last_row)

    sheet.write(row, 0, "Sized Capacity Consumption Totals")
    row += 1

    total_tib_col_heading = '_xlfn.CONCAT("Total TiB", " ", flex_scale_appliance_model)'
    total_tib_col = f"_xlfn.XMATCH({total_tib_col_heading}, OFFSET(flex_scale_available_storage, 0, 0, 1))"
    total_tib_for_node = (
        f"VLOOKUP({row_in_col(8)},flex_scale_available_storage,{total_tib_col},0)"
    )
    usable_tib_col_heading = (
        '_xlfn.CONCAT("Usable TiB", " ", flex_scale_appliance_model)'
    )
    usable_tib_col = f"_xlfn.XMATCH({usable_tib_col_heading}, OFFSET(flex_scale_available_storage, 0, 0, 1))"
    usable_tib_for_node = (
        f"VLOOKUP({row_in_col(8)},flex_scale_available_storage,{usable_tib_col},0)"
    )

    first_row = row
    for content in [
        [
            "Max Usable Capacity\n(usable * capacity\nthreshold)",
            f"={total_tib_for_node}*{row_in_col(7)}",
        ],
        [
            "% of Available Capacity\nUsed at End\nof Year",
            f"={row_in_col(5)}/({usable_tib_for_node}*{row_in_col(7)})",
        ],
    ]:
        sheet.merge_range(
            first_row=row,
            first_col=0,
            last_row=row,
            last_col=1,
            data=content[0],
            cell_format=wrapped_text,
        )
        for yr in range(1, 6):
            sheet.write(row, yr * 2, content[1])
        row += 1
    assert row == 16
    last_row = row

    wipe_tables["totals"] = (first_row, last_row)

    sheet.write(row, 0, "Assumptions (Customizable)")
    row += 1

    for content in [
        [
            "Maximum Capacity Threshold",
            0.8,
            DecimalPolicy(0, 1),
            "flex_scale_capacity_threshold",
        ],
        [
            "Maximum Throughput Threshold",
            0.7,
            DecimalPolicy(0, 1),
            "flex_scale_throughput_threshold",
        ],
        [
            "Total # of Instant Access & parallel streams",
            200,
            NumberPolicyNoUpperBound(),
            "flex_scale_max_streams",
        ],
        [
            "Public network connection speed",
            "10 Gb",
            ChoicePolicy(["10 Gb", "25 Gb"]),
            "flex_scale_public_network",
        ],
        [
            "Maximum Network Throughput Threshold",
            0.8,
            DecimalPolicy(0, 1),
            "flex_scale_network_threshold",
        ],
        [
            "% Total Savings from Compression Alone",
            0.5,
            DecimalPolicy(0, 1),
            "flex_scale_compression_savings",
        ],
        [
            "% Common Data Within Same Workload Types",
            0.1,
            DecimalPolicy(0, 1),
            "flex_scale_common_data",
        ],
        [
            "Appliance Model",
            "14 TB Gen10",
            ChoicePolicy(constants.FLEXSCALE_MODELS),
            "flex_scale_appliance_model",
        ],
    ]:
        (label, value, policy, name) = content

        sheet.merge_range(
            first_row=row, first_col=0, last_row=row, last_col=2, data=label
        )
        sheet.write(row, 3, value)
        value_cell = xlsxwriter.utility.xl_rowcol_to_cell(
            row, 3, row_abs=True, col_abs=True
        )
        sheet.data_validation(value_cell, policy.policy())
        writer.workbook.define_name(
            name, f"='Flex Scale Sizing Results'!{value_cell}:{value_cell}"
        )
        row += 1

    sheet.write_url(
        row,
        0,
        "https://my.allego.com/play.do?contentId=5300851&sch=63690",
        string="MUST CLICK HERE FOR GEN10 PREREQUISITES",
    )
    row += 1

    sheet.write_url(
        row,
        0,
        "https://my.allego.com/play.do?contentId=5332727&sch=63690",
        string="MUST CLICK HERE FOR GEN11 PREREQUISITES",
    )
    row += 1

    sheet.write(row, 0, "Limitations", writer.formats["header"])
    row += 1
    for idx, text in enumerate(LIMITATIONS_TEXT):
        sheet.write(row, 0, f"{idx+1}. {text}", wrapped_text)
        row += 1

    _create_names(
        writer.workbook, wipe_tables, "flexscale_results", "Flex Scale Sizing Results"
    )
