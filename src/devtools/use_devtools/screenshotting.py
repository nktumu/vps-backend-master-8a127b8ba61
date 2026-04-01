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

import enum
import functools
import itertools
import os
import pathlib
import platform

from PIL import ImageGrab
import xlwings as xw
from xlwings.constants import CopyPictureFormat, PictureAppearance

if platform.system() == "Windows":
    import pywintypes

from use_core import constants
from use_xl import connection


class RunType(enum.Enum):
    none = enum.auto()
    nba = enum.auto()
    flex = enum.auto()
    flex_scale = enum.auto()

    def appliance_family(self):
        appliance_families = {
            "nba": constants.ApplianceFamily.NBA,
            "flex": constants.ApplianceFamily.Flex,
            "flex_scale": constants.ApplianceFamily.FlexScale,
        }
        return appliance_families[self.name]


SCENARIOS = {
    "as-shipped": {"execute": RunType.none},
    "local-and-dr": {
        "slps": [
            {
                "Storage Lifecycle Policy": "DC-SLP",
                "Domain": "Domain-1",
                "Site": "DC",
                "Backup Image Location": "Local Only",
            },
            {
                "Storage Lifecycle Policy": "SF-DC-SLP",
                "Domain": "Domain-1",
                "Site": "SF",
                "DR-dest": "DC",
                "Backup Image Location": "Local+DR",
                "Incremental Retention (days) - DR": 30,
                "Weekly Full Retention (weeks) - DR": 4,
                "Monthly Full Retention (months) - DR": 6,
            },
        ],
        "workloads": [
            {
                "Storage Lifecycle Policy": "DC-SLP",
            },
            {
                "Storage Lifecycle Policy": "SF-DC-SLP",
            },
        ],
        "execute": RunType.none,
    },
    "multi-site-nba": {
        "slps": [
            {
                "Storage Lifecycle Policy": "DC-SLP",
                "Domain": "Domain-1",
                "Site": "DC",
                "Backup Image Location": "Local Only",
            },
            {
                "Storage Lifecycle Policy": "LA-SLP",
                "Domain": "Domain-1",
                "Site": "LA",
                "Backup Image Location": "Local Only",
            },
            {
                "Storage Lifecycle Policy": "MUM-SLP",
                "Domain": "Domain-1",
                "Site": "MUM",
                "Backup Image Location": "Local Only",
            },
            {
                "Storage Lifecycle Policy": "SF-Cloud-SLP",
                "Domain": "Domain-1",
                "Site": "SF",
                "Backup Image Location": "Local+LTR",
                "Monthly Full Retention (months) - Cloud": 6,
            },
        ],
        "workloads": [
            {"Storage Lifecycle Policy": "DC-SLP", "FETB (TiB)": 20},
            {"Storage Lifecycle Policy": "LA-SLP", "FETB (TiB)": 15},
            {"Storage Lifecycle Policy": "MUM-SLP", "FETB (TiB)": 25},
            {"Storage Lifecycle Policy": "SF-Cloud-SLP", "FETB (TiB)": 5},
        ],
        "execute": RunType.nba,
    },
    "simple-flexscale": {
        "slps": [
            {
                "Storage Lifecycle Policy": "DC-SLP",
                "Domain": "Domain-1",
                "Site": "DC",
                "Backup Image Location": "Local Only",
            },
        ],
        "workloads": [
            {"Storage Lifecycle Policy": "DC-SLP", "FETB (TiB)": 20},
            {"Storage Lifecycle Policy": "DC-SLP", "FETB (TiB)": 30},
            {"Storage Lifecycle Policy": "DC-SLP", "FETB (TiB)": 10},
            {"Storage Lifecycle Policy": "DC-SLP", "FETB (TiB)": 40},
        ],
        "execute": RunType.flex_scale,
    },
    "multi-site-flex": {
        "slps": [
            {
                "Storage Lifecycle Policy": "DC-1-SLP",
                "Domain": "Domain-1",
                "Site": "DC",
                "Backup Image Location": "Local Only",
            },
            {
                "Storage Lifecycle Policy": "DC-2-SLP",
                "Domain": "Domain-2",
                "Site": "DC",
                "Backup Image Location": "Local Only",
            },
            {
                "Storage Lifecycle Policy": "LA-SLP",
                "Domain": "Domain-1",
                "Site": "LA",
                "Backup Image Location": "Local Only",
            },
            {
                "Storage Lifecycle Policy": "SF-Cloud-SLP",
                "Domain": "Domain-1",
                "Site": "SF",
                "Backup Image Location": "Local+LTR",
                "Monthly Full Retention (months) - Cloud": 6,
            },
        ],
        "workloads": [
            {"Storage Lifecycle Policy": "DC-1-SLP", "FETB (TiB)": 20},
            {"Storage Lifecycle Policy": "DC-2-SLP", "FETB (TiB)": 25},
            {"Storage Lifecycle Policy": "LA-SLP", "FETB (TiB)": 15},
            {"Storage Lifecycle Policy": "SF-Cloud-SLP", "FETB (TiB)": 20},
        ],
        "execute": RunType.flex,
    },
}


SCREENSHOTS = [
    {
        "scenario": "as-shipped",
        "sheet": connection.SETTINGS_SHEET,
        "range": "A1:D9",
        "output": "settings-sheet.png",
    },
    {
        "scenario": "as-shipped",
        "sheet": connection.SKU_SHEET,
        "range": "A1:L420",
        "output": "appliance-definitions-sheet.png",
    },
    {
        "scenario": "as-shipped",
        "sheet": connection.BACKUP_POLICIES_SHEET,
        "range": "A1:M4",
        "output": "slp-sheet-1.png",
    },
    {
        "scenario": "as-shipped",
        "sheet": connection.BACKUP_POLICIES_SHEET,
        "range": "N1:AB4",
        "output": "slp-sheet-2.png",
    },
    {
        "scenario": "as-shipped",
        "sheet": connection.WORKLOAD_ATTRIBUTES_SHEET,
        "range": "A1:N19",
        "output": "default-workload-attributes-sheet.png",
    },
    {
        "scenario": "as-shipped",
        "sheet": connection.SAFETY_SHEET,
        "range": "A1:I16",
        "output": "safety-considerations-sheet.png",
    },
    {
        "scenario": "as-shipped",
        "sheet": connection.OPERATION_WINDOWS_SHEET,
        "range": "A1:B4",
        "output": "windows-sheet.png",
    },
    {
        "scenario": "local-and-dr",
        "sheet": connection.SITE_ASSIGNMENTS_SHEET,
        "range": "A1:G3",
        "output": "sites-sheet.png",
    },
    {
        "scenario": "local-and-dr",
        "sheet": connection.WORKLOADS_SHEET,
        "range": "A1:T3",
        "output": "workloads-sheet.png",
    },
    {
        "scenario": "multi-site-nba",
        "sheet": connection.SITE_SUMMARY_SHEET,
        "range": "A1:G8",
        "output": "results-sheet.png",
    },
    {
        "scenario": "multi-site-nba",
        "sheet": connection.APPLIANCE_SUMMARY_SHEET,
        "range": "A1:K10",
        "output": "appliance-summary-table-1.png",
    },
    {
        "scenario": "multi-site-nba",
        "sheet": connection.APPLIANCE_SUMMARY_SHEET,
        "range": "A13:K18",
        "output": "appliance-summary-table-2.png",
    },
    {
        "scenario": "multi-site-nba",
        "sheet": connection.APPLIANCE_SUMMARY_SHEET,
        "range": "A21:K26",
        "output": "appliance-summary-table-3.png",
    },
    {
        "scenario": "multi-site-nba",
        "sheet": connection.APPLIANCE_SUMMARY_SHEET,
        "range": "A29:K31",
        "output": "appliance-summary-table-4.png",
    },
    {
        "scenario": "multi-site-nba",
        "sheet": connection.APPLIANCE_SUMMARY_SHEET,
        "range": "A34:K39",
        "output": "appliance-summary-table-5.png",
    },
    {
        "scenario": "multi-site-nba",
        "sheet": connection.APPLIANCE_SUMMARY_SHEET,
        "range": "A42:E44",
        "output": "appliance-summary-nba-access.png",
    },
    {
        "scenario": "multi-site-flex",
        "sheet": connection.SITE_SUMMARY_SHEET,
        "range": "A1:G6",
        "output": "results-sheet-flex.png",
    },
    {
        "scenario": "multi-site-flex",
        "sheet": connection.APPLIANCE_SUMMARY_SHEET,
        "range": "A1:K10",
        "output": "appliance-summary-flex-table-1.png",
    },
    {
        "scenario": "multi-site-flex",
        "sheet": connection.APPLIANCE_SUMMARY_SHEET,
        "range": "A14:K19",
        "output": "appliance-summary-flex-table-2.png",
    },
    {
        "scenario": "multi-site-flex",
        "sheet": connection.APPLIANCE_SUMMARY_SHEET,
        "range": "A23:K28",
        "output": "appliance-summary-flex-table-3.png",
    },
    {
        "scenario": "multi-site-flex",
        "sheet": connection.APPLIANCE_SUMMARY_SHEET,
        "range": "A32:K38",
        "output": "appliance-summary-flex-table-4.png",
    },
    {
        "scenario": "multi-site-flex",
        "sheet": connection.APPLIANCE_SUMMARY_SHEET,
        "range": "A43:K48",
        "output": "appliance-summary-flex-table-5.png",
    },
    {
        "scenario": "multi-site-flex",
        "sheet": connection.APPLIANCE_SUMMARY_SHEET,
        "range": "A51:E53",
        "output": "appliance-summary-flex-access.png",
    },
    {
        "scenario": "simple-flexscale",
        "sheet": connection.FLEX_SCALE_RESULTS_SHEET,
        "range": "A2:K25",
        "output": "flexscale-results.png",
    },
]


class RetryFailure(Exception):
    pass


def retry(max_attempts, allowed_exceptions):
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            last_exception = None
            for i in range(max_attempts):
                try:
                    return f(*args, **kwargs)
                except allowed_exceptions as ex:
                    last_exception = ex
                    continue
            raise RetryFailure(last_exception)

        return wrapper

    return decorator


if platform.system() == "Windows":
    ignored_exceptions = (OSError, pywintypes.com_error)
elif platform.system() == "Darwin":
    ignored_exceptions = (OSError,)


# On Windows, occasionally the CopyPicture or grabclipboard call can
# fail.  Retrying usually works.
@retry(max_attempts=10, allowed_exceptions=ignored_exceptions)
def save_range(r, filename):
    if platform.system() == "Darwin":
        f_name, f_ext = os.path.splitext(filename)
        filename = f_name + "-macos" + f_ext
        r.api.copy_picture(
            appearance=PictureAppearance.xlScreen, format=CopyPictureFormat.xlBitmap
        )
    elif platform.system() == "Windows":
        result = r.api.CopyPicture(
            PictureAppearance.xlScreen, CopyPictureFormat.xlBitmap
        )
        assert result
    img = ImageGrab.grabclipboard()
    img.save(filename)


def delete_existing(bk, sh):
    used = sh.used_range
    del_range = sh.range((2, 1), used.last_cell.address)
    # using do_remove_line macro here causes used_range to not update,
    # unless del_range is extended to the XFD column.  That causes
    # add_workload to think there is still an entry in row 2 and add
    # the new workload in row 3.  Using Range.delete makes used_range
    # updated correctly.
    del_range.delete(shift="up")


def read_colmap(sh):
    used = sh.used_range
    headers = used.options(ndim=2).value[0]
    return dict((hdr, idx + 1) for idx, hdr in enumerate(headers))


def setup_scenario_sheet(bk, data, sheet_name, adder_macro):
    if not data:
        return
    sh = bk.sheets[sheet_name]
    bk.macro("activate_sheet")(sheet_name)
    delete_existing(bk, sh)
    colmap = read_colmap(sh)
    for idx, row_content in enumerate(data):
        bk.macro(adder_macro)()
        for key, val in row_content.items():
            row_num = idx + 2
            col_num = colmap[key]
            sh.range((row_num, col_num)).value = val


def setup_scenario_slps(bk, slps):
    setup_scenario_sheet(bk, slps, "Storage Lifecycle Policies", "add_slp")


def setup_scenario_workloads(bk, workloads):
    setup_scenario_sheet(bk, workloads, "Workloads", "add_workload")


def setup_scenario_execute(bk, run_type):
    if run_type == RunType.none:
        return
    bk.macro("activate_sheet")(connection.SITE_ASSIGNMENTS_SHEET)
    connection.do_main(
        bk, progress_reporting=False, appliance_family=run_type.appliance_family()
    )


def setup_scenario(bk, scenario):
    setup_scenario_slps(bk, scenario.get("slps"))
    setup_scenario_workloads(bk, scenario.get("workloads"))
    setup_scenario_execute(bk, scenario.get("execute"))


def screenshot(bk, output_dir):
    def scenario_getter(spec):
        return spec["scenario"]

    # group by scenario, so we can reduce setup costs by reusing the
    # scenario for multiple screenshots
    SCREENSHOTS.sort(key=scenario_getter)
    for scenario, shots in itertools.groupby(SCREENSHOTS, scenario_getter):
        setup_scenario(bk, SCENARIOS[scenario])
        for spec in shots:
            sh = bk.sheets[spec["sheet"]]
            bk.macro("activate_sheet")(spec["sheet"])
            save_range(sh.range(spec["range"]), output_dir / spec["output"])


def main():
    wd = pathlib.Path.cwd()

    xl_file = wd / "USE-1.0.xlsm"
    app = xw.App(visible=False)
    try:
        bk = app.books.open(fullname=xl_file)
        screenshot(bk, wd / "images")
    finally:
        app.quit()


if __name__ == "__main__":
    main()
