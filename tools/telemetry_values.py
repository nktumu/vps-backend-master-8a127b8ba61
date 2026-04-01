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

import os

import psycopg2 as psycopg2


def get_telemetry_data():
    """ query data from the telemetry database """
    command = """
        WITH fetb_table AS (
        SELECT
            id,
            policy_type,
            schedule_type,
            (starting_files_total * 1024 * 1024 * 1024) / starting_kilobytes_total as files_per_tb
        FROM aggregate_jobs
        WHERE created_on >= '2020-09-06 00:00:00'
            AND created_on < '2020-09-12 00:00:00'
            AND schedule_type in ('Full Backup', 'Transaction Log Backup')
            AND starting_files_total > 0
            AND starting_kilobytes_total > 0
        )
        SELECT
            policy_type,
            schedule_type,
            COUNT(distinct id) AS num_jobs,
            MIN(files_per_tb) AS min_files_per_tb,
            MAX(files_per_tb) AS max_files_per_tb
        FROM fetb_table
        GROUP BY policy_type, schedule_type;
        """

    conn = None
    try:
        conn = psycopg2.connect(os.getenv("TELEMETRY_DB_CONN"))
        cur = conn.cursor()
        cur.execute(command)
        print("The number of parts: ", cur.rowcount)
        row = cur.fetchone()

        while row is not None:
            print(row)
            row = cur.fetchone()

        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    get_telemetry_data()
