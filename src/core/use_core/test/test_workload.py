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

import copy
from unittest.mock import patch

import pytest

from use_core import appliance, constants, task, utils, workload
from use_core.calculations import (
    calculate_addl_fulls,
    calculate_annual_full,
    calculate_incrementals,
    calculate_initial_full,
    calculate_monthly_full,
)
from use_core.utils import DEFAULT_TIMEFRAME, DEFAULT_WORST_CASE_CLOUD_FACTOR

import helper_core


def test_initial_full_calculation(test_workloads):
    """test inital full for year 1"""
    cap = workload.Workload(test_workloads[2])
    cap.calculate_capacity(DEFAULT_TIMEFRAME)
    result = calculate_initial_full(
        cap.yearly_sizes[1]["size"], test_workloads[2]["initial_dedup_rate"]
    )
    assert round(result.post_dedupe / utils.Size.UNIT_SCALES["TB"], 2) == 1.8
    assert round(result.pre_dedupe / utils.Size.UNIT_SCALES["TB"], 2) == 6.0


def test_additional_full(test_workloads):
    wl = workload.Workload(test_workloads[2])
    wl.calculate_capacity(DEFAULT_TIMEFRAME)
    result = calculate_addl_fulls(
        wl.yearly_sizes[1]["size"],
        test_workloads[2]["dedupe_rate_adl_full"],
        test_workloads[2]["weekly_full_retention"],
    )
    assert round(result.post_dedupe / utils.Size.UNIT_SCALES["TB"], 2) == 2.7
    assert round(result.pre_dedupe / utils.Size.UNIT_SCALES["TB"], 2) == 18.0


def test_incrementals(test_workloads):
    wl = workload.Workload(test_workloads[2])
    wl.calculate_capacity(DEFAULT_TIMEFRAME)
    result = calculate_incrementals(
        wl.yearly_sizes[1]["size"],
        test_workloads[2]["daily_change_rate"],
        test_workloads[2]["dedup_rate"],
        round(test_workloads[2]["incremental_retention_days"] / 7),
        test_workloads[2]["incremental_per_week"],
    )
    assert round(result.post_dedupe / utils.Size.UNIT_SCALES["TB"], 2) == 2.25
    assert round(result.pre_dedupe / utils.Size.UNIT_SCALES["TB"], 2) == 9.0


def test_single_workload_capacity(test_workloads):
    wl = workload.Workload(test_workloads[2])
    wl.calculate_capacity(DEFAULT_TIMEFRAME)
    result = wl.yearly_sizes[1]["total_current"]
    assert round(result / utils.Size.UNIT_SCALES["TB"], 2) == 14.18


def test_monthly_full(test_workloads):
    wl = workload.Workload(test_workloads[2])
    wl.calculate_capacity(DEFAULT_TIMEFRAME)
    result = calculate_monthly_full(
        wl.yearly_sizes[1]["size"],
        wl.addl_full_dedupe_ratio,
        wl.retention["local"].monthly_full,
        wl.retention["local"].weekly_full,
    )
    assert round(result.post_dedupe / utils.Size.UNIT_SCALES["TB"], 2) == 5.4
    assert round(result.pre_dedupe / utils.Size.UNIT_SCALES["TB"], 2) == 36.0


def test_annual_full(test_workloads):
    wl = workload.Workload(test_workloads[2])
    wl.calculate_capacity(DEFAULT_TIMEFRAME)
    result = calculate_annual_full(
        wl.yearly_sizes[1]["size"],
        wl.addl_full_dedupe_ratio,
        wl.retention["local"].annual_full,
        wl.retention["local"].monthly_full,
    )
    assert round(result.post_dedupe / utils.Size.UNIT_SCALES["TB"], 2) == 1.8
    assert round(result.pre_dedupe / utils.Size.UNIT_SCALES["TB"], 2) == 12.0


def test_annual_only():
    wk = helper_core.workload_on_demand(
        "wk1",
        "File System (Large Files)",
        fetb=50,
        clients=5,
        misc_policy="local",
        locations_policy="local+ltr",
        retentions_policy="local+access-annualonly",
    )
    wk.calculate_capacity(DEFAULT_TIMEFRAME)

    for yr in range(1, DEFAULT_TIMEFRAME.num_years + 1):
        assert wk.cloud_storage_for_year(yr) > 0


def test_bad_workload_input(test_workloads_dict):
    w_src = copy.deepcopy(test_workloads_dict["exp"].attr)
    w_src["unexpected_key"] = "value"
    with pytest.raises(ValueError):
        workload.Workload(w_src)


def test_log_backups_accounted(test_workloads_dict, test_appliances, windows):
    appl = {
        "master_app": appliance.Appliance.from_json(test_appliances[0]),
        "media_app": appliance.Appliance.from_json(test_appliances[0]),
    }
    w_src = test_workloads_dict["exp"].attr

    w1 = workload.Workload(w_src)
    helper_core.make_generate_tasks([w1], w1.domain, [w1.site_name], appl, windows)
    orig_resources = copy.deepcopy(w1.media_resources)

    w_src["log_backup_frequency_minutes"] = 15
    w_src["log_backup_capable"] = True
    w2 = workload.Workload(w_src)
    helper_core.make_generate_tasks([w2], w2.domain, [w2.site_name], appl, windows)
    new_resources = w2.media_resources

    # resources for full window are unaffected
    assert (
        new_resources[("DC", task.WindowType.full)]["total_cpu_utilization"]
        == orig_resources[("DC", task.WindowType.full)]["total_cpu_utilization"]
    )

    # additional resource requirements for incremental because of log
    # backups
    assert (
        new_resources[("DC", task.WindowType.incremental)]["total_cpu_utilization"]
        > orig_resources[("DC", task.WindowType.incremental)]["total_cpu_utilization"]
    )


def test_duplex_with_no_duplex_workload(test_workloads_dict, test_appliances, windows):
    appl = {
        "master_app": appliance.Appliance.from_json(test_appliances[0]),
        "media_app": appliance.Appliance.from_json(test_appliances[0]),
    }
    w_src = test_workloads_dict["exp"].attr

    w1 = workload.Workload(w_src)
    helper_core.make_generate_tasks([w1], w1.domain, [w1.site_name], appl, windows)

    for yr in range(5):
        for tk in w1.media_yearly_tasks[(w1.domain, w1.site_name)][yr]:
            assert tk.duplex == task.TaskDuplexType.half


def test_duplex_with_duplex_workload(test_workloads_dict, test_appliances, windows):
    appl = {
        "master_app": appliance.Appliance.from_json(test_appliances[0]),
        "media_app": appliance.Appliance.from_json(test_appliances[0]),
    }
    w_src = test_workloads_dict["db_workload"].attr

    w_src["log_backup_frequency_minutes"] = 15
    w_src["log_backup_capable"] = True
    w_src["backup_location_policy"] = "local+dr"
    w_src["dr_dest"] = "SF"

    w1 = workload.Workload(w_src)
    helper_core.make_generate_tasks([w1], w1.domain, [w1.site_name], appl, windows)
    helper_core.make_generate_tasks([w1], w1.domain, [w1.dr_dest], appl, windows)

    for yr in range(5):
        for tk in w1.media_yearly_tasks[(w1.domain, w1.site_name)][yr]:
            assert tk.duplex == task.TaskDuplexType.full
        for tk in w1.media_yearly_tasks[(w1.domain, w1.dr_dest)][yr]:
            assert tk.duplex == task.TaskDuplexType.half


@patch("use_core.constants.EXTRA_CPU_TIME", 0)
def test_extra_cpu_time_works(test_workloads_dict, test_appliances, windows):
    appl = {
        "master_app": appliance.Appliance.from_json(test_appliances[0]),
        "media_app": appliance.Appliance.from_json(test_appliances[0]),
    }
    w_src = test_workloads_dict["exp"].attr

    w = workload.Workload(w_src)

    w.calculate_capacity(DEFAULT_TIMEFRAME, DEFAULT_WORST_CASE_CLOUD_FACTOR)
    helper_core.make_generate_tasks([w], w.domain, [w.site_name], appl, windows)
    orig_resources = copy.deepcopy(w.media_resources)

    constants.EXTRA_CPU_TIME = 1

    helper_core.make_generate_tasks([w], w.domain, [w.site_name], appl, windows)
    new_resources = w.media_resources

    for window in [task.WindowType.full, task.WindowType.incremental]:
        assert (
            new_resources[("DC", window)]["total_cpu_utilization"]
            > orig_resources[("DC", window)]["total_cpu_utilization"]
        )


@patch("use_core.constants.FUDGE_IOPS_MAX", 1.0)
@patch("use_core.constants.FUDGE_CPU_MAX", 1.0)
@patch("use_core.constants.FUDGE_NW_MAX", 1.0)
def test_fudge_works(test_appliances, windows):
    appl = {
        "master_app": appliance.Appliance.from_json(test_appliances[0]),
        "media_app": appliance.Appliance.from_json(test_appliances[0]),
    }

    orig_cpu = appl["media_app"].safe_duration(task.WindowType.full, windows)
    orig_iops = appl["media_app"].safe_iops
    orig_nw_1g = appl["media_app"].safe_nw_1g

    constants.FUDGE_CPU_MAX = 0.8
    constants.FUDGE_IOPS_MAX = 0.8
    constants.FUDGE_NW_MAX = 0.8

    assert appl["media_app"].safe_duration(task.WindowType.full, windows) < orig_cpu
    assert appl["media_app"].safe_iops < orig_iops
    assert appl["media_app"].safe_nw_1g < orig_nw_1g


def test_dr_ltr_capacity_accounted(test_workloads_dict):
    w_src = test_workloads_dict["dr_ltr_workload"].attr

    dr_ltr_wl = workload.Workload(w_src)
    dr_ltr_wl.calculate_capacity(DEFAULT_TIMEFRAME)

    w_src["backup_location_policy"] = "local only"
    w_src["dr_dest"] = None

    local_wl = workload.Workload(w_src)
    local_wl.calculate_capacity(DEFAULT_TIMEFRAME)

    # if policy is local only, no storage usage on dr or cloud
    assert local_wl.dr_sizes[1]["total_current"] == 0.0
    assert local_wl.cloud_sizes[1]["total_current"] == 0.0

    # dr has retention identical to local, the storage usage should be
    # identical
    assert dr_ltr_wl.dr_sizes == dr_ltr_wl.yearly_sizes

    # only full backups going to cloud, and retention for those is
    # identical to local, so space usage is somewhere between 0 and
    # local
    assert dr_ltr_wl.cloud_sizes[1]["total_current"] > 0
    assert (
        dr_ltr_wl.cloud_sizes[1]["total_current"]
        < dr_ltr_wl.yearly_sizes[1]["total_current"]
    )


def test_steady_vs_scratch(scratch_vs_steady_workload):
    wk = scratch_vs_steady_workload

    # All retentions are identical.  However, because cloud uses
    # scratch_start, it will have lower space usage as images build up
    # year-over-year.
    assert wk.dr_sizes == wk.yearly_sizes
    assert wk.yearly_sizes != wk.cloud_sizes
    for yr in range(DEFAULT_TIMEFRAME.num_years + 1):
        assert (
            wk.yearly_sizes[yr]["total_current"] >= wk.cloud_sizes[yr]["total_current"]
        )


def test_dr_retention_affects_capacity(test_workloads_dict):
    w_src = test_workloads_dict["dr_ltr_workload"].attr

    w_src["incremental_retention_days"] = 7
    w_src["weekly_full_retention"] = 1
    w_src["monthly_retention"] = 1

    dr_wl = workload.Workload(w_src)
    dr_wl.calculate_capacity(DEFAULT_TIMEFRAME)

    local_dr_sizes = list(zip(dr_wl.yearly_sizes, dr_wl.dr_sizes))[1:]
    for local, dr in local_dr_sizes:
        assert local["total_current"] < dr["total_current"]


def test_site_storage_usage(test_workloads_dict):
    w1 = test_workloads_dict["exp"]
    w2 = test_workloads_dict["dr_ltr_workload"]

    workloads = [w1, w2]

    w1.calculate_capacity(DEFAULT_TIMEFRAME)
    w2.calculate_capacity(DEFAULT_TIMEFRAME)

    test_year = DEFAULT_TIMEFRAME.planning_year

    storage = workload.site_storage_usage(workloads, DEFAULT_TIMEFRAME.num_years)

    assert int(storage["DC"][test_year]["usage"]) == int(
        w1.total_storage_for_year(test_year) * w1.num_instances
    ) + int(w2.total_storage_for_year(test_year) * w2.num_instances)
    assert int(storage["SF"][test_year]["usage"]) == int(
        w2.dr_storage_for_year(test_year) * w2.num_instances
    )
    assert storage["cloud"][test_year]["usage"] == int(
        w2.cloud_storage_for_year(test_year) * w2.num_instances
    )

    print(storage["cloud"])
    for yr in range(1, DEFAULT_TIMEFRAME.num_years + 1):
        assert storage["cloud"][yr]["gb_months"] > storage["cloud"][yr - 1]["gb_months"]


def test_site_with_multiple_domains(test_workloads_dict):
    w1 = workload.Workload(test_workloads_dict["dc_domain-1"].attr)
    w2 = workload.Workload(test_workloads_dict["dc_domain-2"].attr)

    w1.calculate_capacity(DEFAULT_TIMEFRAME)
    w2.calculate_capacity(DEFAULT_TIMEFRAME)
    workloads = [w1, w2]
    test_year = DEFAULT_TIMEFRAME.planning_year
    assert w1.site_name == w2.site_name
    assert w1.domain != w2.domain
    assert w1.workload_size == w2.workload_size
    assert w1.num_instances == w2.num_instances
    test_sites = workload.get_site_hints_from_workloads(workloads, test_year)
    assert (
        test_sites[(w1.domain, w1.site_name)].disk
        == test_sites[(w2.domain, w2.site_name)].disk
    )


def test_replications_per_week(test_workloads_dict, test_appliances, windows):
    appl = {
        "master_app": appliance.Appliance.from_json(test_appliances[0]),
        "media_app": appliance.Appliance.from_json(test_appliances[0]),
    }
    w1 = test_workloads_dict["dr_ltr_workload"]

    helper_core.make_generate_tasks(
        [w1], w1.domain, [w1.site_name, w1.dr_dest], appl, windows
    )

    # verify that we need to do more replication jobs (or at least,
    # non-decreasing number of jobs) year-over-year as volume
    # increases
    replication_counts = [
        w1.replications_per_week(yr) for yr in range(1 + DEFAULT_TIMEFRAME.num_years)
    ]

    assert replication_counts == sorted(replication_counts)


def test_unnecessary_dr_dest(test_workloads_dict):
    w_src = test_workloads_dict["exp"].attr

    # this should now cause no error, VUPC 249
    w_src["dr_dest"] = "SF"
    w_src["backup_location_policy"] = "local only"
    with pytest.raises(ValueError):
        workload.Workload(w_src)

    w_src["dr_dest"] = " "
    w_src["backup_location_policy"] = "local+dr"
    with pytest.raises(ValueError):
        workload.Workload(w_src)


def test_dr_primary_site_duplicate(test_workloads_dict):
    w_src = test_workloads_dict["exp"].attr

    w_src["dr_dest"] = w_src["region"] = "Same"
    w_src["backup_location_policy"] = "local+dr"
    with pytest.raises(ValueError):
        workload.Workload(w_src)


def test_multiple_appliances_dr_ltr(
    test_workloads_dict, test_appliances, test_appliances_with_non_5150, windows
):
    appl1 = {
        "master_app": appliance.Appliance.from_json(test_appliances[0]),
        "media_app": appliance.Appliance.from_json(test_appliances[0]),
    }
    appl2 = {
        "master_app": appliance.Appliance.from_json(test_appliances[0]),
        "media_app": appliance.Appliance.from_json(test_appliances_with_non_5150[0]),
    }
    wk = test_workloads_dict["dr_ltr_workload"]

    helper_core.make_generate_tasks([wk], wk.domain, [wk.site_name], appl1, windows)
    helper_core.make_generate_tasks([wk], wk.domain, [wk.dr_dest], appl2, windows)

    assert (wk.domain, wk.site_name) in wk.media_yearly_tasks
    assert (wk.domain, wk.dr_dest) in wk.media_yearly_tasks

    # only replication tgt at DR destination
    assert len(wk.media_yearly_tasks[(wk.domain, wk.dr_dest)][0]) == 1


def test_catalog_sizes(test_workloads_dict):
    wk = test_workloads_dict["files_backup"]
    wk.calculate_capacity(DEFAULT_TIMEFRAME)
    # verify catalog sizes are non-decreasing
    assert wk.yearly_catalog_sizes == sorted(
        wk.yearly_catalog_sizes, key=lambda cat: cat["catalog_size"]
    )


def test_catalog_size_depends_on_fetb(test_workloads_dict):
    wk_src = test_workloads_dict["files_backup"].attr
    wk1 = workload.Workload(wk_src)
    wk1.calculate_capacity(DEFAULT_TIMEFRAME)

    wk_src["workload_size"] *= 2
    wk2 = workload.Workload(wk_src)
    wk2.calculate_capacity(DEFAULT_TIMEFRAME)

    for wk1_sz, wk2_sz in zip(wk1.yearly_catalog_sizes, wk2.yearly_catalog_sizes):
        assert wk1_sz["catalog_size"] < wk2_sz["catalog_size"]
        assert wk1_sz["catalog_nfiles"] < wk2_sz["catalog_nfiles"]
        assert wk1_sz["catalog_nimages"] == wk2_sz["catalog_nimages"]


def test_client_dedup_without_ndmp(test_workloads_dict, test_appliances, windows):
    appl = {
        "master_app": appliance.Appliance.from_json(test_appliances[0]),
        "media_app": appliance.Appliance.from_json(test_appliances[0]),
    }
    w_src = test_workloads_dict["exp"].attr
    w_src["client_dedup"] = False
    w1 = workload.Workload(w_src)
    helper_core.make_generate_tasks([w1], w1.domain, [w1.site_name], appl, windows)
    orig_resources = copy.deepcopy(w1.media_resources)

    w_src["client_dedup"] = True
    w2 = workload.Workload(w_src)
    helper_core.make_generate_tasks([w2], w2.domain, [w2.site_name], appl, windows)
    new_resources = w2.media_resources

    assert (
        new_resources[("DC", task.WindowType.full)]["total_cpu_utilization"]
        < orig_resources[("DC", task.WindowType.full)]["total_cpu_utilization"]
    )
    assert (
        new_resources[("DC", task.WindowType.full)]["total_nw_utilization"]
        < orig_resources[("DC", task.WindowType.full)]["total_nw_utilization"]
    )

    assert (
        new_resources[("DC", task.WindowType.incremental)]["total_cpu_utilization"]
        < orig_resources[("DC", task.WindowType.incremental)]["total_cpu_utilization"]
    )
    assert (
        new_resources[("DC", task.WindowType.incremental)]["total_nw_utilization"]
        < orig_resources[("DC", task.WindowType.incremental)]["total_nw_utilization"]
    )


def test_client_dedup_with_ndmp(test_workloads_dict, test_appliances, windows):
    appl = {
        "master_app": appliance.Appliance.from_json(test_appliances[0]),
        "media_app": appliance.Appliance.from_json(test_appliances[0]),
    }
    w_src = test_workloads_dict["exp"].attr
    w_src["workload_type"] = "NDMP"
    w_src["client_dedup"] = False
    w1 = workload.Workload(w_src)
    helper_core.make_generate_tasks([w1], w1.domain, [w1.site_name], appl, windows)
    orig_resources = copy.deepcopy(w1.media_resources)

    w_src["workload_type"] = "NDMP"
    w_src["client_dedup"] = True
    w2 = workload.Workload(w_src)
    helper_core.make_generate_tasks([w2], w2.domain, [w2.site_name], appl, windows)
    new_resources = w2.media_resources

    assert (
        new_resources[("DC", task.WindowType.full)]["total_cpu_utilization"]
        == orig_resources[("DC", task.WindowType.full)]["total_cpu_utilization"]
    )
    assert (
        new_resources[("DC", task.WindowType.full)]["total_nw_utilization"]
        == orig_resources[("DC", task.WindowType.full)]["total_nw_utilization"]
    )

    assert (
        new_resources[("DC", task.WindowType.incremental)]["total_cpu_utilization"]
        == orig_resources[("DC", task.WindowType.incremental)]["total_cpu_utilization"]
    )
    assert (
        new_resources[("DC", task.WindowType.incremental)]["total_nw_utilization"]
        == orig_resources[("DC", task.WindowType.incremental)]["total_nw_utilization"]
    )


def test_storage_usage(test_workloads_dict, test_appliances, windows):
    w1 = test_workloads_dict["exp"]
    w2 = test_workloads_dict["files_backup"]

    appl = {
        "master_app": appliance.Appliance.from_json(test_appliances[0]),
        "media_app": appliance.Appliance.from_json(test_appliances[0]),
    }
    helper_core.make_generate_tasks([w1], w1.domain, [w1.site_name], appl, windows)
    helper_core.make_generate_tasks([w2], w1.domain, [w2.site_name], appl, windows)

    u = workload.storage_usage([w1, w2], DEFAULT_TIMEFRAME)
    assert len(u) == 2
    assert w1.name in u
    assert w2.name in u


def test_worst_case_storage():
    wk = helper_core.workload_on_demand(
        "wk1",
        "File System (Large Files)",
        fetb=50,
        clients=5,
        misc_policy="local",
        locations_policy="local+dr+ltr",
        retentions_policy="local+dr+ltr_identical",
    )

    for excess in [0, 0.5]:
        wk.calculate_capacity(DEFAULT_TIMEFRAME, excess_cloud_factor=excess)
        for yr in range(1, DEFAULT_TIMEFRAME.num_years + 1):
            assert wk.cloud_storage_for_year(yr) * (
                1 + excess
            ) == wk.cloud_storage_worst_case_for_year(yr)


def test_weekly_count_effective(test_appliances, windows):
    appl = {
        "master_app": appliance.Appliance.from_json(test_appliances[0]),
        "media_app": appliance.Appliance.from_json(test_appliances[0]),
    }

    wk1 = helper_core.workload_on_demand(
        "wk1",
        "File System (Large Files)",
        fetb=50,
        clients=5,
        misc_policy="local",
        locations_policy="local",
        retentions_policy="local",
    )

    helper_core.make_generate_tasks([wk1], wk1.domain, [wk1.site_name], appl, windows)
    orig_resources = wk1.media_resources

    wk2 = helper_core.workload_on_demand(
        "wk2",
        "File System (Large Files)",
        fetb=50,
        clients=5,
        misc_policy="local",
        locations_policy="local",
        retentions_policy="local+daily-fulls",
    )

    helper_core.make_generate_tasks([wk2], wk2.domain, [wk2.site_name], appl, windows)
    daily_fulls_resources = wk2.media_resources

    wk3 = helper_core.workload_on_demand(
        "wk3",
        "File System (Large Files)",
        fetb=50,
        clients=5,
        misc_policy="local",
        locations_policy="local",
        retentions_policy="local+0fulls",
    )

    helper_core.make_generate_tasks([wk3], wk3.domain, [wk3.site_name], appl, windows)
    zero_fulls_resources = wk3.media_resources

    site_name = wk1.site_name

    # resources for incremental window are unaffected
    assert (
        daily_fulls_resources[(site_name, task.WindowType.incremental)][
            "total_cpu_utilization"
        ]
        == orig_resources[(site_name, task.WindowType.incremental)][
            "total_cpu_utilization"
        ]
    )

    # additional resource requirements for full because of higher frequency
    assert (
        daily_fulls_resources[(site_name, task.WindowType.full)][
            "total_cpu_utilization"
        ]
        > orig_resources[(site_name, task.WindowType.full)]["total_cpu_utilization"]
    )

    # no resources required in full window if no backups done
    assert zero_fulls_resources[(site_name, task.WindowType.full)][
        "total_cpu_utilization"
    ] == pytest.approx(0.0, abs=1e-4)


def test_backup_volume_is_per_client(test_appliances, windows):
    appl = {
        "master_app": appliance.Appliance.from_json(test_appliances[0]),
        "media_app": appliance.Appliance.from_json(test_appliances[0]),
    }

    clients = [5, 10, 25]
    expected_aggregate_volume = None
    for n_clients in clients:
        wk = helper_core.workload_on_demand(
            "wk1",
            "File System (Large Files)",
            fetb=50,
            clients=n_clients,
            misc_policy="local",
            locations_policy="local",
            retentions_policy="local",
        )
        helper_core.make_generate_tasks([wk], wk.domain, [wk.site_name], appl, windows)

        volume = int(wk.backup_volume_per_week(DEFAULT_TIMEFRAME.planning_year))
        aggregate_volume = volume * n_clients
        if expected_aggregate_volume is None:
            expected_aggregate_volume = aggregate_volume

        assert aggregate_volume == pytest.approx(expected_aggregate_volume, rel=1e-6)
