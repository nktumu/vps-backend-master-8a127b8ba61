#!/usr/bin/env conda run -n vupc python

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

import logging
import xlwings as xw

from use_xl import connection
from use_xl import extractor

logger = logging.getLogger(__name__)


def import_workbook(
    src_filename,
    sht_src_name,
    slps_sht_src_name,
    destination_filename=None,
    keep_existing_data=True,
    interactive=True,
):
    if destination_filename is None:
        destination_workbook = xw.Book.caller()
    else:
        destination_workbook = xw.Book(destination_filename)
    logs_sheet = connection.get_sheet(destination_workbook, connection.LOGS_SHEET)
    log_handler = connection.setup_logging(logs_sheet)

    workbook = xw.Book(src_filename)

    try:
        logger.info("Reading from source workbook %s", src_filename)
        scenario = extractor.parse_file(workbook)
        logger.info("Writing workloads into destination")
        data_list = scenario["inputs"]["workloads"]
        extractor.write_excel_data(
            destination_workbook,
            connection.WORKLOADS_SHEET,
            data_list,
            connection.SHEET_WORKLOADS_MAP,
            keep_existing_data,
        )

        logger.info("Writing SLPs into destination")
        slp_data_list = scenario["inputs"]["slps"]
        extractor.write_excel_data(
            destination_workbook,
            connection.BACKUP_POLICIES_SHEET,
            slp_data_list,
            connection.SHEET_STORAGE_LIFECYCLE_POLICIES_MAP,
            keep_existing_data,
        )
    except Exception as ex:
        if interactive:
            logger.exception(ex)
            report_error = destination_workbook.macro("show_message")
            report_error(str(ex), connection.MESSAGE_ERROR_TEXT)
    else:
        if interactive:
            report_info = destination_workbook.macro("show_message")
            report_info(
                f"Successfully imported workbook: {src_filename}",
                connection.MESSAGE_INFO_TEXT,
            )
    finally:
        workbook.close()
        connection.stop_logging(log_handler)
