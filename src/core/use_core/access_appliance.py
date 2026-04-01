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
import functools

from use_core import constants
from use_core import utils

SKU_JSON_PATH = "conf/gurus/access-configs.json"


AccessSoftwareSafety = collections.namedtuple(
    "AccessSoftwareSafety",
    [
        "concurrent_streams",
    ],
)


class AccessAppliance:
    """Represents an Access appliance."""

    MAX_STREAMS = 80
    APPLIANCE_MEMORY = utils.Size.from_string(constants.ACCESS_APPLIANCE_MEMORY)

    def __init__(self):
        self.appliance = "access-3340"
        self.model = "3340"
        self.site_version = constants.DEFAULT_SOFTWARE_VERSION
        self.memory = AccessAppliance.APPLIANCE_MEMORY
        self.number_of_total_drives = 0
        self.max_capacity = 1.0
        self.max_cpu = 1.0
        self.software_safety = AccessSoftwareSafety(
            concurrent_streams=AccessAppliance.MAX_STREAMS
        )

    def __repr__(self):
        return f"{self.appliance} ({self.max_capacity=})"

    def set_safety_limits(self, limits):
        """Apply safety limits from the provided data."""
        self.max_capacity = limits["Access 3340"]["Capacity"]
        self.max_cpu = limits["Access 3340"]["CPU"]

    @staticmethod
    def from_json(spec):
        """Generate an AccessAppliance from JSON SKU definition."""
        app = AccessAppliance()
        app.name = spec["name"]
        app.capacity = utils.Size.from_string(spec["capacity"])
        app.primary_capacity = utils.Size.from_string(spec["primary_capacity"])
        app.shelf_capacity = utils.Size.from_string(spec["shelf_capacity"])
        app.num_shelves = spec["num_shelves"]
        return app

    @staticmethod
    def stub():
        """
        Return a stub object.

        This object is sufficient to indicate that it is an Access
        appliance, but does not otherwise have any useful attributes.
        """
        return AccessAppliance()

    @staticmethod
    def for_size(target_size: utils.Size, max_capacity: float):
        """
        Find Access appliance for storing given amount of data.

        It will find the smallest appliance that has at least the
        required storage.  The available storage is restricted to a
        max_capacity fraction of the total storage.
        """
        all_skus = list(
            sorted(AccessAppliance.get_all_skus(), key=lambda appl: appl.capacity)
        )
        candidates = [
            appl for appl in all_skus if appl.capacity * max_capacity >= target_size
        ]
        if not candidates:
            raise ValueError("no appliance with suitable capacity")
        return candidates[0]

    @staticmethod
    @functools.lru_cache(maxsize=None)
    def get_all_skus():
        appliance_specs = utils.load_json_resource(SKU_JSON_PATH)
        return [AccessAppliance.from_json(spec) for spec in appliance_specs]

    @staticmethod
    @functools.lru_cache(maxsize=None)
    def max_possible_capacity() -> utils.Size:
        """Get the maximum possible capacity for an AccessAppliance."""
        return max(appl.capacity for appl in AccessAppliance.get_all_skus())
