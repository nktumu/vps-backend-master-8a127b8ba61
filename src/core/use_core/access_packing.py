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
import contextlib
import logging
import typing

from ortools.sat.python import cp_model

from use_core import access_appliance
from use_core import constants
from use_core import media_packing
from use_core import task
from use_core import utils


logger = logging.getLogger(__name__)


NON_WINDOW_ERROR_TEXT = """
Sizing failed because:
- The workload {workload_name} on media server {media_server} requires {capacity_value} {unit_value}
- The Access appliance offers {capacity_available_value} {unit_value}
"""


class AccessMisfitError(Exception):
    def __init__(self, media_server, workload_name, error_text):
        self.media_server = media_server
        self.workload_name = workload_name
        self.error_text = error_text

    def __str__(self):
        return self.error_text


class AccessAppliance:
    """Represents a single assigned Access appliance."""

    appliance: str
    workload_groups: typing.List[typing.Tuple[str, str]]
    utilization: utils.YearOverYearUtilization

    def __init__(self, appliance, workload_groups):
        self.appliance = appliance
        self.workload_groups = workload_groups
        self.utilization = utils.YearOverYearUtilization()


class AccessSizerResult:
    """Result of sizing Access appliances."""

    site_assignments: typing.Dict[str, typing.List[AccessAppliance]]

    def __init__(self):
        self.site_assignments = {}

    def set_site_assignment(self, site_name, assignment):
        self.site_assignments[site_name] = assignment

    @property
    def all_appliances(self) -> typing.List[typing.Tuple[str, str, AccessAppliance]]:
        for site_name, assignment in self.site_assignments.items():
            for idx, app in enumerate(assignment):
                yield site_name, f"{site_name}-access-{idx+1}", app

    @property
    def summary(self):
        appconfigs = collections.defaultdict(dict)
        for site_name, _, assigned_appliance in self.all_appliances:
            appliance_cfg = assigned_appliance.appliance.name
            if site_name not in appconfigs[appliance_cfg]:
                appconfigs[appliance_cfg][site_name] = 0
            appconfigs[appliance_cfg][site_name] += 1
        return appconfigs


class AccessSizerContext:
    """Context object that can size Access appliances for capacity and performance."""

    ACCESS_CONSTRAINTS = ["capacity", "cpu"]

    def __init__(self, nbu_result, timeframe, progress_cb, timer_ctx, appliance_spec):
        self.nbu_result = nbu_result
        self.timeframe = timeframe
        self.progress_cb = progress_cb
        self.timer_ctx = timer_ctx
        self.appliance_spec = appliance_spec

        self._workload_fits_logged = set()

    def pack(self) -> AccessSizerResult:
        """
        Solve for Access appliances.

        It will collect all the LTR assignments and produce a result
        which maps media/MSDP-C servers to Access appliances.
        """

        sites = self.nbu_result.all_sites

        result = AccessSizerResult()
        for site_name in sites:
            msg = f"sizing Access appliances for site {site_name}"
            with self._record_event(msg):
                self._progress(msg)
                site_result = self._pack_site(site_name)
                result.set_site_assignment(site_name, site_result)
        return result

    def _pack_site(self, site_name):
        wk_groups = []
        wk_group_capacities = {}
        wk_group_name_map = {}

        idx = 0
        for (
            server_name,
            assigned_server,
            assigned_workload,
        ) in self.nbu_result.ltr_assignments(site_name):
            cloud_cap = assigned_workload.workload.cloud_storage_worst_case_for_year(
                self.timeframe.planning_year
            )
            wk_group_capacity = cloud_cap * assigned_workload.num_clients

            wk_group_name = (server_name, assigned_workload.workload.name)

            wk_group_duration = (
                assigned_workload.workload.ltr_resource_for_year(
                    site_name,
                    task.WindowType.replication,
                    self.timeframe.planning_year,
                    "total_job_duration",
                )
                * assigned_workload.num_clients
            )
            wk_group_name_map[wk_group_name] = assigned_workload
            wk_groups.append(
                {
                    "idx": idx,
                    "name": wk_group_name,
                    "capacity": int(wk_group_capacity),
                    "cpu": wk_group_duration,
                }
            )
            wk_group_capacities[wk_group_name] = wk_group_capacity
            idx += 1

        max_appliances = idx
        min_appliances = 2
        for n_appliances in utils.potential_appliance_counts(
            min_appliances, max_appliances
        ):
            logger.debug("attempting access sizing with %d appliances", n_appliances)

            appliances = [
                {
                    "idx": i,
                    "capacity": int(
                        self.appliance_spec.max_possible_capacity()
                        * self.appliance_spec.max_capacity
                    ),
                    "cpu": self.nbu_result.window_sizes.replication
                    * access_appliance.AccessAppliance.MAX_STREAMS,
                }
                for i in range(n_appliances)
            ]

            solver_data = {
                "wk_groups": wk_groups,
                "wk_group_name_map": wk_group_name_map,
                "wk_group_capacities": wk_group_capacities,
                "appliances": appliances,
                "num_items": idx,
            }

            for item, data in solver_data.items():
                msg = f"Access appliance solver data - {item} is {data}"
                if item == "wk_group_name_map":
                    wk_group = {}
                    for grp, w in data:
                        if grp not in wk_group:
                            wk_group[grp] = [w]
                        wk_group[grp].append(w)
                    msg = f"Access appliance solver data - {item} is {wk_group}"
                logger.debug(msg)
            try:
                return self._solve(solver_data)
            except media_packing.PackingError:
                pass
        else:
            raise media_packing.PackingError("Failed to size Access appliances.")

    def _solve(self, data):
        model = cp_model.CpModel()

        # x[(i, j)] is whether workload group i is assigned to
        # appliance j
        x = {}
        for idx, wk_group in enumerate(data["wk_groups"]):
            for b in data["appliances"]:
                app_id = b["idx"]
                self._check_access_workload_fit(wk_group, b)
                x[(idx, app_id)] = model.NewIntVar(0, 1, f"x_{idx}_{app_id}")

        used_vars = {}
        for dim in AccessSizerContext.ACCESS_CONSTRAINTS:
            used_vars[dim] = [
                model.NewIntVar(0, b[dim], f"{dim}_used_{b['idx']}")
                for b in data["appliances"]
            ]

        for b in data["appliances"]:
            app_id = b["idx"]
            for dim, varlist in used_vars.items():
                model.Add(
                    varlist[app_id]
                    == sum(
                        x[(i, app_id)] * s[dim]
                        for (i, s) in enumerate(data["wk_groups"])
                    )
                )

        # Each item can be in exactly one appliance.
        for idx, _server in enumerate(data["wk_groups"]):
            model.Add(sum(x[(idx, b["idx"])] for b in data["appliances"]) == 1)

        # Calculate how many appliances are used.  appliance_used[i]
        # is 1 if the appliance has been assigned at least one
        # workload group, 0 otherwise.
        appliance_used = []
        num_items = []
        for b in data["appliances"]:
            app_id = b["idx"]
            var_name = "appliance_{}_used".format(app_id)
            appliance_used.append(model.NewIntVar(0, 1, var_name))
            num_items.append(
                model.NewIntVar(0, data["num_items"], "num_items_{}".format(app_id))
            )
            model.Add(
                num_items[app_id]
                == sum(x[(idx, app_id)] for (idx, _) in enumerate(data["wk_groups"]))
            )
            model.AddMinEquality(appliance_used[app_id], [1, num_items[app_id]])
            if app_id > 0:
                # this constraint "front-loads" the appliances, so
                # appliances with lower index are used in preference
                # to appliances with higher index.  This makes sure
                # that all the unused appliances collect at the end of
                # the array.
                model.Add(num_items[app_id - 1] >= num_items[app_id])

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
                raise media_packing.PackingError("Failed to size Access appliances.")
            if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
                # solver was unable to find a solution, but was also
                # unable to conclude that no solution is possible.
                # Check if we can retry with higher timeout.
                chunk_time *= constants.TIMEOUT_SCALING

        appliances = self._parse_solution(data, solver, x)
        self._calculate_utilization(appliances, data)
        return appliances

    def _log_access_workload_fit_info(self, workload, window, dimension, instances):
        key = (workload["name"], window, dimension)
        if key in self._workload_fits_logged:
            return
        logger.info(
            "bottleneck value for access: workload %s, dimension %s, window %s, instances %s",
            workload["name"],
            dimension,
            window,
            instances,
        )
        self._workload_fits_logged.add(key)

    def _check_access_workload_fit(self, w, b):
        for resource in AccessSizerContext.ACCESS_CONSTRAINTS:
            if b[resource] is None or w[resource] == 0:
                self._log_access_workload_fit_info(w, "nowindow", resource, "infinite")
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
                media_server, workload_name = w["name"]
                error_text = NON_WINDOW_ERROR_TEXT.format(
                    media_server=media_server,
                    workload_name=workload_name,
                    capacity_value=capacity,
                    unit_value=unit,
                    capacity_available_value=capacity_available,
                )
                logger.info(error_text)
                raise AccessMisfitError(media_server, workload_name, error_text)
            self._log_access_workload_fit_info(w, "nowindow", resource, max_fit)

    def _parse_solution(self, data, solver, x) -> typing.List[AccessAppliance]:
        appliances = collections.defaultdict(dict)
        for idx, wkg in enumerate(data["wk_groups"]):
            for b in data["appliances"]:
                app_id = b["idx"]
                val = solver.Value(x[(idx, app_id)])
                if val:
                    appliances[app_id][wkg["name"]] = val

        result = []
        for app_id in appliances:
            # calculate total capacity required for the appliance, and
            # pick configuration accordingly
            app_wk_groups = []
            total_capacity = utils.Size.ZERO
            for wk_group_name in appliances[app_id]:
                app_wk_groups.append(wk_group_name)
                total_capacity += data["wk_group_capacities"][wk_group_name]
            result.append(
                AccessAppliance(
                    appliance=access_appliance.AccessAppliance.for_size(
                        total_capacity, self.appliance_spec.max_capacity
                    ),
                    workload_groups=app_wk_groups,
                )
            )

        return result

    def _calculate_utilization(self, appliances: typing.List[AccessAppliance], data):
        for assigned_appl in appliances:
            for yr in range(1, self.timeframe.num_years + 1):
                total_capacities = []
                for wk_group_name in assigned_appl.workload_groups:
                    assigned_wkload = data["wk_group_name_map"][wk_group_name]
                    cloud_cap = (
                        assigned_wkload.workload.cloud_storage_worst_case_for_year(yr)
                    )
                    total_capacities.append(cloud_cap * assigned_wkload.num_clients)
                assigned_appl.utilization.add(
                    "absolute_capacity", yr, utils.Size.sum(total_capacities)
                )
                appliance_obj = assigned_appl.appliance
                assigned_appl.utilization.add(
                    "capacity",
                    yr,
                    appliance_obj.capacity.utilization(total_capacities),
                )

    def _progress(self, status, detail=None):
        if self.progress_cb is None:
            return
        self.progress_cb(status, detail)

    @contextlib.contextmanager
    def _record_event(self, event):
        if self.timer_ctx is None:
            yield
        else:
            with self.timer_ctx.record(event):
                yield
