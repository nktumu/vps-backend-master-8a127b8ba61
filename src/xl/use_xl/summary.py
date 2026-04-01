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

from use_core import constants
from use_core import timers
from use_xl.xlutils import fit_sheet, make_all_rows_same_length


def _fill_remaining(row, own_data):
    max_data = len(constants.APPLIANCE_SUMMARY_HEADINGS)
    row.extend([None] * (max_data - own_data))


def _add_data_to_row(row, util, yr, spec, fill_remaining=True):
    for dimension, unit in spec:
        val = util.get(dimension, yr)
        if unit is not None:
            val = val.to_float(unit)
        row.append(val)
    if fill_remaining:
        _fill_remaining(row, len(spec))


def _master_table_data(mresult, fill_remaining=True):
    last_year = mresult.num_years

    result = []
    for domain, _site_name, app_id, mserver in mresult.all_master_servers:
        row_data = [mserver.appliance.config_name, domain, app_id]
        for yr in range(1, 1 + last_year):
            _add_data_to_row(
                row_data,
                mserver.utilization,
                yr,
                [
                    ("absolute_capacity", "GiB"),
                    ("cpu", None),
                    ("memory", None),
                    ("files", None),
                    ("images", None),
                    ("jobs/day", None),
                ],
                fill_remaining,
            )
        result.append(row_data)

    return result


def _appliance_table_data(
    num_years, assigned_appliance, site_name, app_id, fill_remaining=True
):
    util = assigned_appliance.utilization
    row_data = [assigned_appliance.appliance.config_name, site_name, app_id]
    for y in range(1, 1 + num_years):
        _add_data_to_row(
            row_data,
            util,
            y,
            [
                ("absolute_capacity", "TiB"),
                ("capacity", None),
                ("alloc_capacity", "TiB"),
                ("alloc_capacity_pct", None),
                ("mem", None),
                ("cpu", None),
                ("io", None),
                ("nic_pct", None),
            ],
            fill_remaining,
        )
    return row_data


def _nw_table_data(num_years, assigned_appliance, site_name, app_id):
    util = assigned_appliance.utilization
    row_data = [assigned_appliance.appliance.config_name, site_name, app_id]
    for y in range(1, 1 + num_years):
        _add_data_to_row(
            row_data,
            util,
            y,
            [
                ("nic_dr", "MiB"),
                ("DR Transfer GiB/Week", "GiB"),
                ("nic_cloud", "MiB"),
                ("Cloud Transfer GiB/week", "GiB"),
                ("absolute_io", "MiB"),
            ],
        )
    return row_data


def _storage_space_data(num_years, assigned_appliance, site_name, app_id):
    util = assigned_appliance.utilization
    row_data = [assigned_appliance.appliance.config_name, site_name, app_id]
    for y in range(1, 1 + num_years):
        _add_data_to_row(
            row_data,
            util,
            y,
            [
                ("Full Backup", "TiB"),
                ("Incremental Backup", "TiB"),
                ("Size Before Deduplication", "TiB"),
                ("Size After Deduplication", "TiB"),
                ("cloud_gib_months", "GiB"),
                ("cloud_gib_months_worst_case", "GiB"),
            ],
        )
    return row_data


def was_flex_appliance_nw_table_data(mresult):
    last_year = mresult.num_years

    result = []
    for site_name, appliance_id, app in mresult.all_appliances:
        result.append(_nw_table_data(last_year, app, site_name, appliance_id))

    return result


def was_flex_appliance_storage_space_table_headers(mresult):
    return was_table_headers(
        mresult,
        ["Flex Appliance", "Site", "Appliance ID"],
        constants.STORAGE_SPACE_CALCULATION_HEADINGS,
    )


def was_flex_appliance_storage_space_table_data(mresult):
    last_year = mresult.num_years
    result = []
    for site_name, appliance_id, app in mresult.all_appliances:
        result.append(_storage_space_data(last_year, app, site_name, appliance_id))

    return result


def was_flex_appliance_nw_table_headers(mresult):
    return was_table_headers(
        mresult,
        ["Flex Appliance", "Site", "Appliance ID"],
        constants.RESOURCE_NETWORK_HEADINGS,
    )


def was_flex_appliance_table_headers(mresult):
    return was_table_headers(
        mresult,
        ["Flex Appliance", "Site", "Appliance ID"],
        constants.APPLIANCE_SUMMARY_HEADINGS,
    )


def was_flex_appliance_table_data(mresult):
    last_year = mresult.num_years

    result = []
    # write the utilization information for some years in the future
    for site_name, appliance_id, app in mresult.all_appliances:
        result.append(_appliance_table_data(last_year, app, site_name, appliance_id))
    return result


def was_flex_container_table_data(mresult):
    last_year = mresult.num_years

    result = []
    for site_name, appliance_id, app in mresult.all_appliances:
        for container in app.containers:
            row_data = [container.name, site_name, appliance_id]
            for y in range(1, 1 + last_year):
                abs_cap = container.capacity(y, app.appliance)
                row_data.append(abs_cap.to_float("TiB"))
                _fill_remaining(row_data, 1)
                # Leave the section of codes below commented in case
                # users also need those resource usages reported
                #
                # row_data.append(util.get("capacity", y))
                # abs_mem = util.get("absolute_memory", y)
                # row_data.append(app.appliance.memory.utilization([abs_mem]))
                # for dimension in ("cpu", "io", "nic"):
                #     row_data.append(util.get(dimension, y))
                # row_data.append(storage_usage["cloud"][y]["gb_months"].to_float("GiB"))
            result.append(row_data)
    return result


def was_flex_container_table_headers(mresult):
    return was_table_headers(
        mresult,
        ["Container", "Site", "Appliance ID"],
        constants.CONTAINER_SUMMARY_HEADINGS,
    )


def was_table_headers(mresult, prefix, cols):
    last_year = mresult.num_years
    n_dimensions = len(constants.APPLIANCE_SUMMARY_HEADINGS)

    heading_1 = prefix
    heading_2 = [""] * len(prefix)

    for i in range(1, last_year + 1):
        heading_1.append(f"Year {i}")
        for j in range(n_dimensions - 1):
            heading_1.append("")
        for head in cols:
            heading_2.append(head)

    return [heading_1, heading_2]


def was_media_table_headers(mresult):
    return was_table_headers(
        mresult, ["Media Server", "Site", "ID"], constants.APPLIANCE_SUMMARY_HEADINGS
    )


def was_access_table_headers(mresult):
    if not mresult.access_result:
        return []
    return was_table_headers(
        mresult, ["Access Appliance", "Site", "ID"], constants.ACCESS_SUMMARY_HEADINGS
    )


def was_media_nw_table_headers(mresult):
    return was_table_headers(
        mresult, ["Media Server", "Site", "ID"], constants.RESOURCE_NETWORK_HEADINGS
    )


def was_media_storage_space_table_headers(mresult):
    return was_table_headers(
        mresult,
        ["Media Server", "Site", "ID"],
        constants.STORAGE_SPACE_CALCULATION_HEADINGS,
    )


def was_master_table_headers(mresult):
    return was_table_headers(
        mresult,
        [constants.MANAGEMENT_SERVER_DESIGNATION, "Domain", "ID"],
        constants.MASTER_SUMMARY_HEADINGS,
    )


def was_workload_table_headers(mresult):
    return was_table_headers(
        mresult,
        ["Workload", "Site", ""],
        constants.RESOURCE_WORKLOAD_NETWORK_HEADING,
    )


def was_media_table_data(mresult):
    last_year = mresult.num_years

    result = []
    # write the utilization information for some years in the future
    for domain, site_name, app_id, assigned_appliance in mresult.all_media_servers:
        result.append(
            _appliance_table_data(last_year, assigned_appliance, site_name, app_id)
        )
    return result


def was_access_table_data(mresult):
    if not mresult.access_result:
        return []

    last_year = mresult.num_years

    result = []
    for site_name, app_id, assigned_appliance in mresult.access_result.all_appliances:
        row_data = [assigned_appliance.appliance.name, site_name, app_id]
        util = assigned_appliance.utilization
        for y in range(1, 1 + last_year):
            _add_data_to_row(
                row_data, util, y, [("absolute_capacity", "TiB"), ("capacity", None)]
            )
        result.append(row_data)

    return result


def was_media_nw_table_data(mresult):
    last_year = mresult.num_years
    result = []
    for domain, site_name, app_id, assigned_appliance in mresult.all_media_servers:
        result.append(_nw_table_data(last_year, assigned_appliance, site_name, app_id))

    return result


def was_media_storage_space_table_data(mresult):
    last_year = mresult.num_years
    result = []
    for domain, site_name, app_id, assigned_appliance in mresult.all_media_servers:
        result.append(
            _storage_space_data(last_year, assigned_appliance, site_name, app_id)
        )

    return result


def was_master_table_data(mresult):
    return _master_table_data(mresult)


def was_workload_table_data(mresult, workloads):
    last_year = mresult.num_years

    result = []

    used_workloads = set()
    wk_utils = mresult.yoy_utilization_by_workload
    for key, util in sorted(wk_utils.items()):
        (wname, site) = key
        used_workloads.add(wname)
        row_data = [wname, site, None]
        for y in range(1, last_year + 1):
            _add_data_to_row(
                row_data,
                util,
                y,
                [
                    ("workload_capacity", "TiB"),
                    ("nic_workload", "MiB"),
                    ("cloud_gib_months", "GiB"),
                    ("cloud_gib_months_worst_case", "GiB"),
                    ("cloud_gib_per_week", "GiB"),
                ],
                fill_remaining=False,
            )
            row_data.append(workloads[wname][y]["catalog"].to_float("GiB"))
            _fill_remaining(row_data, 6)
        result.append(row_data)

    for wname in sorted(workloads):
        if wname in used_workloads:
            continue
        row_data = [wname, None, None]
        for y in range(1, last_year + 1):
            row_data.extend([None] * 5)
            row_data.append(workloads[wname][y]["catalog"].to_float("GiB"))
            _fill_remaining(row_data, 6)
        result.append(row_data)

    return result


def was_heading_rows(row, tables):
    """returns the row numbers of the tables"""
    heading_rows = []
    for table in tables:
        heading_rows.append(row)
        row += len(table)
        row += 2
    return heading_rows


def was_format_container_table(sheet, num_rows, first_row, skip_cols, num_years):
    n_dimensions = len(constants.APPLIANCE_SUMMARY_HEADINGS)

    last_row = first_row + num_rows - 1
    for yr in range(1, num_years + 1):
        yr_col = skip_cols + (yr - 1) * n_dimensions + 1
        abs_cap_range = sheet.range((first_row, yr_col), (last_row, yr_col))
        cloud_gib_range = sheet.range(
            (first_row, yr_col + n_dimensions - 1),
            (last_row, yr_col + n_dimensions - 1),
        )
        rest_range = sheet.range(
            (first_row, yr_col + 1), (last_row, yr_col + n_dimensions - 2)
        )
        abs_cap_range.number_format = "0.00"
        cloud_gib_range.number_format = "0.00"
        rest_range.number_format = "0.00%"


def was_format_headings(sheet, mresult, heading_rows, prefix_len):
    n_dimensions = len(constants.APPLIANCE_SUMMARY_HEADINGS)

    for idx, r in enumerate(heading_rows):
        common_range = sheet.range((r, 1), (r + 1, 3))
        common_range.color = constants.SUMMARY_COMMON_COLOR
        for yr in range(1, mresult.num_years + 1):
            first_col = prefix_len + (yr - 1) * n_dimensions + 1
            last_col = prefix_len + yr * n_dimensions

            yr_range = sheet.range((r, first_col), (r + 1, last_col))
            yr_color = constants.BY_YEAR_RGB[(yr - 1) % len(constants.BY_YEAR_RGB)]
            yr_range.color = yr_color

            yr_label = sheet.range((r, first_col), (r, last_col))
            yr_label.merge()
        sheet.range(
            (r, 1), (r + 1, prefix_len + mresult.num_years * n_dimensions)
        ).name = f"heading_was_{idx}"


def was_format_media_table(sheet, num_rows, first_row, skip_cols, num_years):
    n_dimensions = len(constants.APPLIANCE_SUMMARY_HEADINGS)

    last_row = first_row + num_rows - 1
    for yr in range(1, num_years + 1):
        yr_col = skip_cols + (yr - 1) * n_dimensions + 1
        abs_cap_range = sheet.range((first_row, yr_col), (last_row, yr_col))
        abs_cap_pct_range = sheet.range((first_row, yr_col + 1), (last_row, yr_col + 1))
        alloc_cap_range = sheet.range((first_row, yr_col + 2), (last_row, yr_col + 2))
        rest_range = sheet.range(
            (first_row, yr_col + 3), (last_row, yr_col + n_dimensions - 1)
        )
        abs_cap_range.number_format = "0.00"
        abs_cap_pct_range.number_format = "0.00%"
        alloc_cap_range.number_format = "0.00"
        rest_range.number_format = "0.00%"


def was_format_media_nw_table(sheet, num_rows, first_row, skip_cols, num_years):
    n_dimensions = len(constants.APPLIANCE_SUMMARY_HEADINGS)

    last_row = first_row + num_rows - 1
    first_col = skip_cols + 1
    last_col = skip_cols + num_years * n_dimensions
    sheet.range((first_row, first_col), (last_row, last_col)).number_format = "0.00"


def was_format_media_storage_space_table(
    sheet, num_rows, first_row, skip_cols, num_years
):
    n_dimensions = len(constants.APPLIANCE_SUMMARY_HEADINGS)

    last_row = first_row + num_rows - 1
    first_col = skip_cols + 1
    last_col = skip_cols + num_years * n_dimensions
    sheet.range((first_row, first_col), (last_row, last_col)).number_format = "0.00"


def was_format_access_table(sheet, num_rows, first_row, skip_cols, num_years):
    if num_rows < 1:
        return

    n_dimensions = len(constants.ACCESS_SUMMARY_HEADINGS)

    last_row = first_row + num_rows - 1
    for yr in range(1, num_years + 1):
        yr_col = skip_cols + (yr - 1) * n_dimensions + 1
        abs_cap_range = sheet.range((first_row, yr_col), (last_row, yr_col))
        rest_range = sheet.range(
            (first_row, yr_col + 1), (last_row, yr_col + n_dimensions - 2)
        )
        abs_cap_range.number_format = "0.00"
        rest_range.number_format = "0.00%"


def was_format_master_table(sheet, num_rows, first_row, skip_cols, num_years):
    n_dimensions = len(constants.APPLIANCE_SUMMARY_HEADINGS)

    last_row = first_row + num_rows - 1
    for yr in range(1, num_years + 1):
        yr_col = skip_cols + (yr - 1) * n_dimensions + 1
        cap_range = sheet.range((first_row, yr_col), (last_row, yr_col))
        resource_range = sheet.range(
            (first_row, yr_col + 2),
            (last_row, yr_col + n_dimensions),
        )
        cpu_range = sheet.range((first_row, yr_col + 1), (last_row, yr_col + 2))
        cap_range.number_format = "0.00"
        resource_range.number_format = "0"
        cpu_range.number_format = "0.00%"


def was_create_names(sheet, table_start, table_end, prefix_len, num_years):
    n_dimensions = len(constants.APPLIANCE_SUMMARY_HEADINGS)

    last_column = prefix_len + n_dimensions * num_years

    # this range covers all of the data, so it can be cleared easily
    # during next run
    sheet.range(
        (table_start, 1),
        (table_end, last_column),
    ).name = "vupc_summary_area"

    # following ranges are for the year-over-year data, so essentially
    # everything except the prefix columns
    start_column = prefix_len + 1
    sheet.range(
        (table_start, start_column),
        (table_end, last_column),
    ).name = "vupc_summary_max_All"
    sheet.range(
        (table_start, start_column),
        (table_end, last_column),
    ).name = "vupc_summary_All"
    for year in range(1, 1 + num_years):
        first_col = start_column + (year - 1) * n_dimensions
        last_col = first_col + n_dimensions - 1
        sheet.range((table_start, first_col), (table_end, last_col)).name = (
            f"vupc_summary_Year{year}"
        )

    sheet.range((3, 2), (3, num_years + 2)).name = "summary_dropdown_years"


def assert_all_rows_same_length(*rowsets):
    lengths = set()
    for rows in rowsets:
        for row in rows:
            lengths.add(len(row))
    assert len(lengths) == 1


@timers.record_time("writing write_appliance_summary_flex")
def write_appliance_summary_flex(summary_sheet, mresult, workload_storage_usage):
    """
    Write a sheet with year by year utilization for resource categories.
    """

    summary_sheet.range("vupc_summary_area").clear()

    last_year = mresult.num_years

    prefix_len = 3

    selector_row = [["All", "All"] + [f"Year {y}" for y in range(1, last_year + 1)]]

    flex_appliance_table = was_flex_appliance_table_headers(
        mresult
    ) + was_flex_appliance_table_data(mresult)
    flex_appliance_nw_table = was_flex_appliance_nw_table_headers(
        mresult
    ) + was_flex_appliance_nw_table_data(mresult)
    flex_appliance_storage_space_table = was_flex_appliance_storage_space_table_headers(
        mresult
    ) + was_flex_appliance_storage_space_table_data(mresult)
    flex_container_table = was_flex_container_table_headers(
        mresult
    ) + was_flex_container_table_data(mresult)
    workload_usage_table = was_workload_table_headers(
        mresult
    ) + was_workload_table_data(mresult, workload_storage_usage)
    access_table = was_access_table_headers(mresult) + was_access_table_data(mresult)
    assert_all_rows_same_length(
        flex_appliance_table,
        flex_appliance_nw_table,
        flex_appliance_storage_space_table,
        flex_container_table,
        workload_usage_table,
        access_table,
    )

    table_start = 5
    heading_rows = was_heading_rows(
        table_start,
        [
            flex_appliance_table,
            flex_appliance_nw_table,
            flex_appliance_storage_space_table,
            flex_container_table,
            workload_usage_table,
            access_table,
        ],
    )
    was_format_headings(summary_sheet, mresult, heading_rows, prefix_len)
    was_format_media_table(
        summary_sheet,
        len(flex_appliance_table) - 2,
        heading_rows[0] + 2,
        prefix_len,
        mresult.num_years,
    )
    was_format_media_nw_table(
        summary_sheet,
        len(flex_appliance_nw_table) - 2,
        heading_rows[1] + 2,
        prefix_len,
        mresult.num_years,
    )
    was_format_media_storage_space_table(
        summary_sheet,
        len(flex_appliance_storage_space_table) - 2,
        heading_rows[2] + 2,
        prefix_len,
        mresult.num_years,
    )
    was_format_media_table(
        summary_sheet,
        len(flex_container_table) - 2,
        heading_rows[3] + 2,
        prefix_len,
        mresult.num_years,
    )
    was_format_media_nw_table(
        summary_sheet,
        len(workload_usage_table) - 2,
        heading_rows[4] + 2,
        prefix_len,
        mresult.num_years,
    )
    was_format_access_table(
        summary_sheet,
        len(access_table) - 2,
        heading_rows[5] + 2,
        prefix_len,
        mresult.num_years,
    )

    result = (
        selector_row
        + [[]]
        + flex_appliance_table
        + [[], []]
        + flex_appliance_nw_table
        + [[], []]
        + flex_appliance_storage_space_table
        + [[], []]
        + flex_container_table
        + [[], []]
        + workload_usage_table
        + [[], []]
        + access_table
    )
    make_all_rows_same_length(result)
    summary_sheet.range("A3").value = result

    was_create_names(
        summary_sheet, table_start, 3 + len(result) - 1, prefix_len, mresult.num_years
    )

    fit_sheet(summary_sheet)


@timers.record_time("writing write_appliance_summary")
def write_appliance_summary(summary_sheet, mresult, workload_storage_usage):
    """
    Write a sheet with year by year utilization for resource categories.
    """

    summary_sheet.range("vupc_summary_area").clear()

    last_year = mresult.num_years

    prefix_len = 3

    selector_row = [["All", "All"] + [f"Year {y}" for y in range(1, last_year + 1)]]

    media_table = was_media_table_headers(mresult) + was_media_table_data(mresult)
    media_nw_table = was_media_nw_table_headers(mresult) + was_media_nw_table_data(
        mresult
    )
    media_storage_space_table = was_media_storage_space_table_headers(
        mresult
    ) + was_media_storage_space_table_data(mresult)
    master_table = was_master_table_headers(mresult) + was_master_table_data(mresult)
    workload_usage_table = was_workload_table_headers(
        mresult
    ) + was_workload_table_data(mresult, workload_storage_usage)
    access_table = was_access_table_headers(mresult) + was_access_table_data(mresult)
    assert_all_rows_same_length(
        media_table,
        media_nw_table,
        media_storage_space_table,
        master_table,
        workload_usage_table,
        access_table,
    )

    table_start = 5
    heading_rows = was_heading_rows(
        table_start,
        [
            media_table,
            media_nw_table,
            media_storage_space_table,
            master_table,
            workload_usage_table,
            access_table,
        ],
    )
    was_format_headings(summary_sheet, mresult, heading_rows, prefix_len)
    was_format_media_table(
        summary_sheet,
        len(media_table) - 2,
        heading_rows[0] + 2,
        prefix_len,
        mresult.num_years,
    )
    was_format_media_nw_table(
        summary_sheet,
        len(media_nw_table) - 2,
        heading_rows[1] + 2,
        prefix_len,
        mresult.num_years,
    )
    was_format_media_storage_space_table(
        summary_sheet,
        len(media_storage_space_table) - 2,
        heading_rows[2] + 2,
        prefix_len,
        mresult.num_years,
    )
    was_format_master_table(
        summary_sheet,
        len(master_table) - 2,
        heading_rows[3] + 2,
        prefix_len,
        mresult.num_years,
    )
    was_format_media_nw_table(
        summary_sheet,
        len(workload_usage_table) - 2,
        heading_rows[4] + 2,
        prefix_len,
        mresult.num_years,
    )
    was_format_access_table(
        summary_sheet,
        len(access_table) - 2,
        heading_rows[5] + 2,
        prefix_len,
        mresult.num_years,
    )

    result = (
        selector_row
        + [[]]
        + media_table
        + [[], []]
        + media_nw_table
        + [[], []]
        + media_storage_space_table
        + [[], []]
        + master_table
        + [[], []]
        + workload_usage_table
        + [[], []]
        + access_table
    )
    make_all_rows_same_length(result)
    summary_sheet.range("A3").value = result

    was_create_names(
        summary_sheet, table_start, 3 + len(result) - 1, prefix_len, mresult.num_years
    )

    fit_sheet(summary_sheet)


def raw_appliance_media_summary_headers(mresult):
    headers = ["Media Server", "Site", "ID"]

    for i in range(mresult.num_years):
        headings = [
            f"Year {i + 1} - {heading}"
            for heading in constants.RAW_APPLIANCE_SUMMARY_HEADINGS
        ]
        headers.extend(headings)

    return [headers]


def raw_appliance_master_summary_headers(mresult):
    headers = ["Master Server", "Site", "ID"]
    appl_master_summary_headings = constants.MASTER_SUMMARY_HEADINGS[:6]
    for i in range(mresult.num_years):
        headings = [
            f"Year {i + 1} - {heading}" for heading in appl_master_summary_headings
        ]
        headers.extend(headings)

    return [headers]


def raw_appliance_media_summary_sheet_data(mresult):
    """
    Write a sheet with year by year utilization for resource categories.
    """
    last_year = mresult.num_years

    result = []
    # write the utilization information for some years in the future
    for domain, site_name, app_id, assigned_appliance in mresult.all_media_servers:
        result.append(
            _raw_appliance_media_table_data(
                last_year, assigned_appliance, site_name, app_id
            )
        )
    return result


def raw_appliance_master_table_data(mresult):
    return _master_table_data(mresult, fill_remaining=False)


def _raw_appliance_media_table_data(num_years, assigned_appliance, site_name, app_id):
    util = assigned_appliance.utilization
    row_data = [
        assigned_appliance.appliance.config_name,
        site_name,
        app_id,
    ]
    for y in range(1, 1 + num_years):
        _add_data_to_row(
            row_data,
            util,
            y,
            [
                ("absolute_capacity", "TiB"),
                ("capacity", None),
                ("alloc_capacity", "TiB"),
                ("alloc_capacity_pct", None),
                ("mem", None),
                ("cpu", None),
                ("io", None),
                ("nic_pct", None),
                ("nic_dr", "MiB"),
                ("DR Transfer GiB/Week", "GiB"),
                ("nic_cloud", "MiB"),
                ("Cloud Transfer GiB/week", "GiB"),
                ("absolute_io", "MiB"),
                ("Full Backup", "TiB"),
                ("Incremental Backup", "TiB"),
                ("Size Before Deduplication", "TiB"),
                ("Size After Deduplication", "TiB"),
                ("cloud_gib_months", "GiB"),
                ("cloud_gib_months_worst_case", "GiB"),
            ],
        )
    return row_data


@timers.record_time("writing write_raw_appliance_summary")
def write_raw_appliance_summary(summary_sheet, mresult):
    """
    Write a sheet with year by year utilization of each appliance for resource categories.
    """

    media_table = raw_appliance_media_summary_headers(
        mresult
    ) + raw_appliance_media_summary_sheet_data(mresult)
    master_table = raw_appliance_master_summary_headers(
        mresult
    ) + raw_appliance_master_table_data(mresult)

    result = media_table + [[], []] + master_table

    make_all_rows_same_length(result)
    summary_sheet.range("A2").value = result

    fit_sheet(summary_sheet)
    media_table_last_row = len(media_table) + 1

    master_table_last_row = media_table_last_row + 2 + len(master_table)

    num_of_media_table_columns = len(raw_appliance_media_summary_headers(mresult)[0])
    num_of_master_table_columns = len(raw_appliance_master_summary_headers(mresult)[0])

    summary_sheet.range(
        (2, 1), (media_table_last_row, num_of_media_table_columns)
    ).name = "raw_appliance_media_table"
    summary_sheet.range(
        (media_table_last_row + 3, 1),
        (master_table_last_row, num_of_master_table_columns),
    ).name = "raw_appliance_master_table"


def flex_raw_appliance_summary_headers(mresult):
    headers = ["Flex Appliance", "Site", "ID"]
    flex_appl_summary_headings = (
        constants.RESOURCE_ABSOLUTE_HEADINGS
        + constants.RESOURCE_PERCENT_HEADINGS
        + constants.RESOURCE_NETWORK_HEADINGS[:5]
        + constants.STORAGE_SPACE_CALCULATION_HEADINGS[:6]
    )
    for i in range(mresult.num_years):
        headings = [
            f"Year {i + 1} - {heading}" for heading in flex_appl_summary_headings
        ]
        headers.extend(headings)

    return [headers]


def flex_raw_appliance_summary_sheet_data(mresult):
    last_year = mresult.num_years

    result = []
    # write the utilization information for some years in the future
    for site_name, appliance_id, app in mresult.all_appliances:
        util = app.utilization
        row_data = [app.appliance.config_name, site_name, appliance_id]
        for y in range(1, 1 + last_year):
            _add_data_to_row(
                row_data,
                util,
                y,
                [
                    ("absolute_capacity", "TiB"),
                    ("capacity", None),
                    ("alloc_capacity", "TiB"),
                    ("alloc_capacity_pct", None),
                    ("mem", None),
                    ("cpu", None),
                    ("io", None),
                    ("nic_pct", None),
                    ("nic_dr", "MiB"),
                    ("DR Transfer GiB/Week", "GiB"),
                    ("nic_cloud", "MiB"),
                    ("Cloud Transfer GiB/week", "GiB"),
                    ("absolute_io", "MiB"),
                    ("Full Backup", "TiB"),
                    ("Incremental Backup", "TiB"),
                    ("Size Before Deduplication", "TiB"),
                    ("Size After Deduplication", "TiB"),
                    ("cloud_gib_months", "GiB"),
                    ("cloud_gib_months_worst_case", "GiB"),
                ],
                fill_remaining=False,
            )
        result.append(row_data)
    return result


@timers.record_time("writing write_raw_appliance_summary")
def write_raw_appliance_summary_flex(summary_sheet, mresult):
    """
    Write a sheet with year by year utilization of each appliance for resource categories.
    """

    result = flex_raw_appliance_summary_headers(
        mresult
    ) + flex_raw_appliance_summary_sheet_data(mresult)

    make_all_rows_same_length(result)
    summary_sheet.range("A2").value = result
    fit_sheet(summary_sheet)
    flex_appliance_table_last_row = len(result) + 1
    num_of_flex_appliance_table_columns = len(
        flex_raw_appliance_summary_headers(mresult)[0]
    )
    summary_sheet.range(
        (2, 1), (flex_appliance_table_last_row, num_of_flex_appliance_table_columns)
    ).name = "flex_raw_appliance_table"
