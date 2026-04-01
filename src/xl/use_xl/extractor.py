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

import argparse
import datetime
import json
import logging
import pathlib
import sys

import xlwings as xw

from use_core import constants
from use_core import package_version
from use_core import utils
from use_core.appliance import JSONEncoder
from use_xl import connection

logger = logging.getLogger(__name__)


def read_from_excel(
    book,
    workloads_sht_src_name,
    slps_sht_src_name,
    parser_slp,
    parser_workload,
    parser_timeframe,
    excess_cloud_factor,
):
    scenario = {
        "name": book.name,
        "inputs": {},
        "outputs": [],
    }

    scenario["inputs"]["timeframe"] = parser_timeframe(book)
    scenario["inputs"]["safety"] = connection.excel_to_per_model_safety(
        book.sheets[connection.SAFETY_SHEET]
    )
    scenario["inputs"]["slps"] = connection.excel_to_slp(
        book.sheets[slps_sht_src_name], parser_slp, return_as=connection.OBJECT
    )
    scenario["inputs"]["workloads"] = connection.excel_to_workload(
        book.sheets[workloads_sht_src_name],
        scenario["inputs"]["timeframe"],
        scenario["inputs"]["slps"],
        excess_cloud_factor,
        parser=parser_workload,
        return_as=connection.OBJECT,
    )
    scenario["inputs"]["windows"] = connection.excel_to_window(
        book.sheets[connection.OPERATION_WINDOWS_SHEET], connection.OBJECT
    )
    OLD_SHEET_NAME = True
    for sht in range(1, book.sheets.count + 1):
        if book.sheets(sht).name == connection.SITE_SUMMARY_SHEET:
            RESULTS_SHEET = connection.SITE_SUMMARY_SHEET
            OLD_SHEET_NAME = False
            break
    if OLD_SHEET_NAME:
        RESULTS_SHEET = connection.SITE_SUMMARY_SHEET_PREVIOUS
    scenario["outputs"] = connection.excel_to_appliance_needed(
        book.sheets[RESULTS_SHEET]
    )
    return scenario


def current_parser(book):
    return read_from_excel(
        book,
        connection.WORKLOADS_SHEET,
        connection.BACKUP_POLICIES_SHEET,
        connection.SHEET_STORAGE_LIFECYCLE_POLICIES_MAP,
        connection.SHEET_WORKLOADS_MAP,
        connection.read_timeframe,
        connection.read_excess_cloud_factor,
    )


def parser_31(book):
    return read_from_excel(
        book,
        connection.WORKLOADS_SHEET,
        connection.BACKUP_POLICIES_SHEET,
        connection.SHEET_STORAGE_LIFECYCLE_POLICIES_MAP,
        connection.SHEET_WORKLOADS_MAP_31,
        connection.read_timeframe,
        connection.read_excess_cloud_factor,
    )


def parser_30(book):
    return read_from_excel(
        book,
        connection.WORKLOADS_SHEET,
        connection.BACKUP_POLICIES_SHEET,
        connection.SHEET_STORAGE_LIFECYCLE_POLICIES_MAP,
        connection.SHEET_WORKLOADS_MAP_31,
        connection.read_timeframe_21,
        connection.read_excess_cloud_factor,
    )


def parser_21(book):
    return read_from_excel(
        book,
        connection.WORKLOADS_SHEET,
        connection.BACKUP_POLICIES_SHEET,
        connection.SHEET_STORAGE_LIFECYCLE_POLICIES_MAP_21,
        connection.SHEET_WORKLOADS_MAP_21,
        connection.read_timeframe_21,
        connection.read_excess_cloud_factor,
    )


PARSERS = {
    package_version.package_date: current_parser,
    constants.TIMESTAMP_2_1_p1: parser_21,
    constants.TIMESTAMP_2_1: parser_21,
    constants.TIMESTAMP_3_0_pre6: parser_30,
    constants.TIMESTAMP_3_0_pre7: parser_30,
    constants.TIMESTAMP_3_0_pre8: parser_30,
    constants.TIMESTAMP_3_0_pre9: parser_30,
    constants.TIMESTAMP_3_0_pre10: parser_30,
    constants.TIMESTAMP_3_0_pre11: parser_30,
    constants.TIMESTAMP_3_0_pre12: parser_30,
    constants.TIMESTAMP_3_0_rc1: parser_30,
    constants.TIMESTAMP_3_0_rc2: parser_30,
    constants.TIMESTAMP_3_0_rc3: parser_30,
    constants.TIMESTAMP_3_0_rc4: parser_30,
    constants.TIMESTAMP_3_0: parser_30,
    constants.TIMESTAMP_3_0_patch1: parser_31,
    constants.TIMESTAMP_3_0_patch2: parser_31,
    constants.TIMESTAMP_3_1_rc1: parser_31,
    constants.TIMESTAMP_3_1_rc2: parser_31,
    constants.TIMESTAMP_3_1: parser_31,
    constants.TIMESTAMP_3_1_patch1: parser_31,
    constants.TIMESTAMP_3_1_patch2: parser_31,
    constants.TIMESTAMP_3_1_patch3: parser_31,
    constants.TIMESTAMP_3_1_patch4: parser_31,
    constants.TIMESTAMP_3_1_patch5: current_parser,
    constants.TIMESTAMP_3_1_patch6: current_parser,
    constants.TIMESTAMP_4_0_rc1: current_parser,
    constants.TIMESTAMP_4_0: current_parser,
    constants.TIMESTAMP_4_0_patch1: current_parser,
    constants.TIMESTAMP_4_0_patch2: current_parser,
    constants.TIMESTAMP_4_0_patch3: current_parser,
    constants.TIMESTAMP_4_1_rc1: current_parser,
    constants.TIMESTAMP_4_1_rc2: current_parser,
    constants.TIMESTAMP_4_1_rc3: current_parser,
    constants.TIMESTAMP_4_1_rc4: current_parser,
    constants.TIMESTAMP_4_1: current_parser,
    constants.TIMESTAMP_4_1_patch1: current_parser,
    constants.TIMESTAMP_4_1_patch2: current_parser,
    constants.TIMESTAMP_4_1_patch3: current_parser,
    constants.TIMESTAMP_4_1_patch4: current_parser,
    constants.TIMESTAMP_4_1_patch5: current_parser,
    constants.TIMESTAMP_4_1_patch6: current_parser,
    constants.TIMESTAMP_4_1_patch7: current_parser,
    constants.TIMESTAMP_4_1_patch8: current_parser,
    constants.TIMESTAMP_4_1_patch9: current_parser,
    constants.TIMESTAMP_4_1_patch10: current_parser,
    constants.TIMESTAMP_4_1_patch11: current_parser,
    constants.TIMESTAMP_4_1_patch12: current_parser,
}


def parse_file(book):
    version_cell = None
    try:
        version_cell = book.names["package_date"].refers_to_range
    except Exception:
        logger.debug("The pacakge date range does not exist. Checking alternative")
        pass
    if not version_cell:
        version_sheet_name = connection.SITE_SUMMARY_SHEET_PREVIOUS
        for sht in book.sheets:
            if sht.name == connection.SITE_SUMMARY_SHEET:
                version_sheet_name = connection.SITE_SUMMARY_SHEET
                break
        version_cell = book.sheets[version_sheet_name].range("B1")
    doc_timestamp = utils.parse_to_date(version_cell.options(dates=datetime.date).value)
    return PARSERS[doc_timestamp](book)


def parse_to_stream(book, output_stream):
    scenario = parse_file(book)
    json.dump(scenario, output_stream, cls=JSONEncoder)


def parse_excel_files(input_filenames, output_dir):
    for input_file in input_filenames:
        if output_dir is None:
            output_stream = sys.stdout
        else:
            output_filename = (output_dir / input_file.stem).with_suffix(".json")
            output_stream = open(output_filename, "w")

        workbook = xw.Book(input_file)
        try:
            parse_to_stream(workbook, output_stream)
        finally:
            workbook.close()


def get_col_key(columns, column):
    for col, xlator in columns.items():
        if column == xlator.column_name:
            return col, xlator.column_name
    return column, column


def write_excel_data(
    destination_workbook, destination_sheet_name, data_list, columns, keep_existing_data
):
    destination_sheet = destination_workbook.sheets[destination_sheet_name]
    if keep_existing_data:
        row_last_index = destination_sheet.used_range.rows.count
    else:
        row_last_index = 1
    col_end_index = destination_sheet.used_range.columns.count
    col_header = destination_sheet.range((1, 1), (1, col_end_index))

    app_dict = {}
    for each in col_header.value:
        (key, value) = get_col_key(columns, each)
        app_dict[value] = key

    index = row_last_index + 1
    result = []
    for each_row_data in data_list:
        row = []
        for col in col_header.value:
            if app_dict[col] in each_row_data:
                col_val = each_row_data[app_dict[col]]
                if col_val is None:
                    row.append("")
                else:
                    if isinstance(col_val, utils.Size):
                        row.append(col_val.value)
                    else:
                        row.append(str(col_val))

            else:
                print(" column: " + col + " data not found in source sheet")
                row.append("")
        result.append(row)

    destination_sheet.range("A" + str(index)).value = result


def main(arglist):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-o",
        "--output-dir",
        dest="output_dir",
        type=pathlib.Path,
        help="Directory to write results to (required if more than one input file is provided)",
    )
    parser.add_argument(
        "xl_files",
        type=pathlib.Path,
        nargs="+",
        help="Excel workbook(s) to import from",
    )

    args = parser.parse_args(arglist)
    if len(args.xl_files) > 1 and args.output_dir is None:
        parser.print_help(file=sys.stderr)
        sys.exit(1)
    parse_excel_files(args.xl_files, args.output_dir)


if __name__ == "__main__":
    main(sys.argv[1:])
