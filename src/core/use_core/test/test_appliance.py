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

import re

import pytest

from use_core import utils
from use_core.appliance import (
    Appliance,
    ModelNetworkMatchError,
    SiteHints,
    get_model_values,
)

visible_models_all = list(get_model_values().keys())


@pytest.fixture(
    params=[
        ("5150 15TB_Capacity 0_Shelves 64_RAM  4x1GbE 2x10GbE_SFP", "15TiB"),
        (
            "5240 299TB_Capacity 6_Shelves 256_RAM  4x1GbE 6x10GbE_SFP 2x10GbE_Copper 2x8Gb_FC",
            "294TiB",
        ),
        ("5250 36TB_Capacity 0_Shelves 64_RAM  4x1GbE 2x10GbE_SFP", "36TiB"),
        (
            "5250-FLEX 402TB_Capacity 6_Shelves 512_RAM  4x1GbE 6x10GbE_Copper 4x16Gb_FC",
            "402TiB",
        ),
        (
            "5340 480TB_Capacity 2_Shelves 1536_RAM  4x1GbE 8x10GbE_SFP 2x16Gb_FC",
            "480TiB",
        ),
        ("5340 1920TB_Capacity 4_Shelves 1536_RAM  4x1GbE 10x10GbE_SFP", "960TiB"),
        ("5340-FLEX 480TB_Capacity 2_Shelves 1536_RAM  4x1GbE 10x10GbE_SFP", "480TiB"),
        ("5340-HA 1920TB_Capacity 4_Shelves 1536_RAM  4x1GbE 20x10GbE_SFP", "960TiB"),
        (
            "5340-HA-FLEX 840TB_Capacity 3.5_Shelves 1536_RAM  4x1GbE 20x10GbE_SFP",
            "840TiB",
        ),
        (
            "5350 1200TB_Capacity 2.5_Shelves 1536_RAM  4x1GbE 4x10GbE_SFP 6x16Gb_FC",
            "960TiB",
        ),
        (
            "5350-FLEX 1440TB_Capacity 3_Shelves 1536_RAM  4x1GbE 6x10GbE_SFP 4x16Gb_FC",
            "960TiB",
        ),
        (
            "5350-HA-FLEX 720TB_Capacity 1.5_Shelves 768_RAM  4x1GbE 8x10GbE_SFP 12x16Gb_FC",
            "720TiB",
        ),
    ]
)
def capped_calculated_capacity_scenario(request):
    yield request.param


def test_capped_calculated_capacity(
    capped_calculated_capacity_scenario, test_per_appliance_safety_margins
):
    (
        config_name,
        expected_capped_calculated_capacity,
    ) = capped_calculated_capacity_scenario

    [ap] = Appliance.match_config(
        [config_name], safety=test_per_appliance_safety_margins
    )
    assert ap.disk_capacity == utils.Size.from_string(
        expected_capped_calculated_capacity
    )


@pytest.fixture(
    params=[
        ("5150 15TB_Capacity 0_Shelves 64_RAM  4x1GbE 2x10GbE_SFP", "2TiB"),
        (
            "5240 299TB_Capacity 6_Shelves 256_RAM  4x1GbE 6x10GbE_SFP 2x10GbE_Copper 2x8Gb_FC",
            "6TiB",
        ),
        ("5250 36TB_Capacity 0_Shelves 64_RAM  4x1GbE 2x10GbE_SFP", "7TiB"),
        (
            "5250-FLEX 402TB_Capacity 6_Shelves 512_RAM  4x1GbE 6x10GbE_Copper 4x16Gb_FC",
            "12TiB",
        ),
        (
            "5340 480TB_Capacity 2_Shelves 1536_RAM  4x1GbE 8x10GbE_SFP 2x16Gb_FC",
            "336TiB",
        ),
        ("5340 1920TB_Capacity 4_Shelves 1536_RAM  4x1GbE 10x10GbE_SFP", "480TiB"),
        ("5340-FLEX 480TB_Capacity 2_Shelves 1536_RAM  4x1GbE 10x10GbE_SFP", "5TiB"),
        ("5340-HA 1920TB_Capacity 4_Shelves 1536_RAM  4x1GbE 20x10GbE_SFP", "672TiB"),
        (
            "5340-HA-FLEX 840TB_Capacity 3.5_Shelves 1536_RAM  4x1GbE 20x10GbE_SFP",
            "5TiB",
        ),
        (
            "5350 1200TB_Capacity 2.5_Shelves 1536_RAM  4x1GbE 4x10GbE_SFP 6x16Gb_FC",
            "480TiB",
        ),
        (
            "5350-FLEX 1440TB_Capacity 3_Shelves 1536_RAM  4x1GbE 6x10GbE_SFP 4x16Gb_FC",
            "5TiB",
        ),
        (
            "5350-HA-FLEX 720TB_Capacity 1.5_Shelves 768_RAM  4x1GbE 8x10GbE_SFP 12x16Gb_FC",
            "5TiB",
        ),
    ]
)
def catalog_size_scenario(request):
    yield request.param


def test_catalog_size(catalog_size_scenario, test_per_appliance_safety_margins):
    config_name, expected_catalog_size = catalog_size_scenario

    [ap] = Appliance.match_config(
        [config_name], safety=test_per_appliance_safety_margins
    )
    safe_catalog_size = utils.Size.from_string(expected_catalog_size)
    assert ap.catalog_size == safe_catalog_size


def test_dr_condidate(test_appliances, test_appliances_with_non_5150):
    a1 = Appliance.from_json(test_appliances[0])
    a2 = Appliance.from_json(test_appliances_with_non_5150[0])

    assert not a1.dr_candidate
    assert a2.dr_candidate


NO_MARGINS = {
    "Memory": 1.0,
    "CPU": 1.0,
    "Capacity": 1.0,
    "NW": 1.0,
    "IO": 1.0,
    "Max_Cal_Cap": 960,
    "Max_Catalog_Size": None,
}
SAFETY = {
    "5150": NO_MARGINS,
    "5240": NO_MARGINS,
    "5250": NO_MARGINS,
    "5250-FLEX": NO_MARGINS,
    "5260-FLEX": NO_MARGINS,
    "5340": NO_MARGINS,
    "5340-FLEX": NO_MARGINS,
    "5340-HA": NO_MARGINS,
    "5340-HA-FLEX": NO_MARGINS,
    "5350": NO_MARGINS,
    "5350-FLEX": NO_MARGINS,
    "5350-HA-FLEX": NO_MARGINS,
    "5360-FLEX": NO_MARGINS,
    "5360-HA-FLEX": NO_MARGINS,
}

error = object()


@pytest.fixture(
    params=[
        # explicitly ask for specific model/storage combination
        (
            None,
            visible_models_all,
            "5150 15TB",
            ["1GbE"],
            {},
            "5150 15TB_Capacity 0_Shelves 64_RAM  8x1GbE",
        ),
        (
            None,
            visible_models_all,
            "5240 299TB",
            ["1GbE"],
            {},
            "5240 299TB_Capacity 6_Shelves 256_RAM  4x1GbE 2x10GbE_Copper",
        ),
        (
            None,
            visible_models_all,
            "5350 480TB",
            ["1GbE"],
            {},
            "5350 480TB_Capacity 2_Shelves 768_RAM  4x1GbE 8x10GbE_SFP 2x16Gb_FC",
        ),
        # ask for invalid model/network combination
        (
            None,
            visible_models_all,
            "5150 15TB",
            ["1GbE", "10GbE Copper", "10GbE SFP"],
            {},
            error,
        ),
        ("5340", visible_models_all, None, ["10GbE Copper"], {}, error),
        # validate hinting with workload suitable for 5150
        (
            None,
            visible_models_all,
            None,
            ["1GbE", "10GbE Copper"],
            {"disk": "5TiB"},
            "5150 15TB_Capacity 0_Shelves 64_RAM  4x1GbE 2x10GbE_Copper",
        ),
        # specify only model
        (
            "5240",
            visible_models_all,
            None,
            ["1GbE"],
            {"disk": "280TiB"},
            "5240 299TB_Capacity 6_Shelves 256_RAM  4x1GbE 2x10GbE_Copper",
        ),
        (
            "5250",
            visible_models_all,
            None,
            ["1GbE"],
            {"disk": "30TiB"},
            "5250 74.5TB_Capacity 1_Shelves 256_RAM  4x1GbE 2x10GbE_SFP",
        ),
        (
            "5350",
            visible_models_all,
            None,
            ["1GbE", "10GbE SFP"],
            {"disk": "100TiB"},
            "5350 960TB_Capacity 4_Shelves 1536_RAM  4x1GbE 8x10GbE_SFP 2x16Gb_FC",
        ),
        # validate regular hinting is overridden by explicit model specification
        (
            "5150",
            visible_models_all,
            None,
            ["1GbE"],
            {"disk": "20TiB", "dr_dest": True},
            "5150 15TB_Capacity 0_Shelves 64_RAM  8x1GbE",
        ),
        (
            "5150",
            visible_models_all,
            None,
            ["1GbE", "10GbE SFP"],
            {"disk": "20TiB", "dr_dest": True},
            "5150 15TB_Capacity 0_Shelves 64_RAM  4x1GbE 2x10GbE_SFP",
        ),
        (
            "5340",
            visible_models_all,
            None,
            ["10GbE SFP"],
            {"disk": "40TiB"},
            "^5340 .*$",
        ),
        # validate hinting with workloads unsuitable for 5150
        (
            None,
            visible_models_all,
            None,
            ["1GbE", "10GbE Copper"],
            {"disk": "5TiB", "dr_dest": True},
            "^(5250|5350) .*$",
        ),
        (
            None,
            visible_models_all,
            None,
            ["1GbE", "10GbE Copper"],
            {"disk": "20TiB"},
            "^(5250|5350) .*$",
        ),
        (
            None,
            visible_models_all,
            None,
            ["10GbE SFP"],
            {"disk": "20TiB", "dr_dest": True},
            "^(5250|5350) .*$",
        ),
        # validate hinting with workloads unsuitable for 5240/5340
        (
            None,
            visible_models_all,
            None,
            ["1GbE", "10GbE SFP"],
            {"disk": "14TiB", "ltr_src": True},
            "5150 15TB_Capacity 0_Shelves 64_RAM  4x1GbE 2x10GbE_SFP",
        ),
        # flex/non-flex mismatch
        ("5340-FLEX", visible_models_all, None, ["1GbE"], {"disk": "20TiB"}, error),
        ("5350-FLEX", visible_models_all, None, ["1GbE"], {"disk": "20TiB"}, error),
    ]
)
def match_name_network_testcase(request):
    yield request.param


def test_match_name_network(match_name_network_testcase):
    (
        model,
        visible_models,
        display_name,
        network_types,
        hints,
        expected,
    ) = match_name_network_testcase
    site_hints = SiteHints(
        disk=utils.Size.from_string(hints.get("disk", "0PiB")),
        dr_dest=hints.get("dr_dest", False),
        ltr_src=hints.get("ltr_src", False),
        sizing_flex=hints.get("sizing_flex", False),
    )
    if error is expected:
        with pytest.raises(ModelNetworkMatchError):
            Appliance.match_name_network(
                model, visible_models, display_name, network_types, site_hints, SAFETY
            )
    else:
        assert re.match(
            expected,
            Appliance.match_name_network(
                model, visible_models, display_name, network_types, site_hints, SAFETY
            ),
        )


@pytest.fixture(
    params=[
        # explicitly ask for specific model/storage combination
        (
            None,
            visible_models_all,
            "5150 15TB",
            ["1GbE"],
            {},
            "5150 15TB_Capacity 0_Shelves 64_RAM  8x1GbE",
        ),
        (
            None,
            visible_models_all,
            "5240 299TB",
            ["1GbE"],
            {},
            error,
        ),
        (
            None,
            visible_models_all,
            "5350 480TB",
            ["1GbE"],
            {},
            error,
        ),
        # ask for invalid model/network combination
        (
            None,
            visible_models_all,
            "5150 15TB",
            ["1GbE", "10GbE Copper", "10GbE SFP"],
            {},
            error,
        ),
        ("5340", visible_models_all, None, ["10GbE Copper"], {}, error),
        # validate hinting with workload suitable for 5150
        (
            None,
            visible_models_all,
            None,
            ["1GbE", "10GbE Copper"],
            {"disk": "5TiB"},
            "5150 15TB_Capacity 0_Shelves 64_RAM  4x1GbE 2x10GbE_Copper",
        ),
        # specify only model
        (
            "5240",
            visible_models_all,
            None,
            ["1GbE"],
            {"disk": "280TiB"},
            error,
        ),
        (
            "5250",
            visible_models_all,
            None,
            ["1GbE"],
            {"disk": "30TiB"},
            error,
        ),
        (
            "5350-FLEX",
            visible_models_all,
            None,
            ["1GbE", "10GbE SFP"],
            {"disk": "100TiB"},
            "5350-FLEX 960TB_Capacity 4_Shelves 1536_RAM  4x1GbE 8x10GbE_SFP 2x16Gb_FC",
        ),
        # validate regular hinting is overridden by explicit model specification
        (
            "5150",
            visible_models_all,
            None,
            ["1GbE"],
            {"disk": "20TiB", "dr_dest": True},
            "5150 15TB_Capacity 0_Shelves 64_RAM  8x1GbE",
        ),
        (
            "5150",
            visible_models_all,
            None,
            ["1GbE", "10GbE SFP"],
            {"disk": "20TiB", "dr_dest": True},
            "5150 15TB_Capacity 0_Shelves 64_RAM  4x1GbE 2x10GbE_SFP",
        ),
        (
            "5340-FLEX",
            visible_models_all,
            None,
            ["10GbE SFP"],
            {"disk": "40TiB"},
            "^5340-FLEX .*$",
        ),
        # validate hinting with workloads unsuitable for 5150
        (
            None,
            visible_models_all,
            None,
            ["1GbE", "10GbE Copper"],
            {"disk": "5TiB", "dr_dest": True},
            "^5250-FLEX .*$",
        ),
        (
            None,
            visible_models_all,
            None,
            ["1GbE", "10GbE Copper"],
            {"disk": "20TiB"},
            "^(5150|5250-FLEX|5340-FLEX|5340-HA-FLEX|5350-FLEX|5350-HA-FLEX) .*$",
        ),
        (
            None,
            visible_models_all,
            None,
            ["10GbE SFP"],
            {"disk": "20TiB", "dr_dest": True},
            "^(5150|5250-FLEX|5340-FLEX|5340-HA-FLEX|5350-FLEX|5350-HA-FLEX) .*$",
        ),
        # validate hinting with workloads unsuitable for 5240/5340
        (
            None,
            visible_models_all,
            None,
            ["1GbE", "10GbE SFP"],
            {"disk": "20TiB", "ltr_src": True},
            "5250-FLEX 74.5TB_Capacity 1_Shelves 256_RAM  4x1GbE 6x10GbE_SFP 4x16Gb_FC",
        ),
        # flex/non-flex mismatch
        ("5340", visible_models_all, None, ["1GbE"], {"disk": "20TiB"}, error),
        ("5350", visible_models_all, None, ["1GbE"], {"disk": "20TiB"}, error),
    ]
)
def match_name_network_with_flex_testcase(request):
    yield request.param


def test_match_name_network_with_flex(match_name_network_with_flex_testcase):
    (
        model,
        visible_models,
        display_name,
        network_types,
        hints,
        expected,
    ) = match_name_network_with_flex_testcase
    site_hints = SiteHints(
        disk=utils.Size.from_string(hints.get("disk", "0PiB")),
        dr_dest=hints.get("dr_dest", False),
        ltr_src=hints.get("ltr_src", False),
        sizing_flex=hints.get("sizing_flex", True),
    )
    if error is expected:
        with pytest.raises(ModelNetworkMatchError):
            Appliance.match_name_network(
                model, visible_models, display_name, network_types, site_hints, SAFETY
            )
    else:
        assert re.match(
            expected,
            Appliance.match_name_network(
                model, visible_models, display_name, network_types, site_hints, SAFETY
            ),
        )


def test_cal_cap_used_for_huge_requirements():
    # Once the required capacity is more than max_cal_cap, we should
    # always pick the same appliance.  Picking a larger appliance is
    # of no use because we will not use the extra space anyway.

    site_hints1 = SiteHints(
        disk=utils.Size.from_string("3PiB"), dr_dest=True, ltr_src=False
    )
    site_hints2 = SiteHints(
        disk=utils.Size.from_string("2PiB"), dr_dest=True, ltr_src=False
    )
    result1 = Appliance.match_name_network(
        "5340", visible_models_all, None, ["10GbE SFP"], site_hints1, SAFETY
    )
    result2 = Appliance.match_name_network(
        "5340", visible_models_all, None, ["10GbE SFP"], site_hints2, SAFETY
    )

    print(f"result1: {result1}, result2: {result2}")
    assert result1 == result2


@pytest.fixture(
    params=[
        ("5340 1920TB", "120TiB", False, "5340 240TB"),
        ("5340-FLEX 1920TB", "970TiB", True, "5340-FLEX 1200TB"),
        ("5350 1200TB", "120TiB", False, "5350 960TB"),
        ("5350-FLEX 1680TB", "970TiB", True, "5350-FLEX 1200TB"),
    ]
)
def rightsize_testcase(request):
    yield request.param


def test_rightsize(test_appliances_dict, rightsize_testcase):
    (orig, cap, flex, new) = rightsize_testcase

    appl = test_appliances_dict[orig]

    cap = utils.Size.from_string(cap)
    new_appl = appl.rightsize(cap, flex=flex)

    assert new in new_appl.config_name


@pytest.fixture(
    params=[
        ("1TiB", {"5150"}, "^5150 15TB"),
        ("1TiB", {"5250"}, "^5250 9TB"),
        ("12TiB", {"5250"}, "^5250 36TB"),
        ("1TiB", {"5340"}, "^5250 9TB"),
    ]
)
def find_management_testcase(request):
    yield request.param


def test_find_management(find_management_testcase, test_per_appliance_safety_margins):
    (catalog_size_str, models, expected) = find_management_testcase
    catalog_size = utils.Size.from_string(catalog_size_str)
    choice = Appliance.find_management(
        catalog_size, models, test_per_appliance_safety_margins
    )
    assert re.match(expected, choice)


@pytest.fixture(
    params=[
        ("5150 15TB_Capacity 0_Shelves 64_RAM  4x1GbE 2x10GbE_SFP", 1),
        (
            "5240 299TB_Capacity 6_Shelves 256_RAM  4x1GbE 6x10GbE_SFP 2x10GbE_Copper 2x8Gb_FC",
            10,
        ),
        ("5250 36TB_Capacity 0_Shelves 64_RAM  4x1GbE 2x10GbE_SFP", 20),
        (
            "5250-FLEX 402TB_Capacity 6_Shelves 512_RAM  4x1GbE 6x10GbE_Copper 4x16Gb_FC",
            20,
        ),
        (
            "5340 480TB_Capacity 2_Shelves 1536_RAM  4x1GbE 8x10GbE_SFP 2x16Gb_FC",
            30,
        ),
        ("5340 1920TB_Capacity 4_Shelves 1536_RAM  4x1GbE 10x10GbE_SFP", 30),
        ("5340-FLEX 480TB_Capacity 2_Shelves 1536_RAM  4x1GbE 10x10GbE_SFP", 30),
        ("5340-HA 1920TB_Capacity 4_Shelves 1536_RAM  4x1GbE 20x10GbE_SFP", 30),
        (
            "5340-HA-FLEX 840TB_Capacity 3.5_Shelves 1536_RAM  4x1GbE 20x10GbE_SFP",
            50,
        ),
        (
            "5350 1200TB_Capacity 2.5_Shelves 1536_RAM  4x1GbE 4x10GbE_SFP 6x16Gb_FC",
            40,
        ),
        (
            "5350-FLEX 1440TB_Capacity 3_Shelves 1536_RAM  4x1GbE 6x10GbE_SFP 4x16Gb_FC",
            40,
        ),
        (
            "5350-HA-FLEX 720TB_Capacity 1.5_Shelves 768_RAM  4x1GbE 8x10GbE_SFP 12x16Gb_FC",
            50,
        ),
    ]
)
def universal_share_safety_margin_scenario(request):
    yield request.param


def test_universal_share_safety_margin(
    universal_share_safety_margin_scenario, test_per_appliance_safety_margins
):
    (
        config_name,
        expected_max_universal_share,
    ) = universal_share_safety_margin_scenario

    [ap] = Appliance.match_config(
        [config_name], safety=test_per_appliance_safety_margins
    )
    assert ap.max_universal_share == expected_max_universal_share
