#!/usr/bin/env python3

# VERITAS: Copyright (c) 2023 Veritas Technologies LLC. All rights reserved.
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

import csv
import json
import sys


def main(csv_filename, json_filename):
    with open(csv_filename) as csv_stream:
        reader = csv.DictReader(csv_stream)
        new_data = list(reader)
    with open(json_filename) as json_stream:
        existing_data = json.load(json_stream)

    for cfg in new_data:
        one_gbe = int(cfg["1GbE"])
        ten_gbe_copper = int(cfg["10GbE Copper"])
        ten_gbe_sfp = int(cfg["10/25GbE SFP"])
        twentyfive_gbe_sfp = int(cfg["10/25GbE SFP"])
        eight_gbfc = int(cfg["8GbFC"])
        sixteen_gbfc = int(cfg["16GbFC"])

        capacity = {"value": cfg["Calculated Capacity"], "unit": "TiB"}

        new_appl = {
            "name": cfg["Name"],
            "model": cfg["Model"],
            "shelves": cfg["Shelves"],
            "shelf_size": {"value": "0", "unit": "TiB"},
            "capacity": capacity,
            "shelf_capacity": capacity,
            "calculated_capacity": capacity,
            "number_of_appliance_drives": "",
            "drives_per_shelf": "",
            "number_of_shelf_drives": "0",
            "number_of_total_drives": "7",
            "number_of_calculated_drives": "7",
            "drive_size": {"value": "1", "unit": "TB"},
            "memory": {"value": cfg["Memory"], "unit": "GiB"},
            "io_config": cfg["IO Config"],
            "one_gbe": {"count": one_gbe, "io": one_gbe * 80},
            "ten_gbe_copper": {"count": ten_gbe_copper, "io": ten_gbe_copper * 800},
            "ten_gbe_sfp": {"count": ten_gbe_sfp, "io": ten_gbe_sfp * 800},
            "eight_gbfc": {"count": eight_gbfc, "io": eight_gbfc * 525},
            "sixteen_gbfc": {"count": sixteen_gbfc, "io": sixteen_gbfc * 1050},
            "twentyfive_gbe_sfp": {
                "count": twentyfive_gbe_sfp,
                "io": twentyfive_gbe_sfp * 2000,
            },
        }
        existing_data[cfg["Name"]] = new_appl

    with open(json_filename, "w") as json_stream:
        json.dump(existing_data, json_stream, indent=4)


if __name__ == "__main__":
    main(*sys.argv[1:])
