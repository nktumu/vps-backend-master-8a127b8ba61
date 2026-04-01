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
import json
import os
import sys

# record sequence
id = 0
# json output
data = {}

# files
infile = sys.stdin.read().strip()
outfile = "../src/core/use_core/conf/gurus/sku.json"

# read csv line by line
with open(infile) as csvfile:
    csvReader = csv.DictReader(csvfile)
    for line in csvReader:
        # increment sequence
        id += 1
        # clear json variable for this loop
        brass = {}
        # loop through each item in this row
        for item in line.items():
            # if the key contains a period, this is a child record
            # the format of the key is parent.child
            if '.' in str(item[0]):
                # parent key
                parent = item[0].split('.')[0]
                # child key
                child = item[0].split('.')[1]
                # child value
                child_value = item[1]
                # the second row of the csv are the record labels
                if id == 1:
                    brass[parent] = item[1]
                else:
                    try:
                        # if a child record already exists, add another child record
                        isinstance(brass[parent], dict)
                        brass[parent][child] = child_value
                    except KeyError:
                        # if their are not yet any children, create a new child record
                        # as a dictionary
                        brass[parent] = {child: child_value}
            else:
                # if there is no period in the key, there are no children
                # set the value normally
                brass[item[0]] = item[1]
        if id == 1:
            # if this is the second row of the csv, name the record labels
            # and add it to the json variable
            data['labels'] = brass
        else:
            # add the row to the json variable
            data[brass["name"]] = brass

full_name = os.path.join(os.path.dirname(__file__), outfile)
with open(full_name, 'w') as jsonfile:
    # write the json variable to a file
    jsonfile.write(json.dumps(data, indent=4))



