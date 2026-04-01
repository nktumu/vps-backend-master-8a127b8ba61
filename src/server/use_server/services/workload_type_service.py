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

import logging

from . import json_service


logger = logging.getLogger(__name__)

entity_type = "workload_types"

REQUIRED_WORKLOAD_TYPE_KEYS = set(
    [
        "name",
        "annual_growth_rate",
        "daily_change_rate",
        "initial_dedup_rate",
        "dedup_rate",
        "addl_full_dedup_rate",
        "num_files",
        "num_channels",
        "files_per_channel",
        "log_backup_capable",
    ]
)


def is_valid_request(req_data):
    return set(req_data) == REQUIRED_WORKLOAD_TYPE_KEYS


def create_update_workload_type(workload_type_name, workload_type_data):
    try:
        json_service.save_data(entity_type, workload_type_name, workload_type_data)
        return True
    except Exception:
        return None


def delete_workload_type(workload_type_name):
    try:
        json_service.delete_data(entity_type, workload_type_name)
        return True
    except Exception:
        return None


def get_workload_types():
    try:
        return json_service.get_all_data(entity_type)
    except Exception:
        return None


def get_workload_type(workload_type_name):
    try:
        return json_service.get_data(entity_type, workload_type_name)
    except Exception:
        return None
