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

import os.path
import shutil
import sys

import pytest

from use_core import constants
from use_core import packing

try:
    from use_xl import connection
    from use_xl import importers

    import end_to_end_support as etes
    import helper_xl as helper
except ImportError:
    pass


if sys.platform.startswith("linux"):
    pytest.skip("skipping non-linux tests", allow_module_level=True)


pytestmark = pytest.mark.slowtest


def test_rw_flex_minimum(the_rw_book_flex_minimal, the_book, use_tempdir):
    source_filename = os.path.join(use_tempdir, "use-src.xlsm")
    shutil.copy(the_rw_book_flex_minimal.fullname, source_filename)
    the_rw_book_flex_minimal.close()

    importers.import_workbook(
        source_filename,
        connection.WORKLOADS_SHEET,
        connection.STORAGE_LIFECYCLE_POLICIES_SHEET,
        keep_existing_data=False,
        interactive=False,
    )

    the_book.macro("activate_sheet")(connection.SITE_ASSIGNMENTS_SHEET)
    connection.do_main(
        the_book,
        progress_reporting=False,
        appliance_family=constants.ApplianceFamily.Flex,
    )

    results_sheet = etes.get_results_sheet(the_book)
    summary = helper.parse_site_summary(results_sheet)

    totals = summary["totals"]
    assert len(totals) == 1  # kinds of appliances
    assert sum(totals.values()) == 2  # total number of appliances


@pytest.mark.skip(reason="no longer fails because of increased msdp pool size")
def test_rw_multiple_failures(the_rw_book_multiple_failures, the_book, use_tempdir):
    source_filename = os.path.join(use_tempdir, "use-src.xlsm")
    shutil.copy(the_rw_book_multiple_failures.fullname, source_filename)
    the_rw_book_multiple_failures.close()

    importers.import_workbook(
        source_filename,
        connection.WORKLOADS_SHEET,
        connection.STORAGE_LIFECYCLE_POLICIES_SHEET,
        interactive=False,
    )

    the_book.macro("activate_sheet")(connection.SITE_ASSIGNMENTS_SHEET)
    with pytest.raises(packing.NotifyWorkloadError) as sizer_failure:
        connection.do_main(
            the_book,
            progress_reporting=False,
            appliance_family=constants.ApplianceFamily.NBA,
        )
    exc_message = str(sizer_failure.value)
    assert "domains were split" in exc_message
    assert "skipped from media" in exc_message


@pytest.mark.skip(reason="primary server sizing is now disabled")
def test_rw_master_skip(the_rw_book_master_skip, the_book, use_tempdir):
    source_filename = os.path.join(use_tempdir, "use-src.xlsm")
    shutil.copy(the_rw_book_master_skip.fullname, source_filename)
    the_rw_book_master_skip.close()

    importers.import_workbook(
        source_filename,
        connection.WORKLOADS_SHEET,
        connection.STORAGE_LIFECYCLE_POLICIES_SHEET,
        interactive=False,
    )

    the_book.macro("activate_sheet")(connection.SITE_ASSIGNMENTS_SHEET)
    connection.do_main(
        the_book,
        progress_reporting=False,
        appliance_family=constants.ApplianceFamily.NBA,
    )

    results_sheet = etes.get_results_sheet(the_book)
    error = helper.error_summary(results_sheet)
    assert "skipped from master" in error


def test_flexscale_multi_cluster(the_rw_book_flexscale_multi, the_book, use_tempdir):
    source_filename = os.path.join(use_tempdir, "use-src.xlsm")
    shutil.copy(the_rw_book_flexscale_multi.fullname, source_filename)
    the_rw_book_flexscale_multi.close()

    importers.import_workbook(
        source_filename,
        connection.WORKLOADS_SHEET,
        connection.STORAGE_LIFECYCLE_POLICIES_SHEET,
        interactive=False,
    )

    the_book.macro("activate_sheet")(connection.SITE_ASSIGNMENTS_SHEET)
    connection.do_main(
        the_book,
        progress_reporting=False,
        appliance_family=constants.ApplianceFamily.FlexScale,
    )

    # we get the combination (#clusters, #nodes) for each year.  This
    # must match at least one of the (#clusters, #nodes) combinations
    # that are calculated for each dimension.
    results_sheet = the_book.sheets[connection.FLEX_SCALE_RESULTS_SHEET]
    nodes_clusters_range = results_sheet.range("C7:L8").options(numbers=int).value

    reported = []  # list of #clusters,#nodes pairs in result
    for clusters_val, nodes_val in zip(*nodes_clusters_range):
        if not clusters_val:
            continue
        reported.append((clusters_val, nodes_val))

    totals_sheet = the_book.sheets[connection.FLEX_SCALE_TOTALS_SHEET]
    dimensions_range = totals_sheet.range("C40:L43").options(numbers=int).value

    dimensions = []
    for row in dimensions_range:  # each row is a dimension, such as capacity
        dimension_row = []
        for clusters_val, nodes_val in zip(row[::2], row[1::2]):
            dimension_row.append((clusters_val, nodes_val))
        dimensions.append(dimension_row)

    for idx, (clusters_val, nodes_val) in enumerate(reported):
        candidates = [dimension_row[idx] for dimension_row in dimensions]
        assert (clusters_val, nodes_val) in candidates
