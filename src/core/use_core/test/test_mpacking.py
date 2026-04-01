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

from collections import defaultdict
from copy import deepcopy
from unittest.mock import patch

import helper_core
import pytest

from use_core import (
    appliance,
    constants,
    flex_packing,
    packing,
    workload,
)
from use_core.utils import DEFAULT_TIMEFRAME, DEFAULT_WORST_CASE_CLOUD_FACTOR


def test_master_sizing(
    test_workloads_dict,
    test_appliances,
    windows,
    test_per_appliance_safety_margins,
):
    appl = appliance.Appliance.from_json(test_appliances[0])
    media_appl = appliance.Appliance.from_json(test_appliances[2])
    wk = test_workloads_dict["files_backup"]

    ctx = helper_core.make_sizer_context(
        test_per_appliance_safety_margins,
        workloads=[wk],
        window_sizes=windows,
        master_configs={wk.domain: appl},
        media_configs={(wk.domain, wk.site_name): media_appl},
    )

    result = ctx.pack()
    assert len(result.master_servers(wk.domain)) == 1
    storages = []
    for key, w_summary_objs in result.workload_summary_attributes.items():
        (wname, site) = key
        assert wname == wk.name
        for workload_obj in w_summary_objs:
            storages.append(workload_obj.storage_primary)
    assert storages == sorted(storages)
    assert storages[0] < storages[1]


def test_master_sizing_multiple_domains(
    test_workloads_dict, test_appliances, windows, test_per_appliance_safety_margins
):
    appl = appliance.Appliance.from_json(test_appliances[0])
    media_appl = appliance.Appliance.from_json(test_appliances[2])
    wk_src = test_workloads_dict["files_backup"].attr

    wk_src["domain"] = "Domain-2"
    wk1 = workload.Workload(wk_src)
    wk_src["domain"] = "Domain-3"
    wk2 = workload.Workload(wk_src)

    wk1.calculate_capacity(DEFAULT_TIMEFRAME)
    wk2.calculate_capacity(DEFAULT_TIMEFRAME)

    ctx = helper_core.make_sizer_context(
        test_per_appliance_safety_margins,
        workloads=[wk1, wk2],
        window_sizes=windows,
        master_configs={wk1.domain: appl, wk2.domain: appl},
        media_configs={
            (wk1.domain, wk1.site_name): media_appl,
            (wk2.domain, wk2.site_name): media_appl,
        },
        timeframe=DEFAULT_TIMEFRAME,
        rightsize=helper_core.no_rightsize,
    )
    result = ctx.pack()
    assert len(result.master_servers(wk1.domain)) == 1
    assert len(result.master_servers(wk2.domain)) == 1

    summary = result.summary
    assert summary.master_summary == {
        appl.config_name: {
            "Domain-2": {wk1.site_name: 1},
            "Domain-3": {wk1.site_name: 1},
        },
    }
    assert summary.media_summary == {
        media_appl.config_name: {
            "Domain-2": {wk1.site_name: 1},
            "Domain-3": {wk1.site_name: 1},
        },
    }


def test_packing_workload_utilization(
    test_workloads_dict, test_appliances, windows, test_per_appliance_safety_margins
):
    appl = appliance.Appliance.from_json(test_appliances[0])
    media_appl = appliance.Appliance.from_json(test_appliances[2])
    wk = test_workloads_dict["exp"]

    ctx = helper_core.make_sizer_context(
        test_per_appliance_safety_margins,
        workloads=[wk],
        window_sizes=windows,
        media_configs={(wk.domain, wk.site_name): media_appl},
        master_configs={wk.domain: appl},
        timeframe=DEFAULT_TIMEFRAME,
    )
    result = ctx.pack()

    wk_util = result.yoy_utilization_by_workload
    assert (wk.name, wk.site_name) in wk_util

    exp_util = wk_util[(wk.name, wk.site_name)]

    for dim in ["workload_capacity", "nic_workload"]:
        dim_util = [
            exp_util.get(dim, yr) for yr in range(1, DEFAULT_TIMEFRAME.num_years + 1)
        ]
        assert dim_util == sorted(dim_util)


@patch("use_core.constants.CONCURRENT_STREAMS", 195)
@patch("use_core.constants.JOBS_PER_DAY", 13000)
@patch("use_core.constants.NO_OF_IMAGES", 0)
@patch("use_core.constants.VM_CLIENTS", 3900)
def test_packing_utilization_with_mixed_appliances(
    test_workloads_dict, test_appliances, windows, test_per_appliance_safety_margins
):
    appl = appliance.Appliance.from_json(test_appliances[0])
    media_appl = appliance.Appliance.from_json(test_appliances[7])
    flex_appl = appliance.Appliance.from_json(test_appliances[8])
    wk = test_workloads_dict["default_example"]

    media_appl.set_software_safety(
        jobs_per_day=constants.JOBS_PER_DAY,
        dbs_15min_rpo=None,
        vm_clients=constants.VM_CLIENTS,
        concurrent_streams=constants.CONCURRENT_STREAMS,
        files=constants.MAXIMUM_FILES,
        images=constants.MAXIMUM_IMAGES,
        max_cal_cap=None,
        max_universal_share=constants.MAXIMUM_NUMBER_OF_UNIVERSAL_SHARE,
    )
    flex_appl.set_software_safety(
        jobs_per_day=constants.JOBS_PER_DAY,
        dbs_15min_rpo=None,
        vm_clients=constants.VM_CLIENTS,
        concurrent_streams=constants.CONCURRENT_STREAMS,
        files=constants.MAXIMUM_FILES,
        images=constants.MAXIMUM_IMAGES,
        max_cal_cap=None,
        max_universal_share=constants.MAXIMUM_NUMBER_OF_UNIVERSAL_SHARE,
        lun_size=65.5,
    )
    ctx1 = helper_core.make_sizer_context(
        test_per_appliance_safety_margins,
        workloads=[wk],
        window_sizes=windows,
        master_configs={wk.domain: appl},
        media_configs={(wk.domain, wk.site_name): media_appl},
        rightsize=helper_core.no_rightsize,
        pack_flex=False,
        master_sizing=False,
    )

    result1 = ctx1.pack()
    ctx2 = helper_core.make_sizer_context(
        test_per_appliance_safety_margins,
        workloads=[wk],
        window_sizes=windows,
        media_configs={(wk.domain, wk.site_name): flex_appl},
        master_configs={wk.domain: appl},
        timeframe=DEFAULT_TIMEFRAME,
        pack_flex=True,
        master_sizing=False,
        rightsize=helper_core.no_rightsize,
    )
    result2 = ctx2.pack()

    for _, _, _, app in result1.all_media_servers:
        wk_util1 = app.utilization
    for _, _, app in result2.all_appliances:
        wk_util2 = app.utilization

    for yr in range(1, DEFAULT_TIMEFRAME.num_years + 1):
        for dim in ["absolute_capacity", "capacity"]:
            assert wk_util1.get(dim, yr) == wk_util2.get(dim, yr)
        for dim in ["alloc_capacity", "alloc_capacity_pct"]:
            assert wk_util1.get(dim, yr) != wk_util2.get(dim, yr)


def test_packing_utilization_with_same_appliances(
    test_workloads_dict, test_appliances, windows, test_per_appliance_safety_margins
):
    appl = appliance.Appliance.from_json(test_appliances[0])
    media_appl = appliance.Appliance.from_json(test_appliances[9])
    flex_appl = appliance.Appliance.from_json(test_appliances[9])
    wk = test_workloads_dict["default_example"]

    ctx1 = helper_core.make_sizer_context(
        test_per_appliance_safety_margins,
        workloads=[wk],
        window_sizes=windows,
        media_configs={(wk.domain, wk.site_name): media_appl},
        master_configs={wk.domain: appl},
        timeframe=DEFAULT_TIMEFRAME,
        pack_flex=False,
        master_sizing=False,
        rightsize=helper_core.no_rightsize,
    )
    result1 = ctx1.pack()
    ctx2 = helper_core.make_sizer_context(
        test_per_appliance_safety_margins,
        workloads=[wk],
        window_sizes=windows,
        media_configs={(wk.domain, wk.site_name): flex_appl},
        master_configs={wk.domain: appl},
        timeframe=DEFAULT_TIMEFRAME,
        pack_flex=True,
        master_sizing=False,
        rightsize=helper_core.no_rightsize,
    )
    result2 = ctx2.pack()

    for _, _, _, app in result1.all_media_servers:
        wk_util1 = app.utilization
    for _, _, app in result2.all_appliances:
        wk_util2 = app.utilization

    for yr in range(1, DEFAULT_TIMEFRAME.num_years + 1):
        for dim in [
            "absolute_capacity",
            "alloc_capacity",
            "capacity",
            "alloc_capacity_pct",
        ]:
            assert wk_util1.get(dim, yr) == wk_util2.get(dim, yr)


def test_packing_error_decorator(
    test_appliances_dict, windows, test_per_appliance_safety_margins
):
    appl = test_appliances_dict["5240 4TB"]
    media_appl = test_appliances_dict["5240 4TB"]

    wk = [
        helper_core.workload_on_demand(
            "wk",
            "File System (Large Files)",
            fetb=50,
            clients=5,
            overrides={"annual_growth_rate": 0.8, "daily_change_rate": 0.8},
        )
    ]

    ctx = helper_core.make_sizer_context(
        test_per_appliance_safety_margins,
        workloads=wk,
        window_sizes=windows,
        media_configs={(w.domain, w.site_name): media_appl for w in wk},
        master_configs={w.domain: appl for w in wk},
        timeframe=DEFAULT_TIMEFRAME,
    )
    ctx._init_sizer_results()
    ctx.primary_workloads = ctx.workloads[:]

    @packing._continue_on_packing_error
    def mock_pack_error(sizer_context, exception, retry_on_error=False):
        if exception:  # not strictly required, but resolves editor highlighting issue
            raise exception("wk", "test mock generated error")

    # If not retrying on errors, the workload should throw a misfit exception
    with pytest.raises(packing.WorkloadMisfitMasterError):
        mock_pack_error(deepcopy(ctx), packing.WorkloadMisfitMasterError)

    mock_pack_error(
        deepcopy(ctx), packing.WorkloadMisfitMasterError, retry_on_error=True
    )

    with pytest.raises(packing.WorkloadMisfitMediaError):
        mock_pack_error(deepcopy(ctx), packing.WorkloadMisfitMediaError)

    with pytest.raises(packing.PackingError):
        mock_pack_error(
            deepcopy(ctx), packing.WorkloadMisfitMediaError, retry_on_error=True
        )


def test_packing_workload_misfit_error(
    test_appliances_dict, windows, test_per_appliance_safety_margins
):
    appl = test_appliances_dict["5240 4TB"]
    media_appl = test_appliances_dict["5240 4TB"]

    wk = [
        helper_core.workload_on_demand(
            "wk" + str(w),
            "File System (Large Files)",
            fetb=50,
            clients=5,
            overrides={"annual_growth_rate": 0.8, "daily_change_rate": 0.8},
        )
        for w in range(3)
    ]

    ctx = helper_core.make_sizer_context(
        test_per_appliance_safety_margins,
        workloads=wk,
        window_sizes=windows,
        media_configs={(w.domain, w.site_name): media_appl for w in wk},
        master_configs={w.domain: appl for w in wk},
        timeframe=DEFAULT_TIMEFRAME,
    )

    # If not retrying on errors, the workload should throw a misfit exception
    with pytest.raises(packing.WorkloadMisfitMediaError):
        deepcopy(ctx).pack()

    # if retrying on errors, should throw exception when all workloads fail
    with pytest.raises(packing.PackingError):
        deepcopy(ctx).pack(retry_on_error=True)


def test_packing_retry_on_error(
    test_appliances_dict, windows, test_per_appliance_safety_margins
):
    appl = test_appliances_dict["5250 9TB"]
    media_appl = test_appliances_dict["5250 9TB"]

    wk = [
        helper_core.workload_on_demand(
            "wk0",
            "Exchange",
            fetb=1,
            clients=1,
        ),
        helper_core.workload_on_demand(
            "wk1",
            "File System (Large Files)",
            fetb=50,
            clients=5,
            overrides={"annual_growth_rate": 0.8, "daily_change_rate": 0.8},
        ),
    ]

    ctx = helper_core.make_sizer_context(
        test_per_appliance_safety_margins,
        workloads=wk,
        window_sizes=windows,
        media_configs={(w.domain, w.site_name): media_appl for w in wk},
        master_configs={w.domain: appl for w in wk},
        timeframe=DEFAULT_TIMEFRAME,
    )

    # This should not generate an exception
    result = ctx.pack(retry_on_error=True)
    assert hasattr(result, "workload_error_list")
    assert "wk1" in result.workload_error_list
    assert "Sizing failed because:" in result.workload_error_list["wk1"]


def test_master_sizing_multiple_master_server(
    test_workloads_dict, test_appliances, windows, test_per_appliance_safety_margins
):
    appl = appliance.Appliance.from_json(test_appliances[4])
    media_appl = appliance.Appliance.from_json(test_appliances[2])
    wk_src = test_workloads_dict["files_backup"].attr
    workloads = []
    for i in range(4):
        wk_src["workload_name"] = f"files_backup_{i}"
        workloads.append(workload.Workload(wk_src))
    workload.calculate_capacity_all_workloads(
        workloads, DEFAULT_TIMEFRAME, DEFAULT_WORST_CASE_CLOUD_FACTOR
    )
    w1 = workloads[0]

    ctx = helper_core.make_sizer_context(
        test_per_appliance_safety_margins,
        workloads=workloads,
        media_configs={(w1.domain, w1.site_name): media_appl},
        master_configs={w1.domain: appl},
        timeframe=DEFAULT_TIMEFRAME,
        window_sizes=windows,
    )
    result = ctx.pack()
    all_domains = list(m[0] for m in result.all_master_servers)
    expected_domains = ["Domain-1_1", "Domain-1_2", "Domain-1_3", "Domain-1_4"]
    assert all_domains == expected_domains
    for d in expected_domains:
        assert len(result.master_servers(d)) == 1


def test_master_sizing_disabled(
    test_appliances_dict, windows, flex_choice, test_per_appliance_safety_margins
):
    master_appl = test_appliances_dict["5250 9TB"]
    media_appl = test_appliances_dict["5340 960TB"]

    wk = helper_core.workload_on_demand(
        "wk1", "File System (Large Files)", fetb=50, clients=5, policy_type="local"
    )
    ctx = helper_core.make_sizer_context(
        test_per_appliance_safety_margins,
        workloads=[wk],
        media_configs={(wk.domain, wk.site_name): media_appl},
        master_configs={wk.domain: master_appl},
        timeframe=DEFAULT_TIMEFRAME,
        window_sizes=windows,
        master_sizing=False,
        pack_flex=flex_choice,
    )
    result = ctx.pack()

    if flex_choice:
        master_servers = [
            ctr_obj
            for (
                _domain,
                _site,
                _app_name,
                _app_obj,
                _ctr_name,
                ctr_type,
                ctr_obj,
            ) in result.all_containers
            if ctr_type == flex_packing.ContainerType.primary
        ]
    else:
        master_servers = list(result.all_master_servers)

    assert master_servers == []


def test_workloads_isolation(
    test_workloads_dict, test_appliances, windows, test_per_appliance_safety_margins
):
    appl = appliance.Appliance.from_json(test_appliances[0])
    media_appl = appliance.Appliance.from_json(test_appliances[2])
    wk1_src = test_workloads_dict["files_backup"].attr
    wk2_src = test_workloads_dict["isolated_files_backup"].attr

    wk1 = workload.Workload(wk1_src)
    wk2 = workload.Workload(wk2_src)

    wk1.calculate_capacity(DEFAULT_TIMEFRAME)
    wk2.calculate_capacity(DEFAULT_TIMEFRAME)

    ctx = helper_core.make_sizer_context(
        test_per_appliance_safety_margins,
        workloads=[wk1, wk2],
        window_sizes=windows,
        media_configs={
            (wk1.domain, wk1.site_name): media_appl,
        },
        master_configs={wk1.domain: appl},
        timeframe=DEFAULT_TIMEFRAME,
        rightsize=helper_core.no_rightsize,
    )
    result = ctx.pack()
    assert len(result.master_servers(wk1.domain)) == 1

    summary = result.summary
    assert summary.master_summary == {
        appl.config_name: {
            "Domain-1": {wk1.site_name: 1},
        },
    }
    assert summary.media_summary == {
        media_appl.config_name: {
            "Domain-1": {wk1.site_name: 2},
        },
    }


def test_packing_transfer_volumes(
    test_appliances_dict, windows, test_per_appliance_safety_margins
):
    master_appl = test_appliances_dict["5250 9TB"]
    media_appl = test_appliances_dict["5340 960TB"]

    wk = helper_core.workload_on_demand(
        "wk",
        "File System (Typical)",
        5,
        11,
        misc_policy="local",
        locations_policy="local+dr+ltr",
        retentions_policy="local+dr+ltr_identical",
    )
    for yr in range(1, DEFAULT_TIMEFRAME.num_years + 1):
        assert wk.weekly_transfer_volume_ltr(yr) == wk.weekly_transfer_volume_dr(yr)
        assert wk.weekly_transfer_volume_ltr(yr) > 0

    ctx = helper_core.make_sizer_context(
        test_per_appliance_safety_margins,
        workloads=[wk],
        window_sizes=windows,
        media_configs={
            (wk.domain, wk.site_name): media_appl,
            (wk.domain, wk.dr_dest): media_appl,
        },
        master_configs={wk.domain: master_appl},
        timeframe=DEFAULT_TIMEFRAME,
        master_sizing=False,
        pack_flex=False,
    )
    result = ctx.pack()

    for ctr in result.all_servers:
        util = ctr.obj.utilization
        for y in range(1, DEFAULT_TIMEFRAME.num_years + 1):
            u = util.get("Cloud Transfer GiB/week", y)
            if ctr.site == wk.site_name:
                assert u > 0
            else:  # DR site
                assert u == 0


def test_packing_oracle(
    test_appliances_dict, windows, test_per_appliance_safety_margins
):
    master_appl = test_appliances_dict["5250 9TB"]
    media_appl = test_appliances_dict["5240 299TB"]

    wk = helper_core.workload_on_demand(
        "wk",
        "Oracle",
        82,
        1,
        policy_type="local",
        retentions_policy="2wk-local",
    )

    ctx = helper_core.make_sizer_context(
        test_per_appliance_safety_margins,
        workloads=[wk],
        window_sizes=windows,
        media_configs={
            (wk.domain, wk.site_name): media_appl,
            (wk.domain, wk.dr_dest): media_appl,
        },
        master_configs={wk.domain: master_appl},
        timeframe=DEFAULT_TIMEFRAME,
        master_sizing=False,
        pack_flex=False,
    )
    result = ctx.pack()

    assert result is not None


def test_primary_server_looks_at_dr_disposition(
    test_appliances_dict, windows, test_per_appliance_safety_margins
):
    master_appl = test_appliances_dict["5250 9TB"]
    media_appl = test_appliances_dict["5240 299TB"]

    wk = helper_core.workload_on_demand(
        "wk1",
        "File System (Typical)",
        100,
        5,
        misc_policy="local",
        locations_policy="local+dr",
        retentions_policy="local+double-dr",
    )

    ctx = helper_core.make_sizer_context(
        test_per_appliance_safety_margins,
        workloads=[wk],
        window_sizes=windows,
        media_configs={
            (wk.domain, wk.site_name): media_appl,
            (wk.domain, wk.dr_dest): media_appl,
        },
        master_configs={wk.domain: master_appl},
        timeframe=DEFAULT_TIMEFRAME,
        master_sizing=True,
        pack_flex=False,
    )
    result = ctx.pack()

    media_counts = defaultdict(int)
    for (
        _domain,
        site_name,
        _server_name,
        _assigned_appliance,
    ) in result.all_media_servers:
        media_counts[site_name] += 1
    primary_counts = defaultdict(int)
    for (
        _domain,
        site_name,
        _server_name,
        _assigned_appliance,
    ) in result.all_master_servers:
        primary_counts[site_name] += 1

    primary_site = wk.site_name
    dr_site = wk.dr_dest

    # verify that DR site uses more appliances (because of higher
    # retention)
    assert media_counts[dr_site] > media_counts[primary_site]

    # verify that the site hosting the DR target was *not* chosen
    # despite having more appliances
    assert primary_site in primary_counts


@pytest.mark.parametrize("flex", [False, True])
def test_sizing_25gbe(
    test_appliances_dict,
    windows,
    test_per_appliance_safety_margins,
    flex,
):
    appl = test_appliances_dict["5250 9TB"]
    if flex:
        media_appl = test_appliances_dict["5350-FLEX 1680TB"]
    else:
        media_appl = test_appliances_dict["5350 1680TB"]
    wk = helper_core.workload_on_demand(
        "wk1", "File System (Large Files)", 50, 5, "local"
    )
    wk_25gbe = helper_core.workload_on_demand(
        "wk1", "File System (Large Files)", 50, 5, "local", misc_policy="25gbe"
    )

    ctx = helper_core.make_sizer_context(
        test_per_appliance_safety_margins,
        workloads=[wk],
        window_sizes=windows,
        master_configs={wk.domain: appl},
        media_configs={(wk.domain, wk.site_name): media_appl},
        master_sizing=False,
        pack_flex=flex,
    )
    ctx_25gbe = helper_core.make_sizer_context(
        test_per_appliance_safety_margins,
        workloads=[wk_25gbe],
        window_sizes=windows,
        master_configs={wk.domain: appl},
        media_configs={(wk.domain, wk.site_name): media_appl},
        master_sizing=False,
        pack_flex=flex,
    )

    result = ctx.pack()
    result_25gbe = ctx_25gbe.pack()

    if flex:
        _site, _name, appl = list(result.all_appliances)[0]
        _site, _name, appl_25gbe = list(result_25gbe.all_appliances)[0]
    else:
        _domain, _site, _name, appl = list(result.all_media_servers)[0]
        _domain, _site, _name, appl_25gbe = list(result_25gbe.all_media_servers)[0]

    util = appl.utilization
    util_25gbe = appl_25gbe.utilization

    yoy_nw = [
        util.get("nic_pct", yr) for yr in range(1, DEFAULT_TIMEFRAME.num_years + 1)
    ]
    yoy_nw_25gbe = [
        util_25gbe.get("nic_pct", yr)
        for yr in range(1, DEFAULT_TIMEFRAME.num_years + 1)
    ]

    # sizing with 25gbe network should report less relative
    # utilization
    for nw, nw_25gbe in zip(yoy_nw, yoy_nw_25gbe):
        assert nw > nw_25gbe
