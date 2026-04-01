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

import enum

from . import constants
from . import policy
from . import utils

CAT_SIZER_OPTIONS = "Sizer Options"
PARAM_BANDWIDTH_CLOUD = "Site Bandwidth for CC (Gbps)"
PARAM_LTR_TARGET = "Cloud Target Type"
PARAM_MASTER_SIZING = f"{constants.MANAGEMENT_SERVER_DESIGNATION} Sizing"
PARAM_RESROUCE_TIP = "Display Resource Tip"
PARAM_USHARE_FILE = "Files per Universal Share"
PARAM_CLOUD_STORAGE_WORST_CASE = "Worst case excess space usage for MSDP-C"

CAT_TIMEFRAME = "Time Frame"
PARAM_PLANNING_YEAR = "Sizing Time Frame"
PARAM_FIRST_EXTENSION = "Planning Horizon"

SETTINGS = [
    {
        "category": CAT_SIZER_OPTIONS,
        "params": [
            {
                "name": PARAM_BANDWIDTH_CLOUD,
                "range": "settings_bandwidth_cloud",
                "value": constants.DEFAULT_CC_BW,
                "description": "Default network bandwidth at each site for Cloud Catalyst or MSDP-Cloud replication",
                "policy": policy.DecimalPolicyNoUpperBound(0.01),
                "visible": True,
            },
            {
                "name": PARAM_MASTER_SIZING,
                "range": "settings_primary_sizing",
                "value": "disabled",
                "description": f"If enabled, the {constants.MANAGEMENT_SERVER_DESIGNATION.lower()} appliances or "
                f"containers will be sized. If {constants.MANAGEMENT_SERVER_DESIGNATION.lower()} "
                f"sizing is not required, e.g if an external server will be used as "
                f'{constants.MANAGEMENT_SERVER_DESIGNATION.lower()} , select "disabled" here.',
                "policy": policy.ChoicePolicy(["enabled", "disabled"]),
                "visible": True,
            },
            {
                "name": PARAM_LTR_TARGET,
                "range": "settings_ltr_target",
                "value": "Access",
                "description": 'Type of LTR target to use.  Selecting "Access" uses the performance characteristics '
                "of the Access appliance for cloud replication, and additionally sizes Access "
                "appliances.",
                "policy": policy.ChoicePolicy(
                    ["Access", "Recovery Vault", "Other Target"]
                ),
                "visible": True,
            },
            {
                "name": PARAM_RESROUCE_TIP,
                "range": "settings_resource_tip",
                "value": "enabled",
                "description": 'If enabled, resource safety constraint(s) will be displayed in "Workload Assignments" '
                "sheet.",
                "policy": policy.ChoicePolicy(["enabled", "disabled"]),
                "visible": True,
            },
            {
                "name": PARAM_USHARE_FILE,
                "range": "settings_ushare_file",
                "value": constants.MAXIMUM_FILES_PER_UNIVERSAL_SHARE,
                "description": "Maximum number of files supported in each of the Universal Share",
                "policy": policy.NumberPolicyNoUpperBound(1),
                "visible": False,
            },
            {
                "name": PARAM_CLOUD_STORAGE_WORST_CASE,
                "range": "settings_worst_case_cloud",
                "value": constants.MSDP_CLOUD_WORST_CASE_FACTOR,
                "description": "Excess space used in the worst case when using MSDP-C to send data to the cloud",
                "policy": policy.DecimalPolicyNoUpperBound(0),
                "visible": True,
                "format": "percent_two_decimals",
            },
        ],
    },
    {
        "category": CAT_TIMEFRAME,
        "params": [
            {
                "name": PARAM_PLANNING_YEAR,
                "range": "settings_planning_year",
                "value": constants.PLANNING_YEAR,
                "description": "Year to size for. The sizer will ensure that resource requirements at the end of this "
                "year will be met by the chosen appliances.",
                "policy": policy.NumberPolicy(
                    1,
                    "=settings_first_extension",
                    message="Must be earlier than the configured Planning Horizon",
                ),
                "visible": True,
            },
            {
                "name": PARAM_FIRST_EXTENSION,
                "range": "settings_first_extension",
                "value": constants.FIRST_EXTENSION,
                "description": "Years to project usage to. The sizer will use growth rate to project resource "
                "utilization up to the end of this year.",
                "policy": policy.NumberPolicyNoUpperBound(
                    "=settings_planning_year",
                    message="Must be at least as large as the configured Sizing Time Frame",
                ),
                "visible": True,
            },
        ],
    },
]


class LtrType(enum.Enum):
    """Type of LTR target to size for."""

    ACCESS = enum.auto()
    RECOVERYVAULT = enum.auto()
    OTHER = enum.auto()

    @staticmethod
    def from_string(ltr_type_str):
        """Build an LtrType object from a string representation."""
        ltr_type_map = {
            "access": LtrType.ACCESS,
            "recoveryvault": LtrType.RECOVERYVAULT,
            "othertarget": LtrType.OTHER,
        }
        return ltr_type_map[ltr_type_str.lower()]


class Settings:
    """
    Represent settings that affect sizer operation.

    These are options that don't associate with specific sites or
    workloads, but instead affect the operation of the sizer globally.
    """

    def __init__(self):
        """Construct a Settings object with defaults."""
        self.settings = {}
        for settings_group in SETTINGS:
            cat = settings_group["category"]
            for param in settings_group["params"]:
                self.settings[(cat, param["name"])] = param["value"]

    @staticmethod
    def from_list(data):
        """
        Construct Settings object from a list of tuples.

        Each entry in the list must be a tuple of the form (category, key, value).
        """
        s = Settings()
        for row in data:
            (cat, key, val) = row
            if cat:
                current_cat = cat
                continue
            s.settings[(current_cat, key)] = val
        return s

    @property
    def timeframe(self) -> utils.TimeFrame:
        """Build TimeFrame object from settings."""
        num_years = int(self.settings[(CAT_TIMEFRAME, PARAM_FIRST_EXTENSION)])
        planning_year = int(self.settings[(CAT_TIMEFRAME, PARAM_PLANNING_YEAR)])
        return utils.TimeFrame(num_years=num_years, planning_year=planning_year)

    @timeframe.setter
    def timeframe(self, value: utils.TimeFrame):
        self.settings[(CAT_TIMEFRAME, PARAM_FIRST_EXTENSION)] = value.num_years
        self.settings[(CAT_TIMEFRAME, PARAM_PLANNING_YEAR)] = value.planning_year

    @property
    def master_sizing(self):
        """Return where master server sizing is enabled in settings."""
        val = self.settings[(CAT_SIZER_OPTIONS, PARAM_MASTER_SIZING)]
        return val == "enabled"

    @master_sizing.setter
    def master_sizing(self, value: bool):
        self.settings[(CAT_SIZER_OPTIONS, PARAM_MASTER_SIZING)] = (
            "enabled" if value else "disabled"
        )

    @property
    def ltr_type(self) -> LtrType:
        """Return type of LTR target specified in settings."""
        val = self.settings.get((CAT_SIZER_OPTIONS, PARAM_LTR_TARGET), "Access")
        return LtrType.from_string(val)

    @ltr_type.setter
    def ltr_type(self, value: LtrType):
        self.settings[(CAT_SIZER_OPTIONS, PARAM_LTR_TARGET)] = value.name

    @property
    def resource_tip(self):
        """Return whether resource tip is enabled in settings."""
        val = self.settings[(CAT_SIZER_OPTIONS, PARAM_RESROUCE_TIP)]
        return val == "enabled"

    @resource_tip.setter
    def resource_tip(self, value: bool):
        """set resource tip is enabled in settings if value is true."""
        self.settings[(CAT_SIZER_OPTIONS, PARAM_RESROUCE_TIP)] = (
            "enabled" if value else "disabled"
        )

    @property
    def ushare_files(self):
        """Return the maximum number of files per Universal Share specified in settings."""
        return int(self.settings[(CAT_SIZER_OPTIONS, PARAM_USHARE_FILE)])

    @property
    def worst_case_cloud_factor(self) -> float:
        """Return factor to use for worst-case cloud storage requirements."""
        val = self.settings[(CAT_SIZER_OPTIONS, PARAM_CLOUD_STORAGE_WORST_CASE)]
        return val

    @worst_case_cloud_factor.setter
    def worst_case_cloud_factor(self, value: float):
        self.settings[(CAT_SIZER_OPTIONS, PARAM_CLOUD_STORAGE_WORST_CASE)] = value
