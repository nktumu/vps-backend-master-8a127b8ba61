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

import itertools
import logging

from ortools.sat.python import cp_model

from use_core import (
    access_appliance,
    appliance,
    constants,
    settings,
    task,
    utils,
    workload,
)
from use_core.utils import WorkloadMode

logger = logging.getLogger(__name__)

GENERIC_ERROR_TEXT = """
Unable to size appliance. This could be because:
1. The individual workloads are too large for an appliance,
   i.e. the appliance is not big enough to handle a single
   instance of your workload, or
2. The provided window sizes are not large enough.
"""

NON_WINDOW_ERROR_TEXT = """
Sizing failed because:
- The workload {workload_name} requires {capacity_value} {unit_value}
- The appliance {appliance_config} offers {capacity_available_value} {unit_value}
This means that the Media Server Appliance cannot support a single client for the
given workload.
"""

WINDOW_ERROR_TEXT = """
Sizing failed because:
- The workload {workload_name} requires {window_size} {resource_value}
- The window {window_type} offers {window_available}
This means that the Media Server Appliance cannot support a single client for the
given workload.
"""


class UserCancel(Exception):
    pass


class PackingError(Exception):
    pass


class PackingAllWorkloadsError(PackingError):
    def __init__(self, error_text, workload_error_list):
        super().__init__(self, error_text)
        self.error_text = error_text
        self.workload_error_list = workload_error_list

    def __str__(self):
        message = [self.error_text]
        for name, error in self.workload_error_list.items():
            message.append(f"{name}: {error}")
        return "\n\n".join(message)


class NotifyWorkloadError(Exception):
    pass


class WorkloadMisfitError(Exception):
    def __init__(self, workload_name, error_text):
        self.workload_name = workload_name
        self.error_text = error_text


class WorkloadMisfitMasterError(WorkloadMisfitError):
    pass


class WorkloadMisfitMediaError(WorkloadMisfitError):
    pass


class SizerResult:
    """Represent result of a sizer run for a particular appliance type."""

    def __init__(self, appliance, timeframe):
        self.appliance = appliance
        self.timeframe = timeframe
        self.sites = {}
        self.utilizations = {}
        self.storage_usage = {}

    def __setitem__(self, site_name, appliances):
        self.sites[site_name] = appliances

    def __getitem__(self, site_name):
        return self.sites[site_name]

    def __iter__(self):
        return iter(self.sites)

    def __repr__(self):
        return str(self.__class__) + ": " + str(self.__dict__)

    @property
    def all_domains(self):
        domains = set()
        for site_name in self.sites:
            for appl in self.sites[site_name]:
                for assign in appl["assignment"]:
                    domains.add(assign["workload"].domain)
        return domains

    @property
    def num_years(self):
        return self.timeframe.num_years

    @property
    def planning_year(self):
        return self.timeframe.planning_year

    def set_utilization(self, site_name, utilization):
        self.utilizations[site_name] = utilization

    def get_utilization(self, site_name):
        return self.utilizations[site_name]

    @staticmethod
    def get_yoy_max_utilization(results):
        # get max utilization year-over-year across multiple SizerResult objects
        max_util = []
        for year in range(1, 1 + results[0].num_years):
            yr_max_util = {}
            for dim in ["capacity", "cpu", "mem", "io", "nic"]:
                yr_max_util[dim] = max(
                    SizerResult.get_utils_for_year(results, dim, year)
                )
            max_util.append(yr_max_util)
        return max_util

    @staticmethod
    def get_utils_for_year(results, dim, year):
        for result in results:
            for site_name in result:
                util = result.utilizations[site_name][year][dim]
                yield util

    def get_site_utilization(self, site_name, year):
        return max(
            self.utilizations[site_name][year][dim]
            for dim in ["capacity", "cpu", "mem", "io", "nic"]
        )


def scale_value(value_type, value):
    if value_type in ["nw"]:
        return int(value * 100)
    if value_type in ["io"]:
        return int(value * 1000)
    if value_type in ["capacity", "memory"]:
        return int(value)
    if value_type in ["duration"]:
        return int(value)


def nw_avail(
    appliance_spec: appliance.Appliance,
    workload: workload.Workload,
    window: task.WindowType,
):
    if window == task.WindowType.replication:
        nw_type = workload.dr_nw
    else:
        nw_type = workload.front_end_nw
    if nw_type == appliance.NetworkType.auto:
        nw_type = appliance_spec.auto_nw_name

    nw_for_type = {
        appliance.NetworkType.one_gbe: appliance_spec.nw_1g,
        appliance.NetworkType.ten_gbe_copper: appliance_spec.nw_10g_copper,
        appliance.NetworkType.ten_gbe_sfp: appliance_spec.nw_10g_sfp,
        appliance.NetworkType.twentyfive_gbe_sfp: appliance_spec.nw_25g_sfp,
    }

    return int(nw_for_type[nw_type])


def fdiv(num, den):
    try:
        return num / den
    except ZeroDivisionError:
        return 0.0


class SizerContext:
    def __init__(
        self,
        workloads,
        appliance_spec,
        window_sizes,
        site_name,
        progress_cb,
        generate_tasks,
        timeframe,
        message_cb=None,
        pack_flex: bool = False,
        pack_ltr: bool = False,
        ltr_target: settings.LtrType = settings.LtrType.ACCESS,
    ):
        self.workloads = workloads
        self.appliance_spec = appliance_spec
        self.window_sizes = window_sizes
        self.site_name = site_name
        self.progress_cb = progress_cb
        self.generate_tasks = generate_tasks
        self.timeframe = timeframe
        self.message_cb = message_cb
        self.pack_flex = pack_flex
        self.pack_ltr = pack_ltr
        self.ltr_target = ltr_target

        self.max_fits_logged = set()

    def _find_relevant_workloads(self):
        relevant_workloads = []

        for w in self.workloads:
            if w.site_name == self.site_name and self.pack_ltr:
                relevant_workloads.append(
                    {"workload": w, "mode": WorkloadMode.media_cloud}
                )
            elif w.site_name == self.site_name:
                relevant_workloads.append(
                    {"workload": w, "mode": WorkloadMode.media_primary}
                )
            if not self.pack_ltr and w.dr_dest == self.site_name:
                relevant_workloads.append(
                    {"workload": w, "mode": WorkloadMode.media_dr}
                )

        return relevant_workloads

    def _get_workload_groups(self, workloads):
        workload_grp = []
        for grp_key, group in itertools.groupby(
            sorted(
                workloads,
                key=lambda wk: wk["workload"].workload_isolation,
                reverse=True,
            ),
            lambda wk: wk["workload"].workload_isolation,
        ):
            if grp_key:
                for wk in group:
                    workload_grp.append([wk])
                logger.debug("registering %d isolated workloads", len(workload_grp))
            else:
                workload_grp.append([wk for wk in group])

        return workload_grp

    def pack(self):
        logger.debug(
            "SITE: "
            + self.site_name
            + "  SITE-VERSION: "
            + str(self.appliance_spec["media_app"].site_version)
            + ": "
            + self.appliance_spec["media_app"].site_version.name
        )

        result = SizerResult(self.appliance_spec["media_app"], self.timeframe)

        relevant_workloads = self._find_relevant_workloads()
        wk_grps = self._get_workload_groups(relevant_workloads)

        grp_app = []
        grp_uti = []
        grp_bot = {}
        for wk_grp in wk_grps:
            if self.generate_tasks:
                for w in wk_grp:
                    w["workload"].generate_tasks(
                        w["workload"].domain,
                        [self.site_name],
                        self.appliance_spec,
                        self.window_sizes,
                        self.timeframe,
                    )

            max_appliances = self._total_clients(wk_grp)
            min_appliances = 2
            for n_appliances in utils.potential_appliance_counts(
                min_appliances, max_appliances
            ):
                logger.debug("attempting sizing with %d appliance", n_appliances)
                solver_data = self._build_solver_data_model(wk_grp, n_appliances)

                try:
                    appliances, utilizations, bottlenecks = self._solve(solver_data)
                    grp_app += appliances
                    if not grp_uti:
                        grp_uti = utilizations
                    for yr in range(len(utilizations)):
                        for dim in utilizations[yr]:
                            grp_uti[yr][dim] = max(
                                grp_uti[yr][dim], utilizations[yr][dim]
                            )
                    grp_bot.update(bottlenecks)
                    break
                except PackingError:
                    pass
            else:
                raise PackingError(GENERIC_ERROR_TEXT)

        result[self.site_name] = grp_app
        result.set_utilization(self.site_name, grp_uti)
        result.bottlenecks = grp_bot
        return result

    def _total_clients(self, workloads):
        return sum(w["workload"].num_instances for w in workloads)

    def _build_solver_data_model(self, workloads, num_appliances):
        solver_workloads = [self._convert_one_workload(w) for w in workloads]
        workload_name_map = dict((w["workload"].name, w) for w in workloads)
        num_items = self._total_clients(workloads)
        appliance_list = [self._convert_one_appliance(i) for i in range(num_appliances)]
        return {
            "site_name": self.site_name,
            "appliance": self.appliance_spec["media_app"],
            "workload_names": workload_name_map,
            "workloads": solver_workloads,
            "num_items": num_items,
            "num_appliances": num_appliances,
            "all_appliances": appliance_list,
            "window_sizes": self.window_sizes,
        }

    def _convert_one_workload(self, relevant_workload):
        w: workload.Workload = relevant_workload["workload"]
        mode: WorkloadMode = relevant_workload["mode"]

        if mode == WorkloadMode.media_cloud:
            # LTR workload will not use local storage
            capacity = utils.Size.ZERO
            logger.info("using msdp-c capacity %s for workload %s", capacity, w.name)
        elif mode == WorkloadMode.media_primary:
            assert not self.pack_ltr
            capacity = w.total_storage_for_year(self.timeframe.planning_year)
            logger.info("using primary capacity %s for workload %s", capacity, w.name)
        elif mode == WorkloadMode.media_dr:
            assert not self.pack_ltr
            capacity = w.dr_storage_for_year(self.timeframe.planning_year)
            logger.info("using dr capacity %s for workload %s", capacity, w.name)
        else:
            assert False

        cloud_capacity = w.cloud_storage_for_year(self.timeframe.planning_year)

        winfo = {
            "name": w.name,
            "num_instances": w.num_instances,
            "capacity": scale_value("capacity", capacity),
            "cloud_capacity": scale_value("capacity", cloud_capacity),
            "vms": w.software_resources["vms"],
            "dbs": w.software_resources["dbs"],
            "jobs/day": w.software_resources["jobs/day"],
            "files": w.software_resources["files"],
            "images": w.master_resources_for_year(self.timeframe.planning_year)[
                "images"
            ],
            "has_ltr_tasks": w.ltr_enabled and not self.pack_flex,
        }

        for window in task.WindowType:
            if window == task.WindowType.master:
                continue
            if self.pack_ltr:
                res = w.ltr_resources(
                    self.site_name, window, self.timeframe.planning_year
                )
            else:
                res = w.resources(
                    self.site_name, window, self.timeframe.planning_year, self.pack_flex
                )
            if res is None:
                continue
            winfo[("cpu", window)] = scale_value("duration", res["total_job_duration"])
            winfo[("memory", window)] = scale_value(
                "memory", res["total_mem_utilization"]
            )
            winfo[("io", window)] = scale_value("io", res["total_io_utilization"])

            nw_util = int(res["total_nw_utilization"] * 100)
            winfo[("nw_1g", window)] = winfo[("nw_10g_copper", window)] = winfo[
                ("nw_10g_sfp", window)
            ] = winfo[("nw_25g_sfp", window)] = 0
            if window == task.WindowType.replication:
                nw_type = w.dr_nw
            else:
                nw_type = w.front_end_nw
            nw_type_map = {
                appliance.NetworkType.one_gbe: "nw_1g",
                appliance.NetworkType.ten_gbe_copper: "nw_10g_copper",
                appliance.NetworkType.ten_gbe_sfp: "nw_10g_sfp",
                appliance.NetworkType.twentyfive_gbe_sfp: "nw_25g_sfp",
            }
            nw_type_map[appliance.NetworkType.auto] = nw_type_map[
                self.appliance_spec["media_app"].auto_nw_name
            ]
            winfo[(nw_type_map[nw_type], window)] = nw_util
            winfo[("nw_cloud", window)] = int(res["total_cloud_nw_utilization"] * 100)

        logger.info("workload info: %s", winfo)
        return winfo

    def _convert_one_appliance(self, idx):
        appinfo = {
            "appliance_id": idx,
            "jobs/day": self.appliance_spec["media_app"].software_safety.jobs_per_day,
            "dbs": self.appliance_spec["media_app"].software_safety.dbs_15min_rpo,
            "vms": self.appliance_spec["media_app"].software_safety.vm_clients,
            "files": self.appliance_spec["media_app"].software_safety.files,
            "images": self.appliance_spec["media_app"].software_safety.images,
            "memory": int(self.appliance_spec["media_app"].safe_memory)
            - self.appliance_spec["media_app"].memory_overhead,
            "full_memory": int(self.appliance_spec["media_app"].memory)
            - self.appliance_spec["media_app"].memory_overhead,
            "max_streams": self.appliance_spec[
                "media_app"
            ].software_safety.concurrent_streams,
            "msdp_reserved_size": scale_value(
                "capacity", self.appliance_spec["media_app"].msdp_container_size
            ),
        }

        appinfo["capacity"] = scale_value(
            "capacity", self.appliance_spec["media_app"].safe_capacity
        )
        msdp_cloud_capacity = (
            self.appliance_spec["media_app"].msdp_cloud_capacity_recovery_vault
            if self.ltr_target == settings.LtrType.RECOVERYVAULT
            else self.appliance_spec["media_app"].msdp_cloud_capacity
        )
        appinfo["cloud_capacity"] = scale_value("capacity", msdp_cloud_capacity)

        for window in task.WindowType:
            appinfo[("cpu", window)] = scale_value(
                "duration",
                self.appliance_spec["media_app"].safe_duration(
                    window, self.window_sizes
                ),
            )
            appinfo[("solo_cpu", window)] = scale_value(
                "duration",
                self.appliance_spec["media_app"].safe_duration(
                    window, self.window_sizes
                )
                * self.appliance_spec["media_app"].software_safety.concurrent_streams,
            )
            appinfo[("nw_1g", window)] = scale_value(
                "nw", self.appliance_spec["media_app"].safe_nw_1g
            )
            appinfo[("nw_10g_copper", window)] = scale_value(
                "nw", self.appliance_spec["media_app"].safe_nw_10g_copper
            )
            appinfo[("nw_10g_sfp", window)] = scale_value(
                "nw", self.appliance_spec["media_app"].safe_nw_10g_sfp
            )
            appinfo[("nw_25g_sfp", window)] = scale_value(
                "nw", self.appliance_spec["media_app"].safe_nw_25g_sfp
            )
            appinfo[("nw_cloud", window)] = scale_value(
                "nw", self.appliance_spec["media_app"].nw_cloud
            )
            appinfo[("io", window)] = scale_value(
                "io", self.appliance_spec["media_app"].safe_iops
            )
            max_streams = self.appliance_spec[
                "media_app"
            ].software_safety.concurrent_streams
            if (
                window == task.WindowType.replication
                and self.ltr_target == settings.LtrType.ACCESS
            ):
                # ensure we don't exceed limits of the Access appliance
                max_streams = min(
                    max_streams, access_appliance.AccessAppliance.MAX_STREAMS
                )
            appinfo[("max_streams", window)] = max_streams

        logger.info("appliance details: %s", appinfo)
        return appinfo

    def _progress(self, status, detail=None):
        if self.progress_cb is None:
            return
        self.progress_cb(status, detail)

    def _solve(self, data):
        model = cp_model.CpModel()
        workload_bottlenecks = {}

        # x[(i, j)] is how many instances of workload i are assigned to
        # appliance j
        x = {}

        for idx, w in enumerate(data["workloads"]):
            for b in data["all_appliances"]:
                b["appliance_model"] = data["appliance"].appliance
                b["config_name"] = data["appliance"].config_name
                max_fit, max_fit_details = self._choose_max_fit(w, b)
                if w["name"] not in workload_bottlenecks:
                    workload_bottlenecks[w["name"]] = max_fit_details
                app_id = b["appliance_id"]
                x[(idx, app_id)] = model.NewIntVar(
                    0, max_fit, "x_%i_%i" % (idx, app_id)
                )

        mem_reqd = []
        for w in data["workloads"]:
            for window in task.WindowType:
                if window == task.WindowType.master:
                    continue
                mem_reqd.append(w[("memory", window)])
        data["max_mem_reqd"] = max(mem_reqd)

        # streams[window][i] is the number of streams that appliance i
        # can support in the specified window
        #
        # max_streams[i] is the maximum number of streams that
        # appliance i supports across all windows
        streams = {}

        max_streams = []
        for b in data["all_appliances"]:
            app_id = b["appliance_id"]
            max_streams.append(
                model.NewIntVar(
                    1,
                    max(
                        b[("max_streams", window)]
                        for window in task.WindowType.packing_windows()
                    ),
                    f"max_streams_{app_id}",
                )
            )

        for window in task.WindowType.packing_windows():
            streams[window] = {}
            for b in data["all_appliances"]:
                app_id = b["appliance_id"]
                streams[window][app_id] = model.NewIntVar(
                    1, b[("max_streams", window)], f"streams_{app_id}"
                )
                if data["max_mem_reqd"]:
                    logger.info(
                        "maximum possible concurrency on appliance %d is %d",
                        app_id,
                        b["memory"] // data["max_mem_reqd"],
                    )

        workloads_fit = any(
            data["max_mem_reqd"] < b["memory"] for b in data["all_appliances"]
        )
        if not workloads_fit:
            logger.warning(
                "workloads will not fit in appliance memory, trying without safety margin"
            )
            for b in data["all_appliances"]:
                b["memory"] = b["full_memory"]

        # Total resource usage per appliance
        capacity_used = [
            model.NewIntVar(0, b["capacity"], "capacity_used_%i" % b["appliance_id"])
            for b in data["all_appliances"]
        ]
        cloud_capacity_used = [
            model.NewIntVar(
                0, b["cloud_capacity"], 'cloud_capacity_used_{b["appliance_id"]}'
            )
            for b in data["all_appliances"]
        ]
        ltr_capacity_used = [
            model.NewIntVar(0, b["capacity"], f"ltr_capacity_used_{b['appliance_id']}")
            for b in data["all_appliances"]
        ]
        mem_used = [
            model.NewIntVar(0, b["memory"], "mem_used_{b['appliance_id']}")
            for b in data["all_appliances"]
        ]
        jobs_per_day_used = [
            model.NewIntVar(
                0, b["jobs/day"], "jobs_per_day_used_%i" % b["appliance_id"]
            )
            for b in data["all_appliances"]
        ]
        db_slots_used = []
        for b in data["all_appliances"]:
            if b["dbs"] is not None:
                db_slots_used.append(
                    model.NewIntVar(0, b["dbs"], "db_slots_used_%i" % b["appliance_id"])
                )
            else:
                db_slots_used.append(None)
        vm_slots_used = [
            model.NewIntVar(0, b["vms"], "vm_slots_used_%i" % b["appliance_id"])
            for b in data["all_appliances"]
        ]
        files_used = []
        for b in data["all_appliances"]:
            if b["files"] is not None:
                files_used.append(
                    model.NewIntVar(0, b["files"], "files_used_%i" % b["appliance_id"])
                )
            else:
                files_used.append(None)

        images_used = []
        for b in data["all_appliances"]:
            if b["images"] is not None:
                images_used.append(
                    model.NewIntVar(
                        0, b["images"], "images_used_%i" % b["appliance_id"]
                    )
                )
            else:
                images_used.append(None)

        cpu_used = {}
        solo_cpu_used = {}
        io_used = {}
        one_gb_nw_used = {}
        ten_gb_copper_nw_used = {}
        ten_gb_sfp_nw_used = {}
        twentyfive_gb_sfp_nw_used = {}
        cloud_nw_used = {}
        for window in task.WindowType:
            cpu_used[window] = [
                model.NewIntVar(
                    0, b[("cpu", window)], f"cpu_used_{b['appliance_id']}_{window.name}"
                )
                for b in data["all_appliances"]
            ]
            solo_cpu_used[window] = [
                model.NewIntVar(
                    0,
                    b[("solo_cpu", window)],
                    f"solo_cpu_used_{b['appliance_id']}_{window.name}",
                )
                for b in data["all_appliances"]
            ]
            io_used[window] = [
                model.NewIntVar(
                    0,
                    b[("io", window)],
                    "io_used_%i_%s" % (b["appliance_id"], window.name),
                )
                for b in data["all_appliances"]
            ]
            one_gb_nw_used[window] = [
                model.NewIntVar(
                    0,
                    b[("nw_1g", window)],
                    "one_gb_nw_used_%i_%s" % (b["appliance_id"], window.name),
                )
                for b in data["all_appliances"]
            ]
            ten_gb_copper_nw_used[window] = [
                model.NewIntVar(
                    0,
                    b[("nw_10g_copper", window)],
                    "ten_gb_copper_nw_used_%i_%s" % (b["appliance_id"], window.name),
                )
                for b in data["all_appliances"]
            ]
            ten_gb_sfp_nw_used[window] = [
                model.NewIntVar(
                    0,
                    b[("nw_10g_sfp", window)],
                    "ten_gb_sfp_nw_used_%i_%s" % (b["appliance_id"], window.name),
                )
                for b in data["all_appliances"]
            ]
            twentyfive_gb_sfp_nw_used[window] = [
                model.NewIntVar(
                    0,
                    b[("nw_25g_sfp", window)],
                    "twentyfive_gb_sfp_nw_used_%i_%s"
                    % (b["appliance_id"], window.name),
                )
                for b in data["all_appliances"]
            ]
            cloud_nw_used[window] = [
                model.NewIntVar(
                    0,
                    b[("nw_cloud", window)],
                    "cloud_nw_used_%i_%s" % (b["appliance_id"], window.name),
                )
                for b in data["all_appliances"]
            ]

        for b in data["all_appliances"]:
            app_id = b["appliance_id"]
            model.Add(
                capacity_used[app_id]
                == sum(
                    x[(i, app_id)] * w["capacity"]
                    for (i, w) in enumerate(data["workloads"])
                )
                + ltr_capacity_used[app_id]
            )
            model.Add(
                cloud_capacity_used[app_id]
                == sum(
                    x[(i, app_id)] * w["cloud_capacity"]
                    for (i, w) in enumerate(data["workloads"])
                )
            )
            model.AddMaxEquality(
                max_streams[app_id], [streams[w][app_id] for w in streams]
            )
            model.Add(mem_used[app_id] == data["max_mem_reqd"] * max_streams[app_id])
            model.Add(
                jobs_per_day_used[app_id]
                == sum(
                    x[(i, app_id)] * w["jobs/day"]
                    for (i, w) in enumerate(data["workloads"])
                )
            )
            if db_slots_used[app_id] is not None:
                model.Add(
                    db_slots_used[app_id]
                    == sum(
                        x[(i, app_id)] * w["dbs"]
                        for (i, w) in enumerate(data["workloads"])
                    )
                )
            model.Add(
                vm_slots_used[app_id]
                == sum(
                    x[(i, app_id)] * w["vms"] for (i, w) in enumerate(data["workloads"])
                )
            )
            if files_used[app_id] is not None:
                model.Add(
                    files_used[app_id]
                    == sum(
                        x[(i, app_id)] * w["files"]
                        for (i, w) in enumerate(data["workloads"])
                    )
                )
            if images_used[app_id] is not None:
                model.Add(
                    images_used[app_id]
                    == sum(
                        x[(i, app_id)] * w["images"]
                        for (i, w) in enumerate(data["workloads"])
                    )
                )
            for window in task.WindowType:
                if window == task.WindowType.master:
                    continue
                model.Add(
                    solo_cpu_used[window][app_id]
                    == sum(
                        x[(i, app_id)] * w[("cpu", window)]
                        for (i, w) in enumerate(data["workloads"])
                    )
                )
                model.AddDivisionEquality(
                    cpu_used[window][app_id],
                    solo_cpu_used[window][app_id],
                    streams[window][app_id],
                )
                model.Add(
                    io_used[window][app_id]
                    == sum(
                        x[(i, app_id)] * w[("io", window)]
                        for (i, w) in enumerate(data["workloads"])
                    )
                )
                model.Add(
                    one_gb_nw_used[window][app_id]
                    == sum(
                        x[(i, app_id)] * w[("nw_1g", window)]
                        for (i, w) in enumerate(data["workloads"])
                    )
                )
                model.Add(
                    ten_gb_copper_nw_used[window][app_id]
                    == sum(
                        x[(i, app_id)] * w[("nw_10g_copper", window)]
                        for (i, w) in enumerate(data["workloads"])
                    )
                )
                model.Add(
                    ten_gb_sfp_nw_used[window][app_id]
                    == sum(
                        x[(i, app_id)] * w[("nw_10g_sfp", window)]
                        for (i, w) in enumerate(data["workloads"])
                    )
                )
                model.Add(
                    twentyfive_gb_sfp_nw_used[window][app_id]
                    == sum(
                        x[(i, app_id)] * w[("nw_25g_sfp", window)]
                        for (i, w) in enumerate(data["workloads"])
                    )
                )
                model.Add(
                    cloud_nw_used[window][app_id]
                    == sum(
                        x[(i, app_id)] * w[("nw_cloud", window)]
                        for (i, w) in enumerate(data["workloads"])
                    )
                )

        # Each item can be in exactly one appliance.  So sum of all
        # x[(idx, _)] across appliances must be exactly equal to the
        # number of instances of workload idx.
        for idx, w in enumerate(data["workloads"]):
            model.Add(
                sum(x[(idx, b["appliance_id"])] for b in data["all_appliances"])
                == w["num_instances"]
            )

        # Calculate storage required for MSDP-C.  This is only if the
        # appliance has any LTR workloads assigned to it.
        appliance_ltr_used = []
        for idx, b in enumerate(data["all_appliances"]):
            app_id = b["appliance_id"]
            var_name = f"appliance_{app_id}_ltr_used"
            appliance_ltr_used.append(model.NewIntVar(0, 1, var_name))

            # num_wk_with_ltr will be the number of workloads assigned
            # to this appliance that have LTR tasks
            num_wk_with_ltr = model.NewIntVar(
                0, data["num_items"], "num_wk_with_ltr_{}".format(app_id)
            )
            model.Add(
                num_wk_with_ltr
                == sum(
                    x[(idx, app_id)]
                    for (idx, w) in enumerate(data["workloads"])
                    if w["has_ltr_tasks"]
                )
            )

            # appliance_ltr_used[i] will be 0 or 1, depending on
            # whether this appliance has any workloads with LTR tasks
            model.AddMinEquality(appliance_ltr_used[app_id], [1, num_wk_with_ltr])

            # ltr_capacity_used[i] will be 0 if no LTR workloads are
            # assigned here, otherwise, it will be the capacity
            # reserved for MSDP-C
            model.Add(
                ltr_capacity_used[app_id]
                == appliance_ltr_used[app_id] * b["msdp_reserved_size"]
            )

        # Calculate how many appliances are used.  appliance_used[i] is 1
        # if the appliance has been assigned at least one workload, 0
        # otherwise.
        appliance_used = []
        for idx, b in enumerate(data["all_appliances"]):
            app_id = b["appliance_id"]
            var_name = "appliance_{}_used".format(app_id)
            appliance_used.append(model.NewIntVar(0, 1, var_name))
            num_items = model.NewIntVar(
                0, data["num_items"], "num_items_{}".format(app_id)
            )
            model.Add(
                num_items
                == sum(x[(idx, app_id)] for (idx, _) in enumerate(data["workloads"]))
            )
            model.AddMinEquality(appliance_used[app_id], [1, num_items])
            if idx > 0:
                # this constraint "front-loads" the appliances, so
                # appliances with lower index are used in preference
                # to appliances with higher index.  This makes sure
                # that all the unused appliances collect at the end of
                # the array.
                model.Add(appliance_used[idx - 1] >= appliance_used[idx])

        # Minimize number of appliances used
        model.Minimize(sum(appliance_used))

        solver_chunks = 1 + data["num_items"] // constants.ITEM_CHUNK_SIZE
        solver = self._run_solver(model, solver_chunks)

        logger.info("attempting to balance workloads at site %s", data["site_name"])

        min_appl_count = self._find_min_appliances(data, solver, x)
        model.Add(sum(appliance_used) == min_appl_count)

        min_capacity_used = model.NewIntVar(
            0, data["all_appliances"][0]["capacity"], "min_capacity_used"
        )
        max_capacity_used = model.NewIntVar(
            0, data["all_appliances"][0]["capacity"], "max_capacity_used"
        )

        # If we don't use all the appliances, the front-loading
        # constraints ensure that the first min_appl_count appliances
        # in the list are the ones that are used.
        model.AddMinEquality(min_capacity_used, capacity_used[:min_appl_count])
        model.AddMaxEquality(max_capacity_used, capacity_used[:min_appl_count])

        model.Minimize(max_capacity_used - min_capacity_used)

        solver = self._run_solver(model, solver_chunks)

        return self._parse_solution(data, solver, x, streams, workload_bottlenecks)

    def _run_solver(self, model, nchunks):
        solver = cp_model.CpSolver()
        status = cp_model.UNKNOWN
        chunk_time = constants.CHUNK_TIME
        workers = utils.cpu_count()
        first_time_thru = True
        solver.parameters.num_search_workers = workers

        while status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            timeout = max(constants.MIN_SOLVER_TIMEOUT, chunk_time * nchunks // workers)
            solver.parameters.max_time_in_seconds = timeout

            msg = f"Searching solution for {timeout} seconds..."
            if first_time_thru:
                self._progress(None, msg)
            else:
                self._progress(
                    None, f"Initial search failed, increasing timeout. {msg}"
                )

            status = solver.Solve(model)
            if status == cp_model.INFEASIBLE:
                # solver has proved that no solution is possible.
                # There is no point in retrying with higher timeout.
                raise PackingError(GENERIC_ERROR_TEXT)

            if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
                # solver was unable to find a solution, but was also
                # unable to conclude that no solution is possible.
                # Check if we can retry with higher timeout.
                first_time_thru = False
                chunk_time *= constants.TIMEOUT_SCALING
                self._check_continue()

        return solver

    def _check_continue(self):
        if self.message_cb is None:
            return

        msg = "Calculating a result is taking longer than expected. Continue?"
        self.message_cb(msg)

    def _find_min_appliances(self, data, solver, x):
        used_appliances = set()
        for idx, w in enumerate(data["workloads"]):
            for b in data["all_appliances"]:
                app_id = b["appliance_id"]
                val = solver.Value(x[(idx, app_id)])
                if val:
                    used_appliances.add(app_id)
        return len(used_appliances)

    def _parse_solution(self, data, solver, x, streams, bottlenecks):
        appliances = {}
        for idx, w in enumerate(data["workloads"]):
            for b in data["all_appliances"]:
                app_id = b["appliance_id"]
                val = solver.Value(x[(idx, app_id)])
                if val:
                    if app_id not in appliances:
                        appliances[app_id] = {}
                    if w["name"] not in appliances[app_id]:
                        appliances[app_id][w["name"]] = 0
                    appliances[app_id][w["name"]] += val

        result = []
        for app_id in appliances:
            app_workloads = []
            for wname in appliances[app_id]:
                workload_info = data["workload_names"][wname]
                app_workloads.append(
                    {
                        "workload": workload_info["workload"],
                        "mode": workload_info["mode"],
                        "total_inst": appliances[app_id][wname],
                    }
                )
            window_streams = {}
            for window in streams:
                nstreams = solver.Value(streams[window][app_id])
                logger.debug(
                    "calculated maximum concurrent streams for appliance %s in window %s: %d",
                    app_id,
                    window,
                    nstreams,
                )
                window_streams[window] = nstreams
            result.append(
                {
                    "appliance_model": data["appliance"],
                    "assignment": app_workloads,
                    "streams": window_streams,
                }
            )

        utilizations = self._analyze_headroom(data, result)
        return result, utilizations, bottlenecks

    def _analyze_headroom(self, data, assignment):
        utilizations = []
        for yr in range(self.timeframe.num_years + 1):
            for assign in assignment:
                app: appliance.Appliance = assign["appliance_model"]
                if "utilization" not in assign:
                    assign["utilization"] = {}
                assign["utilization"][yr] = {}

                for soft_res in ["jobs/day", "dbs", "vms"]:
                    assign["utilization"][yr][f"media_{soft_res}"] = sum(
                        a["workload"].software_resources[soft_res] * a["total_inst"]
                        for a in assign["assignment"]
                    )

                capacities = []
                pre_dedupe_capacities = []
                full_backup_storage = []
                incremental_backup_storage = []
                msdp_c_assigned = False
                for a in assign["assignment"]:
                    if a["mode"] == WorkloadMode.media_primary:
                        capacity = a["workload"].total_storage_for_year(yr)
                        pre_dedupe_capacity = a[
                            "workload"
                        ].total_storage_pre_dedupe_for_year(yr)
                        full_backup = a["workload"].full_storage_for_year(yr)
                        incremental_backup = a["workload"].incremental_storage_for_year(
                            yr
                        )
                    elif a["mode"] == WorkloadMode.media_dr:
                        capacity = a["workload"].dr_storage_for_year(yr)
                        pre_dedupe_capacity = a[
                            "workload"
                        ].dr_storage_pre_dedupe_for_year(yr)
                        full_backup = a["workload"].dr_full_storage_for_year(yr)
                        incremental_backup = a[
                            "workload"
                        ].dr_incremental_storage_for_year(yr)
                    elif a["mode"] == WorkloadMode.media_cloud:
                        # if this "server" is actually a msdp-c
                        # container, backups don't store data locally
                        # in a permanent manner.  We record this as 0
                        # usage for the workloads + a constant amount
                        # of storage required for MSDP-C functioning
                        capacity = pre_dedupe_capacity = utils.Size.ZERO
                        full_backup = incremental_backup = utils.Size.ZERO
                        msdp_c_assigned = True
                    else:
                        assert False
                    capacities.append(capacity * a["total_inst"])
                    pre_dedupe_capacities.append(pre_dedupe_capacity * a["total_inst"])
                    full_backup_storage.append(full_backup * a["total_inst"])
                    incremental_backup_storage.append(
                        incremental_backup * a["total_inst"]
                    )
                if msdp_c_assigned:
                    capacities.append(app.msdp_container_size)
                    pre_dedupe_capacities.append(app.msdp_container_size)
                assign["utilization"][yr]["absolute_capacity"] = utils.Size.sum(
                    capacities
                )
                assign["utilization"][yr]["alloc_capacity"] = utils.Size.sum(capacities)
                assign["utilization"][yr]["capacity"] = (
                    app.calculated_capacity.utilization(capacities)
                )
                assign["utilization"][yr]["alloc_capacity_pct"] = (
                    app.calculated_capacity.utilization(capacities)
                )
                assign["utilization"][yr]["Full Backup"] = utils.Size.sum(
                    full_backup_storage
                )
                assign["utilization"][yr]["Incremental Backup"] = utils.Size.sum(
                    incremental_backup_storage
                )
                assign["utilization"][yr]["Size Before Deduplication"] = utils.Size.sum(
                    pre_dedupe_capacities
                )
                assign["utilization"][yr]["Size After Deduplication"] = utils.Size.sum(
                    capacities
                )

                transfer_volume_DR = []
                transfer_volume_LTR = []
                for a in assign["assignment"]:
                    if a["workload"].dr_enabled:
                        DR_transfer_volume = (
                            a["workload"].weekly_transfer_volume_dr(yr)
                            * a["total_inst"]
                        )
                        transfer_volume_DR.append(DR_transfer_volume)
                    if (
                        a["workload"].ltr_enabled
                        and (self.pack_ltr or not self.pack_flex)
                        and a["mode"]
                        in (WorkloadMode.media_primary, WorkloadMode.media_cloud)
                    ):
                        # if we're sizing flex, this should be
                        # accounted for only with the MSDP-C
                        # containers.  If we're not sizing flex, this
                        # goes in with the media containers.
                        LTR_transfer_volume = (
                            a["workload"].weekly_transfer_volume_ltr(yr)
                            * a["total_inst"]
                        )
                        transfer_volume_LTR.append(LTR_transfer_volume)

                assign["utilization"][yr]["cpu"] = 0
                assign["utilization"][yr]["window_cpu"] = {
                    window: 0 for window in task.WindowType.packing_windows()
                }
                assign["utilization"][yr]["window_nic_pct"] = {
                    window: 0 for window in task.WindowType.packing_windows()
                }
                assign["utilization"][yr]["window_nic"] = {
                    window: utils.Size.ZERO
                    for window in task.WindowType.packing_windows()
                }
                assign["utilization"][yr]["window_nic_dr"] = {
                    window: utils.Size.ZERO
                    for window in task.WindowType.packing_windows()
                }
                assign["utilization"][yr]["window_nic_cloud"] = {
                    window: utils.Size.ZERO
                    for window in task.WindowType.packing_windows()
                }
                assign["utilization"][yr]["mem"] = 0
                assign["utilization"][yr]["absolute_memory"] = utils.Size.ZERO
                assign["utilization"][yr]["absolute_io"] = utils.Size.ZERO
                assign["utilization"][yr]["io"] = 0
                assign["utilization"][yr]["nic_pct"] = 0
                assign["utilization"][yr]["nic"] = utils.Size.ZERO
                assign["utilization"][yr]["nic_dr"] = utils.Size.ZERO
                assign["utilization"][yr]["nic_cloud"] = utils.Size.ZERO
                assign["utilization"][yr]["DR Transfer GiB/Week"] = utils.Size.sum(
                    transfer_volume_DR
                )
                assign["utilization"][yr]["Cloud Transfer GiB/week"] = utils.Size.sum(
                    transfer_volume_LTR
                )
                assign["utilization"][yr]["Cloud Minimum Bandwidth(Mbps)"] = (
                    utils.Size.sum(transfer_volume_LTR)
                )

                if not app.performance_supported:
                    continue

                for window in task.WindowType.packing_windows():
                    job_duration_reqd = sum(
                        a["workload"].resource_for_year(
                            data["site_name"], window, yr, "total_job_duration"
                        )
                        * a["total_inst"]
                        for a in assign["assignment"]
                    )
                    duration_avail = (
                        app.total_duration(data["window_sizes"])
                        * assign["streams"][window]
                    )
                    assign["utilization"][yr]["window_cpu"][window] = (
                        job_duration_reqd / duration_avail
                    )

                    mem_reqd = (
                        data["max_mem_reqd"] * assign["streams"][window]
                        + app.memory_overhead
                    )
                    mem_avail = int(app.memory)
                    assign["utilization"][yr]["mem"] = max(
                        assign["utilization"][yr]["mem"], mem_reqd / mem_avail
                    )
                    assign["utilization"][yr]["absolute_memory"] = max(
                        assign["utilization"][yr]["absolute_memory"],
                        utils.Size.assume_unit(mem_reqd, "KiB"),
                    )

                    abs_io = utils.Size.sum(
                        a["workload"].resource_for_year(
                            data["site_name"],
                            window,
                            yr,
                            "total_absolute_io",
                        )
                        * a["total_inst"]
                        for a in assign["assignment"]
                    )
                    assign["utilization"][yr]["absolute_io"] = max(
                        assign["utilization"][yr]["absolute_io"], abs_io
                    )
                    io_reqd = sum(
                        a["workload"].resource_for_year(
                            data["site_name"],
                            window,
                            yr,
                            "total_io_utilization",
                        )
                        * a["total_inst"]
                        for a in assign["assignment"]
                    )
                    io_avail = app.iops
                    assign["utilization"][yr]["io"] = max(
                        assign["utilization"][yr]["io"], io_reqd / io_avail
                    )

                    nw_util_pct = sum(
                        fdiv(
                            int(
                                a["workload"].resource_for_year(
                                    data["site_name"],
                                    window,
                                    yr,
                                    "total_nw_utilization",
                                )
                            )
                            * a["total_inst"],
                            nw_avail(app, a["workload"], window),
                        )
                        for a in assign["assignment"]
                    )
                    assign["utilization"][yr]["window_nic_pct"][window] += nw_util_pct

                    nw_util = utils.Size.sum(
                        a["workload"].resource_for_year(
                            data["site_name"],
                            window,
                            yr,
                            "total_nw_utilization",
                        )
                        * a["total_inst"]
                        for a in assign["assignment"]
                    )
                    assign["utilization"][yr]["window_nic"][window] += nw_util

                    dr_nw_util = utils.Size.sum(
                        a["workload"].resource_for_year(
                            data["site_name"],
                            window,
                            yr,
                            "total_dr_nw_utilization",
                        )
                        * a["total_inst"]
                        for a in assign["assignment"]
                    )
                    if window == task.WindowType.replication:
                        assign["utilization"][yr]["window_nic_dr"][window] += dr_nw_util

                    cloud_nw_util = utils.Size.sum(
                        a["workload"].ltr_resource_for_year(
                            data["site_name"],
                            window,
                            yr,
                            "total_cloud_nw_utilization",
                        )
                        * a["total_inst"]
                        for a in assign["assignment"]
                    )
                    if window == task.WindowType.replication:
                        assign["utilization"][yr]["window_nic_cloud"][
                            window
                        ] += cloud_nw_util
                assign["utilization"][yr]["cpu"] = sum(
                    assign["utilization"][yr]["window_cpu"].values()
                )
                assign["utilization"][yr]["nic_pct"] = sum(
                    assign["utilization"][yr]["window_nic_pct"].values()
                )
                assign["utilization"][yr]["nic"] = utils.Size.sum(
                    assign["utilization"][yr]["window_nic"].values()
                )
                assign["utilization"][yr]["nic_dr"] = utils.Size.sum(
                    assign["utilization"][yr]["window_nic_dr"].values()
                )
                assign["utilization"][yr]["nic_cloud"] = utils.Size.sum(
                    assign["utilization"][yr]["window_nic_cloud"].values()
                )

            for assign in assignment:
                for a in assign["assignment"]:
                    if "w_utilization" not in a:
                        a["w_utilization"] = {}
                    a["w_utilization"][yr] = {}
                    a["w_utilization"][yr][a["workload"].name] = {}
                    a["w_utilization"][yr][a["workload"].name]["workload_capacity"] = (
                        utils.Size.assume_unit(0, "TiB")
                    )
                    a["w_utilization"][yr][a["workload"].name][
                        "nic_workload"
                    ] = utils.Size.ZERO
                    if a["mode"] != WorkloadMode.media_primary:
                        continue
                    capacity = a["workload"].total_storage_for_year(yr)
                    a["w_utilization"][yr][a["workload"].name]["workload_capacity"] = (
                        capacity * a["total_inst"]
                    )

                    dr_nw_util = (
                        a["workload"].resource_for_year(
                            data["site_name"],
                            task.WindowType.replication,
                            yr,
                            "total_dr_nw_utilization",
                        )
                        * a["total_inst"]
                    )
                    cloud_nw_util = (
                        a["workload"].ltr_resource_for_year(
                            data["site_name"],
                            task.WindowType.replication,
                            yr,
                            "total_cloud_nw_utilization",
                        )
                        * a["total_inst"]
                    )
                    a["w_utilization"][yr][a["workload"].name]["nic_workload"] = (
                        dr_nw_util + cloud_nw_util
                    )
            utilizations.append(
                {
                    "absolute_capacity": utils.Size.sum(
                        assign["utilization"][yr]["absolute_capacity"]
                        for assign in assignment
                    ),
                    "alloc_capacity": utils.Size.sum(
                        assign["utilization"][yr]["alloc_capacity"]
                        for assign in assignment
                    ),
                    "capacity": max(
                        assign["utilization"][yr]["capacity"] for assign in assignment
                    ),
                    "alloc_capacity_pct": max(
                        assign["utilization"][yr]["alloc_capacity_pct"]
                        for assign in assignment
                    ),
                    "cpu": max(
                        assign["utilization"][yr]["cpu"] for assign in assignment
                    ),
                    "mem": max(
                        assign["utilization"][yr]["mem"] for assign in assignment
                    ),
                    "absolute_memory": max(
                        assign["utilization"][yr]["absolute_memory"]
                        for assign in assignment
                    ),
                    "absolute_io": utils.Size.sum(
                        assign["utilization"][yr]["absolute_io"]
                        for assign in assignment
                    ),
                    "io": max(assign["utilization"][yr]["io"] for assign in assignment),
                    "nic_pct": max(
                        assign["utilization"][yr]["nic_pct"] for assign in assignment
                    ),
                    "nic": utils.Size.sum(
                        assign["utilization"][yr]["nic"] for assign in assignment
                    ),
                    "nic_dr": utils.Size.sum(
                        assign["utilization"][yr]["nic_dr"] for assign in assignment
                    ),
                    "nic_cloud": utils.Size.sum(
                        assign["utilization"][yr]["nic_cloud"] for assign in assignment
                    ),
                    "DR Transfer GiB/Week": utils.Size.sum(
                        assign["utilization"][yr]["DR Transfer GiB/Week"]
                        for assign in assignment
                    ),
                    "Cloud Transfer GiB/week": utils.Size.sum(
                        assign["utilization"][yr]["Cloud Transfer GiB/week"]
                        for assign in assignment
                    ),
                    "Cloud Minimum Bandwidth(Mbps)": utils.Size.sum(
                        (
                            assign["utilization"][yr]["Cloud Transfer GiB/week"]
                            / self.window_sizes.replication_hours
                        )
                        * ((1024 / 3600) * 8.388608 * 1.05)
                        for assign in assignment
                    ),
                    "Full Backup": utils.Size.sum(
                        assign["utilization"][yr]["Full Backup"]
                        for assign in assignment
                    ),
                    "Incremental Backup": utils.Size.sum(
                        assign["utilization"][yr]["Incremental Backup"]
                        for assign in assignment
                    ),
                    "Size Before Deduplication": utils.Size.sum(
                        assign["utilization"][yr]["Size Before Deduplication"]
                        for assign in assignment
                    ),
                    "Size After Deduplication": utils.Size.sum(
                        assign["utilization"][yr]["Size After Deduplication"]
                        for assign in assignment
                    ),
                }
            )
        return utilizations

    def _log_max_fit_info(self, workload, window, dimension, instances):
        key = (workload["name"], window, dimension)
        if key in self.max_fits_logged:
            return
        logger.info(
            "bottleneck for media: workload %s, dimension %s, window %s, instances %s",
            workload["name"],
            dimension,
            window,
            instances,
        )
        self.max_fits_logged.add(key)

    def _choose_max_fit(self, w, b):
        details = {}
        arr = []
        for resource in [
            "capacity",
            "cloud_capacity",
            "jobs/day",
            "dbs",
            "vms",
            "files",
            "images",
        ]:
            if b[resource] is None or w[resource] == 0:
                self._log_max_fit_info(w, "nowindow", resource, "infinite")
                continue
            max_fit = b[resource] // w[resource]
            if max_fit == 0:
                if resource == "capacity":
                    capacity = int(w[resource] / (1024 * 1024))
                    capacity_available = int(b[resource] / (1024 * 1024))
                    unit = "GB"
                else:
                    capacity = w[resource]
                    capacity_available = b[resource]
                    unit = resource
                error_text = NON_WINDOW_ERROR_TEXT.format(
                    workload_name=w["name"],
                    capacity_value=capacity,
                    unit_value=unit,
                    appliance_config=b["config_name"],
                    capacity_available_value=capacity_available,
                )
                logger.info(error_text)
                raise WorkloadMisfitMediaError(w["name"], error_text)
            self._log_max_fit_info(w, "nowindow", resource, max_fit)
            arr.append(max_fit)
            details[resource] = max_fit

        if b["appliance_model"] in appliance.get_models("performance_supported"):
            nw_details = []
            for resource in [
                "cpu",
                "io",
                "nw_1g",
                "nw_10g_copper",
                "nw_10g_sfp",
                "nw_25g_sfp",
                "nw_cloud",
            ]:
                window_details = []
                for window in (
                    task.WindowType.full,
                    task.WindowType.replication,
                    task.WindowType.incremental,
                ):
                    reqd = w[(resource, window)]
                    avail = b[(resource, window)]
                    if reqd == 0:
                        self._log_max_fit_info(w, window, resource, "infinite")
                        continue

                    if resource == "cpu":
                        avail = b[("solo_cpu", window)]

                    max_fit = avail // reqd
                    if max_fit == 0:
                        error_text = WINDOW_ERROR_TEXT.format(
                            workload_name=w["name"],
                            resource_value=resource,
                            window_size=reqd,
                            window_type=window,
                            window_available=avail,
                        )
                        logger.info(error_text)
                        raise WorkloadMisfitMediaError(w["name"], error_text)
                    self._log_max_fit_info(w, window, resource, max_fit)
                    arr.append(max_fit)
                    window_details.append(max_fit)
                if window_details and resource in ["cpu", "io"]:
                    details[resource] = min(window_details)
                elif window_details:
                    nw_details.extend(window_details)
            if nw_details:
                details["nw"] = min(nw_details)
        return min(arr), details
