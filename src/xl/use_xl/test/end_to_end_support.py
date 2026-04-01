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

#
# Support for end to end testing with the USE spreadsheet
#

import os.path

from use_core import constants
from use_xl import connection

_nbdeployutil_data_spreadsheet_name = "src/xl/use_xl/test/test_nbdeployutil.xlsx"

_production_book_name = "USE-1.0.xlsm"

_import_test_dir = "src/xl/use_xl/test/importing-tests"
_rw_test_dir = "src/xl/use_xl/test/workload-tests"

# save name if sheet is saved after run.
_production_output_spreadsheet_name = "OUTPUT-USE-1.0.xlsm"

# Set True to request unit tests save their generated spreadsheets
# for analysis.
_save_generated_sheets_flag = False


def generate_spreadsheet_path(file_name):
    return os.path.realpath(
        os.path.join(os.path.dirname(__file__), "../../../..", file_name)
    )


def production_book_path():
    return generate_spreadsheet_path(_production_book_name)


def nbdeployutil_data_book_path():
    return generate_spreadsheet_path(_nbdeployutil_data_spreadsheet_name)


def import_test_book_path(basename):
    return generate_spreadsheet_path(os.path.join(_import_test_dir, basename))


def rw_test_book_path(basename):
    return generate_spreadsheet_path(os.path.join(_rw_test_dir, basename))


def get_sheet_by_name(book, name):
    """
    Search a book (Excel document) for a sheet with the
    requested name.

    Returns a Sheet object or None if no sheet is found.
    """
    return book.sheets[name]


def get_variables_sheet(book):
    """
    Return the _variables Frame sheet.
    """
    return get_sheet_by_name(book, connection.VARIABLES_SHEET)


def get_sites_sheet(book):
    """
    Return the Sites sheet.
    """
    return get_sheet_by_name(book, connection.SITE_ASSIGNMENTS_SHEET)


def get_assignment_details_sheet(book):
    """
    Return the Workload Assignment Details sheet.
    """
    return get_sheet_by_name(book, connection.RAW_SHEET)


def get_slp_sheet(book):
    """
    Find the Storage Lifecycle Policy sheet with the workloads
    and the button to run the packing.
    """
    return get_sheet_by_name(book, connection.STORAGE_LIFECYCLE_POLICIES_SHEET)


def get_workloads_sheet(book):
    """
    Find the Workloads sheet with the workloads
    and the button to run the packing.
    """
    return get_sheet_by_name(book, connection.WORKLOADS_SHEET)


def get_results_sheet(book):
    """
    Find the Results sheet.
    """
    return get_sheet_by_name(book, connection.SITE_SUMMARY_SHEET)


def get_errors_and_notes_sheet(book):
    """
    Find the Errors And Notes sheet.
    """
    return get_sheet_by_name(book, connection.ERRORS_AND_NOTES_SHEET)


def get_itemization_sheet(book):
    """
    Find the Itermization sheet of NBDeployUtil.
    """
    return get_sheet_by_name(book, connection.NBDEPLOYUTIL_ITEMIZATION_SHEET)


def run_packing_on_book(book):
    """

    Start the packing process in the Excel document.

    This is abstracted out so it can be changed to another method, or
    a choice among multiple methods.  Main other candidate is:

        import connection; connection.main()

    from the Python code in the test case.

    """
    book.macro("activate_sheet")(connection.SITE_ASSIGNMENTS_SHEET)
    connection.main(progress_reporting=False)


def run_flex_packing_on_book(book):
    book.macro("activate_sheet")(connection.SITE_ASSIGNMENTS_SHEET)
    connection.main(
        progress_reporting=False, appliance_family=constants.ApplianceFamily.Flex
    )


def run_flexscale_packing_on_book(book):
    book.macro("activate_sheet")(connection.SITE_ASSIGNMENTS_SHEET)
    connection.main(
        progress_reporting=False, appliance_family=constants.ApplianceFamily.FlexScale
    )
