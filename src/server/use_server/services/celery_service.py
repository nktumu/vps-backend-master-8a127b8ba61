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
import pickle
from use_server.celery_app import app
from flask import jsonify

logger = logging.getLogger(__name__)


# Stores the results in the results queue
def store_result(results):
    logger.debug("storing results in results_queue for job id: %s", results["job_id"])
    results_queue = results["job_id"]

    try:
        # ack existing message, if any. This is to ensure we keep a single copy of the message for the given id
        with app.connection_for_read() as conn:
            conn.default_channel.basic_get(results_queue, no_ack=True)
    except Exception as ex:
        logger.exception(ex)

    # send a message to results_queue
    app.send_task("store_result", args=[results], queue=results_queue)


# Fetches the results from the results queue for the given id
def get_async_task_result(job_id):
    result = None

    with app.connection_for_read() as conn:
        message = conn.default_channel.basic_get(job_id, no_ack=False)

    if message is not None:
        message_body = pickle.loads(message.body)
        result = message_body[0][0]
        return jsonify(result)

    return result
