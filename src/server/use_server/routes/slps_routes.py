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

from ..services import slps_service

logger = logging.getLogger(__name__)


def configure_routes(app):
    @app.route("/v1/slps", methods=["GET"])
    def get_all_slps():
        logger.debug("call to get_all_slps")

        slps = slps_service.get_slps()
        if slps is None:
            return (
                jsonify({"message": "Storage Lifecycle Policies does not exist"}),
                404,
            )
        return (jsonify(slps), 200)

    @app.route("/v1/slps/<name>", methods=["GET"])
    def get_slp(name):
        logger.debug("call to get_slp with name : " + name)

        slp = slps_service.get_slp(name)
        if slp is None:
            return (
                jsonify({"message": "Named policy does not exist"}),
                404,
            )
        return (jsonify(slp), 200)

    @app.route("/v1/slps/<name>", methods=["PUT"])
    def create_update_slp(name):
        logger.debug(
            "call to create_update_slp with name : " + name + " and request data : "
        )
        req_data = request.get_json()
        logger.debug(req_data)

        if slps_service.is_valid_request(req_data):
            response = slps_service.create_update_slp(name, req_data)
            if response is None:
                return (
                    jsonify({"message": "Internal Server Error"}),
                    500,
                )
            return (jsonify({"message": "Slp successfully updated/created"}), 204)
        else:
            return (
                jsonify({"message": "Invalid input"}),
                405,
            )

    @app.route("/v1/slps/<name>", methods=["DELETE"])
    def delete_slp(name):
        logger.debug("call to delete_slp with name : " + name)

        response = slps_service.delete_slp(name)
        if response is None:
            return (
                jsonify({"message": "Named policy does not exist"}),
                404,
            )
        return (jsonify({"message": "SLP successfully deleted"}), 204)
