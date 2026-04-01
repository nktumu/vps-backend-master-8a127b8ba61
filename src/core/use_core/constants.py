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
import enum

# RunInfo constants
WORKLOAD_TYPES = ("default", "vmware", "ma_cc", "ma_msdp_cc", "master")
PRIMARY_MEMORY_OVERHEAD = 32494816
PRIMARY_MEMORY_USAGE = 12
SEQUENTIAL_WRITE_IO = 64

# Access Appliance hardware
ACCESS_APPLIANCE_MEMORY = "768GiB"

# Packing timeouts
MIN_SOLVER_TIMEOUT = 15
ITEM_CHUNK_SIZE = 10000
CHUNK_TIME = 5
TIMEOUT_SCALING = 2

FLEX_CHUNK_SIZE = 50
FLEX_CHUNK_TIME = 100

# Handy constants
WEEKS_PER_YEAR = 52
MONTHS_PER_YEAR = 12
DAYS_PER_WEEK = 7
HOURS_PER_WEEK = 24 * 7
MINUTES_PER_WEEK = 60 * 24 * 7
MINUTES_PER_DAY = 60 * 24
SECONDS_PER_HOUR = 60 * 60
FILES_PER_HOUR = 130_000_000
USE_PATH = "../vps-backend/src/main/python/USE-1.0.xlsm"

# defaults for horizons
FIRST_EXTENSION = 5
PLANNING_YEAR = 3

# fudge factors
EXTRA_CPU_TIME = 1
FUDGE_CPU_MAX = 0.8
FUDGE_IOPS_MAX = 0.8
FUDGE_NW_MAX = 0.8

# defaults for software safety
CONCURRENT_STREAMS = 8
JOBS_PER_DAY = 1000
MAXIMUM_FILES = None
MAXIMUM_IMAGES = None
NO_OF_IMAGES = 10000
VM_CLIENTS = 100

# default for universal share
MAXIMUM_FILES_PER_UNIVERSAL_SHARE = 5000000
MAXIMUM_NUMBER_OF_UNIVERSAL_SHARE = 50

# default workload attributes requirement
NO_SUPPORT_CLIENT_DEDUP = ["NDMP"]
NO_SUPPORT_INCR_BACKUP_WORKLOAD_TYPES = ["PostgreSQL"]
INCR_BACKUP_ADJUST_WORKLOAD_TYPES = [
    "File System (Large Files)",
    "File System (Small Files)",
    "File System (Typical)",
    "Image Files",
    "NDMP (Large Files)",
    "NDMP (Small Files)",
    "NDMP (Typical)",
    "VMware",
]

MAX_FILES_FOR_WORKLOAD_TYPE = {"Oracle": 65533}

# IOPS contributed by each additional disk
ADDL_DISK_IOPS_SCALE = 0

# bandwidth defaults
DEFAULT_CC_BW = 1.6  # gbps

# Site Assignment constants
MASTER_MODEL_PREFERENCES = {"5240": 2, "5250": 1}
MASTER_PREFERRED_MODEL = "5250"
DEFAULT_MASTER_CONFIG = "5250 9TB_Capacity 0_Shelves 64_RAM  4x1GbE 2x10GbE_SFP"
PRIMARY_CONFIGS = {
    "5150": "5150 15TB_Capacity 0_Shelves 64_RAM  4x1GbE 2x10GbE_SFP",
}

DEFAULT_DOMAIN_NAME = "Domain-X"

BACKUP_LOCATIONS = ["Local Only", "Local+DR", "Local+DR+LTR", "Local+LTR", "LTR Only"]
VISIBLE_BACKUP_LOCATIONS = ["Local Only", "Local+DR"]


# Software version constants


class SoftwareVersion(enum.Enum):
    VER8_2 = "8.2"
    VER8_3 = "8.3"
    VER9_0 = "9.0"


DEFAULT_SOFTWARE_VERSION = SoftwareVersion.VER9_0
DEFAULT_SOFTWARE_VERSION_STRING = DEFAULT_SOFTWARE_VERSION.name

# Excel UI constants
FIRST_ROW_HEIGHT = 98
FIRST_ROW_FILL = (142, 169, 219)
ERROR_FIRST_ROW_FILL = (177, 23, 29)
NOTE_FIRST_ROW_FILL = (255, 153, 51)

# RGB assignments for by-year display, currently only used on "Appliance Summary" page.
SUMMARY_COMMON_COLOR = (217, 225, 242)
BY_YEAR_RGB = [
    (169, 208, 142),
    (142, 169, 219),
    (255, 217, 102),
    (181, 131, 223),
    (255, 72, 29),
]

RESOURCE_ABSOLUTE_HEADINGS = ["Capacity (TiB)"]
RESOURCE_PERCENT_HEADINGS = [
    "Capacity (%)",
    "Allocated Capacity (TiB)",
    "Allocated Capacity (%)",
    "Memory (%)",
    "CPU (%)",
    "I/O (%)",
    "Network (%)",
]
RESOURCE_NETWORK_HEADINGS = [
    "DR-NW Transfer(Mbps)",
    "DR Transfer GiB/Week",
    "Cloud-NW Transfer(Mbps)",
    "Cloud Transfer GiB/week",
    "I/O (MB/s)",
    "",
    "",
    "",
]
STORAGE_SPACE_CALCULATION_HEADINGS = [
    "Full Backup (TiB)",
    "Incremental Backup (TiB)",
    "Size Before Deduplication (TiB)",
    "Size After Deduplication (TiB)",
    "Cloud Storage GiB-Months",
    "Worst-case\nCloud Storage GiB-Months",
    "",
    "",
]
RESOURCE_WORKLOAD_NETWORK_HEADING = [
    "Capacity Workload (TiB)",
    "Replication (Mbps)",
    "Cloud Storage GiB-Months",
    "Worst-case\nCloud Storage GiB-Months",
    "Cloud Transfer GiB/week",
    "Catalog Size (GiB)",
    "",
    "",
]
WORKLOAD_SUMMARY_ATTRIBUTES = [
    "workload_capacity",
    "nic_workload",
    "cloud_gib_months",
    "cloud_gib_months_worst_case",
    "cloud_gib_per_week",
    "Storage Primary",
    "Storage DR",
    "Storage Catalog",
    "Storage Cloud",
    "Storage Cloud Worst-Case",
    "Size Before Deduplication",
    "Total network utilization",
    "Total dr network utilization",
    "Total cloud network utilization",
    "Backup Volume",
]
WORKLOAD_SUMMARY_HEADINGS = [
    "Storage - Primary (TiB)",
    "Storage - DR (TiB)",
    "Storage - Cloud (TiB)",
    "Storage - Cloud Worst-Case (TiB)",
    "Storage Before Deduplication-Primary (TiB)",
    "Storage - Catalog (GiB)",
    "Total Network Utilization (Mbps)",
    "Total DR Network Utilization (Mbps)",
    "Total Cloud Network Utilization (Mbps)",
    "Cloud Storage -  GiB-Months",
    "Cloud Transfer -  GiB/Week",
    "Backup Volume - GiB/Week",
]

APPLIANCE_SUMMARY_HEADINGS = RESOURCE_ABSOLUTE_HEADINGS + RESOURCE_PERCENT_HEADINGS
RAW_APPLIANCE_SUMMARY_HEADINGS = (
    RESOURCE_ABSOLUTE_HEADINGS
    + RESOURCE_PERCENT_HEADINGS
    + RESOURCE_NETWORK_HEADINGS[:5]
    + STORAGE_SPACE_CALCULATION_HEADINGS[:6]
)
RAW_APPLIANCE_SUMMARY_ATTRIBUTES = [
    "absolute_capacity",
    "alloc_capacity",
    "alloc_capacity_pct",
    "nic_dr",
    "DR Transfer GiB/Week",
    "nic_cloud",
    "Cloud Transfer GiB/week",
    "Cloud Minimum Bandwidth(Mbps)",
    "absolute_io",
    "Full Backup",
    "Incremental Backup",
    "Size Before Deduplication",
    "Size After Deduplication",
    "cloud_gib_months",
    "cloud_gib_months_worst_case",
]
ACCESS_SUMMARY_HEADINGS = [
    "Capacity (TiB)",
    "Capacity (%)",
    "",
    "",
    "",
    "",
    "",
    "",
]

CONTAINER_SUMMARY_HEADINGS = [
    "Capacity (TiB)",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
]

MASTER_SUMMARY_HEADINGS = [
    "Capacity (GiB)",
    "CPU (%)",
    "Memory (%)",
    "Files",
    "Images",
    "Jobs/day",
    None,
    None,
]

assert len(APPLIANCE_SUMMARY_HEADINGS) == len(RESOURCE_WORKLOAD_NETWORK_HEADING)
assert len(APPLIANCE_SUMMARY_HEADINGS) == len(RESOURCE_NETWORK_HEADINGS)
assert len(APPLIANCE_SUMMARY_HEADINGS) == len(STORAGE_SPACE_CALCULATION_HEADINGS)
assert len(APPLIANCE_SUMMARY_HEADINGS) == len(ACCESS_SUMMARY_HEADINGS)
assert len(APPLIANCE_SUMMARY_HEADINGS) == len(CONTAINER_SUMMARY_HEADINGS)
assert len(APPLIANCE_SUMMARY_HEADINGS) == len(MASTER_SUMMARY_HEADINGS)

CHARTED_APPLIANCE_SUMMARY_HEADINGS = [
    "Capacity",
    "Memory",
    "CPU",
    "I/O",
    "Network",
    "Allocated_Capacity",
]

# Master server sizes
MANAGEMENT_SERVER_DESIGNATION = "Primary Server"
MANAGEMENT_SERVER_DESIGNATION_PREVIOUS = "Master Server"
CATALOG_PER_FILE = 132
CATALOG_FIXED = "30MiB"

TIMESTAMP_2_1 = datetime.date(2020, 6, 5)
TIMESTAMP_2_1_p1 = datetime.date(2020, 9, 28)
TIMESTAMP_3_0_pre6 = datetime.date(2020, 9, 30)
TIMESTAMP_3_0_pre7 = datetime.date(2020, 11, 6)
TIMESTAMP_3_0_pre8 = datetime.date(2020, 11, 17)
TIMESTAMP_3_0_pre9 = datetime.date(2020, 11, 25)
TIMESTAMP_3_0_pre10 = datetime.date(2020, 12, 9)
TIMESTAMP_3_0_pre11 = datetime.date(2020, 12, 17)
TIMESTAMP_3_0_pre12 = datetime.date(2021, 1, 21)
TIMESTAMP_3_0_rc1 = datetime.date(2021, 2, 2)
TIMESTAMP_3_0_rc2 = datetime.date(2021, 2, 11)
TIMESTAMP_3_0_rc3 = datetime.date(2021, 2, 25)
TIMESTAMP_3_0_rc4 = datetime.date(2021, 3, 19)
TIMESTAMP_3_0 = datetime.date(2021, 3, 29)
TIMESTAMP_3_0_patch1 = datetime.date(2021, 4, 1)
TIMESTAMP_3_0_patch2 = datetime.date(2021, 4, 8)
TIMESTAMP_3_1_rc1 = datetime.date(2021, 4, 30)
TIMESTAMP_3_1_rc2 = datetime.date(2021, 5, 12)
TIMESTAMP_3_1 = datetime.date(2021, 5, 17)
TIMESTAMP_3_1_patch1 = datetime.date(2021, 5, 25)
TIMESTAMP_3_1_patch2 = datetime.date(2021, 6, 1)
TIMESTAMP_3_1_patch3 = datetime.date(2021, 6, 16)
TIMESTAMP_3_1_patch4 = datetime.date(2021, 6, 22)
TIMESTAMP_3_1_patch5 = datetime.date(2021, 7, 9)
TIMESTAMP_3_1_patch6 = datetime.date(2021, 7, 30)
TIMESTAMP_4_0_rc1 = datetime.date(2021, 9, 7)
TIMESTAMP_4_0 = datetime.date(2021, 9, 17)
TIMESTAMP_4_0_patch1 = datetime.date(2021, 10, 22)
TIMESTAMP_4_0_patch2 = datetime.date(2021, 11, 29)
TIMESTAMP_4_0_patch3 = datetime.date(2021, 12, 17)
TIMESTAMP_4_1_rc1 = datetime.date(2022, 2, 4)
TIMESTAMP_4_1_rc2 = datetime.date(2022, 3, 12)
TIMESTAMP_4_1_rc3 = datetime.date(2022, 3, 28)
TIMESTAMP_4_1_rc4 = datetime.date(2022, 4, 1)
TIMESTAMP_4_1 = datetime.date(2022, 4, 11)
TIMESTAMP_4_1_patch1 = datetime.date(2022, 4, 25)
TIMESTAMP_4_1_patch2 = datetime.date(2022, 6, 3)
TIMESTAMP_4_1_patch3 = datetime.date(2022, 6, 9)
TIMESTAMP_4_1_patch4 = datetime.date(2022, 7, 8)
TIMESTAMP_4_1_patch5 = datetime.date(2022, 8, 3)
TIMESTAMP_4_1_patch6 = datetime.date(2022, 8, 31)
TIMESTAMP_4_1_patch7 = datetime.date(2023, 1, 25)
TIMESTAMP_4_1_patch8 = datetime.date(2023, 3, 15)
TIMESTAMP_4_1_patch9 = datetime.date(2023, 7, 7)
TIMESTAMP_4_1_patch10 = datetime.date(2023, 7, 21)
TIMESTAMP_4_1_patch11 = datetime.date(2024, 1, 2)
TIMESTAMP_4_1_patch12 = datetime.date(2024, 10, 18)
TIMESTAMP_4_1_patch13 = datetime.date(2025, 9, 9)

# Flex appliance constants
MAXIMUM_CONTAINERS = 6
MEMORY_SHARING_DISCOUNT = 0.7  # effect of shared memory across media server instances
MEDIA_ROUNDUP_TIB = 80  # round up media storage requirement to avoid LUN sharing
MSDP_CLOUD_MAX_FILESIZE_MB = 64
MSDP_CLOUD_MAX_CACHE_PCT = 0.5
MSDP_CLOUD_MIN_LSU_TB = 1  # minimum LSU size on a media server
MSDP_CLOUD_TOTAL_LSU_PB = 1  # total size across all LSUs on a media server for Access
MSDP_CLOUD_TOTAL_LSU_PB_RV = (
    2.4  # total size across all LSUs on a media server for Recovery Vault
)
MSDP_CLOUD_WORST_CASE_FACTOR = 0.3  # default excess space required for msdp-c

# Modified/split default workload attributes map
REMAPPED_WORKLOAD_TYPES = {
    "File System": "File System (Typical)",
    "NDMP": "NDMP (Typical)",
}

DEFAULT_APPLIANCE_FAMILY = "flex"
DEFAULT_SITE_NETWORK_TYPE = "10GbE SFP"

DEFAULT_WORKLOAD_ISOLATION = False
DEFAULT_UNIVERSAL_SHARE = False

DEFAULT_INCREMENTAL_RETENTION = 30
DEFAULT_WEEKLY_FULL_RETENTION = 4
DEFAULT_MONTHLY_FULL_RETENTION = 6
DEFAULT_ANNUAL_FULL_RETENTION = 0

DEFAULT_FULLS_PER_WEEK = 1
DEFAULT_INCREMENTALS_PER_WEEK = 5
DEFAULT_LOG_BACKUP_INTERVAL = 15

# Flexscale constants

FLEXSCALE_MODELS = ["14 TB Gen10", "16 TB Gen11", "20 TB Gen11"]


class ApplianceFamily(enum.Enum):
    NBA = enum.auto()
    Flex = enum.auto()
    FlexScale = enum.auto()

    def sizing_flex(self):
        return self in (ApplianceFamily.Flex, ApplianceFamily.FlexScale)
