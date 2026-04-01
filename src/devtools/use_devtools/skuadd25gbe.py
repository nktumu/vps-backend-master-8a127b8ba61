#!/usr/bin/env python3

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

import json
import sys


def update_skus(skus):
    for key, value in skus.items():
        if key == "labels":
            value["twentyfive_gbe_sfp"] = "25GbE_SFP"
            continue
        value["twentyfive_gbe_sfp"] = {
            "count": 0,
            "io": 0,
        }
        if (
            value["model"] in ["5150", "5250", "5350", "5250-FLEX", "5350-FLEX"]
            and int(value["ten_gbe_sfp"]["count"]) > 0
            and value["io_config"] != "F"
        ):
            value["twentyfive_gbe_sfp"]["count"] = value["ten_gbe_sfp"]["count"]
            value["twentyfive_gbe_sfp"]["io"] = str(
                5 * int(value["ten_gbe_sfp"]["io"]) // 2
            )


def main(filename):
    with open(filename) as in_stream:
        all_skus = json.load(in_stream)
    update_skus(all_skus)
    with open(filename, "w") as out_stream:
        json.dump(all_skus, out_stream, indent=4)


if __name__ == "__main__":
    main(*sys.argv[1:])
