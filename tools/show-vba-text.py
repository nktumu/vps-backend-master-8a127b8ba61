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
import subprocess
import sys

def main(filename):
    out = subprocess.check_output(["olevba", "--code", "--json", filename])
    result = json.loads(out)
    container = [elem for elem in result if elem["type"] == "OLE"][0]
    for macro in sorted(container["macros"], key=lambda m: m["vba_filename"]):
        filename = macro["vba_filename"]
        code = macro["code"]

        if filename == "VBA_P-code.txt":
            continue

        print(f"File: {filename}")
        print(code)
        print("--")

if __name__ == "__main__":
    main(*sys.argv[1:])
