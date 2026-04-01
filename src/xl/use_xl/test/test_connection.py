# VERITAS: Copyright (c) 2021 Veritas Technologies LLC. All rights reserved.
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
import sys
from unittest.mock import patch

import pytest

from use_core.appliance import Appliance
from use_core import constants
from use_core import packing
from use_core import task
from use_core import utils
from use_core import workload

from use_core.utils import DEFAULT_TIMEFRAME

from use_core.test import helper_core

try:
    from use_xl import connection

    import end_to_end_support as etes
except ImportError:
    pass

if sys.platform.startswith("linux"):
    pytest.skip("skipping non-linux tests", allow_module_level=True)


@pytest.fixture
def excel_book(excel_app):
    book = excel_app.books.add()
    yield book
    book.close()


@pytest.fixture
def excel_sheet(excel_book):
    sheet = excel_book.sheets.add()
    sheet.clear_contents()
    yield sheet


@pytest.fixture
def excel_sheet_with_chart(excel_sheet):
    excel_sheet.charts.add()
    yield excel_sheet


@pytest.fixture
def excel_sheet_appliance_def(excel_sheet):
    heading = ["Model", "Visible"]
    data = [[f"model{i}", i % 2] for i in range(100)]
    excel_sheet.range("A1").value = [heading, *data]
    visible_models = set(f"model{i}" for i in range(100) if i % 2 == 1)
    return visible_models, excel_sheet


def window_to_excel(sheet, windows):
    col_array = []
    val_array = []

    for w in windows:
        col_list = []
        val_list = []
        for key, val in w.items():
            col_list.append(key)
            val_list.append(val)
        col_array.append(col_list)
        val_array.append(val_list)

    sheet.range("A1").value = col_array[0]
    sheet.range("A2").value = val_array


def workload_to_excel(sheet, workloads):
    col_array = []
    val_array = []

    for w in workloads:
        key_list = []
        col_list = []
        val_list = []
        for key, val in w.items():
            key_list.append(key)
            if key in connection.SHEET_WORKLOADS_MAP:
                xlator = connection.SHEET_WORKLOADS_MAP[key]
                if xlator.column_name:
                    col_list.append(connection.SHEET_WORKLOADS_MAP[key].column_name)
                    if isinstance(val, utils.Size):
                        val_list.append(val.value)
                    else:
                        val_list.append(str(val))
        col_array.append(col_list)
        val_array.append(val_list)

    sheet.range("A1").value = col_array[0]
    sheet.range("A2").value = val_array


def slp_to_excel(sheet, slp_list):
    col_array = []
    val_array = []

    for slp in slp_list:
        key_list = []
        col_list = []
        val_list = []
        for key, val in slp.items():
            key_list.append(key)
            if key in connection.SHEET_STORAGE_LIFECYCLE_POLICIES_MAP:
                xlator = connection.SHEET_STORAGE_LIFECYCLE_POLICIES_MAP[key]
                if xlator.column_name:
                    col_list.append(
                        connection.SHEET_STORAGE_LIFECYCLE_POLICIES_MAP[key].column_name
                    )
                    if isinstance(val, utils.Size):
                        val_list.append(val.value)
                    else:
                        val_list.append(str(val))
        col_array.append(col_list)
        val_array.append(val_list)

    sheet.range("A1").value = col_array[0]
    sheet.range("A2").value = val_array


def test_get_selected_models(excel_sheet_appliance_def):
    expected_models, sheet = excel_sheet_appliance_def
    visible_models = connection.get_selected_models(sheet)
    assert visible_models == expected_models
    return


def test_excel_to_window(excel_sheet, test_windows):
    expected_windows = utils.WindowSize(
        full_backup_hours=50, incremental_backup_hours=24, replication_hours=90
    )

    window_to_excel(excel_sheet, test_windows)
    parsed_windows = connection.excel_to_window(excel_sheet)

    assert parsed_windows == expected_windows


def test_excel_to_slp(excel_sheet, test_slp):
    slp_to_excel(excel_sheet, test_slp)
    slp_excel = connection.excel_to_slp(excel_sheet)

    for parsed_slp, expected_slp in zip(slp_excel, test_slp):
        for k in parsed_slp.keys():
            if (
                k in connection.SHEET_STORAGE_LIFECYCLE_POLICIES_MAP.keys()
                and not isinstance(expected_slp[k], utils.Size)
            ):
                if expected_slp[k] == "No":
                    expected_slp[k] = False
                if expected_slp[k] == "Yes":
                    expected_slp[k] = True
                if k == "domain" and expected_slp[k] == "":
                    expected_slp[k] = constants.DEFAULT_DOMAIN_NAME
                print(parsed_slp[k], k, "parsed_slp")
                print(expected_slp[k], k, "expected_slp")
                assert parsed_slp[k] == expected_slp[k]


def test_excel_to_workload(excel_sheet, test_workloads, test_slp):
    workload_to_excel(excel_sheet, test_workloads)
    workload_excel = connection.excel_to_workload(
        excel_sheet, DEFAULT_TIMEFRAME, test_slp, utils.DEFAULT_WORST_CASE_CLOUD_FACTOR
    )

    for parsed_workload, expected_workload in zip(workload_excel, test_workloads):
        for k in parsed_workload.attr.keys():
            if k in connection.SHEET_WORKLOADS_MAP.keys() and not isinstance(
                expected_workload[k], utils.Size
            ):
                if expected_workload[k] == "No":
                    expected_workload[k] = False
                if expected_workload[k] == "Yes":
                    expected_workload[k] = True
                print(parsed_workload.attr[k], k, "parsed_workload")
                print(expected_workload[k], k, "expected_workload")
                assert parsed_workload.attr[k] == expected_workload[k]


def test_workload_names_duplicates(excel_sheet, test_workloads, test_slp):
    workload_to_excel(excel_sheet, test_workloads)

    excel_sheet.range("A2").value = [
        ["workload name"],
        ["workload name"],
        ["workload name"],
    ]

    workloads = connection.excel_to_workload(
        excel_sheet, DEFAULT_TIMEFRAME, test_slp, utils.DEFAULT_WORST_CASE_CLOUD_FACTOR
    )
    names = [wk.name for wk in workloads]
    assert len(names) == len(set(names))


def test_workload_names_pathological(excel_sheet, test_workloads, test_slp):
    workload_to_excel(excel_sheet, test_workloads)

    excel_sheet.range("A2").value = [
        ["workload name@A4"],
        ["workload name"],
        ["workload name"],
    ]

    workloads = connection.excel_to_workload(
        excel_sheet, DEFAULT_TIMEFRAME, test_slp, utils.DEFAULT_WORST_CASE_CLOUD_FACTOR
    )
    names = [wk.name for wk in workloads]
    assert len(names) == len(set(names))


def test_workload_invalid_slp(excel_sheet, test_workloads, test_slp):
    workload_to_excel(excel_sheet, test_workloads)

    assert excel_sheet.range("E1").value == "Storage Lifecycle Policy"
    excel_sheet.range("E2").value = "non-existent"

    with pytest.raises(connection.BadInputError) as exc:
        connection.excel_to_workload(
            excel_sheet,
            DEFAULT_TIMEFRAME,
            test_slp,
            utils.DEFAULT_WORST_CASE_CLOUD_FACTOR,
        )

    assert "non-existent" in str(exc.value)


def test_workload_zero_and_tiny_size(
    excel_sheet, test_zero_and_tiny_workloads, test_slp
):
    workload_to_excel(excel_sheet, test_zero_and_tiny_workloads)

    workloads = connection.excel_to_workload(
        excel_sheet, DEFAULT_TIMEFRAME, test_slp, utils.DEFAULT_WORST_CASE_CLOUD_FACTOR
    )
    names = [wk.name for wk in workloads]
    assert len(names) == 0


def test_is_config_safe(test_per_appliance_safety_margins):
    test_per_appliance_safety_margins["FAKE-5250-FLEX"] = {
        "Capacity": 0.8,
        "LUN_Size": 1,
    }
    test_config = {
        "5250 9TB": True,
        "5250-FLEX 74.5TB": False,
        "5250-FLEX 101.5TB": True,
        "5350-FLEX 120TB": True,
        "FAKE-5250-FLEX 74.5TB": True,
    }
    for config, expected_result in test_config.items():
        assert (
            connection.is_config_safe(config, test_per_appliance_safety_margins)
            == expected_result
        )


def test_write_appliance(excel_sheet, test_appliances):
    a1 = Appliance.from_json(test_appliances[0])
    a2 = Appliance.from_json(test_appliances[1])
    connection.write_appliance(excel_sheet, [a1, a2])

    assert excel_sheet.range("A2").value == a1.config_name
    assert excel_sheet.range("B2").value == 5150
    assert excel_sheet.range("C2").value == 0
    assert excel_sheet.range("D2").value == a1.disk_capacity.ignore_unit()
    assert excel_sheet.range("E2").value == a1.memory.ignore_unit()
    assert excel_sheet.range("F2").value == a1.io_config

    assert excel_sheet.range("A3").value == a2.config_name
    assert excel_sheet.range("B3").value == 5150
    assert excel_sheet.range("C3").value == 0
    assert excel_sheet.range("D3").value == a2.disk_capacity.ignore_unit()
    assert excel_sheet.range("E3").value == a2.memory.ignore_unit()
    assert excel_sheet.range("F3").value == a2.io_config


def fake_utilization():
    u = utils.YearOverYearUtilization()
    for dimension in utils.YearOverYearUtilization.PERCENTAGE_DIMENSIONS:
        for yr in range(DEFAULT_TIMEFRAME.num_years + 1):
            u.add(dimension, yr, 0)
    return u


def fake_master_utilization():
    u = utils.YearOverYearUtilization()
    for dimension in [
        "absolute_capacity",
        "cpu",
        "memory",
        "files",
        "images",
        "jobs/day",
    ]:
        for yr in range(DEFAULT_TIMEFRAME.num_years + 1):
            u.add(dimension, yr, 0)
    return u


def fake_bottlenecks():
    b = {
        ("DC", "exp"): {106: ["Capacity"]},
        ("SF", "exp"): {12: ["Jobs/Day"]},
    }
    return b


def create_result(workloads, master_appliance, media_appliance, clients):
    workload_map = dict((w.name, w) for w in workloads)
    master_result = packing.SizerResult(timeframe=DEFAULT_TIMEFRAME, flex=False)
    domains = set(w.domain for w in workloads)
    for domain in domains:
        master_appliance = packing.AssignedAppliance(
            master_appliance,
            set([packing.ApplianceRole.primary]),
            [
                packing.AssignedWorkload(
                    w,
                    packing.WorkloadMode.primary,
                    w.num_instances,
                )
                for w in workloads
            ],
        )
        master_appliance.utilization = fake_master_utilization()
        domain_assignment = packing.DomainAssignment([master_appliance])
        for site_name in clients:
            site_appliances = []
            for appliance_details in clients[site_name]:
                appl_workloads = []
                for wname_mode, num_clients in appliance_details.items():
                    wname, mode = wname_mode
                    appl_workloads.append(
                        packing.AssignedWorkload(workload_map[wname], mode, num_clients)
                    )
                appl = packing.AssignedAppliance(
                    media_appliance, set([packing.ApplianceRole.media]), appl_workloads
                )
                site_appliances.append(appl)

            domain_assignment.set_site_assignment(
                site_name,
                packing.SiteAssignment(
                    site_appliances, fake_utilization(), fake_bottlenecks()
                ),
            )
        master_result.set_domain_assignment(domain, domain_assignment)
    return master_result


def test_write_raw(excel_sheet, test_workloads, test_appliances):
    w1 = workload.Workload(test_workloads[0])
    w1.calculate_capacity(DEFAULT_TIMEFRAME)

    app = Appliance.from_json(test_appliances[0])
    result = create_result(
        [w1],
        Appliance.match_config([constants.DEFAULT_MASTER_CONFIG])[0],
        app,
        {
            w1.site_name: [
                {(w1.name, packing.WorkloadMode.media_primary): 1},
                {(w1.name, packing.WorkloadMode.media_primary): 1},
            ]
        },
    )
    connection.write_raw(excel_sheet, result, [w1])

    assert excel_sheet.range("A2:G3").value == [
        [
            w1.domain,
            w1.site_name,
            app.config_name,
            f"{w1.domain}-{w1.site_name}-1",
            w1.name,
            str(packing.WorkloadMode.media_primary),
            1,
        ],
        [
            w1.domain,
            w1.site_name,
            app.config_name,
            f"{w1.domain}-{w1.site_name}-2",
            w1.name,
            str(packing.WorkloadMode.media_primary),
            1,
        ],
    ]


def test_write_site_summary_all_5150(
    excel_sheet_with_chart, test_workloads, test_appliances
):
    excel_sheet = excel_sheet_with_chart

    w1 = workload.Workload(test_workloads[0])
    w2 = workload.Workload(test_workloads[1])
    app = Appliance.from_json(test_appliances[0])

    fake_safety = {app.model: {"Capacity": 1, "CPU": 1, "IO": 1, "Memory": 1, "NW": 1}}

    master_result = create_result(
        [w1, w2],
        Appliance.match_config([constants.DEFAULT_MASTER_CONFIG])[0],
        app,
        {
            "Site_A": [{(w1.name, packing.WorkloadMode.media_primary): 1}],
            "Site_B": [
                {(w2.name, packing.WorkloadMode.media_primary): 1},
                {(w2.name, packing.WorkloadMode.media_primary): 1},
            ],
        },
    )
    connection.write_site_summary(
        excel_sheet, None, master_result, fake_safety, errors={}
    )

    header_row = 4

    assert excel_sheet.range(f"D{header_row}:E{header_row}").value == [
        "Domain-1/Site_A",
        "Domain-1/Site_B",
    ]

    assert excel_sheet.range(f"A{header_row + 1}:E{header_row + 1}").value == [
        app.config_name,
        3,
        None,
        1,
        2,
    ]

    # there should be no indicators that non-5150 devices were present
    assert "NOTE" not in excel_sheet.range(f"A{header_row + 1}").value
    assert excel_sheet.range(f"BA{header_row + 1}").value is None

    # wish there was a way to teach excel the difference between
    # strings and numbers
    assert excel_sheet.book.names[
        "heading_app_needed_safety"
    ].refers_to_range.value == ["Resource Type", 5150.0]


def test_write_site_summary_mixed(
    excel_sheet_with_chart, test_workloads, test_appliances_with_non_5150
):
    excel_sheet = excel_sheet_with_chart

    w1 = workload.Workload(test_workloads[0])
    w2 = workload.Workload(test_workloads[1])
    app = Appliance.from_json(test_appliances_with_non_5150[0])

    fake_safety = {app.model: {"Capacity": 1, "CPU": 1, "IO": 1, "Memory": 1, "NW": 1}}

    master_result = create_result(
        [w1, w2],
        Appliance.match_config([constants.DEFAULT_MASTER_CONFIG])[0],
        app,
        {
            "Site_A": [{(w1.name, packing.WorkloadMode.media_primary): 1}],
            "Site_B": [
                {(w2.name, packing.WorkloadMode.media_primary): 1},
                {(w2.name, packing.WorkloadMode.media_primary): 1},
            ],
        },
    )
    connection.write_site_summary(
        excel_sheet, None, master_result, fake_safety, errors={}
    )

    header_row = 4
    assert excel_sheet.range(f"D{header_row}:E{header_row}").value == [
        "Domain-1/Site_A",
        "Domain-1/Site_B",
    ]

    # since there is a notification in row 5 the appliance is described in row 6
    # cannot test for equality since there might be a warning tag appended
    # to the appliance name
    assert "NOTE" in excel_sheet.range(f"A{header_row + 1}").value

    assert app.config_name in excel_sheet.range(f"A{header_row + 2}").value
    assert excel_sheet.range(f"B{header_row + 2}:E{header_row + 2}").value == [
        3,
        None,
        1,
        2,
    ]

    # there should be no indicators that non-5150 devices were present
    assert excel_sheet.range(f"BA{header_row + 2}").value == 1

    assert excel_sheet.book.names[
        "heading_app_needed_safety"
    ].refers_to_range.value == ["Resource Type", app.model]


def verify_workload_assignment(sheet, workload_instances):
    row_last_index = sheet.used_range.rows.count
    sheet_data = sheet.range(f"G2:I{row_last_index}").value
    summary_dict = collections.defaultdict(int)
    for wname, wmode, winst in sheet_data:
        if wname is None:
            continue
        summary_dict[(wname, wmode)] += winst

    for wname_mode, num_instances in workload_instances.items():
        assert summary_dict[wname_mode] == num_instances


def test_write_workload_assignment_5150_no_dr(
    excel_sheet, test_workloads_dict, test_appliances
):
    w1 = test_workloads_dict["exp"]

    app = Appliance.from_json(test_appliances[0])

    master_result = create_result(
        [w1],
        Appliance.match_config([constants.DEFAULT_MASTER_CONFIG])[0],
        app,
        {
            w1.site_name: [
                {(w1.name, packing.WorkloadMode.media_primary): w1.num_instances}
            ]
        },
    )

    connection.write_workload_assignment(excel_sheet, master_result)
    verify_workload_assignment(
        excel_sheet,
        {(w1.name, str(packing.WorkloadMode.media_primary)): w1.num_instances},
    )


def test_write_workload_assignment_non_5150(
    excel_sheet, test_workloads_dict, test_appliances_with_non_5150
):
    w1 = test_workloads_dict["dr_workload"]

    app = Appliance.from_json(test_appliances_with_non_5150[0])

    master_result = create_result(
        [w1],
        Appliance.match_config([constants.DEFAULT_MASTER_CONFIG])[0],
        app,
        {
            w1.site_name: [
                {(w1.name, packing.WorkloadMode.media_primary): w1.num_instances}
            ],
            w1.dr_dest: [{(w1.name, packing.WorkloadMode.media_dr): w1.num_instances}],
        },
    )

    connection.write_workload_assignment(excel_sheet, master_result)
    verify_workload_assignment(
        excel_sheet,
        {
            (w1.name, str(packing.WorkloadMode.media_primary)): w1.num_instances,
            (w1.name, str(packing.WorkloadMode.media_dr)): w1.num_instances,
        },
    )


def test_write_appliance_summary(
    excel_sheet,
    test_workloads_dict,
    test_appliances,
    windows,
    test_per_appliance_safety_margins,
):
    w1 = test_workloads_dict["exp"]
    w2 = test_workloads_dict["exp2"]

    # fake resources
    w1.resources = w2.resources = fake_resources(["DC", "SF"])
    helper_core.hack_total_current(w1)
    helper_core.hack_total_current(w2)

    apps = [Appliance.from_json(ap) for ap in test_appliances]

    ctx = helper_core.make_sizer_context(
        test_per_appliance_safety_margins,
        workloads=[w1, w2],
        media_configs={
            (w1.domain, w1.site_name): apps[0],
            (w2.domain, w2.site_name): apps[1],
        },
        master_configs={
            w1.domain: Appliance.match_config([constants.DEFAULT_MASTER_CONFIG])[0]
        },
        timeframe=DEFAULT_TIMEFRAME,
        window_sizes=windows,
        rightsize=False,
    )
    mresult = ctx.pack()

    excel_sheet.range("A5:AV6").name = "vupc_summary_area"

    workload_storage_usage = workload.storage_usage([w1, w2], DEFAULT_TIMEFRAME)

    connection.write_appliance_summary(excel_sheet, mresult, workload_storage_usage)
    media_values = excel_sheet.range("A7:AQ7").value
    master_values = excel_sheet.range("A17:AQ17").value

    # first item is string
    assert type(media_values[0]) is str

    # second column is the region
    assert media_values[1] is not None

    # values start from column 3
    base_offset = 3

    # remainder are numbers
    for n in range(base_offset, len(media_values)):
        assert type(media_values[n]) is float
        assert media_values[n] >= 0

    n_dimensions = len(constants.APPLIANCE_SUMMARY_HEADINGS)

    # Be sure the values for each category are not decreasing.
    # there are five items to check
    for n in range(n_dimensions):
        # Skip the columns with non-percentage unit
        if n in [0, 2]:
            continue
        # there are five years to check, each year/value should be
        # no more than next year's, so only four starting years 0, 1, 2, 3
        for year in range(0, 4):
            this_value = media_values[base_offset + n + n_dimensions * year]
            next_value = media_values[base_offset + n + n_dimensions * (year + 1)]
            if year + 1 == constants.PLANNING_YEAR and n not in (0, n_dimensions - 1):
                # actually should be smaller than the max utilization
                # for that dimension, but this testcase is using
                # default 1.0 for that
                assert this_value <= 1
            assert this_value <= next_value

            this_value = master_values[base_offset + n + n_dimensions * year]
            next_value = master_values[base_offset + n + n_dimensions * (year + 1)]
            if this_value is None:
                assert next_value is None
            else:
                assert this_value <= next_value

    required_names = [
        "vupc_summary_max_All",
        "vupc_summary_All",
        "vupc_summary_Year1",
        "vupc_summary_Year2",
        "vupc_summary_Year3",
        "vupc_summary_Year4",
        "vupc_summary_Year5",
        "vupc_summary_area",
    ]
    for name in required_names:
        assert name in excel_sheet.book.names


def test_write_chart_data(
    excel_book,
    test_workloads_dict,
    test_appliances,
    windows,
    test_per_appliance_safety_margins,
):
    sheet = excel_book.sheets.add()

    w1 = test_workloads_dict["exp"]
    w1.calculate_capacity(DEFAULT_TIMEFRAME)
    w2 = test_workloads_dict["exp2"]
    w2.calculate_capacity(DEFAULT_TIMEFRAME)

    # fake resources
    w1.resources = w2.resources = fake_resources(["DC", "SF"])
    helper_core.hack_total_current(w1)
    helper_core.hack_total_current(w2)

    apps = [Appliance.from_json(ap) for ap in test_appliances]
    ctx = helper_core.make_sizer_context(
        test_per_appliance_safety_margins,
        workloads=[w1, w2],
        media_configs={
            (w1.domain, w1.site_name): apps[0],
            (w2.domain, w2.site_name): apps[1],
        },
        master_configs={
            w1.domain: Appliance.match_config([constants.DEFAULT_MASTER_CONFIG])[0]
        },
        timeframe=DEFAULT_TIMEFRAME,
        window_sizes=windows,
        rightsize=False,
    )
    mresult = ctx.pack()

    connection.write_chart_data(sheet, mresult)

    # be sure there are numbers in the data area of sheet

    value_array = sheet.range("A1:E5").value
    assert len(value_array) == 5
    for row in value_array:
        assert len(row) == 5
        for v in row:
            assert v is not None
            # TODO add equal check for now, and remove it once
            # the master server resource calculation is completed
            assert v >= 0

    # check the planning horizon
    horizon_array = sheet.range("G1:H2").value

    # these values are small integers so OK to check for equality
    # the X values (first index) are both for the planning year
    # the Y values (second index) are 0 and 1 so it is vertical
    # from  0 to 100%
    assert horizon_array[0][0] == DEFAULT_TIMEFRAME.planning_year
    assert horizon_array[1][0] == DEFAULT_TIMEFRAME.planning_year
    assert horizon_array[0][1] == 0
    assert horizon_array[1][1] == 1

    # check the 100% warning
    warning_array = sheet.range("J1:K5").value

    # these values are small integers so OK to check for equality
    # the X values (first index) stretch the width of the graph
    # the Y values (second index) are both 1, so the line is
    # horizontal at 100%
    for i in range(5):
        assert warning_array[i][0] == i + 1
        assert warning_array[i][1] == 1


def test_import_nbdeployutil(the_rep_nbdeployutil, the_book):
    sheet = etes.get_itemization_sheet(the_rep_nbdeployutil)
    REP_NBDEPLOYUTIL_HEADERS = [
        constants.MANAGEMENT_SERVER_DESIGNATION_PREVIOUS,
        "Client Name",
        "Policy Name",
        "Policy Type",
        "Backup Image",
        "Backup Date (UTC)",
        "Accuracy",
        "Accuracy Comment",
        "FULL (KB)",
        "UBAK (KB)",
        "DB (KB)",
        "Overlap size (KB)",
        "Total (KB)",
    ]
    assert sheet.range("A1:M1").value == REP_NBDEPLOYUTIL_HEADERS

    connection.import_nbdeployutil(
        "src/xl/use_xl/test/test_nbdeployutil.xlsx",
        "default",
        "USE-1.0.xlsm",
        interactive=False,
    )
    workloads_sheet = etes.get_workloads_sheet(the_book)
    assert (
        workloads_sheet.range("A1:D1").value
        == connection.NBDEPLOYUTIL_EXPECTED_WORKLOADS_HEADERS
    )


def test_import_nbdeployutil_no_slps(the_rep_nbdeployutil, the_book):
    sheet = etes.get_itemization_sheet(the_rep_nbdeployutil)
    REP_NBDEPLOYUTIL_HEADERS = [
        constants.MANAGEMENT_SERVER_DESIGNATION_PREVIOUS,
        "Client Name",
        "Policy Name",
        "Policy Type",
        "Backup Image",
        "Backup Date (UTC)",
        "Accuracy",
        "Accuracy Comment",
        "FULL (KB)",
        "UBAK (KB)",
        "DB (KB)",
        "Overlap size (KB)",
        "Total (KB)",
    ]
    assert sheet.range("A1:M1").value == REP_NBDEPLOYUTIL_HEADERS

    # delete SLPs
    slps_sheet = etes.get_slp_sheet(the_book)
    left = (2, 1)
    right = (3, len(slps_sheet.used_range.columns))
    the_book.macro("do_remove_line")(slps_sheet.range(left, right), 1, True)

    connection.import_nbdeployutil(
        "src/xl/use_xl/test/test_nbdeployutil.xlsx",
        "customer-1",
        "USE-1.0.xlsm",
        interactive=False,
    )
    workloads_sheet = etes.get_workloads_sheet(the_book)
    assert (
        workloads_sheet.range("A1:D1").value
        == connection.NBDEPLOYUTIL_EXPECTED_WORKLOADS_HEADERS
    )

    # verify slp was created
    assert the_book.names["backup_policy_names"].refers_to_range.value == "customer-1"


def test_translators():
    error = object()
    translator_tests = [
        (
            connection.OneToOneTranslator("col_name"),
            {"col_name": "col_value"},
            "col_value",
        ),
        (
            connection.OneToOneTranslator("col_name", default=42),
            {"col_name": "col_value"},
            "col_value",
        ),
        (connection.OneToOneTranslator("col_name", default=42), {"col_name": None}, 42),
        (connection.IntTranslator("col_name"), {"col_name": "32"}, 32),
        (connection.IntTranslator("col_name"), {"col_name": None}, error, "empty"),
        (
            connection.IntTranslator("col_name"),
            {"col_name": "garbage"},
            error,
            "valid value",
        ),
        (connection.IntTranslator("col_name", default=0), {"col_name": None}, 0),
        (connection.NullableIntTranslator("col_name"), {"col_name": "32"}, 32),
        (connection.NullableIntTranslator("col_name"), {"col_name": None}, None),
        (connection.BooleanTranslator("col_name"), {"col_name": "yes"}, True),
        (connection.BooleanTranslator("col_name"), {"col_name": "no"}, False),
        (
            connection.BooleanTranslator("col_name"),
            {"col_name": "garbage"},
            error,
            "valid value",
        ),
        (connection.BooleanTranslator("col_name"), {"col_name": None}, False),
        (connection.BooleanTranslator("col_name"), {"col_name": "N/A"}, False),
        (connection.FloatTranslator("col_name"), {"col_name": "0.2"}, float("0.2")),
        (connection.FloatTranslator("col_name"), {"col_name": None}, error, "empty"),
        (
            connection.FloatTranslator("col_name"),
            {"col_name": "garbage"},
            error,
            "valid value",
        ),
        (
            connection.SizeTranslator("col1", "col2"),
            {"col1": 10, "col2": 1},
            utils.Size.from_string("10TiB"),
        ),
        (
            connection.SizeTranslator("col1", "col2"),
            {"col1": 10, "col2": 20},
            utils.Size.from_string("512GiB"),
        ),
        (
            connection.SizeTranslator("col1", "col2"),
            {"col1": 1, "col2": 1024},
            utils.Size.from_string("1GiB"),
        ),
        (
            connection.SizeTranslator("col1", "col2"),
            {"col1": 2.6, "col2": 2},
            utils.Size.from_string("1395864371KiB"),
        ),
        (
            connection.SizeTranslator("col1", "col2"),
            {"col1": 2.13, "col2": 26},
            utils.Size.from_string(f"{int(2.13 * 1024 * 1024 * 1024 / 26)}KiB"),
        ),
        (
            connection.SizeTranslator("col1", "col2"),
            {"col1": 0.5, "col2": 1},
            utils.Size.from_string("512GiB"),
        ),
        (
            connection.SizeTranslator("col1", "col2"),
            {"col1": "garbage", "col2": 20},
            error,
            "valid value",
        ),
        (
            connection.SizeTranslator("col1", "col2"),
            {"col1": 10, "col2": "garbage"},
            error,
            "valid value",
        ),
        (
            connection.SizeTranslator("col1", "col2"),
            {"col1": 1, "col2": 0},
            error,
            "valid value",
        ),
        (
            connection.SizeTranslator("col1", "col2"),
            {"col1": 1, "col2": 0},
            error,
            "valid value",
        ),
        (
            connection.EnumTranslator("col_name", ["val1", "val2"], "val1"),
            {"col_name": "val2"},
            "val2",
        ),
        (
            connection.EnumTranslator("col_name", ["val1", "val2"], "val1"),
            {"col_name": None},
            "val1",
        ),
        (
            connection.EnumTranslator("col_name", ["val1", "val2"], "val1"),
            {"col_name": "garbage"},
            error,
            "valid value",
        ),
        (
            connection.EnumTranslator("col_name", {"val1": 1, "val2": 2}, "val1"),
            {"col_name": "val2"},
            2,
        ),
        (
            connection.EnumTranslator("col_name", {"val1": 1, "val2": 2}, "val1"),
            {"col_name": None},
            1,
        ),
        (
            connection.UnitTranslator("col_name", "GiB"),
            {"col_name": 2},
            utils.Size.from_string("2GiB"),
        ),
        (
            connection.UnitTranslator("col_name", "GiB"),
            {"col_name": 0.5},
            utils.Size.from_string("512MiB"),
        ),
        (
            connection.UnitTranslator("col_name", "GiB"),
            {"col_name": "invalid"},
            error,
            "valid value",
        ),
    ]

    for testcase in translator_tests:
        xlator, row_dict, expected_result, *rest = testcase
        if expected_result is error:
            expected_message = rest[0]
            with pytest.raises(connection.CellValueError) as exc:
                xlator.value(row_dict)
            assert expected_message in str(exc.value)
        else:
            value = xlator.value(row_dict)
            assert value == expected_result


def test_size_translator_bounds():
    xlator = connection.SizeTranslator("col1", "col2")
    with pytest.raises(Exception) as exc:
        xlator.value({"col1": 1, "col2": 1024 * 1024 * 1024 * 1024})
    assert "too small" in str(exc.value)


def test_master_summary(excel_sheet, test_workloads_dict, test_appliances):
    w1 = test_workloads_dict["exp"]
    w2 = test_workloads_dict["exp2"]

    app = Appliance.from_json(test_appliances[0])

    mresult = create_result(
        [w1, w2],
        Appliance.match_config([constants.DEFAULT_MASTER_CONFIG])[0],
        app,
        {
            "Site_A": [{(w1.name, packing.WorkloadMode.media_primary): 1}],
            "Site_B": [
                {(w2.name, packing.WorkloadMode.media_primary): 1},
                {(w2.name, packing.WorkloadMode.media_primary): 1},
            ],
        },
    )
    connection.write_management_server_summary(excel_sheet, mresult)

    # each master server is represented by two pictures in master summary sheet
    assert len(excel_sheet.pictures) == 2

    w2.domain = "Domain-2"
    mresult = create_result(
        [w1, w2],
        Appliance.match_config([constants.DEFAULT_MASTER_CONFIG])[0],
        app,
        {
            "Site_A": [{(w1.name, packing.WorkloadMode.media_primary): 1}],
            "Site_B": [
                {(w2.name, packing.WorkloadMode.media_primary): 1},
                {(w2.name, packing.WorkloadMode.media_primary): 1},
            ],
        },
    )
    connection.write_management_server_summary(excel_sheet, mresult)

    assert len(excel_sheet.pictures) == 4


_test_settings = [
    {
        "category": "Cat1",
        "params": [
            {
                "name": "Key1",
                "value": "value1",
            },
            {
                "name": "Key2",
                "value": "value2",
            },
        ],
    },
    {
        "category": "Cat2",
        "params": [
            {
                "name": "Key1",
                "value": "value3",
            },
            {
                "name": "Key2",
                "value": "value4",
            },
        ],
    },
]


@patch("use_core.settings.SETTINGS", _test_settings)
def test_read_settings(excel_sheet):
    rows = [
        ["Category", "Parameter", "Value", "Description"],
        ["Cat1", None, None, None],
        [None, "Key1", "Value1", "Desc1"],
        [None, "Key2", "Value2", "Desc2"],
        ["Cat2", None, None, None],
        [None, "Key1", "Value3", "Desc1"],
    ]
    excel_sheet.range("A1").value = rows

    excel_sheet.range("A1:C6").name = "settings"

    s = connection.read_settings(excel_sheet.book)
    assert s.settings == {
        ("Cat1", "Key1"): "Value1",
        ("Cat1", "Key2"): "Value2",
        ("Cat2", "Key1"): "Value3",
        ("Cat2", "Key2"): "value4",
    }


def fake_resources(sites, overrides={}):
    res = {}
    for site in sites:
        for wtype in [
            task.WindowType.full,
            task.WindowType.incremental,
            task.WindowType.replication,
        ]:
            res[(site, wtype)] = {
                "volume": 0,
                "total_job_duration": 0,
                "total_io_utilization": 0,
                "total_nw_utilization": 0,
                "total_cloud_nw_utilization": 0,
                "total_mem_utilization": 0,
            }
            if (site, wtype) in overrides:
                res[(site, wtype)].update(overrides[(site, wtype)])

    def resource_fetcher(site, window, year, pack_flex):
        return res[(site, window)]

    return resource_fetcher
