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

from copy import deepcopy
import enum
import json
import logging
import uuid
from collections import defaultdict
from http import HTTPStatus

from flask import Response, abort, make_response
from flask import jsonify
from use_core import constants, model_basis, packing, settings, utils
from use_core.appliance import NetworkType, get_model_values
from use_core.packing import SiteAssignment
from use_core.workload import (
    Workload,
    get_site_hints_from_workloads,
    calculate_capacity_all_workloads,
)
from use_server.services import schema_service, celery_service
from use_server.tasks import packing_task

logger = logging.getLogger(__name__)


class SizeRequestMode(enum.Enum):
    Sync = enum.auto()
    Async = enum.auto()


def report_error(http_status: int = 500, errors: list[str] = [], location: str = ""):
    if type(errors) is not list:
        errors = list(errors)
    logger.error("status %i from %s: %s", http_status, location, errors)
    abort(
        make_response(
            (
                {"errors": errors, "origin": location},
                http_status,
            )
        )
    )


def is_valid_request(req_data):
    errors = schema_service.list_validation_errors(req_data, "size_request")
    if errors:
        report_error(HTTPStatus.UNPROCESSABLE_ENTITY, errors, "request validation")


def is_request_supported(req_data):
    def is_multifamily_request(req_data):
        # if family is not specified, the issue is caught in appliance selection
        set_of_families = {
            pref.get("appliance_family") for pref in req_data.get("site_preferences")
        }
        if len(set_of_families) != 1:
            return "All appliances must be the same family"

    def is_unsupported_family_request(req_data):
        supported_families = {
            "flex",
            # "flexscale", # flexscale support not yet implemented
            "nba",
        }
        set_of_families = {
            pref.get("appliance_family")
            for pref in req_data.get("site_preferences")
            if pref.get("appliance_family") is not None
        }
        if unsupported_families := set_of_families - supported_families:
            return f"Requested appliance family not supported: {unsupported_families}"

    def is_planned_beyond_size_request(req_data):
        horizon = req_data.get("horizon")
        if horizon.get("planning_year") > horizon.get("num_years"):
            return (
                f"Planning year is beyond the sizing years requested."
                f" planning_year: {horizon.get('planning_year')}"
                f" num_years: {horizon.get('num_years')}"
            )

    errors = [
        unsupported_feature(req_data)
        for unsupported_feature in [
            is_multifamily_request,
            is_unsupported_family_request,
            is_planned_beyond_size_request,
        ]
        if unsupported_feature(req_data)
    ]
    if errors:
        report_error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, errors, "is_request_supported")


def solve(safety_margins, sites, workload_list, settings):
    logger.debug("solve: settings %s, workload_list %s ", settings, workload_list)
    logger.debug(
        "solve: worst_case_cloud_factor %s,timeframe  %s",
        settings.worst_case_cloud_factor,
        settings.timeframe,
    )
    visible_models_all = list(get_model_values().keys())

    appliance_selection_criteria = packing.ApplianceSelectionCriteria(
        sites, visible_models_all, safety_margins
    )

    ctx = packing.SizerContext(
        appliance_selection_criteria,
        workloads=workload_list,
        window_sizes=model_basis.window_sizes,
        # API supports appliance family for each site, but core library requires one family
        # This is error checked in is_multifamily_request()
        pack_flex=sites[0]["appliance_family"] == "flex",
        sizer_settings=settings,
    )
    mresult = ctx.pack(retry_on_error=True)
    response_dict = dict()
    response_dict["site_assignments"] = site_assignments_as_dict(mresult)
    response_dict["windows"] = vars(mresult.window_sizes)
    response_dict["horizon"] = {
        "num_years": settings.timeframe.num_years,
        "planning_year": settings.timeframe.planning_year,
    }
    if getattr(settings, "ltr_type", None):
        if getattr(mresult, "access_result", None):
            access_appliances = get_access_appliance_summary(mresult)
            response_dict["ltr_appliances"] = access_appliances

    return response_dict


def fill_default_site_prefs(
    sites: set, site_hints: dict, site_preferences: list = []
) -> list:
    for site_key in sites:
        # if no prefs have been given for a required site, add site to list
        sites_with_prefs = ((s["domain"], s["site_name"]) for s in site_preferences)
        if site_key not in sites_with_prefs:
            domain_name, site_name = site_key
            site_preferences.append({"domain": domain_name, "site_name": site_name})

    return [
        {
            "domain_name": pref[
                "domain"
            ],  # required, but enforced by schema validation
            "site_name": pref[
                "site_name"
            ],  # required, but enforced by schema validation
            "appliance_bandwidth_cc": pref.get(
                "appliance_bandwidth_cc",
                utils.Size.from_ratio(constants.DEFAULT_CC_BW, 8, "GiB"),
            ),
            "software_version": pref.get(
                "software_version", constants.DEFAULT_SOFTWARE_VERSION_STRING
            ),
            "site_network_type": pref.get(
                "site_network_type", constants.DEFAULT_SITE_NETWORK_TYPE
            ),
            "wan_network_type": pref.get("wan_network_type"),
            "cc_network_type": pref.get("cc_network_type"),
            "appliance_family": pref.get(
                "appliance_family", constants.DEFAULT_APPLIANCE_FAMILY
            ),
            "appliance_name": pref.get("appliance_config"),
            "appliance_model": pref.get("appliance_model"),
            "site_hints": pref.get(
                "site_hints", site_hints[(pref["domain"], pref["site_name"])]
            ),
        }
        for pref in site_preferences
    ]


def size_data(req_data, req_mode: SizeRequestMode):
    response = [{"message": " Incorrect Request Payload"}]

    min_size_dup_jobs = utils.Size.assume_unit(
        model_basis.default_slp_data["min_size_dup_jobs"], "GB"
    )
    max_size_dup_jobs = utils.Size.assume_unit(
        model_basis.default_slp_data["max_size_dup_jobs"], "GB"
    )
    force_small_dup_jobs = model_basis.default_slp_data["force_small_dup_jobs"]

    if "workloads" not in req_data:
        return Response(
            response=json.dumps(response), status=400, mimetype="application/json"
        )

    workloads = req_data["workloads"]

    num_years_val = req_data.get("horizon", {}).get(
        "num_years", constants.FIRST_EXTENSION
    )
    planning_year_val = req_data.get("horizon", {}).get(
        "planning_year", constants.PLANNING_YEAR
    )

    if (
        num_years_val <= 0
        or planning_year_val <= 0
        or num_years_val < planning_year_val
    ):
        response = {"message": " Incorrect horizon value "}
        return Response(
            response=json.dumps(response), status=400, mimetype="application/json"
        )

    settings_obj = settings.Settings()
    timeframe = utils.TimeFrame(
        num_years=num_years_val, planning_year=planning_year_val
    )
    settings_obj.timeframe = timeframe
    settings_obj.master_sizing = req_data.get("settings", {}).get(
        "primary_server_sizing", False
    )
    settings_obj.ltr_type = settings.LtrType.from_string(
        req_data.get("settings", {}).get("cloud_target_type", "Access")
    )
    settings_obj.resource_tip = req_data.get("settings", {}).get(
        "display_resource_tip", True
    )
    settings_obj.worst_case_cloud_factor = constants.MSDP_CLOUD_WORST_CASE_FACTOR

    safety_margins = model_basis.get_model_limits()
    if req_data.get("safety_considerations"):
        for dct in req_data["safety_considerations"]:
            mdl = dct["model"]
            for fld in dct:
                safety_margins[mdl][fld] = dct[fld]
    sites = set()

    reference_workload_attr_dict = model_basis.default_workload_attributes_data_dict()

    workload_list = []
    for each_workload in workloads:
        slp = each_workload["slp"]

        slp.setdefault("local_retention", {})
        slp.setdefault("dr_retention", {})
        slp.setdefault("cloud_retention", {})
        slp.setdefault("backup_intervals", {})
        num_clients: int = each_workload["number_of_clients"]
        workload_size = utils.Size.from_ratio(
            each_workload["size"]["value"], num_clients, each_workload["size"]["unit"]
        )
        domain = slp["domain"]
        sitename = slp.get("site_name", None)
        sites.add((domain, sitename))

        dr_dests = slp.get("dr_dest", [])
        for dr_dest in dr_dests:
            sites.add((domain, dr_dest))

        if "preset_type_id" in each_workload.keys():
            workload_type = each_workload["preset_type_id"]
        else:
            # TODO: Need to assign each_workload["custom_workload_type"] to something
            pass

        each_workload = {
            "workload_name": each_workload["name"],
            "workload_type": workload_type,
            "number_of_clients": num_clients,
            "workload_size": workload_size,
            "storage_lifecycle_policy": slp["name"],
            "workload_isolation": each_workload.get(
                "workload_isolation", constants.DEFAULT_WORKLOAD_ISOLATION
            ),
            "universal_share": each_workload.get(
                "universal_share", constants.DEFAULT_UNIVERSAL_SHARE
            ),
            "domain": domain,
            "region": sitename,
            "dr_dest": dr_dests[0] if dr_dests else None,
            "backup_location_policy": slp["backup_type"].lower(),
            "incremental_retention_days": slp["local_retention"].get(
                "incremental", constants.DEFAULT_INCREMENTAL_RETENTION
            ),
            "weekly_full_retention": slp["local_retention"].get(
                "weekly_full", constants.DEFAULT_WEEKLY_FULL_RETENTION
            ),
            "monthly_retention": slp["local_retention"].get(
                "monthly_full", constants.DEFAULT_MONTHLY_FULL_RETENTION
            ),
            "annually_retention": slp["local_retention"].get(
                "annual_full", constants.DEFAULT_ANNUAL_FULL_RETENTION
            ),
            "incremental_retention_dr": slp["dr_retention"].get(
                "incremental", constants.DEFAULT_INCREMENTAL_RETENTION
            ),
            "incremental_retention_cloud": slp["cloud_retention"].get(
                "incremental", constants.DEFAULT_INCREMENTAL_RETENTION
            ),
            "weekly_full_retention_dr": slp["dr_retention"].get(
                "weekly_full", constants.DEFAULT_WEEKLY_FULL_RETENTION
            ),
            "weekly_full_retention_cloud": slp["cloud_retention"].get(
                "weekly_full", constants.DEFAULT_WEEKLY_FULL_RETENTION
            ),
            "monthly_full_retention_dr": slp["dr_retention"].get(
                "monthly_full", constants.DEFAULT_MONTHLY_FULL_RETENTION
            ),
            "monthly_full_retention_cloud": slp["cloud_retention"].get(
                "monthly_full", constants.DEFAULT_MONTHLY_FULL_RETENTION
            ),
            "annually_full_retention_dr": slp["dr_retention"].get(
                "annual_full", constants.DEFAULT_ANNUAL_FULL_RETENTION
            ),
            "annually_full_retention_cloud": slp["cloud_retention"].get(
                "annual_full", constants.DEFAULT_ANNUAL_FULL_RETENTION
            ),
            "log_backup_frequency_minutes": slp["backup_intervals"].get(
                "log_backup_interval", constants.DEFAULT_LOG_BACKUP_INTERVAL
            ),
            "incremental_per_week": slp["backup_intervals"].get(
                "incrementals_per_week", constants.DEFAULT_INCREMENTALS_PER_WEEK
            ),
            "full_backup_per_week": slp["backup_intervals"].get(
                "fulls_per_week", constants.DEFAULT_FULLS_PER_WEEK
            ),
            "incremental_backup_level": "differential",
            "log_backup_incremental_level": "differential",
            "min_size_dup_jobs": min_size_dup_jobs,
            "max_size_dup_jobs": max_size_dup_jobs,
            "force_small_dup_jobs": force_small_dup_jobs,
            "appliance_front_end_network": NetworkType(
                slp.get("appliance_frontend_network", NetworkType.auto)
            ),
            "appliance_dr_network": NetworkType(
                slp.get("appliance_dr_network", NetworkType.auto)
            ),
            "appliance_ltr_network": NetworkType(
                slp.get("appliance_ltr_network", NetworkType.auto)
            ),
        }
        reference_workload_attr = reference_workload_attr_dict.get(workload_type)
        each_workload.update(reference_workload_attr)

        w = Workload(each_workload)

        workload_list.append(w)

    calculate_capacity_all_workloads(
        workload_list, settings_obj.timeframe, settings_obj.worst_case_cloud_factor
    )
    pack_flex = True
    for site_pref in req_data.get("site_preferences", []):
        if site_pref["appliance_family"] != "flex":
            pack_flex = False
    active_sites = get_site_hints_from_workloads(
        workload_list, planning_year_val, sizing_flex=pack_flex
    )
    site_preferences = fill_default_site_prefs(
        sites, active_sites, req_data.get("site_preferences")
    )

    if req_mode == SizeRequestMode.Sync:
        try:
            return jsonify(
                solve(
                    safety_margins,
                    site_preferences,
                    workload_list,
                    settings_obj,
                )
            )
        except Exception as err:
            report_error(HTTPStatus.INTERNAL_SERVER_ERROR, [str(err)], "solve")
    else:
        # generate a unique job id used for querying job status
        job_id = str(uuid.uuid4())

        response_dict = dict()
        response_dict["job_id"] = job_id
        response_dict["tasks"] = [
            {"task": "workload_sizing", "status": "COMPLETE", "progress": 100},
            {"task": "appliance_sizing", "status": "IN_PROGRESS", "progress": 20},
        ]
        response_dict["workload_results"] = workload_list

        # store workload status in results cache before apply_async(), otherwise there is a race condition
        celery_service.store_result(response_dict)

        # make asynchronous call to start the celery task
        async_result = packing_task.solve.apply_async(
            job_id=job_id,
            args=[
                response_dict,
                safety_margins,
                site_preferences,
                deepcopy(workload_list),
                settings_obj,
            ],
            serializer="pickle",
        )
        logger.debug("Initiated async task with task id: %s", async_result.id)

        return jsonify(response_dict), HTTPStatus.ACCEPTED


def get_appliance_utilization_attributes(
    utilization: utils.YearOverYearUtilization, num_years, appliance_summary_attributes
):
    dict_utilization = defaultdict(list)
    for y in range(1, 1 + num_years):
        for key_val in (
            ["capacity", "capacity"],
            ["memory", "mem"],
            ["cpu", "cpu"],
            ["io", "io"],
            ["network", "nic_pct"],
        ):
            dict_utilization[key_val[0]].append(utilization.get(key_val[1], y))

        for dimension in appliance_summary_attributes:
            dict_utilization[dimension].append(utilization.get(dimension, y))

    return dict_utilization


def assign_dict(assign):
    return {
        "workload": {"name": assign.workload.name},
        "mode": assign.mode.name,
        "number_of_clients": assign.num_clients,
    }


def site_assignments_as_dict(mresult):
    """
    get appliance configuration, utilization and workload summary each site
    """
    site_assignments = []
    last_year = mresult.num_years
    primary_servers = (
        get_primary_server_summary(mresult)
        if getattr(mresult, "all_master_servers", None)
        else {}
    )

    for domain, site_name, site_assignment in mresult.site_assignments:
        appliances = []
        is_nba = isinstance(site_assignment, SiteAssignment)
        servers = (
            site_assignment.media_servers if is_nba else site_assignment.flex_servers
        )

        for appl in servers:
            media_server_dict = get_media_server_dict(appl, is_nba, last_year)
            appliances.append(media_server_dict)
            appliances.extend(primary_servers.get(site_name, []))

        workload_summary = [
            {
                "workload": w,
                "summary_by_year": [obj.__dict__ for obj in summaries],
            }
            for (w, site), summaries in mresult.workload_summary_attributes.items()
            if site == site_name
        ]

        site_assignments.append(
            {
                "site_name": site_name,
                "appliances": appliances,
                "workload_summary": workload_summary,
                "domain": domain,
            }
        )

    return site_assignments


def all_media_servers_as_dict(mresult) -> dict:
    all_media_servers = [
        {
            "domain": domain,
            "site": site,
            "app_id": app_id,
            "config_name": appl.appliance.config_name,
            "workloads": [
                {
                    "name": w.workload.name,
                    "mode": str(w.mode),
                }
                for w in appl.workloads
            ],
        }
        for (domain, site, app_id, appl) in mresult.all_media_servers
    ]
    return all_media_servers


def primary_site_summaries_as_dict(mresult) -> dict:
    summaries = [
        {"config_name": config_name, "config_count": sum(cfg_summary.values())}
        for (config_name, cfg_summary) in mresult.summary.master_site_summaries
    ]
    return summaries


def get_media_server_dict(appliance, is_nba, last_year):
    appliance_dict = {"assignments": []}
    workloads = []
    containers_workloads = "workloads" if is_nba else "containers"

    if is_nba:
        for assign in getattr(appliance, containers_workloads):
            appliance_dict["assignments"].append(assign_dict(assign))
            workloads.append(assign.workload.name)

    else:
        for container in appliance.containers:
            for assign in container.obj.workloads:
                appliance_dict["assignments"].append(
                    assign_dict(assign) | {"container": container.name}
                )
                workloads.append(assign.workload.name)

    appliance_dict["appliance"] = {
        "family": "nba" if is_nba else "flex",
        "model": appliance.appliance.model,
        "config_name": appliance.appliance.config_name,
    }
    appliance_summary_attributes = appliance.appliance_summary_attributes
    appliance_dict["utilization"] = get_appliance_utilization_attributes(
        appliance.utilization, last_year, appliance_summary_attributes
    )
    return appliance_dict


def get_primary_server_summary(mresult):
    primary_servers = defaultdict(list)

    for domain, _site_name, app_id, mserver in mresult.all_master_servers:
        primary_server_dict = {
            "assignments": [],
            "appliance": {
                "family": "nba",
                "model": mserver.appliance.model,
                "config_name": mserver.appliance.config_name,
            },
        }

        utilization_dict = defaultdict(list)
        for assign in getattr(mserver, "workloads"):
            primary_server_dict["assignments"].append(assign_dict(assign))

        utilization = mserver.utilization
        for y in range(1, mresult.num_years + 1):
            for dim, unit in [
                ("absolute_capacity", "GiB"),
                ("cpu", None),
                ("memory", None),
                ("files", None),
                ("images", None),
                ("jobs/day", None),
            ]:
                val = utilization.get(dim, y)
                if unit is not None:
                    val = val.to_float(unit)
                utilization_dict[dim].append(val)
        primary_server_dict["utilization"] = utilization_dict
        primary_servers[_site_name].append(primary_server_dict)
    return primary_servers


def get_access_appliance_summary(mresult):
    access_appliances = []

    for site_name, app_id, assigned_appliance in mresult.access_result.all_appliances:
        access_appliances_dict = {"site_name": site_name}
        if mresult.ltr_target == settings.LtrType.ACCESS:
            access_appliances_dict["appliance"] = {
                "family": "access",
                "model": assigned_appliance.appliance.name,
            }
        else:
            access_appliances_dict["family"] = "recovery vault"

        utilization_dict = defaultdict(list)

        utilization = assigned_appliance.utilization
        for y in range(1, mresult.num_years + 1):
            for dim, unit in [
                ("absolute_capacity", "TiB"),
                ("capacity", None),
            ]:
                val = utilization.get(dim, y)
                if unit is not None:
                    val = val.to_float(unit)
                utilization_dict[dim].append(val)
        access_appliances_dict["utilization"] = utilization_dict

        access_appliances.append(access_appliances_dict)
    return access_appliances
