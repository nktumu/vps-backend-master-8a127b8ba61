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
import csv
import io
import json
from typing import List, Tuple

import pkg_resources

from .appliance import get_model_values
from .utils import WindowSize

network_types = ["10GbE SFP"]

window_sizes = WindowSize(
    full_backup_hours=60,
    incremental_backup_hours=18,
    replication_hours=90,
)

default_slp_data = {
    "slp_name": "default",
    "site": "DC",
    "dr_dest": " ",
    "backup_location": "Local Only",
    "retention_local_weekly": 4,
    "retention_local_monthly": 6,
    "retention_local_annually": 0,
    "retention_local_incr": 30,
    "retention_dr_weekly": 0,
    "retention_dr_monthly": 0,
    "retention_dr_annually": 0,
    "retention_dr_incr": 0,
    "retention_cloud_weekly": 0,
    "retention_cloud_monthly": 0,
    "retention_cloud_annually": 0,
    "retention_cloud_incr": 0,
    "fulls_per_week": 1,
    "incrementals_per_week": 5,
    "incremental_level": "differential",
    "log_backup_interval": 15,
    "log_backup_level": "differential",
    "front_end_nw": "auto",
    "min_size_dup_jobs": 8,
    "max_size_dup_jobs": 100,
    "force_small_dup_jobs": 30,
    "dr_nw": "auto",
    "ltr_nw": "auto",
}

model_values = get_model_values()


def default_workload_attributes_data(profile="standard"):
    return [
        dwa_dict_to_row(d)
        for d in sorted(dwa_data(profile).items(), key=lambda dwa: dwa[0].lower())
    ]


def dwa_dict_to_row(dwa_item):
    workload_type, workload_attrs = dwa_item
    if "help" in workload_attrs:
        workload_attrs["workload_type"] = (
            workload_type,
            None,
            None,
            workload_attrs["help"],
        )
    else:
        workload_attrs["workload_type"] = workload_type
    del workload_attrs["help"]

    return workload_attrs


DWA_IGNORED_KEYS = ["accelerator", "cbt", "sfr", "help"]
# Remove below when Universal Share is ready
DWA_IGNORE_TEMP = ["universal_share"]


def dwa_data(profile):
    if profile == "standard":
        file_path = "conf/gurus/workload-attributes.json"
    else:
        file_path = f"conf/gurus/workload-attributes-{profile}.json"
    attrs_in = pkg_resources.resource_stream(__name__, file_path)
    # Uncomment below when Universal Share is ready
    # return json.load(attrs_in)

    # Remove below when Universal Share is ready
    org_data = json.load(attrs_in)
    for wtype, winfo in org_data.items():
        for key in DWA_IGNORE_TEMP:
            del winfo[key]
    return org_data


def default_workload_attributes_data_dict(profile="standard"):
    raw_data = dwa_data(profile)
    for wtype, winfo in raw_data.items():
        for key in DWA_IGNORED_KEYS:
            del winfo[key]
    return raw_data


def dwa_names(profile):
    reference_workload_attr_dict = default_workload_attributes_data_dict()
    return list(reference_workload_attr_dict.keys())


LIMITS_LABELS = {
    "Max Capacity Utilization (%)": "Capacity",
    "MSDP Max Size (TB)": "Max_Cal_Cap",
    "Max Catalog Size (TB)": "Max_Catalog_Size",
    "Max CPU Utilization (%)": "CPU",
    "Max NW Utilization (%)": "NW",
    "Max MBPs Utilization (%)": "IO",
    "Max Memory Utilization (%)": "Memory",
    "Max Jobs/Day": "Jobs_Per_Day",
    "Max DBs with 15 Min RPO": "DBs@15",
    "Max VM Clients": "VMs",
    "Max Concurrent Streams": "Streams",
    "Version": "Version",
    "Max Number of Files": "Files",
    "Max Number of Images": "Images",
    "LUN Size (TiB)": "LUN_Size",
    "Max Number of Primary Containers": "Primary_Containers",
    "Max Number of MSDP Containers": "MSDP_Containers",
    "Max Catalog Size (TB)": "Max_Catalog_Size",
    "Max Number of Universal Shares": "Max_Universal_Share",
}


# safety_margins should be set to a dictionary describing safety margins for each appliance model (as below)
# {
#     "5150": {"Capacity": 0.8, "Max_Cal_Cap": None},
#     "5240": {"Capacity": 0.8, "Max_Cal_Cap": None},
#     "5250": {"Capacity": 0.8, "Max_Cal_Cap": None},
#     "5340": {"Capacity": 0.8, "Max_Cal_Cap": 960},
#     "5340-HA": {"Capacity": 0.8, "Max_Cal_Cap": 960},
# }
def get_model_limits():
    safety_margins = {}
    for model_value in model_values:
        safety_margin = {}
        fields = model_values[model_value]
        for key, value in fields.items():
            value = value[0]
            if key not in LIMITS_LABELS:
                continue
            if value == "NA" or value is None or value == 0:
                safety_margin[LIMITS_LABELS[key]] = None
            else:
                safety_margin[LIMITS_LABELS[key]] = value
        safety_margins[model_value] = safety_margin

    return safety_margins


def get_model_data(model):
    return model_values[model]


def get_flexscale_throughput() -> List[Tuple[float, List[float]]]:
    csv_bytes = pkg_resources.resource_string(__name__, "conf/gurus/flexscale.csv")
    csv_str = csv_bytes.decode("utf-8")
    reader = csv.DictReader(io.StringIO(csv_str), dialect="excel-tab")
    data = collections.defaultdict(list)
    for row in reader:
        del row["Nodes"]
        for dedup_rate_pct, throughput in row.items():
            data[dedup_rate_pct].append(float(throughput))

    return [
        (int(dedup_rate_pct) / 100, throughputs)
        for dedup_rate_pct, throughputs in data.items()
    ]
