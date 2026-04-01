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

from use_core import (
    appliance,
    constants,
    media_packing,
    model_basis,
    packing,
    settings,
    utils,
    workload,
)
from use_core.appliance import get_model_values
from use_core.utils import DEFAULT_TIMEFRAME, DEFAULT_WORST_CASE_CLOUD_FACTOR


def hack_total_current(workload):
    """Hacks total_current value in workload sizes as a temporary measure."""

    for entry in workload.yearly_sizes:
        entry["total_current"] = entry["size"]


def pack(
    workloads,
    appliance_spec,
    window_sizes,
    site,
    progress_callback=None,
    skip_generate_task=False,
    timeframe=None,
    pack_flex=False,
):
    if timeframe is not None:
        timeframe_obj = timeframe
    else:
        timeframe_obj = utils.TimeFrame(
            num_years=constants.FIRST_EXTENSION, planning_year=constants.PLANNING_YEAR
        )
    workload.calculate_capacity_all_workloads(
        workloads, timeframe_obj, utils.DEFAULT_WORST_CASE_CLOUD_FACTOR
    )
    ctx = media_packing.SizerContext(
        workloads=workloads,
        appliance_spec=appliance_spec,
        window_sizes=window_sizes,
        site_name=site,
        progress_cb=progress_callback,
        generate_tasks=not skip_generate_task,
        timeframe=timeframe_obj,
        pack_flex=pack_flex,
    )
    return ctx.pack()


POLICY_TYPE_RETENTIONS = {
    "local": {
        "incremental_retention_days": 30,
        "weekly_full_retention": 4,
        "monthly_retention": 6,
        "annually_retention": 0,
        "incremental_retention_dr": 0,
        "weekly_full_retention_dr": 0,
        "monthly_full_retention_dr": 0,
        "annually_full_retention_dr": 0,
        "incremental_retention_cloud": 0,
        "weekly_full_retention_cloud": 0,
        "monthly_full_retention_cloud": 0,
        "annually_full_retention_cloud": 0,
        "full_backup_per_week": 1,
        "incremental_per_week": 5,
    },
    "local+daily-fulls": {
        "incremental_retention_days": 30,
        "weekly_full_retention": 4,
        "monthly_retention": 6,
        "annually_retention": 0,
        "incremental_retention_dr": 0,
        "weekly_full_retention_dr": 0,
        "monthly_full_retention_dr": 0,
        "annually_full_retention_dr": 0,
        "incremental_retention_cloud": 0,
        "weekly_full_retention_cloud": 0,
        "monthly_full_retention_cloud": 0,
        "annually_full_retention_cloud": 0,
        "full_backup_per_week": 7,
        "incremental_per_week": 5,
    },
    "local+0fulls": {
        "incremental_retention_days": 30,
        "weekly_full_retention": 4,
        "monthly_retention": 6,
        "annually_retention": 0,
        "incremental_retention_dr": 0,
        "weekly_full_retention_dr": 0,
        "monthly_full_retention_dr": 0,
        "annually_full_retention_dr": 0,
        "incremental_retention_cloud": 0,
        "weekly_full_retention_cloud": 0,
        "monthly_full_retention_cloud": 0,
        "annually_full_retention_cloud": 0,
        "full_backup_per_week": 0,
        "incremental_per_week": 5,
    },
    "2wk-local": {
        "incremental_retention_days": 14,
        "weekly_full_retention": 2,
        "monthly_retention": 0,
        "annually_retention": 0,
        "incremental_retention_dr": 0,
        "weekly_full_retention_dr": 0,
        "monthly_full_retention_dr": 0,
        "annually_full_retention_dr": 0,
        "incremental_retention_cloud": 0,
        "weekly_full_retention_cloud": 0,
        "monthly_full_retention_cloud": 0,
        "annually_full_retention_cloud": 0,
        "full_backup_per_week": 1,
        "incremental_per_week": 5,
    },
    "local+double-dr": {
        "incremental_retention_days": 30,
        "weekly_full_retention": 4,
        "monthly_retention": 6,
        "annually_retention": 0,
        "incremental_retention_dr": 30,
        "weekly_full_retention_dr": 8,
        "monthly_full_retention_dr": 12,
        "annually_full_retention_dr": 0,
        "incremental_retention_cloud": 0,
        "weekly_full_retention_cloud": 0,
        "monthly_full_retention_cloud": 0,
        "annually_full_retention_cloud": 0,
        "full_backup_per_week": 1,
        "incremental_per_week": 5,
    },
    "local+dr+0incr": {
        "incremental_retention_days": 30,
        "weekly_full_retention": 4,
        "monthly_retention": 6,
        "annually_retention": 0,
        "incremental_retention_dr": 0,
        "weekly_full_retention_dr": 4,
        "monthly_full_retention_dr": 6,
        "annually_full_retention_dr": 0,
        "incremental_retention_cloud": 0,
        "weekly_full_retention_cloud": 0,
        "monthly_full_retention_cloud": 0,
        "annually_full_retention_cloud": 0,
        "full_backup_per_week": 7,
        "incremental_per_week": 0,
    },
    "local+access": {
        "incremental_retention_days": 30,
        "weekly_full_retention": 4,
        "monthly_retention": 6,
        "annually_retention": 0,
        "incremental_retention_dr": 0,
        "weekly_full_retention_dr": 0,
        "monthly_full_retention_dr": 0,
        "annually_full_retention_dr": 0,
        "incremental_retention_cloud": 0,
        "weekly_full_retention_cloud": 24,
        "monthly_full_retention_cloud": 24,
        "annually_full_retention_cloud": 7,
        "full_backup_per_week": 1,
        "incremental_per_week": 5,
    },
    "0local+access-long": {
        "incremental_retention_days": 0,
        "weekly_full_retention": 0,
        "monthly_retention": 0,
        "annually_retention": 0,
        "incremental_retention_dr": 0,
        "weekly_full_retention_dr": 0,
        "monthly_full_retention_dr": 0,
        "annually_full_retention_dr": 0,
        "incremental_retention_cloud": 0,
        "weekly_full_retention_cloud": 24,
        "monthly_full_retention_cloud": 24,
        "annually_full_retention_cloud": 10,
        "full_backup_per_week": 1,
        "incremental_per_week": 5,
    },
    "local-4wk+access-5yr": {
        "incremental_retention_days": 0,
        "weekly_full_retention": 4,
        "monthly_retention": 0,
        "annually_retention": 0,
        "incremental_retention_dr": 0,
        "weekly_full_retention_dr": 0,
        "monthly_full_retention_dr": 0,
        "annually_full_retention_dr": 0,
        "incremental_retention_cloud": 0,
        "weekly_full_retention_cloud": 5 * 52,
        "monthly_full_retention_cloud": 0,
        "annually_full_retention_cloud": 0,
        "full_backup_per_week": 1,
        "incremental_per_week": 0,
    },
    "local+access-annualonly": {
        "incremental_retention_days": 30,
        "weekly_full_retention": 4,
        "monthly_retention": 6,
        "annually_retention": 0,
        "incremental_retention_dr": 0,
        "weekly_full_retention_dr": 0,
        "monthly_full_retention_dr": 0,
        "annually_full_retention_dr": 0,
        "incremental_retention_cloud": 0,
        "weekly_full_retention_cloud": 0,
        "monthly_full_retention_cloud": 0,
        "annually_full_retention_cloud": 10,
        "full_backup_per_week": 1,
        "incremental_per_week": 5,
    },
    "local+dr+ltr_identical": {
        "incremental_retention_days": 30,
        "weekly_full_retention": 4,
        "monthly_retention": 6,
        "annually_retention": 0,
        "incremental_retention_dr": 30,
        "weekly_full_retention_dr": 4,
        "monthly_full_retention_dr": 5,
        "annually_full_retention_dr": 0,
        "incremental_retention_cloud": 30,
        "weekly_full_retention_cloud": 4,
        "monthly_full_retention_cloud": 6,
        "annually_full_retention_cloud": 0,
        "full_backup_per_week": 1,
        "incremental_per_week": 5,
    },
}

POLICY_TYPE_LOCATIONS = {
    "local": {
        "region": "DC",
        "dr_dest": None,
        "backup_location_policy": "local only",
    },
    "local+dr": {
        "region": "DC",
        "dr_dest": "SF",
        "backup_location_policy": "local+dr",
    },
    "local+ltr": {
        "region": "DC",
        "dr_dest": None,
        "backup_location_policy": "local+ltr",
    },
    "local+dr+ltr": {
        "region": "DC",
        "dr_dest": "SF",
        "backup_location_policy": "local+dr+ltr",
    },
    "ltr-only": {"region": "DC", "dr_dest": None, "backup_location_policy": "ltr only"},
}

POLICY_TYPE_MISC = {
    "local": {
        "appliance_front_end_network": appliance.NetworkType.auto,
        "appliance_dr_network": appliance.NetworkType.auto,
        "appliance_ltr_network": appliance.NetworkType.auto,
        "log_backup_incremental_level": "differential",
        "incremental_backup_level": "differential",
        "log_backup_frequency_minutes": 15,
        "min_size_dup_jobs": utils.Size.assume_unit(8, "GB"),
        "max_size_dup_jobs": utils.Size.assume_unit(100, "GB"),
        "force_small_dup_jobs": 30,
    },
    "25gbe": {
        "appliance_front_end_network": appliance.NetworkType.twentyfive_gbe_sfp,
        "appliance_dr_network": appliance.NetworkType.auto,
        "appliance_ltr_network": appliance.NetworkType.auto,
        "log_backup_incremental_level": "differential",
        "incremental_backup_level": "differential",
        "log_backup_frequency_minutes": 15,
        "min_size_dup_jobs": utils.Size.assume_unit(8, "GB"),
        "max_size_dup_jobs": utils.Size.assume_unit(100, "GB"),
        "force_small_dup_jobs": 30,
    },
}


def workload_on_demand(
    name,
    workload_type,
    fetb,
    clients,
    policy_type="local",
    misc_policy=None,
    locations_policy=None,
    retentions_policy=None,
    overrides=None,
):
    wspec = {
        "workload_name": name,
        "workload_type": workload_type,
        "workload_size": utils.Size.assume_unit(fetb / clients, "TB"),
        "number_of_clients": clients,
        "domain": "Domain-1",
        "storage_lifecycle_policy": policy_type,
        "workload_isolation": False,
        "universal_share": False,
    }

    dwa = model_basis.default_workload_attributes_data_dict()
    dwa_attrs = dwa[workload_type]
    wspec.update(dwa_attrs)
    if locations_policy is None:
        locations_policy = policy_type
    wspec.update(POLICY_TYPE_LOCATIONS[locations_policy])
    if retentions_policy is None:
        retentions_policy = policy_type
    wspec.update(POLICY_TYPE_RETENTIONS[retentions_policy])
    if misc_policy is None:
        misc_policy = policy_type
    wspec.update(POLICY_TYPE_MISC[misc_policy])
    if overrides is not None:
        wspec.update(overrides)

    w = workload.Workload(wspec)
    default_timeframe = utils.TimeFrame(
        num_years=constants.FIRST_EXTENSION, planning_year=constants.PLANNING_YEAR
    )
    w.calculate_capacity(default_timeframe)
    return w


def default_rightsize(_site):
    return True


def no_rightsize(_site):
    return False


def make_sizer_context(
    test_per_appliance_safety_margins,
    workloads,
    window_sizes,
    timeframe=utils.DEFAULT_TIMEFRAME,
    **kwargs,
):
    visible_models = list(get_model_values().keys())
    appliance_selection_criteria = packing.ApplianceSelectionCriteria(
        [], visible_models, test_per_appliance_safety_margins
    )
    sizer_settings = settings.Settings()
    sizer_settings.timeframe = timeframe
    sizer_settings.master_sizing = True
    if "ltr_target" in kwargs:
        sizer_settings.ltr_type = kwargs.pop("ltr_target")
    if "excess_cloud_storage" in kwargs:
        sizer_settings.worst_case_cloud_factor = kwargs.pop("excess_cloud_storage")
    if "master_sizing" in kwargs:
        sizer_settings.master_sizing = kwargs.pop("master_sizing")
    ctx = packing.SizerContext(
        appliance_selection_criteria,
        workloads=workloads,
        window_sizes=window_sizes,
        sizer_settings=sizer_settings,
    )
    for key, value in kwargs.items():
        setattr(ctx, key, value)

    return ctx


def make_generate_tasks(
    workloads,
    domain_name,
    site_names,
    appliance_spec,
    window_sizes,
    time_frame=DEFAULT_TIMEFRAME,
):
    workload.calculate_capacity_all_workloads(
        workloads, time_frame, DEFAULT_WORST_CASE_CLOUD_FACTOR
    )
    for w in workloads:
        w.generate_tasks(
            domain_name, site_names, appliance_spec, window_sizes, time_frame
        )
