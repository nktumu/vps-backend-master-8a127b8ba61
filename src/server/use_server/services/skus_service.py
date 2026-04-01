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

entity_type = "skus"

REQUIRED_SKU_KEYS = set(
    [
        "name",
        "model",
        "io_config",
        "shelves",
        "calculated_capacity",
        "capacity",
        "number_of_appliance_drives",
        "drives_per_shelf",
        "number_of_shelf_drives",
        "number_of_total_drives",
        "number_of_calculated_drives",
        "drive_size",
        "memory",
        "one_gbe",
        "ten_gbe_copper",
        "ten_gbe_sfp",
        "eight_gbfc",
        "sixteen_gbfc",
    ]
)
REQUIRED_SIZE_KEYS = set(["value", "unit"])
REQUIRED_COUNT_IO_KEYS = set(["count", "io"])


def is_valid_request(req_data):
    if "add" in req_data:
        if len(req_data["add"]) > 0:
            for each in req_data["add"]:
                return (
                    set(each) == REQUIRED_SKU_KEYS
                    and set(each["calculated_capacity"]) == REQUIRED_SIZE_KEYS
                    and set(each["capacity"]) == REQUIRED_SIZE_KEYS
                    and set(each["drive_size"]) == REQUIRED_SIZE_KEYS
                    and set(each["memory"]) == REQUIRED_SIZE_KEYS
                    and set(each["one_gbe"]) == REQUIRED_COUNT_IO_KEYS
                    and set(each["ten_gbe_copper"]) == REQUIRED_COUNT_IO_KEYS
                    and set(each["ten_gbe_sfp"]) == REQUIRED_COUNT_IO_KEYS
                    and set(each["eight_gbfc"]) == REQUIRED_COUNT_IO_KEYS
                    and set(each["sixteen_gbfc"]) == REQUIRED_COUNT_IO_KEYS
                )

    if "remove" in req_data:
        if len(req_data["remove"]) > 0:
            for each in req_data["remove"]:
                if each is None:
                    return False
    return True


def get_skus(model, io_config):
    models = []
    if model is not None:
        models = model.split(",")

    io_configs = []
    if io_config is not None:
        io_configs = io_config.split(",")
    try:
        all_skus = json_service.get_all_data(entity_type)
        filtered_skus = []
        for each_sku in all_skus:
            if model is not None and len(model) > 0:
                for each_model in models:
                    print("--Each Model----")
                    print(each_model)
                    if each_sku["model"] == each_model:
                        filtered_skus.append(each_sku)
            else:
                filtered_skus.append(each_sku)

        for each_sku in filtered_skus:
            for each_io_config in io_configs:
                if each_sku["io_config"] != each_io_config:
                    filtered_skus.remove(each_sku)

        return filtered_skus
    except Exception:
        return None


def add_remove_sku(sku_update):
    if "add" in sku_update:
        for new_sku in sku_update["add"]:
            resp = create_update_sku(new_sku["name"], new_sku)
            if resp is None:
                return None

    if "remove" in sku_update:
        for remove_sku in sku_update["remove"]:
            del_resp = delete_sku(remove_sku)
            if del_resp is None:
                return None

    return True


def create_update_sku(sku_name, sku_data):
    try:
        json_service.save_data(entity_type, sku_name, sku_data)
        return True
    except Exception:
        return None


def delete_sku(sku_name):
    try:
        json_service.delete_data(entity_type, sku_name)
        return True
    except Exception:
        return None
