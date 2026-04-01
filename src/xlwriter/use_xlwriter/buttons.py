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

from typing import List


class Position:
    """
    The Position class represents the location and size of a button.
    The attributes are float values in pixels.  Some trial-and-error
    is typically involved in assigning a position to a button.
    """

    left: float
    top: float
    width: float
    height: float

    def __init__(self, left: float, top: float, width: float, height: float):
        self.left = left
        self.top = top
        self.width = width
        self.height = height


class Button:
    """
    Represents a button in an Excel workbook.  A button is associated
    with a VBA macro, which must be created in the VBA project.
    Additionally, the position, text and other appearance-related
    attributes of the button are represented in the Button object.
    """

    position: Position
    macro: str
    caption: str
    font_bold: str
    font_size: str
    name: str

    def __init__(
        self,
        position: Position,
        macro: str,
        caption: str,
        font_bold: bool,
        font_size: int,
    ):
        self.position = position
        self.macro = macro
        self.caption = caption
        self.font_bold = font_bold
        self.font_size = font_size

    @property
    def name(self):
        return self.caption.replace(" ", "_").lower()


class ButtonGroup:
    """
    A group of buttons associated with a set of sheets.  This helps
    keep multiple buttons organized, when the same set of buttons must
    be shown on multiple sheets.
    """

    sheet_names: List[str]
    buttons: List[Button]

    def __init__(self, sheet_names: List[str], buttons: List[Button]):
        self.sheet_names = sheet_names
        self.buttons = buttons


def button_activate_workloads(left):
    return Button(
        Position(left, 0.75, 120, 30),
        "activate_workloads_sheet",
        "Go to Workloads",
        True,
        12,
    )


def button_unhide_tabs(left):
    return Button(
        Position(left, 0.75, 40, 30), "unhide_all_sheets", "Unhide All Tabs", True, 9
    )


def button_hide_tabs(left):
    return Button(Position(left, 0.75, 40, 30), "hide_all_sheets", "Hide Tabs", True, 9)


def button_results_tab(left):
    return Button(
        Position(left, 0.75, 40, 30),
        "activate_results_sheet",
        "Results Tab",
        True,
        9,
    )


def button_activate_settings(left):
    return Button(
        Position(left, 40, 80, 30), "activate_settings_sheet", "Settings", True, 12
    )


def button_activate_slp(left):
    return Button(
        Position(left, 0.75, 120, 30), "activate_slp_sheet", "Go to Policies", True, 12
    )


def button_new_slp(left):
    return Button(Position(left, 0.75, 120, 30), "add_slp", "New SLP", True, 12)


def button_add_multiple_slps(left):
    return Button(
        Position(left, 40, 120, 30),
        "add_multiple_slps",
        "Add Multiple SLPs",
        True,
        12,
    )


def button_duplicate_slp(left):
    return Button(Position(left, 0.75, 120, 30), "duplicate_slp", "Copy SLP", True, 12)


def button_remove_slp(left):
    return Button(Position(left, 0.75, 120, 30), "remove_slp", "Delete SLP", True, 12)


def button_activate_sites(left):
    return Button(
        Position(left, 0.75, 120, 30), "activate_sites_sheet", "Go to Sites", True, 12
    )


def button_new_workload(left):
    return Button(
        Position(left, 0.75, 120, 30), "add_workload", "New Workload", True, 12
    )


def button_add_multiple_workloads(left):
    return Button(
        Position(left, 40, 120, 30),
        "add_multiple_workloads",
        "Add Multiple Workloads",
        True,
        9,
    )


def button_duplicate_workload(left):
    return Button(
        Position(left, 0.75, 120, 30), "duplicate_workload", "Copy Workload", True, 12
    )


def button_remove_workload(left):
    return Button(
        Position(left, 0.75, 120, 30), "remove_workload", "Delete Workload", True, 12
    )


def button_import_workload(left):
    return Button(
        Position(left, 0.75, 120, 30), "import_workload", "Import Workload", True, 12
    )


def button_import_nbdeployutil(left):
    return Button(
        Position(left, 40, 120, 30),
        "import_nbdeployutil",
        "Import NBDeployUtil",
        True,
        12,
    )


def button_vupc_input(left):
    return Button(
        Position(left, 0.75, 120, 20), "nba_sizing", "Sizing Results", True, 12
    )


def button_vupc_input_flex(left, top=30):
    return Button(Position(left, top, 120, 20), "flex_sizing", "Flex Sizing", True, 12)


def button_vupc_input_flexscale(left):
    return Button(
        Position(left, 60, 120, 20), "flexscale_sizing", "Flex Scale Sizing", True, 12
    )


def button_duplicate_workload_type(left):
    return Button(
        Position(left, 0.75, 120, 30),
        "duplicate_workload_type",
        "Copy Workload Type",
        True,
        12,
    )


def button_remove_workload_type(left):
    return Button(
        Position(left, 0.75, 120, 30),
        "remove_workload_type",
        "Delete Workload Type",
        True,
        12,
    )


BUTTONS_COMMON: List[ButtonGroup] = [
    ButtonGroup(
        buttons=[
            button_activate_workloads(0.75),
            button_unhide_tabs(290),
            button_hide_tabs(330),
            button_results_tab(370),
        ],
        sheet_names=[
            "Appliance Definitions",
            "Appliance Summary",
            "Workload Summary",
            "Master Server Summary",
            "Raw Appliance Summary",
            "Safety Considerations",
            "Windows",
            "Workload Assign Details Flex",
            "Workload Assignment Details",
            "Workload Assignments",
            "Workload Assignments Flex",
        ],
    ),
    ButtonGroup(
        buttons=[
            button_activate_slp(0.75),
            button_activate_workloads(150),
            button_unhide_tabs(290),
            button_hide_tabs(330),
            button_results_tab(370),
        ],
        sheet_names=["Settings"],
    ),
    ButtonGroup(
        buttons=[
            button_activate_workloads(0.75),
            button_unhide_tabs(290),
            button_hide_tabs(330),
        ],
        sheet_names=["Results", "Flex Scale Sizing Results"],
    ),
    ButtonGroup(
        buttons=[
            button_activate_workloads(0.75),
            button_new_slp(150),
            button_add_multiple_slps(150),
            button_duplicate_slp(273),
            button_remove_slp(397),
            button_unhide_tabs(521),
            button_hide_tabs(561),
            button_results_tab(601),
            button_activate_settings(0.75),
        ],
        sheet_names=["Storage Lifecycle Policies"],
    ),
    ButtonGroup(
        buttons=[
            button_activate_sites(0.75),
            button_new_workload(150),
            button_add_multiple_workloads(150),
            button_duplicate_workload(273),
            button_remove_workload(397),
            button_import_workload(521),
            button_unhide_tabs(645),
            button_hide_tabs(685),
            button_results_tab(725),
            button_import_nbdeployutil(521),
        ],
        sheet_names=["Workloads"],
    ),
    ButtonGroup(
        buttons=[
            button_activate_workloads(0.75),
            button_duplicate_workload_type(150),
            button_remove_workload_type(273),
            button_unhide_tabs(397),
            button_hide_tabs(437),
            button_results_tab(477),
        ],
        sheet_names=["Default Workload Attributes"],
    ),
]

BUTTONS_STANDARD: List[ButtonGroup] = BUTTONS_COMMON + [
    ButtonGroup(
        buttons=[
            button_vupc_input(0.75),
            button_activate_workloads(150),
            button_unhide_tabs(290),
            button_hide_tabs(330),
            button_results_tab(370),
            button_vupc_input_flex(0.75),
            button_vupc_input_flexscale(0.75),
        ],
        sheet_names=["Sites"],
    )
]

BUTTONS_TERADATA: List[ButtonGroup] = BUTTONS_COMMON + [
    ButtonGroup(
        buttons=[
            button_activate_workloads(150),
            button_unhide_tabs(290),
            button_hide_tabs(330),
            button_results_tab(370),
            button_vupc_input_flex(0.75, top=0.75),
        ],
        sheet_names=["Sites"],
    )
]

BUTTON_LAYOUTS = {
    "standard": BUTTONS_STANDARD,
    "teradata": BUTTONS_TERADATA,
}


def button_layout(profile: str) -> List[ButtonGroup]:
    return BUTTON_LAYOUTS[profile]
