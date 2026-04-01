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

from flask import jsonify, request

from ..services import skus_service

logger = logging.getLogger(__name__)


def configure_routes(app):
    @app.route("/v1/skus", methods=["GET"])
    def get_sku():
        # (i.e. ?model=some-value)
        model = request.args.get(
            "model"
        )  # Comma-separated list of models to include in result.
        io_config = request.args.get(
            "io_config"
        )  # Comma-separated list of IO configs to include in result.

        logger.debug(
            "call to get_sku with model: %s and io_config: %s", model, io_config
        )
        sku = skus_service.get_skus(model, io_config)

        if sku is None or len(sku) == 0:
            return (
                jsonify({"message": "Appliance SKU does not exist"}),
                404,
            )
        return (jsonify(sku), 200)

    @app.route("/v1/skus", methods=["POST"])
    def add_remove_sku():
        req_data = request.get_json()
        if req_data is None:
            return (
                jsonify({"message": "Invalid input"}),
                405,
            )

        logger.debug("call to create_update_sku with req_data : ")
        logger.debug(req_data)

        if skus_service.is_valid_request(req_data):
            response = skus_service.add_remove_sku(req_data)
            if response is None:
                return (
                    jsonify({"message": "Internal Server Error"}),
                    500,
                )
            return (
                jsonify({"message": "Appliance SKUs successfully created/removed"}),
                204,
            )
        else:
            return (
                jsonify({"message": "Invalid input"}),
                405,
            )
