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

from use_core import constants


def fit_sheet(sheet):
    sheet.autofit()
    # Make room for navigation buttons
    sheet.range("A1").row_height = constants.FIRST_ROW_HEIGHT
    # Blue fill color in first row for consistent look
    sheet.range("A1:AB1").color = constants.FIRST_ROW_FILL


def make_all_rows_same_length(vec):
    """
    Ensure all lists are the same length by appending None elements.

    Input is a list of lists.  All rows shorter than the longest row
    will be extended by padding with `None` elements.

    Example: [ [1, 2], [3, 4, 5]] => [ [1, 2, None], [3, 4, 5]]
    """
    longest_len = max([len(s) for s in vec])
    for r in vec:
        if len(r) < longest_len:
            r += [None] * (longest_len - len(r))
