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
import enum
import functools
import itertools
import logging
from types import SimpleNamespace
import typing

from ortools.sat.python import cp_model

from use_core import appliance
from use_core import constants
from use_core import task
from use_core import utils
from use_core.media_packing import (  # noqa: F401
    PackingError,
)
from use_core.utils import WorkloadSummary

logger = logging.getLogger(__name__)


class ContainerMisfitError(Exception):
    def __init__(self, container_name, error_text):
        self.container_name = container_name
        self.error_text = error_text

    def __str__(self):
        return self.error_text


class ContainerType(enum.Enum):
    primary = enum.auto()
    media = enum.auto()
    msdp_cloud = enum.auto()

    def __str__(self):
        visible_names = {
            "media": "Media Server",
            "primary": constants.MANAGEMENT_SERVER_DESIGNATION,
            "msdp_cloud": "MSDP-C",
        }
        return visible_names[self.name]


ERROR_TEXT = """
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
This means that the Flex Appliance cannot support a single client for the given workload.
"""


class Container:
    def __init__(self, domain, site, type, name, obj, nmedia=None):
        self.domain = domain
        self.site = site
        self.type = type
        self.name = name
        self.obj = obj
        self.nmedia = nmedia

    def __str__(self):
        return str(self.__class__) + ": " + str(self.__dict__)

    def __repr__(self):
        return str(self.__class__) + ": " + str(self.__dict__)

    def abs_capacity(self, yr):
        return self.obj.utilization.get("absolute_capacity", yr)

    def capacity(self, yr, appconfig=None):
        appl = self.obj.appliance
        if appconfig:
            appl = appconfig
        abs_capacity = self.obj.utilization.get("absolute_capacity", yr)
        if self.type == ContainerType.primary:
            return abs_capacity
        elif self.type == ContainerType.media:
            if appl.requires_storage_roundup:
                r_up = appl.lun_size
                return abs_capacity.roundup(r_up)
            else:
                return abs_capacity
        elif self.type == ContainerType.msdp_cloud:
            abs_capacity = appl.msdp_container_size
            if appl.requires_storage_roundup:
                r_up = appl.lun_size
                return abs_capacity.roundup(r_up)
            else:
                return abs_capacity

    def memory(self, yr, appconfig):
        if self.type == ContainerType.primary:
            # appconfig is the flex appliance we're sizing.  The
            # reservation is configured on this appliance.
            # self.obj.appliance refers to the appliance the container
            # was originally sized for.  For a master server
            # container, it could be a 5150 or a 5250, but if we're
            # sizing a 5340-Flex appliance, the reservation needs to
            # be looked up there.
            reservation = appconfig.primary_reservation(self.nmedia)
            if reservation["memory"]:
                return reservation["memory"]
            else:
                return (
                    self.obj.utilization.get("absolute_memory", yr)
                    * constants.MEMORY_SHARING_DISCOUNT
                )
        elif self.type == ContainerType.media:
            # rule of thumb is that media containers get 1 GiB of
            # memory per TiB of storage managed.  We lower memory
            # requirement slightly to account for host memory that
            # can be shared across containers (such as pagecache).
            abs_capacity = self.obj.utilization.get("absolute_capacity", yr)
            if self.obj.appliance.requires_storage_roundup:
                r_up = self.obj.appliance.lun_size
                abs_capacity_r_up = abs_capacity.roundup(r_up)
                cap_tib = abs_capacity_r_up.to_float("TiB")
                return utils.Size.assume_unit(
                    cap_tib * constants.MEMORY_SHARING_DISCOUNT, "GiB"
                )
            else:
                cap_tib = abs_capacity.to_float("TiB")
                return utils.Size.assume_unit(
                    cap_tib * constants.MEMORY_SHARING_DISCOUNT, "GiB"
                )
        elif self.type == ContainerType.msdp_cloud:
            # msdp-cloud container uses the same capacity rule of
            # media containers to calculate the memory usage, and
            # rule of thumb is that media containers get 1 GiB of
            # memory per TiB of storage managed.  We lower memory
            # requirement slightly to account for host memory that
            # can be shared across containers (such as pagecache).
            abs_capacity = self.obj.utilization.get("absolute_capacity", yr)
            cap_by_total_lsus = utils.Size.assume_unit(
                constants.MSDP_CLOUD_TOTAL_LSU_PB, "PiB"
            )
            appl_mem = self.obj.appliance.safe_memory
            appl_mem_pct = appl_mem * constants.MSDP_CLOUD_MAX_CACHE_PCT
            if self.obj.appliance.requires_storage_roundup:
                r_up = self.obj.appliance.lun_size
                abs_capacity_r_up = abs_capacity.roundup(r_up)
                cap_tib = min(cap_by_total_lsus, abs_capacity_r_up).to_float("TiB")
                return min(
                    utils.Size.assume_unit(
                        cap_tib * constants.MEMORY_SHARING_DISCOUNT, "GiB"
                    ),
                    appl_mem_pct,
                )
            else:
                cap_by_lsu = utils.Size.assume_unit(
                    constants.MSDP_CLOUD_MIN_LSU_TB, "TiB"
                )
                cap_tip = min(
                    cap_by_total_lsus, max(cap_by_lsu, abs_capacity)
                ).to_float("TiB")
                return min(
                    utils.Size.assume_unit(
                        cap_tip * constants.MEMORY_SHARING_DISCOUNT, "GiB"
                    ),
                    appl_mem_pct,
                )

    def cpu_real(self, yr, window):
        return self.obj.utilization.get(("window_cpu", window), yr)

    def cpu_reserved(self, appconfig: appliance.Appliance):
        if self.type == ContainerType.primary:
            return appconfig.primary_reservation(self.nmedia)["cpu"]
        else:
            return 0

    def cpu(self, yr, window, appconfig: appliance.Appliance):
        ctr_cpu = self.cpu_real(yr, window)
        if self.type == ContainerType.primary:
            reservation = self.cpu_reserved(appconfig)
            return max(reservation, ctr_cpu)
        else:
            return ctr_cpu

    def io(self, yr):
        return self.obj.utilization.get("io", yr)

    def nic(self, yr, window):
        return self.obj.utilization.get(("window_nic_pct", window), yr)

    def jobs_per_day(self, yr):
        return self.obj.utilization.get("media_jobs/day", yr)

    def dbs(self, yr):
        return self.obj.utilization.get("media_dbs", yr)

    def vms(self, yr):
        return self.obj.utilization.get("media_vms", yr)


class FlexAppliance:
    def __init__(self, appliance, containers):
        self.appliance = appliance
        self.containers = containers

        self.utilization = utils.YearOverYearUtilization()

    def rightsize(self, timeframe):
        storage_used = self.utilization.get("alloc_capacity", timeframe.planning_year)
        new_appliance = self.appliance.rightsize(storage_used, flex=True)
        for yr in range(1, timeframe.num_years + 1):
            abs_capacity = self.utilization.get("absolute_capacity", yr)
            new_rel_capacity = new_appliance.calculated_capacity_orig.utilization(
                [abs_capacity]
            )
            self.utilization.replace("capacity", yr, new_rel_capacity)
            alloc_capacity = self.utilization.get("alloc_capacity", yr)
            new_rel_alloc_capacity = new_appliance.calculated_capacity_orig.utilization(
                [alloc_capacity]
            )
            self.utilization.replace("alloc_capacity_pct", yr, new_rel_alloc_capacity)
        self.appliance = new_appliance

    @property
    def appliance_summary_attributes(self):
        return constants.RAW_APPLIANCE_SUMMARY_ATTRIBUTES + [
            "files",
            "images",
            "jobs/day",
        ]


ApplianceConfig = str
Site = str
SiteSummary = typing.Dict[Site, int]


class FlexSizerSummary:
    def __init__(
        self,
        appliance_summary: typing.Dict[ApplianceConfig, SiteSummary],
        appliances: typing.Dict[str, appliance.Appliance],
    ):
        self.appliance_summary = appliance_summary
        self.appliances = appliances

    @property
    def flex_app_site_summaries(self):
        for config_name, site_summary in sorted(self.appliance_summary.items()):
            cfg_summary = {}
            for site_name, appliance_count in sorted(site_summary.items()):
                cfg_summary[site_name] = appliance_count
            yield config_name, cfg_summary


FlexSiteAssignment = typing.List[FlexAppliance]


class FlexSizerResult:
    timeframe: utils.TimeFrame
    sites: typing.Dict[Site, FlexSiteAssignment]
    workload_summary_attributes: typing.Dict[
        typing.Tuple[str, str], typing.List[WorkloadSummary]
    ]

    def __init__(self, timeframe, ltr_target):
        self.timeframe = timeframe
        self.ltr_target = ltr_target
        self.sites = {}
        self.workload_summary_attributes = collections.defaultdict(list)

    def all_domains_in_site(self, site):
        for site_name, appliance_name, app in self.all_appliances:
            if site_name != site:
                continue
            domains = set()
            for container in app.containers:
                if container.domain in domains:
                    continue
                domains.add(container.domain)
                yield container.domain

    def set_site_assignment(self, site_name, appliances):
        self.sites[site_name] = appliances

    def site_utilization(self, site_name, year=None):
        if year is None:
            year = self.planning_year
        max_site_utilization = 0
        for app in self.sites[site_name]:
            s_util = app.utilization.get_max_proportion_for_year(year)
            if max_site_utilization < s_util:
                max_site_utilization = s_util
        return max_site_utilization

    @property
    def _all_site_utilizations(self):
        for site_name, site_assignment in sorted(self.sites.items()):
            for app in site_assignment:
                yield app.utilization

    @property
    def site_assignments(self):
        for site_name, site_assignment in self.sites.items():
            obj = SimpleNamespace()
            obj.flex_servers = site_assignment
            yield (None, site_name, obj)

    @property
    def all_appliances(self):
        for site_name, appliances in sorted(self.sites.items()):
            for idx, app in enumerate(appliances):
                yield (site_name, f"{site_name}-{idx+1}", app)

    @property
    def all_containers(self):
        def container_sort_key(container):
            if container.type == ContainerType.primary:
                type_key = 1
            elif container.type == ContainerType.media:
                type_key = 2
            elif container.type == ContainerType.msdp_cloud:
                type_key = 3
            return (container.domain, type_key)

        for site_name, appliance_name, app in self.all_appliances:
            for container in sorted(app.containers, key=container_sort_key):
                yield (
                    container.domain,
                    site_name,
                    appliance_name,
                    app,
                    container.name,
                    container.type,
                    container.obj,
                )

    @property
    def num_years(self):
        return self.timeframe.num_years

    @property
    def planning_year(self):
        return self.timeframe.planning_year

    @property
    def summary(self) -> FlexSizerSummary:
        appliances = {}

        appliance_summary = collections.defaultdict(
            lambda: collections.defaultdict(int)
        )
        for site_name, appliance_id, app in self.all_appliances:
            appliance_name = app.appliance.config_name
            appliances[appliance_name] = app.appliance
            appliance_summary[appliance_name][site_name] += 1

        return FlexSizerSummary(appliance_summary, appliances)

    @property
    def yoy_max_utilization(self):
        overall_max = functools.reduce(
            utils.YearOverYearUtilization.combine_by_max,
            self._all_site_utilizations,
        )
        result = []
        for yr in range(1, 1 + self.num_years):
            year_utilization = dict(
                (dimension, overall_max.get(dimension, yr))
                for dimension in utils.YearOverYearUtilization.PERCENTAGE_DIMENSIONS
            )
            result.append(year_utilization)
        return result

    @property
    def yoy_utilization_by_workload(self):
        aggregate = collections.defaultdict(utils.YearOverYearUtilization)
        for (
            domain,
            site_name,
            appliance_name,
            app,
            container_name,
            container_type,
            container_obj,
        ) in self.all_containers:
            for assigned_workload in container_obj.workloads:
                if assigned_workload.mode not in [
                    utils.WorkloadMode.media_primary,
                    utils.WorkloadMode.media_cloud,
                ]:
                    continue
                wk = assigned_workload.workload
                aggregate[(wk.name, site_name)] = aggregate[
                    (wk.name, site_name)
                ].combine_by_sum(
                    assigned_workload.w_utilization,
                    self.num_years,
                    constants.WORKLOAD_SUMMARY_ATTRIBUTES,
                )
        return aggregate

    def rightsize_appliances(self, selector):
        for site_name, site_assignment in self.sites.items():
            if not selector(site_name):
                continue

            for appl in site_assignment:
                appl.rightsize(self.timeframe)


# resources involved in flex sizing. For each flex appliance, the sum
# of the values for these resources per container must stay within the
# value available with the appliance.
FLEX_CONSTRAINTS = [
    "primary_containers",
    "msdp_containers",
    "capacity",
    "memory",
    "io",
    "jobs/day",
    "dbs",
    "vms",
    *(("cpu", window) for window in task.WindowType.packing_windows()),
    *(("nic", window) for window in task.WindowType.packing_windows()),
]


class FlexSizerContext:
    def __init__(self, container_result, progress_cb, flex_configs, rightsize):
        self.container_result = container_result
        self.progress_cb = progress_cb
        self.flex_configs = flex_configs
        self.rightsize = rightsize

        self.timeframe = self.container_result.timeframe
        self.workload_fits_logged = set()

    def pack(self) -> FlexSizerResult:
        self.result = FlexSizerResult(self.timeframe, self.container_result.ltr_target)
        self.result.domains_split = self.container_result.domains_split
        self.result.primary_errors = self.container_result.primary_errors
        self.result.access_result = self.container_result.access_result

        sites = self.container_result.all_sites
        for site_name in sites:
            appliances = self._solve_for_site(site_name)
            self.result.set_site_assignment(site_name, appliances)

        if self.rightsize:
            self.result.rightsize_appliances(self.rightsize)

        return self.result

    def _get_container_groups(
        self, containers: typing.List[Container]
    ) -> typing.List[Container]:
        container_grp = []
        for grp_key, group in itertools.groupby(
            sorted(
                containers,
                key=lambda container: container.obj.workloads[
                    0
                ].workload.workload_isolation,
                reverse=True,
            ),
            lambda container: container.obj.workloads[0].workload.workload_isolation,
        ):
            if grp_key:
                for container in group:
                    container_grp.append([container])
                logger.debug("registering %d isolated containers", len(container_grp))
            else:
                container_grp.append([container for container in group])

        return container_grp

    def _solve_for_site(self, site_name):
        self._progress(f"Sizing flex appliances for site {site_name}")
        appconfig = self.flex_configs[site_name]
        logger.debug("using appliance %s for site %s", appconfig.config_name, site_name)
        servers = self._servers_for_site(site_name)
        container_grps = self._get_container_groups(servers)
        grp_result = []
        for container_grp in container_grps:
            container_list = [
                self._convert_one_container(c, appconfig) for c in container_grp
            ]
            appliance_data = self._convert_one_appliance(appconfig)
            n_appliances, hints = self._min_appliances(container_list, appliance_data)
            logger.debug(
                "attempting to flex size with %d appliances",
                n_appliances,
            )
            solver_data = self._build_solver_data_model(
                container_list, appliance_data, n_appliances
            )
            solver_data["appliance"] = appconfig
            solver_data["hints"] = hints
            grp_result += self._solve(solver_data)
        return grp_result

    def _servers_for_site(self, site_name):
        servers = []
        for container_spec in self.container_result.all_servers:
            if container_spec.site != site_name:
                continue
            servers.append(container_spec)
        return servers

    def _progress(self, status, detail=None):
        if self.progress_cb is None:
            return
        self.progress_cb(status, detail)

    def _build_solver_data_model(self, container_list, appliance_data, num_appliances):
        container_name_map = dict((c["name"], c) for c in container_list)
        appliance_list = [
            self._index_one_appliance(i, appliance_data) for i in range(num_appliances)
        ]

        return {
            "num_items": self.container_result.num_servers,
            "containers": container_list,
            "container_names": container_name_map,
            "appliances": appliance_list,
        }

    def _convert_one_container(
        self, container_spec: Container, appconfig: appliance.Appliance
    ):
        c = {
            "name": container_spec.name,
            "obj": container_spec,
            "primary_containers": 0,
            "msdp_containers": 0,
        }
        if container_spec.type == ContainerType.primary:
            c["primary_containers"] = 1
        else:
            c["msdp_containers"] = 1

        yr = self.container_result.planning_year
        c["capacity"] = int(container_spec.capacity(yr, appconfig))
        c["memory"] = int(container_spec.memory(yr, appconfig))
        for window in task.WindowType.packing_windows():
            c[("cpu", window)] = int(container_spec.cpu(yr, window, appconfig) * 100)
            c[("nic", window)] = int(container_spec.nic(yr, window) * 100)
        c["io"] = int(container_spec.io(yr) * 100)
        c["jobs/day"] = int(container_spec.jobs_per_day(yr))
        c["dbs"] = container_spec.dbs(yr)
        c["vms"] = container_spec.vms(yr)
        for item, data in c.items():
            msg = f"Container - {item} is {data}"
            if item == "obj":
                continue
            logger.debug(msg)
        for obj_k, obj_v in c["obj"].__dict__.items():
            msg = f"Container obj - {obj_k} is {obj_v}"
            if obj_k == "obj":
                continue
            logger.debug(msg)
        for app_k, app_v in c["obj"].obj.__dict__.items():
            msg = f"Container obj.obj - {app_k} is {app_v}"
            if app_k == "workloads":
                for wk in app_v:
                    msg = f"Container obj.obj.workloads - {wk}"
            logger.debug(msg)
        return c

    def _index_one_appliance(self, idx, appliance_data):
        a = dict(appliance_data)  # ensure a separate copy
        a["appliance_id"] = idx
        return a

    def _convert_one_appliance(self, appliance_spec):
        a = {
            "primary_containers": appliance_spec.primary_container_limit,
            "msdp_containers": appliance_spec.msdp_container_limit,
        }
        a["capacity"] = int(appliance_spec.flex_capacity)
        a["memory"] = int(appliance_spec.safe_memory)
        for window in task.WindowType:
            a[("cpu", window)] = int(appliance_spec.max_cpu * 100)
            a[("nic", window)] = int(appliance_spec.max_nw * 100)
        a["io"] = int(appliance_spec.max_io * 100)

        app_ss = appliance_spec.software_safety
        a["jobs/day"] = app_ss.jobs_per_day
        a["dbs"] = app_ss.dbs_15min_rpo
        a["vms"] = app_ss.vm_clients
        logger.debug("flex appliance provides %s", a)
        return a

    def _min_appliances(self, container_list, appliance_data):
        res_available = dict(appliance_data)
        appliances_consumed = 0
        hints = set()
        for c_idx, c in enumerate(container_list):
            if any(
                res_available[res] is not None and res_available[res] < c[res]
                for res in FLEX_CONSTRAINTS
            ):
                appliances_consumed += 1
                res_available = dict(appliance_data)
            res_available.update(
                (
                    res,
                    (
                        res_available[res] - c[res]
                        if res_available[res] is not None
                        else None
                    ),
                )
                for res in FLEX_CONSTRAINTS
            )
            hints.add((c_idx, appliances_consumed + 1))
        return (appliances_consumed + 1, hints)

    def _solve(self, data):
        model = cp_model.CpModel()

        # x[(i, j)] is whether container i is assigned to appliance j
        x = {}
        for idx, w in enumerate(data["containers"]):
            for b in data["appliances"]:
                b["appliance_model"] = data["appliance"].appliance
                b["config_name"] = data["appliance"].config_name
                self._check_flex_workload_fit(w, b)
                app_id = b["appliance_id"]
                x[(idx, app_id)] = model.NewIntVar(0, 1, f"x_{idx}_{app_id}")

        used_vars = {}
        for dim in FLEX_CONSTRAINTS:
            if b[dim] is None:
                continue
            used_vars[dim] = [
                model.NewIntVar(0, b[dim], f"{dim}_used_{b['appliance_id']}")
                for b in data["appliances"]
            ]

        for b in data["appliances"]:
            app_id = b["appliance_id"]
            for dim, varlist in used_vars.items():
                model.Add(
                    varlist[app_id]
                    == sum(
                        x[(i, app_id)] * c[dim]
                        for (i, c) in enumerate(data["containers"])
                    )
                )

        # Each item can be in exactly one appliance.
        for idx, c in enumerate(data["containers"]):
            model.Add(sum(x[(idx, b["appliance_id"])] for b in data["appliances"]) == 1)

        # Calculate how many appliances are used.  appliance_used[i] is 1
        # if the appliance has been assigned at least one container, 0
        # otherwise.
        appliance_used = []
        num_items = []
        for b in data["appliances"]:
            app_id = b["appliance_id"]
            var_name = "appliance_{}_used".format(app_id)
            appliance_used.append(model.NewIntVar(0, 1, var_name))
            num_items.append(
                model.NewIntVar(0, data["num_items"], "num_items_{}".format(app_id))
            )
            model.Add(
                num_items[app_id]
                == sum(x[(idx, app_id)] for (idx, _) in enumerate(data["containers"]))
            )
            model.AddMinEquality(appliance_used[app_id], [1, num_items[app_id]])
            if app_id > 0:
                # this constraint "front-loads" the appliances, so
                # appliances with lower index are used in preference
                # to appliances with higher index.  This makes sure
                # that all the unused appliances collect at the end of
                # the array.
                model.Add(num_items[app_id - 1] >= num_items[app_id])

        for b in data["appliances"]:
            app_id = b["appliance_id"]
            for container_idx, c in enumerate(data["containers"]):
                key = (container_idx, app_id)
                if key in data["hints"]:
                    model.AddHint(x[key], 1)
                else:
                    model.AddHint(x[key], 0)

        # Minimize number of appliances used
        model.Minimize(sum(appliance_used))

        solver = cp_model.CpSolver()
        status = cp_model.UNKNOWN
        chunk_time = constants.FLEX_CHUNK_TIME
        workers = utils.cpu_count()
        nchunks = 1 + data["num_items"] // constants.FLEX_CHUNK_SIZE
        solver.parameters.num_search_workers = workers

        while status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            timeout = max(constants.MIN_SOLVER_TIMEOUT, chunk_time * nchunks // workers)
            solver.parameters.max_time_in_seconds = timeout

            msg = f"Searching solution for {timeout} seconds..."
            self._progress(None, msg)

            status = solver.Solve(model)
            if status == cp_model.INFEASIBLE:
                # solver has proved that no solution is possible.
                # There is no point in retrying with higher timeout.
                raise PackingError(ERROR_TEXT)
            if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
                # solver was unable to find a solution, but was also
                # unable to conclude that no solution is possible.
                # Check if we can retry with higher timeout.
                chunk_time *= constants.TIMEOUT_SCALING

        appliances = self._parse_solution(data, solver, x)
        self._calculate_utilization(appliances)
        return appliances

    def _parse_solution(self, data, solver, x):
        appliances = collections.defaultdict(dict)
        for idx, c in enumerate(data["containers"]):
            for b in data["appliances"]:
                app_id = b["appliance_id"]
                val = solver.Value(x[(idx, app_id)])
                if val:
                    appliances[app_id][c["name"]] = val

        result = []
        for app_id in appliances:
            app_containers = []
            for cname in appliances[app_id]:
                container_info = data["container_names"][cname]
                app_containers.append(container_info["obj"])
            result.append(
                FlexAppliance(
                    appliance=data["appliance"],
                    containers=app_containers,
                )
            )

        return result

    def _calculate_utilization(self, appliances: typing.List[FlexAppliance]):
        for app in appliances:
            ctr_utils = [ctr.obj.utilization for ctr in app.containers]
            for dim in [
                "absolute_io",
                "io",
                "nic_pct",
                "nic_dr",
                "nic_cloud",
                "DR Transfer GiB/Week",
                "Cloud Transfer GiB/week",
                "Cloud Minimum Bandwidth(Mbps)",
                "cloud_gib_months",
                "cloud_gib_months_worst_case",
                "cloud_gib_per_week",
                "Full Backup",
                "Incremental Backup",
                "Size Before Deduplication",
                "Size After Deduplication",
                "files",
                "images",
                "jobs/day",
            ]:
                app.utilization.sum_yoy(ctr_utils, self.timeframe.num_years, dim)

            # Memory/CPU are accounted for differently in Flex than
            # other dimensions.  The memory/CPU requirements for
            # containers follow the best practices documented for Flex
            # sizing, and the memory/CPU requirements of individual
            # containers cannot be simply added up.
            for yr in range(1, self.timeframe.num_years + 1):
                abs_mem = utils.Size.sum(
                    ctr.memory(yr, app.appliance) for ctr in app.containers
                )
                app.utilization.add("absolute_memory", yr, abs_mem)

                ctr_cpus = []
                ctr_nics = []
                for ctr in app.containers:
                    cpu = sum(
                        ctr.cpu_real(yr, window)
                        for window in task.WindowType.packing_windows()
                    )
                    ctr_cpus.append(max(cpu, ctr.cpu_reserved(app.appliance)))
                    nic = sum(
                        ctr.nic(yr, window)
                        for window in task.WindowType.packing_windows()
                    )
                    ctr_nics.append(nic)
                app.utilization.add("cpu", yr, sum(ctr_cpus))
                app.utilization.add("nic", yr, sum(ctr_nics))

                abs_cap = utils.Size.sum(ctr.abs_capacity(yr) for ctr in app.containers)
                alloc_cap = utils.Size.sum(
                    ctr.capacity(yr, app.appliance) for ctr in app.containers
                )
                app.utilization.add("absolute_capacity", yr, abs_cap)
                app.utilization.add("alloc_capacity", yr, alloc_cap)

            for yr in range(1, self.timeframe.num_years + 1):
                abs_cap = app.utilization.get("absolute_capacity", yr)
                alloc_cap = app.utilization.get("alloc_capacity", yr)
                rel_cap = app.appliance.calculated_capacity_orig.utilization([abs_cap])
                app.utilization.add("capacity", yr, rel_cap)
                rel_alloc_cap = app.appliance.calculated_capacity_orig.utilization(
                    [alloc_cap]
                )
                app.utilization.add("alloc_capacity_pct", yr, rel_alloc_cap)

                abs_mem = app.utilization.get("absolute_memory", yr)
                rel_mem = app.appliance.memory.utilization([abs_mem])
                app.utilization.add("mem", yr, rel_mem)

    def _log_flex_workload_fit_info(self, workload, window, dimension, instances):
        key = (workload["name"], window, dimension)
        if key in self.workload_fits_logged:
            return
        logger.info(
            "bottleneck value for flex: workload %s, dimension %s, window %s, instances %s",
            workload["name"],
            dimension,
            window,
            instances,
        )
        self.workload_fits_logged.add(key)

    def _check_flex_workload_fit(self, w, b):
        # Total resource usage per appliance
        for resource in FLEX_CONSTRAINTS:
            if b[resource] is None or w[resource] == 0:
                self._log_flex_workload_fit_info(w, "nowindow", resource, "infinite")
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
                raise ContainerMisfitError(w["name"], error_text)
            self._log_flex_workload_fit_info(w, "nowindow", resource, max_fit)
