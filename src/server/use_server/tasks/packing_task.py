# VERITAS: Copyright (c) 2024 Veritas Technologies LLC. All rights reserved.
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

from use_server.celery_app import app
from use_server.services import celery_service, size_service

logger = logging.getLogger(__name__)


# Celery task to execute appliance sizing
@app.task(name="solve", bind=True)
def solve(
    self, response_dict, safety_margins, site_preferences, workload_list, settings_obj
):
    logger.debug("started celery task: 'solve' with task id: %s", self.request.id)

    appliance_results = {}
    error = False

    try:
        appliance_results = size_service.solve(
            safety_margins, site_preferences, workload_list, settings_obj
        )
    except Exception as ex:
        logger.exception(ex)
        error = True
        response_dict["tasks"][1].update(
            {
                "task": "appliance_sizing",
                "status": "ERROR",
                "progress": 20,
                "error_code": 7,
                "error_msg": str(ex),
            }
        )

    if not error:
        response_dict["tasks"][1].update(
            {"task": "appliance_sizing", "status": "COMPLETE", "progress": 100}
        )
        response_dict["appliance_results"] = appliance_results

    # store the response
    celery_service.store_result(response_dict)

    return response_dict
