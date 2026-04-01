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

entity_type = "slps"

REQUIRED_SLP_KEYS = set(
    [
        "name",
        "site_name",
        "dr_dest",
        "backup_type",
        "local_retention",
        "dr_retention",
        "cloud_retention",
        "backup_intervals",
    ]
)
REQUIRED_RETENTION_KEYS = set(
    ["incremental", "weekly_full", "monthly_full", "annual_full"]
)
REQUIRED_BACKUP_KEYS = set(
    ["fulls_per_week", "incrementals_per_week", "log_backup_interval"]
)


def is_valid_request(req_data):
    return (
        set(req_data) == REQUIRED_SLP_KEYS
        and set(req_data["local_retention"]) == REQUIRED_RETENTION_KEYS
        and set(req_data["dr_retention"]) == REQUIRED_RETENTION_KEYS
        and set(req_data["cloud_retention"]) == REQUIRED_RETENTION_KEYS
        and set(req_data["backup_intervals"]) == REQUIRED_BACKUP_KEYS
    )


def create_update_slp(slp_name, slp_data):
    try:
        json_service.save_data(entity_type, slp_name, slp_data)
        return True
    except Exception:
        return None


def delete_slp(slp_name):
    try:
        json_service.delete_data(entity_type, slp_name)
        return True
    except Exception:
        return None


def get_slps():
    try:
        return json_service.get_all_data(entity_type)
    except Exception:
        return None


def get_slp(slp_name):
    try:
        return json_service.get_data(entity_type, slp_name)
    except Exception:
        return None
