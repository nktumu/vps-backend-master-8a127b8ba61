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

import csv
import pathlib
import sqlite3

csv_path = pathlib.Path("constants.csv")
try:
    csv_path.unlink()
except FileNotFoundError:
    pass

with sqlite3.connect("src/core/use_core/conf/models/constants.db") as conn:
    results = conn.cursor().execute("select * from constants_table")

    with open(csv_path, "w") as f:
        writer = csv.writer(f)
        writer.writerow(
            ("appliance", "site_version", "task", "workload", "name", "value")
        )
        for row in results:
            writer.writerow(row)
