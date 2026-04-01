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


from use_core import appliance
from use_core import constants
from use_core import flex_packing
from use_core import utils
from use_core.utils import DEFAULT_TIMEFRAME

import helper_core


def flex_validate(
    per_appliance_safety_margins,
    workloads,
    appl_configs,
    windows,
    expected_appliances,
    expected_containers,
    expected_media,
    expected_configs=None,
    expected_msdp_cloud=0,
    rightsize=helper_core.default_rightsize,
):

    ctx = helper_core.make_sizer_context(
        per_appliance_safety_margins,
        workloads=workloads,
        media_configs=appl_configs["media"],
        master_configs=appl_configs["primary"],
        timeframe=DEFAULT_TIMEFRAME,
        window_sizes=windows,
        pack_flex=True,
        rightsize=rightsize,
    )
    result = ctx.pack()
    assert isinstance(result, flex_packing.FlexSizerResult)
    all_appliances = list(result.all_appliances)
    assert len(all_appliances) == expected_appliances

    assert hasattr(result, "workload_summary_attributes")

    usage = result.yoy_max_utilization
    for dim in ["cpu"]:
        assert usage[DEFAULT_TIMEFRAME.planning_year - 1][dim] < 1

    if expected_configs:
        for site_name, _, appl in all_appliances:
            assert expected_configs[site_name] == appl.appliance.config_name

    for _, _, appl in all_appliances:
        for dim in [
            "capacity",
            "absolute_capacity",
            "memory",
            "absolute_memory",
            "cpu",
            "io",
            "nic",
        ]:
            values = [
                appl.utilization.get("capacity", yr)
                for yr in range(1, DEFAULT_TIMEFRAME.num_years + 1)
            ]
            assert values == sorted(values)
        if dim in ["capacity", "memory", "cpu", "io", "nic_pct"]:
            assert appl.utilization.get(dim, DEFAULT_TIMEFRAME.planning_year) < 1

    wk_util = result.yoy_utilization_by_workload

    for wk in workloads:
        exp_util = wk_util[(wk.name, wk.site_name)]
        for dim in ["Storage Primary"]:
            dim_util = [
                exp_util.get(dim, yr)
                for yr in range(1, DEFAULT_TIMEFRAME.num_years + 1)
            ]
            assert dim_util == sorted(dim_util)
            assert utils.Size.ZERO not in dim_util or not wk.local_enabled

    expected_sites = set()
    for wk in workloads:
        expected_sites.add(wk.site_name)
        if wk.dr_enabled:
            expected_sites.add(wk.dr_dest)
    got_sites = set(site for (site, server_name, app) in all_appliances)
    assert got_sites == expected_sites

    total_containers = sum(
        len(app.containers) for (site, server_name, app) in all_appliances
    )
    assert total_containers == expected_containers

    all_containers = list(result.all_containers)
    app_names = set()
    container_names = set()
    primary_count = media_count = msdpc_count = 0
    expected_domains = set(wk.domain for wk in workloads)
    for container in all_containers:
        (
            domain,
            site,
            appliance_name,
            _appliance_obj,
            container_name,
            container_type,
            _obj,
        ) = container
        assert domain in expected_domains
        assert site in expected_sites
        app_names.add(appliance_name)
        container_names.add(container_name)
        if container_type == flex_packing.ContainerType.primary:
            primary_count += 1
        elif container_type == flex_packing.ContainerType.media:
            media_count += 1
        elif container_type == flex_packing.ContainerType.msdp_cloud:
            msdpc_count += 1
    assert len(app_names) == expected_appliances
    assert len(container_names) == expected_containers
    assert primary_count == len(expected_domains)
    assert media_count == expected_media


def test_flex_sizing(
    test_workloads_dict, test_appliances, windows, test_per_appliance_safety_margins
):
    appl = appliance.Appliance.from_json(test_appliances[0])
    media_appl = appliance.Appliance.from_json(test_appliances[6])
    wk1 = test_workloads_dict["exp"]
    wk2 = test_workloads_dict["exp_other_site"]

    flex_validate(
        test_per_appliance_safety_margins,
        workloads=[wk1, wk2],
        appl_configs={
            "media": {
                (wk1.domain, wk1.site_name): media_appl,
                (wk1.domain, wk2.site_name): media_appl,
            },
            "primary": {wk1.domain: appl},
        },
        windows=windows,
        expected_appliances=2,
        expected_containers=3,
        expected_media=2,
    )


def test_flex_sizing_huge_workload(
    test_workloads_dict, test_appliances, windows, test_per_appliance_safety_margins
):
    appl = appliance.Appliance.from_json(test_appliances[5])
    media_appl = appliance.Appliance.from_json(test_appliances[6])
    wk = test_workloads_dict["giant_workload_2021_02_11"]

    flex_validate(
        test_per_appliance_safety_margins,
        workloads=[wk],
        appl_configs={
            "media": {
                (wk.domain, wk.site_name): media_appl,
            },
            "primary": {wk.domain: appl},
        },
        windows=windows,
        expected_appliances=60,
        expected_containers=61,
        expected_media=60,
    )


def test_flex_sizing_appconfigs(
    test_workloads_dict,
    test_appliances_dict,
    windows,
    test_per_appliance_safety_margins,
):
    appl = test_appliances_dict["5150 15TB"]
    media_appl1 = test_appliances_dict["5340-FLEX 960TB"]
    media_appl2 = test_appliances_dict["5340-FLEX 1920TB"]

    wk1 = test_workloads_dict["exp"]
    wk2 = test_workloads_dict["exp_other_site"]

    flex_validate(
        test_per_appliance_safety_margins,
        workloads=[wk1, wk2],
        appl_configs={
            "media": {
                (wk1.domain, wk1.site_name): media_appl1,
                (wk1.domain, wk2.site_name): media_appl2,
            },
            "primary": {wk1.domain: appl},
        },
        windows=windows,
        expected_appliances=2,
        expected_containers=3,
        expected_media=2,
        expected_configs={
            wk1.site_name: media_appl1.config_name,
            wk2.site_name: media_appl2.config_name,
        },
        rightsize=helper_core.no_rightsize,
    )


def test_flex_sizing_msdp_limit(
    test_workloads_dict, test_appliances, windows, test_per_appliance_safety_margins
):
    appl = appliance.Appliance.from_json(test_appliances[0])
    media_appl = appliance.Appliance.from_json(test_appliances[6])
    media_appl.set_software_safety(
        jobs_per_day=constants.JOBS_PER_DAY,
        dbs_15min_rpo=None,
        vm_clients=constants.VM_CLIENTS,
        concurrent_streams=1000,
        files=constants.MAXIMUM_FILES,
        images=None,
        max_cal_cap=960,
        max_universal_share=constants.MAXIMUM_NUMBER_OF_UNIVERSAL_SHARE,
    )

    wk = test_workloads_dict["bulky_workload"]

    flex_validate(
        test_per_appliance_safety_margins,
        workloads=[wk],
        appl_configs={
            "media": {
                (wk.domain, wk.site_name): media_appl,
            },
            "primary": {wk.domain: appl},
        },
        windows=windows,
        expected_appliances=25,
        expected_containers=26,
        expected_media=25,
    )


def test_flex_sizing_ltr_with_roundup(
    test_workloads_dict, test_appliances, windows, test_per_appliance_safety_margins
):
    appl = appliance.Appliance.from_json(test_appliances[0])
    media_appl = appliance.Appliance.from_json(test_appliances[6])
    wk1 = test_workloads_dict["dr_ltr_workload"]
    wk2 = test_workloads_dict["ltr_only_workload"]

    flex_validate(
        test_per_appliance_safety_margins,
        workloads=[wk1, wk2],
        appl_configs={
            "media": {
                (wk1.domain, wk1.site_name): media_appl,
                (wk1.domain, wk1.dr_dest): media_appl,
                (wk1.domain, wk2.site_name): media_appl,
            },
            "primary": {wk1.domain: appl},
        },
        windows=windows,
        expected_appliances=4,
        expected_containers=8,
        expected_media=3,
        expected_msdp_cloud=1,
    )


def test_flex_sizing_ltr_without_roundup(
    test_workloads_dict, test_appliances, windows, test_per_appliance_safety_margins
):
    appl = appliance.Appliance.from_json(test_appliances[0])
    media_appl = appliance.Appliance.from_json(test_appliances[1])
    wk1 = test_workloads_dict["dr_ltr_workload"]
    wk2 = test_workloads_dict["ltr_only_workload"]

    flex_validate(
        test_per_appliance_safety_margins,
        workloads=[wk1, wk2],
        appl_configs={
            "media": {
                (wk1.domain, wk1.site_name): media_appl,
                (wk1.domain, wk1.dr_dest): media_appl,
                (wk1.domain, wk2.site_name): media_appl,
            },
            "primary": {wk1.domain: appl},
        },
        windows=windows,
        expected_appliances=12,
        expected_containers=17,
        expected_media=12,
        expected_msdp_cloud=1,
        rightsize=helper_core.no_rightsize,
    )


def test_flex_sizing_cpu(
    test_appliances_dict, windows, test_per_appliance_safety_margins
):
    master_appl = test_appliances_dict["5250 9TB"]
    media_appl = test_appliances_dict["5340-FLEX 1920TB"]

    wk1 = helper_core.workload_on_demand("wk1", "NDMP (Typical)", 568, 4, "local")
    wk2 = helper_core.workload_on_demand("wk2", "VMware", 200, 60, "local")
    wk3 = helper_core.workload_on_demand(
        "wk3", "File System (Typical)", 10, 10, "local"
    )

    flex_validate(
        test_per_appliance_safety_margins,
        workloads=[wk1, wk2, wk3],
        appl_configs={
            "media": {
                (wk1.domain, wk1.site_name): media_appl,
            },
            "primary": {wk1.domain: master_appl},
        },
        windows=windows,
        expected_appliances=6,
        expected_containers=8,
        expected_media=6,
    )


def test_flex_sizing_unsupported(
    test_appliances_dict, windows, test_per_appliance_safety_margins
):
    master_appl = test_appliances_dict["5250 9TB"]
    media_appl = test_appliances_dict["5340-HA-FLEX 1920TB"]

    wk = helper_core.workload_on_demand("wk", "File System (Typical)", 10, 10, "local")

    flex_validate(
        test_per_appliance_safety_margins,
        workloads=[wk],
        appl_configs={
            "media": {
                (wk.domain, wk.site_name): media_appl,
            },
            "primary": {wk.domain: master_appl},
        },
        windows=windows,
        expected_appliances=1,
        expected_containers=2,
        expected_media=1,
    )


def test_flex_sizing_workloads_isolation(
    test_workloads_dict, test_appliances, windows, test_per_appliance_safety_margins
):
    appl = appliance.Appliance.from_json(test_appliances[0])
    media_appl = appliance.Appliance.from_json(test_appliances[6])
    wk1 = test_workloads_dict["files_backup"]
    wk2 = test_workloads_dict["isolated_files_backup"]

    flex_validate(
        test_per_appliance_safety_margins,
        workloads=[wk1, wk2],
        appl_configs={
            "media": {
                (wk1.domain, wk1.site_name): media_appl,
            },
            "primary": {wk1.domain: appl},
        },
        windows=windows,
        expected_appliances=2,
        expected_containers=3,
        expected_media=2,
        expected_msdp_cloud=1,
    )
