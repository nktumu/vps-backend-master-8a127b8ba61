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
import datetime
import decimal
import enum
import functools
import json
import logging
import os
import os.path
import re
import string

from . import constants

logger = logging.getLogger(__name__)


class WorkloadSummary:
    def __init__(self):
        self.storage_primary: Size = None
        self.storage_dr: Size = None
        self.storage_cloud: Size = None
        self.storage_cloud_worst_case: Size = None
        self.storage_before_deduplication_primary: Size = None
        self.storage_catalog: Size = None
        self.total_network_utilization: Size = None
        self.total_dr_network_utilization: Size = None
        self.total_cloud_network_utilization: Size = None
        self.cloud_storage: Size = None
        self.cloud_transfer: Size = None
        self.backup_volume: Size = None


def get_abs_path(relative_path):
    return os.path.join(os.path.dirname(__file__), relative_path)


def load_json_resource(relative_path):
    full_name = get_abs_path(relative_path)
    with open(full_name, "r") as stream:
        return json.load(stream)


def cpu_count():
    cpus = os.cpu_count()
    if not cpus:
        return 1
    # Leave one CPU uncommited if possible, so that it doesn't slow down
    # the entire computer.
    cpus = max(cpus - 1, 1)
    return cpus


@functools.total_ordering
class Size:
    SIZE_RE = re.compile(
        r"""
        (?P<val>[0-9]+)
        \s*
        (?P<unit>KiB|MiB|GiB|TiB|PiB)
        """,
        re.VERBOSE,
    )

    UNIT_SCALES = {
        "KiB": 1,
        "MiB": 1024,
        "GiB": 1024 * 1024,
        "TiB": 1024 * 1024 * 1024,
        "PiB": 1024 * 1024 * 1024 * 1024,
        "KB": 1,
        "MB": 1024,
        "GB": 1024 * 1024,
        "TB": 1024 * 1024 * 1024,
        "PB": 1024 * 1024 * 1024 * 1024,
    }

    def __init__(self, value, unit):
        self.value = float(value)
        if unit not in Size.UNIT_SCALES:
            raise ValueError("invalid unit", unit)
        self.unit = unit

    @staticmethod
    def from_ratio(num, den, unit):
        units = ["TiB", "GiB", "MiB", "KiB"]
        unit_idx = units.index(unit)

        num_dec = round(decimal.Decimal(num), 2)
        den_dec = decimal.Decimal(den)
        ratio = num_dec / den_dec
        while ratio != int(ratio):
            if unit_idx == len(units) - 1:
                if int(ratio) > 0:
                    # we've run out of units, but have a non-zero
                    # value for size; just truncate at this
                    # point. Fractions of KBs are unlikely to affect
                    # the result.
                    break
                raise Exception("FETB value too small for the given number of clients")
            num_dec *= 1024
            unit_idx += 1
            ratio = num_dec / den_dec
        return Size.assume_unit(int(ratio), units[unit_idx])

    @staticmethod
    def from_dict(dict_item):
        return Size.assume_unit(dict_item["value"], dict_item["unit"])

    @staticmethod
    def from_string(s):
        """Create a size structure out of a string possibly including a unit."""
        match_obj = Size.SIZE_RE.fullmatch(s)
        if not match_obj:
            raise ValueError("invalid size", s)
        return Size(value=float(match_obj.group("val")), unit=match_obj.group("unit"))

    @staticmethod
    def assume_unit(num, unit):
        """Create a size structure for a numeric string, assuming the provided unit."""
        if unit not in Size.UNIT_SCALES.keys():
            raise ValueError("invalid unit", unit)
        return Size(value=float(num), unit=unit)

    @staticmethod
    def sum(sizes):
        return sum(sizes, Size(0, "PiB"))

    def to_float(self, unit):
        mult_value = Size.UNIT_SCALES[self.unit] / Size.UNIT_SCALES[unit]
        return self.value * mult_value

    def __repr__(self):
        return "{}{}".format(self.value, self.unit)

    def __hash__(self):
        return hash(int(self))

    def __eq__(self, other):
        return int(self) == int(other)

    def __lt__(self, other):
        return int(self) < int(other)

    def __int__(self):
        return int(self.value * Size.UNIT_SCALES[self.unit])

    def __add__(self, other):
        if not isinstance(other, Size):
            return NotImplemented
        if self.unit == other.unit:
            return Size(self.value + other.value, self.unit)
        lscale = Size.UNIT_SCALES[self.unit]
        rscale = Size.UNIT_SCALES[other.unit]
        if lscale < rscale:
            result_unit = self.unit
            lvalue = self.value
            rvalue = other.value * rscale // lscale
        else:
            result_unit = other.unit
            lvalue = self.value * lscale // rscale
            rvalue = other.value
        return Size(lvalue + rvalue, result_unit)

    def __mul__(self, other):
        if not isinstance(other, (int, float)):
            return NotImplemented
        return Size(value=self.value * other, unit=self.unit)

    def __truediv__(self, other):
        if not isinstance(other, (int, float, Size)):
            return NotImplemented
        if isinstance(other, (int, float)):
            return Size(value=self.value / other, unit=self.unit)
        if self.unit == other.unit:
            return self.value / other.value
        lscale = Size.UNIT_SCALES[self.unit]
        rscale = Size.UNIT_SCALES[other.unit]
        if lscale < rscale:
            lvalue = self.value
            rvalue = other.value * rscale // lscale
        else:
            lvalue = self.value * lscale // rscale
            rvalue = other.value
        return lvalue / rvalue

    def ignore_unit(self):
        return self.value

    def new_size_scaled(self, factor):
        #
        # Modify the value by the numeric factor.
        # Convert result back to integer with rounding.
        new_value = round(self.value * factor)
        return Size(new_value, self.unit)

    def utilization(self, sizes):
        """Return how much is used out of SELF after fitting everything in SIZES as a proportion of SELF."""
        scaled1 = int(self)
        total_req = sum(int(s) for s in sizes)
        return total_req / scaled1

    def roundup(self, factor):
        """Return new Size object that is rounded up to a multiple of the given factor."""
        factor_kb = int(factor)
        self_kb = int(self)
        rem = self_kb % factor_kb
        if rem == 0:
            return self
        new_val = self_kb + factor_kb - (self_kb % factor_kb)
        return Size(new_val, "KiB")


Size.ZERO = Size.assume_unit(0, "PiB")


class LiteralSize:
    def __init__(self, value, unit):
        self.value = value
        if unit not in Size.UNIT_SCALES:
            raise ValueError("invalid unit", unit)
        self.unit = unit

    @staticmethod
    def from_dict(dict_item):
        return LiteralSize(dict_item["value"], dict_item["unit"])

    def __repr__(self):
        return "{}{}".format(self.value, self.unit)


def sanitize_named_range(raw_name):
    """
    Return a sanitized version of the given name, suitable for use as
    a named range.  The first character must be an underscore or a
    letter, and subsequent characters can be letter, digits,
    underscores or periods.
    """
    first_char_allowed = string.ascii_letters + "_"
    allowed_chars = first_char_allowed + string.digits + "."
    if raw_name[0] not in first_char_allowed:
        raw_name = "_" + raw_name
    translation_table = collections.defaultdict(lambda: None)
    for ch in allowed_chars:
        translation_table[ord(ch)] = ch
    return raw_name.translate(translation_table)


def parse_to_date(raw_value):
    """
    Convert provided value to a datetime.date.  Input may be an
    existing datetime.date, in which case it is returned directly.  If
    provided a string, it will attempt to parse dates of the formats:

    - 18 Dec 2020
    - 18 December 2020

    Raises ValueError if unable to parse.
    """
    if isinstance(raw_value, datetime.date):
        return raw_value

    formats = ["%d %b %Y", "%d %B %Y"]
    for fmt in formats:
        try:
            d = datetime.datetime.strptime(raw_value, fmt)
            return d.date()
        except ValueError:
            pass

    raise ValueError(f"unable to parse {raw_value} as date")


def potential_appliance_counts(min_appliances, max_appliances):
    """
    Produce increasing sequence of numbers up to the given maximum.
    The series starts with the given minimum and increases by doubling
    each time.
    """

    n_appliances = min(min_appliances, max_appliances)
    while n_appliances <= max_appliances:
        yield n_appliances
        if n_appliances == max_appliances:
            return
        n_appliances = min(max_appliances, n_appliances * 2)


class YearOverYearUtilization:
    PERCENTAGE_DIMENSIONS = [
        "capacity",
        "alloc_capacity_pct",
        "cpu",
        "mem",
        "io",
        "nic_pct",
    ]

    DEFAULTS = {
        "absolute_capacity": Size.ZERO,
        "alloc_capacity": Size.ZERO,
        "workload_capacity": Size.ZERO,
        "nic_workload": Size.ZERO,
        "capacity": 0,
        "alloc_capacity_pct": 0,
        "absolute_memory": Size.ZERO,
        "cpu": 0,
        "absolute_io": Size.ZERO,
        "io": 0,
        "nic_pct": 0,
        "nic": Size.ZERO,
        "nic_dr": Size.ZERO,
        "nic_cloud": Size.ZERO,
        "DR Transfer GiB/Week": Size.ZERO,
        "Cloud Transfer GiB/week": Size.ZERO,
        "Cloud Minimum Bandwidth(Mbps)": Size.ZERO,
        "cloud_gib_months": Size.ZERO,
        "cloud_gib_months_worst_case": Size.ZERO,
        "cloud_gib_per_week": Size.ZERO,
        "Full Backup": Size.ZERO,
        "Incremental Backup": Size.ZERO,
        "Size Before Deduplication": Size.ZERO,
        "Size After Deduplication": Size.ZERO,
        "Storage Primary": Size.ZERO,
        "Storage DR": Size.ZERO,
        "Storage Cloud": Size.ZERO,
        "Storage Cloud Worst-Case": Size.ZERO,
        "Storage Catalog": Size.ZERO,
        "Total network utilization": Size.ZERO,
        "Total dr network utilization": Size.ZERO,
        "Total cloud network utilization": Size.ZERO,
        "Backup Volume": Size.ZERO,
        "files": 0,
        "images": 0,
        "jobs/day": 0,
    }

    def __init__(self):
        self.utils = {}

    def add(self, dimension, year, value):
        assert (dimension, year) not in self.utils
        self.utils[(dimension, year)] = value

    def replace(self, dimension, year, value):
        assert (dimension, year) in self.utils
        self.utils[(dimension, year)] = value

    def get(self, dimension, year):
        return self.utils[(dimension, year)]

    def combine_by_max(self, other):
        result = YearOverYearUtilization()

        for dimension, year in self.utils:
            if dimension not in YearOverYearUtilization.PERCENTAGE_DIMENSIONS:
                continue
            value = self.utils[(dimension, year)]
            other_value = other.utils[(dimension, year)]
            result.add(dimension, year, max(value, other_value))

        return result

    def combine_by_sum(self, other, last_year, dimensions):
        result = YearOverYearUtilization()

        for yr in range(1, last_year + 1):
            for dim in dimensions:
                value = self.utils.get((dim, yr), YearOverYearUtilization.DEFAULTS[dim])
                other_value = other.utils[(dim, yr)]
                result.add(dim, yr, value + other_value)

        return result

    def get_max_proportion_for_year(self, year):
        dim_utils = {}
        for dimension, yr in self.utils:
            if yr != year:
                continue
            dim_utils[dimension] = self.utils[(dimension, yr)]
        return max(
            dim_utils[dimension]
            for dimension in YearOverYearUtilization.PERCENTAGE_DIMENSIONS
        )

    @staticmethod
    def aggregate(utilizations, last_year, dimensions):
        result = YearOverYearUtilization()
        for utilization in utilizations:
            result = result.combine_by_sum(utilization, last_year, dimensions)
        return result

    def sum_yoy(self, utilizations, last_year, dimension):
        for yr in range(1, last_year + 1):
            agg = YearOverYearUtilization.DEFAULTS[dimension]
            for utilization in utilizations:
                agg += utilization.utils.get(
                    (dimension, yr), YearOverYearUtilization.DEFAULTS[dimension]
                )
            self.add(dimension, yr, agg)


TimeFrame = collections.namedtuple("TimeFrame", ["num_years", "planning_year"])
DEFAULT_TIMEFRAME = TimeFrame(
    num_years=constants.FIRST_EXTENSION, planning_year=constants.PLANNING_YEAR
)
DEFAULT_WORST_CASE_CLOUD_FACTOR = 0.5


class WorkloadMode(enum.Enum):
    media_primary = enum.auto()
    media_dr = enum.auto()
    media_cloud = enum.auto()
    primary = enum.auto()

    def __str__(self):
        visible_names = {
            "media_primary": "Media Server (Primary)",
            "media_dr": "Media Server (DR)",
            "primary": constants.MANAGEMENT_SERVER_DESIGNATION,
            "media_cloud": "MSDP-Cloud",
        }
        return visible_names[self.name]


class WindowSize:
    def __init__(self, full_backup_hours, incremental_backup_hours, replication_hours):
        self.full_backup_hours = full_backup_hours
        self.incremental_backup_hours = incremental_backup_hours
        self.replication_hours = replication_hours

    def __eq__(self, other):
        return (
            self.full_backup_hours == other.full_backup_hours
            and self.incremental_backup_hours == other.incremental_backup_hours
            and self.replication_hours == other.replication_hours
        )

    @property
    def full_backup(self):
        return self.full_backup_hours * constants.SECONDS_PER_HOUR

    @property
    def incremental_backup(self):
        return self.incremental_backup_hours * constants.SECONDS_PER_HOUR

    @property
    def replication(self):
        return self.replication_hours * constants.SECONDS_PER_HOUR
