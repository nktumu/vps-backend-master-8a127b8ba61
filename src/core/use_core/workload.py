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
import copy
import enum
import logging
import math
from typing import Callable, List

from use_core import appliance, constants, task, utils
from use_core.calculations import (
    SizePair,
    calculate_addl_fulls,
    calculate_annual_full,
    calculate_incrementals,
    calculate_initial_full,
    calculate_monthly_full,
)

logger = logging.getLogger(__name__)

StorageCategory = str  # "local", "dr", or "cloud"


class CapacityCalculationMode(enum.Enum):
    steady_state = enum.auto()
    scratch_start = enum.auto()

    @staticmethod
    def mode_for(location: StorageCategory):
        calc_modes = {
            "local": CapacityCalculationMode.scratch_start,
            "dr": CapacityCalculationMode.scratch_start,
            "cloud": CapacityCalculationMode.scratch_start,
        }
        return calc_modes[location]


Retention = collections.namedtuple(
    "Retention", "incremental weekly_full monthly_full annual_full"
)
NIL_RETENTION = Retention(incremental=0, weekly_full=0, monthly_full=0, annual_full=0)

IGNORED_KEYS = set(["cbt", "sfr", "accelerator"])
# Remove below when Universal Share is ready
IGNORED_KEYS.add("universal_share")


class Workload:
    def __init__(self, workload_json):
        # copy for later use
        self.attr = copy.deepcopy(workload_json)

        # copy for mutation
        src = copy.deepcopy(workload_json)
        self.num_instances = src.pop("number_of_clients")
        self.name = src.pop("workload_name")
        self.type = src.pop("workload_type")
        self.slp_name = src.pop("storage_lifecycle_policy")
        self.workload_isolation = src.pop("workload_isolation")
        # Uncomment below when Universal Share is ready
        # self.universal_share = src.pop("universal_share")
        self.domain = src.pop("domain")
        if self.domain is not None:
            self.domain = self.domain.strip()
        self.orig_domain = self.domain
        self.site_name = src.pop("region").strip()
        self.front_end_nw = src.pop("appliance_front_end_network")

        # workload size and growth
        self.workload_size = int(src.pop("workload_size"))
        self.growth_rate = src.pop("annual_growth_rate")
        self.change_rate = src.pop("daily_change_rate")

        # replication
        self.backup_location_policy = src.pop("backup_location_policy")
        self.dr_dest = src.pop("dr_dest")
        self.dr_nw = src.pop("appliance_dr_network")
        self.ltr_nw = src.pop("appliance_ltr_network")
        self.validate_dr_dest()

        if not self.dr_enabled:
            self.dr_dest = None
            self.dr_nw = appliance.NetworkType.auto

        # client_dedup
        self.client_dedup = src.pop("client_dedup")
        if self.type in constants.NO_SUPPORT_CLIENT_DEDUP:
            self.client_dedup = False

        # dedup rates
        self.dedupe_ratio = src.pop("dedup_rate")
        self.initial_dedupe_ratio = src.pop("initial_dedup_rate")
        self.addl_full_dedupe_ratio = src.pop("dedupe_rate_adl_full")

        # backup frequencies
        self.fulls_per_week = src.pop("full_backup_per_week")
        self.log_backup_incremental_level = src.pop("log_backup_incremental_level")
        self.backup_incremental_level = src.pop("incremental_backup_level")
        incremental_frequency = src.pop("incremental_per_week")

        if incremental_frequency:
            self.incrementals_per_week = incremental_frequency
        else:
            self.incrementals_per_week = 0
        self.log_backup_capable = src.pop("log_backup_capable")
        self.log_backup_frequency = src.pop("log_backup_frequency_minutes")
        if self.log_backup_capable and self.log_backup_frequency:
            self.log_backups_per_week = (
                constants.MINUTES_PER_WEEK / self.log_backup_frequency
            )
        else:
            self.log_backup_frequency = 0
            self.log_backups_per_week = 0

        if (
            self.fulls_per_week + self.incrementals_per_week + self.log_backups_per_week
            == 0
        ):
            raise ValueError("workload has no backups")

        self.min_size_dup_jobs = src.pop("min_size_dup_jobs")
        self.max_size_dup_jobs = src.pop("max_size_dup_jobs")
        self.force_small_dup_jobs = src.pop("force_small_dup_jobs")

        # retention
        incr_ret_days = src.pop("incremental_retention_days")
        incr_ret_dr = src.pop("incremental_retention_dr")
        incr_ret_cloud = src.pop("incremental_retention_cloud")
        if self.type in constants.NO_SUPPORT_INCR_BACKUP_WORKLOAD_TYPES:
            incr_ret_days = incr_ret_dr = incr_ret_cloud = 0
        self.retention = {
            "local": Retention(
                incremental=incr_ret_days,
                weekly_full=src.pop("weekly_full_retention"),
                monthly_full=src.pop("monthly_retention"),
                annual_full=src.pop("annually_retention"),
            ),
            "dr": Retention(
                incremental=incr_ret_dr,
                weekly_full=src.pop("weekly_full_retention_dr"),
                monthly_full=src.pop("monthly_full_retention_dr"),
                annual_full=src.pop("annually_full_retention_dr"),
            ),
            "cloud": Retention(
                incremental=incr_ret_cloud,
                weekly_full=src.pop("weekly_full_retention_cloud"),
                monthly_full=src.pop("monthly_full_retention_cloud"),
                annual_full=src.pop("annually_full_retention_cloud"),
            ),
        }
        if not self.local_enabled:
            self.retention["local"] = NIL_RETENTION
        if not self.dr_enabled:
            self.retention["dr"] = NIL_RETENTION
        if not self.ltr_enabled:
            self.retention["cloud"] = NIL_RETENTION

        files_per_fetb = src.pop("files")
        workload_fetb = utils.Size.assume_unit(self.workload_size, "KiB").to_float(
            "TiB"
        )

        self.files = int(workload_fetb * files_per_fetb)
        self.files = min(
            self.files, constants.MAX_FILES_FOR_WORKLOAD_TYPE.get(self.type, self.files)
        )

        self.files_per_channel = src.pop("files_per_channel")
        self.channels = src.pop("channels")
        if self.channels:
            # Only really does anything for Oracle
            self.number_of_streams = self.files / self.channels
            logger.debug(
                "workload %s: number of streams: %f", self.name, self.number_of_streams
            )
        else:
            self.number_of_streams = 1

        unused_keys = set(src.keys()) - IGNORED_KEYS
        if unused_keys:
            raise ValueError(f"unused keys {src.keys()}")

        self.yearly_sizes = self.dr_sizes = self.cloud_sizes = None

        self.master_yearly_tasks = {}
        self.media_yearly_tasks = {}
        self.ltr_yearly_tasks = {}
        self.m_resources = {}
        self.media_resources = {}  # testcase only
        self.master_yearly_resources = {}
        self.media_yearly_resources = {}
        self.ltr_yearly_resources = {}
        self.master_resources = []
        self.domain_adjusted = False

    def __str__(self):
        return str(self.__class__) + ": " + str(self.__dict__)

    def __repr__(self):
        return str(self.__class__) + ": " + str(self.__dict__)

    def restore_domain(self):
        self.domain = self.orig_domain
        self.domain_adjusted = False

    def validate_dr_dest(self):
        dr_dest_specified = self.dr_dest is not None and len(self.dr_dest.strip()) > 0
        if self.dr_enabled and not dr_dest_specified:
            raise ValueError(
                f"Backup policy for workload {self.name} requires DR, but no DR destination was specified"
            )
        if self.dr_enabled and self.site_name == self.dr_dest.strip():
            raise ValueError("DR destination may not be the same as primary site")
        if not self.dr_enabled and dr_dest_specified:
            raise ValueError(
                f"Backup policy for workload {self.name} does not call for DR, but a DR destination was specified"
            )

    @property
    def max_retention(self):
        return Retention(
            incremental=max(r.incremental for r in self.retention.values()),
            weekly_full=max(r.weekly_full for r in self.retention.values()),
            monthly_full=max(r.monthly_full for r in self.retention.values()),
            annual_full=max(r.annual_full for r in self.retention.values()),
        )

    @property
    def local_enabled(self):
        return "local" in self.backup_location_policy

    @property
    def dr_enabled(self):
        return "dr" in self.backup_location_policy

    @property
    def ltr_enabled(self):
        return "ltr" in self.backup_location_policy

    def replications_per_week(self, year):
        duplication_size = int(self.client_size_for_year(year))
        weekly_volume = (
            duplication_size
            * self.change_rate
            * self.dedupe_ratio
            * constants.DAYS_PER_WEEK
        )

        # how many jobs are required if duplication happens exactly at
        # min_size or max_size?
        jobs_by_min_size = math.ceil(weekly_volume / int(self.min_size_dup_jobs))
        jobs_by_max_size = math.ceil(weekly_volume / int(self.max_size_dup_jobs))

        # how many jobs are required if duplication happens according
        # to force_interval?  These jobs will happen after every full
        # and incremental backup.
        jobs_by_force_interval = (
            self.fulls_per_week + self.incrementals_per_week + self.log_backups_per_week
        )
        if jobs_by_force_interval == 0:
            # no backups, then no duplications
            return 0

        size_by_force_interval = weekly_volume / jobs_by_force_interval

        # if job size is too big at force interval, let max_size
        # control number of jobs
        if size_by_force_interval > self.max_size_dup_jobs:
            return jobs_by_max_size

        # between min_size and force_interval, we pick whichever leads
        # to more jobs.  if min_size would cause fewer jobs,
        # force_interval should take precedence to meet the RPO
        # requirements
        return max(jobs_by_force_interval, jobs_by_min_size)

    def incremental_storage_for_year(self, year):
        current_incremental = self.get_yearly()[year]["incrementals"]
        return utils.Size.assume_unit(current_incremental, "KiB")

    def dr_incremental_storage_for_year(self, year):
        incrs = self.dr_sizes[year]["incrementals"]
        return utils.Size.assume_unit(incrs, "KiB")

    def full_storage_for_year(self, year):
        full_incremental = self.get_yearly()[year]["total_full"]
        return utils.Size.assume_unit(full_incremental, "KiB")

    def dr_full_storage_for_year(self, year):
        full = self.dr_sizes[year]["total_full"]
        return utils.Size.assume_unit(full, "KiB")

    def client_size_for_year(self, year):
        client_size = self.get_yearly()[year]["size"]
        return utils.Size.assume_unit(client_size, "KiB")

    def total_storage_for_year(self, year):
        total_current = self.get_yearly()[year]["total_current"]
        return utils.Size.assume_unit(total_current, "KiB")

    def dr_storage_for_year(self, year):
        total_current = self.dr_sizes[year]["total_current"]
        return utils.Size.assume_unit(total_current, "KiB")

    def cloud_storage_for_year(self, year):
        total_current = self.cloud_sizes[year]["total_current"]
        return utils.Size.assume_unit(total_current, "KiB")

    def cloud_storage_worst_case_for_year(self, year):
        sz = self.cloud_sizes[year]["worst_case_total"]
        return utils.Size.assume_unit(sz, "KiB")

    def cloud_minimum_bandwidth(self, year):
        sz = self.cloud_sizes[year]["worst_case_total"]
        return utils.Size.assume_unit(sz, "KiB")

    def total_storage_pre_dedupe_for_year(self, year):
        total_current = self.get_yearly()[year]["total_current_pre_dedupe"]
        return utils.Size.assume_unit(total_current, "KiB")

    def dr_storage_pre_dedupe_for_year(self, year):
        total_current = self.dr_sizes[year]["total_current_pre_dedupe"]
        return utils.Size.assume_unit(total_current, "KiB")

    def cloud_storage_pre_dedupe_for_year(self, year):
        total_current = self.cloud_sizes[year]["total_current_pre_dedupe"]
        return utils.Size.assume_unit(total_current, "KiB")

    def _cloud_gib_months_for_year(self, year, data_fn):
        if year == 0:
            return utils.Size.ZERO
        last_usage = int(data_fn(year - 1))
        this_usage = int(data_fn(year))
        return utils.Size.assume_unit(
            last_usage * 12 + (this_usage - last_usage) * 6.5, "KiB"
        )

    def cloud_gib_months_for_year(self, year):
        return self._cloud_gib_months_for_year(year, self.cloud_storage_for_year)

    def cloud_gib_months_worst_case_for_year(self, year):
        return self._cloud_gib_months_for_year(
            year, self.cloud_storage_worst_case_for_year
        )

    def backup_volume_per_week(self, year):
        return (
            self.client_size_for_year(year) * self.change_rate * constants.DAYS_PER_WEEK
        )

    def catalog_storage_for_year(self, year):
        return self.yearly_catalog_sizes[year]["catalog_size"]

    def master_resources_for_year(self, year):
        return self.master_resources[year]

    def get_yearly(self):
        return self.yearly_sizes

    def ltr_resource_for_year(self, site, window, year, resource):
        return self.ltr_yearly_resources[(site, window)][year][resource]

    def resource_for_year(self, site, window, year, resource):
        return self.media_yearly_resources[(site, window)][year][resource]

    def ltr_resources(self, site, window, year):
        if (site, window) not in self.ltr_yearly_resources:
            return None
        return self.ltr_yearly_resources[(site, window)][year]

    def resources(self, site, window, year, pack_flex):
        if (site, window) not in self.media_yearly_resources:
            return None
        media_res = self.media_yearly_resources[(site, window)][year]

        # if this is Flex, resources for media server container may
        # not include LTR.  It *will* include LTR, if there is also a
        # local backup component, because in that case, the media
        # server container might be sending data over to the MSDP-C
        # container.  If, on the other hand, the workload is LTR only,
        # client can send backup directly to the MSDP-C container; in
        # that case, LTR resources will not be included for the media
        # server container.

        if pack_flex and not self.local_enabled:
            return media_res

        if (site, window) not in self.ltr_yearly_resources:
            return media_res
        ltr_res = self.ltr_yearly_resources[(site, window)][year]
        res = {}
        for k in [
            "total_job_duration",
            "total_cpu_utilization",
            "total_io_utilization",
            "total_nw_utilization",
            "total_dr_nw_utilization",
            "total_cloud_nw_utilization",
        ]:
            res[k] = media_res[k] + ltr_res[k]
        for k in ["total_mem_utilization"]:
            res[k] = max(media_res[k], ltr_res[k])
        return res

    def weekly_transfer_volume_dr(self, year):
        if not self.dr_enabled:
            return utils.Size.ZERO

        dr_volume = (
            int(self.client_size_for_year(year))
            * self.change_rate
            * constants.DAYS_PER_WEEK
        )
        return utils.Size.assume_unit(dr_volume, "KiB")

    def weekly_transfer_volume_ltr(self, year):
        if not self.ltr_enabled:
            return utils.Size.ZERO

        ltr_volume = (
            int(self.client_size_for_year(year))
            * self.change_rate
            * constants.DAYS_PER_WEEK
        )
        return utils.Size.assume_unit(ltr_volume, "KiB")

    def generate_tasks(
        self,
        domain_name,
        site_names,
        appliance_spec,
        window_sizes,
        timeframe,
    ):

        for site_name in site_names:
            if site_name not in [self.site_name, self.dr_dest]:
                raise ValueError("workload not associated with site")

            self.master_yearly_tasks[(domain_name, site_name)] = [
                task.primary_tasks_for_workload(
                    self,
                    domain_name,
                    site_name,
                    appliance_spec["master_app"],
                    window_sizes,
                    yr,
                )
                for yr in range(0, timeframe.num_years + 1)
            ]
            self.sum_all_master_resources(domain_name, site_name, timeframe)

            media_app = appliance_spec["media_app"]
            self.media_yearly_tasks[(domain_name, site_name)] = [
                task.media_tasks_for_workload(
                    self,
                    domain_name,
                    site_name,
                    media_app,
                    window_sizes,
                    yr,
                )
                for yr in range(0, timeframe.num_years + 1)
            ]

            self.ltr_yearly_tasks[(domain_name, site_name)] = [
                task.ltr_tasks_for_workload(
                    self,
                    domain_name,
                    site_name,
                    appliance_spec.get("ltr_app", media_app),
                    window_sizes,
                    yr,
                )
                for yr in range(0, timeframe.num_years + 1)
            ]

            self.sum_all_media_resources(domain_name, site_name, timeframe)
            self.sum_all_ltr_resources(domain_name, site_name, timeframe)

        self.calculate_master_resources(timeframe)

    @staticmethod
    def m_resources_for_year(tasks, site_name, window):
        """calculate resources for master server"""
        return {
            "total_job_duration": sum(
                t.resources["duration"]
                for t in tasks
                if t.site_name == site_name and t.window == window
            ),
            "total_cpu_utilization": sum(
                t.resources["cpu"]
                for t in tasks
                if t.site_name == site_name and t.window == window
            ),
            "total_io_utilization": sum(
                t.resources["io"]
                for t in tasks
                if t.site_name == site_name and t.window == window
            ),
            "total_mem_utilization": max(
                (
                    t.resources["mem"]
                    for t in tasks
                    if t.site_name == site_name and t.window == window
                ),
                default=0,
            ),
            "total_nw_utilization": utils.Size.sum(
                t.resources["nic"]
                for t in tasks
                if t.site_name == site_name and t.window == window
            ),
        }

    @staticmethod
    def resources_for_year(tasks, site_name, window):
        return {
            "total_job_duration": sum(
                t.resources["duration"]
                for t in tasks
                if t.site_name == site_name and t.window == window
            ),
            "total_cpu_utilization": sum(
                t.resources["cpu"]
                for t in tasks
                if t.site_name == site_name and t.window == window
            ),
            "total_absolute_io": utils.Size.sum(
                t.resources["absolute_io"]
                for t in tasks
                if t.site_name == site_name and t.window == window
            ),
            "total_io_utilization": sum(
                t.resources["io"]
                for t in tasks
                if t.site_name == site_name and t.window == window
            ),
            "total_mem_utilization": max(
                (
                    t.resources["mem"]
                    for t in tasks
                    if t.site_name == site_name and t.window == window
                ),
                default=0,
            ),
            "total_nw_utilization": utils.Size.sum(
                t.resources["nic"]
                for t in tasks
                if t.site_name == site_name and t.window == window
            ),
            "total_dr_nw_utilization": utils.Size.sum(
                t.resources["nic_dr"]
                for t in tasks
                if t.site_name == site_name
                and t.window == window
                and t.task_type
                in [task.TaskType.replication_source, task.TaskType.replication_target]
            ),
            "total_cloud_nw_utilization": utils.Size.sum(
                t.resources["nic_cloud"]
                for t in tasks
                if t.site_name == site_name
                and t.window == window
                and t.task_type
                in [task.TaskType.ltr_only_copy, task.TaskType.ltr_with_msdp_copy]
            ),
        }

    def sum_all_master_resources(self, domain, site, timeframe):
        if (domain, site) not in self.master_yearly_tasks:
            return
        for window in [
            task.WindowType.master,
        ]:
            self.master_yearly_resources[(domain, window)] = []
            for year in range(0, timeframe.num_years + 1):
                self.master_yearly_resources[(domain, window)].append(
                    Workload.m_resources_for_year(
                        self.master_yearly_tasks[(domain, site)][year], site, window
                    )
                )
            self.m_resources[(domain, window)] = self.master_yearly_resources[
                (domain, window)
            ][timeframe.planning_year]

        logger.debug(
            'workload "%s" required %s resources are %s',
            self.name,
            constants.MANAGEMENT_SERVER_DESIGNATION.lower(),
            self.m_resources,
        )

    def sum_all_media_resources(self, domain, site, timeframe):
        if (domain, site) not in self.media_yearly_tasks:
            return
        for window in [
            task.WindowType.full,
            task.WindowType.incremental,
            task.WindowType.replication,
        ]:
            self.media_yearly_resources[(site, window)] = []
            for year in range(0, timeframe.num_years + 1):
                self.media_yearly_resources[(site, window)].append(
                    Workload.resources_for_year(
                        self.media_yearly_tasks[(domain, site)][year], site, window
                    )
                )
            self.media_resources[(site, window)] = self.media_yearly_resources[
                (site, window)
            ][timeframe.planning_year]
        self.software_resources = {"dbs": 0, "vms": 0}
        if self.log_backup_frequency == 15:
            self.software_resources["dbs"] = 1
        if self.type.lower() == "vmware":
            self.software_resources["vms"] = 1
        self.software_resources["files"] = self.files
        self.software_resources["jobs/day"] = int(
            sum(
                t.weekly_count
                for t in self.media_yearly_tasks[(domain, site)][
                    timeframe.planning_year
                ]
            )
            / constants.DAYS_PER_WEEK
        )

        logger.debug(
            'workload "%s" required media server resources are %s',
            self.name,
            self.media_resources,
        )

    def sum_all_ltr_resources(self, domain, site, timeframe):
        ltr_resources_dbg = {}
        if (domain, site) not in self.ltr_yearly_tasks:
            return
        for window in [
            task.WindowType.full,
            task.WindowType.incremental,
            task.WindowType.replication,
        ]:
            self.ltr_yearly_resources[(site, window)] = []
            for year in range(0, timeframe.num_years + 1):
                self.ltr_yearly_resources[(site, window)].append(
                    Workload.resources_for_year(
                        self.ltr_yearly_tasks[(domain, site)][year], site, window
                    )
                )
            ltr_resources_dbg[(site, window)] = self.ltr_yearly_resources[
                (site, window)
            ][timeframe.planning_year]

        logger.debug(
            'workload "%s" required ltr server resources are %s',
            self.name,
            ltr_resources_dbg,
        )

    def jobs_per_day(self, year):
        return (
            sum(
                t.weekly_count
                for t in self.master_yearly_tasks[(self.domain, self.site_name)][year]
                if t.is_job
            )
            / constants.DAYS_PER_WEEK
        )

    def files_for_year(self, year):
        return self.yearly_files[year]

    def backed_up_files(self, year):
        return self.yearly_catalog_sizes[year]["catalog_nfiles"]

    def backed_up_images(self, year):
        return self.yearly_catalog_sizes[year]["catalog_nimages"]

    def calculate_master_resources(self, timeframe):
        for year in range(timeframe.num_years + 1):
            res = {
                "jobs/day": self.jobs_per_day(year),
                "files": self.backed_up_files(year),
                "images": self.backed_up_images(year),
            }
            res[(self.domain, task.WindowType.master)] = self.master_yearly_resources[
                (self.domain, task.WindowType.master)
            ][year]

            self.master_resources.append(res)

    def calculate_capacity(
        self, timeframe: utils.TimeFrame, excess_cloud_factor: float = 0
    ):
        """
        Calculate storage requirements for given timeframe.

        This will assign backup storage requirements for the various
        tiers to self.yearly_sizes, self.dr_sizes and
        self.cloud_sizes.  Additionally, catalog capacity is also
        calculated and assigned to self.yearly_catalog_sizes.
        """
        yearly_sizes = [self.workload_size]
        for i in range(1, timeframe.num_years + 1):
            yearly_sizes.append(yearly_sizes[-1] * (1 + self.growth_rate))

        self.yearly_sizes = [
            Workload.calculate_one_year_capacity(
                self,
                "local",
                i,
                yearly_sizes,
                CapacityCalculationMode.mode_for("local"),
            )
            for (i, sz) in enumerate(yearly_sizes)
        ]
        self.dr_sizes = [
            Workload.calculate_one_year_capacity(
                self, "dr", i, yearly_sizes, CapacityCalculationMode.mode_for("dr")
            )
            for (i, sz) in enumerate(yearly_sizes)
        ]
        self.cloud_sizes = [
            Workload.calculate_one_year_capacity(
                self,
                "cloud",
                i,
                yearly_sizes,
                CapacityCalculationMode.mode_for("cloud"),
                excess_cloud_factor,
            )
            for (i, sz) in enumerate(yearly_sizes)
        ]

        self.calculate_catalog_capacity(timeframe)

    def calculate_catalog_capacity(self, timeframe):
        yearly_nfiles = [self.files]
        for i in range(1, timeframe.num_years + 1):
            yearly_nfiles.append(
                yearly_nfiles[-1] + int(yearly_nfiles[-1] * self.growth_rate)
            )
        self.yearly_catalog_sizes = [
            self.calculate_one_year_catalog(nfiles) for nfiles in yearly_nfiles
        ]
        self.yearly_files = yearly_nfiles

    def calculate_one_year_catalog(self, nfiles):
        retention = self.max_retention

        nimages = retention.weekly_full + retention.monthly_full + retention.annual_full
        nfullfiles = nimages * nfiles

        incs_at_a_time = (
            self.incrementals_per_week * retention.incremental / constants.DAYS_PER_WEEK
        )
        nincrfiles = incs_at_a_time * nfiles
        if self.type in constants.INCR_BACKUP_ADJUST_WORKLOAD_TYPES:
            nincrfiles = incs_at_a_time * nfiles * self.change_rate

        total_nfiles = nfullfiles + nincrfiles

        catalog_bytes = total_nfiles * constants.CATALOG_PER_FILE
        catalog_size = utils.Size.assume_unit(catalog_bytes // 1024, "KiB")
        fixed = utils.Size.from_string(constants.CATALOG_FIXED)
        return {
            "catalog_size": fixed + catalog_size,
            "catalog_nfiles": int(total_nfiles),
            "catalog_nimages": int(nimages),
        }

    @staticmethod
    def calculate_one_year_capacity(
        workload: "Workload",
        retention_selector: StorageCategory,
        year: int,
        sizes: List[int],
        calculation_mode: CapacityCalculationMode,
        excess_factor: float = 0,
    ):
        """
        Calculate storage requirements at the end of the given year.

        The sizes argument is the list of client sizes at each year.
        """
        retention = workload.retention[retention_selector]

        retention_level_for_inc_backup_week = math.ceil(
            retention.incremental / constants.DAYS_PER_WEEK
        )

        if calculation_mode == CapacityCalculationMode.steady_state:
            monthly_images = retention.monthly_full
            weekly_images = retention.weekly_full
            annual_images = retention.annual_full
            incr_images = retention_level_for_inc_backup_week
        elif calculation_mode == CapacityCalculationMode.scratch_start:
            monthly_images = min(
                retention.monthly_full, year * constants.MONTHS_PER_YEAR
            )
            weekly_images = min(retention.weekly_full, year * constants.WEEKS_PER_YEAR)
            annual_images = min(retention.annual_full, year)
            incr_images = min(
                retention_level_for_inc_backup_week, year * constants.WEEKS_PER_YEAR
            )

        if calculation_mode == CapacityCalculationMode.scratch_start and year == 0:
            initial_full = initial_full_pre_dedupe = 0.0
        elif retention.weekly_full > 0 or retention.monthly_full > 0:
            initial_full_pre_dedupe, initial_full = calculate_initial_full(
                sizes[year], workload.initial_dedupe_ratio
            )
        else:
            initial_full = initial_full_pre_dedupe = 0.0

        additional_full_pre_dedupe, additional_full = Workload.yearly_calculate(
            weekly_images,
            constants.WEEKS_PER_YEAR,
            sizes,
            year,
            lambda n_images, client_size: calculate_addl_fulls(
                client_size, workload.addl_full_dedupe_ratio, n_images
            ),
        )

        monthly_full_pre_dedupe, monthly_full = Workload.yearly_calculate(
            monthly_images,
            constants.MONTHS_PER_YEAR,
            sizes,
            year,
            lambda n_images, client_size: calculate_monthly_full(
                client_size,
                workload.addl_full_dedupe_ratio,
                n_images,
                weekly_images,
            ),
        )

        annual_full_pre_dedupe, annual_full = Workload.yearly_calculate(
            annual_images,
            1,
            sizes,
            year,
            lambda n_images, client_size: calculate_annual_full(
                client_size,
                workload.addl_full_dedupe_ratio,
                n_images,
                annual_images,
            ),
        )

        incrementals_pre_dedupe, incrementals = Workload.yearly_calculate(
            incr_images,
            workload.incrementals_per_week * constants.WEEKS_PER_YEAR,
            sizes,
            year,
            lambda n_images, client_size: calculate_incrementals(
                client_size,
                workload.change_rate,
                workload.dedupe_ratio,
                n_images,
                workload.incrementals_per_week,
            ),
        )

        total_full = initial_full + additional_full + monthly_full + annual_full
        total_full_pre_dedupe = (
            initial_full_pre_dedupe
            + additional_full_pre_dedupe
            + monthly_full_pre_dedupe
            + annual_full_pre_dedupe
        )

        return {
            "size": sizes[year],
            "site_name": workload.site_name,
            "additional_full": additional_full,
            "initial_full": initial_full,
            "incrementals": incrementals,
            "monthly_full": monthly_full,
            "annual_full": annual_full,
            "total_full": total_full,
            "total_current": total_full + incrementals,
            "initial_full_pre_dedupe": initial_full_pre_dedupe,
            "incrementals_pre_dedupe": incrementals_pre_dedupe,
            "additional_full_pre_dedupe": additional_full_pre_dedupe,
            "monthly_full_pre_dedupe": monthly_full_pre_dedupe,
            "annual_full_pre_dedupe": annual_full_pre_dedupe,
            "total_full_pre_dedupe": total_full_pre_dedupe,
            "total_current_pre_dedupe": total_full_pre_dedupe + incrementals_pre_dedupe,
            "worst_case_total": (total_full + incrementals) * (1 + excess_factor),
            "year": year,
        }

    @staticmethod
    def yearly_calculate(
        total_images: int,
        max_per_year: int,
        sizes: List[int],
        year: int,
        calculator_fn: Callable[[int, int], SizePair],
    ):
        """
        Calculate size for given year, adjusting number of images.

        With large retention intervals, not all images being stored at
        any given time are consuming the same storage space.  The most
        recent images use the client size from the current year, the
        set of images earlier than that use the client size as of the
        year the images were created.  Given a total number of images
        and the maximum number of images possible in a year, this
        function calls the given calculation function multiple times,
        with the number of images and client size adjusted for each
        year.  It returns the total size across all the images.
        """
        n_images = total_images
        size_idx = year
        sizes_per_year = []
        while n_images > 0:
            if size_idx == 0:
                this_year_images = n_images
            else:
                this_year_images = min(n_images, max_per_year)
            sizes_per_year.append(calculator_fn(this_year_images, sizes[size_idx]))
            n_images -= this_year_images
            size_idx -= 1
        return SizePair(
            pre_dedupe=sum(sz.pre_dedupe for sz in sizes_per_year),
            post_dedupe=sum(sz.post_dedupe for sz in sizes_per_year),
        )


def get_site_hints_from_workloads(
    workload_list, planning_year, sizing_flex=False
) -> collections.defaultdict:
    sites = collections.defaultdict(lambda: appliance.SiteHints())

    site_domains = collections.defaultdict(lambda: set())
    if sizing_flex:
        for w in workload_list:
            site_domains[w.site_name].add(w.domain)
            if w.dr_enabled:
                site_domains[w.dr_dest].add(w.domain)

    for w in workload_list:
        if sizing_flex:
            key = w.site_name
            dr_key = w.dr_dest
        else:
            key = (w.domain, w.site_name)
            dr_key = (w.domain, w.dr_dest)
        sites[key].sizing_flex = sizing_flex
        sites[key].disk += w.total_storage_for_year(planning_year) * w.num_instances
        if w.ltr_enabled:
            sites[key].ltr_src = True
        if w.dr_enabled:
            sites[dr_key].sizing_flex = sizing_flex
            sites[dr_key].disk += w.dr_storage_for_year(planning_year) * w.num_instances
            sites[dr_key].dr_dest = True

    if not sizing_flex:
        return sites

    flex_sites = collections.defaultdict(lambda: appliance.SiteHints())
    for site_name, site_hints in sites.items():
        for domain in site_domains[site_name]:
            flex_sites[(domain, site_name)] = site_hints

    return flex_sites


def site_storage_usage(workloads, first_extension):
    storage_usage = []
    gb_months = []

    for yr in range(first_extension + 1):
        yr_storage = collections.defaultdict(int)
        yr_storage["cloud"] = 0

        yr_gb_months = {}

        for w in workloads:
            local_usage = int(w.total_storage_for_year(yr) * w.num_instances)
            yr_storage[w.site_name] += local_usage

            if w.dr_enabled:
                dr_usage = int(w.dr_storage_for_year(yr) * w.num_instances)
                yr_storage[w.dr_dest] += dr_usage

            if w.ltr_enabled:
                yr_storage["cloud"] += int(
                    w.cloud_storage_for_year(yr) * w.num_instances
                )
        storage_usage.append(yr_storage)

        for site_name, this_usage in yr_storage.items():
            if yr == 0:
                last_usage = 0
            else:
                last_usage = storage_usage[yr - 1][site_name]
            yr_gb_months[site_name] = last_usage * 12 + (this_usage - last_usage) * 6.5
        gb_months.append(yr_gb_months)

    storage = collections.defaultdict(list)
    for usage, yr_gb_months in zip(storage_usage, gb_months):
        for site_name in usage.keys():
            storage[site_name].append(
                {
                    "usage": utils.Size.assume_unit(usage[site_name], "KiB"),
                    "gb_months": utils.Size.assume_unit(yr_gb_months[site_name], "KiB"),
                }
            )

    return storage


def storage_usage(workloads: List[Workload], timeframe: utils.TimeFrame):
    usage = {}

    for w in workloads:
        logger.debug("calculating storage usage for %s", w.name)
        usage[w.name] = []
        for yr in range(timeframe.num_years + 1):
            volume = utils.Size.assume_unit(
                w.num_instances
                * sum(
                    t.volume
                    for t in w.media_yearly_tasks[(w.orig_domain, w.site_name)][yr]
                    if t.task_type
                    in (task.TaskType.full_backup, task.TaskType.incremental_backup)
                ),
                "KiB",
            )
            network_bw = (
                utils.Size.sum(
                    t.resources["nic"]
                    for t in w.media_yearly_tasks[(w.orig_domain, w.site_name)][yr]
                    if t.task_type
                    in (task.TaskType.full_backup, task.TaskType.incremental_backup)
                )
                * w.num_instances
            )

            info = {
                "catalog": w.catalog_storage_for_year(yr) * w.num_instances,
                "volume": volume,
                "network_bw": network_bw,
                "workload": w,
            }
            usage[w.name].append(info)

    return usage


def appliance_for_catalog(workloads, timeframe, media_choices, safety_margins):
    """
    Return suitable appliances per-domain suitable for catalog storage.
    """
    domain_catalogs = collections.defaultdict(lambda: utils.Size.ZERO)
    for w in workloads:
        domain_catalogs[w.domain] += (
            w.catalog_storage_for_year(timeframe.planning_year) * w.num_instances
        )
    domain_medias = collections.defaultdict(set)
    for (domain, site_name), media_app in media_choices.items():
        domain_medias[domain].add(media_app.model)

    domain_appliances = {}
    for domain, catalog_size in domain_catalogs.items():
        domain_appliances[domain] = appliance.Appliance.find_management(
            catalog_size, domain_medias[domain], safety_margins
        )

    return domain_appliances


def calculate_capacity_all_workloads(workloads, timeframe, excess_cloud_factor):
    for w in workloads:
        w.calculate_capacity(timeframe, excess_cloud_factor)
