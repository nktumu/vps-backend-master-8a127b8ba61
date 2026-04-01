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

import sys

import pytest

from use_core import constants

try:
    from use_xl import connection

    import end_to_end_support as etes
except ImportError:
    pass


if sys.platform.startswith("linux"):
    pytest.skip("skipping non-linux tests", allow_module_level=True)


def test_flexscale_simple(the_book):
    etes.run_flexscale_packing_on_book(the_book)

    results_sheet = the_book.sheets[connection.FLEX_SCALE_RESULTS_SHEET]
    nclusters_data = results_sheet.range("A7:L7").value
    row_head, *row_data = nclusters_data
    assert row_head == "Total # Clusters"

    values = [val for val in row_data if val is not None]
    assert values == sorted(values)


def test_flexscale_model_change_effect(the_book):
    etes.run_flexscale_packing_on_book(the_book)

    model_range = the_book.names["flex_scale_appliance_model"].refers_to_range
    capacity_range = the_book.names["NumberOfNodesPerClusterPerYear"].refers_to_range

    capacity_values = []
    for model in constants.FLEXSCALE_MODELS:
        model_range.value = model
        capacity_values.append(capacity_range.value)

    # verify that usable capacity values change for each chosen model
    for idx1, cap1 in enumerate(capacity_values):
        for idx2, cap2 in enumerate(capacity_values):
            if idx1 == idx2:
                continue
            assert cap1 != cap2
