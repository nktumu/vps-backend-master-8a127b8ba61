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
import enum
import os.path
from typing import Callable, Dict, List, Optional, Union

import xlsxwriter
from xlsxwriter.worksheet import Worksheet

from use_core import (
    appliance,
    constants,
    model_basis,
    package_version,
    settings,
    software_version,
    utils,
)
from use_core.policy import (
    ChoicePolicy,
    CustomPolicy,
    DecimalPolicy,
    DecimalPolicyNoUpperBound,
    NamePolicy,
    NoPolicy,
    NumberPolicy,
    NumberPolicyNoUpperBound,
)

from .buttons import button_layout
from .flexscale import flex_scale_results_writer, flex_scale_totals_writer
from .sheets import SHEET_VISIBILITY_OVERRIDES, Window


def rgb(r: int, g: int, b: int) -> str:
    """
    Convert the given RGB integer values into a string formatted for
    use as a color parameter to xlsxwriter functions.
    """
    return f"#{r:02x}{g:02x}{b:02x}"


# The COLOR_CHART_* constants are the colors for the components of the
# chart on the Results sheet.

COLOR_CHART_CPU = rgb(165, 165, 165)
COLOR_CHART_GRIDLINES = rgb(217, 217, 217)
COLOR_CHART_HORIZON = rgb(112, 173, 71)
COLOR_CHART_IO = rgb(255, 192, 0)
COLOR_CHART_MEMORY = rgb(237, 125, 49)
COLOR_CHART_NETWORK = rgb(91, 155, 213)
COLOR_CHART_SAFETY = rgb(255, 0, 0)
COLOR_CHART_STORAGE = rgb(0, 176, 80)
COLOR_CHART_ALLOC_STORAGE = rgb(0, 80, 176)


# The COLOR_TAB_* constants are the colors for the sheets that are
# being explicitly highlighted.
COLOR_TAB_APPLIANCE_DEFNS = rgb(84, 130, 53)
COLOR_TAB_RESULTS = rgb(0, 0, 0)
COLOR_TAB_SITE_ASSIGNMENTS = rgb(255, 192, 0)
COLOR_TAB_STORAGE_LIFECYCLE_POLICIES = rgb(255, 130, 29)
COLOR_TAB_WORKLOADS = rgb(177, 23, 29)

# Use this value when we want to have "sufficient" formatted rows.
NUM_ROWS_FORMATTED = 65536

# Formats that can be used by name when writing cells.  These are
# defined here with names so changes are easier.
STATIC_FORMATS = {
    "header": {"bold": True, "text_wrap": True, "bg_color": rgb(142, 169, 219)},
    "header_retention_dr": {
        "bold": True,
        "text_wrap": True,
        "bg_color": rgb(146, 208, 80),
    },
    "header_retention_local": {
        "bold": True,
        "text_wrap": True,
        "bg_color": rgb(255, 192, 0),
    },
    "header_retention_cloud": {
        "bold": True,
        "text_wrap": True,
        "bg_color": rgb(0, 176, 240),
    },
    "invisible": {"font_color": rgb(255, 255, 255)},
    "invalid": {"bg_color": rgb(255, 192, 0)},
    "disabled": {"bg_color": rgb(191, 191, 191)},
    "percent": {"num_format": "0%"},
    "summary_common": {"bold": True, "bg_color": rgb(217, 225, 242)},
    "decimal": {"num_format": "0.00"},
    "percent_two_decimals": {"num_format": "0.00%"},
    "description": {"text_wrap": True},
}
COMPUTED_FORMATS = {
    f"summary_year_{year+1}": {
        "bold": True,
        "bg_color": rgb(*constants.BY_YEAR_RGB[year % len(constants.BY_YEAR_RGB)]),
    }
    for year in range(5 * constants.FIRST_EXTENSION)
}

FORMATS = {**STATIC_FORMATS, **COMPUTED_FORMATS}

VxUSE_DOCUMENTATION_AND_REFERENCE_SHEET = "VxUSE Documentation and References"


class Column:
    def __init__(
        self,
        name,
        width,
        validation=None,
        format=None,
        visible=True,
        key=None,
        custom_format=None,
    ):
        self.name = name
        self.width = width
        self.validation = validation
        self.format = format
        self.visible = visible
        self.key = key
        self.custom_format = custom_format

    @property
    def usable_key(self):
        if self.key is not None:
            return self.key
        return self.name


class SheetType(enum.Enum):
    """
    Type of datasource for the sheet.  SheetType.table is used for
    sheets having simple tabular data.  SheetType.custom is for sheets
    having more complex layouts.  The Sheet object's data_provider
    attribute is treated differently, based on the sheet's type.
    """

    table = enum.auto()
    custom = enum.auto()


CellValue = Union[str, int, float]
TableDataRow = Union[List[CellValue], Dict[str, CellValue]]
TableDataProvider = Callable[[], List[TableDataRow]]
CustomDataProvider = Callable[["UseWriter", Worksheet], None]

RawTableData = List[List[CellValue]]
PostCreationHookType = Callable[
    ["UseWriter", Worksheet, List[Column], RawTableData],
    None,
]


class Sheet:
    """
    A structured representation of an Excel sheet, including its
    contents and formatting.
    """

    def __init__(
        self,
        name: str,
        columns: List[Column],
        header_height: float,
        data_provider: Union[TableDataProvider, CustomDataProvider],
        sheet_type: SheetType = SheetType.table,
        visible: bool = True,
        tab_color: Optional[str] = None,
        keyed_data: bool = False,
        post_creation_hook: Optional[PostCreationHookType] = None,
        window_view: Optional[Window] = None,
        vba_name: Optional[str] = None,
        metadata: bool = False,
        profile_dependent: bool = False,
    ):
        """
        Creates a Sheet object.

        The data_provider attribute defines the source of data for the
        sheet.  If sheet_type is SheetType.table, it must be a
        function taking no arguments and returning a list of rows.
        The contents of the row depend on the value for the keyed_data
        parameter.  If keyed_data is True, each row must be a
        dictionary-like object, mapping column names to values.  If
        keyed_data is False, each row must be a list of values.

        If sheet_type is SheetType.custom, data_provider must be a
        function that takes two arguments: a UseWriter object and an
        xlsxwriter.WorkSheet object, and must fill in the contents
        directly into the worksheet.

        :param str name: Name for the sheet.
        :param list[Column] columns: List of column objects.  This is
            normally only suitable for tabular sheets.
        :param float header_height: Height of the header row.
        :param callable data_provider: Source of data for the sheet.
        :param SheetType sheet_type: Type of the sheet.
        :param boolean visible: Whether the sheet should be visible by
            default.
        :param str tab_color: Color to set for the tab.  This must be
            a string in the format returned by the rgb function.  If
            not provided, no color is set for the tab.
        :param bool keyed_data: Whether the data provider produces
            keyed data.
        :param callable post_creation_hook: Hook executed after data
            provider has filled in the sheet contents.  The hook is
            called with four parameters: the UseWriter object, the
            xlsxwriter.worksheet.Worksheet object, the list of Column
            objects, and the list of rows that have been written.
            This function can manipulate the worksheet properties or
            contents in ways that are difficult to specify generally
            using the data provider or column specifications.
        :param Window window_view: Object specifying whether the sheet
            requires header or row column freezing or splitting.
        :param str vba_name: Name for the VBA module associated with
            the sheet.  This ties the created worksheet to specific
            files in the VBA module.  The name of the VBA module is
            decided by Excel.
        :param bool metadata: Whether the sheet is an internal
            metadata sheet.  Such sheets are not made visible even
            when the user clicks the "Unhide All Sheets" button.
        :param bool profile_dependent: Whether the sheet data depends
            on profile.  If it does, the profile in use will be passed
            to the data provider.
        """
        self.name = name
        self.columns = columns
        self.header_height = header_height
        self.data_provider = data_provider
        self.sheet_type = sheet_type
        self.visible = visible
        self.tab_color = tab_color
        self.keyed_data = keyed_data
        self.post_creation_hook = post_creation_hook
        self.window_view = window_view
        self.vba_name = vba_name
        self.metadata = metadata
        self.profile_dependent = profile_dependent

    def data(self, **kwargs) -> RawTableData:
        """
        Data to be filled in to the sheet.  This calls the data
        provider and translates the result, based on the keyed_data
        attribute, into a list of rows.
        """
        assert self.sheet_type == SheetType.table

        raw_data = self.data_provider(**kwargs)
        if not self.keyed_data:
            return raw_data

        ordered_data = []
        key_list = [col.usable_key for col in self.columns]
        assert len(key_list) == len(set(key_list))  # no duplicates
        for row in raw_data:
            ordered_row = []
            for key in key_list:
                ordered_row.append(row.pop(key))
            assert len(row) == 0  # dataset consumed
            ordered_data.append(ordered_row)
        return ordered_data


def get_appliance_models():
    """Return a set of all distinct models."""
    return model_basis.get_model_values().keys()


def get_appliance_data(profile) -> List[Dict[str, CellValue]]:
    """
    Return list of appliance configurations.  Each element in the
    returned list is a dictionary mapping field names to values from
    the SKU entry.
    """
    appliance_list = appliance.Appliance.get_all_sku(profile)
    output_array = []
    for appliance_config in appliance_list:
        output_array.append(
            {
                "Name": appliance_config.config_name,
                "Display Name": appliance_config.display_name,
                "Model": appliance_config.model,
                "Shelves": appliance_config.shelves,
                "Calculated Capacity": appliance_config.disk_capacity.ignore_unit(),
                "Memory": appliance_config.memory.ignore_unit(),
                "IO Config": appliance_config.io_config,
                "1GbE": appliance_config.one_gbe_count,
                "10GbE Copper": appliance_config.ten_gbe_copper_count,
                "10GbE SFP": appliance_config.ten_gbe_sfp_count,
                "25GbE SFP": appliance_config.twentyfive_gbe_sfp_count,
                "8GbFC": appliance_config.eight_gbfc_count,
                "16GbFC": appliance_config.sixteen_gbfc_count,
                "Visible": "=_xlfn.AGGREGATE(3,5,INDIRECT(ADDRESS(ROW(),1)))",
                # reason for using _xlfn: https://xlsxwriter.readthedocs.io/working_with_formulas.html#formulas-added-in-excel-2010-and-later
            }
        )
    return output_array


def settings_writer(writer: "UseWriter", sheet: Worksheet):
    """
    Write out the contents of the Settings sheet.  This function is a
    CustomDataProvider.
    """
    row = 1
    for settings_group in settings.SETTINGS:
        cat = settings_group["category"]
        sheet.write(row, 0, cat)
        row += 1

        for param in settings_group["params"]:
            if not param["visible"]:
                continue
            sheet.write(row, 1, param["name"])

            value_args = [param["value"]]
            if "format" in param:
                value_args.append(writer.formats[param["format"]])
            sheet.write(row, 2, *value_args)
            cell_name = xlsxwriter.utility.xl_rowcol_to_cell(
                row, 2, row_abs=True, col_abs=True
            )
            sheet.data_validation(cell_name, param["policy"].policy())
            writer.workbook.define_name(param["range"], f"Settings!{cell_name}")

            sheet.write(row, 3, param["description"], writer.formats["description"])

            row += 1

    range_start = xlsxwriter.utility.xl_rowcol_to_cell(1, 0, row_abs=True, col_abs=True)
    range_end = xlsxwriter.utility.xl_rowcol_to_cell(
        row - 1, 2, row_abs=True, col_abs=True
    )
    writer.workbook.define_name("settings", f"='Settings'!{range_start}:{range_end}")


def write_color_table(writer: "UseWriter", worksheet: Worksheet, row: int) -> int:
    """
    Write out a table of colors of various shades of yellow.  The
    table has three columns:

        - format: name of format in the form value_shaded_N, where N
          ranges from 1 to 9

        - r, g, b: columns with values for the red, green, and blue
          components

    These colors are used to shade site names based on their
    utilization.

    This table is part of the datasets written out to the _variables
    sheet.
    """
    (r, g, b) = (255, 255, 255)

    worksheet.write_row(row, 0, ["format", "r", "g", "b"])

    i = 1
    start_row = row + i + 1
    while b > 0:
        worksheet.write_row(row + i, 0, [f"value_shaded_{i - 1}", r, g, b])
        i += 1
        b -= 26
    end_row = row + i
    writer.workbook.define_name(
        "shaded_values", f"='_variables'!$A${start_row}:$A${end_row}"
    )
    return row + i


def write_buttons_table(writer: "UseWriter", worksheet: Worksheet, row: int) -> int:
    """
    Write out a table of buttons.  The columns are various properties
    of the buttons, such as caption, and font.  The table has a ragged
    right edge; the sheet names where the button should go are to the
    right of the table, using as many columns as required.

    The `create_nav_buttons` VBA macro in the Excel workbook reads
    this table and creates the buttons.  This is done instead of
    creating buttons using xlsxwriter because that provides more
    control over the label font size and properties.

    This table is part of the datasets written out to the _variables
    sheet.
    """
    worksheet.write_row(
        row,
        0,
        [
            "macro",
            "name",
            "caption",
            "bold",
            "font_size",
            "left",
            "top",
            "width",
            "height",
            "sheets ->",
        ],
    )
    row += 1
    start_row = row
    row_lengths = []
    for group in button_layout(writer.profile):
        for button in group.buttons:
            row_data = [
                button.macro,
                button.name,
                button.caption,
                button.font_bold,
                button.font_size,
                button.position.left,
                button.position.top,
                button.position.width,
                button.position.height,
                *group.sheet_names,
            ]
            worksheet.write_row(row, 0, row_data)
            row_lengths.append(len(row_data))
            row += 1

    max_row_length = max(row_lengths)
    range_start = xlsxwriter.utility.xl_rowcol_to_cell(
        start_row, 0, row_abs=True, col_abs=True
    )
    range_end = xlsxwriter.utility.xl_rowcol_to_cell(
        row - 1, max_row_length, row_abs=True, col_abs=True
    )
    writer.workbook.define_name(
        "button_definitions", f"='_variables'!{range_start}:{range_end}"
    )

    return row


def write_sheets_table(
    writer: "UseWriter", worksheet: Worksheet, current_row: int
) -> int:
    """
    Write out a table of sheets.  The columns in this table have
    various attributes of the sheet, such as whether the sheet should
    be visible by default.

    This table is used by the VBA macros in the `SheetManagement`
    module to setup default sheet visibility.

    This table is part of the datasets written out to the _variables
    sheet.
    """
    worksheet.write_row(
        current_row,
        0,
        [
            "Sheet Name",
            "Visible",
            "Freeze Panes",
            "Split Column",
            "Split Row",
            "Metadata",
        ],
    )
    current_row += 1
    start_row = current_row
    row_lengths = []
    for sheet in SHEETS:
        row = [sheet.name]
        if sheet.visible:
            row.append(1)
        else:
            row.append(0)
        if sheet.window_view:
            row.extend(
                [
                    sheet.window_view.freeze_panes,
                    sheet.window_view.split_column,
                    sheet.window_view.split_row,
                ]
            )
        else:
            row.extend([False, 0, 0])
        row.append(sheet.metadata)

        worksheet.write_row(current_row, 0, row)
        row_lengths.append(len(row))
        current_row += 1

    range_start = xlsxwriter.utility.xl_rowcol_to_cell(
        start_row, 0, row_abs=True, col_abs=True
    )
    range_end = xlsxwriter.utility.xl_rowcol_to_cell(
        current_row - 1, max(row_lengths), row_abs=True, col_abs=True
    )
    writer.workbook.define_name(
        "sheet_definitions", f"='_variables'!{range_start}:{range_end}"
    )

    return current_row


def write_package_data_table(
    writer: "UseWriter", worksheet: Worksheet, current_row: int
) -> int:
    """
    Write out package version information.  This data may be used by
    import functionality to identify which version of USE a particular
    workbook would have been created by.

    This table is part of the datasets written out to the _variables
    sheet.
    """
    worksheet.write_row(
        current_row, 0, ["Package Date", package_version.package_timestamp]
    )
    writer.workbook.define_name(
        "package_date", f"='_variables'!$B${1+current_row}:$B${1+current_row}"
    )
    current_row += 1
    worksheet.write_row(
        current_row, 0, ["Package Version", package_version.package_version]
    )
    writer.workbook.define_name(
        "package_version", f"='_variables'!$B${1+current_row}:$B${1+current_row}"
    )
    current_row += 1
    worksheet.write_row(current_row, 0, ["Package Profile", writer.profile])
    writer.workbook.define_name(
        "package_profile", f"='_variables'!$B${1+current_row}:$B${1+current_row}"
    )
    current_row += 1

    return current_row


def setup_variables_sheet(
    writer: "UseWriter",
    worksheet: Worksheet,
    columns: List[Column],
    rows: RawTableData,
):
    """
    The variables sheet has various tables that are used to avoid
    hardcoded policies in VBA.  This makes changing these things
    simpler, because modifying VBA is a more costly operation.
    """
    num_workloads = len(rows)
    setup_workloads_formatting(writer, worksheet, num_workloads)
    current_row = num_workloads + 1
    for writer_func in [
        write_color_table,
        write_buttons_table,
        write_sheets_table,
        write_package_data_table,
    ]:
        current_row = writer_func(writer, worksheet, current_row)


def setup_variables2_sheet(
    writer: "UseWriter", worksheet: Worksheet, columns: List[Column], rows: RawTableData
):
    """
    The variables2 sheet contains the source data for new SLPs.  This
    is on a separate sheet because the formatting is setup for the
    entire sheet, and the variables sheet already has similar
    formatting setup for new workloads.
    """
    setup_slp_formats(writer, worksheet, columns, rows)


def setup_workloads_formatting(
    writer: "UseWriter", worksheet: Worksheet, num_rows: int
):
    """
    Configure conditional formatting for the Workloads sheet.  On this
    sheet, the DR- and LTR-related columns need to be disabled (grayed
    out) based on the choice in the backup location column.
    """
    loc_cols = {
        "DR": ["H", "T", "U", "V", "W"],
        "LTR": ["X", "Y", "Z", "AA"],
        "Local": ["P", "Q", "R", "S"],
    }
    setup_conditional_disabling(writer, worksheet, "I", loc_cols, num_rows)


def setup_appliance_filter(
    writer: "UseWriter",
    worksheet: Worksheet,
    columns: List[Column],
    rows: RawTableData,
):
    """
    Setup autofilter on the Appliance Definitions sheet.  Default
    filtering restricts appliance models to the ones that are
    supported by default, and to a single IO Config.
    """

    supported_models = appliance.get_models_multi(
        {"performance_supported": True, "eosl": False}, profile=writer.profile
    )
    # The string `Blanks` is treated specially to match empty cells
    supported_ioconfigs = ["Blanks", "A"]
    supported_ioconfigs_row_hide = ["", "A"]

    worksheet.autofilter(0, 0, len(rows) + 1, len(columns))
    worksheet.filter_column_list(2, supported_models)
    worksheet.filter_column_list(6, supported_ioconfigs)

    # Autofilter is done only by a running Excel instance.  Using
    # xlsxwriter, we need to also explicitly hide the rows that would
    # have been filtered out.

    for i, row_data in enumerate(rows):
        if (
            row_data[2] in supported_models
            and row_data[6] in supported_ioconfigs_row_hide
        ):
            continue
        worksheet.set_row(i + 1, options={"hidden": True})

    num_skus = len(rows)
    NAMESET_DYNAMIC["sku_entry"] = f"='Appliance Definitions'!$B$2:$B${num_skus+1}"


def setup_appliance_summary(
    writer: "UseWriter", worksheet: Worksheet, columns: List[Column], rows: RawTableData
):
    """
    Setup headings and formatting for the Appliance Summary sheet.
    This sheet has year-over-year summary of utilization of various
    resources.  The columns representing each year can be hidden or
    shown using VBA functions associated with the sheet.  The dropdown
    in cell A3 is used as the datasource for the VBA code.
    """
    worksheet.write("A2", "YEARS TO SHOW")
    worksheet.write("A3", "All")
    year_data_row = ["All"] + [f"Year {y_num}" for y_num in range(1, 1000)]
    worksheet.write_row(
        2,
        1,
        year_data_row,
        writer.formats["invisible"],
    )

    # The summary_dropdown_years range is created to point to a list
    # of year numbers.  After sizing, this range will get adjusted to
    # the actual number of years used in sizing.

    worksheet.data_validation(
        "A3", {"validate": "list", "source": "=summary_dropdown_years"}
    )

    worksheet.write_row(
        4, 0, ["Appliance", "Site", "ID"], writer.formats["summary_common"]
    )
    worksheet.write_row(5, 0, ["", "", ""], writer.formats["summary_common"])
    n_dimensions = len(constants.APPLIANCE_SUMMARY_HEADINGS)
    # make a lot of columns properly formatted
    for i in range(constants.FIRST_EXTENSION):
        worksheet.merge_range(
            4,
            3 + n_dimensions * i,
            4,
            (3 + n_dimensions - 1) + n_dimensions * i,
            f"Year {i+1}",
            writer.formats[f"summary_year_{i+1}"],
        )
        worksheet.write_row(
            5,
            3 + n_dimensions * i,
            constants.APPLIANCE_SUMMARY_HEADINGS,
            writer.formats[f"summary_year_{i+1}"],
        )
        # write a large number of rows to have the required percent format
        for row_to_format in range(6, 1000):
            worksheet.write_row(
                row_to_format, 3 + n_dimensions * i, [""], writer.formats["decimal"]
            )
            worksheet.write_row(
                row_to_format,
                4 + n_dimensions * i,
                [""],
                writer.formats["percent_two_decimals"],
            )
            worksheet.write_row(
                row_to_format, 5 + n_dimensions * i, [""], writer.formats["decimal"]
            )
            worksheet.write_row(
                row_to_format,
                6 + n_dimensions * i,
                ["", "", "", "", ""],
                writer.formats["percent_two_decimals"],
            )
            worksheet.write_row(
                row_to_format,
                n_dimensions + 2 + n_dimensions * i,
                [""],
                writer.formats["decimal"],
            )


def setup_raw_appliance_summary(
    writer: "UseWriter", worksheet: Worksheet, columns: List[Column], rows: RawTableData
):
    """
    Setup headings and formatting for the workload Summary sheet.
    This sheet has year-over-year summary of utilization of various
    resources.
    """

    worksheet.write_row(1, 0, ["Appliance", "Type", "Site", "ID"])
    headings = constants.RAW_APPLIANCE_SUMMARY_HEADINGS

    n_dimensions = len(headings)
    # make a lot of columns properly formatted
    for i in range(constants.FIRST_EXTENSION):
        headings = [f"Year {i+1} - {heading}" for heading in headings]

        worksheet.write_row(1, 4 + n_dimensions * i, headings)
        for row_to_format in range(2, 1000):
            worksheet.write_row(
                row_to_format,
                3 + n_dimensions * i,
                [""] * n_dimensions,
                writer.formats["decimal"],
            )


def setup_workload_summary(
    writer: "UseWriter", worksheet: Worksheet, columns: List[Column], rows: RawTableData
):
    """
    Setup headings and formatting for the workload Summary sheet.
    This sheet has year-over-year summary of utilization of various
    resources.
    """

    worksheet.write_row(1, 0, ["Workload", "Site", "ID"])

    n_dimensions = len(constants.WORKLOAD_SUMMARY_HEADINGS)
    # make a lot of columns properly formatted
    for i in range(constants.FIRST_EXTENSION):
        headings = [
            f"Year {i+1} - {heading}" for heading in constants.WORKLOAD_SUMMARY_HEADINGS
        ]

        worksheet.write_row(1, 3 + n_dimensions * i, headings)
        for row_to_format in range(2, 1000):
            worksheet.write_row(
                row_to_format,
                3 + n_dimensions * i,
                [""] * n_dimensions,
                writer.formats["decimal"],
            )


def setup_results(
    writer: "UseWriter", worksheet: Worksheet, columns: List[Column], rows: RawTableData
):
    """
    The Results sheet presents summary of the sizing results.  It
    includes a chart that shows the year-over-year resource
    utilization of the most utilized appliance.  The chart will get
    moved after sizing to a row where it does not obfuscate any data.
    """
    worksheet.write("A1", "Package Date")
    worksheet.write("B1", package_version.package_timestamp)
    worksheet.write("D1", "Package Version")
    worksheet.write("E1", package_version.package_version)
    worksheet.write("A2", "Sizing Run At")
    worksheet.write("A3", "Config")
    worksheet.write("B3", "Total")

    chart = writer.workbook.add_chart({"type": "line"})
    chart.add_series(
        {
            "name": "Storage",
            "values": "='Appliance Chart Data'!chart_series_storage",
            "line": {"color": COLOR_CHART_STORAGE, "width": 2},
        }
    )
    chart.add_series(
        {
            "name": "Allocated Storage",
            "values": "='Appliance Chart Data'!chart_series_alloc_storage",
            "line": {"color": COLOR_CHART_ALLOC_STORAGE, "width": 2},
        }
    )

    chart.add_series(
        {
            "name": "Memory",
            "values": "='Appliance Chart Data'!chart_series_memory",
            "line": {"color": COLOR_CHART_MEMORY, "width": 2},
        }
    )
    chart.add_series(
        {
            "name": "CPU",
            "values": "='Appliance Chart Data'!chart_series_cpu",
            "line": {"color": COLOR_CHART_CPU, "width": 2},
        }
    )
    chart.add_series(
        {
            "name": "I/O",
            "values": "='Appliance Chart Data'!chart_series_io",
            "line": {"color": COLOR_CHART_IO, "width": 2},
        }
    )
    chart.add_series(
        {
            "name": "Network",
            "values": "='Appliance Chart Data'!chart_series_network",
            "line": {"color": COLOR_CHART_NETWORK, "width": 2},
        }
    )

    chart.add_series(
        {
            "name": "Max Safety",
            "values": "='Appliance Chart Data'!chart_series_safety",
            "categories": "='Appliance Chart Data'!chart_categories_safety",
            "line": {"dash_type": "round_dot", "color": COLOR_CHART_SAFETY, "width": 2},
        }
    )

    # A chart can only have a single type.  To have different series
    # use different types, we create additional charts and combine
    # them.
    secondary = writer.workbook.add_chart({"type": "scatter"})
    secondary.add_series(
        {
            "name": "Planning Horizon",
            "values": "='Appliance Chart Data'!chart_series_planning",
            "categories": "='Appliance Chart Data'!chart_categories_planning",
            "line": {"color": COLOR_CHART_HORIZON, "width": 2},
        }
    )

    chart.combine(secondary)

    chart.set_x_axis(
        {
            "name": "Planning Year",
            "min": 1.0,
            "max": 5.0,
            "interval_unit": 1,
            "interval_tick": 1,
            "crossing": 1,
            "position_axis": "on_tick",
        }
    )
    chart.set_y_axis(
        {
            "name": "Usage",
            "major_gridlines": {
                "visible": True,
                "line": {"color": COLOR_CHART_GRIDLINES},
            },
            "num_format": "0%",
            "crossing": 0.0,
        }
    )

    chart.set_size({"width": 830, "height": 510})
    chart.show_blanks_as("gap")
    chart.set_title({"name": "Resource Utilization"})

    worksheet.insert_chart("G2", chart)


def setup_windows_warning(
    writer: "UseWriter", worksheet: Worksheet, columns: List[Column], rows: RawTableData
):
    """
    Sets up conditional formatting to point out problems when the sum
    of the individual windows adds up to more than a single week.
    """
    worksheet.conditional_format(
        "B2:B4",
        {
            "type": "formula",
            "criteria": "=SUM($B$2:$B$4)>7*24",
            "format": writer.formats["invalid"],
        },
    )


def criteria_for_string(match_str: str, location_col: str):
    # generate a formula that returns whether the given string is not
    # present in the chosen backup location.  It is used to disable
    # the cells that are irrelevant.
    cases = [loc for loc in constants.BACKUP_LOCATIONS if match_str not in loc]
    clauses = ",".join(f'EXACT({location_col}2,"{case}")' for case in cases)
    return f"=OR({clauses})"


def setup_conditional_disabling(
    writer: "UseWriter",
    worksheet: Worksheet,
    location_col: str,
    loc_cols: Dict[str, List[str]],
    num_rows: int,
):
    """
    Sets up conditional formatting for a set of columns.  location_col
    is the column used as the decision factor.  loc_cols is a mapping
    that defines which set of columns are enabled for each value in
    the location_col column.
    """
    for loc, cols in loc_cols.items():
        for col in cols:
            cases = [
                l for l in constants.BACKUP_LOCATIONS if loc not in l  # noqa: E741
            ]
            if not cases:
                continue
            clauses = ",".join(f'EXACT({location_col}2,"{case}")' for case in cases)
            criteria = f"=OR({clauses})"
            worksheet.conditional_format(
                f"{col}2:{col}{1+num_rows}",
                {
                    "type": "formula",
                    "criteria": criteria,
                    "format": writer.formats["disabled"],
                },
            )


def setup_slp_formats(
    writer: "UseWriter",
    worksheet: Worksheet,
    _columns: List[Column],
    rows: RawTableData,
):
    """
    Sets up conditional formatting for SLP sheet.  The various columns
    referring to local/DR/LTR retention are enabled or disabled based
    on the selection in the Backup Location column.
    """
    loc_cols = {
        "DR": ["D", "J", "K", "L", "M"],
        "LTR": ["N", "O", "P", "Q"],
        "Local": ["F", "G", "H", "I"],
    }
    setup_conditional_disabling(writer, worksheet, "E", loc_cols, len(rows))


def setup_sites_formats(
    writer: "UseWriter",
    worksheet: Worksheet,
    columns: List[Column],
    _rows: RawTableData,
):
    """
    Sets up conditional formatting for the Sites sheet.  The
    `Appliance Configuration` and `Appliance Model` are not useful if
    both are being set.  This formatting will highlight this mutual
    exclusivity to give the users a hint.
    """
    [config_idx] = [
        idx
        for (idx, col) in enumerate(columns)
        if col.name == "Appliance Configuration"
    ]
    [model_idx] = [
        idx for (idx, col) in enumerate(columns) if col.name == "Appliance Model"
    ]
    config_ref = f"INDIRECT(ADDRESS(ROW(),{config_idx+1}))"
    model_ref = f"INDIRECT(ADDRESS(ROW(),{model_idx+1}))"
    warning_formula = f"=COUNTA({config_ref}, {model_ref}) > 1"

    config_col = xlsxwriter.utility.xl_col_to_name(config_idx, col_abs=True)
    model_col = xlsxwriter.utility.xl_col_to_name(model_idx, col_abs=True)

    config_col_formula = f'=AND({config_col}2 = "", {model_col}2 <> "")'
    model_col_formula = f'=AND({model_col}2 = "", {config_col}2 <> "")'

    for col, disabling_formula in [
        (config_col, config_col_formula),
        (model_col, model_col_formula),
    ]:
        worksheet.conditional_format(
            f"{col}2:{col}{NUM_ROWS_FORMATTED}",
            {
                "type": "formula",
                "criteria": warning_formula,
                "format": writer.formats["invalid"],
            },
        )

        worksheet.conditional_format(
            f"{col}2:{col}{NUM_ROWS_FORMATTED}",
            {
                "type": "formula",
                "criteria": disabling_formula,
                "format": writer.formats["disabled"],
            },
        )


def selected_appliance_data(
    writer: "UseWriter",
    worksheet: Worksheet,
    columns: List[Column],
    rows: RawTableData,
):
    """
    Sets up the data required for building the Appliance Configuration
    dropdown on the Sites sheet.  It needs to find out which rows on
    the Appliance Definition sheet are currently visible.
    """
    num_skus = len(appliance.Appliance.get_all_sku(writer.profile))
    for i in range(num_skus):
        worksheet.write_array_formula(
            i + 1,
            0,
            i + 1,
            0,
            f'{{=IFERROR(INDEX(sku_entry, SMALL(IF(SUBTOTAL(3, OFFSET(sku_entry, MATCH(ROW(sku_entry), ROW(sku_entry))-1, 0, 1)), MATCH(ROW(sku_entry), ROW(sku_entry)), ""), ROWS($A$1:A{i+1}))), "")}}',
        )
    for i in range(20):
        worksheet.write_formula(
            i + 1,
            1,
            f'=IFERROR(INDEX(sku_model,MATCH(0,INDEX(COUNTIF($B$1:B{i+1},sku_model),0,0),0)),"")',
        )


def empty_data():
    return []


def safety_considerations_header(models: List[str]) -> List[Column]:
    """
    Header for the 'Safety Considerations' sheet.  This sheet has a
    column for each appliance model.
    """
    basis = [Column("Option", 24, NoPolicy())]
    for m in models:
        basis.append(Column(m, 24, NoPolicy()))
    return basis


def safety_considerations_data(models: List[str]) -> RawTableData:
    """
    Data for the Safety Considerations sheet.  This fetches data from
    the model description file and returns the dataset describing the
    per-model safety considerations.
    """
    full_model_data = [model_basis.get_model_data(model) for model in models]

    field_names = [
        "Max Capacity Utilization (%)",
        "Max CPU Utilization (%)",
        "Max NW Utilization (%)",
        "Max MBPs Utilization (%)",
        "Max Memory Utilization (%)",
        "Max Jobs/Day",
        "Max DBs with 15 Min RPO",
        "Max VM Clients",
        "Max Concurrent Streams",
        "Max Number of Files",
        "MSDP Max Size (TB)",
        "Max Number of Images",
        "LUN Size for Flex appliance (TiB)",
        f"Max Number of {constants.MANAGEMENT_SERVER_DESIGNATION} Containers",
        "Max Number of Media Server Containers",
        "Max Catalog Size (TB)",
        "Max Number of Universal Shares",
    ]
    field_name_map = {
        "LUN Size for Flex appliance (TiB)": "LUN Size (TiB)",
        f"Max Number of {constants.MANAGEMENT_SERVER_DESIGNATION} Containers": "Max Number of Primary Containers",
        "Max Number of Media Server Containers": "Max Number of MSDP Containers",
    }
    extended_model_data = []
    for fld in field_names:
        # Remove below when Universal Share is ready
        if fld == "Max Number of Universal Shares":
            continue
        row = [fld]
        model_data_key = field_name_map.get(fld, fld)
        for mod_data in full_model_data:
            row.append(mod_data.get(model_data_key))
        extended_model_data.append(row)
    return extended_model_data


def safety_considerations_sheet() -> Sheet:
    models = [constants.MANAGEMENT_SERVER_DESIGNATION] + sorted(get_appliance_models())
    return Sheet(
        "Safety Considerations",
        safety_considerations_header(models),
        constants.FIRST_ROW_HEIGHT,
        lambda: safety_considerations_data(models),
        visible=False,
        window_view=Window(True, 1, 1),
        vba_name="Sheet4",
    )


def slp_data():
    """
    Returns the default SLPs the USE workbook ships with on the
    Storage Lifecycle Policies sheet.
    """
    return [
        {
            "slp_name": "default",
            "domain": constants.DEFAULT_DOMAIN_NAME,
            "site": "DC",
            "dr_dest": " ",
            "backup_location": "Local Only",
            "retention_local_weekly": 4,
            "retention_local_monthly": 6,
            "retention_local_annually": 0,
            "retention_local_incr": 30,
            "retention_dr_weekly": 0,
            "retention_dr_monthly": 0,
            "retention_dr_annually": 0,
            "retention_dr_incr": 0,
            "retention_cloud_weekly": 0,
            "retention_cloud_monthly": 0,
            "retention_cloud_annually": 0,
            "retention_cloud_incr": 0,
            "fulls_per_week": 1,
            "incrementals_per_week": 5,
            "incremental_level": "differential",
            "log_backup_interval": 15,
            "log_backup_level": "differential",
            "front_end_nw": "auto",
            "min_size_dup_jobs": 8,
            "max_size_dup_jobs": 100,
            "force_small_dup_jobs": 30,
            "dr_nw": "auto",
            "ltr_nw": "auto",
        },
    ]


def windows_data():
    """
    Returns default values for the window sizes for the Windows sheet.
    """
    return [["Incrementals", 18], ["Full", 60], ["Replications", 90]]


def table_lookup_ref(key_column: str, table_name: str, table_header: str):
    """
    Builds and returns an Excel formula for looking up values from a
    datasource table.  The key_column argument is the column used as
    the selector.  table_name is a reference to the datasource.
    table_header is a reference to the heading row in the datasource.
    """
    header_address = "INDIRECT(ADDRESS(1,COLUMN()))"
    lookup_key = f"MATCH({header_address}, {table_header}, 0)"
    return f"=VLOOKUP(${key_column}2, {table_name}, {lookup_key}, FALSE)"


def default_workloads_ref() -> str:
    """
    Formula for looking up workload attributes from the datasource in
    the Default Workload Attributes sheet.
    """
    return table_lookup_ref("B", "default_workloads", "default_workloads_header")


def policy_header_ref(column):
    return f"='Storage Lifecycle Policies'!{column}1"


def workloads_header_ref(column):
    return f"='Default Workload Attributes'!{column}1"


def storage_lifecycle_policies_columns() -> List[Column]:
    return [
        Column("Storage Lifecycle Policy", 24, NamePolicy(), key="slp_name"),
        Column("Domain", 20, NamePolicy(), key="domain"),
        Column("Site", 20, NamePolicy(), key="site"),
        Column(
            "DR-dest",
            20,
            dr_dest_policy(location_col="E", dr_dest_col="D"),
            key="dr_dest",
        ),
        Column(
            "Backup Image Location",
            20,
            BACKUP_LOCATION_POLICY,
            key="backup_location",
        ),
        Column(
            "Incremental Retention (days) - Local",
            12,
            NumberPolicyNoUpperBound(),
            key="retention_local_incr",
            custom_format="header_retention_local",
        ),
        Column(
            "Weekly Full Retention (weeks) - Local",
            12,
            NumberPolicyNoUpperBound(),
            key="retention_local_weekly",
            custom_format="header_retention_local",
        ),
        Column(
            "Monthly Full Retention (months) - Local",
            12,
            NumberPolicyNoUpperBound(),
            key="retention_local_monthly",
            custom_format="header_retention_local",
        ),
        Column(
            "Annual Full Retention (years) - Local",
            12,
            NumberPolicyNoUpperBound(),
            key="retention_local_annually",
            custom_format="header_retention_local",
        ),
        Column(
            "Incremental Retention (days) - DR",
            12,
            NumberPolicyNoUpperBound(),
            key="retention_dr_incr",
            custom_format="header_retention_dr",
        ),
        Column(
            "Weekly Full Retention (weeks) - DR",
            12,
            NumberPolicyNoUpperBound(),
            key="retention_dr_weekly",
            custom_format="header_retention_dr",
        ),
        Column(
            "Monthly Full Retention (months) - DR",
            12,
            NumberPolicyNoUpperBound(),
            key="retention_dr_monthly",
            custom_format="header_retention_dr",
        ),
        Column(
            "Annual Full Retention (years) - DR",
            12,
            NumberPolicyNoUpperBound(),
            key="retention_dr_annually",
            custom_format="header_retention_dr",
        ),
        Column(
            "Incremental Retention (days) - Cloud",
            12,
            NumberPolicyNoUpperBound(),
            key="retention_cloud_incr",
            custom_format="header_retention_cloud",
        ),
        Column(
            "Weekly Full Retention (weeks) - Cloud",
            12,
            NumberPolicyNoUpperBound(),
            key="retention_cloud_weekly",
            custom_format="header_retention_cloud",
        ),
        Column(
            "Monthly Full Retention (months) - Cloud",
            12,
            NumberPolicyNoUpperBound(),
            key="retention_cloud_monthly",
            custom_format="header_retention_cloud",
        ),
        Column(
            "Annual Full Retention (years) - Cloud",
            12,
            NumberPolicyNoUpperBound(),
            key="retention_cloud_annually",
            custom_format="header_retention_cloud",
        ),
        Column(
            "Number of Full Backups per Week",
            12,
            NumberPolicyNoUpperBound(),
            key="fulls_per_week",
        ),
        Column(
            "Number of Incremental Backups per Week",
            12,
            NumberPolicyNoUpperBound(),
            key="incrementals_per_week",
        ),
        Column(
            "Incremental Backup Level",
            12,
            INCR_TYPE_POLICY,
            key="incremental_level",
        ),
        Column(
            "Log Backup Frequency (minutes between)",
            12,
            NumberPolicy(0, 1440),
            key="log_backup_interval",
        ),
        Column(
            "Log Backup Incremental Level",
            12,
            INCR_TYPE_POLICY,
            key="log_backup_level",
        ),
        Column("Appliance Front-End Network", 12, NW_INTF_POLICY, key="front_end_nw"),
        Column(
            "Minimum Size Per Duplication Job (GiB)",
            12,
            DecimalPolicyNoUpperBound(1 / utils.Size.UNIT_SCALES["GiB"]),
            key="min_size_dup_jobs",
            visible=False,
        ),
        Column(
            "Maximum Size Per Duplication Job (GiB)",
            12,
            DecimalPolicyNoUpperBound(1 / utils.Size.UNIT_SCALES["GiB"]),
            key="max_size_dup_jobs",
            visible=False,
        ),
        Column(
            "Force Interval for Small Jobs (min)",
            12,
            NumberPolicyNoUpperBound(1),
            key="force_small_dup_jobs",
            visible=False,
        ),
        Column("Appliance DR Network", 12, NW_INTF_POLICY, key="dr_nw"),
        Column("Appliance LTR Network", 12, NW_INTF_POLICY, key="ltr_nw"),
    ]


def workloads_columns() -> List[Column]:
    return [
        Column("Workload Name", 24, NamePolicy(), key="name"),
        Column("Workload Type", 20, ChoicePolicy("=workload_types"), key="type"),
        Column(
            "Number of Clients", 20, NumberPolicyNoUpperBound(1), key="num_instances"
        ),
        Column(
            "FETB (TiB)", 20, DecimalPolicyNoUpperBound(0.01), "decimal", key="fetb"
        ),
        Column(
            policy_header_ref("A"),
            20,
            ChoicePolicy("=backup_policy_names"),
            key="slp_name",
        ),
        Column(
            "Workload Isolation",
            20,
            ChoicePolicy(["Yes", "No"]),
            key="workload_isolation",
        ),
        # Uncomment below when Universal Share is ready
        # Column(
        #     workloads_header_ref("O"),
        #     20,
        #     ChoicePolicy(["Yes", "No"]),
        #     visible=False,
        #     key="universal_share",
        # ),
        Column(
            workloads_header_ref("B"), 10, NoPolicy(), visible=False, key="client_dedup"
        ),
        Column(workloads_header_ref("C"), 10, NoPolicy(), visible=False, key="cbt"),
        Column(workloads_header_ref("D"), 10, NoPolicy(), visible=False, key="sfr"),
        Column(
            workloads_header_ref("E"), 10, NoPolicy(), visible=False, key="accelerator"
        ),
        Column(
            workloads_header_ref("F"),
            10,
            DecimalPolicyNoUpperBound(0.0),
            "percent",
            key="growth_rate",
        ),
        Column(
            workloads_header_ref("G"),
            10,
            DecimalPolicy(0.0),
            "percent",
            key="change_rate",
        ),
        Column(
            workloads_header_ref("H"),
            8,
            DecimalPolicy(0.0),
            "percent",
            visible=False,
            key="initial_dedup",
        ),
        Column(
            workloads_header_ref("I"),
            8,
            DecimalPolicy(0.0),
            "percent",
            visible=False,
            key="dedup",
        ),
        Column(
            workloads_header_ref("J"),
            8,
            DecimalPolicy(0.0),
            "percent",
            visible=False,
            key="addl_full_dedup",
        ),
        Column(
            workloads_header_ref("K"), 8, NumberPolicy(1), visible=False, key="files"
        ),
        Column(
            workloads_header_ref("L"), 8, NumberPolicy(1), visible=False, key="channels"
        ),
        Column(
            workloads_header_ref("M"),
            8,
            NumberPolicy(1),
            visible=False,
            key="files_per_channel",
        ),
        Column(
            workloads_header_ref("N"),
            8,
            ChoicePolicy(["Yes", "No"]),
            visible=False,
            key="log_backup_capable",
        ),
    ]


def workloads_data(*args, **kwargs):
    """
    Sample data for the Workloads table.
    """
    return [
        {
            "name": '=CONCATENATE(VLOOKUP($E2, backup_policies, MATCH("Site", backup_policies_header, 0), FALSE),"_",'
            'C2,"_",B2,"_", ADDRESS(ROW(),COLUMN(),4))',
            "type": "File System (Large Files)",
            "num_instances": 10,
            "fetb": 5,
            "workload_isolation": "No",
            # Uncomment below when Universal Share is ready
            # "universal_share": default_workloads_ref(),
            "client_dedup": default_workloads_ref(),
            "cbt": default_workloads_ref(),
            "sfr": default_workloads_ref(),
            "accelerator": default_workloads_ref(),
            "growth_rate": default_workloads_ref(),
            "change_rate": default_workloads_ref(),
            "initial_dedup": default_workloads_ref(),
            "dedup": default_workloads_ref(),
            "addl_full_dedup": default_workloads_ref(),
            "files": default_workloads_ref(),
            "channels": default_workloads_ref(),
            "files_per_channel": default_workloads_ref(),
            "log_backup_capable": default_workloads_ref(),
            "slp_name": "default",
        }
    ]


def dwa_columns() -> List[Column]:
    """
    Columns for the Default Workload Attributes sheet.
    """
    return [
        Column("Workload Type", 24, NamePolicy(), key="workload_type"),
        Column(
            "Client-Side Dedup?",
            20,
            ChoicePolicy(["Yes", "No", "N/A"]),
            key="client_dedup",
        ),
        Column(
            "Changed Block Tracking?", 20, ChoicePolicy(["Yes", "No", "N/A"]), key="cbt"
        ),
        Column(
            "Enable Single File Recovery?",
            12,
            ChoicePolicy(["Yes", "No", "N/A"]),
            key="sfr",
        ),
        Column("Accelerator?", 12, ChoicePolicy(["Yes", "No"]), key="accelerator"),
        Column(
            "Annual Growth Rate (%)",
            12,
            DecimalPolicyNoUpperBound(0.0),
            "percent",
            key="annual_growth_rate",
        ),
        Column(
            "Daily Change Rate (%)",
            12,
            DecimalPolicy(0.0),
            "percent",
            key="daily_change_rate",
        ),
        Column(
            "Initial Dedup Rate (%)",
            12,
            DecimalPolicy(0.0),
            "percent",
            key="initial_dedup_rate",
        ),
        Column("Dedup Rate (%)", 12, DecimalPolicy(0.0), "percent", key="dedup_rate"),
        Column(
            "Dedup Rate Adl Full (%)",
            12,
            DecimalPolicy(0.0),
            "percent",
            key="dedupe_rate_adl_full",
        ),
        Column(
            "Number of Files per FETB",
            12,
            NumberPolicy(
                1,
            ),
            key="files",
        ),
        Column("Number of Channels", 12, NumberPolicy(1, 10000), key="channels"),
        Column(
            "Files per Channel", 12, NumberPolicy(1, 10000), key="files_per_channel"
        ),
        Column(
            "Log Backup Capable?",
            12,
            ChoicePolicy(["Yes", "No"]),
            key="log_backup_capable",
        ),
        # Uncomment below when Universal Share is ready
        # Column(
        #     "Universal Share?",
        #     12,
        #     ChoicePolicy(["Yes", "No"]),
        #     visible=False,
        #     key="universal_share",
        # ),
    ]


BACKUP_LOCATION_POLICY = ChoicePolicy(constants.VISIBLE_BACKUP_LOCATIONS)
INCR_TYPE_POLICY = ChoicePolicy(["none", "differential", "cumulative"])
NW_INTF_POLICY = ChoicePolicy([str(n) for n in appliance.NetworkType])
SITE_NW_TYPE_POLICY = ChoicePolicy(
    [str(n) for n in appliance.NetworkType if n.is_site_criteria]
)
SITE_SOFTWARE_VERSION_POLICY = ChoicePolicy(software_version.list_names_default_first())


def dr_dest_policy(location_col, dr_dest_col):
    """
    Validation policy that ensures the DR destination column only
    contains a value if the backup location policy requires DR.
    """
    no_dr_chosen = f'ISERROR(FIND("DR", {location_col}2))'
    dr_chosen_clause = f"AND(LEN(TRIM({dr_dest_col}2)) = 0, {no_dr_chosen})"
    dr_not_chosen_clause = f"AND(LEN(TRIM({dr_dest_col}2)) > 0, NOT({no_dr_chosen}))"
    return CustomPolicy(f"=OR({dr_chosen_clause}, {dr_not_chosen_clause})")


SHEETS: List[Sheet] = [
    Sheet(
        "Storage Lifecycle Policies",
        storage_lifecycle_policies_columns(),
        constants.FIRST_ROW_HEIGHT,
        slp_data,
        keyed_data=True,
        post_creation_hook=setup_slp_formats,
        tab_color=COLOR_TAB_STORAGE_LIFECYCLE_POLICIES,
        window_view=Window(True, 1, 1),
        vba_name="Sheet11",
    ),
    Sheet(
        "Workloads",
        workloads_columns(),
        constants.FIRST_ROW_HEIGHT,
        workloads_data,
        keyed_data=True,
        tab_color=COLOR_TAB_WORKLOADS,
        window_view=Window(True, 1, 1),
        vba_name="Sheet10",
    ),
    Sheet(
        "Sites",
        [
            Column("Site Name", 24, NamePolicy()),
            Column("Appliance Configuration", 80, ChoicePolicy("=site_appliance")),
            Column("Appliance Model", 20, ChoicePolicy("=site_model")),
            Column("Site Network Type", 20, SITE_NW_TYPE_POLICY),
            Column("WAN Network Type", 20, SITE_NW_TYPE_POLICY),
            Column("CC Network Type", 20, SITE_NW_TYPE_POLICY),
            Column(
                "Appliance Bandwidth for CC (Gbps)",
                10,
                DecimalPolicy(0.0, maximum=None),
            ),
            Column("Software Version", 20, SITE_SOFTWARE_VERSION_POLICY, visible=False),
        ],
        constants.FIRST_ROW_HEIGHT,
        empty_data,
        post_creation_hook=setup_sites_formats,
        tab_color=COLOR_TAB_SITE_ASSIGNMENTS,
        window_view=Window(True, 0, 1),
        vba_name="Sheet13",
    ),
    Sheet(
        "Appliance Definitions",
        [
            Column("Name", 80, NoPolicy()),
            Column("Display Name", 12, NoPolicy(), visible=False),
            Column("Model", 12, NoPolicy()),
            Column("Shelves", 12, NoPolicy()),
            Column("Calculated Capacity", 16, NoPolicy()),
            Column("Memory", 12, NoPolicy()),
            Column("IO Config", 12, NoPolicy()),
            Column("1GbE", 12, NoPolicy()),
            Column("10GbE Copper", 12, NoPolicy()),
            Column("10GbE SFP", 12, NoPolicy()),
            Column("25GbE SFP", 12, NoPolicy()),
            Column("8GbFC", 12, NoPolicy()),
            Column("16GbFC", 12, NoPolicy()),
            Column("Visible", 12, NoPolicy(), visible=False),
        ],
        constants.FIRST_ROW_HEIGHT,
        get_appliance_data,
        keyed_data=True,
        post_creation_hook=setup_appliance_filter,
        tab_color=COLOR_TAB_APPLIANCE_DEFNS,
        window_view=Window(True, 1, 1),
        vba_name="Sheet12",
        profile_dependent=True,
    ),
    Sheet(
        "Settings",
        [
            Column("Category", 24, NoPolicy()),
            Column("Parameter", 22, NoPolicy()),
            Column("Value", 20, NoPolicy()),
            Column("Description", 80, NoPolicy()),
        ],
        constants.FIRST_ROW_HEIGHT,
        settings_writer,
        sheet_type=SheetType.custom,
        visible=False,
        vba_name="Sheet5",
    ),
    Sheet(
        "Logs",
        [
            Column("Timestamp", 24, NoPolicy()),
            Column("Level", 20, NoPolicy()),
            Column("Logger", 20, NoPolicy()),
            Column("Message", 64, NoPolicy()),
            Column("Backtrace", 64, NoPolicy()),
        ],
        constants.FIRST_ROW_HEIGHT,
        empty_data,
        visible=False,
        window_view=Window(True, 0, 1),
        vba_name="Sheet16",
    ),
    Sheet(
        "Errors And Notes",
        [
            Column("Workload Name", 48, NamePolicy(), key="name"),
            Column("Error & Note", 128, NoPolicy()),
        ],
        constants.FIRST_ROW_HEIGHT,
        empty_data,
        visible=False,
        window_view=Window(True, 0, 1),
        vba_name="Sheet17",
    ),
    Sheet(
        "Appliance Summary",
        [],
        constants.FIRST_ROW_HEIGHT,
        empty_data,
        post_creation_hook=setup_appliance_summary,
        visible=False,
        vba_name="Sheet2",
    ),
    Sheet(
        "Raw Appliance Summary",
        [],
        constants.FIRST_ROW_HEIGHT,
        empty_data,
        post_creation_hook=setup_raw_appliance_summary,
        visible=False,
        vba_name="Sheet23",
    ),
    Sheet(
        "Workload Summary",
        [],
        constants.FIRST_ROW_HEIGHT,
        empty_data,
        post_creation_hook=setup_workload_summary,
        visible=False,
        vba_name="Sheet22",
    ),
    Sheet(
        "Results",
        [],
        constants.FIRST_ROW_HEIGHT,
        empty_data,
        post_creation_hook=setup_results,
        tab_color=COLOR_TAB_RESULTS,
        visible=True,
        vba_name="Sheet7",
    ),
    Sheet(
        f"{constants.MANAGEMENT_SERVER_DESIGNATION} Summary",
        [
            Column("Domain", 24, NoPolicy()),
            Column(constants.MANAGEMENT_SERVER_DESIGNATION, 24, NoPolicy()),
        ],
        constants.FIRST_ROW_HEIGHT,
        empty_data,
        visible=False,
        vba_name="Sheet9",
    ),
    Sheet(
        "Default Workload Attributes",
        dwa_columns(),
        constants.FIRST_ROW_HEIGHT,
        model_basis.default_workload_attributes_data,
        keyed_data=True,
        visible=False,
        window_view=Window(True, 1, 1),
        vba_name="Sheet51",
        profile_dependent=True,
    ),
    Sheet(
        "Windows",
        [
            Column("Operation", 24, NoPolicy()),
            Column(
                "Time (hours per week)", 20, NumberPolicy(1, constants.HOURS_PER_WEEK)
            ),
        ],
        constants.FIRST_ROW_HEIGHT,
        windows_data,
        post_creation_hook=setup_windows_warning,
        visible=False,
        window_view=Window(True, 0, 1),
        vba_name="Sheet3",
    ),
    safety_considerations_sheet(),
    Sheet(
        "Workload Assignment Details",
        [
            Column("Domain", 24, NoPolicy()),
            Column("Site", 20, NoPolicy()),
            Column("Appliance", 24, NoPolicy()),
            Column("Appliance Id", 20, NoPolicy()),
            Column("Workload", 20, NoPolicy()),
            Column("Mode", 20, NoPolicy()),
            Column("Assignment", 20, NoPolicy()),
            Column("DR Capacity of Planning Horizon (TiB)", 20, NoPolicy()),
        ],
        constants.FIRST_ROW_HEIGHT,
        empty_data,
        visible=False,
        window_view=Window(True, 1, 1),
        vba_name="Sheet1",
    ),
    Sheet(
        "Workload Assign Details Flex",
        [
            Column("Site", 20, NoPolicy()),
            Column("Appliance", 20, NoPolicy()),
            Column("Container", 20, NoPolicy()),
            Column("Workload", 20, NoPolicy()),
            Column("Mode", 20, NoPolicy()),
            Column("Assignment", 20, NoPolicy()),
            Column("DR Capacity of Planning Horizon (TiB)", 20, NoPolicy()),
        ],
        constants.FIRST_ROW_HEIGHT,
        empty_data,
        visible=False,
        window_view=Window(True, 1, 1),
        vba_name="Sheet19",
    ),
    Sheet(
        "Appliance Chart Data",
        [],
        16,
        empty_data,
        visible=False,
        vba_name="Sheet6",
        metadata=True,
    ),
    Sheet(
        "Site Data",
        [
            Column("Appliance Selected", 80, NamePolicy()),
            Column("Appliance Model Available", 20, NamePolicy()),
            Column("Appliance Model Sorted", 20, NamePolicy()),
        ],
        constants.FIRST_ROW_HEIGHT,
        empty_data,
        post_creation_hook=selected_appliance_data,
        visible=False,
        vba_name="Sheet14",
        metadata=True,
    ),
    Sheet(
        "xlwings.conf",
        [],
        78,
        empty_data,
        visible=False,
        vba_name="Sheet8",
        metadata=True,
    ),
    Sheet(
        "Workload Assignments",
        [
            Column("Domain", 20, NoPolicy()),
            Column("Site", 20, NoPolicy()),
            Column(
                f"Number of {constants.MANAGEMENT_SERVER_DESIGNATION}s", 20, NoPolicy()
            ),
            Column(
                f"{constants.MANAGEMENT_SERVER_DESIGNATION} Configuration",
                20,
                NoPolicy(),
            ),
            Column("Number of Media Servers", 20, NoPolicy()),
            Column("Media Server Configuration", 20, NoPolicy()),
            Column("Workload Name", 20, NoPolicy()),
            Column("Workload Mode", 20, NoPolicy()),
            Column("Number of Instances", 20, NoPolicy()),
        ],
        constants.FIRST_ROW_HEIGHT,
        empty_data,
        visible=False,
        window_view=Window(True, 1, 1),
        vba_name="Sheet15",
    ),
    Sheet(
        "Workload Assignments Flex",
        [
            Column("Site", 20, NoPolicy()),
            Column("Appliance", 20, NoPolicy()),
            Column("Number of Containers", 20, NoPolicy()),
            Column("Domain", 20, NoPolicy()),
            Column("Container", 20, NoPolicy()),
            Column("Workload", 20, NoPolicy()),
            Column("Mode", 20, NoPolicy()),
            Column("Number of Clients", 20, NoPolicy()),
        ],
        constants.FIRST_ROW_HEIGHT,
        empty_data,
        visible=False,
        window_view=Window(True, 1, 1),
        vba_name="Sheet18",
    ),
    Sheet(
        "_variables",
        workloads_columns(),
        constants.FIRST_ROW_HEIGHT,
        workloads_data,
        post_creation_hook=setup_variables_sheet,
        keyed_data=True,
        visible=False,
        vba_name="Sheet20",
        metadata=True,
    ),
    Sheet(
        "_variables2",
        storage_lifecycle_policies_columns(),
        constants.FIRST_ROW_HEIGHT,
        slp_data,
        post_creation_hook=setup_variables2_sheet,
        keyed_data=True,
        visible=False,
        vba_name="Sheet21",
        metadata=True,
    ),
    Sheet(
        "_flex_scale_data",
        [],
        constants.FIRST_ROW_HEIGHT,
        empty_data,
        visible=False,
    ),
    Sheet(
        "Flex Scale Totals",
        [],
        constants.FIRST_ROW_HEIGHT,
        flex_scale_totals_writer,
        sheet_type=SheetType.custom,
        visible=False,
    ),
    Sheet(
        "Flex Scale Sizing Results",
        [],
        constants.FIRST_ROW_HEIGHT,
        flex_scale_results_writer,
        sheet_type=SheetType.custom,
        visible=True,
    ),
]

NAMESET_APPLIANCE_SELECTION = {
    "site_appliance": "=OFFSET('Site Data'!$A$2,0,0,COUNTIF('Site Data'!$A:$A, \"?*\")-1,1)",
    "site_model": "=OFFSET('Site Data'!$B$2,0,0,COUNTIF('Site Data'!$B:$B, \"?*\")-1,1)",
    "site_model_sorted": "=SORT(OFFSET('Site Data'!$B$2,0,0,COUNTIF('Site Data'!$B:$B, \"?*\")-1,1))",
    "sku_model": "=OFFSET('Appliance Definitions'!$A$1,1,MATCH(\"Model\",'Appliance Definitions'!$1:$1,0)-1,COUNTA('Appliance Definitions'!$A:$A)-1,1)",
}

NAMESET_DYNAMIC: Dict[str, str] = {
    # filled in during post-creation hooks
}

NAMESET_PROGRESS_REPORT = {
    "detail_progress_cell": "='Results'!$A$3",
    "progress_cell": "='Results'!$A$2",
}

NAMESET_SLPS = {
    "backup_policies": "=OFFSET('Storage Lifecycle Policies'!$A$1,1,0,COUNTA('Storage Lifecycle Policies'!$A:$A)-1,COUNTA('Storage Lifecycle Policies'!$1:$1))",
    "backup_policies_header": "=OFFSET('Storage Lifecycle Policies'!$A$1,0,0,1,COUNTA('Storage Lifecycle Policies'!$1:$1))",
    "backup_policy_names": "=OFFSET('Storage Lifecycle Policies'!$A$1,1,0,COUNTA('Storage Lifecycle Policies'!$A:$A)-1,1)",
}

NAMESET_SUMMARY_SHEET = {
    "summary_dropdown": "='Appliance Summary'!$A3",
    "summary_dropdown_years": "='Appliance Summary'!$B$3:$G$3",
    "vupc_summary_area": "='Appliance Summary'!$A$5:$AZ$6",
}

NAMESET_WORKLOAD_DEFAULTS = {
    "default_workloads": "=OFFSET('Default Workload Attributes'!$A$2,0,0,COUNTA('Default Workload Attributes'!$A:$A)-1,COUNTA('Default Workload Attributes'!$1:$1))",
    "default_workloads_header": "=OFFSET('Default Workload Attributes'!$A$1,0,0,1,COUNTA('Default Workload Attributes'!$1:$1))",
    "workload_types": "=OFFSET('Default Workload Attributes'!$A$2,0,0,COUNTA('Default Workload Attributes'!$A:$A)-1,1)",
}

NAMESET_NEW_ROW = {
    "new_slp_row": "='_variables2'!$A$2:$AB$2",
    "new_workload_row": "='_variables'!$A$2:$AS$2",
}

NAMESET_APPLIANCE_CHART_DATA = {
    "chart_data_rgb": "='Appliance Chart Data'!$M1:$M$%d" % len(constants.BY_YEAR_RGB),
}

NAMESET_CHART_DATA = {
    "chart_series_storage": "='Appliance Chart Data'!$A$1:$A$5",
    "chart_series_memory": "='Appliance Chart Data'!$B$1:$B$5",
    "chart_series_cpu": "='Appliance Chart Data'!$C$1:$C$5",
    "chart_series_io": "='Appliance Chart Data'!$D$1:$D$5",
    "chart_series_network": "='Appliance Chart Data'!$E$1:$E$5",
    "chart_series_alloc_storage": "='Appliance Chart Data'!$F$1:$F$5",
    "chart_series_safety": "='Appliance Chart Data'!$K$1:$K$5",
    "chart_categories_safety": "='Appliance Chart Data'!$J$1:$J$5",
    "chart_series_planning": "='Appliance Chart Data'!$H$1:$H$5",
    "chart_categories_planning": "='Appliance Chart Data'!$G$1:$G$5",
}

NAMESET_WINDOWS_DATA = {
    "window_duration_incremental": "='Windows'!$B$2",
    "window_duration_full": "='Windows'!$B$3",
    "window_duration_replication": "='Windows'!$B$4",
}

# List of names to create.  These are grouped into "namesets" for
# organization.  VBA, Excel formulas and python code can use these
# names to conveniently refer to specific ranges in the workbook and
# avoid hardcoding cell addresses.
NAMES = [
    NAMESET_APPLIANCE_CHART_DATA,
    NAMESET_APPLIANCE_SELECTION,
    NAMESET_CHART_DATA,
    NAMESET_DYNAMIC,
    NAMESET_NEW_ROW,
    NAMESET_PROGRESS_REPORT,
    NAMESET_SLPS,
    NAMESET_SUMMARY_SHEET,
    NAMESET_WORKLOAD_DEFAULTS,
    NAMESET_WINDOWS_DATA,
]


class UseWriter:
    """
    Represents the USE workbook.  The workbook is programmatically
    generated so as to not require it to be checked in to source
    control, making changes easier to track and manage.
    """

    workbook: xlsxwriter.Workbook

    def __init__(self, filename: str, profile: str):
        self.profile = profile
        self.workbook = xlsxwriter.Workbook(filename)

    def close(self):
        self.workbook.close()

    def write_data(self, worksheet: Worksheet, sheet_data: RawTableData):
        """
        Write the provided data into the worksheet.  The data is a
        list of rows.  Each row is, in turn, a list of values.  The
        values can be scalar values such as strings or integers, or
        they can be tuples.  If the value is a 2-tuple, the second
        element is the validation policy.  If the value is a 3-tuple,
        the third element is the name of the format to use.  If the
        value is a 4-tuple, the fourth element is the help text
        associated with the cell.
        """
        for i, row_data in enumerate(sheet_data):
            for j, cell_data in enumerate(row_data):
                format = None
                tip = None
                if isinstance(cell_data, tuple):
                    value = cell_data[0]
                    validation = cell_data[1]
                    if len(cell_data) > 2:
                        format = cell_data[2]
                    if len(cell_data) > 3:
                        tip = cell_data[3]
                else:
                    value = cell_data
                    validation = None
                if format is None:
                    worksheet.write(i + 1, j, value)
                else:
                    worksheet.write(i + 1, j, value, self.formats[format])
                if validation is not None:
                    worksheet.data_validation(i + 1, j, i + 1, j, validation.policy())
                if tip is not None:
                    worksheet.write_comment(i + 1, j, tip)

    def create_sheets(self):
        """
        Create the sheets configured in the SHEETS list.
        """
        self.sheets = []
        for sheet in SHEETS:
            sheet.profile = self.profile
            worksheet: xlsxwriter.worksheet.Worksheet = self.workbook.add_worksheet(
                sheet.name
            )
            for i, column in enumerate(sheet.columns):
                worksheet.write(0, i, column.name)
                if column.format is None:
                    if not column.visible:
                        worksheet.set_column(i, i, column.width, options={"hidden": 1})
                    else:
                        worksheet.set_column(i, i, column.width)
                else:
                    if not column.visible:
                        worksheet.set_column(
                            i,
                            i,
                            column.width,
                            self.formats[column.format],
                            options={"hidden": 1},
                        )
                    else:
                        worksheet.set_column(
                            i, i, column.width, self.formats[column.format]
                        )
                worksheet.data_validation(
                    1, i, NUM_ROWS_FORMATTED, i, column.validation.policy()
                )

            worksheet.set_row(0, sheet.header_height, self.formats["header"])

            for i, column in enumerate(sheet.columns):
                if column.custom_format is not None:
                    worksheet.write(
                        0, i, column.name, self.formats[column.custom_format]
                    )

            profile_arg = {}
            if sheet.profile_dependent:
                profile_arg["profile"] = self.profile
            if sheet.sheet_type is SheetType.table:
                rows = sheet.data(**profile_arg)
                self.write_data(worksheet, rows)
            else:
                sheet.data_provider(self, worksheet, **profile_arg)

            if sheet.post_creation_hook is not None:
                sheet.post_creation_hook(self, worksheet, sheet.columns, rows)

            visible_by_default = SHEET_VISIBILITY_OVERRIDES[self.profile].get(
                sheet.name, sheet.visible
            )
            if not visible_by_default:
                worksheet.hide()
            if sheet.tab_color is not None:
                worksheet.set_tab_color(sheet.tab_color)

            if sheet.vba_name:
                worksheet.set_vba_name(sheet.vba_name)
            self.sheets.append(worksheet)

    def create_formats(self):
        self.formats = {}
        for fmt_name, fmt_info in FORMATS.items():
            self.formats[fmt_name] = self.workbook.add_format(fmt_info)

    def create_names(self):
        for nameset in NAMES:
            for name, value in nameset.items():
                self.workbook.define_name(name, value)

    def add_vba(self):
        self.workbook.set_vba_name("ThisWorkbook")
        vba_file = os.path.join(os.path.dirname(__file__), "vbaProject.bin")
        self.workbook.add_vba_project(vba_file)


def main():
    """
    Create the USE workbook.
    """

    parser = argparse.ArgumentParser(prog="use_xlwriter")
    parser.add_argument("--profile", type=str, default="standard")
    parser.add_argument("output_filename", type=str)
    args = parser.parse_args()

    workbook = UseWriter(args.output_filename, args.profile)
    workbook.create_formats()
    workbook.create_sheets()
    workbook.create_names()
    workbook.add_vba()
    workbook.close()
