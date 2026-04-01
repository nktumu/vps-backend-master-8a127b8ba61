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

from ..services import workload_type_service

logger = logging.getLogger(__name__)


def configure_routes(app):
    @app.route("/v1/workload-type", methods=["GET"])
    def get_workload_types():
        logger.debug("call to get_workload_types")

        workload_types = workload_type_service.get_workload_types()
        if workload_types is None:
            return (
                jsonify({"message": "Workload type does not exist"}),
                404,
            )
        return (jsonify(workload_types), 200)

    @app.route("/v1/workload-type/<name>", methods=["GET"])
    def get_workload_type(name):
        logger.debug("call to get_workload_type with name : " + name)

        workload_type = workload_type_service.get_workload_type(name)
        if workload_type is None:
            return (
                jsonify({"message": "Named workload type does not exist"}),
                404,
            )
        return (jsonify(workload_type), 200)

    @app.route("/v1/workload-type/<name>", methods=["PUT"])
    def create_update_workload_type(name):
        logger.debug(
            "call to create_update_workload_type with name : "
            + name
            + " and request data : "
        )
        req_data = request.get_json()
        logger.debug(req_data)

        if workload_type_service.is_valid_request(req_data):
            response = workload_type_service.create_update_workload_type(name, req_data)
            if response is None:
                return (
                    jsonify({"message": "Internal Server Error"}),
                    500,
                )
            return (
                jsonify({"message": "Workload type successfully updated/created"}),
                204,
            )
        else:
            return (
                jsonify({"message": "Invalid input"}),
                405,
            )

    @app.route("/v1/workload-type/<name>", methods=["DELETE"])
    def delete_workload_type(name):
        logger.debug("call to delete_workload_type with name : " + name)

        response = workload_type_service.delete_workload_type(name)
        if response is None:
            return (
                jsonify({"message": "Named workload type does not exist"}),
                404,
            )
        return (jsonify({"message": "Workload type successfully deleted"}), 204)
