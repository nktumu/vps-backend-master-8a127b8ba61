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

import pytest
import xlwings as xw

from use_core import model_basis
import end_to_end_support as etes


@pytest.fixture
def the_rep_nbdeployutil(excel_app):
    book = excel_app.books.open(fullname=etes.nbdeployutil_data_book_path())
    yield book
    book.close()


@pytest.fixture
def the_rw_book_flex_minimal(excel_app):
    return excel_app.books.open(fullname=etes.rw_test_book_path(RW_BOOK_FLEX_MINIMAL))


@pytest.fixture
def the_rw_book_multiple_failures(excel_app):
    return excel_app.books.open(
        fullname=etes.rw_test_book_path(RW_BOOK_MULTIPLE_FAILURES)
    )


@pytest.fixture
def the_rw_book_master_skip(excel_app):
    return excel_app.books.open(fullname=etes.rw_test_book_path(RW_BOOK_MASTER_SKIP))


@pytest.fixture
def the_rw_book_flexscale_multi(excel_app):
    return excel_app.books.open(
        fullname=etes.rw_test_book_path(RW_BOOK_FLEXSCALE_MULTI)
    )


@pytest.fixture
def the_book(excel_app):
    excel_app.display_alerts = False
    book = excel_app.books.open(fullname=etes.production_book_path())
    book.set_mock_caller()
    yield book
    # remove the mock caller because the book is going away.  No
    # reference to the book will be usable.
    del xw.Book._mock_caller
    book.close()


SHIPPED_BOOKS = [
    {"file": "USE-3.0.xlsm", "nworkloads": 1},
    {"file": "USE-3.1.xlsm", "nworkloads": 1},
    {"file": "USE-3.1-patch6.xlsm", "nworkloads": 1},
    {"file": "USE-4.0.xlsm", "nworkloads": 1},
    {"file": "USE-4.0-patch1.xlsm", "nworkloads": 1},
    {"file": "USE-4.0-patch3.xlsm", "nworkloads": 1},
    {"file": "USE-4.1-rc4.xlsm", "nworkloads": 1},
    {"file": "USE-4.1-patch4.xlsm", "nworkloads": 1},
]

USER_BOOKS = [
    {"file": "DXC-K-H 2 USE-3.0-pre8.xlsm", "nworkloads": 7},
    {"file": "USE-2.1-ADBv1.xlsm", "nworkloads": 24},
]

RW_BOOK_FLEX_MINIMAL = "USE-3.0-rc3 - Russell testing 4 - stc removed - flex.xlsm"
RW_BOOK_MULTIPLE_FAILURES = "USE-3.0-rc3-Boulder.xlsm"
RW_BOOK_MASTER_SKIP = "Credit-Suisse-All-Sites-USE-3.0.xlsm"
RW_BOOK_FLEXSCALE_MULTI = "USE-NBFS.xlsm"


@pytest.fixture(params=SHIPPED_BOOKS + USER_BOOKS)
def import_source_book(excel_app, request):
    filename = request.param["file"]
    nworkloads = request.param["nworkloads"]
    book = excel_app.books.open(fullname=etes.import_test_book_path(filename))
    yield {"book": book, "nworkloads": nworkloads}
    book.close()


@pytest.fixture(params=model_basis.dwa_names("standard"))
def dwa_testcase(request):
    yield request.param
