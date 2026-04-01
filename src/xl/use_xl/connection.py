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
import enum
import itertools
import logging
import typing

import xlwings as xw

from use_core import appliance as appl
from use_core import (
    constants,
    package_version,
    packing,
    settings,
    timers,
    utils,
    workload,
)
from use_core.appliance import NetworkType
from use_core.workload import (
    get_site_hints_from_workloads,
    calculate_capacity_all_workloads,
)
from use_xl import charting, flexscale
from use_xl.summary import (
    write_appliance_summary,
    write_appliance_summary_flex,
    write_raw_appliance_summary,
    write_raw_appliance_summary_flex,
)
from use_xl.xlutils import fit_sheet, make_all_rows_same_length

APPLIANCE_SUMMARY_SHEET = "Appliance Summary"
APPLIANCE_USAGE_CHART_DATA_SHEET = "Appliance Chart Data"
BACKUP_POLICIES_SHEET = "Storage Lifecycle Policies"
ERRORS_AND_NOTES_SHEET = "Errors And Notes"
FLEX_SCALE_DATA_SHEET = "_flex_scale_data"
FLEX_SCALE_RESULTS_SHEET = "Flex Scale Sizing Results"
FLEX_SCALE_TOTALS_SHEET = "Flex Scale Totals"
ITEMIZATION_SHEET = "Itemization"
LOGS_SHEET = "Logs"
MASTER_SUMMARY_SHEET = f"{constants.MANAGEMENT_SERVER_DESIGNATION} Summary"
OPERATION_WINDOWS_SHEET = "Windows"
RAW_APPLIANCE_SUMMARY_SHEET = "Raw Appliance Summary"
RAW_FLEX_SHEET = "Workload Assign Details Flex"
RAW_SHEET = "Workload Assignment Details"
SAFETY_SHEET = "Safety Considerations"
SETTINGS_SHEET = "Settings"
SITE_ASSIGNMENTS_SHEET = "Sites"
SITE_SUMMARY_SHEET = "Results"
SITE_SUMMARY_SHEET_PREVIOUS = "Appliances Needed"
SKU_SHEET = "Appliance Definitions"
STORAGE_LIFECYCLE_POLICIES_SHEET = "Storage Lifecycle Policies"
VARIABLES_SHEET = "_variables"
VARIABLES_SHEET_2 = "_variables2"
WORKLOADS_SHEET = "Workloads"
WORKLOAD_ASSIGNMENT_FLEX_SHEET = "Workload Assignments Flex"
WORKLOAD_ASSIGNMENT_SHEET = "Workload Assignments"
WORKLOAD_ATTRIBUTES_SHEET = "Default Workload Attributes"
WORKLOAD_SUMMARY_SHEET = "Workload Summary"
XLWINGS_CONFIG_SHEET = "xlwings.conf"

FAMILY_NBA = constants.ApplianceFamily.NBA
FAMILY_FLEX = constants.ApplianceFamily.Flex
FAMILY_FLEXSCALE = constants.ApplianceFamily.FlexScale

NBDEPLOYUTIL_EXPECTED_DEFAULT_SLP = "default"
NBDEPLOYUTIL_EXPECTED_WORKLOADS_HEADERS = [
    "Workload Name",
    "Workload Type",
    "Number of Clients",
    "FETB (TiB)",
]
NBDEPLOYUTIL_ITEMIZATION_SHEET = "Itemization"

OBJECT = "object"
SLP = "slp"
SLP_NEW_ROW_NAME = "new_slp_row"
STORAGE_LIFECYCLE_POLICIES = "storage lifecycle policies"
SUMMARY_ERROR_CELL = "I2"
WINDOW_SIZE = "bandaid"
WORKLOAD = "workload"
WORKLOAD_NEW_ROW_NAME = "new_workload_row"

APPLIANCE_CONFIG_CAPACITY_ERROR_TEXT = """
The \"Max Capacity Utilization (%)\"
multiplied by the size of the
selected appliance configuration
\"{config_name}\" is smaller
than the value of the
\"LUN Size for Flex appliance (TiB)\"
at site \"{site_name}\"
"""

WORKLOAD_ERRORS_TEXT = """
Some errors were encountered during sizing.  Refer to the \"Errors And
Notes\" sheet for details.  Summary of errors:
"""

WORKLOAD_MASTER_SKIPPED_TEXT = """
- Some workloads were skipped from master server sizing.
"""

WORKLOAD_MEDIA_SKIPPED_TEXT = """
- Some workloads were skipped from media server sizing.
"""

WORKLOAD_DOMAIN_NOTE_TEXT = """
- Some domains were split because they were too large for a single master server.
"""

WORKLOAD_DOMAIN_CHANGE_TEXT = """
Domain for workload {workload_name} was changed to {new_domain_name}
"""

UNKNOWN_SLP_ERROR_TEXT = f"Workload refers to SLP name {{slp_name}} which \
is not defined on the {BACKUP_POLICIES_SHEET} sheet."

EMPTY_SHEET_ERROR_TEXT = "{sheet_name} sheet has no entry."

MISSING_SHEET_ERROR_TEXT = "Workbook does not contain sheet with name {sheet_name}."

MESSAGE_ERROR_TEXT = (
    f"{package_version.package_product_name}-{package_version.package_version}: Error"
)
MESSAGE_INFO_TEXT = f"{package_version.package_product_name}-{package_version.package_version}: Information"

logger = logging.getLogger(__name__)


class WorkloadErrorType(enum.Enum):
    media_skip = enum.auto()
    master_skip = enum.auto()
    domains_split = enum.auto()

    def __str__(self):
        messages = {
            "media_skip": WORKLOAD_MEDIA_SKIPPED_TEXT,
            "master_skip": WORKLOAD_MASTER_SKIPPED_TEXT,
            "domains_split": WORKLOAD_DOMAIN_NOTE_TEXT,
        }
        return messages[self.name]


class ApplianceConfigurationCapacityError(Exception):
    def __init__(self, config_name, site_name):
        self.config_name = config_name
        self.site_name = site_name

    def __str__(self):
        return APPLIANCE_CONFIG_CAPACITY_ERROR_TEXT.format(
            config_name=self.config_name, site_name=self.site_name
        )


class CellValueError(Exception):
    def __init__(self, column_name, bad_value):
        self.column_name = column_name
        self.bad_value = bad_value

    def __str__(self):
        if self.bad_value is None:
            return f"Column {self.column_name} must not be empty"
        return f"{self.bad_value} is not a valid value for {self.column_name}"


class ConnectionError(Exception):
    pass


class BadInputError(ConnectionError):
    pass


class MissingWorkloadsError(ConnectionError):
    pass


class MissingRequiredKey(Exception):
    def __init__(self, msgs):
        self.msgs = msgs

    def __str__(self):
        return f"{self.msgs}"


class MissingSitesError(ConnectionError):
    pass


class UnknownSlpError(ConnectionError):
    def __init__(self, slp_name):
        self.slp_name = slp_name

    def __str__(self):
        return UNKNOWN_SLP_ERROR_TEXT.format(slp_name=self.slp_name)


class EmptySheetError(ConnectionError):
    def __init__(self, sheet_name):
        self.sheet_name = sheet_name

    def __str__(self):
        return EMPTY_SHEET_ERROR_TEXT.format(sheet_name=self.sheet_name)


class MissingSheetError(ConnectionError):
    def __init__(self, sheet_name):
        self.sheet_name = sheet_name

    def __str__(self):
        return MISSING_SHEET_ERROR_TEXT.format(sheet_name=self.sheet_name)


class BooleanTranslator:
    def __init__(self, column_name):
        self.column_name = column_name

    def value(self, excel_row):
        raw_value = excel_row[self.column_name]
        if isinstance(raw_value, bool):
            return raw_value
        if raw_value is None:
            return False
        raw_value = raw_value.lower()
        value_map = {"yes": True, "no": False, "n/a": False}
        if raw_value in value_map:
            return value_map[raw_value]
        raise CellValueError(self.column_name, raw_value)

    def raw_value(self, excel_row):
        return excel_row[self.column_name]


class EnumTranslator:
    def __init__(self, column_name, allowed_values, default):
        self.column_name = column_name
        self.allowed_values = allowed_values
        self.default = default
        if isinstance(allowed_values, dict):
            self.allowed_values = allowed_values
        else:
            self.allowed_values = {}
            for val in allowed_values:
                self.allowed_values[val] = val

    def value(self, excel_row):
        raw_value = excel_row[self.column_name]
        if not raw_value and self.default:
            raw_value = self.default
        raw_value = raw_value.lower()
        logger.info("column: %s raw value: %s", self.column_name, raw_value)
        if raw_value not in self.allowed_values:
            raise CellValueError(self.column_name, raw_value)
        return self.allowed_values[raw_value]

    def raw_value(self, excel_row):
        return excel_row[self.column_name]


class FloatTranslator:
    def __init__(self, column_name):
        self.column_name = column_name

    def value(self, excel_row):
        raw_value = excel_row[self.column_name]
        try:
            return float(raw_value)
        except (ValueError, TypeError):
            raise CellValueError(self.column_name, raw_value)

    def raw_value(self, excel_row):
        return excel_row[self.column_name]


class IntTranslator:
    def __init__(self, column_name, default=None):
        self.column_name = column_name
        self.default = default

    def value(self, excel_row):
        raw_value = excel_row[self.column_name]
        if raw_value is None and self.default is not None:
            raw_value = self.default

        try:
            return int(raw_value)
        except (ValueError, TypeError):
            raise CellValueError(self.column_name, raw_value)

    def raw_value(self, excel_row):
        return excel_row[self.column_name]


class NullableIntTranslator:
    def __init__(self, column_name):
        self.column_name = column_name

    def value(self, excel_row):
        raw_value = excel_row[self.column_name]
        if raw_value is not None and raw_value != "None":
            return int(raw_value)
        else:
            return None

    def raw_value(self, excel_row):
        return excel_row[self.column_name]


fail_conversion = object()


class OneToOneTranslator:
    def __init__(self, column_name, default=fail_conversion):
        self.column_name = column_name
        self.default = default

    def handle_missing(self, raw_value):
        if self.default is fail_conversion:
            raise CellValueError(self.column_name, raw_value)
        return self.default

    def value(self, excel_row):
        raw_value = self.raw_value(excel_row)
        if not raw_value:
            return self.handle_missing(raw_value)
        if not isinstance(raw_value, str):
            raise CellValueError(self.column_name, raw_value)
        raw_value = raw_value.strip()
        if not raw_value:
            return self.handle_missing(raw_value)
        return raw_value

    def raw_value(self, excel_row):
        return excel_row[self.column_name]


class SizeTranslator:
    def __init__(self, column1, column2):
        self.column1 = column1
        self.column2 = column2
        self.column_name = column1

    def value(self, excel_row):
        col1_value = self.raw_value(excel_row)
        try:
            col1_value = float(col1_value)
        except (TypeError, ValueError):
            raise CellValueError(self.column1, col1_value)

        col2_value = excel_row[self.column2]
        try:
            col2_value = int(col2_value)
        except (TypeError, ValueError):
            raise CellValueError(self.column2, col2_value)

        if col2_value == 0:
            raise CellValueError(self.column2, col2_value)

        return utils.Size.from_ratio(col1_value, col2_value, "TiB")

    def raw_value(self, excel_row):
        return excel_row[self.column_name]


class UnitTranslator:
    def __init__(self, column_name, unit):
        self.column_name = column_name
        self.unit = unit

    def value(self, excel_row):
        raw_value = excel_row[self.column_name]
        try:
            num_value = float(raw_value)
            return utils.Size.from_ratio(num_value, 1, self.unit)
        except ValueError:
            raise CellValueError(self.column_name, raw_value)

    def raw_value(self, excel_row):
        return excel_row[self.column_name]


NETWORK_TYPE_MAP = {
    "auto": NetworkType.auto,
    "1gbe": NetworkType.one_gbe,
    "10gbe copper": NetworkType.ten_gbe_copper,
    "10gbe sfp": NetworkType.ten_gbe_sfp,
    "25gbe sfp": NetworkType.twentyfive_gbe_sfp,
}

POLICY_TYPE_MAP = {
    "FlashBackup-Windows": "File System",
    "Lotus-Notes": "Notes",
    "MS-Exchange-Server": "Exchange",
    "MS-Sharepoint": "SharePoint",
    "MS-SQL-Server": "SQL",
    "MS-Windows": "File System",
    "MS-Windows-NT": "File System",
    "Standard": "File System",
}

REQUIRED_ITEMIZATION_KEYS = set(["client_name", "policy_name", "policy_type", "total"])

SHEET_ITEMIZATION_MAP = {
    "master_server": constants.MANAGEMENT_SERVER_DESIGNATION,
    "client_name": "Client Name",
    "policy_name": "Policy Name",
    "policy_type": "Policy Type",
    "backup_image": "Backup Image",
    "backup_date": "Backup Date (UTC)",
    "accuracy": "Accuracy",
    "accuracy_comment": "Accuracy Comment",
    "full": "FULL (KB)",
    "ubak": "UBAK (KB)",
    "db": "DB (KB)",
    "overlap_size": "Overlap size (KB)",
    "total": "Total (KB)",
    "total_readable": "Total (Readable)",
    "charged_size": "Charged Size (KB)",
    "enter_a_reason_here_when_modifying_the_charged_size": "Enter a Reason here when modifying the Charged Size",
    "nb_platform_base": "NB Platform Base (KB)",
    "nb_deduplication": "NB Deduplication (KB)",
    "nb_realtime": "NB RealTime (KB)",
    "nb_replicationdirector": "NB ReplicationDirector (KB)",
    "tape": "Tape (KB)",
    "basicdisk": "BasicDisk (KB)",
    "advanceddisk": "AdvancedDisk (KB)",
    "puredisk": "PureDisk (KB)",
    "accelerator": "Accelerator (KB)",
    "openstorage": "OpenStorage (KB)",
    "cloudcatalyst": "CloudCatalyst (KB)",
}

SHEET_WINDOWS_MAP = {
    "Incrementals": "incremental_backup",
    "Full": "full_backup",
    "Replications": "replication",
}

SHEET_WORKLOADS_MAP = {
    "workload_name": OneToOneTranslator("Workload Name"),
    "workload_type": OneToOneTranslator("Workload Type"),
    "number_of_clients": IntTranslator("Number of Clients"),
    "workload_size": SizeTranslator("FETB (TiB)", "Number of Clients"),
    "storage_lifecycle_policy": OneToOneTranslator("Storage Lifecycle Policy"),
    "workload_isolation": BooleanTranslator("Workload Isolation"),
    # Uncomment below when Universal Share is ready
    # "universal_share": BooleanTranslator("Universal Share?"),
    "client_dedup": BooleanTranslator("Client-Side Dedup?"),
    "annual_growth_rate": FloatTranslator("Annual Growth Rate (%)"),
    "daily_change_rate": FloatTranslator("Daily Change Rate (%)"),
    "initial_dedup_rate": FloatTranslator("Initial Dedup Rate (%)"),
    "dedup_rate": FloatTranslator("Dedup Rate (%)"),
    "files": IntTranslator("Number of Files per FETB"),
    "channels": IntTranslator("Number of Channels"),
    "files_per_channel": IntTranslator("Files per Channel"),
    "dedupe_rate_adl_full": FloatTranslator("Dedup Rate Adl Full (%)"),
    "log_backup_capable": BooleanTranslator("Log Backup Capable?"),
    "cbt": BooleanTranslator("Changed Block Tracking?"),
    "sfr": BooleanTranslator("Enable Single File Recovery?"),
    "accelerator": BooleanTranslator("Accelerator?"),
}

SHEET_WORKLOADS_MAP_31 = {
    "workload_name": OneToOneTranslator("Workload Name"),
    "workload_type": OneToOneTranslator("Workload Type"),
    "number_of_clients": IntTranslator("Number of Clients"),
    "workload_size": SizeTranslator("FETB (TiB)", "Number of Clients"),
    "storage_lifecycle_policy": OneToOneTranslator("Storage Lifecycle Policy"),
    "client_dedup": BooleanTranslator("Client-Side Dedup?"),
    "annual_growth_rate": FloatTranslator("Annual Growth Rate (%)"),
    "daily_change_rate": FloatTranslator("Daily Change Rate (%)"),
    "initial_dedup_rate": FloatTranslator("Initial Dedup Rate (%)"),
    "dedup_rate": FloatTranslator("Dedup Rate (%)"),
    "files": IntTranslator("Number of Files per FETB"),
    "channels": IntTranslator("Number of Channels"),
    "files_per_channel": IntTranslator("Files per Channel"),
    "dedupe_rate_adl_full": FloatTranslator("Dedup Rate Adl Full (%)"),
    "log_backup_capable": BooleanTranslator("Log Backup Capable?"),
    "cbt": BooleanTranslator("Changed Block Tracking?"),
    "sfr": BooleanTranslator("Enable Single File Recovery?"),
    "accelerator": BooleanTranslator("Accelerator?"),
}

SHEET_WORKLOADS_MAP_21 = {
    "workload_name": OneToOneTranslator("Workload Name"),
    "workload_type": OneToOneTranslator("Workload Type"),
    "number_of_clients": IntTranslator("Number of Clients"),
    "workload_size": SizeTranslator("FETB (TiB)", "Number of Clients"),
    "region": OneToOneTranslator("Site"),
    "dr_dest": OneToOneTranslator("DR-dest", default=None),
    "backup_location_policy": EnumTranslator(
        "Backup Image Location",
        [loc.lower() for loc in constants.BACKUP_LOCATIONS],
        default="local only",
    ),
    "annual_growth_rate": FloatTranslator("Annual Growth Rate (%)"),
    "daily_change_rate": FloatTranslator("Daily Change Rate (%)"),
    "incremental_retention_days": IntTranslator(
        "Incremental Retention (days) - Local", default=0
    ),
    "incremental_retention_dr": IntTranslator(
        "Incremental Retention (days) - DR", default=0
    ),
    "incremental_retention_cloud": IntTranslator(
        "Incremental Retention (days) - Cloud", default=0
    ),
    "weekly_full_retention": IntTranslator(
        "Weekly Full Retention (weeks) - Local", default=0
    ),
    "weekly_full_retention_dr": IntTranslator(
        "Weekly Full Retention (weeks) - DR", default=0
    ),
    "weekly_full_retention_cloud": IntTranslator(
        "Weekly Full Retention (weeks) - Cloud", default=0
    ),
    "monthly_retention": IntTranslator(
        "Monthly Full Retention (months) - Local", default=0
    ),
    "monthly_full_retention_dr": IntTranslator(
        "Monthly Full Retention (months) - DR", default=0
    ),
    "monthly_full_retention_cloud": IntTranslator(
        "Monthly Full Retention (months) - Cloud", default=0
    ),
    "annually_retention": IntTranslator(
        "Annual Full Retention (years) - Local", default=0
    ),
    "annually_full_retention_dr": IntTranslator(
        "Annual Full Retention (years) - DR", default=0
    ),
    "annually_full_retention_cloud": IntTranslator(
        "Annual Full Retention (years) - Cloud", default=0
    ),
    "initial_dedup_rate": FloatTranslator("Initial Dedup Rate (%)"),
    "dedup_rate": FloatTranslator("Dedup Rate (%)"),
    "full_backup_per_week": IntTranslator("Number of Full Backups per Week", default=0),
    "incremental_per_week": IntTranslator(
        "Number of Incremental Backups per Week", default=0
    ),
    "incremental_backup_level": EnumTranslator(
        "Incremental Backup Level", ["differential", "cumulative", "none"], "none"
    ),
    "log_backup_frequency_minutes": NullableIntTranslator(
        "Log Backup Frequency (minutes between)"
    ),
    "appliance_front_end_network": EnumTranslator(
        "Appliance Front-End Network", NETWORK_TYPE_MAP, "auto"
    ),
    "min_size_dup_jobs": UnitTranslator(
        "Minimum Size Per Duplication Job (GiB)", "GiB"
    ),
    "max_size_dup_jobs": UnitTranslator(
        "Maximum Size Per Duplication Job (GiB)", "GiB"
    ),
    "force_small_dup_jobs": IntTranslator("Force Interval for Small Jobs (min)"),
    "appliance_dr_network": EnumTranslator(
        "Appliance DR Network", NETWORK_TYPE_MAP, "auto"
    ),
    "files": IntTranslator("Number of Files"),
    "channels": IntTranslator("Number of Channels"),
    "files_per_channel": IntTranslator("Files per Channel"),
    "dedupe_rate_adl_full": FloatTranslator("Dedup Rate Adl Full (%)"),
    "log_backup_capable": BooleanTranslator("Log Backup Capable?"),
}

SHEET_STORAGE_LIFECYCLE_POLICIES_MAP = {
    "storage_lifecycle_policy": OneToOneTranslator("Storage Lifecycle Policy"),
    "domain": OneToOneTranslator("Domain", default=constants.DEFAULT_DOMAIN_NAME),
    "region": OneToOneTranslator("Site"),
    "dr_dest": OneToOneTranslator("DR-dest", default=None),
    "backup_location_policy": EnumTranslator(
        "Backup Image Location",
        [loc.lower() for loc in constants.BACKUP_LOCATIONS],
        default="local only",
    ),
    "incremental_retention_days": IntTranslator(
        "Incremental Retention (days) - Local", default=0
    ),
    "incremental_retention_dr": IntTranslator(
        "Incremental Retention (days) - DR", default=0
    ),
    "incremental_retention_cloud": IntTranslator(
        "Incremental Retention (days) - Cloud", default=0
    ),
    "weekly_full_retention": IntTranslator(
        "Weekly Full Retention (weeks) - Local", default=0
    ),
    "weekly_full_retention_dr": IntTranslator(
        "Weekly Full Retention (weeks) - DR", default=0
    ),
    "weekly_full_retention_cloud": IntTranslator(
        "Weekly Full Retention (weeks) - Cloud", default=0
    ),
    "monthly_retention": IntTranslator(
        "Monthly Full Retention (months) - Local", default=0
    ),
    "monthly_full_retention_dr": IntTranslator(
        "Monthly Full Retention (months) - DR", default=0
    ),
    "monthly_full_retention_cloud": IntTranslator(
        "Monthly Full Retention (months) - Cloud", default=0
    ),
    "annually_retention": IntTranslator(
        "Annual Full Retention (years) - Local", default=0
    ),
    "annually_full_retention_dr": IntTranslator(
        "Annual Full Retention (years) - DR", default=0
    ),
    "annually_full_retention_cloud": IntTranslator(
        "Annual Full Retention (years) - Cloud", default=0
    ),
    "full_backup_per_week": IntTranslator("Number of Full Backups per Week", default=0),
    "incremental_per_week": IntTranslator(
        "Number of Incremental Backups per Week", default=0
    ),
    "incremental_backup_level": EnumTranslator(
        "Incremental Backup Level", ["differential", "cumulative", "none"], "none"
    ),
    "log_backup_frequency_minutes": NullableIntTranslator(
        "Log Backup Frequency (minutes between)"
    ),
    "log_backup_incremental_level": EnumTranslator(
        "Log Backup Incremental Level", ["differential", "cumulative", "none"], "none"
    ),
    "appliance_front_end_network": EnumTranslator(
        "Appliance Front-End Network", NETWORK_TYPE_MAP, "auto"
    ),
    "min_size_dup_jobs": UnitTranslator(
        "Minimum Size Per Duplication Job (GiB)", "GiB"
    ),
    "max_size_dup_jobs": UnitTranslator(
        "Maximum Size Per Duplication Job (GiB)", "GiB"
    ),
    "force_small_dup_jobs": IntTranslator("Force Interval for Small Jobs (min)"),
    "appliance_dr_network": EnumTranslator(
        "Appliance DR Network", NETWORK_TYPE_MAP, "auto"
    ),
    "appliance_ltr_network": EnumTranslator(
        "Appliance LTR Network", NETWORK_TYPE_MAP, "auto"
    ),
}

SHEET_STORAGE_LIFECYCLE_POLICIES_MAP_21 = {
    "storage_lifecycle_policy": OneToOneTranslator("Storage Lifecycle Policy"),
    "region": OneToOneTranslator("Site"),
    "dr_dest": OneToOneTranslator("DR-dest", default=None),
    "backup_location_policy": EnumTranslator(
        "Backup Image Location",
        [loc.lower() for loc in constants.BACKUP_LOCATIONS],
        default="local only",
    ),
    "incremental_retention_days": IntTranslator(
        "Incremental Retention (days) - Local", default=0
    ),
    "incremental_retention_dr": IntTranslator(
        "Incremental Retention (days) - DR", default=0
    ),
    "incremental_retention_cloud": IntTranslator(
        "Incremental Retention (days) - Cloud", default=0
    ),
    "weekly_full_retention": IntTranslator(
        "Weekly Full Retention (weeks) - Local", default=0
    ),
    "weekly_full_retention_dr": IntTranslator(
        "Weekly Full Retention (weeks) - DR", default=0
    ),
    "weekly_full_retention_cloud": IntTranslator(
        "Weekly Full Retention (weeks) - Cloud", default=0
    ),
    "monthly_retention": IntTranslator(
        "Monthly Full Retention (months) - Local", default=0
    ),
    "monthly_full_retention_dr": IntTranslator(
        "Monthly Full Retention (months) - DR", default=0
    ),
    "monthly_full_retention_cloud": IntTranslator(
        "Monthly Full Retention (months) - Cloud", default=0
    ),
    "annually_retention": IntTranslator(
        "Annual Full Retention (years) - Local", default=0
    ),
    "annually_full_retention_dr": IntTranslator(
        "Annual Full Retention (years) - DR", default=0
    ),
    "annually_full_retention_cloud": IntTranslator(
        "Annual Full Retention (years) - Cloud", default=0
    ),
    "full_backup_per_week": IntTranslator("Number of Full Backups per Week", default=0),
    "incremental_per_week": IntTranslator(
        "Number of Incremental Backups per Week", default=0
    ),
    "incremental_backup_level": EnumTranslator(
        "Incremental Backup Level", ["differential", "cumulative", "none"], "none"
    ),
    "log_backup_frequency_minutes": NullableIntTranslator(
        "Log Backup Frequency (minutes between)"
    ),
    "log_backup_incremental_level": EnumTranslator(
        "Log Backup Incremental Level", ["differential", "cumulative", "none"], "none"
    ),
    "appliance_front_end_network": EnumTranslator(
        "Appliance Front-End Network", NETWORK_TYPE_MAP, "auto"
    ),
    "min_size_dup_jobs": UnitTranslator(
        "Minimum Size Per Duplication Job (GiB)", "GiB"
    ),
    "max_size_dup_jobs": UnitTranslator(
        "Maximum Size Per Duplication Job (GiB)", "GiB"
    ),
    "force_small_dup_jobs": IntTranslator("Force Interval for Small Jobs (min)"),
    "appliance_dr_network": EnumTranslator(
        "Appliance DR Network", NETWORK_TYPE_MAP, "auto"
    ),
    "appliance_ltr_network": EnumTranslator(
        "Appliance LTR Network", NETWORK_TYPE_MAP, "auto"
    ),
}


def get_sheet(book, sheet_name, clear_contents=True):
    sheet = book.sheets[sheet_name]
    if clear_contents:
        sheet.clear_contents()
    return sheet


def sheet_exists(book, sheet_name):
    all_sheet_names = [sh.name for sh in book.sheets]
    return sheet_name in all_sheet_names


def write_appliance(sheet, appliance_list):
    sheet.clear_contents()
    output_col = [
        "Name",
        "Model",
        "Shelves",
        "Calculated Capacity",
        "Memory",
        "IO Config",
        "1GbE",
        "10GbE Copper",
        "10GbE SFP",
        "25GbE SFP",
        "8GbFC",
        "16GbFC",
    ]
    output_array = [output_col]
    for appliance_config in appliance_list:
        output_array.append(
            [
                appliance_config.config_name,
                appliance_config.model,
                appliance_config.shelves,
                appliance_config.disk_capacity.ignore_unit(),
                appliance_config.memory.ignore_unit(),
                appliance_config.io_config,
                appliance_config.one_gbe_count,
                appliance_config.ten_gbe_copper_count,
                appliance_config.ten_gbe_sfp_count,
                appliance_config.twentyfive_gbe_sfp_count,
                appliance_config.eight_gbfc_count,
                appliance_config.sixteen_gbfc_count,
            ]
        )

    sheet.range("A1").value = output_array
    fit_sheet(sheet)


@timers.record_time("writing write_workload_assignment")
def write_workload_assignment(sheet, mresult, resource_tip=True):
    sheet.clear()
    row_info = {}
    row_count = 0
    output_col = [
        "Domain",
        "Site",
        f"Number of {constants.MANAGEMENT_SERVER_DESIGNATION}s",
        f"{constants.MANAGEMENT_SERVER_DESIGNATION} Configuration",
        "Number of Media Servers",
        "Media Server Configuration",
        "Workload Name",
        "Workload Mode",
        "Number of Instances",
    ]
    output_array = [output_col]
    row_count = len(output_array)

    for domain in sorted(mresult.domains):
        mservers = mresult.master_servers(domain)
        row = [domain, mresult.largest_site(domain), len(mservers)]
        output_array.append(row)
        row_count += 1
        for mserver in mservers:
            row = ["", "", "", mserver.appliance.config_name]
            output_array.append(row)
            row_count += 1

        output_domain_media, row_data = get_domain_media(mresult, domain)
        output_array.extend(output_domain_media)
        row_offset = 0
        for (row, r_domain, r_site, r_workload), value in row_data.items():
            row_offset = row
            row_info[(row_count + row_offset, r_domain, r_site, r_workload)] = value
        row_count += row_offset

    make_all_rows_same_length(output_array)
    sheet.range("A1").value = output_array

    if resource_tip:
        for (row, row_domain, row_site, row_workload), value in row_info.items():
            [(limit_value, limit_resources)] = mresult.bottleneck_clients(
                row_domain, row_site, row_workload
            )
            limit_resource = ", ".join(limit_resources)
            sheet.range("I" + str(row)).add_hyperlink(
                "",
                text_to_display=f"{value}",
                screen_tip=f"Fits a maximum of {limit_value} client(s)\nbefore exceeding the safety\nconstraint(s):\n{limit_resource}.",
            )

    fit_sheet(sheet)


@timers.record_time("writing write_workload_assignment_flex")
def write_workload_assignment_flex(sheet, mresult):
    sheet.clear()
    row_info = {}
    output_col = [
        "Site",
        "Appliance",
        "Number of Containers",
        "Domain",
        "Container",
        "Workload",
        "Mode",
        "Number of Clients",
    ]
    output_array = [output_col]

    last_site = last_appliance_name = last_domain = None
    for (
        domain,
        site_name,
        appliance_name,
        app,
        container_name,
        container_type,
        container_obj,
    ) in mresult.all_containers:
        if last_site is None or last_site != site_name:
            row = [site_name]
            output_array.append(row)
            last_site = site_name
            last_appliance_name = None

        if last_appliance_name is None or last_appliance_name != appliance_name:
            row = [None, appliance_name, len(app.containers)]
            output_array.append(row)
            row_info[(len(output_array), app.appliance.config_name)] = appliance_name
            last_appliance_name = appliance_name
            last_domain = None

        if last_domain is None or last_domain != domain:
            row = [None, None, None, domain]
            output_array.append(row)
            last_domain = domain

        row = [None, None, None, None, container_name]
        output_array.append(row)

        for assigned_workload in container_obj.workloads:
            if container_type != packing.ContainerType.primary:
                output_array.append(
                    [
                        "",
                        "",
                        "",
                        "",
                        "",
                        assigned_workload.workload.name,
                        str(assigned_workload.mode),
                        assigned_workload.num_clients,
                    ]
                )

    make_all_rows_same_length(output_array)
    sheet.range("A1").value = output_array

    for (row, row_appliance), appliance_idx in row_info.items():
        sheet.range("B" + str(row)).add_hyperlink(
            "",
            text_to_display=f"{appliance_idx}",
            screen_tip=f"{row_appliance}",
        )

    fit_sheet(sheet)


def get_domain_media(mresult, domain_selected):
    row_data = {}
    row_count = 0
    output_array = []

    filtered_media_servers = (
        (site_name, app_id, assigned_appliance)
        for (domain, site_name, app_id, assigned_appliance) in mresult.all_media_servers
        if domain == domain_selected
    )
    site_groups = itertools.groupby(
        filtered_media_servers, lambda appl_description: appl_description[0]
    )

    for site_name, appliance_iter in site_groups:
        appliance_list = list(appliance_iter)
        output_list_site = [
            ["", site_name, "", "", len(appliance_list), "", "", "", ""]
        ]
        row_count += len(output_list_site)
        for _, app_id, assigned_appliance in appliance_list:
            all_dr = True
            output_list_appliance = [
                [
                    "",
                    "",
                    "",
                    "",
                    "",
                    assigned_appliance.appliance.config_name,
                    "",
                    "",
                    "",
                ]
            ]
            row_count += len(output_list_appliance)
            for assigned_workload in assigned_appliance.workloads:
                if (
                    assigned_workload.mode == packing.WorkloadMode.media_primary
                    or assigned_appliance.appliance.dr_candidate
                ):
                    all_dr = False
                    output_list_appliance.append(
                        [
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            assigned_workload.workload.name,
                            str(assigned_workload.mode),
                            assigned_workload.num_clients,
                        ]
                    )
                    row_count += 1
                    row_data[
                        (
                            row_count,
                            domain_selected,
                            site_name,
                            assigned_workload.workload.name,
                        )
                    ] = assigned_workload.num_clients
            if not all_dr:
                output_list_site.extend(output_list_appliance)
        if len(output_list_site) > 1:
            output_array.extend(output_list_site)
    return output_array, row_data


def sort_workload_region_name(workload_list):
    """
    In place sort of the workload list, by region, then by name.
    Name is highest level sort.
    Then in order, origin site, DR site (if present), Cloud if present.

    Case insensitive sort.
    """

    def destination_code(w):
        if w.ltr_enabled:
            return 2
        elif w.dr_enabled:
            return 1
        else:
            return 0

    workload_list.sort(key=lambda a: [a.name.upper(), destination_code(a)])


def get_multiple_workloads_types(wkld, final_year):
    """
    Given a workload return up to three rows for display.

    Local backup.
    Possible DR replication.
    Possible Cloud.

    Return an array of one to three rows.
    """
    result = []
    # first the local
    row = [wkld.name, wkld.site_name, "PRIMARY"]
    for yr in range(1, final_year + 1):
        yr_storage = wkld.total_storage_for_year(yr) * wkld.num_instances
        row.append(yr_storage.to_float("TiB"))
    result.append(row)
    # then Replication, if enabled
    if wkld.dr_enabled:
        row = [wkld.name, str(wkld.dr_dest), "REP"]
        for yr in range(1, final_year + 1):
            yr_storage = wkld.dr_storage_for_year(yr) * wkld.num_instances
            row.append(yr_storage.to_float("TiB"))
        result.append(row)

    if wkld.ltr_enabled:
        row = [wkld.name, "CLOUD", "REP"]
        for yr in range(1, final_year + 1):
            yr_storage = wkld.cloud_storage_for_year(yr) * wkld.num_instances
            row.append(yr_storage.to_float("TiB"))
        result.append(row)

    return result


def get_workload_capacity_usage(workload_list, final_year):
    result = []
    sort_workload_region_name(workload_list)
    for w in workload_list:
        # get one or more rows depending on which backup destinatons in use
        rows_workload_by_types = get_multiple_workloads_types(w, final_year)
        for one_row in rows_workload_by_types:
            result.append(one_row)
    return result


@timers.record_time("writing write_raw_flex")
def write_raw_flex(sheet, mresult, workload_list, resource_tip=True):
    planning_year = mresult.planning_year
    num_years = mresult.num_years

    sheet.clear()
    row_info = {}
    result = [
        [
            "Site",
            "Appliance",
            "Container",
            "Workload",
            "Mode",
            "Assignment",
            "DR Capacity of Planning Horizon (TiB)",
        ]
    ]

    for (
        domain,
        site_name,
        appliance_name,
        app,
        container_name,
        container_type,
        container_obj,
    ) in mresult.all_containers:
        appliance_spec = app.appliance

        if container_type == packing.ContainerType.primary:
            workload_name = ""
            inst_assigned = ""
            dr_site_capacity = ""
            result.append(
                [
                    site_name,
                    appliance_name,
                    container_name,
                    workload_name,
                    str(container_type),
                    inst_assigned,
                    dr_site_capacity,
                ]
            )
            row_info[(len(result), appliance_spec.config_name)] = appliance_name
        else:
            for assigned_workload in container_obj.workloads:
                wk = assigned_workload.workload
                mode = assigned_workload.mode
                num_clients = assigned_workload.num_clients
                if mode == packing.WorkloadMode.primary:
                    workload_name = ""
                    inst_assigned = ""
                    dr_site_capacity = ""
                elif (
                    mode == packing.WorkloadMode.media_dr
                    and not appliance_spec.dr_candidate
                ):
                    workload_name = "DR for " + str(wk.name)
                    inst_assigned = ""
                    dr_site_capacity = round(
                        (
                            wk.total_storage_for_year(planning_year) * num_clients
                        ).to_float("TiB"),
                        2,
                    )
                else:
                    workload_name = wk.name
                    inst_assigned = num_clients
                    dr_site_capacity = ""
                result.append(
                    [
                        site_name,
                        appliance_name,
                        container_name,
                        workload_name,
                        str(mode),
                        inst_assigned,
                        dr_site_capacity,
                    ]
                )
                row_info[(len(result), appliance_spec.config_name)] = appliance_name

    sheet.range("A1").value = result
    sheet.range("A1").expand().name = "vupc_data_flex"
    sheet.range((1, 1), (1, len(result[0]))).name = "heading_raw_data_flex"

    if resource_tip:
        for (row, row_appliance), appliance_idx in row_info.items():
            sheet.range("B" + str(row)).add_hyperlink(
                "",
                text_to_display=f"{appliance_idx}",
                screen_tip=f"{row_appliance}",
            )

    workloads_with_usage = get_workload_capacity_usage(workload_list, num_years)
    capacity_top_line = len(result) + 8
    capacity_rows = [
        ["Workload Disk Usage By Year (TB)"],
        ["Workload", "Site", "Usage"] + [f"Year {n}" for n in range(1, 1 + num_years)],
    ]

    row_now = capacity_top_line + 2
    for wk_new in workloads_with_usage:
        capacity_rows.append(wk_new)
        row_now += 1
    make_all_rows_same_length(capacity_rows)
    cp_cell = f"A{capacity_top_line}"
    sheet.range(cp_cell).value = capacity_rows

    sheet.range(
        (capacity_top_line, 1),
        (capacity_top_line + len(workloads_with_usage), 1 + num_years),
    ).name = "capacity_usage_summary_flex"

    sheet.range((capacity_top_line, 1)).name = "section_header_wk_caps_flex"
    sheet.range((capacity_top_line, 1), (capacity_top_line, 3 + num_years)).merge()

    # 3 + NUM_YEARS because two extra columns are used for site and
    # type of usage (normal/replicated)
    sheet.range(
        (capacity_top_line + 1, 1), (capacity_top_line + 1, 3 + num_years)
    ).name = "heading_wk_caps_flex"

    sheet.range(
        (capacity_top_line + 2, 2),
        (
            capacity_top_line + len(workloads_with_usage) + 1,
            3 + num_years,
        ),
    ).name = "number_non_decimal_wk_capacities_flex"

    fit_sheet(sheet)


@timers.record_time("writing write_raw")
def write_raw(sheet, mresult, workload_list):
    planning_year = mresult.planning_year
    num_years = mresult.num_years

    sheet.clear()
    result = [
        [
            "Domain",
            "Site",
            "Appliance",
            "Appliance Id",
            "Workload",
            "Mode",
            "Assignment",
            "DR Capacity of Planning Horizon (TiB)",
        ]
    ]

    for domain, site_name, app_id, assigned_appliance in mresult.all_media_servers:
        appliance_spec = assigned_appliance.appliance

        for assigned_workload in assigned_appliance.workloads:
            wk = assigned_workload.workload
            mode = assigned_workload.mode
            num_clients = assigned_workload.num_clients
            if (
                mode == packing.WorkloadMode.media_dr
                and not appliance_spec.dr_candidate
            ):
                workload_name = "DR for " + str(wk.name)
                inst_assigned = ""
                dr_site_capacity = round(
                    (wk.total_storage_for_year(planning_year) * num_clients).to_float(
                        "TiB"
                    ),
                    2,
                )
            else:
                workload_name = wk.name
                inst_assigned = num_clients
                dr_site_capacity = ""
            result.append(
                [
                    domain,
                    site_name,
                    appliance_spec.config_name,
                    app_id,
                    workload_name,
                    str(mode),
                    inst_assigned,
                    dr_site_capacity,
                ]
            )

    sheet.range("A1").value = result
    sheet.range("A1").expand().name = "vupc_data"
    sheet.range((1, 1), (1, len(result[0]))).name = "heading_raw_data"

    workloads_with_usage = get_workload_capacity_usage(workload_list, num_years)
    capacity_top_line = len(result) + 8
    capacity_rows = [
        ["Workload Disk Usage By Year (TB)"],
        ["Workload", "Site", "Usage"] + [f"Year {n}" for n in range(1, 1 + num_years)],
    ]

    row_now = capacity_top_line + 2
    for wk_new in workloads_with_usage:
        capacity_rows.append(wk_new)
        row_now += 1
    make_all_rows_same_length(capacity_rows)
    cp_cell = f"A{capacity_top_line}"
    sheet.range(cp_cell).value = capacity_rows

    sheet.range(
        (capacity_top_line, 1),
        (capacity_top_line + len(workloads_with_usage), 1 + num_years),
    ).name = "capacity_usage_summary"

    sheet.range((capacity_top_line, 1)).name = "section_header_wk_caps"
    sheet.range((capacity_top_line, 1), (capacity_top_line, 3 + num_years)).merge()

    # 3 + NUM_YEARS because two extra columns are used for site and
    # type of usage (normal/replicated)
    sheet.range(
        (capacity_top_line + 1, 1), (capacity_top_line + 1, 3 + num_years)
    ).name = "heading_wk_caps"

    sheet.range(
        (capacity_top_line + 2, 2),
        (
            capacity_top_line + len(workloads_with_usage) + 1,
            3 + num_years,
        ),
    ).name = "number_non_decimal_wk_capacities"

    fit_sheet(sheet)


def get_name_for_utilization(site_name, util):
    concentrated_site = utils.sanitize_named_range(site_name)
    return f"value_shaded_{int(util * 10)}_{concentrated_site}"


def clear_names_like(book, name_prefix):
    names_to_delete = [
        name_obj.name
        for name_obj in book.names
        if name_obj.name.startswith(name_prefix)
    ]

    # The list has been built of names rather than the name objects
    # themselves because name objects can get invalidated after any
    # other object is deleted on macOS.

    for name in names_to_delete:
        book.names[name].delete()


def clear_shading_names(sheet):
    clear_names_like(sheet.book, "value_shaded_")


def all_dr(distribution, site_name):
    """
    Return whether all assignments in the distribution for the
    specified site are for DR targets, and the appliance selected is
    not suitable for DR.
    """

    if distribution.appliance.dr_candidate:
        return False

    for appliance in distribution[site_name]:
        for assign in appliance["assignment"]:
            if assign["mode"].name != "dr":
                return False
    return True


def build_summary_error_message(errors):
    message_parts = [WORKLOAD_ERRORS_TEXT]
    for err in errors:
        message_parts.append(str(err))
    return "".join(message_parts)


def report_error_site_summary(sheet, errors):
    if not errors:
        return

    color_range = sheet.range("A1:AB1")
    message_range = sheet.range(SUMMARY_ERROR_CELL)

    if errors == set([WorkloadErrorType.domains_split]):
        # if domain change was the only problem, use a caution color
        color = constants.NOTE_FIRST_ROW_FILL
    else:
        color = constants.ERROR_FIRST_ROW_FILL

    color_range.color = color
    message_range.column_width = 40
    message_range.value = build_summary_error_message(errors)
    message_range.color = (255, 255, 73)


def build_access_appliance_rows(mresult, site_columns: typing.Dict[str, int]):
    if not mresult.access_result:
        return []

    summary = mresult.access_result.summary
    heading_row = ["Access Appliances"]
    rows = []
    for appconfig, sitecounts in summary.items():
        row = [appconfig, sum(sitecounts.values()), ""]
        row.extend([""] * max(site_columns.values()))
        for site_name, site_count in sitecounts.items():
            site_col = site_columns[site_name]
            row[site_col] = site_count
        rows.append(row)
    return [heading_row, *rows]


@timers.record_time("writing write_site_summary_flex")
def write_site_summary_flex(sheet, variable_sheet, mresult, safety_margins, errors):
    sheet.clear()
    clear_shading_names(sheet)

    header_row_1 = ["Flex Appliance Config", "Total", "", "Sites"]
    header_row_2 = ["", "", ""]
    heading_rows = [header_row_1, header_row_2]

    # try if any unsupported appliances found
    any_unsupported = False

    # models for unsupported appliances
    unsupported_models = {}

    # separate out the supported and unsupported Appliances
    # so supported can be put first in output
    supported_excel_rows = []
    unsupported_excel_rows = []

    site_cells = {}

    appliance_configs = {}
    sites = set()
    appliance_models = set()

    summary = mresult.summary
    for config_name, cfg_summary in summary.flex_app_site_summaries:
        sites = sites.union(cfg_summary.keys())
        appliance_obj = summary.appliances[config_name]
        appliance_configs[config_name] = {
            "model": appliance_obj.model,
            "supported": appliance_obj.performance_supported,
        }
        appliance_models.add(appliance_obj.model)

    for config_name, cfg_summary in summary.flex_app_site_summaries:
        appliance_info = appliance_configs[config_name]

        is_supported = appliance_info["supported"]
        any_unsupported |= not is_supported

        if is_supported:
            support_tag = ""
        else:
            unsupported_models[appliance_info["model"]] = 1
            support_tag = " Unsup"

        summary_row = [config_name + support_tag, 0, ""]
        for site_name in sorted(sites):
            if site_name not in cfg_summary:
                # This site does not have any appliances of the
                # current config_name type.
                logger.info(
                    "site %s has no need of Flex Appliance %s",
                    site_name,
                    config_name,
                )
                summary_row.append(None)
                continue

            site_cells[site_name] = {"utilization": mresult.site_utilization(site_name)}

            num_appliances = cfg_summary[site_name]
            summary_row.append(num_appliances)
            summary_row[1] += num_appliances

        if is_supported:
            supported_excel_rows.append(summary_row)
        else:
            # this 1 in the last row is a marker that the Appliance
            # is unsupported and is used by conditional formatting
            # in the Excel sheet to indicate this fact

            # adjust length to length needed for the marker for unsupported
            # to be in column BA
            if len(summary_row) < 52:
                for _ in range(52 - len(summary_row)):
                    summary_row.append(None)
                summary_row.append(1)
            unsupported_excel_rows.append(summary_row)

    access_rows = build_access_appliance_rows(
        mresult, {site_name: idx + 3 for (idx, site_name) in enumerate(sites)}
    )

    table_row = 3
    sites_row_num = table_row + 1
    site_col = len(header_row_2) + 1
    for site_name in sorted(sites):
        header_row_2.append(f"{site_name}")
        site_cells[site_name]["cell"] = (sites_row_num, site_col)
        site_col += 1

    sheet.range("A1").value = [
        [
            "Package Date",
            package_version.package_timestamp,
            None,
            "Package Version",
            package_version.package_version,
        ],
        ["Sizing Run At", datetime.datetime.now(), None, None, None],
    ]

    result = heading_rows + supported_excel_rows + unsupported_excel_rows + access_rows

    if any_unsupported:
        # create warning text and include it in the output sheet
        bad_models = sorted(unsupported_models.keys())
        have_multiple_models = len(bad_models) > 1

        if have_multiple_models:
            # commas to separate models
            bad_model_text = (", ").join(bad_models[:-1])
            bad_model_text += ", and %s," % (bad_models[-1],)
        else:
            # only one model is unsupported
            bad_model_text = bad_models[0]

        model_alert_text = f"NOTE: {bad_model_text} appliances are sized for capacity only, no performance metrics are considered"

        # Make the model alert text the second item in the result array.
        result = result[:2] + [[model_alert_text]] + result[2:]

    for site_name, site_info in site_cells.items():
        if "cell" not in site_info:
            # DR site, no header for it
            continue
        sheet.range(site_info["cell"]).name = get_name_for_utilization(
            f"{site_name}", site_info["utilization"]
        )

    make_all_rows_same_length(result)
    sheet.range(f"A{table_row}").value = result

    sheet.range((table_row, 1), (sites_row_num, 1)).merge()
    sheet.range((table_row, 2), (sites_row_num, 2)).merge()
    last_col = 3 + len(sites)
    sheet.range((table_row, 4), (table_row, last_col)).merge()
    sheet.range((table_row, 1), (sites_row_num, last_col)).name = (
        "heading_flex_appliances_needed"
    )

    if access_rows:
        access_table_row = table_row + len(result) - len(access_rows)
        sheet.range((access_table_row, 1)).name = "heading_flex_access_appliances"
        sheet.range((access_table_row, 1), (access_table_row, last_col)).merge()

    chart = sheet.charts[0]
    chart.top = sheet.range((1, 1), (3 + len(result), 1)).height
    chart.left = 0

    write_safety_table(sheet, chart, 4 + len(result), appliance_models, safety_margins)

    fit_sheet(sheet)

    report_error_site_summary(sheet, errors)


@timers.record_time("writing write_site_summary")
def write_site_summary(sheet, variable_sheet, mresult, safety_margins, errors):
    sheet.clear()
    clear_shading_names(sheet)

    header_row_1 = ["Media Server Config", "Total", "", "Domains/Sites"]
    header_row_2 = ["", "", ""]
    result = [header_row_1, header_row_2]

    # try if any unsupported appliances found
    any_unsupported = False

    # models for unsupported appliances
    unsupported_models = {}

    # separate out the supported and unsupported Appliances
    # so supported can be put first in output
    supported_excel_rows = []
    unsupported_excel_rows = []

    site_cells = {}

    appliance_configs = {}
    sites = set()
    appliance_models = set()

    summary = mresult.summary
    for config_name, cfg_summary in summary.media_site_summaries:
        sites = sites.union(cfg_summary.keys())
        appliance_obj = summary.appliances[config_name]
        appliance_configs[config_name] = {
            "model": appliance_obj.model,
            "supported": appliance_obj.performance_supported,
        }
        appliance_models.add(appliance_obj.model)

    for config_name, cfg_summary in summary.media_site_summaries:
        appliance_info = appliance_configs[config_name]

        is_supported = appliance_info["supported"]
        any_unsupported |= not is_supported

        if is_supported:
            support_tag = ""
        else:
            unsupported_models[appliance_info["model"]] = 1
            support_tag = " Unsup"

        summary_row = [config_name + support_tag, 0, ""]
        for site_qname in sorted(sites):
            (domain, site_name) = site_qname
            if site_qname not in cfg_summary:
                # This site does not have any appliances of the
                # current config_name type.
                logger.info(
                    "site %s/%s has no need of media server %s",
                    domain,
                    site_name,
                    config_name,
                )
                summary_row.append(None)
                continue

            site_cells[site_qname] = {
                "utilization": mresult.site_utilization(domain, site_name)
            }

            num_appliances = cfg_summary[site_qname]
            summary_row.append(num_appliances)
            summary_row[1] += num_appliances

        if is_supported:
            supported_excel_rows.append(summary_row)
        else:
            # this 1 in the last row is a marker that the Appliance
            # is unsupported and is used by conditional formatting
            # in the Excel sheet to indicate this fact

            # adjust length to length needed for the marker for unsupported
            # to be in column BA
            if len(summary_row) < 52:
                for _ in range(52 - len(summary_row)):
                    summary_row.append(None)
                summary_row.append(1)
            unsupported_excel_rows.append(summary_row)

    site_columns = {}
    for idx, (_domain, site_name) in enumerate(sorted(sites)):
        if site_name in site_columns:
            continue
        site_columns[site_name] = idx + 3
    access_rows = build_access_appliance_rows(mresult, site_columns)

    table_row = 3
    sites_row_num = table_row + 1
    site_col = len(header_row_2) + 1
    for site_qname in sorted(sites):
        (domain, site_name) = site_qname
        header_row_2.append(f"{domain}/{site_name}")
        site_cells[site_qname]["cell"] = (sites_row_num, site_col)
        site_col += 1

    sheet.range("A1").value = [
        [
            "Package Date",
            package_version.package_timestamp,
            None,
            "Package Version",
            package_version.package_version,
        ],
        ["Sizing Run At", datetime.datetime.now(), None, None, None],
    ]

    result = result + supported_excel_rows + unsupported_excel_rows

    if any_unsupported:
        # create warning text and include it in the output sheet
        bad_models = sorted(unsupported_models.keys())
        have_multiple_models = len(bad_models) > 1

        if have_multiple_models:
            # commas to separate models
            bad_model_text = (", ").join(bad_models[:-1])
            bad_model_text += ", and %s," % (bad_models[-1],)
        else:
            # only one model is unsupported
            bad_model_text = bad_models[0]

        model_alert_text = f"NOTE: {bad_model_text} appliances are sized for capacity only, no performance metrics are considered"

        # Make the model alert text the second item in the result array.
        result = result[:2] + [[model_alert_text]] + result[2:]

    for site_qname, site_info in site_cells.items():
        if "cell" not in site_info:
            # DR site, no header for it
            continue
        (domain, site_name) = site_qname
        sheet.range(site_info["cell"]).name = get_name_for_utilization(
            f"{domain}{site_name}", site_info["utilization"]
        )

    master_summary = []
    for config_name, cfg_summary in summary.master_site_summaries:
        config_count = sum(cfg_summary.values())
        master_row = [config_name, config_count, ""]
        for site_qname in sorted(sites):
            master_count = cfg_summary.get(site_qname)
            master_row.append(master_count)
        master_summary.append(master_row)

    master_row = table_row + len(result)
    header_row_3 = [f"{constants.MANAGEMENT_SERVER_DESIGNATION} Config", "Total", ""]
    result.append(header_row_3)
    result = result + master_summary

    result += access_rows

    make_all_rows_same_length(result)
    sheet.range(f"A{table_row}").value = result

    sheet.range((table_row, 1), (sites_row_num, 1)).merge()
    sheet.range((table_row, 2), (sites_row_num, 2)).merge()
    last_col = 3 + len(sites)
    sheet.range((table_row, 4), (table_row, last_col)).merge()
    sheet.range((table_row, 1), (sites_row_num, last_col)).name = (
        "heading_appliances_needed"
    )
    sheet.range((master_row, 1), (master_row, last_col)).name = (
        "heading_appliances_needed_master_server"
    )

    if access_rows:
        access_table_row = table_row + len(result) - len(access_rows)
        sheet.range((access_table_row, 1)).name = "heading_access_appliances"
        sheet.range((access_table_row, 1), (access_table_row, last_col)).merge()

    chart = sheet.charts[0]
    chart.top = sheet.range((1, 1), (3 + len(result), 1)).height
    chart.left = 0

    write_safety_table(sheet, chart, 4 + len(result), appliance_models, safety_margins)

    fit_sheet(sheet)

    report_error_site_summary(sheet, errors)


@timers.record_time("writing write_management_server_summary")
def write_management_server_summary(sheet, mresult):
    last_year = mresult.num_years

    while sheet.pictures:
        sheet.pictures[0].delete()
    clear_names_like(sheet.book, "heading_master")

    sheet.range("A1").value = ["Domain", constants.MANAGEMENT_SERVER_DESIGNATION]
    current_row = 2
    for domain, _site_name, app_id, mserver in mresult.all_master_servers:
        fig = charting.render_master_chart_single(mserver, last_year)
        head_cell = sheet.range((current_row, 1), (current_row, 2))
        head_cell.value = [domain, app_id]
        head_cell.name = utils.sanitize_named_range(f"heading_master_{app_id}")
        chart_left = 0
        chart_top = head_cell.top + head_cell.height
        chart_width = fig.get_figwidth() * fig.get_dpi() * 0.5
        chart_height = fig.get_figheight() * fig.get_dpi() * 0.5
        chart = sheet.pictures.add(
            fig,
            name=f"Utilization_{app_id}",
            update=False,
            left=chart_left,
            top=chart_top,
            width=chart_width,
            height=chart_height,
        )
        current_next_col = find_next_column(sheet, chart, current_row)
        current_row = write_master_server_resource_usage_chart(
            current_row, current_next_col, sheet, mserver, domain, app_id, last_year
        )


def write_master_server_utilization_chart(
    current_row_next, sheet, mserver, domain, app_id, last_year
):
    clear_names_like(sheet.book, "heading_master")

    fig_next = charting.render_master_chart_single(mserver, last_year)
    head_cell = sheet.range((current_row_next, 1), (current_row_next, 2))
    head_cell.value = [domain, app_id]
    head_cell.name = utils.sanitize_named_range(f"heading_master{app_id}")
    chart_left = 0
    chart_top = head_cell.top + head_cell.height
    chart_width = fig_next.get_figwidth() * fig_next.get_dpi() * 0.5
    chart_height = fig_next.get_figheight() * fig_next.get_dpi() * 0.5
    chart = sheet.pictures.add(
        fig_next,
        name=f"Utilization_{app_id}",
        update=False,
        left=chart_left,
        top=chart_top,
        width=chart_width,
        height=chart_height,
    )

    return find_next_column(sheet, chart, current_row_next)


def write_master_server_resource_usage_chart(
    current_row, current_next_col, sheet, mserver, domain, app_id, last_year
):
    fig_next = charting.render_master_resorce_usage_chart(mserver, last_year)
    head_cell = sheet.range(
        (current_row, current_next_col), (current_row, current_next_col + 1)
    )
    head_cell.name = utils.sanitize_named_range(f"heading_master{app_id}")
    chart_left = head_cell.left
    chart_top = head_cell.top + head_cell.height
    chart_width = fig_next.get_figwidth() * fig_next.get_dpi() * 0.5
    chart_height = fig_next.get_figheight() * fig_next.get_dpi() * 0.5

    chart = sheet.pictures.add(
        fig_next,
        name=f"Master Resource Utilization_{app_id}",
        update=False,
        left=chart_left,
        top=chart_top,
        width=chart_width,
        height=chart_height,
    )

    return find_next_cell(sheet, chart)


def find_next_cell(sheet, chart):
    height_required = chart.top + chart.height

    top = bottom = 1

    sheet_range = sheet.range((top, 1), (bottom, 1))
    while sheet_range.top + sheet_range.height < height_required:
        bottom *= 2
        sheet_range = sheet.range((top, 1), (bottom, 1))

    # required row is somewhere between bottom/2 and bottom
    low, high = bottom // 2, bottom
    while high > low + 1:
        mid = (low + high) // 2
        sheet_range = sheet.range((top, 1), (mid, 1))
        range_position = sheet_range.top + sheet_range.height
        if range_position < height_required:
            low = mid
        elif range_position >= height_required:
            high = mid
    return high + 1


def write_safety_table(sheet, chart, row_num, appliance_models, safety_margins):
    col = find_next_column(sheet, chart, row_num)
    models = list(sorted(appliance_models))
    data = [["Resource Safety Margins"], ["Resource Type", *models]]
    safety_keys = {
        "Max Capacity Utilization (%)": "Capacity",
        "Max CPU Utilization (%)": "CPU",
        "Max NW Utilization (%)": "NW",
        "Max MBPs Utilization (%)": "IO",
        "Max Memory Utilization (%)": "Memory",
    }
    for display_key, key in safety_keys.items():
        values = [f"{safety_margins[model][key] * 100:.0f}%" for model in models]
        data.append([display_key, *values])
    make_all_rows_same_length(data)
    sheet.range((row_num, col)).value = data

    section_header = sheet.range((row_num, col), (row_num, col + len(appliance_models)))
    section_header.merge()
    section_header.name = "section_header_app_needed_safety"

    table_header = sheet.range(
        (row_num + 1, col), (row_num + 1, col + len(appliance_models))
    )
    table_header.name = "heading_app_needed_safety"

    key_column = sheet.range((row_num + 2, col), (row_num + 2 + len(safety_keys), col))
    key_column.name = "heading_app_needed_safety_col"


def find_next_column(sheet, chart, row_num):
    # figure out what the first column is that we can write the safety
    # table in without being hidden under the chart.
    # Helps to find next column next empty column
    width_required = chart.left + chart.width

    # first calculate outer bounds to test
    col = 2
    sheet_range = sheet.range((row_num, 1), (row_num, col - 1))
    while sheet_range.width < width_required:
        col *= 2
        sheet_range = sheet.range((row_num, 1), (row_num, col - 1))

    # required column is somewhere between col/2 and col
    low, high = col // 2, col
    while high > low + 1:
        mid = (low + high) // 2
        sheet_range = sheet.range((row_num, 1), (row_num, mid - 1))
        if sheet_range.width < width_required:
            low = mid
        elif sheet_range.width >= width_required:
            high = mid
    return high


def workload_summary_headers(mresult):
    headers = ["Workload", "Site", "ID"]
    for i in range(mresult.num_years):
        headings = [
            f"Year {i + 1} - {heading}"
            for heading in constants.WORKLOAD_SUMMARY_HEADINGS
        ]
        headers.extend(headings)

    return [headers]


def workload_summary_sheet_data(mresult):
    """returns workload attributes like storage and network throughput for each workload"""
    result = []

    workload_summary_attributes = mresult.workload_summary_attributes
    for key, w_summary_objs in workload_summary_attributes.items():
        (wname, site) = key
        row_data = [wname, site, None]
        for workload_obj in w_summary_objs:
            row_data.append(workload_obj.storage_primary.to_float("TiB"))
            row_data.append(workload_obj.storage_dr.to_float("TiB"))
            row_data.append(workload_obj.storage_cloud.to_float("TiB"))
            row_data.append(workload_obj.storage_cloud_worst_case.to_float("TiB"))
            row_data.append(
                workload_obj.storage_before_deduplication_primary.to_float("TiB")
            )
            row_data.append(workload_obj.storage_catalog.to_float("GiB"))
            row_data.append(workload_obj.total_network_utilization.to_float("MiB"))
            row_data.append(workload_obj.total_dr_network_utilization.to_float("MiB"))
            row_data.append(
                workload_obj.total_cloud_network_utilization.to_float("MiB")
            )
            row_data.append(workload_obj.cloud_storage.to_float("GiB"))
            row_data.append(workload_obj.cloud_transfer.to_float("GiB"))
            row_data.append(workload_obj.backup_volume.to_float("GiB"))
        result.append(row_data)

    return result


@timers.record_time("writing write_workload_summary")
def write_workload_summary(summary_sheet, mresult):
    """
    Write a sheet with year by year utilization of each workload for resource categories.
    """

    result = workload_summary_headers(mresult) + workload_summary_sheet_data(mresult)
    summary_sheet.range("A2").value = result

    fit_sheet(summary_sheet)


@timers.record_time("write_chart_data_flex")
def write_chart_data(sheet, mresult):
    """
    Take data put in the Appliance Summary sheet, and put it in the
    Appliance Chart Data sheet, where it will be used, via named ranges,
    by the chart in the Appliance Chart sheet.
    """

    timeframe = mresult.timeframe
    usage = mresult.yoy_max_utilization

    usage_data = {
        "Capacity": [u["capacity"] for u in usage],
        "Memory": [u["mem"] for u in usage],
        "CPU": [u["cpu"] for u in usage],
        "I/O": [u["io"] for u in usage],
        "Network": [u["nic_pct"] for u in usage],
        "Allocated_Capacity": [u["alloc_capacity_pct"] for u in usage],
    }

    # This is the order they are used in the chart
    data_type_list = constants.CHARTED_APPLIANCE_SUMMARY_HEADINGS

    # need a bit of complication to be sure records are distinct
    usage_data_record = [None] * len(data_type_list)
    for n in range(len(data_type_list)):
        # Get the information for this data type, Storage, etc.
        data_to_use = usage_data[data_type_list[n]]
        data_type_numbers = []
        for row in range(len(data_to_use)):
            data_type_numbers.append(data_to_use[row])
        usage_data_record[n] = data_type_numbers

    # transpose to get the data into columns for the spreadsheet
    transposed_data_record = [
        [usage_data_record[m][c] for m in range(len(usage_data_record))]
        for c in range(len(usage_data_record[0]))
    ]
    sheet.range("A1").value = transposed_data_record

    # Data that doesn't require scaling.
    # Put data related to planning horizon and safety that is used by chart.

    # Vertical line for the planning horizon
    # X axis at the year, Y axis from 0 to 1 (100%)
    sheet.range("G1").value = [
        [timeframe.planning_year, 0],
        [timeframe.planning_year, 1],
    ]

    axis_labels_rows = []
    # per year graph axis labeling
    for y in range(1, 1 + timeframe.num_years):
        # Horizontal line for the safety 100% line
        # X axis from year 1 to year NUM_YEARS
        axis_labels_rows.append([y, 1])

    sheet.range("J1").value = axis_labels_rows
    last_row = timeframe.num_years
    sheet.range((1, 1), (last_row, 1)).name = "chart_series_storage"
    sheet.range((1, 2), (last_row, 2)).name = "chart_series_memory"
    sheet.range((1, 3), (last_row, 3)).name = "chart_series_cpu"
    sheet.range((1, 4), (last_row, 4)).name = "chart_series_io"
    sheet.range((1, 5), (last_row, 5)).name = "chart_series_network"
    sheet.range((1, 6), (last_row, 6)).name = "chart_series_alloc_storage"
    sheet.range((1, 10), (last_row, 10)).name = "chart_categories_safety"
    sheet.range((1, 11), (last_row, 11)).name = "chart_series_safety"


def write_errors_and_notes(
    error_note_sheet, workload_error_list, workload_domain_change_list, primary_errors
):
    error_note_sheet.clear_contents()
    error_list = []
    error_list.append(["Workload", "Error & Note", "Domain", "Error Type"])
    if workload_error_list:
        for key, item in workload_error_list.items():
            error_list.append([key, item, "", "Media Server Misfit"])
    if workload_domain_change_list:
        error_list.extend(workload_domain_change_list)
    if primary_errors:
        for wname, werror in sorted(primary_errors.items()):
            error_list.append(
                [wname, werror, "", f"{constants.MANAGEMENT_SERVER_DESIGNATION} Misfit"]
            )
    error_note_sheet.range("A1").value = error_list


def row_to_dict(sheet, col_header, row_current_index, col_end_index):
    row_current = sheet.range(
        (row_current_index, 1), (row_current_index, col_end_index)
    )

    return dict(zip(col_header.value, row_current.value))


def row_to_policy(sheet, col_header, row_current_index, col_end_index):
    excel_row = row_to_dict(sheet, col_header, row_current_index, col_end_index)
    if constants.MANAGEMENT_SERVER_DESIGNATION_PREVIOUS in excel_row:
        if not excel_row[constants.MANAGEMENT_SERVER_DESIGNATION_PREVIOUS]:
            return None
    elif constants.MANAGEMENT_SERVER_DESIGNATION in excel_row:
        if not excel_row[constants.MANAGEMENT_SERVER_DESIGNATION]:
            return None
    else:
        return None
    p = {}
    for k, col in SHEET_ITEMIZATION_MAP.items():
        if col in excel_row.keys():
            p[k] = excel_row[col]
    for p_std, p_use in POLICY_TYPE_MAP.items():
        if p["policy_type"] == p_std:
            p["policy_type"] = p_use
    isValid = set(p.keys()) >= REQUIRED_ITEMIZATION_KEYS
    if not isValid:
        missing_keys = REQUIRED_ITEMIZATION_KEYS - set(p.keys())
        cols = [SHEET_ITEMIZATION_MAP[k] for k in missing_keys]
        raise MissingRequiredKey("Missing the required column(s): " + str(cols))

    return p


def row_to_slp(dataset, row_num, parser, return_as=SLP):
    excel_row = dict(zip(dataset[0], dataset[row_num]))
    if not excel_row["Storage Lifecycle Policy"]:
        return None
    sl = {}
    errors = []
    for col, xlator in parser.items():
        try:
            if return_as is OBJECT:
                sl[col] = xlator.raw_value(excel_row)
            else:
                sl[col] = xlator.value(excel_row)

            logger.debug("column: %s, result: %s", col, sl[col])
        except Exception as ex:
            errors.append(ex)
    if errors:
        msgs = "\n".join(
            msg for (msg, _) in itertools.groupby(sorted(str(e) for e in errors))
        )
        raise BadInputError(f"In row {row_num + 1}:\n" + msgs)
    if "domain" in sl:
        if sl["domain"] in ["", "None", "none"]:
            sl["domain"] = None

    return sl


def row_to_workload(
    dataset,
    row_num,
    slps,
    parser,
    return_as=WORKLOAD,
):
    excel_row = dict(zip(dataset[0], dataset[row_num]))
    if not excel_row["Workload Name"]:
        return None
    w = {}
    errors = []
    for col, xlator in parser.items():
        try:
            if return_as is OBJECT:
                w[col] = xlator.raw_value(excel_row)
            else:
                w[col] = xlator.value(excel_row)

            logger.info("column: %s, result: %s", col, w[col])
        except Exception as ex:
            if col in workload.IGNORED_KEYS:
                logger.debug(ex)
            else:
                logger.exception("error parsing column %s from row %s", col, excel_row)
                errors.append(ex)
    if excel_row["Storage Lifecycle Policy"]:
        slp_name = excel_row["Storage Lifecycle Policy"]
        if slp_name not in slps:
            errors.append(UnknownSlpError(slp_name))
        else:
            slp_info = slps[slp_name]
            w.update(slp_info)

    if errors:
        msgs = "\n".join(
            msg for (msg, _) in itertools.groupby(sorted(str(e) for e in errors))
        )
        raise BadInputError(f"In row {row_num + 1}:\n" + msgs)

    # compensate for the dr location being present on the sheet
    # if a DR dest SLP is changed to non-DR-Dest on the workloads
    # page.
    if "dr" not in w["backup_location_policy"]:
        w["dr_dest"] = None

    if return_as is not WORKLOAD:
        return w
    else:
        if int(w["workload_size"]) == 0:
            logger.debug(
                "Discarded workload %s. converted FETB size: %s entered FETB size: %.19f",
                w["workload_name"],
                w["workload_size"],
                excel_row["FETB (TiB)"],
            )
            return None
        return workload.Workload(w)


def excel_to_per_model_safety(sheet):
    #
    # Get per model safety margins
    #

    # First get the Appliance models from the headers
    app_models = sheet.range("B1").expand("right").value
    # get all the data as an array
    # Starts in Column B
    app_data = sheet.range("A2").expand("table").value
    app_dict = {}
    for row in app_data:
        app_dict[row[0]] = row[1:]
    per_app_data = {}
    for n in range(len(app_models)):
        values = {
            "Capacity": app_dict["Max Capacity Utilization (%)"][n],
            "CPU": app_dict["Max CPU Utilization (%)"][n],
            "NW": app_dict["Max NW Utilization (%)"][n],
            "IO": app_dict["Max MBPs Utilization (%)"][n],
            "Memory": app_dict["Max Memory Utilization (%)"][n],
            "Jobs_Per_Day": app_dict["Max Jobs/Day"][n],
            "DBs@15": app_dict["Max DBs with 15 Min RPO"][n],
            "VMs": app_dict["Max VM Clients"][n],
            "Streams": app_dict["Max Concurrent Streams"][n],
            "Version": app_dict.get("Software Version", "Latest"),
            "Max_Cal_Cap": app_dict["MSDP Max Size (TB)"][n],
        }
        for safety_value in ["DBs@15", "Streams", "Jobs_Per_Day", "VMs"]:
            if values[safety_value] is not None and values[safety_value] != "NA":
                values[safety_value] = int(values[safety_value])
            else:
                values[safety_value] = None
        if (
            values["Max_Cal_Cap"] is not None
            and values["Max_Cal_Cap"] != "NA"
            and app_models[n] in appl.get_models("MSDP_CAPPED_APPLIANCES")
        ):
            values["Max_Cal_Cap"] = int(values["Max_Cal_Cap"])
        else:
            values["Max_Cal_Cap"] = None

        for src_fld, tgt_fld in [
            ("Max Number of Files", "Files"),
            ("Max Number of Images", "Images"),
            ("LUN Size for Flex appliance (TiB)", "LUN_Size"),
            (
                f"Max Number of {constants.MANAGEMENT_SERVER_DESIGNATION} Containers",
                "Primary_Containers",
            ),
            ("Max Number of Media Server Containers", "MSDP_Containers"),
            (
                "Max Catalog Size (TB)",
                "Max_Catalog_Size",
            ),
            (
                "Max Number of Universal Shares",
                "Max_Universal_Share",
            ),
        ]:
            if src_fld in app_dict:
                value = app_dict[src_fld][n]
                if value == "NA" or value is None or value == 0:
                    values[tgt_fld] = None
                else:
                    values[tgt_fld] = int(value)

        per_app_data[app_models[n]] = values

    return per_app_data


def excel_to_horizon(variables_sheet):
    """
    Get planning_horizon from the _variables sheet.
    """
    horizon_value = int(variables_sheet.range("sizing_time_frame").value)
    extension_value = int(variables_sheet.range("sizing_first_extension").value)
    return utils.TimeFrame(num_years=extension_value, planning_year=horizon_value)


def policy_to_itemization(sheet):
    itemization_list = []
    col_end_index = sheet.used_range.columns.count
    col_header = sheet.range((1, 1), (1, col_end_index))
    row_last_index = sheet.used_range.rows.count
    for row_current_index in range(2, row_last_index + 1):
        policy = row_to_policy(sheet, col_header, row_current_index, col_end_index)
        if policy:
            itemization_list.append(policy)
        row_current_index += 1

    return itemization_list


def post_nbdeployutil_import(book):
    book.macro("freeze_sheet_header")()


def import_nbdeployutil(rep_file_name, slp_name, src_file_name=None, interactive=True):
    if src_file_name is None:
        bk_vupc = xw.Book.caller()
    else:
        bk_vupc = xw.Book(src_file_name)

    logs_sheet = get_sheet(bk_vupc, LOGS_SHEET, clear_contents=False)
    log_handler = setup_logging(logs_sheet)
    logger.info("Importing NBDeployUtil Report: %s", rep_file_name)

    bk_rep = None
    try:
        bk_rep = xw.Book(rep_file_name)
        if not sheet_exists(bk_rep, ITEMIZATION_SHEET):
            raise MissingSheetError(ITEMIZATION_SHEET)
        if bk_rep.sheets(ITEMIZATION_SHEET).used_range.rows.count <= 1:
            raise EmptySheetError(ITEMIZATION_SHEET)
        do_import_nbdeployutil(bk_vupc, bk_rep, slp_name)
    except Exception as ex:
        logger.exception(ex)
        report_error = bk_vupc.macro("show_message")
        report_error(str(ex), MESSAGE_ERROR_TEXT)
    else:
        if interactive:
            report_info = bk_vupc.macro("show_message")
            report_info(
                f"Successfully imported NBDeployUtil Report: {rep_file_name}",
                MESSAGE_INFO_TEXT,
            )
    finally:
        if bk_rep is not None and src_file_name is None:
            bk_vupc.macro("close_workbook")(rep_file_name)

    stop_logging(log_handler)


def do_import_nbdeployutil(bk_vupc, bk_rep, slp_name):
    try:
        itemization_sheet = get_sheet(bk_rep, ITEMIZATION_SHEET, clear_contents=False)
        itemization_list = policy_to_itemization(itemization_sheet)
    except MissingRequiredKey:
        raise

    logger.info("Processing NBDeployUtil Report")
    policies = {}

    for item in itemization_list:
        if item["policy_name"] not in policies:
            policy = {
                "policy_name": item["policy_name"],
                "policy_type": item["policy_type"],
                "client_name": set(),
                "total": 0,
            }
            policies[item["policy_name"]] = policy

        if item["client_name"] not in policies[item["policy_name"]]["client_name"]:
            policies[item["policy_name"]]["client_name"].add(item["client_name"])
            policies[item["policy_name"]]["total"] += item["total"]

    workloads = []
    for po in sorted(policies.keys()):
        imported_type = policies[po]["policy_type"]
        policies[po]["policy_type"] = constants.REMAPPED_WORKLOAD_TYPES.get(
            imported_type, imported_type
        )

        workloads.append(
            [
                policies[po]["policy_name"],
                policies[po]["policy_type"],
                len(policies[po]["client_name"]),
                policies[po]["total"] / (utils.Size.UNIT_SCALES["TB"]),
                slp_name,
            ]
        )

    require_slp(bk_vupc, slp_name)

    logger.info("Imported %s workloads", len(workloads))
    workload_sheet = get_sheet(bk_vupc, WORKLOADS_SHEET, clear_contents=False)
    if workload_sheet.range("A1:D1").value != NBDEPLOYUTIL_EXPECTED_WORKLOADS_HEADERS:
        raise MissingWorkloadsError("Mismatched headers in Workloads sheet")
    row_last_index = workload_sheet.used_range.rows.count
    bk_vupc.macro("do_add_line")(
        WORKLOADS_SHEET, "new_workload_row", True, len(workloads)
    )
    workload_sheet.range(((row_last_index + 1), 1)).value = workloads
    post_nbdeployutil_import(bk_vupc)


def slp_exists(bk_vupc, slp_name):
    slps_sheet = bk_vupc.sheets[STORAGE_LIFECYCLE_POLICIES_SHEET]
    slps_data = excel_to_slp(slps_sheet)
    slp_names = set(slp["storage_lifecycle_policy"] for slp in slps_data)
    return slp_name in slp_names


def require_slp(book, slp_name):
    if slp_exists(book, slp_name):
        return

    logger.info("SLP %s does not exist, creating", slp_name)
    new_slp_row = book.macro("do_add_line")(
        STORAGE_LIFECYCLE_POLICIES_SHEET, "new_slp_row", True, 1
    )

    sheet = book.sheets[STORAGE_LIFECYCLE_POLICIES_SHEET]
    sheet.range((new_slp_row, 1)).value = slp_name


def excel_to_site_assignment(
    sheet, workload_list, planning_year, sizing_flex, safety_margins
):
    active_sites = get_site_hints_from_workloads(
        workload_list, planning_year, sizing_flex
    )
    site_assignments_list = []
    col_end_index = sheet.used_range.columns.count
    col_header = sheet.range((1, 1), (1, col_end_index))
    row_list = sheet.range((1, 1), (sheet.used_range.rows.count, 1)).value
    row_list = list(filter(None, row_list))
    row_last_index = len(row_list)
    for row_current_index in range(2, row_last_index + 1):
        excel_row = row_to_dict(sheet, col_header, row_current_index, col_end_index)
        if not excel_row["Site Name"]:
            break

        for as_domain, as_site in active_sites.keys():
            site_info = {
                "domain_name": None,
                "site_name": excel_row["Site Name"],
                "appliance_name": None,
                "appliance_model": None,
                "site_network_type": constants.DEFAULT_SITE_NETWORK_TYPE,
                "wan_network_type": None,
                "cc_network_type": None,
                "appliance_bandwidth_cc": utils.Size.from_ratio(
                    excel_row["Appliance Bandwidth for CC (Gbps)"], 8, "GiB"
                ),
                "software_version": constants.DEFAULT_SOFTWARE_VERSION,
            }
            if site_info["site_name"] != as_site:
                continue
            if site_info["site_name"] == as_site:
                site_info["domain_name"] = as_domain
                site_assignments_list.append(site_info)
            if excel_row["Software Version"]:
                site_info["software_version"] = excel_row["Software Version"]
            if excel_row["Appliance Configuration"]:
                if not is_config_safe(
                    excel_row["Appliance Configuration"], safety_margins
                ):
                    raise ApplianceConfigurationCapacityError(
                        excel_row["Appliance Configuration"], site_info["site_name"]
                    )
                site_info["appliance_name"] = excel_row["Appliance Configuration"]
            if excel_row["Appliance Model"]:
                site_info["appliance_model"] = str(
                    excel_row["Appliance Model"]
                ).replace(".0", "")
            if excel_row["Site Network Type"]:
                site_info["site_network_type"] = excel_row["Site Network Type"]
            if excel_row["WAN Network Type"]:
                site_info["wan_network_type"] = excel_row["WAN Network Type"]
            if excel_row["CC Network Type"]:
                site_info["cc_network_type"] = excel_row["CC Network Type"]
            site_info["site_hints"] = active_sites[(as_domain, as_site)]

        row_current_index += 1
    return site_assignments_list


def is_config_safe(config, safety_values):
    check_result = True
    config_model, config_size_str = config.split()
    if safety_values[config_model]["LUN_Size"]:
        safety_lun = float(safety_values[config_model]["LUN_Size"])
        safety_capacity = float(safety_values[config_model]["Capacity"])
        if config_size_str.endswith("TB"):
            suffix = "TB"
        else:
            suffix = "TiB"
        config_size = float(config_size_str.removesuffix(suffix))
        check_result = config_size * safety_capacity > safety_lun
        if not check_result:
            logger.debug(
                "Config: %s, Max Capacity Utilization: %s, LUN Size for Flex appliance: %s",
                config,
                safety_capacity,
                safety_lun,
            )
    return check_result


def get_selected_models(sheet):
    heading, *app_data = sheet.used_range.options(numbers=int).value
    col_model = heading.index("Model")
    col_visible = heading.index("Visible")
    return set(row[col_model] for row in app_data if row[col_visible] == 1)


def excel_to_slp(sheet, parser=SHEET_STORAGE_LIFECYCLE_POLICIES_MAP, return_as=SLP):
    last_col = sheet.used_range.columns.count
    last_row = sheet.used_range.rows.count
    dataset = sheet.range((1, 1), (last_row, last_col)).value

    slp_list = []
    for row_num in range(1, last_row):
        slp = row_to_slp(dataset, row_num, parser, return_as)
        if slp:
            slp_list.append(slp)
    return slp_list


def excel_to_window(sheet, return_as=WINDOW_SIZE):
    windows_dict = {}
    col_end_index = sheet.used_range.columns.count
    col_header = sheet.range((1, 1), (1, col_end_index))
    row_last_index = sheet.used_range.rows.count
    for row_current_index in range(2, row_last_index + 1):
        excel_row = row_to_dict(sheet, col_header, row_current_index, col_end_index)
        windows_dict[SHEET_WINDOWS_MAP[excel_row["Operation"]]] = int(
            excel_row["Time (hours per week)"]
        )
        row_current_index += 1

    if (
        windows_dict["incremental_backup"]
        + windows_dict["full_backup"]
        + windows_dict["replication"]
        > constants.HOURS_PER_WEEK
    ):
        raise BadInputError(
            "Sum of operation windows exceeded the total hours in a week."
        )

    if return_as is WINDOW_SIZE:
        return utils.WindowSize(
            full_backup_hours=windows_dict["full_backup"],
            incremental_backup_hours=windows_dict["incremental_backup"],
            replication_hours=windows_dict["replication"],
        )
    elif return_as is OBJECT:
        return windows_dict


def excel_to_workload(
    sheet,
    timeframe,
    slp_list,
    excess_cloud_factor,
    parser=SHEET_WORKLOADS_MAP,
    return_as=WORKLOAD,
):
    last_col = sheet.used_range.columns.count
    last_row = sheet.used_range.rows.count
    dataset = sheet.range((1, 1), (last_row, last_col)).value

    workloads_list = []
    workload_names = collections.defaultdict(list)

    indexed_slps = {}
    for slp in slp_list:
        slp_name = slp["storage_lifecycle_policy"]
        indexed_slps[slp_name] = slp

    for row_num in range(1, last_row):
        wk = row_to_workload(
            dataset,
            row_num,
            indexed_slps,
            parser,
            return_as,
        )
        if wk:
            if return_as is WORKLOAD:
                wk.calculate_capacity(timeframe, excess_cloud_factor)
                workload_names[wk.name].append({"row": row_num + 1, "workload": wk})
            workloads_list.append(wk)

    if return_as is not WORKLOAD:
        return workloads_list

    for wk_name, wk_info in workload_names.items():
        if len(wk_info) == 1:
            continue
        for wk in wk_info:
            cur_name = wk["workload"].name
            new_name = new_name_base = f"{cur_name}@A{wk['row']}"
            addl_idx = 0
            while new_name in workload_names:
                new_name = f"{new_name_base}+{addl_idx}"
                addl_idx += 1
            logger.info("changing workload name from %s to %s", cur_name, new_name)
            wk["workload"].name = new_name

    return workloads_list


def read_settings(book):
    data = book.names["settings"].refers_to_range.value
    return settings.Settings.from_list(data)


def read_timeframe(book):
    return read_settings(book).timeframe


def read_excess_cloud_factor(book):
    return read_settings(book).worst_case_cloud_factor


def read_timeframe_21(book):
    sheet = book.sheets[VARIABLES_SHEET]
    num_years = sheet.range("sizing_first_extension").value
    planning_year = sheet.range("sizing_time_frame").value
    return utils.TimeFrame(num_years=num_years, planning_year=planning_year)


@timers.record_time("post sizing")
def post_sizing(book):
    for vba_fn in ["freeze_sheet_header", "create_nav_buttons", "format_named_ranges"]:
        book.macro(vba_fn)()


class ExcelLogHandler(logging.Handler):
    def __init__(self, sheet, max_batch_size=500):
        logging.Handler.__init__(self)
        self.sheet = sheet
        self.sheet.clear_contents()
        self.sheet.range("A1").value = [
            "Timestamp",
            "Level",
            "Logger",
            "Message",
            "Backtrace",
        ]
        self.row = 2
        self.batch = []
        self.max_batch_size = max_batch_size

    def setFormatter(self, fmt):
        self.formatter = fmt

    def splitMsg(self, msg, max_msg_length):
        return [
            msg[0 + i : max_msg_length + i] for i in range(0, len(msg), max_msg_length)
        ]

    def emit(self, record):
        MAX_MSG_CHARS = 32000
        msg = self.splitMsg(record.getMessage(), MAX_MSG_CHARS)
        for i, part_msg in enumerate(msg):
            row_content = [
                "",
                "",
                "",
                f"{package_version.package_product_name}-{package_version.package_version}: "
                + part_msg,
                "",
            ]
            if i == 0:
                # first part has timestamp and level, subsequent parts
                # only have message
                row_content[0:3] = [
                    self.formatter.formatTime(record),
                    record.levelname,
                    record.name,
                ]
                if record.exc_info:
                    exc_message = self.formatter.formatException(record.exc_info)
                    row_content[4] = exc_message

            self.batch.append(row_content)
        flush_now = bool(record.exc_info)
        if flush_now or len(self.batch) >= self.max_batch_size:
            self.flush()

    def flush(self):
        if not self.batch:
            return
        self.sheet.range(f"A{self.row}").value = self.batch
        self.row += len(self.batch)
        self.batch = []


def setup_logging(logs_sheet):
    handler = ExcelLogHandler(logs_sheet)
    formatter = logging.Formatter(fmt="%(message)s")
    handler.setFormatter(formatter)
    handler.setLevel(logging.DEBUG)

    for logger_name in ["use_xl", "use_core"]:
        logger = logging.getLogger(logger_name)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

    return handler


def stop_logging(handler):
    handler.flush()

    for logger_name in ["use_xl", "use_core"]:
        logger = logging.getLogger(logger_name)
        logger.removeHandler(handler)


def log_times(time_ctx):
    for event, duration in time_ctx.report():
        logger.info("event: %s, time %s seconds", event, duration)


def main(progress_reporting=True, appliance_family=constants.ApplianceFamily.NBA):
    bk_vupc = xw.Book.caller()

    logs_sheet = get_sheet(bk_vupc, LOGS_SHEET, clear_contents=False)
    log_handler = setup_logging(logs_sheet)
    try:
        do_main(bk_vupc, progress_reporting, appliance_family)
    except Exception as ex:
        logger.exception(ex)
        report_error = bk_vupc.macro("show_message")
        report_error(str(ex), MESSAGE_ERROR_TEXT)

    stop_logging(log_handler)


def do_main(bk_vupc, progress_reporting, appliance_family):
    time_ctx = timers.TimerContext()

    sizing_flex = appliance_family.sizing_flex()

    time_ctx.start("reading data")
    raw_sheet = get_sheet(bk_vupc, RAW_SHEET)
    raw_flex_sheet = get_sheet(bk_vupc, RAW_FLEX_SHEET)
    site_summary_sheet = get_sheet(bk_vupc, SITE_SUMMARY_SHEET)
    workload_assignment_sheet = get_sheet(bk_vupc, WORKLOAD_ASSIGNMENT_SHEET)
    workload_assignment_flex_sheet = get_sheet(bk_vupc, WORKLOAD_ASSIGNMENT_FLEX_SHEET)
    variables_sheet = get_sheet(bk_vupc, VARIABLES_SHEET, clear_contents=False)
    master_summary_sheet = get_sheet(bk_vupc, MASTER_SUMMARY_SHEET)
    error_note_sheet = get_sheet(bk_vupc, ERRORS_AND_NOTES_SHEET, clear_contents=True)

    # avoid sheet.activate() which causes permission errors on macOS
    bk_vupc.macro("activate_sheet")(SITE_SUMMARY_SHEET)

    if progress_reporting:
        # test runs disable screen updating to make things a little
        # faster.  The activate_sheet macro also disables screen
        # updating to reduce screen flicker.  If progress reporting is
        # required, though, we ensure screen updates are enabled.
        bk_vupc.app.screen_updating = True
        user_message = bk_vupc.macro("confirm_message")

    progress_cell = site_summary_sheet.range("progress_cell")
    detail_progress_cell = site_summary_sheet.range("detail_progress_cell")

    def report_progress(status, detail=None):
        if not progress_reporting:
            return
        if status is None:
            detail_progress_cell.value = detail
        else:
            progress_cell.value = [[f"In progress: {status}..."], [detail]]

    def query_user(message):
        if not progress_reporting:
            return
        result = user_message(message)
        if not result:
            raise packing.UserCancel(packing.GENERIC_ERROR_TEXT)

    # The Summary sheet needs special handling since it contains
    # widgets that much not be deleted.  Clear only the data area.
    appliance_summary_sheet = get_sheet(
        bk_vupc, APPLIANCE_SUMMARY_SHEET, clear_contents=False
    )

    workload_summary_sheet = get_sheet(bk_vupc, WORKLOAD_SUMMARY_SHEET)

    raw_appliance_summary_sheet = get_sheet(bk_vupc, RAW_APPLIANCE_SUMMARY_SHEET)

    # holds the data used by the chart on Results page
    appliance_usage_chart_data_sheet = get_sheet(
        bk_vupc, APPLIANCE_USAGE_CHART_DATA_SHEET
    )

    report_progress("Reading workloads and site assignments")

    settings = read_settings(bk_vupc)

    timeframe = settings.timeframe
    per_appliance_safety_margins = excel_to_per_model_safety(
        bk_vupc.sheets[SAFETY_SHEET]
    )

    slp_list = excel_to_slp(bk_vupc.sheets[STORAGE_LIFECYCLE_POLICIES_SHEET])
    window_sizes = excel_to_window(bk_vupc.sheets[OPERATION_WINDOWS_SHEET])
    workload_list = excel_to_workload(
        bk_vupc.sheets[WORKLOADS_SHEET],
        timeframe,
        slp_list,
        settings.worst_case_cloud_factor,
    )
    sheet = bk_vupc.sheets[SKU_SHEET]
    visible_models = get_selected_models(sheet)

    if not workload_list:
        raise MissingWorkloadsError("No workloads provided for sizing")
    site_assignment_list = excel_to_site_assignment(
        bk_vupc.sheets[SITE_ASSIGNMENTS_SHEET],
        workload_list,
        timeframe.planning_year,
        sizing_flex,
        per_appliance_safety_margins,
    )

    if not site_assignment_list:
        raise MissingSitesError("No sites on sites sheet")
    time_ctx.stop("reading data")

    appliance_selection_criteria = packing.ApplianceSelectionCriteria(
        site_assignment_list, visible_models, per_appliance_safety_margins
    )

    try:
        with time_ctx.record("sizing"):
            calculate_capacity_all_workloads(
                workload_list, settings.timeframe, settings.worst_case_cloud_factor
            )

            mctx = packing.SizerContext(
                appliance_selection_criteria,
                workloads=workload_list,
                window_sizes=window_sizes,
                progress_cb=report_progress,
                message_cb=query_user,
                timer_ctx=time_ctx,
                pack_flex=sizing_flex,
                sizer_settings=settings,
            )
        mresult = mctx.pack(retry_on_error=True)
        workload_storage_usage = workload.storage_usage(workload_list, timeframe)
        write_results(
            time_ctx,
            mresult,
            bk_vupc,
            raw_sheet,
            raw_flex_sheet,
            report_progress,
            workload_assignment_sheet,
            workload_assignment_flex_sheet,
            appliance_summary_sheet,
            workload_summary_sheet,
            raw_appliance_summary_sheet,
            variables_sheet,
            appliance_usage_chart_data_sheet,
            master_summary_sheet,
            error_note_sheet,
            per_appliance_safety_margins,
            site_summary_sheet,
            workload_list,
            workload_storage_usage,
            appliance_family,
            settings,
        )

        if appliance_family == constants.ApplianceFamily.FlexScale:
            bk_vupc.macro("activate_sheet")(FLEX_SCALE_RESULTS_SHEET)
    except packing.PackingAllWorkloadsError as err:
        with time_ctx.record("writing write_error_and_note_sheet"):
            write_errors_and_notes(error_note_sheet, err.workload_error_list, [], None)
            bk_vupc.macro("activate_sheet")(ERRORS_AND_NOTES_SHEET)
            raise packing.PackingError(
                f"Sizing failed. Refer to the {ERRORS_AND_NOTES_SHEET} sheet for details."
            )


def maybe_write_flexscale_results(
    time_ctx, bk_vupc, mresult, workload_storage_usage, appliance_family
):
    if appliance_family != constants.ApplianceFamily.FlexScale:
        return
    flexscale.write_flex_scale_data(
        bk_vupc.sheets[FLEX_SCALE_DATA_SHEET],
        mresult,
        workload_storage_usage,
        time_ctx=time_ctx,
    )
    flexscale.write_flex_scale_totals(
        bk_vupc.sheets[FLEX_SCALE_TOTALS_SHEET],
        mresult,
        time_ctx=time_ctx,
    )
    flexscale.write_flex_scale_results(
        bk_vupc.sheets[FLEX_SCALE_RESULTS_SHEET],
        mresult,
        time_ctx=time_ctx,
    )


def write_results(
    time_ctx,
    mresult,
    bk_vupc,
    raw_sheet,
    raw_flex_sheet,
    report_progress,
    workload_assignment_sheet,
    workload_assignment_flex_sheet,
    appliance_summary_sheet,
    workload_summary_sheet,
    raw_appliance_summary_sheet,
    variables_sheet,
    appliance_usage_chart_data_sheet,
    master_summary_sheet,
    error_note_sheet,
    per_appliance_safety_margins,
    site_summary_sheet,
    workload_list,
    workload_storage_usage,
    appliance_family,
    settings,
):
    sizing_flex = appliance_family.sizing_flex()

    error_message = set()
    if mresult.workload_error_list:
        error_message.add(WorkloadErrorType.media_skip)
    if mresult.primary_errors:
        error_message.add(WorkloadErrorType.master_skip)
    if mresult.domains_split:
        error_message.add(WorkloadErrorType.domains_split)

    with time_ctx.record("writing results"):
        report_progress("Writing results")
        if sizing_flex:
            write_raw_flex(
                raw_flex_sheet,
                mresult,
                workload_list,
                settings.resource_tip,
                time_ctx=time_ctx,
            )
            write_site_summary_flex(
                site_summary_sheet,
                variables_sheet,
                mresult,
                per_appliance_safety_margins,
                error_message,
                time_ctx=time_ctx,
            )
            write_workload_assignment_flex(
                workload_assignment_flex_sheet, mresult, time_ctx=time_ctx
            )
            write_appliance_summary_flex(
                appliance_summary_sheet,
                mresult,
                workload_storage_usage,
                time_ctx=time_ctx,
            )
            write_chart_data(
                appliance_usage_chart_data_sheet, mresult, time_ctx=time_ctx
            )
            write_raw_appliance_summary_flex(
                raw_appliance_summary_sheet, mresult, time_ctx=time_ctx
            )

            bk_vupc.macro("hide_sheet")(MASTER_SUMMARY_SHEET)
        else:
            write_raw(raw_sheet, mresult, workload_list, time_ctx=time_ctx)
            write_site_summary(
                site_summary_sheet,
                variables_sheet,
                mresult,
                per_appliance_safety_margins,
                error_message,
                time_ctx=time_ctx,
            )
            write_management_server_summary(
                master_summary_sheet, mresult, time_ctx=time_ctx
            )
            write_workload_assignment(
                workload_assignment_sheet,
                mresult,
                settings.resource_tip,
                time_ctx=time_ctx,
            )
            write_appliance_summary(
                appliance_summary_sheet,
                mresult,
                workload_storage_usage,
                time_ctx=time_ctx,
            )
            write_chart_data(
                appliance_usage_chart_data_sheet, mresult, time_ctx=time_ctx
            )
            bk_vupc.macro("unhide_sheet")(MASTER_SUMMARY_SHEET)
            write_raw_appliance_summary(
                raw_appliance_summary_sheet, mresult, time_ctx=time_ctx
            )
        maybe_write_flexscale_results(
            time_ctx, bk_vupc, mresult, workload_storage_usage, appliance_family
        )
        write_workload_summary(workload_summary_sheet, mresult, time_ctx=time_ctx)

    post_sizing(bk_vupc, time_ctx=time_ctx)
    log_times(time_ctx)

    workload_domain_change_list = []
    if mresult.domains_split:
        for wk in workload_list:
            if not wk.domain_adjusted:
                continue
            note_text = WORKLOAD_DOMAIN_CHANGE_TEXT.format(
                workload_name=wk.name,
                orig_domain_name=wk.orig_domain,
                new_domain_name=wk.domain,
            )
            workload_domain_change_list.append(
                [wk.name, note_text, wk.domain, "Workload Domain Change"]
            )

    if error_message:
        write_errors_and_notes(
            error_note_sheet,
            mresult.workload_error_list,
            workload_domain_change_list,
            mresult.primary_errors,
        )
        if mresult.domains_split or mresult.primary_errors:
            bk_vupc.macro("activate_sheet")(ERRORS_AND_NOTES_SHEET)
        if mresult.workload_error_list:
            bk_vupc.macro("activate_sheet")(ERRORS_AND_NOTES_SHEET)
            exc_message = build_summary_error_message(error_message)
            raise packing.NotifyWorkloadError(exc_message)


def excel_to_appliance_needed(sheet):
    """
    Inputs: sheet
    Output: List of dictionary [{},{}]
    """
    appliance_needed_arr = []
    col_end_index = sheet.used_range.columns.count
    col_header = sheet.range(("A3:C3"))
    row_last_index = sheet.used_range.rows.count

    for row_current_index in range(2, row_last_index + 1):
        excel_row = row_to_dict(sheet, col_header, row_current_index, col_end_index)
        appliance_needed_arr.append(excel_row)

    return appliance_needed_arr[2:]
