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

from unittest.mock import patch

import helper_core
import pytest

from use_core import constants
from use_core import media_packing as packing
from use_core import task, utils, workload
from use_core.appliance import Appliance, ApplianceResources

TIMEFRAME_0 = utils.TimeFrame(num_years=constants.FIRST_EXTENSION, planning_year=0)


def test_packing_capped_appliance(
    test_workloads_dict, test_appliances, windows, test_per_appliance_safety_margins
):
    appl1 = {
        "master_app": Appliance.from_json(test_appliances[0]),
        "media_app": Appliance.match_config(
            [test_appliances[2]["name"]],
            safety=test_per_appliance_safety_margins,
        )[0],
    }
    appl2 = {
        "master_app": Appliance.from_json(test_appliances[0]),
        "media_app": Appliance.match_config(
            [test_appliances[3]["name"]],
            safety=test_per_appliance_safety_margins,
        )[0],
    }
    workload = test_workloads_dict["exp"]
    appl1["media_app"]._cached_resources = ApplianceResources(
        capacity=appl1["media_app"].disk_capacity,
        cpu=100,
        memory=appl1["media_app"].memory,
        memory_overhead=0,
        primary_memory_overhead=0,
        nw_1g=utils.Size.assume_unit(appl1["media_app"].one_gbe_io, "MB"),
        nw_10g_copper=utils.Size.assume_unit(
            appl1["media_app"].ten_gbe_copper_io, "MB"
        ),
        nw_10g_sfp=utils.Size.assume_unit(appl1["media_app"].ten_gbe_sfp_io, "MB"),
        nw_25g_sfp=utils.Size.assume_unit(
            appl1["media_app"].twentyfive_gbe_sfp_io, "MB"
        ),
        nw_cloud=0,
        iops=50000,
    )
    appl2["media_app"]._cached_resources = ApplianceResources(
        capacity=appl2["media_app"].disk_capacity,
        cpu=100,
        memory=appl2["media_app"].memory,
        memory_overhead=0,
        primary_memory_overhead=0,
        nw_1g=utils.Size.assume_unit(appl2["media_app"].one_gbe_io, "MB"),
        nw_10g_copper=utils.Size.assume_unit(
            appl2["media_app"].ten_gbe_copper_io, "MB"
        ),
        nw_10g_sfp=utils.Size.assume_unit(appl2["media_app"].ten_gbe_sfp_io, "MB"),
        nw_25g_sfp=utils.Size.assume_unit(
            appl2["media_app"].twentyfive_gbe_sfp_io, "MB"
        ),
        nw_cloud=0,
        iops=50000,
    )
    result = helper_core.pack([workload], appl1, windows, workload.site_name)
    instances1 = [dist["assignment"][0]["total_inst"] for dist in result["DC"]]

    result = helper_core.pack([workload], appl2, windows, workload.site_name)
    instances2 = [dist["assignment"][0]["total_inst"] for dist in result["DC"]]

    assert sum(instances1) == sum(instances2)


def test_packing_single_workload_without_dr(
    test_workloads_dict, test_appliances, windows
):
    appl = {
        "master_app": Appliance.from_json(test_appliances[0]),
        "media_app": Appliance.from_json(test_appliances[0]),
    }
    workload = test_workloads_dict["exp"]
    result = helper_core.pack([workload], appl, windows, workload.site_name)
    instances = [dist["assignment"][0]["total_inst"] for dist in result["DC"]]
    assert sum(instances) == 11


def test_packing_multiple_sites(test_workloads_dict, test_appliances, windows):
    appl = {
        "master_app": Appliance.from_json(test_appliances[0]),
        "media_app": Appliance.from_json(test_appliances[0]),
    }
    w1 = test_workloads_dict["exp"]
    w2 = test_workloads_dict["exp_other_site"]

    result = helper_core.pack([w1, w2], appl, windows, w1.site_name)
    instances = [dist["assignment"][0]["total_inst"] for dist in result["DC"]]
    assert sum(instances) == 11
    result = helper_core.pack([w1, w2], appl, windows, w2.site_name)
    instances = [dist["assignment"][0]["total_inst"] for dist in result["SF"]]
    assert sum(instances) == 11


@patch("use_core.constants.EXTRA_CPU_TIME", 0)
@patch("use_core.constants.FUDGE_IOPS_MAX", 1.0)
@patch("use_core.constants.FUDGE_CPU_MAX", 1.0)
@patch("use_core.constants.FUDGE_NW_MAX", 1.0)
@patch("use_core.constants.CONCURRENT_STREAMS", 1)
def test_packing_multiple_workloads(
    test_workloads_dict, test_appliances, test_appliance_safety, windows
):
    appl1 = {
        "master_app": Appliance.from_json(test_appliances[0]),
        "media_app": Appliance.from_json(test_appliances[0]),
    }
    appl2 = {
        "master_app": Appliance.from_json(test_appliances[0]),
        "media_app": Appliance.from_json(test_appliance_safety),
    }
    w1 = test_workloads_dict["exp"]
    w2 = test_workloads_dict["exp2"]

    w1.generate_tasks(
        w1.domain,
        [w1.site_name],
        appl1,
        windows,
        TIMEFRAME_0,
    )
    w2.generate_tasks(
        w2.domain,
        [w2.site_name],
        appl1,
        windows,
        TIMEFRAME_0,
    )

    # set things up so that both workloads can finish full backups within the window
    half_window = windows.full_backup / 2
    w1.resources = fake_resources(
        ["SF", "DC"],
        {("DC", task.WindowType.full): {"total_job_duration": half_window}},
    )
    w2.resources = fake_resources(
        ["SF", "DC"],
        {("DC", task.WindowType.full): {"total_job_duration": half_window}},
    )

    result = helper_core.pack(
        [w1, w2],
        appl1,
        windows,
        w1.site_name,
        skip_generate_task=True,
        timeframe=TIMEFRAME_0,
    )["DC"]
    assert len(result) == 8

    result_length = len(result)

    instances = {}
    for dist in result:
        for assign in dist["assignment"]:
            wname = assign["workload"].name
            if wname not in instances:
                instances[wname] = 0
            instances[wname] += assign["total_inst"]
    assert instances == {"exp": 11, "exp2": 5}

    # now run with an appliance with a safety margin

    appl2["media_app"].set_max_utilization(memory=0.7, cpu=0.65, disk=0.65, nw=0.65)
    result_safety = helper_core.pack(
        [w1, w2],
        appl2,
        windows,
        w1.site_name,
        skip_generate_task=True,
        timeframe=TIMEFRAME_0,
    )["DC"]

    # with a safety margin, there should be more appliances required
    assert len(result_safety) > result_length

    instances_safety = {}
    for dist in result_safety:
        for assign in dist["assignment"]:
            wname = assign["workload"].name
            if wname not in instances_safety:
                instances_safety[wname] = 0
            instances_safety[wname] += assign["total_inst"]

    assert instances_safety == {"exp": 11, "exp2": 5}


def test_packing_single_workload_with_dr(test_workloads_dict, test_appliances, windows):
    appl = {
        "master_app": Appliance.from_json(test_appliances[0]),
        "media_app": Appliance.from_json(test_appliances[0]),
    }
    workload = test_workloads_dict["dr_workload"]

    result1 = helper_core.pack([workload], appl, windows, workload.site_name)
    result2 = helper_core.pack([workload], appl, windows, workload.dr_dest)

    instances_dc = [dist["assignment"][0]["total_inst"] for dist in result1["DC"]]
    assert sum(instances_dc) == 11
    instances_sf = [dist["assignment"][0]["total_inst"] for dist in result2["SF"]]
    assert sum(instances_sf) == 11


@patch("use_core.constants.EXTRA_CPU_TIME", 0)
@patch("use_core.constants.FUDGE_IOPS_MAX", 1.0)
@patch("use_core.constants.FUDGE_CPU_MAX", 1.0)
@patch("use_core.constants.FUDGE_NW_MAX", 1.0)
@patch("use_core.constants.CONCURRENT_STREAMS", 1)
def test_packing_with_windows(test_workloads_dict, test_appliances, windows):
    appl = {
        "master_app": Appliance.from_json(test_appliances[0]),
        "media_app": Appliance.from_json(test_appliances[0]),
    }
    workload1 = test_workloads_dict["exp"]
    workload2 = test_workloads_dict["exp2"]

    timeframe = utils.DEFAULT_TIMEFRAME

    workload1.generate_tasks(
        workload1.domain,
        [workload1.site_name],
        appl,
        windows,
        timeframe,
    )
    workload2.generate_tasks(
        workload2.domain,
        [workload2.site_name],
        appl,
        windows,
        timeframe,
    )

    half_window = windows.full_backup / 2
    workload1.resources = fake_resources(
        ["DC", "SF"],
        {("DC", task.WindowType.full): {"total_job_duration": half_window}},
    )
    workload2.resources = fake_resources(
        ["DC", "SF"],
        {("DC", task.WindowType.full): {"total_job_duration": half_window}},
    )

    result = helper_core.pack(
        [workload1, workload2],
        appl,
        windows,
        workload1.site_name,
        skip_generate_task=True,
        timeframe=timeframe,
    )["DC"]
    assert len(result) == 8

    # increase requirements for different windows for the workloads,
    # this should not affect assignment because full and incremental
    # resources do not conflict
    incr_half_window = windows.incremental_backup / 2
    workload1.resources = fake_resources(
        ["DC", "SF"],
        {
            ("DC", task.WindowType.full): {"total_job_duration": half_window},
            ("DC", task.WindowType.incremental): {
                "total_job_duration": incr_half_window
            },
        },
    )
    workload2.resources = fake_resources(
        ["DC", "SF"],
        {
            ("DC", task.WindowType.full): {"total_job_duration": half_window},
            ("DC", task.WindowType.incremental): {
                "total_job_duration": incr_half_window
            },
        },
    )

    result = helper_core.pack(
        [workload1, workload2],
        appl,
        windows,
        workload1.site_name,
        skip_generate_task=True,
        timeframe=timeframe,
    )["DC"]
    assert len(result) == 8


def test_packing_with_maximum_number_of_clients_and_fetb(
    test_workloads_dict, test_appliances, windows
):
    appl = {
        "master_app": Appliance.from_json(test_appliances[0]),
        "media_app": Appliance.from_json(test_appliances[0]),
    }
    workload_data = test_workloads_dict["exp"].attr

    workload_data["number_of_clients"] = 15000
    workload_data["workload_size"] = utils.Size.assume_unit(512, "GiB")

    w1 = workload.Workload(workload_data)

    # changing number of clients should have no effect on capacity
    # utilization, as long as FETB is kept the same
    workload_data["number_of_clients"] = 7500
    workload_data["workload_size"] = utils.Size.assume_unit(1024, "GiB")

    w2 = workload.Workload(workload_data)

    result1 = helper_core.pack([w1], appl, windows, w1.site_name)
    result2 = helper_core.pack([w2], appl, windows, w2.site_name)

    assert len(result1["DC"]) == len(result2["DC"])
    assert len(result1["DC"]) == 536

    utilization1 = result1.get_utilization("DC")
    utilization2 = result2.get_utilization("DC")

    for util1, util2 in zip(utilization1, utilization2):
        assert util1["capacity"] == pytest.approx(util2["capacity"])


@patch("use_core.constants.EXTRA_CPU_TIME", 0)
@patch("use_core.constants.FUDGE_IOPS_MAX", 1.0)
@patch("use_core.constants.FUDGE_CPU_MAX", 1.0)
@patch("use_core.constants.FUDGE_NW_MAX", 1.0)
def test_software_safety_dbs(test_workloads_dict, test_appliances, windows):
    appl = {
        "master_app": Appliance.from_json(test_appliances[0]),
        "media_app": Appliance.from_json(test_appliances[0]),
    }
    workload = test_workloads_dict["db_workload"]

    workload.generate_tasks(
        workload.domain,
        [workload.site_name],
        appl,
        windows,
        TIMEFRAME_0,
    )

    workload.resources = fake_resources(["DC"])

    appl["media_app"].set_software_safety(
        jobs_per_day=constants.JOBS_PER_DAY,
        dbs_15min_rpo=5,
        vm_clients=constants.VM_CLIENTS,
        concurrent_streams=constants.CONCURRENT_STREAMS,
        files=constants.MAXIMUM_FILES,
        images=constants.MAXIMUM_IMAGES,
        max_cal_cap=None,
        max_universal_share=constants.MAXIMUM_NUMBER_OF_UNIVERSAL_SHARE,
    )

    result = helper_core.pack(
        [workload],
        appl,
        windows,
        workload.site_name,
        skip_generate_task=True,
        timeframe=TIMEFRAME_0,
    )["DC"]
    assert len(result) == 2

    # allow more databases and concurrent streams, should reduce
    # appliances required
    appl["media_app"].set_software_safety(
        jobs_per_day=constants.JOBS_PER_DAY,
        dbs_15min_rpo=15,
        vm_clients=constants.VM_CLIENTS,
        concurrent_streams=15,
        files=constants.MAXIMUM_FILES,
        images=constants.MAXIMUM_IMAGES,
        max_cal_cap=None,
        max_universal_share=constants.MAXIMUM_NUMBER_OF_UNIVERSAL_SHARE,
    )

    result = helper_core.pack(
        [workload],
        appl,
        windows,
        workload.site_name,
        skip_generate_task=True,
        timeframe=TIMEFRAME_0,
    )["DC"]
    assert len(result) == 1


@patch("use_core.constants.EXTRA_CPU_TIME", 0)
@patch("use_core.constants.FUDGE_IOPS_MAX", 1.0)
@patch("use_core.constants.FUDGE_CPU_MAX", 1.0)
@patch("use_core.constants.FUDGE_NW_MAX", 1.0)
def test_software_safety_vms(test_workloads_dict, test_appliances, windows):
    appl = {
        "master_app": Appliance.from_json(test_appliances[0]),
        "media_app": Appliance.from_json(test_appliances[0]),
    }
    workload = test_workloads_dict["vm_workload"]

    workload.generate_tasks(
        workload.domain, [workload.site_name], appl, windows, TIMEFRAME_0
    )

    # fake available resources to avoid memory overhead impacting
    # calculations
    appl["media_app"]._cached_resources = ApplianceResources(
        capacity=appl["media_app"].disk_capacity,
        cpu=100,
        memory=appl["media_app"].memory,
        memory_overhead=0,
        primary_memory_overhead=0,
        nw_1g=utils.Size.assume_unit(appl["media_app"].one_gbe_io, "MB"),
        nw_10g_copper=utils.Size.assume_unit(appl["media_app"].ten_gbe_copper_io, "MB"),
        nw_10g_sfp=utils.Size.assume_unit(appl["media_app"].ten_gbe_sfp_io, "MB"),
        nw_25g_sfp=utils.Size.assume_unit(
            appl["media_app"].twentyfive_gbe_sfp_io, "MB"
        ),
        nw_cloud=0,
        iops=50000,
    )
    workload.resources = fake_resources(["DC"])

    appl["media_app"].set_software_safety(
        jobs_per_day=constants.JOBS_PER_DAY,
        dbs_15min_rpo=None,
        vm_clients=constants.VM_CLIENTS,
        concurrent_streams=1000,
        files=constants.MAXIMUM_FILES,
        images=constants.MAXIMUM_IMAGES,
        max_cal_cap=None,
        max_universal_share=constants.MAXIMUM_NUMBER_OF_UNIVERSAL_SHARE,
    )

    result = helper_core.pack(
        [workload],
        appl,
        windows,
        workload.site_name,
        skip_generate_task=True,
        timeframe=TIMEFRAME_0,
    )["DC"]
    assert len(result) == 5

    # allow more VMs and concurrent streams, should reduce appliances
    # required
    appl["media_app"].set_software_safety(
        jobs_per_day=constants.JOBS_PER_DAY,
        dbs_15min_rpo=None,
        vm_clients=1000,
        concurrent_streams=1000,
        files=constants.MAXIMUM_FILES,
        images=constants.MAXIMUM_IMAGES,
        max_cal_cap=None,
        max_universal_share=constants.MAXIMUM_NUMBER_OF_UNIVERSAL_SHARE,
    )

    result = helper_core.pack(
        [workload],
        appl,
        windows,
        workload.site_name,
        skip_generate_task=True,
        timeframe=TIMEFRAME_0,
    )["DC"]
    assert len(result) == 1


@patch("use_core.constants.EXTRA_CPU_TIME", 0)
@patch("use_core.constants.FUDGE_IOPS_MAX", 1.0)
@patch("use_core.constants.FUDGE_CPU_MAX", 1.0)
@patch("use_core.constants.FUDGE_NW_MAX", 1.0)
def test_software_safety_images(test_workloads_dict, test_appliances, windows):
    appl = {
        "master_app": Appliance.from_json(test_appliances[0]),
        "media_app": Appliance.from_json(test_appliances[0]),
    }
    workload = test_workloads_dict["vm_workload"]

    workload.generate_tasks(
        workload.domain, [workload.site_name], appl, windows, TIMEFRAME_0
    )

    # fake available resources to avoid memory overhead impacting
    # calculations
    appl["media_app"]._cached_resources = ApplianceResources(
        capacity=appl["media_app"].disk_capacity,
        cpu=100,
        memory=appl["media_app"].memory,
        memory_overhead=0,
        primary_memory_overhead=0,
        nw_1g=utils.Size.assume_unit(appl["media_app"].one_gbe_io, "MB"),
        nw_10g_copper=utils.Size.assume_unit(appl["media_app"].ten_gbe_copper_io, "MB"),
        nw_10g_sfp=utils.Size.assume_unit(appl["media_app"].ten_gbe_sfp_io, "MB"),
        nw_25g_sfp=utils.Size.assume_unit(
            appl["media_app"].twentyfive_gbe_sfp_io, "MB"
        ),
        nw_cloud=0,
        iops=50000,
    )
    workload.resources = fake_resources(["DC"])

    appl["media_app"].set_software_safety(
        jobs_per_day=constants.JOBS_PER_DAY,
        dbs_15min_rpo=None,
        vm_clients=constants.VM_CLIENTS,
        concurrent_streams=1000,
        files=constants.MAXIMUM_FILES,
        images=constants.NO_OF_IMAGES,
        max_cal_cap=None,
        max_universal_share=constants.MAXIMUM_NUMBER_OF_UNIVERSAL_SHARE,
    )

    result = helper_core.pack(
        [workload],
        appl,
        windows,
        workload.site_name,
        skip_generate_task=True,
        timeframe=TIMEFRAME_0,
    )["DC"]
    assert len(result) == 5

    appl["media_app"].set_software_safety(
        jobs_per_day=constants.JOBS_PER_DAY,
        dbs_15min_rpo=None,
        vm_clients=constants.VM_CLIENTS,
        concurrent_streams=1000,
        files=constants.MAXIMUM_FILES,
        images=10,
        max_cal_cap=None,
        max_universal_share=constants.MAXIMUM_NUMBER_OF_UNIVERSAL_SHARE,
    )

    # small limit on number of images should increase number of
    # appliances
    result = helper_core.pack(
        [workload],
        appl,
        windows,
        workload.site_name,
        skip_generate_task=True,
        timeframe=TIMEFRAME_0,
    )["DC"]
    assert len(result) > 5


def test_number_of_clients_do_not_affect_utilization(
    test_workloads_dict, test_appliances, windows
):
    appl = {
        "master_app": Appliance.from_json(test_appliances[0]),
        "media_app": Appliance.from_json(test_appliances[0]),
    }
    workload_data = test_workloads_dict["exp"].attr

    workload_data["number_of_clients"] = 10
    workload_data["workload_size"] = utils.Size.assume_unit(100, "GB")

    w1 = workload.Workload(workload_data)

    # changing number of clients should have no effect on capacity
    # utilization, as long as FETB is kept the same
    workload_data["number_of_clients"] = 20
    workload_data["workload_size"] = utils.Size.assume_unit(50, "GB")

    w2 = workload.Workload(workload_data)

    result1 = helper_core.pack([w1], appl, windows, w1.site_name)
    result2 = helper_core.pack([w2], appl, windows, w2.site_name)

    assert len(result1["DC"]) == len(result2["DC"])
    assert len(result1["DC"]) == 1

    utilization1 = result1.get_utilization("DC")
    utilization2 = result2.get_utilization("DC")

    for util1, util2 in zip(utilization1, utilization2):
        assert util1["capacity"] == pytest.approx(util2["capacity"])


def test_site_utilizations(test_workloads_dict, test_appliances, windows):
    appl = {
        "master_app": Appliance.from_json(test_appliances[0]),
        "media_app": Appliance.from_json(test_appliances[0]),
    }
    w = test_workloads_dict["exp"]

    result = helper_core.pack(
        [w],
        appl,
        windows,
        w.site_name,
    )

    utilizations = [
        result.get_site_utilization(w.site_name, yr)
        for yr in range(1, constants.FIRST_EXTENSION + 1)
    ]
    assert list(sorted(utilizations)) == utilizations


def test_cc_bandwidth_restrictions(test_workloads_dict, test_appliances, windows):
    appl = {
        "master_app": Appliance.from_json(test_appliances[0]),
        "media_app": Appliance.from_json(test_appliances[0]),
    }
    w1 = test_workloads_dict["dr_ltr_workload"]

    result1 = helper_core.pack([w1], appl, windows, w1.site_name)
    assert len(result1[w1.site_name]) == 6

    appl["media_app"].set_cloud_bandwidth(0)
    appl["media_app"]._cached_resources = appl["media_app"].calculate_resources()

    with pytest.raises(packing.WorkloadMisfitError):
        helper_core.pack([w1], appl, windows, w1.site_name)


def test_workload_io(test_workloads_dict, test_appliances, windows):
    appl = {
        "master_app": Appliance.from_json(test_appliances[0]),
        "media_app": Appliance.from_json(test_appliances[7]),
    }
    w1 = test_workloads_dict["files_backup"]
    w2 = test_workloads_dict["3_x_files_backup"]

    result1 = helper_core.pack([w1], appl, windows, w1.site_name)
    result2 = helper_core.pack([w2], appl, windows, w2.site_name)
    last_year = result1.num_years
    for yr in range(1, 1 + last_year):
        abs_io1 = result1.utilizations[w1.site_name][yr]["absolute_io"]
        abs_io2 = result2.utilizations[w2.site_name][yr]["absolute_io"]
        assert abs_io2 / abs_io1 == pytest.approx(3, rel=1e-3)


def test_workload_balancing(test_workloads_dict, test_appliances_dict, windows):
    appl = {
        "master_app": test_appliances_dict["5250 9TB"],
        "media_app": test_appliances_dict["5150 15TB"],
    }
    wk1 = test_workloads_dict["balancer1"]
    wk2 = test_workloads_dict["balancer2"]
    result = helper_core.pack([wk1, wk2], appl, windows, wk1.site_name)
    instances = [dist["assignment"][0]["total_inst"] for dist in result["DC"]]
    assert sum(instances) == 6


def test_packing_dr_workload_with_0_incr(test_appliances, windows):
    appl = {
        "master_app": Appliance.from_json(test_appliances[0]),
        "media_app": Appliance.from_json(test_appliances[0]),
    }

    wk = helper_core.workload_on_demand(
        "wk1",
        "Oracle",
        5,
        11,
        misc_policy="local",
        locations_policy="local+dr",
        retentions_policy="local+dr+0incr",
    )

    result1 = helper_core.pack([wk], appl, windows, wk.site_name)
    result2 = helper_core.pack([wk], appl, windows, wk.dr_dest)

    instances_dc = [dist["assignment"][0]["total_inst"] for dist in result1["DC"]]
    assert sum(instances_dc) == 11
    instances_sf = [dist["assignment"][0]["total_inst"] for dist in result2["SF"]]
    assert sum(instances_sf) == 11


def test_packing_utilizations_consistency(test_appliances, windows):
    appl = {
        "master_app": Appliance.from_json(test_appliances[0]),
        "media_app": Appliance.from_json(test_appliances[0]),
    }

    wk = helper_core.workload_on_demand(
        "wk1",
        "Oracle",
        5,
        11,
        misc_policy="local",
        locations_policy="local+dr",
        retentions_policy="local+double-dr",
    )
    result = helper_core.pack([wk], appl, windows, wk.site_name)
    dr_result = helper_core.pack([wk], appl, windows, wk.dr_dest)

    for res, site in [(result, wk.site_name), (dr_result, wk.dr_dest)]:
        for assign in res[site]:
            utilization = assign["utilization"]
            for yr in range(1, utils.DEFAULT_TIMEFRAME.num_years + 1):
                assert (
                    utilization[yr]["Full Backup"]
                    + utilization[yr]["Incremental Backup"]
                    == utilization[yr]["Size After Deduplication"]
                )
                assert (
                    utilization[yr]["Size Before Deduplication"]
                    >= utilization[yr]["Size After Deduplication"]
                )


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
