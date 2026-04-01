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
from http import HTTPStatus

from flask import request

from ..services import size_service, celery_service

logger = logging.getLogger(__name__)


def configure_routes(app):
    @app.route("/v1/size", methods=["POST"])
    def size_api():
        logger.debug("call to size_api with request data : ")
        req_data = request.get_json()
        logger.debug(req_data)

        size_service.is_valid_request(req_data)
        size_service.is_request_supported(req_data)

        response = size_service.size_data(req_data, size_service.SizeRequestMode.Sync)
        if response is None:
            return (
                {"message": "Internal Server Error"},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
        return response


def configure_async_routes(app):
    @app.route("/v1/async_size", methods=["POST"])
    def async_size_api():
        logger.debug("call to size_api with request data : ")
        req_data = request.get_json()
        logger.debug(req_data)

        size_service.is_valid_request(req_data)
        size_service.is_request_supported(req_data)

        response = size_service.size_data(req_data, size_service.SizeRequestMode.Async)
        if response is None:
            return (
                {"message": "Internal Server Error"},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
        return response

    @app.route("/v1/async_size/status/<job_id>", methods=["GET"])
    def async_size_status_api(job_id):
        logger.debug("call to async_size_status_api with request data : ")

        response = celery_service.get_async_task_result(job_id)
        if response is None:
            return (
                {"message": "Internal Server Error"},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
        return response
