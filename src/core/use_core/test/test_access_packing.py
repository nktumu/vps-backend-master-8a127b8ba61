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

import pytest

from use_core import access_appliance
from use_core import constants
from use_core import packing
from use_core import settings
from use_core.utils import DEFAULT_TIMEFRAME, Size

import helper_core


@pytest.fixture(
    params=[
        (True, "5340-FLEX 960TB"),
        (False, "5340 960TB"),
    ]
)
def simple_access_sizing_scenario(request):
    return request.param


def test_simple_access_sizing(
    test_appliances_dict,
    windows,
    simple_access_sizing_scenario,
    test_per_appliance_safety_margins,
):
    (pack_flex, media_choice) = simple_access_sizing_scenario
    master_appl = test_appliances_dict["5250 9TB"]
    media_appl = test_appliances_dict[media_choice]

    wk = helper_core.workload_on_demand(
        "wk1",
        "File System (Large Files)",
        fetb=50,
        clients=5,
        misc_policy="local",
        locations_policy="local+ltr",
        retentions_policy="local+access",
    )
    ctx = helper_core.make_sizer_context(
        test_per_appliance_safety_margins,
        workloads=[wk],
        media_configs={(wk.domain, wk.site_name): media_appl},
        master_configs={wk.domain: master_appl},
        timeframe=DEFAULT_TIMEFRAME,
        window_sizes=windows,
        pack_flex=pack_flex,
        ltr_target=settings.LtrType.ACCESS,
        access_choice=access_appliance.AccessAppliance.stub(),
        excess_cloud_storage=0,
    )
    result = ctx.pack()

    assert result.access_result is not None
    acc_appliances = list(result.access_result.all_appliances)
    assert len(acc_appliances) == 1
    [(site_name, _app_name, assigned_appliance)] = acc_appliances
    assert site_name == wk.site_name
    assert assigned_appliance.appliance.name == "Access 3340 (255TiB) 280TB"


@pytest.fixture(
    params=[
        # max_capacity, expected_count, config
        (1.0, 2, "Access 3340 (2544TiB) 2800TB"),
        (0.5, 4, "Access 3340 (2544TiB) 2800TB"),
    ]
)
def safety_scenario(request):
    yield request.param


def test_access_sizing_safety(
    test_appliances_dict, windows, safety_scenario, test_per_appliance_safety_margins
):
    master_appl = test_appliances_dict["5250 9TB"]
    media_appl = test_appliances_dict["5340 960TB"]

    workloads = []
    for i in range(20):
        workloads.append(
            helper_core.workload_on_demand(
                "wk1",
                "File System (Large Files)",
                fetb=50,
                clients=5,
                misc_policy="local",
                locations_policy="local+ltr",
                retentions_policy="local+access",
            )
        )

    access_app = access_appliance.AccessAppliance()

    capacity_safety, expected_count, expected_config = safety_scenario
    access_app.set_safety_limits(
        {"Access 3340": {"Capacity": capacity_safety, "CPU": 1.0}}
    )
    ctx = helper_core.make_sizer_context(
        test_per_appliance_safety_margins,
        workloads=workloads,
        media_configs={(workloads[0].domain, workloads[0].site_name): media_appl},
        master_configs={workloads[0].domain: master_appl},
        timeframe=DEFAULT_TIMEFRAME,
        window_sizes=windows,
        pack_flex=False,
        ltr_target=settings.LtrType.ACCESS,
        access_choice=access_app,
        excess_cloud_storage=0,
    )
    result = ctx.pack()

    assert result.access_result is not None
    acc_appliances = list(result.access_result.all_appliances)
    assert len(acc_appliances) == expected_count

    for site_name, _app_name, assigned_appliance in acc_appliances:
        assert site_name == workloads[0].site_name
        assert assigned_appliance.appliance.name == expected_config

        for dim in ["absolute_capacity", "capacity"]:
            yoy_util = [
                assigned_appliance.utilization.get(dim, yr)
                for yr in range(1, 1 + DEFAULT_TIMEFRAME.num_years)
            ]
            assert yoy_util == sorted(yoy_util)

        assert (
            assigned_appliance.utilization.get(dim, DEFAULT_TIMEFRAME.planning_year) < 1
        )


def test_msdp_cloud_limit(
    test_appliances_dict, windows, test_per_appliance_safety_margins
):
    master_appl = test_appliances_dict["5250 9TB"]
    media_appl = test_appliances_dict["5340 960TB"]

    wk = helper_core.workload_on_demand(
        "wk",
        "Image Files",
        fetb=800,
        clients=50,
        misc_policy="local",
        locations_policy="ltr-only",
        retentions_policy="0local+access-long",
    )
    ctx = helper_core.make_sizer_context(
        test_per_appliance_safety_margins,
        workloads=[wk],
        media_configs={(wk.domain, wk.site_name): media_appl},
        master_configs={wk.domain: master_appl},
        timeframe=DEFAULT_TIMEFRAME,
        window_sizes=windows,
        pack_flex=False,
        ltr_target=settings.LtrType.ACCESS,
        access_choice=access_appliance.AccessAppliance.stub(),
    )

    result = ctx.pack()
    for _domain, _site_name, _appliance_name, media_server in result.all_media_servers:
        size_limit = Size.assume_unit(constants.MSDP_CLOUD_TOTAL_LSU_PB, "PiB")
        total_cloud = Size.ZERO
        for assigned_wkload in media_server.workloads:
            util = assigned_wkload.w_utilization
            total_cloud += util.get("Storage Cloud", DEFAULT_TIMEFRAME.planning_year)
        assert total_cloud <= size_limit


def test_bottlenecks_calculation_includes_cloud(
    test_appliances_dict, windows, test_per_appliance_safety_margins
):
    master_appl = test_appliances_dict["5250 9TB"]
    media_appl = test_appliances_dict["5240 299TB"]

    wk = helper_core.workload_on_demand(
        "wk1",
        "Image Files",
        42,
        1,
        misc_policy="local",
        locations_policy="ltr-only",
        retentions_policy="local-4wk+access-5yr",
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
        ltr_target=settings.LtrType.ACCESS,
        access_choice=access_appliance.AccessAppliance.stub(),
    )

    # The workload requires more than 1PiB of cloud storage, so should
    # raise a misfit error
    with pytest.raises(packing.WorkloadMisfitMediaError):
        ctx.pack()
