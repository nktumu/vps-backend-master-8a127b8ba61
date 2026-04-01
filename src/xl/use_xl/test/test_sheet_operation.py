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
import itertools
import sys

import pytest

from unittest.mock import patch
from use_core import appliance
from use_core import constants
from use_core import package_version
from use_core import packing

try:
    from use_xl import connection

    import end_to_end_support as etes
    import helper_xl as helper
except ImportError:
    pass


if sys.platform.startswith("linux"):
    pytest.skip("skipping non-linux tests", allow_module_level=True)

DAILY_CHANGE_RATE_COL = helper.DAILY_CHANGE_RATE_COL
DR_DEST_COL = helper.DR_DEST_COL
DR_INCR = helper.DR_INCR
DR_MONTHLY = helper.DR_MONTHLY
FETB_COL = helper.FETB_COL
GROWTH_RATE_COL = helper.GROWTH_RATE_COL
IMG_LOCATION_COL = helper.IMG_LOCATION_COL
NUMBER_OF_FILES_PER_FETB = helper.NUMBER_OF_FILES_PER_FETB
ONE_PAST_COL = helper.ONE_PAST_COL
SITE_COL = helper.SITE_COL
SLP_COL = helper.SLP_COL
SLP_NAME_COL = helper.SLP_NAME_COL
WORKLOAD_ISOLATION_COL = helper.WORKLOAD_ISOLATION_COL
WORKLOAD_NAME_COL = helper.WORKLOAD_NAME_COL
WORKLOAD_TYPE_COL = helper.WORKLOAD_TYPE_COL


def test_column_header_awareness(the_book):
    # This test just verifies that all the expected columns are where
    # we expect.  This makes it much easier to diagnose problems when
    # new columns are added, and the other tests don't have to repeat
    # these checks.
    workload_sheet_headers = [
        "FETB (TiB)",
        "Storage Lifecycle Policy",
        "Workload Isolation",
        # Uncomment below when Universal Share is ready
        # "Universal Share?",
        "Client-Side Dedup?",
        "Changed Block Tracking?",
        "Enable Single File Recovery?",
        "Accelerator?",
        "Annual Growth Rate (%)",
        "Daily Change Rate (%)",
        "Initial Dedup Rate (%)",
        "Dedup Rate (%)",
        "Dedup Rate Adl Full (%)",
        "Number of Files per FETB",
        "Number of Channels",
        "Files per Channel",
        "Log Backup Capable?",
        None,
    ]
    workload_sheet = etes.get_workloads_sheet(the_book)
    data_block = workload_sheet.range(f"{FETB_COL}1:{ONE_PAST_COL}1").value
    for idx in range(len(workload_sheet_headers)):
        assert data_block[idx] == workload_sheet_headers[idx]


def test_workload_name_generated(the_book):
    workload_sheet = etes.get_workloads_sheet(the_book)
    (workload_name, workload_type, num_clients) = (
        workload_sheet.range("A2:C2").options(numbers=int).value
    )
    assert workload_type in workload_name
    assert str(num_clients) in workload_name


@pytest.mark.parametrize(
    "sheet_name, new_row_name, batch_row_count",
    [
        (connection.WORKLOADS_SHEET, connection.WORKLOAD_NEW_ROW_NAME, 1),
        (connection.WORKLOADS_SHEET, connection.WORKLOAD_NEW_ROW_NAME, 3),
        (connection.STORAGE_LIFECYCLE_POLICIES_SHEET, connection.SLP_NEW_ROW_NAME, 1),
        (connection.STORAGE_LIFECYCLE_POLICIES_SHEET, connection.SLP_NEW_ROW_NAME, 5),
    ],
)
def test_add_rows(the_book, sheet_name, new_row_name, batch_row_count):
    """
    Test 'do_add_row' function in VBA
    """
    # Lookup the default values expected for the new row
    default_values_range = the_book.names[new_row_name].refers_to_range
    expected_new_values = default_values_range.value
    assert any(expected_new_values)
    filled_column_count = default_values_range.columns.count

    # Check for existing range
    the_sheet = etes.get_sheet_by_name(the_book, sheet_name)
    expected_rows = the_sheet.used_range.rows.count
    assert expected_rows > 0
    used_range = the_sheet.used_range.resize(column_size=filled_column_count)
    expected_data = [row.value for row in used_range.rows]

    # Add rows
    # Function do_add_line( sht_tgt_name As String,
    #                       line_src As String,
    #                       Optional op_batch As Boolean = False,
    #                       Optional line_batch As Long = 1,
    #                       Optional line_value As Variant = Null,
    #                       Optional overwrite_row As Boolean = True,
    #                       Optional target_address As String = ""
    #                       ) As Integer
    args = [sheet_name, new_row_name, False]
    if batch_row_count != 1:
        args.append(batch_row_count)
    last_row = the_book.macro("do_add_line")(*args)
    expected_data.append(expected_new_values)

    # Check for proper sheet data
    used_range = the_sheet.used_range.resize(column_size=filled_column_count)
    for expected, actual in zip(expected_data[1:], used_range.rows[1:]):
        assert expected[1:] == actual.value[1:]

    expected_rows = expected_rows + batch_row_count
    assert expected_rows == last_row

    # Test for no overwrite & target address
    used_range.columns[2].clear_contents()
    used_range.columns[4].value = "cloud"

    the_book.macro("do_add_line")(
        sheet_name,
        new_row_name,
        True,
        batch_row_count,
        "test do_add_row no overwrite ",
        False,
        "".join((str(last_row - batch_row_count + 1), ":", str(last_row))),
    )

    expected_data = [
        r[0:2]
        + (
            [None]
            if (index < last_row - batch_row_count or index + 1 > last_row)
            else [r[2]]
        )
        + [r[3]]
        + ["cloud"]
        + r[5:]
        for index, r in enumerate(expected_data)
    ]

    # Check for proper sheet data
    used_range = the_sheet.used_range.resize(column_size=filled_column_count)
    for expected, actual in zip(expected_data[1:], used_range.rows[1:]):
        assert expected[1:] == actual.value[1:]

    assert expected_rows == last_row

    # Test for yes overwrite & target address
    the_book.macro("do_add_line")(
        sheet_name,
        new_row_name,
        True,
        batch_row_count,
        "test do_add_row overwrite ",
        True,
        "".join((str(last_row - batch_row_count + 1), ":", str(last_row))),
    )
    for index, row in enumerate(expected_data):
        if index >= last_row - batch_row_count and index + 1 <= last_row:
            expected_data[index] = expected_new_values

    # Check for proper sheet data
    used_range = the_sheet.used_range.resize(column_size=filled_column_count)
    for expected, actual in zip(expected_data[1:], used_range.rows[1:]):
        assert expected[1:] == actual.value[1:]

    assert expected_rows == last_row


def test_end_to_end_production_macro_invocation(the_book):
    """

    Run the default workload(s), be sure that the requested regions
    are present in the Results sheet.

    """

    assert the_book is not None
    etes.run_packing_on_book(the_book)
    # verify there is output in the expected Results sheet
    result_sheet = etes.get_results_sheet(the_book)
    assert result_sheet is not None
    slp_sheet = etes.get_slp_sheet(the_book)
    assert slp_sheet is not None

    helper.assert_assigned_regions_match_requested_regions(
        slp_sheet, result_sheet, expected=("Domain-X/DC",)
    )


def test_flex_macro_invocation(the_book):
    assert the_book is not None
    etes.run_flex_packing_on_book(the_book)
    # verify there is output in the expected Results sheet
    result_sheet = etes.get_results_sheet(the_book)
    assert result_sheet is not None
    slp_sheet = etes.get_slp_sheet(the_book)
    assert slp_sheet is not None

    helper.assert_assigned_regions_match_requested_regions(
        slp_sheet, result_sheet, expected=("DC",), prefix_domain=False
    )


def test_end_to_end_dr_workload(the_book):
    slp_sheet = etes.get_slp_sheet(the_book)

    # fill in a DR in slp sheet
    slp_sheet.range(f"{DR_DEST_COL}2").value = ["SF", "Local+DR"]
    slp_sheet.range(f"{DR_INCR}2").value = [30, 4, 6]

    etes.run_packing_on_book(the_book)

    # verify there is output in the expected Results sheet
    result_sheet = etes.get_results_sheet(the_book)
    assert result_sheet is not None

    helper.assert_assigned_regions_match_requested_regions(
        slp_sheet, result_sheet, expected=("Domain-X/DC", "Domain-X/SF")
    )


def test_end_to_end_multiple_runs(the_book):
    etes.run_packing_on_book(the_book)

    result_sheet = etes.get_results_sheet(the_book)
    slp_sheet = etes.get_slp_sheet(the_book)

    helper.assert_assigned_regions_match_requested_regions(
        slp_sheet, result_sheet, expected=("Domain-X/DC",)
    )

    slp_sheet.range(f"{DR_INCR}2").value = [30, 4, 6]

    etes.run_packing_on_book(the_book)

    helper.assert_assigned_regions_match_requested_regions(
        slp_sheet, result_sheet, expected=("Domain-X/DC",)
    )


@pytest.mark.skip(reason="primary server sizing is now disabled")
def test_end_to_end_production_macro_invocation_extra_row_basic(the_book):
    """
    Add a second workload with a different region.  Be sure that both
    regions are used in the Results sheet.
    """
    assert the_book is not None
    # copy the first workload to the second, and change its region
    slp_sheet = etes.get_slp_sheet(the_book)
    assert slp_sheet is not None

    # data is columns including hidden columns
    slp_sheet.range("A4").value = slp_sheet.range("A3:AA3").value
    # change the region
    slp_sheet.range(f"{SITE_COL}4").value = "SF"

    workload_sheet = etes.get_workloads_sheet(the_book)
    assert workload_sheet is not None

    the_book.macro("activate_sheet")(connection.WORKLOADS_SHEET)
    the_book.macro("add_workload")()
    workload_sheet.range(f"{SLP_COL}3").value = slp_sheet.range(
        f"{SLP_NAME_COL}4"
    ).value

    etes.run_packing_on_book(the_book)

    # verify there is output in the expected Results sheet
    result_sheet = etes.get_results_sheet(the_book)
    assert result_sheet is not None

    helper.assert_assigned_regions_match_requested_regions(
        slp_sheet, result_sheet, expected=("Domain-X/DC", "Domain-X/SF")
    )

    # Capacity usage, be sure there for both workloads and that the
    # amount increases from year to year (just check years 1 and 2)

    # Verify that there are two workloads on the Workload Assigment Details sheet
    detail_sheet = etes.get_assignment_details_sheet(the_book)
    assert detail_sheet is not None

    # Get the first column, lots of lines, to search for marker for capacity details

    detail_columns = detail_sheet.range("A1:F1000").value
    capacity_row = None
    for n in range(len(detail_columns)):
        if detail_columns[n][0] == "Workload Disk Usage By Year (TB)":
            capacity_row = n
            break
    assert capacity_row is not None
    # First the label for the site
    assert detail_columns[capacity_row + 2][0] is not None
    assert detail_columns[capacity_row + 2][1] is not None
    # then the actual data
    assert detail_columns[capacity_row + 3][0] is not None
    assert detail_columns[capacity_row + 3][1] is not None
    assert detail_columns[capacity_row + 3][3] < detail_columns[capacity_row + 3][4]


def test_end_to_end_production_four_year_first_extension(the_book):
    """
    Change the first extension value on Safety Considerations sheet.

    The sizing should run to completion as expected.

    This is for VUPC-202.
    """
    assert the_book is not None

    planning_year_range = the_book.names["settings_planning_year"].refers_to_range
    # this is planning horizon
    original_value = int(planning_year_range.value)

    # some checks to be sure we have the correct row
    assert original_value == 3

    planning_year_range.value = 2

    # if packing completes without an error the test passes
    etes.run_packing_on_book(the_book)


@pytest.mark.skip(reason="primary server sizing is now disabled")
def test_end_to_end_different_appliances(the_book):
    slp_sheet = etes.get_slp_sheet(the_book)

    # add a second storage lifecycle policy
    the_book.macro("add_slp")()

    # change site for third storage lifecycle policy
    slp_sheet.range(f"{SITE_COL}4").value = "SF"

    workload_sheet = etes.get_workloads_sheet(the_book)
    # add second workload and change the storage lifecycle policy name according to storage lifecycle policy sheet
    the_book.macro("activate_sheet")(connection.WORKLOADS_SHEET)
    the_book.macro("add_workload")()
    workload_sheet.range(f"{SLP_COL}3").value = slp_sheet.range(
        f"{SLP_NAME_COL}4"
    ).value
    # assign different networks to the sites (so different appliances
    # are selected)
    sites_sheet = etes.get_sites_sheet(the_book)
    sites_sheet.range("B2").value = [
        ["5150 15TB", "", "1GbE", "1GbE", "1GbE"],
        ["5150 15TB", "", "10GbE SFP", "10GbE SFP", "10GbE SFP"],
    ]

    etes.run_packing_on_book(the_book)

    # verify there is output in the expected Results sheet
    result_sheet = etes.get_results_sheet(the_book)
    assert result_sheet is not None

    helper.assert_assigned_regions_match_requested_regions(
        slp_sheet, result_sheet, expected=("Domain-X/DC", "Domain-X/SF")
    )


def test_sites_sheet_lists_all_sites(the_book):
    activate_sheet = the_book.macro("activate_sheet")

    slp_sheet = etes.get_slp_sheet(the_book)

    # add a third storage lifecycle policy
    the_book.macro("add_slp")()

    # change site for third storage lifecycle policy, and add dr site
    slp_sheet.range(f"{SITE_COL}3").value = ["SF", "NY"]

    # verify all sites are listed
    sites_sheet = etes.get_sites_sheet(the_book)
    activate_sheet(connection.SITE_ASSIGNMENTS_SHEET)

    available_sites = set(sites_sheet.range("A2").expand("down").value)
    assert available_sites == set(["DC", "SF", "NY"])

    # reduce number of distict sites
    activate_sheet(connection.STORAGE_LIFECYCLE_POLICIES_SHEET)
    slp_sheet.range(f"{SITE_COL}3").value = ["DC", "DC"]
    activate_sheet(connection.SITE_ASSIGNMENTS_SHEET)

    assert "DC" == sites_sheet.range("A2").expand("down").value


def test_package_data_sheet(the_book):
    assert (
        the_book.names["package_date"].refers_to_range.value
        == package_version.package_timestamp
    )
    assert (
        the_book.names["package_version"].refers_to_range.value
        == package_version.package_version
    )


def test_progress_reporting_does_not_crash(the_book):
    # This test just runs sizing and verifies that it does not crash
    # if progress reporting is enabled.  It does not have any real
    # verification to do, since the progress messages do not survive
    # when sizing finishes.
    the_book.macro("activate_sheet")(connection.SITE_ASSIGNMENTS_SHEET)
    connection.do_main(
        the_book,
        progress_reporting=True,
        appliance_family=constants.ApplianceFamily.NBA,
    )


def test_skipped_full_workloads(the_book):
    workload_sheet = etes.get_workloads_sheet(the_book)
    # add second and third workload and changing the growth rate and
    # daily change rate
    the_book.macro("activate_sheet")(connection.WORKLOADS_SHEET)
    the_book.macro("add_workload")()
    the_book.macro("add_workload")()
    workload_sheet.range(f"{GROWTH_RATE_COL}2").value = workload_sheet.range(
        f"{GROWTH_RATE_COL}3"
    ).value = workload_sheet.range(f"{GROWTH_RATE_COL}4").value = ".80"
    workload_sheet.range(f"{DAILY_CHANGE_RATE_COL}2").value = workload_sheet.range(
        f"{DAILY_CHANGE_RATE_COL}3"
    ).value = workload_sheet.range(f"{DAILY_CHANGE_RATE_COL}4").value = ".80"
    # assign different networks to the sites (so different appliances
    # are selected)
    the_book.macro("activate_sheet")(connection.SITE_ASSIGNMENTS_SHEET)
    sites_sheet = etes.get_sites_sheet(the_book)
    sites_sheet.range("B2").value = [
        ["5240 4TB", "5240", "1GbE", "1GbE", "1GbE"],
    ]

    with pytest.raises(Exception) as sizer_failure:
        connection.do_main(
            the_book,
            progress_reporting=False,
            appliance_family=constants.ApplianceFamily.NBA,
        )
    assert "Sizing failed" in str(sizer_failure.value)

    # verify there is output in the Errors and Notes sheet
    # assert that all workloads are skipped and sizing is stopped
    error_sheet = etes.get_errors_and_notes_sheet(the_book)
    skipped_workloads = error_sheet.range("A1:A4").value
    assert None not in skipped_workloads


def test_workload_summary_sheet_data(the_book):
    """
    this test runs sizing and the checks wether the values in workload summary sheet
    in each year are in non decreasing order
    """
    assert the_book is not None

    slp_sheet = etes.get_slp_sheet(the_book)

    # fill in a DR in slp sheet
    dr_dest = ["SF"]
    image_location = ["Local+DR+LTR"]
    retention = [30, 4, 6, 0]
    slp_sheet.range(f"{DR_DEST_COL}2").value = dr_dest + image_location + retention * 3

    etes.run_packing_on_book(the_book)

    # verify there is output in the expected Results sheet
    workload_summary_sheet = etes.get_sheet_by_name(
        the_book, connection.WORKLOAD_SUMMARY_SHEET
    )

    assert workload_summary_sheet is not None
    val = workload_summary_sheet.range("D3").expand("right").value
    num_attributes = len(constants.WORKLOAD_SUMMARY_HEADINGS)
    years = int(len(val) / num_attributes)
    ignored_columns = set(
        constants.WORKLOAD_SUMMARY_HEADINGS.index(col_heading)
        for col_heading in [
            "Total DR Network Utilization (Mbps)",
            "Total Cloud Network Utilization (Mbps)",
        ]
    )

    for i in range(num_attributes):
        if i in ignored_columns:
            continue
        attr1 = []
        for j in range(years):
            attr1.append(val[i + j * num_attributes])
        attr2 = attr1.copy()
        attr1.sort()
        assert attr1 == attr2


def test_raw_appliance_summary_sheet_data(the_book):
    """
    this test runs sizing and the checks wether the values in workload summary sheet
    in each year are in non decreasing order
    """
    assert the_book is not None

    slp_sheet = etes.get_slp_sheet(the_book)

    # fill in a DR in slp sheet
    dr_dest = ["SF"]
    image_location = ["Local+DR+LTR"]
    retention = [30, 4, 6, 0]
    slp_sheet.range(f"{DR_DEST_COL}2").value = dr_dest + image_location + retention * 3

    etes.run_packing_on_book(the_book)

    # verify there is output in the expected Results sheet
    raw_appliance_summary_sheet = etes.get_sheet_by_name(
        the_book, connection.RAW_APPLIANCE_SUMMARY_SHEET
    )

    assert raw_appliance_summary_sheet is not None
    val = raw_appliance_summary_sheet.range("D3").expand("right").value
    attributes = (
        constants.RESOURCE_ABSOLUTE_HEADINGS
        + constants.RESOURCE_PERCENT_HEADINGS
        + constants.RESOURCE_NETWORK_HEADINGS[:5]
        + constants.STORAGE_SPACE_CALCULATION_HEADINGS[:6]
    )
    num_attributes = len(attributes)
    years = int(len(val) / num_attributes)
    ignored_columns = set(
        attributes.index(col_heading)
        for col_heading in [
            "DR-NW Transfer(Mbps)",
            "Cloud-NW Transfer(Mbps)",
        ]
    )

    for i in range(num_attributes):
        if i in ignored_columns:
            continue
        attr1 = []
        for j in range(years):
            attr1.append(val[i + j * num_attributes])
        attr2 = attr1.copy()
        attr1.sort()
        assert attr1 == attr2


@pytest.fixture(
    params=[
        {"appliance_family": constants.ApplianceFamily.NBA, "extra_workload": True},
        {"appliance_family": constants.ApplianceFamily.NBA, "extra_workload": False},
    ]
)
def partial_failure_cases(request):
    yield request.param


@pytest.mark.skip(reason="primary server sizing is now disabled")
def test_master_sizing_failure(the_book, test_master_server, partial_failure_cases):
    appliance_family = partial_failure_cases["appliance_family"]
    extra_workload = partial_failure_cases["extra_workload"]

    low_capacity_appliance = appliance.Appliance.from_json(test_master_server)

    def fake_selector(_, safety_margins=None):
        return collections.defaultdict(lambda: low_capacity_appliance)

    workload_sheet = etes.get_workloads_sheet(the_book)
    slp_sheet = etes.get_slp_sheet(the_book)
    result_sheet = etes.get_results_sheet(the_book)

    # The large workload should fail master sizing because of large
    # number of files.  Media sizing should still work.
    workload_name = workload_sheet.range(f"{WORKLOAD_NAME_COL}2").value

    workload_sheet.range(f"{FETB_COL}2").value = 50
    workload_sheet.range(f"{NUMBER_OF_FILES_PER_FETB}2").value = 10_000_000

    if extra_workload:
        # with one small workload, sizing should still work and the small
        # workload should get sized
        the_book.macro("activate_sheet")(connection.WORKLOADS_SHEET)
        the_book.macro("add_workload")()

    the_book.macro("activate_sheet")(connection.SITE_ASSIGNMENTS_SHEET)
    with patch.object(packing.SizerContext, "primary_selector", fake_selector):
        connection.do_main(
            the_book, progress_reporting=False, appliance_family=appliance_family
        )

    error_sheet = etes.get_errors_and_notes_sheet(the_book)
    skipped_workloads = error_sheet.range("A2:D3").value
    assert skipped_workloads[0][0] == workload_name
    assert (
        skipped_workloads[0][3] == f"{constants.MANAGEMENT_SERVER_DESIGNATION} Misfit"
    )
    assert skipped_workloads[1][0] is None
    if appliance_family == constants.ApplianceFamily.Flex:
        expected = ("DC",)
    else:
        expected = ("Domain-X/DC",)
    helper.assert_assigned_regions_match_requested_regions(
        slp_sheet,
        result_sheet,
        expected=expected,
        prefix_domain=(appliance_family == constants.ApplianceFamily.NBA),
    )

    # verify that workload table reports all workloads, even those
    # that were skipped
    if extra_workload:
        all_workloads = set(
            workload_sheet.range(f"{WORKLOAD_NAME_COL}2:{WORKLOAD_NAME_COL}3").value
        )
    else:
        all_workloads = set([workload_sheet.range(f"{WORKLOAD_NAME_COL}2").value])
    summary_sheet = the_book.sheets[connection.APPLIANCE_SUMMARY_SHEET]
    all_data = summary_sheet.used_range.value
    workload_table_start = [
        i for (i, row) in enumerate(all_data) if row[0] == "Workload"
    ][0]
    workload_table_data = all_data[workload_table_start + 2 :]
    workload_table_names = set(
        row[0] for row in itertools.takewhile(lambda row: row[0], workload_table_data)
    )
    assert workload_table_names == all_workloads


def test_pass_full_workloads(the_book):
    # add second and third workload
    the_book.macro("activate_sheet")(connection.WORKLOADS_SHEET)
    the_book.macro("add_workload")()
    the_book.macro("add_workload")()
    # assign different networks to the sites (so different appliances
    # are selected)
    the_book.macro("activate_sheet")(connection.SITE_ASSIGNMENTS_SHEET)
    sites_sheet = etes.get_sites_sheet(the_book)
    sites_sheet.range("B2").value = [
        ["5240 4TB", "5240", "1GbE", "1GbE", "1GbE"],
        ["5240 4TB", "5240", "10GbE SFP", "10GbE SFP", "10GbE SFP"],
    ]

    etes.run_packing_on_book(the_book)

    # verify there is no output in the Errors and Notes sheet
    error_sheet = etes.get_errors_and_notes_sheet(the_book)
    assert error_sheet.range("A2").value is None
    # verify there is output in the expected Results sheet
    result_sheet = etes.get_results_sheet(the_book)
    assert result_sheet is not None


def test_skipped_partial_workloads(the_book):
    workload_sheet = etes.get_workloads_sheet(the_book)
    # add second and third workload and changing the growth rate and
    # daily change rate
    the_book.macro("activate_sheet")(connection.WORKLOADS_SHEET)
    the_book.macro("add_workload")()
    the_book.macro("add_workload")()
    workload_sheet.range(f"{GROWTH_RATE_COL}4:{DAILY_CHANGE_RATE_COL}4").value = [
        ".80",
        ".80",
    ]
    # assign different networks to the sites (so different appliances
    # are selected)
    the_book.macro("activate_sheet")(connection.SITE_ASSIGNMENTS_SHEET)
    sites_sheet = etes.get_sites_sheet(the_book)
    sites_sheet.range("B2").value = [
        ["5240 4TB", "5240", "1GbE", "1GbE", "1GbE"],
    ]

    with pytest.raises(packing.NotifyWorkloadError) as sizer_failure:
        connection.do_main(
            the_book,
            progress_reporting=False,
            appliance_family=constants.ApplianceFamily.NBA,
        )
    assert "skipped from media server sizing" in str(sizer_failure.value)

    # verify there is output in the Errors and Notes sheet
    # assert that all workloads are skipped and sizing is stopped
    error_sheet = etes.get_errors_and_notes_sheet(the_book)
    skipped_workloads = error_sheet.range("A1:A2").value
    assert None not in skipped_workloads


@pytest.mark.skip(reason="primary server sizing is now disabled")
def test_splitting_workloads_domain(the_book, test_master_server):
    """
    tests the splitting of the domain since the capacity given is
    less than the what is required for the workloads together
    """
    low_capacity_appliance = appliance.Appliance.from_json(test_master_server)

    def fake_selector(_, safety_margins=None):
        return collections.defaultdict(lambda: low_capacity_appliance)

    workload_sheet = etes.get_workloads_sheet(the_book)
    # adding 15 workloads to test the domain change of workloads
    # due to multiple master server assignment to the workloads
    the_book.macro("activate_sheet")(connection.WORKLOADS_SHEET)
    for i in range(1, 16):
        the_book.macro("add_workload")()
    # changing number of files for the workloads
    values = []
    for i in range(2, 18):
        values.append(["3000000"])
    workload_sheet.range(
        f"{NUMBER_OF_FILES_PER_FETB}2:{NUMBER_OF_FILES_PER_FETB}17"
    ).value = values
    the_book.macro("activate_sheet")(connection.SITE_ASSIGNMENTS_SHEET)
    with patch.object(
        packing.SizerContext,
        "primary_selector",
        fake_selector,
    ):

        etes.run_packing_on_book(the_book)

    # verify there is output in the Errors and Notes sheet
    # assert that workloads domains are changed
    error_sheet = etes.get_errors_and_notes_sheet(the_book)
    warned_workloads = error_sheet.range("A1:A17").value
    assert None not in warned_workloads


@pytest.mark.slowtest
def test_default_workload_sanity(the_book, dwa_testcase):
    # This test takes all the default workloads as workload and
    # just runs sizing to verifies that it does not crash in case
    # of any change in attributes of any default workload.
    # If this test fails then the changed attribute value of
    # default workload needs to be revisited for proper value.
    workload_sheet = etes.get_workloads_sheet(the_book)

    # Set given workload type
    workload_sheet.range(f"{WORKLOAD_TYPE_COL}2").value = dwa_testcase
    the_book.macro("activate_sheet")(connection.SITE_ASSIGNMENTS_SHEET)

    connection.do_main(
        the_book,
        progress_reporting=False,
        appliance_family=constants.ApplianceFamily.NBA,
    )

    # verify there is no output in the Errors and Notes sheet
    error_sheet = etes.get_errors_and_notes_sheet(the_book)
    assert error_sheet.range("A2").value is None

    # verify there is output in the expected Results sheet, sizing
    # produces a single media appliance and a single primary appliance
    result_sheet = etes.get_results_sheet(the_book)
    values = result_sheet.range("B5:B7").value
    media_appliance_count = values[0]
    assert int(media_appliance_count) == 1
