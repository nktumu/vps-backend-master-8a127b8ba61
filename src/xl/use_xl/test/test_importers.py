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

try:
    from use_xl import connection
    from use_xl import importers
except ImportError:
    pass


if sys.platform.startswith("linux"):
    pytest.skip("skipping non-linux tests", allow_module_level=True)


def _test_actual_import(src, dest, tmpdir, nworkloads):
    target_filename = os.path.join(tmpdir, "use-src.xlsm")
    shutil.copy(src.fullname, target_filename)

    current_workloads = len(
        dest.sheets[connection.WORKLOADS_SHEET].range("A2").expand("down")
    )
    importers.import_workbook(
        target_filename,
        connection.WORKLOADS_SHEET,
        connection.STORAGE_LIFECYCLE_POLICIES_SHEET,
        interactive=False,
    )
    new_workloads = len(
        dest.sheets[connection.WORKLOADS_SHEET].range("A2").expand("down")
    )

    assert new_workloads == current_workloads + nworkloads
    dest.macro("activate_sheet")(connection.SITE_ASSIGNMENTS_SHEET)
    connection.do_main(
        dest, progress_reporting=False, appliance_family=constants.ApplianceFamily.NBA
    )


def test_import_workload(the_book, use_tempdir):
    _test_actual_import(the_book, the_book, use_tempdir, 1)


@pytest.mark.slowtest
def test_import_old_workload(import_source_book, the_book, use_tempdir):
    book = import_source_book["book"]
    nworkloads = import_source_book["nworkloads"]

    _test_actual_import(book, the_book, use_tempdir, nworkloads)
