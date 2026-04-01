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

from . import constants


def text_to_version(text):
    """
    From a text name return the matching software version.  Default is
    the SoftwareVersion default value.
    """
    for sv in constants.SoftwareVersion:
        if text == sv.name:
            return sv
    # no match, return default version
    return constants.DEFAULT_SOFTWARE_VERSION


def list_names_default_first():
    """
    Return a list of display names.

    The first name in the list will be that of the default version.
    """
    name_list = []
    name_list.append(constants.DEFAULT_SOFTWARE_VERSION_STRING)
    for sv in constants.SoftwareVersion:
        if sv != constants.DEFAULT_SOFTWARE_VERSION:
            name_list.append(sv.name)
    return name_list
