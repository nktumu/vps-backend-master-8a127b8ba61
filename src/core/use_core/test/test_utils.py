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

import datetime
import re

import pytest

from use_core import utils


def test_parse_size_unit():
    assert utils.Size.from_string("32TiB") == utils.Size(value=32, unit="TiB")
    with pytest.raises(ValueError):
        utils.Size.from_string("42")


def test_value_of_float():
    sz1 = utils.Size(65.5, "TiB")
    sz2 = utils.Size(65.51, "TiB")
    assert repr(sz1) == "65.5TiB"
    assert repr(sz2) == "65.51TiB"
    assert sz1 == 65.5 * utils.Size.UNIT_SCALES["TiB"]
    assert sz2 == 65.51 * utils.Size.UNIT_SCALES["TiB"]
    assert sz1 < sz2
    assert sz1 / sz2 == pytest.approx(0.9998, rel=1e-4)


def test_assume_unit():
    assert utils.Size.assume_unit("32", "TiB") == utils.Size(value=32, unit="TiB")
    with pytest.raises(ValueError):
        utils.Size.assume_unit("not-a-number", "TiB")
    with pytest.raises(ValueError):
        utils.Size.assume_unit("32", "not-a-unit")
    with pytest.raises(ValueError):
        utils.Size(32, "not-a-unit")


def test_unit_repr():
    sz = utils.Size.from_string("32TiB")
    assert repr(sz) == "32.0TiB"


def test_unit_with_scaling():
    cases = [
        ("32TiB", 0.5, "16TiB"),
        ("32TiB", 0.2, "6TiB"),
        ("32TiB", 0.55, "18TiB"),
        ("16TiB", 3, "48TiB"),
    ]
    for capacity, scale, new_capacity in cases:
        size1 = utils.Size.from_string(capacity)
        size2 = size1.new_size_scaled(scale)
        size3 = utils.Size.from_string(new_capacity)
        assert size2 == size3


def test_size_arithmetic():
    sz = utils.Size.from_string("32TiB")
    assert sz * 2 == utils.Size.from_string("64TiB")
    assert sz / 4 == utils.Size.from_string("8TiB")
    assert int(sz) == 32 * 1024 * 1024 * 1024
    with pytest.raises(TypeError):
        sz * "invalid"
    sz2 = utils.Size.from_string("1TiB")
    assert sz + sz2 == utils.Size.from_string("33TiB")
    sz3 = utils.Size.from_string("512GiB")
    assert sz2 + sz3 == utils.Size.from_string(f"{1024+512}GiB")

    assert utils.Size.sum([sz2, sz3]) == sz2 + sz3

    assert sz2 / sz3 == 1024 / 512
    assert sz3 / sz2 == 512 / 1024


def test_size_roundup():
    cases = [
        ("50TiB", "80TiB"),
        ("80TiB", "80TiB"),
        ("90TiB", "160TiB"),
    ]
    fac = utils.Size.from_string("80TiB")
    for s, expected in cases:
        sz = utils.Size.from_string(s)
        exp = utils.Size.from_string(expected)
        assert sz.roundup(fac) == exp


def test_utilization():
    cases = [
        ("32TiB", ["8TiB"] * 4, 100),
        ("32TiB", ["6TiB"] * 5, 93),
        ("32TiB", ["6TiB"] * 6, 112),
    ]
    for capacity, items, expected in cases:
        capacity_sz = utils.Size.from_string(capacity)
        items = [utils.Size.from_string(item) for item in items]
        assert expected == int(capacity_sz.utilization(items) * 100)


def test_sanitize_named_range():
    valid_name = re.compile("^[a-zA-Z_][a-zA-Z0-9_.]*$")
    for name in ["name1", "9leadingdigit", "hyphen-ated", "space runs thru it"]:
        assert valid_name.match(utils.sanitize_named_range(name))


@pytest.fixture(
    params=[
        (datetime.date(2020, 12, 18), datetime.date(2020, 12, 18)),
        ("18 Dec 2020", datetime.date(2020, 12, 18)),
        ("18 December 2020", datetime.date(2020, 12, 18)),
    ]
)
def parse_to_date_testcase(request):
    yield request.param


def test_parse_to_date(parse_to_date_testcase):
    (param, expected) = parse_to_date_testcase
    assert expected == utils.parse_to_date(param)


@pytest.fixture(
    params=[
        (1, 5, [1, 2, 4, 5]),
        (1, 1, [1]),
        (2, 1, [1]),
    ]
)
def potential_appliance_counts_testcase(request):
    yield request.param


def test_potential_appliance_counts(potential_appliance_counts_testcase):
    (min_appliances, max_appliances, expected) = potential_appliance_counts_testcase
    assert expected == list(
        utils.potential_appliance_counts(min_appliances, max_appliances)
    )


def test_sum_yoy():
    util1 = utils.YearOverYearUtilization()
    util2 = utils.YearOverYearUtilization()

    num_years = 3

    for yr in range(1, num_years + 1):
        util1.add("absolute_capacity", yr, utils.Size.from_string("1GiB"))
        util2.add("absolute_capacity", yr, utils.Size.from_string("2GiB"))

    sum_util = utils.YearOverYearUtilization()
    sum_util.sum_yoy([util1, util2], num_years, "absolute_capacity")

    for yr in range(1, num_years + 1):
        assert sum_util.get("absolute_capacity", yr) == utils.Size.from_string("3GiB")
