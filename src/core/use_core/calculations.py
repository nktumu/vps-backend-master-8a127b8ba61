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


import collections

SizePair = collections.namedtuple("SizePair", ["pre_dedupe", "post_dedupe"])


def calculate_incrementals_pre_dedupe(
    data_size_tb,
    change_rate,
    retention_level_for_diff_inc,
    number_of_increments_per_week,
):
    pre_dedupe_size = (
        data_size_tb
        * change_rate
        * (retention_level_for_diff_inc * number_of_increments_per_week)
    )
    return pre_dedupe_size


def calculate_incrementals(
    data_size_tb,
    change_rate,
    dedupe_rate_daily,
    retention_level_for_diff_inc,
    number_of_increments_per_week,
):
    sz = calculate_incrementals_pre_dedupe(
        data_size_tb,
        change_rate,
        retention_level_for_diff_inc,
        number_of_increments_per_week,
    )
    return SizePair(pre_dedupe=sz, post_dedupe=sz * (1 - dedupe_rate_daily))


def calculate_addl_fulls_pre_dedupe(data_size_tb, retention_level_for_week_full):
    return data_size_tb * max(0, retention_level_for_week_full - 1)


def calculate_addl_fulls(
    data_size_tb, dedupe_rate_adl_fulls, retention_level_for_week_full
):
    sz = calculate_addl_fulls_pre_dedupe(data_size_tb, retention_level_for_week_full)
    return SizePair(pre_dedupe=sz, post_dedupe=sz * (1 - dedupe_rate_adl_fulls))


def calculate_initial_full_pre_dedupe(data_size_tb):
    return data_size_tb


def calculate_initial_full(data_size_tb, dedupe_rate_initial_full):
    sz = calculate_initial_full_pre_dedupe(data_size_tb)
    return SizePair(pre_dedupe=sz, post_dedupe=sz * (1 - dedupe_rate_initial_full))


def calculate_monthly_full_pre_dedupe(
    data_size_tb,
    retention_level_of_monthly_full_backups,
    retention_level_for_week_full,
):
    if retention_level_for_week_full > 0:
        double_count_adj = 0
    else:
        double_count_adj = 1
    pre_dedupe_size = data_size_tb * max(
        0, retention_level_of_monthly_full_backups - double_count_adj
    )
    return pre_dedupe_size


def calculate_monthly_full(
    data_size_tb,
    dedupe_rate_adl_fulls,
    retention_level_of_monthly_full_backups,
    retention_level_for_week_full,
):
    sz = calculate_monthly_full_pre_dedupe(
        data_size_tb,
        retention_level_of_monthly_full_backups,
        retention_level_for_week_full,
    )
    return SizePair(pre_dedupe=sz, post_dedupe=sz * (1 - dedupe_rate_adl_fulls))


def calculate_annual_full_pre_dedupe(
    data_size_tb,
    retention_level_of_annual_full,
    retention_level_of_monthly_full,
):
    if retention_level_of_monthly_full > 0:
        double_count_adj = 0
    else:
        double_count_adj = 1
    pre_dedupe_size = data_size_tb * max(
        0, retention_level_of_annual_full - double_count_adj
    )
    return pre_dedupe_size


def calculate_annual_full(
    data_size_tb,
    dedupe_rate_adl_fulls,
    retention_level_of_annual_full,
    retention_level_of_monthly_full,
):
    sz = calculate_annual_full_pre_dedupe(
        data_size_tb, retention_level_of_annual_full, retention_level_of_monthly_full
    )
    return SizePair(pre_dedupe=sz, post_dedupe=sz * (1 - dedupe_rate_adl_fulls))
