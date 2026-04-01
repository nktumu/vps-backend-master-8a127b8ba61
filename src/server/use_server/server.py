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
import os

from flask import Flask

from use_server.encoders import CustomJSONProvider
from use_server.routes import (
    routes,
    size_routes,
    workload_type_routes,
    slps_routes,
    safety_margin_routes,
    skus_routes,
)


api = Flask(__name__)
api.json = CustomJSONProvider(api)

routes.configure_routes(api)
size_routes.configure_routes(api)
size_routes.configure_async_routes(api)
workload_type_routes.configure_routes(api)
slps_routes.configure_routes(api)
safety_margin_routes.configure_routes(api)
skus_routes.configure_routes(api)


def main():
    logging.basicConfig(
        format="%(asctime)s %(message)s",
        datefmt="%m/%d/%Y %I:%M:%S %p",
        filename="server.log",
        filemode="w",
        level=logging.DEBUG,
    )
    port = int(os.environ.get("USE_SERVER_PORT", 7186))
    api.run(host="0.0.0.0", port=port)
