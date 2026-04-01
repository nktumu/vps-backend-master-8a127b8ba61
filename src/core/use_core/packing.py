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
import enum
import functools
import logging
import typing

from ortools.sat.python import cp_model

from use_core import access_appliance
from use_core import appliance
from use_core import constants
from use_core import media_packing
from use_core import settings
from use_core import task
from use_core import timers
from use_core import utils
from use_core import workload
from use_core.access_packing import AccessSizerContext, AccessSizerResult
from use_core.flex_packing import (
    Container,
    ContainerType,
    FlexSizerContext,
    FlexSizerResult,
)
from use_core.media_packing import (  # noqa: F401
    GENERIC_ERROR_TEXT,
    NotifyWorkloadError,
    PackingError,
    PackingAllWorkloadsError,
    UserCancel,
    WorkloadMisfitError,
    WorkloadMisfitMasterError,
    WorkloadMisfitMediaError,
)
from use_core.utils import WorkloadMode, WorkloadSummary
from use_core.appliance import Appliance
from use_core import software_version

logger = logging.getLogger(__name__)


class ApplianceRole(enum.Enum):
    media = enum.auto()
    primary = enum.auto()
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
This means that the Master Server Appliance cannot support a single client for the
given workload.
"""

WINDOW_ERROR_TEXT = """
Sizing failed because:
- The workload {workload_name} requires {window_size} {resource_value}
- The appliance {appliance_config} offers {window_available}
This means that the Master Server Appliance cannot support a single client for the
given workload.
"""

# Type aliases for readibility

Site = str
Domain = str

WorkloadList = typing.List[workload.Workload]
SiteWorkloadList = typing.Dict[Site, WorkloadList]
Site_Info = typing.Tuple[Domain, Site]
MediaConfigs = typing.Dict[Site_Info, appliance.Appliance]
MasterConfigs = typing.Dict[Domain, appliance.Appliance]
ProgressCallback = typing.Callable[[str, str], None]
MessageCallback = typing.Callable[[str], None]
FlexSelection = bool
RightsizeSelection = typing.Callable[[Site], bool]


class BadInputError(Exception):
    pass


def _continue_on_packing_error(pack):
    """Decorator can be used on pack() methods"""

    @functools.wraps(pack)
    def _wrap_with_retry(self, *args, **kwargs):
        if ("retry_on_error" not in kwargs) or (not kwargs["retry_on_error"]):
            return pack(self, *args, **kwargs)

        workload_error_list = {}
        try:
            timer_ctx = self.timer_ctx.record
        except Exception:
            timer_ctx = contextlib.nullcontext

        while True:
            try:
                with timer_ctx("sizing"):
                    results = pack(self, *args, **kwargs)
                    results.workload_error_list = workload_error_list
            except WorkloadMisfitMediaError as err:
                workload_error_list[err.workload_name] = err.error_text
                self.workloads = [
                    w for w in self.workloads if w.name != err.workload_name
                ]
                for w in self.workloads:
                    w.restore_domain()
                if not self.workloads:
                    raise PackingAllWorkloadsError(
                        "Sizing failed. Packing failed on all workloads.",
                        workload_error_list,
                    )
            except WorkloadMisfitMasterError as err:
                logger.info(
                    f"dropping workload %s from {constants.MANAGEMENT_SERVER_DESIGNATION} sizing",
                    err.workload_name,
                )
                self.primary_workloads = [
                    w for w in self.primary_workloads if w.name != err.workload_name
                ]
                self.result.primary_errors[err.workload_name] = err.error_text
                self.result.reset_domain_assignments()
                for w in self.primary_workloads:
                    w.restore_domain()
                if not self.primary_workloads:
                    break  # User feedback: continue when all Master sizing fails
            else:
                break
        return results if "results" in locals() else self.result

    return _wrap_with_retry


class AssignedWorkload:
    workload: workload.Workload
    mode_: WorkloadMode
    num_clients: int
    w_utilization: utils.YearOverYearUtilization

    def __init__(self, workload_, mode, num_clients):
        self.workload = workload_
        self.mode_ = mode
        self.num_clients = num_clients
        self.w_utilization = utils.YearOverYearUtilization()

    def __repr__(self):
        return str(self.__class__) + ": " + str(self.__dict__)

    @property
    def mode(self):
        mode_map = {
            media_packing.WorkloadMode.media_primary: WorkloadMode.media_primary,
            media_packing.WorkloadMode.media_dr: WorkloadMode.media_dr,
        }
        return mode_map.get(self.mode_, self.mode_)


class AssignedAppliance:
    appliance: appliance.Appliance
    roles: typing.Set[ApplianceRole]
    workloads: typing.List[AssignedWorkload]
    utilization: utils.YearOverYearUtilization

    def __init__(self, appliance_, roles, workloads):
        self.appliance = appliance_
        self.roles = roles
        self.workloads = workloads
        self.utilization = utils.YearOverYearUtilization()

    def __repr__(self):
        return str(self.__class__) + ": " + str(self.__dict__)

    def rightsize(self, timeframe):
        storage_used = self.utilization.get(
            "absolute_capacity", timeframe.planning_year
        )
        new_appliance = self.appliance.rightsize(storage_used, flex=False)
        for yr in range(timeframe.num_years + 1):
            abs_capacity = self.utilization.get("absolute_capacity", yr)
            new_rel_capacity = new_appliance.calculated_capacity_orig.utilization(
                [abs_capacity]
            )
            self.utilization.replace("capacity", yr, new_rel_capacity)
        self.appliance = new_appliance

    def primary_assignments(self) -> int:
        """Return number of workloads for which this appliance is primary site."""
        return sum(
            1
            for assigned_workload in self.workloads
            if assigned_workload.mode == WorkloadMode.media_primary
        )

    @property
    def appliance_summary_attributes(self):
        return constants.RAW_APPLIANCE_SUMMARY_ATTRIBUTES


class SiteAssignment:
    media_servers: typing.List[AssignedAppliance]
    ltr_servers: typing.List[AssignedAppliance]
    site_utilization: utils.YearOverYearUtilization
    site_bottlenecks: typing.Dict[typing.Tuple[Site, str], typing.Dict[int, str]]

    def __init__(self, media_servers, site_utilization, site_bottlenecks):
        self.media_servers = media_servers
        self.site_utilization = site_utilization
        self.site_bottlenecks = site_bottlenecks
        self.ltr_servers = []

    @property
    def all_bad_dr(self):
        """
        Return whether all assignments for this site are DR with an appliance
        that is not supported for DR.
        """
        for assigned_appliance in self.media_servers:
            if assigned_appliance.appliance.dr_candidate:
                return False
            for assigned_workload in assigned_appliance.workloads:
                if assigned_workload.mode != WorkloadMode.media_dr:
                    return False
        return True

    def utilization(self, year):
        return self.site_utilization.get_max_proportion_for_year(year)

    def update_ltr(self, new_assignment):
        self.ltr_servers = new_assignment.media_servers

    def rightsize_appliances(self, timeframe):
        for appl in [*self.media_servers, *self.ltr_servers]:
            appl.rightsize(timeframe)


class DomainAssignment:
    master_servers: typing.List[AssignedAppliance]
    sites: typing.Dict[Site, SiteAssignment]

    def __init__(self, master_servers):
        self.master_servers = master_servers

        self.sites = {}

    def __repr__(self):
        return str(self.__class__) + ": " + str(self.__dict__)

    def set_site_assignment(self, site_name, site_assignment):
        assert site_name not in self.sites
        self.sites[site_name] = site_assignment

    def update_ltr_assignment(self, site_name, site_assignment):
        assert site_name in self.sites
        self.sites[site_name].update_ltr(site_assignment)

    def rightsize_appliances(self, timeframe, selector):
        for site_name, site_assignment in self.sites.items():
            if not selector(site_name):
                continue

            site_assignment.rightsize_appliances(timeframe)


ApplianceConfig = str
DomainSummary = typing.Dict[Domain, typing.Dict[Site, int]]


class SizerSummary:
    def __init__(
        self,
        master_summary: typing.Dict[ApplianceConfig, DomainSummary],
        media_summary: typing.Dict[ApplianceConfig, DomainSummary],
        appliances: typing.Dict[str, appliance.Appliance],
    ):
        self.master_summary = master_summary
        self.media_summary = media_summary
        self.appliances = appliances

    @property
    def media_site_summaries(self):
        yield from _emit_summaries(self.media_summary)

    @property
    def master_site_summaries(self):
        yield from _emit_summaries(self.master_summary)


def _emit_summaries(appliance_summary):
    for config_name, domain_summary in sorted(appliance_summary.items()):
        cfg_summary = {}
        for domain, site_summary in sorted(domain_summary.items()):
            for site_name, appliance_count in sorted(site_summary.items()):
                cfg_summary[(domain, site_name)] = appliance_count
        yield config_name, cfg_summary


class SizerResult:
    timeframe: utils.TimeFrame
    domains: typing.Dict[Domain, DomainAssignment]
    access_result: typing.Optional[AccessSizerResult]
    workload_summary_attributes: typing.Dict[
        typing.Tuple[str, str], typing.List[WorkloadSummary]
    ]

    def __init__(self, timeframe, flex, ltr_target=settings.LtrType.ACCESS):
        self.timeframe = timeframe
        self.flex = flex
        self.ltr_target = ltr_target
        self.domains = {}
        self.domains_split = False
        self.primary_errors = {}
        self.access_result = None
        self.workload_summary_attributes = collections.defaultdict(list)

    def __repr__(self):
        return str(self.__class__) + ": " + str(self.__dict__)

    @property
    def num_years(self) -> int:
        return self.timeframe.num_years

    @property
    def planning_year(self) -> int:
        return self.timeframe.planning_year

    def reset_domain_assignments(self):
        self.domains = {}

    def set_domain_assignment(self, domain_name, domain_assignment):
        assert domain_name not in self.domains
        self.domains[domain_name] = domain_assignment

    def set_domains_split(self, value):
        self.domains_split = value

    @property
    def summary(self) -> SizerSummary:
        appliances = {}

        master_summary = collections.defaultdict(
            lambda: collections.defaultdict(lambda: collections.defaultdict(int))
        )
        for domain, site_name, app_id, assigned_appliance in self.all_master_servers:
            app_obj = assigned_appliance.appliance
            app_name = app_obj.config_name
            appliances[app_name] = app_obj
            master_summary[app_name][domain][site_name] += 1

        media_summary = collections.defaultdict(
            lambda: collections.defaultdict(lambda: collections.defaultdict(int))
        )
        for domain, domain_assignment in self.domains.items():
            for site_name, site_assignment in domain_assignment.sites.items():
                if site_assignment.all_bad_dr:
                    continue
                for assigned_appliance in site_assignment.media_servers:
                    app_obj = assigned_appliance.appliance
                    app_name = app_obj.config_name
                    appliances[app_name] = app_obj
                    media_summary[app_name][domain][site_name] += 1

        return SizerSummary(master_summary, media_summary, appliances)

    @property
    def num_servers(self):
        nmedia = len(list(self.all_media_servers))
        nprimary = len(list(self.all_master_servers))
        ncloud = len(list(self.all_ltr_servers))
        return nmedia + nprimary + ncloud

    @property
    def all_media_servers(self):
        for domain, domain_assignment in self.domains.items():
            for site_name, site_assignment in domain_assignment.sites.items():
                for app_id, assigned_appliance in enumerate(
                    site_assignment.media_servers
                ):
                    yield (
                        domain,
                        site_name,
                        f"{domain}-{site_name}-{app_id + 1}",
                        assigned_appliance,
                    )

    @property
    def all_ltr_servers(self):
        for domain, domain_assignment in self.domains.items():
            for site_name, site_assignment in domain_assignment.sites.items():
                for app_id, assigned_appliance in enumerate(
                    site_assignment.ltr_servers
                ):
                    yield (
                        domain,
                        site_name,
                        f"{domain}-{site_name}-cloud-{app_id + 1}",
                        assigned_appliance,
                    )

    @property
    def all_master_servers(self):
        sites_for_domain = dict(self.largest_sites)
        for domain, domain_assignment in self.domains.items():
            for app_id, mserver in enumerate(domain_assignment.master_servers):
                yield (
                    domain,
                    sites_for_domain[domain],
                    f"{domain}-{constants.MANAGEMENT_SERVER_DESIGNATION.lower()}-{app_id + 1}",
                    mserver,
                )

    @property
    def all_servers(self):
        nmedia = collections.defaultdict(int)
        for domain, site, server_name, mserver in self.all_media_servers:
            nmedia[domain] += 1

        for domain, site, server_name, mserver in self.all_master_servers:
            yield Container(
                domain=domain,
                site=site,
                name=server_name,
                obj=mserver,
                type=ContainerType.primary,
                nmedia=nmedia[domain],
            )
        for domain, site, server_name, mserver in self.all_media_servers:
            yield Container(
                domain=domain,
                site=site,
                name=server_name,
                obj=mserver,
                type=ContainerType.media,
            )
        for domain, site, server_name, mserver in self.all_ltr_servers:
            yield Container(
                domain=domain,
                site=site,
                name=server_name,
                obj=mserver,
                type=ContainerType.msdp_cloud,
            )

    def ltr_assignments(
        self, site_name
    ) -> typing.List[typing.Tuple[str, AssignedAppliance, AssignedWorkload]]:
        """Return list of LTR workload assignments."""
        if self.flex:
            servers = self.all_ltr_servers
        else:
            servers = self.all_media_servers
        for domain, site, server_name, mserver in servers:
            if site != site_name:
                continue
            for wkload in mserver.workloads:
                if self.flex and wkload.mode_ != utils.WorkloadMode.media_cloud:
                    continue
                if not self.flex and not wkload.workload.ltr_enabled:
                    continue
                yield server_name, mserver, wkload

    @property
    def all_sites(self):
        sites = set()
        for domain, domain_assignment in self.domains.items():
            for site_name, site_assignment in domain_assignment.sites.items():
                sites.add(site_name)
        return sites

    @property
    def site_assignments(self):
        for domain, domain_assignment in self.domains.items():
            for site_name, site_assignment in domain_assignment.sites.items():
                yield (domain, site_name, site_assignment)

    @property
    def yoy_utilization_by_workload(self):
        aggregate = collections.defaultdict(utils.YearOverYearUtilization)
        for domain, site_name, app_id, assigned_appliance in self.all_media_servers:
            for assigned_workload in assigned_appliance.workloads:
                if assigned_workload.mode not in [
                    WorkloadMode.media_primary,
                    WorkloadMode.media_cloud,
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

    def master_servers(self, domain_name):
        return self.domains[domain_name].master_servers

    def largest_site(self, domain_name):
        for domain, site_name in self.largest_sites:
            if domain == domain_name:
                return site_name

    @property
    def largest_sites(self):
        workload_counts = collections.defaultdict(lambda: collections.defaultdict(int))
        for domain, site_name, app_id, assigned_appliance in self.all_media_servers:
            workload_counts[domain][
                site_name
            ] += assigned_appliance.primary_assignments()
        for domain, site_table in workload_counts.items():
            largest_num_workloads, largest_site = max(
                (num_workloads, site_name)
                for (site_name, num_workloads) in site_table.items()
            )
            yield (domain, largest_site)

    def site_utilization(self, domain, site_name, year=None):
        if year is None:
            year = self.planning_year
        return self.domains[domain].sites[site_name].utilization(year)

    @property
    def _all_site_utilizations(self):
        for domain, domain_assignment in self.domains.items():
            for site_name, site_assignment in domain_assignment.sites.items():
                yield site_assignment.site_utilization

    @property
    def yoy_max_utilization(self):
        overall_max = functools.reduce(
            utils.YearOverYearUtilization.combine_by_max, self._all_site_utilizations
        )
        result = []
        for yr in range(1, 1 + self.num_years):
            year_utilization = dict(
                (dimension, overall_max.get(dimension, yr))
                for dimension in utils.YearOverYearUtilization.PERCENTAGE_DIMENSIONS
            )
            result.append(year_utilization)
        return result

    def bottleneck_clients(self, domain, site_name, workload_name):
        return (
            self.domains[domain]
            .sites[site_name]
            .site_bottlenecks[(site_name, workload_name)]
            .items()
        )

    def rightsize_appliances(self, selector):
        for domain, domain_assignment in self.domains.items():
            domain_assignment.rightsize_appliances(self.timeframe, selector)


class ApplianceSelectionCriteria:
    def __init__(
        self, site_assignment_list, visible_models, per_appliance_safety_margins
    ):
        self.site_assignment_list = site_assignment_list
        self.visible_models = visible_models
        self.per_appliance_safety_margins = per_appliance_safety_margins


class SizerContext:
    def __init__(
        self,
        appliance_selection_criteria: ApplianceSelectionCriteria,
        workloads: WorkloadList,
        window_sizes: utils.WindowSize,
        progress_cb: ProgressCallback = None,
        message_cb: MessageCallback = None,
        timer_ctx: timers.TimerContext = None,
        pack_flex: FlexSelection = False,
        sizer_settings: settings.Settings = None,
    ):
        self.access_choice = None
        self.master_configs = {}
        self.media_configs = {}
        self.flex_config_info = {}
        self.rightsize = {}
        self.per_appliance_safety_margins = (
            appliance_selection_criteria.per_appliance_safety_margins
        )
        self.workloads = workloads
        self.site_assignment_list = appliance_selection_criteria.site_assignment_list
        self.window_sizes = window_sizes
        self.progress_cb = progress_cb
        self.message_cb = message_cb
        self.timer_ctx = timer_ctx
        self.pack_flex = pack_flex
        self.sizer_settings = sizer_settings
        self.timeframe = sizer_settings.timeframe
        self.master_sizing = sizer_settings.master_sizing
        self.ltr_target = sizer_settings.ltr_type
        self.visible_models = appliance_selection_criteria.visible_models
        self.select_appliances()

        assert (
            self.ltr_target == settings.LtrType.OTHER
            or self.access_choice
            or settings.LtrType.RECOVERYVAULT
        )
        self._init_sizer_results()

    def select_appliances(self):
        for site_config in self.site_assignment_list:
            all_network_types = [
                site_config["site_network_type"],
                site_config["wan_network_type"],
                site_config["cc_network_type"],
            ]
            network_types = set(nw for nw in all_network_types if nw is not None)
            site_config["appliance_config"] = Appliance.match_name_network(
                site_config["appliance_model"],
                self.visible_models,
                site_config["appliance_name"],
                network_types,
                site_config["site_hints"],
                self.per_appliance_safety_margins,
            )
            site_config["appliance_selectors"] = {
                "model": site_config["appliance_model"],
                "config": site_config["appliance_name"],
                "networks": network_types,
                "hints": site_config["site_hints"],
                "margins": self.per_appliance_safety_margins,
                "allow_rightsize": site_config["appliance_name"] is None,
                "visible_models": self.visible_models,
            }
            domain = site_config["domain_name"]
            site_name = site_config["site_name"]

            model = site_config["appliance_config"]
            appliance = Appliance.match_config(
                [model],
                safety=self.per_appliance_safety_margins,
                cloud_bandwidth=site_config["appliance_bandwidth_cc"],
                site_software_version=software_version.text_to_version(
                    site_config["software_version"]
                ),
            )[0]
            appliance.ensure_compatible_appliances(
                domain,
                site_name,
                self.workloads,
            )
            self.media_configs[(domain, site_name)] = appliance
            self.flex_config_info[(domain, site_name)] = site_config[
                "appliance_selectors"
            ]
            self.rightsize[site_name] = site_config["appliance_selectors"][
                "allow_rightsize"
            ]
        self.rightsize = SizerContext.rightsize_selector(self.rightsize)

        if self.pack_flex:
            self.master_configs = workload.appliance_for_catalog(
                self.workloads,
                self.timeframe,
                self.media_configs,
                safety_margins=self.per_appliance_safety_margins,
            )
            for domain, cfg_name in self.master_configs.items():
                self.master_configs[domain] = Appliance.match_config(
                    [cfg_name],
                    safety=self.per_appliance_safety_margins,
                    cloud_bandwidth=site_config["appliance_bandwidth_cc"],
                    site_software_version=software_version.text_to_version(
                        site_config["software_version"]
                    ),
                )[0]
        else:
            self.master_configs = SizerContext.primary_selector(
                self.media_configs, safety_margins=self.per_appliance_safety_margins
            )
        self.access_choice = access_appliance.AccessAppliance()
        self.access_choice.set_safety_limits(self.per_appliance_safety_margins)

    @staticmethod
    def primary_selector(media_configs, safety_margins=None):
        domain_medias = collections.defaultdict(set)
        for (domain, site_name), media_app in media_configs.items():
            domain_medias[domain].add(media_app.model)
        domain_primaries = {}
        for domain, media_models in domain_medias.items():
            domain_primaries[domain] = appliance.find_primary(
                media_models, safe_margins=safety_margins
            )
        return domain_primaries

    @staticmethod
    def rightsize_selector(selections):
        def impl(site_name):
            return selections.get(site_name, True)

        return impl

    def _init_sizer_results(self):
        self.result = SizerResult(
            timeframe=self.timeframe, flex=self.pack_flex, ltr_target=self.ltr_target
        )
        self.result.window_sizes = self.window_sizes
        self.workload_fits_logged = set()

    @_continue_on_packing_error
    def pack(self, retry_on_error=False) -> typing.Union[SizerResult, FlexSizerResult]:
        """
        Attempts to fit SizingContext workloads in appliances
        If 'retry_on_error' keyword parameter is true, then packing will attempt to
        continue for some errors.  'retry_on_error' keyword must be provided.
        """
        self._init_sizer_results()
        with self._record_event("generating tasks"):
            self._generate_tasks()
        with self._record_event(
            f"packing {constants.MANAGEMENT_SERVER_DESIGNATION.lower()}s"
        ):
            self._pack_master()
        with self._record_event("packing media servers"):
            self._pack_media()
        if (
            self.ltr_target == settings.LtrType.ACCESS
            or self.ltr_target == settings.LtrType.RECOVERYVAULT
        ):
            with self._record_event("packing access appliances"):
                access_ctx = AccessSizerContext(
                    self.result,
                    timeframe=self.timeframe,
                    progress_cb=self.progress_cb,
                    timer_ctx=self.timer_ctx,
                    appliance_spec=self.access_choice,
                )
                self.result.access_result = access_ctx.pack()

        if self.pack_flex:
            self._build_flexconfigs()
            with self._record_event("packing flex"):
                self.flex_ctx = FlexSizerContext(
                    self.result,
                    progress_cb=self.progress_cb,
                    flex_configs=self.flex_configs,
                    rightsize=self.rightsize,
                )
                flex_sizer_result = self.flex_ctx.pack()
                calculate_workload_attributes(flex_sizer_result)
                flex_sizer_result.window_sizes = self.window_sizes
                return flex_sizer_result
        if self.rightsize:
            self.result.rightsize_appliances(self.rightsize)
        calculate_workload_attributes(self.result)
        return self.result

    def _build_flexconfigs(self):
        self.flex_configs = {}
        if not self.flex_config_info:
            for (domain, site_name), appliance_spec in self.media_configs.items():
                self.flex_configs[site_name] = appliance_spec
            return

        # Calculate new space requirements.  These can be different
        # from the original values because of storage roundup.
        site_capacities = collections.defaultdict(lambda: utils.Size.ZERO)
        for ctr in self.result.all_servers:
            site_capacities[ctr.site] += ctr.capacity(self.timeframe.planning_year)

        for (domain, site_name), flex_spec in self.flex_config_info.items():
            old_disk = flex_spec["hints"].disk
            new_disk = site_capacities[site_name]
            flex_spec["hints"].disk = new_disk
            logger.debug(
                "hinted capacity for site %s/%s changed from %s to %s",
                domain,
                site_name,
                old_disk,
                new_disk,
            )

            config_name = appliance.Appliance.match_name_network(
                flex_spec["model"],
                flex_spec["visible_models"],
                flex_spec["config"],
                flex_spec["networks"],
                flex_spec["hints"],
                flex_spec["margins"],
            )

            logger.debug(
                "flex appliance config for site %s/%s: %s",
                domain,
                site_name,
                config_name,
            )
            [self.flex_configs[site_name]] = appliance.Appliance.match_config(
                [config_name],
                safety=flex_spec["margins"],
            )

    @contextlib.contextmanager
    def _record_event(self, event):
        if self.timer_ctx is None:
            yield
        else:
            with self.timer_ctx.record(event):
                yield

    def _progress(self, status, detail=None):
        if self.progress_cb is None:
            return
        self.progress_cb(status, detail)

    def _generate_tasks(self):
        for w in self.workloads:
            if self.ltr_target == settings.LtrType.ACCESS:
                ltr_app = access_appliance.AccessAppliance.stub()
            else:
                ltr_app = self.media_configs[(w.domain, w.site_name)]
            appliance_spec = {
                "master_app": self.master_configs[w.domain],
                "media_app": self.media_configs[(w.domain, w.site_name)],
                "ltr_app": ltr_app,
            }
            w.generate_tasks(
                w.domain,
                [w.site_name],
                appliance_spec,
                self.window_sizes,
                self.timeframe,
            )
            if w.dr_enabled:
                appliance_spec = {
                    "master_app": self.master_configs[w.domain],
                    "media_app": self.media_configs[(w.domain, w.dr_dest)],
                }
                w.generate_tasks(
                    w.domain,
                    [w.dr_dest],
                    appliance_spec,
                    self.window_sizes,
                    self.timeframe,
                )

    def _pack_media(self):
        domain_sites = extract_sites(self.workloads)
        for domain, site_map in sorted(domain_sites.items()):
            domain_assignment = self.result.domains.setdefault(
                domain, DomainAssignment([])
            )
            for site_name, site_workloads in sorted(site_map.items()):
                with self._record_event(
                    f"sizing media servers for domain {domain}, site {site_name}"
                ):
                    self._progress(
                        f"Sizing media servers for domain {domain}, site {site_name}"
                    )
                    appliance_spec = {
                        "master_app": self.master_configs[domain],
                        "media_app": self.media_configs[(domain, site_name)],
                    }
                    ctx = media_packing.SizerContext(
                        workloads=site_workloads,
                        appliance_spec=appliance_spec,
                        window_sizes=self.window_sizes,
                        site_name=site_name,
                        progress_cb=self.progress_cb,
                        message_cb=self.message_cb,
                        generate_tasks=False,
                        timeframe=self.timeframe,
                        pack_flex=self.pack_flex,
                        ltr_target=self.ltr_target,
                    )
                    distribution = ctx.pack()
                    site_result = distribution_to_site_assignment(
                        distribution, ApplianceRole.media, self.pack_flex
                    )
                    domain_assignment.set_site_assignment(site_name, site_result)

                    ltr_workloads = [
                        w
                        for w in site_workloads
                        if w.ltr_enabled and w.site_name == site_name
                    ]
                    if ltr_workloads and self.pack_flex:
                        ltr_ctx = media_packing.SizerContext(
                            workloads=ltr_workloads,
                            appliance_spec=appliance_spec,
                            window_sizes=self.window_sizes,
                            site_name=site_name,
                            progress_cb=self.progress_cb,
                            message_cb=self.message_cb,
                            generate_tasks=False,
                            timeframe=self.timeframe,
                            pack_flex=self.pack_flex,
                            ltr_target=self.ltr_target,
                            pack_ltr=True,
                        )
                        ltr_distribution = ltr_ctx.pack()
                        ltr_site_result = distribution_to_site_assignment(
                            ltr_distribution, ApplianceRole.msdp_cloud, self.pack_flex
                        )
                        domain_assignment.update_ltr_assignment(
                            site_name, ltr_site_result
                        )

    def _pack_master(self):
        if not self.master_sizing:
            return

        self.primary_workloads = self.workloads[:]
        self._pack_master_impl(retry_on_error=True)

    @_continue_on_packing_error
    def _pack_master_impl(self, retry_on_error=False):
        domains = extract_domains(self.primary_workloads)
        for domain, domain_workloads in domains.items():
            with self._record_event(
                f"sizing {constants.MANAGEMENT_SERVER_DESIGNATION.lower()} for domain {domain}"
            ):
                logger.debug(
                    "sizing %s for domain %s",
                    constants.MANAGEMENT_SERVER_DESIGNATION.lower(),
                    domain,
                )
                self._progress(
                    f"Sizing {constants.MANAGEMENT_SERVER_DESIGNATION.lower()} for domain {domain}"
                )
                appliance_spec = self.master_configs[domain]

                # workloads are not supposed to split across master servers
                max_appliances = len(self.primary_workloads)
                for n_appliances in utils.potential_appliance_counts(1, max_appliances):
                    solver_data = self._build_solver_data_model(
                        domain_workloads, n_appliances, appliance_spec
                    )
                    try:
                        appliances = self._solve(solver_data)
                        new_assignment = self._maybe_reassign_domains(
                            appliances, domain
                        )
                        for domain, appliances in new_assignment.items():
                            self.result.set_domain_assignment(
                                domain,
                                DomainAssignment(master_servers=appliances),
                            )
                        break
                    except PackingError:
                        pass
                else:
                    raise PackingError(ERROR_TEXT)

        return self.result

    def _split_master_configs(self, old_domain, new_domain):
        new_configs = {}
        for domain in self.master_configs:
            if domain != old_domain:
                continue
            new_configs[new_domain] = self.master_configs[domain]
        self.master_configs.update(new_configs)

    def _split_media_configs(self, old_domain, new_domain):
        new_configs = {}
        for domain, site in self.media_configs:
            if domain != old_domain:
                continue
            new_configs[(new_domain, site)] = self.media_configs[(domain, site)]
        self.media_configs.update(new_configs)

    def _maybe_reassign_domains(self, appliances, domain):
        if len(appliances) == 1:
            return {domain: appliances}

        self.result.set_domains_split(True)
        new_assignments = {}
        for index_appl, assigned_appl in enumerate(appliances):
            new_domain = f"{domain}_{index_appl + 1}"
            for assigned_wload in assigned_appl.workloads:
                wload = assigned_wload.workload
                wload.domain_adjusted = True
                logger.debug(
                    "Changing domain for workload %s from %s to %s",
                    wload.name,
                    wload.domain,
                    new_domain,
                )
                self._split_master_configs(wload.domain, new_domain)
                self._split_media_configs(wload.domain, new_domain)
                wload.domain = new_domain
            new_assignments[new_domain] = [assigned_appl]

        return new_assignments

    def _build_solver_data_model(self, workloads, num_appliances, appliance_spec):
        solver_workloads = [self._convert_one_workload(w) for w in workloads]
        workload_name_map = dict((w.name, w) for w in workloads)
        num_items = len(workloads)
        appliance_list = [
            self._convert_one_appliance(i, appliance_spec)
            for i in range(num_appliances)
        ]
        return {
            "appliance": appliance_spec,
            "workload_names": workload_name_map,
            "workloads": solver_workloads,
            "num_items": num_items,
            "all_appliances": appliance_list,
            "window_sizes": self.window_sizes,
        }

    def _convert_one_workload(self, workload):
        capacity = (
            workload.catalog_storage_for_year(self.timeframe.planning_year)
            * workload.num_instances
        )

        mr = workload.master_resources_for_year(self.timeframe.planning_year)

        winfo = {
            "name": workload.name,
            "capacity": scale_value("capacity", capacity),
            "files": mr["files"] * workload.num_instances,
            "images": mr["images"] * workload.num_instances,
            "jobs/day": mr["jobs/day"] * workload.num_instances,
        }

        for window in task.WindowType:
            if window != task.WindowType.master:
                continue
            if (workload.domain, window) not in mr:
                logging.debug("(%s, %s) not in %s", workload.domain, window, mr)
                continue
            res = mr[(workload.domain, window)]
            winfo[("cpu", window)] = scale_value(
                "duration", res["total_job_duration"] * workload.num_instances
            )
            winfo[("memory", window)] = scale_value(
                "memory", res["total_mem_utilization"]
            )

        logger.info("workload info: %s", winfo)
        return winfo

    def _convert_one_appliance(self, idx, appliance_spec):
        safety_capacity = appliance_spec.catalog_size or appliance_spec.safe_capacity
        assert (
            appliance_spec.catalog_size is None
            or appliance_spec.catalog_size < appliance_spec.safe_capacity
            or appliance_spec.catalog_size == appliance_spec.safe_capacity
        )
        appinfo = {
            "appliance_id": idx,
            "capacity": scale_value("capacity", safety_capacity),
            "memory": scale_value("memory", appliance_spec.safe_memory)
            - appliance_spec.primary_memory_overhead,
            "files": appliance_spec.supported_files,
            "images": appliance_spec.supported_images,
            "jobs/day": appliance_spec.supported_jobs_per_day,
        }
        for window in task.WindowType:
            appinfo[("cpu", window)] = scale_value(
                "duration",
                appliance_spec.safe_duration(window, self.window_sizes),
            )

        logger.info("appliance details: %s", appinfo)
        return appinfo

    def _solve(self, data):
        model = cp_model.CpModel()

        # x[(i, j)] is whether workload i is assigned to appliance j
        x = {}
        for idx, w in enumerate(data["workloads"]):
            for b in data["all_appliances"]:
                b["appliance_model"] = data["appliance"].appliance
                b["config_name"] = data["appliance"].config_name
                self._check_workload_fit(w, b)
                app_id = b["appliance_id"]
                x[(idx, app_id)] = model.NewIntVar(0, 1, f"x_{idx}_{app_id}")

        mem_reqd = []
        for w in data["workloads"]:
            for window in task.WindowType:
                if window != task.WindowType.master:
                    continue
                mem_reqd.append(w[("memory", window)])
        data["max_mem_reqd"] = max(mem_reqd)

        for b in data["all_appliances"]:
            app_id = b["appliance_id"]
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
        dimensions = ["capacity", "files", "images", "jobs/day"]
        used_vars = {}
        for dim in dimensions:
            if b[dim] is None:
                continue
            used_vars[dim] = [
                model.NewIntVar(0, b[dim], f"{dim}_used_{b['appliance_id']}")
                for b in data["all_appliances"]
            ]
        mem_used = [
            model.NewIntVar(0, b["memory"], f"mem_used_{b['appliance_id']}")
            for b in data["all_appliances"]
        ]

        for b in data["all_appliances"]:
            app_id = b["appliance_id"]
            for dim, varlist in used_vars.items():
                model.Add(
                    varlist[app_id]
                    == sum(
                        x[(i, app_id)] * w[dim]
                        for (i, w) in enumerate(data["workloads"])
                    )
                )

        for b in data["all_appliances"]:
            app_id = b["appliance_id"]
            model.Add(mem_used[app_id] == data["max_mem_reqd"])

        cpu_used = {}

        for window in task.WindowType:
            cpu_used[window] = [
                model.NewIntVar(
                    0, b[("cpu", window)], f"cpu_used_{b['appliance_id']}_{window.name}"
                )
                for b in data["all_appliances"]
            ]

        for b in data["all_appliances"]:
            app_id = b["appliance_id"]

            model.Add(mem_used[app_id] == data["max_mem_reqd"])

            for window in task.WindowType:
                if window != task.WindowType.master:
                    continue
                model.Add(
                    cpu_used[window][app_id]
                    == sum(
                        x[(i, app_id)] * w[("cpu", window)]
                        for (i, w) in enumerate(data["workloads"])
                    )
                )

        # Each item can be in exactly one appliance.
        for idx, w in enumerate(data["workloads"]):
            model.Add(
                sum(x[(idx, b["appliance_id"])] for b in data["all_appliances"]) == 1
            )

        # Calculate how many appliances are used.  appliance_used[i] is 1
        # if the appliance has been assigned at least one workload, 0
        # otherwise.
        appliance_used = []
        for b in data["all_appliances"]:
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

        # Minimize number of appliances used
        model.Minimize(sum(appliance_used))

        solver = cp_model.CpSolver()
        status = cp_model.UNKNOWN
        chunk_time = constants.CHUNK_TIME
        workers = utils.cpu_count()
        nchunks = 1 + data["num_items"] // constants.ITEM_CHUNK_SIZE
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
                raise PackingError(ERROR_TEXT)
            if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
                # solver was unable to find a solution, but was also
                # unable to conclude that no solution is possible.
                # Check if we can retry with higher timeout.
                first_time_thru = False
                chunk_time *= constants.TIMEOUT_SCALING
                self._check_continue()

        return self._parse_solution(data, solver, x)

    def _check_continue(self):
        if self.message_cb is None:
            return

        msg = "Calculating a result is taking longer than expected. Continue?"
        self.message_cb(msg)

    def _parse_solution(self, data, solver, x):
        appliances = collections.defaultdict(dict)
        for idx, w in enumerate(data["workloads"]):
            for b in data["all_appliances"]:
                app_id = b["appliance_id"]
                val = solver.Value(x[(idx, app_id)])
                if val:
                    appliances[app_id][w["name"]] = val

        result = []
        for app_id in appliances:
            app_workloads = []
            for wname in appliances[app_id]:
                workload_info = data["workload_names"][wname]
                app_workloads.append(
                    AssignedWorkload(
                        workload_=workload_info,
                        mode=WorkloadMode.primary,
                        num_clients=workload_info.num_instances,
                    )
                )
            result.append(
                AssignedAppliance(
                    appliance_=data["appliance"],
                    roles=set([ApplianceRole.primary]),
                    workloads=app_workloads,
                )
            )

        self._analyze_headroom(data, result)

        return result

    def _analyze_headroom(self, data, appliances):
        for yr in range(self.timeframe.num_years + 1):
            for assigned_appl in appliances:
                appliance = assigned_appl.appliance
                util = assigned_appl.utilization

                capacities = []
                absolute_memory = 0
                cpu = memory = files = images = jobs_per_day = 0
                total_clients = 1
                dist_policy = []
                window_cpus = {window: 0 for window in task.WindowType}
                window_nic_pcts = {window: 0 for window in task.WindowType}
                window_nics = {window: utils.Size.ZERO for window in task.WindowType}
                for a in assigned_appl.workloads:
                    capacities.append(
                        a.workload.catalog_storage_for_year(yr) * a.num_clients
                    )
                    mr = a.workload.master_resources_for_year(yr)
                    files += mr["files"] * a.num_clients
                    images += mr["images"] * a.num_clients
                    jobs_per_day += mr["jobs/day"] * a.num_clients
                    total_clients += a.num_clients
                    if a.workload.slp_name not in dist_policy:
                        dist_policy.append(a.workload.slp_name)

                    for window in task.WindowType:
                        if window != task.WindowType.master:
                            continue
                        job_duration_reqd = (
                            mr[(a.workload.domain, window)]["total_job_duration"]
                            * a.num_clients
                        )
                        duration_avail = appliance.duration(
                            window, data["window_sizes"]
                        )
                        cpu_util = job_duration_reqd / duration_avail
                        window_cpus[window] += cpu_util
                        cpu = max(cpu, cpu_util)
                if dist_policy:
                    max_concurrent_job = min(total_clients, len(dist_policy))
                else:
                    max_concurrent_job = min(total_clients, 1)
                for window in task.WindowType:
                    if window != task.WindowType.master:
                        continue
                    mem_reqd = (
                        data["max_mem_reqd"] * max_concurrent_job
                        + appliance.primary_memory_overhead
                    )
                    mem_avail = int(appliance.memory)
                    memory = max(memory, mem_reqd / mem_avail)
                    absolute_memory = max(mem_reqd, absolute_memory)

                util.add(
                    "capacity",
                    yr,
                    appliance.calculated_capacity.utilization(capacities),
                )
                util.add("absolute_capacity", yr, utils.Size.sum(capacities))
                util.add("cpu", yr, cpu)
                for window in task.WindowType:
                    util.add(("window_cpu", window), yr, window_cpus[window])
                    util.add(("window_nic_pct", window), yr, window_nic_pcts[window])
                    util.add(("window_nic", window), yr, window_nics[window])
                util.add("memory", yr, memory)
                util.add(
                    "absolute_memory",
                    yr,
                    utils.Size.assume_unit(absolute_memory, "KiB"),
                )
                util.add("io", yr, 0)
                util.add("nic_pct", yr, 0)
                util.add("nic", yr, utils.Size.ZERO)
                util.add("files", yr, files)
                util.add("images", yr, images)
                util.add("jobs/day", yr, jobs_per_day)
                util.add("media_jobs/day", yr, 0)
                util.add("media_dbs", yr, 0)
                util.add("media_vms", yr, 0)

    def _log_workload_fit_info(self, workload, window, dimension, instances):
        key = (workload["name"], window, dimension)
        if key in self.workload_fits_logged:
            return
        logger.info(
            f"bottleneck value for {constants.MANAGEMENT_SERVER_DESIGNATION}: workload %s, dimension %s, window %s, instances %s",
            workload["name"],
            dimension,
            window,
            instances,
        )
        self.workload_fits_logged.add(key)

    def _check_workload_fit(self, w, b):
        for resource in ["capacity", "jobs/day", "files", "images"]:
            if b[resource] is None or w[resource] == 0:
                self._log_workload_fit_info(w, "nowindow", resource, "infinite")
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
                raise WorkloadMisfitMasterError(w["name"], error_text)
            self._log_workload_fit_info(w, "nowindow", resource, max_fit)
        for resource in ["cpu"]:
            window = task.WindowType.master
            reqd = w[(resource, window)]
            avail = b[(resource, window)]
            if reqd == 0:
                self._log_workload_fit_info(w, window, resource, "infinite")
                continue
            max_fit = avail // reqd
            logger.debug("avail: %s, reqd: %s", avail, reqd)
            if max_fit == 0:
                error_text = WINDOW_ERROR_TEXT.format(
                    workload_name=w["name"],
                    resource_value=resource,
                    window_size=reqd,
                    window_type=window,
                    appliance_config=b["config_name"],
                    window_available=avail,
                )
                logger.info(error_text)
                raise WorkloadMisfitMasterError(w["name"], error_text)
            self._log_workload_fit_info(w, window, resource, max_fit)


def extract_domains(workloads: WorkloadList) -> typing.Dict[Domain, WorkloadList]:
    domain_map = collections.defaultdict(list)
    for w in workloads:
        domain_map[w.domain].append(w)
    return domain_map


def extract_sites(workloads: WorkloadList) -> typing.Dict[Domain, SiteWorkloadList]:
    site_map = collections.defaultdict(lambda: collections.defaultdict(list))
    for w in workloads:
        site_map[w.domain][w.site_name].append(w)
        if w.dr_dest:
            site_map[w.domain][w.dr_dest].append(w)
    return site_map


def distribution_to_site_assignment(distribution, role, pack_flex) -> SiteAssignment:
    """
    distribution: sizer resulit object to store the result
    role: specifies the role of the appliance (media or primary or msdp_cloud)
    pack_flex: boolean value to specify type of  sizing
    """
    (site_name,) = list(distribution)
    site_appliances = distribution[site_name]
    site_utilization = distribution.get_utilization(site_name)
    site_bottlenecks = distribution.bottlenecks
    media_servers = []
    for appl in site_appliances:
        app_workloads = []
        for wkload in appl["assignment"]:
            assigned_workload = AssignedWorkload(
                workload_=wkload["workload"],
                mode=wkload["mode"],
                num_clients=wkload["total_inst"],
            )
            util = assigned_workload.w_utilization
            for year, w_util in wkload["w_utilization"].items():
                for name, orig_util in w_util.items():
                    for dimension in [
                        "workload_capacity",
                        "nic_workload",
                    ]:
                        if dimension in orig_util:
                            util.add(dimension, year, orig_util[dimension])
            max_year = max(yr for (yr, _w_util) in wkload["w_utilization"].items())
            for year in range(1, max_year + 1):
                _store_workload_metrics(util, pack_flex, year, site_name, wkload)
            app_workloads.append(assigned_workload)
        assigned_appl = AssignedAppliance(
            appliance_=appl["appliance_model"],
            roles=set([role]),
            workloads=app_workloads,
        )
        util = assigned_appl.utilization
        for year, orig_util in appl["utilization"].items():
            for dimension in [
                "absolute_capacity",
                "alloc_capacity",
                "capacity",
                "alloc_capacity_pct",
                "cpu",
                "mem",
                "absolute_memory",
                "absolute_io",
                "io",
                "nic_pct",
                "nic",
                "nic_dr",
                "DR Transfer GiB/Week",
                "nic_cloud",
                "Cloud Transfer GiB/week",
                "Cloud Minimum Bandwidth(Mbps)",
                "Full Backup",
                "Incremental Backup",
                "Size Before Deduplication",
                "Size After Deduplication",
                "media_jobs/day",
                "media_dbs",
                "media_vms",
            ]:
                util.add(dimension, year, orig_util[dimension])
            for window, window_util in orig_util["window_cpu"].items():
                util.add(("window_cpu", window), year, window_util)
            for window_dim in ["window_nic_pct", "window_nic"]:
                for window, window_util in orig_util[window_dim].items():
                    util.add((window_dim, window), year, window_util)
            gib_months = []
            gib_months_worst_case = []
            for wkload in assigned_appl.workloads:
                if (pack_flex and wkload.mode == WorkloadMode.media_cloud) or (
                    not pack_flex and wkload.mode == WorkloadMode.media_primary
                ):
                    gib_months.append(
                        wkload.workload.cloud_gib_months_for_year(year)
                        * wkload.num_clients
                    )
                    gib_months_worst_case.append(
                        wkload.workload.cloud_gib_months_worst_case_for_year(year)
                        * wkload.num_clients
                    )
            util.add("cloud_gib_months", year, utils.Size.sum(gib_months))
            util.add(
                "cloud_gib_months_worst_case",
                year,
                utils.Size.sum(gib_months_worst_case),
            )

        media_servers.append(assigned_appl)

    utilization = utils.YearOverYearUtilization()
    for yr, yr_utilization in enumerate(site_utilization):
        for dimension, value in yr_utilization.items():
            utilization.add(dimension, yr, value)

    available_cols = {
        "capacity": "Capacity",
        "cpu": "CPU",
        "io": "I/O",
        "nw": "N/W",
        "jobs/day": "Jobs/Day",
        "dbs": "Databases",
        "vms": "VMs",
    }
    bottlenecks = {}

    for workload_name, bottleneck_values in site_bottlenecks.items():
        for resource in available_cols:
            if resource not in bottleneck_values:
                continue
            if (site_name, workload_name) not in bottlenecks:
                bottlenecks[(site_name, workload_name)] = {}
            if not bottlenecks[(site_name, workload_name)]:
                bottlenecks[(site_name, workload_name)][bottleneck_values[resource]] = [
                    available_cols[resource]
                ]
            if (
                bottleneck_values[resource] in bottlenecks[(site_name, workload_name)]
                and available_cols[resource]
                not in bottlenecks[(site_name, workload_name)][
                    bottleneck_values[resource]
                ]
            ):
                bottlenecks[(site_name, workload_name)][
                    bottleneck_values[resource]
                ].append(available_cols[resource])
            [(min_value)] = bottlenecks[(site_name, workload_name)].keys()
            if bottleneck_values[resource] < min_value:
                bottlenecks[(site_name, workload_name)] = {}
                bottlenecks[(site_name, workload_name)][bottleneck_values[resource]] = [
                    available_cols[resource]
                ]

    return SiteAssignment(media_servers, utilization, bottlenecks)


def scale_value(value_type, value):
    if value_type in ["nw"]:
        return int(value * 100)
    if value_type in ["io"]:
        return int(value * 1000)
    if value_type in ["capacity", "memory"]:
        return int(value)
    if value_type in ["duration"]:
        return int(value)


def _store_workload_metrics(
    util: utils.YearOverYearUtilization,
    pack_flex: bool,
    year: int,
    site_name: str,
    wkload,
):
    wk = wkload["workload"]

    # We have three types of metrics to record, when it comes to
    # workload assignments.
    #
    # cloud - These metrics must be associated with a workload
    # assignment that relates to replicating backups to cloud targets.
    # For Flex, this will be the dedicated media_cloud container.  For
    # NBA, this will be the media server assignment.
    #
    # local - These metrics must be associated with a local backup
    # assignment.  For example, if a workload is LTR only, such a
    # metric must be reported as zero.
    #
    # local_or_cloud - We don't care which assignment gets this
    # metric, but when a workload group is assigned to multiple
    # containers (such as media server + msdp-c), this metric must be
    # attached to only one.  We'll preferentially assign this to a
    # media server assignment if available.  If the workload has no
    # local backup, we'll assign it to the msdp-c server assignment.

    MetricType = collections.namedtuple("MetricType", ["assignment", "value"])
    metrics = {
        "cloud_gib_months": MetricType("cloud", wk.cloud_gib_months_for_year(year)),
        "cloud_gib_months_worst_case": MetricType(
            "cloud", wk.cloud_gib_months_worst_case_for_year(year)
        ),
        "cloud_gib_per_week": MetricType("cloud", wk.weekly_transfer_volume_ltr(year)),
        "Storage Cloud": MetricType("cloud", wk.cloud_storage_for_year(year)),
        "Storage Cloud Worst-Case": MetricType(
            "cloud", wk.cloud_storage_worst_case_for_year(year)
        ),
        "Size Before Deduplication": MetricType(
            "local", wk.total_storage_pre_dedupe_for_year(year)
        ),
        "Storage Primary": MetricType(
            "local",
            wk.full_storage_for_year(year) + wk.incremental_storage_for_year(year),
        ),
        "Storage DR": MetricType(
            "local",
            wk.dr_full_storage_for_year(year)
            + wk.dr_incremental_storage_for_year(year),
        ),
        "Storage Catalog": MetricType(
            "local_or_cloud", wkload["workload"].catalog_storage_for_year(year)
        ),
        "Total network utilization": MetricType(
            "local_or_cloud",
            wk.resource_for_year(
                site_name,
                task.WindowType.full,
                year,
                "total_nw_utilization",
            )
            + wk.resource_for_year(
                site_name,
                task.WindowType.incremental,
                year,
                "total_nw_utilization",
            ),
        ),
        "Total dr network utilization": MetricType(
            "local",
            wk.resource_for_year(
                site_name,
                task.WindowType.replication,
                year,
                "total_dr_nw_utilization",
            ),
        ),
        "Total cloud network utilization": MetricType(
            "cloud",
            wk.ltr_resource_for_year(
                site_name,
                task.WindowType.replication,
                year,
                "total_cloud_nw_utilization",
            ),
        ),
        "Backup Volume": MetricType("local_or_cloud", wk.backup_volume_per_week(year)),
    }

    is_ltr_assignment = (pack_flex and wkload["mode"] == WorkloadMode.media_cloud) or (
        not pack_flex and wkload["mode"] == WorkloadMode.media_primary
    )
    is_local_assignment = (
        wk.local_enabled and wkload["mode"] == WorkloadMode.media_primary
    )
    is_local_or_cloud_assignment = is_local_assignment or (
        not wk.local_enabled
        and wkload["mode"] in (WorkloadMode.media_cloud, WorkloadMode.media_primary)
    )
    for metric_name, metric_spec in metrics.items():
        value = utils.Size.ZERO
        if (
            (metric_spec.assignment == "cloud" and is_ltr_assignment)
            or (metric_spec.assignment == "local" and is_local_assignment)
            or (
                metric_spec.assignment == "local_or_cloud"
                and is_local_or_cloud_assignment
            )
        ):
            value = metric_spec.value * wkload["total_inst"]

        util.add(metric_name, year, value)


def calculate_workload_attributes(result: typing.Union[SizerResult, FlexSizerResult]):
    last_year = result.num_years
    wk_utils = result.yoy_utilization_by_workload
    for key, util in sorted(wk_utils.items()):
        (wname, site) = key
        for y in range(1, last_year + 1):
            workload_summary_obj = WorkloadSummary()
            workload_summary_obj.storage_primary = util.get("Storage Primary", y)
            workload_summary_obj.storage_dr = util.get("Storage DR", y)
            workload_summary_obj.storage_cloud = util.get("Storage Cloud", y)
            workload_summary_obj.storage_cloud_worst_case = util.get(
                "Storage Cloud Worst-Case", y
            )
            workload_summary_obj.storage_before_deduplication_primary = util.get(
                "Size Before Deduplication", y
            )
            workload_summary_obj.storage_catalog = util.get("Storage Catalog", y)
            workload_summary_obj.total_network_utilization = util.get(
                "Total network utilization", y
            )
            workload_summary_obj.total_dr_network_utilization = util.get(
                "Total dr network utilization", y
            )
            workload_summary_obj.total_cloud_network_utilization = util.get(
                "Total cloud network utilization", y
            )
            workload_summary_obj.cloud_storage = util.get("cloud_gib_months", y)
            workload_summary_obj.cloud_transfer = util.get("cloud_gib_per_week", y)
            workload_summary_obj.backup_volume = util.get("Backup Volume", y)
            result.workload_summary_attributes[(wname, site)].append(
                workload_summary_obj
            )
