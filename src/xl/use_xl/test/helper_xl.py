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

import collections

from use_core import packing
from use_core import utils
from use_xl import connection
from use_xlwriter import xlwriter

# column index of Storage Lifecycle Policies sheet
SLP_NAME_COL = "A"
DOMAIN_COL = "B"
SITE_COL = "C"
DR_DEST_COL = "D"
IMG_LOCATION_COL = "E"
DR_INCR = "I"
DR_MONTHLY = "K"

# column index of Workloads sheet
WORKLOAD_NAME_COL = "A"
WORKLOAD_TYPE_COL = "B"
FETB_COL = "D"
SLP_COL = "E"
WORKLOAD_ISOLATION_COL = "F"
# Remove below when Universal Share is ready
GROWTH_RATE_COL = "K"
DAILY_CHANGE_RATE_COL = "O"
NUMBER_OF_FILES_PER_FETB = "P"
ONE_PAST_COL = "T"
# Uncomment below when Universal Share is ready
# GROWTH_RATE_COL = "L"
# DAILY_CHANGE_RATE_COL = "M"
# NUMBER_OF_FILES_PER_FETB = "Q"
# ONE_PAST_COL = "U"


def clear_data(sheet):
    sheet.range("A2").expand(mode="table").clear_contents()


def workload_to_excel(slp_sheet, wk_sheet, workloads):
    clear_data(slp_sheet)
    clear_data(wk_sheet)

    slp_key_list = [col.key for col in xlwriter.storage_lifecycle_policies_columns()]
    wk_key_list = [col.key for col in xlwriter.workloads_columns()]

    # set arbitrary slp names
    for idx, w in enumerate(workloads):
        w["slp_name"] = f"SLP {idx}"

    map_data_to_sheet(slp_sheet, slp_key_list, workloads)
    map_data_to_sheet(wk_sheet, wk_key_list, workloads)


def map_data_to_sheet(sheet, key_list, workloads):
    rows = []
    for w in workloads:
        row = []
        row_data = {}
        for key, val in w.items():
            if key in key_list:
                if isinstance(val, utils.Size):
                    row_data[key] = val.value
                else:
                    row_data[key] = str(val)
        for key in key_list:
            row.append(row_data.get(key))
        rows.append(row)

    sheet.range("A2").value = rows


def assert_sites_in_result(sheet, expected_sites):
    sites = set()

    col = 4
    while True:
        region = sheet.range((4, col)).value
        if region is None:
            break
        sites.add(region)
        col += 1

    assert sites == set(expected_sites)


def workloads_skipped(sheet):
    errors_range = sheet.range("A1:B1").expand("down").value
    errors_header, *errors_values = errors_range
    assert errors_header == ["Workload", "Error & Note"]
    return set(row[0] for row in errors_values)


def assert_assigned_regions_match_requested_regions(
    launch_sheet, needed_sheet, expected, prefix_domain=True
):
    """
    The regions to save, DC, SF, etc, are specified in column E of the launch sheet
    as part of the workload description.

    They are also in row 3 of the Results sheet, in column C and
    going right from there.

    The sets of regions on the two sheets should match, which this subroutine
    tests for.
    """
    launch_region_tuples = set()
    needed_regions = set()

    # first from the launch sheet
    sites_range = (
        launch_sheet.range(f"{DOMAIN_COL}1:{DR_DEST_COL}1").expand("down").value
    )
    sites_header, *sites_values = sites_range
    assert sites_header == ["Domain", "Site", "DR-dest"]
    for domain, region, dr_site in sites_values:
        if region is None:
            break
        launch_region_tuples.add((domain, region))
        if dr_site is not None and dr_site.strip():
            launch_region_tuples.add((domain, dr_site.strip()))

    if prefix_domain:
        launch_regions = set(
            f"{domain}/{site_name}" for (domain, site_name) in launch_region_tuples
        )
    else:
        launch_regions = set(site_name for (domain, site_name) in launch_region_tuples)

    shading_names = {}
    for n in needed_sheet.book.names:
        if not n.name.startswith("value_shaded_"):
            continue
        rng = n.refers_to_range.get_address()
        # each cell must only be referred to by a single name
        assert rng not in shading_names
        shading_names[rng] = n.name

    # and then site headers from the Results sheet
    needed_column_number = 4

    while True:
        site_range = needed_sheet.range((4, needed_column_number))
        region = site_range.value
        if region is None:
            break
        needed_regions.add(region)
        # all site cells should be included
        assert site_range.get_address() in shading_names
        shading_names.pop(site_range.get_address())
        needed_column_number += 1

    # no extraneous names should be present
    assert shading_names == {}

    # Verify the two sets of regions are identical.  The expected
    # parameter is a list of expected regions and should match what
    # was found in the sheets.
    assert needed_regions == launch_regions
    assert needed_regions == set(expected)


def parse_site_summary(summary_sheet):
    data = summary_sheet.used_range.value
    totals = collections.defaultdict(int)
    for row in range(4, len(data)):
        cfg, total, *rest = data[row]
        if cfg is None or total is None:
            continue
        totals[cfg] += int(total)
    return {"totals": totals}


def workload_assignments(sheet):
    wk_cols = slice(6, 9)

    (headers, *full_data) = sheet.used_range.value
    assert headers[wk_cols] == ["Workload Name", "Workload Mode", "Number of Instances"]

    primary_counts = collections.defaultdict(int)
    dr_counts = collections.defaultdict(int)
    for row in full_data:
        (wname, mode, num_inst) = row[wk_cols]
        if wname is None:
            continue
        if mode == str(packing.WorkloadMode.media_primary):
            primary_counts[wname] += num_inst
        elif mode == str(packing.WorkloadMode.media_dr):
            dr_counts[wname] += num_inst
    return primary_counts, dr_counts


def bracket(value, stride):
    group = value // stride
    if group == 0:
        return f"< {stride}"
    return f"in range {stride*group} - {stride*(group+1)-1}"


def error_summary(sheet):
    return sheet.range(connection.SUMMARY_ERROR_CELL).value
