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

import os
import sys

import pytest

from use_core import appliance
from use_core import utils

from use_core.test import helper_core

try:
    from use_xl import charting
except ImportError:
    pass


if sys.platform.startswith("linux"):
    pytest.skip("skipping non-linux tests", allow_module_level=True)


def test_master_chart(
    test_workloads_dict, test_appliances, windows, test_per_appliance_safety_margins
):
    appl = appliance.Appliance.from_json(test_appliances[0])
    media_appl = appliance.Appliance.from_json(test_appliances[2])
    wk = test_workloads_dict["files_backup"]

    timeframe = utils.DEFAULT_TIMEFRAME

    ctx = helper_core.make_sizer_context(
        test_per_appliance_safety_margins,
        workloads=[wk],
        media_configs={(wk.domain, wk.site_name): media_appl},
        master_configs={wk.domain: appl},
        timeframe=timeframe,
        window_sizes=windows,
    )
    result = ctx.pack()

    for domain, _site_name, app_id, mserver in result.all_master_servers:
        chart = charting.render_master_chart(mserver, timeframe.num_years)
        assert chart is not None
        if "VUPC_TEST_SHOW_CHART" in os.environ:
            # showing the chart blocks the test, so only do if
            # explicitly asked for.  This allows for quick checks when
            # making changes to the charting code.
            charting.plt.show()
