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

import glob
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

json_folder = "json_test_data"
schema_folder = "json_data"


def base_folder(folder):
    if folder in ("schemas", "example_responses"):
        return schema_folder
    return json_folder


def save_data(folder, file, data):
    dest_folder = base_folder(folder) + "/" + folder
    os.makedirs(dest_folder, exist_ok=True)

    dest_file = dest_folder + "/" + file + ".json"
    with open(dest_file, "w") as outfile:
        json.dump(data, outfile)


def delete_data(folder, file):
    dest_folder = base_folder(folder) + "/" + folder
    dest_file = dest_folder + "/" + file + ".json"

    if os.path.exists(dest_file):
        os.remove(dest_file)
    else:
        raise Exception("The file to be deleted does not exist")


def get_data(folder, file):
    dest_folder = base_folder(folder) + "/" + folder
    dest_file = dest_folder + "/" + file + ".json"

    with open(dest_file) as json_file:
        response = json.load(json_file)
    return response


def get_all_data(folder):
    dest_folder = base_folder(folder) + "/" + folder
    all_jsons = glob.glob(dest_folder + "/*.json")

    response_arr = []
    for each_json in all_jsons:
        dest_file = each_json
        with open(dest_file) as json_file:
            response = json.load(json_file)
            response_arr.append(response)

    return response_arr


def list_all_data(folder):
    dest_folder = base_folder(folder) + "/" + folder
    for f in glob.glob(dest_folder + "/*.json"):
        return [
            os.path.splitext(os.path.basename(f))[0]
            for f in glob.glob(dest_folder + "/*.json")
        ]


def get_uri(folder, file):
    return (
        Path("/".join([base_folder(folder), folder, file + ".json"])).resolve().as_uri()
    )
