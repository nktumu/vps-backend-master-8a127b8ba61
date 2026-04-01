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

import enum
import logging

from use_core import constants
from use_core.shaping import PrimaryRunConfig, Resources

logger = logging.getLogger(__name__)


class WindowType(enum.Enum):
    full = 1
    incremental = 2
    replication = 3
    master = 4

    def __str__(self):
        return f"WindowType.{self.name}"

    @staticmethod
    def packing_windows():
        return [WindowType.full, WindowType.incremental, WindowType.replication]


MasterTaskType = enum.Enum(
    "MasterTaskType",
    [
        "file_insertion_full",
        "file_insertion_incr",
        "file_insertion_log",
        "image_expiration",
        "image_import",
        "image_export",
        "image_replication",
        "catalog_compression",
        "catalog_backup",
    ],
)

# These are the tasks done by master server that should count as
# "jobs" against the jobs/day limits.
MASTER_JOBS = [
    MasterTaskType.file_insertion_full,
    MasterTaskType.file_insertion_incr,
    MasterTaskType.file_insertion_log,
    MasterTaskType.catalog_backup,
    MasterTaskType.image_import,
    MasterTaskType.image_export,
    MasterTaskType.image_replication,
]

TaskType = enum.Enum(
    "TaskType",
    [
        "full_backup",
        "incremental_backup",
        "log_backup",
        "replication_source",
        "replication_target",
        "ltr_only_copy",
        "ltr_with_msdp_copy",
    ],
)

TaskDuplexType = enum.Enum("TaskDuplexType", ["half", "full"])


class MasterTask:
    def __init__(
        self,
        task_type,
        site_name,
        window,
        weekly_count,
        workload_ref,
        year,
    ):
        self.task_type = task_type
        self.site_name = site_name
        self.window = window
        self.weekly_count = weekly_count
        self.workload = workload_ref
        self.year = year

        self.volume = None
        self.resources = None
        self.duplex = TaskDuplexType.half

    def __str__(self):
        return str(self.__class__) + ": " + str(self.__dict__)

    def __repr__(self):
        return str(self.__class__) + ": " + str(self.__dict__)

    @property
    def is_job(self):
        return self.task_type in MASTER_JOBS

    def calculate_master_volume(self):
        if self.task_type == MasterTaskType.file_insertion_full:
            volume = self.workload.files if self.weekly_count else 0

        elif self.task_type == MasterTaskType.file_insertion_incr:
            volume = self.workload.files if self.weekly_count else 0

            if self.workload.type in constants.INCR_BACKUP_ADJUST_WORKLOAD_TYPES:
                volume = (
                    (
                        volume
                        * self.workload.change_rate
                        * constants.DAYS_PER_WEEK
                        / self.weekly_count
                    )
                    if self.weekly_count
                    else 0
                )

        elif self.task_type == MasterTaskType.file_insertion_log:
            volume = (
                (
                    self.workload.files
                    * self.workload.change_rate
                    * constants.DAYS_PER_WEEK
                    / self.weekly_count
                )
                if self.weekly_count
                else 0
            )

        else:
            assert False

        self.volume = volume

    def calculate_master_resources(self, appliance_spec, window_sizes):
        window_duration = Task.window_for_task_type(self.task_type, window_sizes)

        disk_usage = int(self.workload.catalog_storage_for_year(self.year))
        nfiles = self.workload.files_for_year(self.year)
        rc = PrimaryRunConfig(self.workload.type, self.task_type, nfiles)
        year_resource = Resources.for_primary(rc, appliance_spec)
        year_resource.calculate_utilizations(window_duration)
        master_resource_data = {
            "disk": disk_usage,
            "cpu": year_resource.cpu_utilization,
            "duration": year_resource.job_duration,
            "io": year_resource.io_utilization,
            "mem": year_resource.mem_utilization,
            "nic": year_resource.nic_utilization,
        }
        self.resources = master_resource_data


class Task:
    def __init__(
        self,
        task_type,
        site_name,
        window,
        weekly_count,
        workload_ref,
        year,
    ):
        self.task_type = task_type
        self.site_name = site_name
        self.window = window
        self.weekly_count = weekly_count
        self.workload = workload_ref
        self.year = year

        self.volume = None
        self.resources = None
        self.duplex = TaskDuplexType.half

    def __str__(self):
        return str(self.__class__) + ": " + str(self.__dict__)

    def __repr__(self):
        return str(self.__class__) + ": " + str(self.__dict__)

    def calculate_volume(self):
        workload_size = int(self.workload.client_size_for_year(self.year))
        if (self.task_type, self.workload.backup_incremental_level) == (
            TaskType.incremental_backup,
            "differential",
        ):
            volume = (
                (
                    workload_size
                    * self.workload.change_rate
                    * constants.DAYS_PER_WEEK
                    / self.weekly_count
                )
                if self.weekly_count
                else 0
            )

            if self.workload.client_dedup:
                volume = volume * (1 - self.workload.dedupe_ratio)

        elif self.task_type == TaskType.incremental_backup:
            # TODO this calculation is suspect for cumulative backups
            volume = workload_size * self.workload.change_rate

            if self.workload.client_dedup:
                volume = volume * (1 - self.workload.dedupe_ratio)

        elif self.task_type == TaskType.full_backup:
            volume = workload_size

            if self.workload.client_dedup:
                volume = volume * (1 - self.workload.dedupe_ratio)

        elif self.task_type == TaskType.log_backup:
            volume = (
                (
                    workload_size
                    * self.workload.change_rate
                    * constants.DAYS_PER_WEEK
                    / self.weekly_count
                )
                if self.weekly_count
                else 0
            )

        elif self.task_type in [
            TaskType.replication_source,
            TaskType.replication_target,
            TaskType.ltr_only_copy,
            TaskType.ltr_with_msdp_copy,
        ]:
            volume = (
                (
                    workload_size
                    * self.workload.change_rate
                    * self.workload.dedupe_ratio
                    * constants.DAYS_PER_WEEK
                    / self.weekly_count
                )
                if self.weekly_count
                else 0
            )

        else:
            assert False

        self.volume = volume * self.weekly_count

    @staticmethod
    def window_for_task_type(task_type, window_sizes):
        task_windows = {
            MasterTaskType.file_insertion_full: WindowType.master,
            MasterTaskType.file_insertion_incr: WindowType.master,
            MasterTaskType.file_insertion_log: WindowType.master,
            MasterTaskType.image_expiration: WindowType.master,
            MasterTaskType.image_import: WindowType.master,
            MasterTaskType.image_export: WindowType.master,
            MasterTaskType.image_replication: WindowType.master,
            MasterTaskType.catalog_compression: WindowType.master,
            MasterTaskType.catalog_backup: WindowType.master,
            TaskType.incremental_backup: WindowType.incremental,
            TaskType.full_backup: WindowType.full,
            TaskType.log_backup: WindowType.incremental,
            TaskType.replication_source: WindowType.replication,
            TaskType.replication_target: WindowType.replication,
            TaskType.ltr_only_copy: WindowType.replication,
            TaskType.ltr_with_msdp_copy: WindowType.replication,
        }

        return Task.duration_for_window(task_windows[task_type], window_sizes)

    @staticmethod
    def duration_for_window(window_type, window_sizes):
        durations = {
            WindowType.full: window_sizes.full_backup,
            WindowType.incremental: window_sizes.incremental_backup,
            WindowType.replication: window_sizes.replication,
            WindowType.master: window_sizes.full_backup
            + window_sizes.incremental_backup
            + window_sizes.replication,
        }

        return durations[window_type]

    def calculate_resources(self, appliance_spec, window_sizes):
        window_duration = Task.window_for_task_type(self.task_type, window_sizes)

        disk_usage = int(self.workload.total_storage_for_year(self.year))
        dedupe_ratio = self.workload.dedupe_ratio
        if self.workload.client_dedup:
            dedupe_ratio = 0

        year_resource = Resources.for_media(
            self.task_type,
            self.workload.type,
            int(self.volume),
            dedupe_ratio,
            self.workload.number_of_streams,
            appliance_spec,
            self.duplex,
        )
        year_resource.calculate_utilizations(window_duration)
        resource_data = {
            "disk": disk_usage,
            "cpu": year_resource.cpu_utilization,
            "absolute_io": year_resource.absolute_io,
            "io": year_resource.io_utilization,
            "mem": year_resource.mem_utilization,
            "nic": year_resource.nic_utilization,
            "nic_dr": year_resource.nic_dr_utilization,
            "nic_cloud": year_resource.nic_cloud_utilization,
            "duration": int(year_resource.job_duration),
            "DR Transfer GiB/Week": year_resource.weekly_transfer_DR,
            "Cloud Transfer GiB/week": year_resource.weekly_transfer_LTR,
            "Cloud Minimum Bandwidth(Mbps)": year_resource.weekly_transfer_LTR,
            "minimum_bandwidth": year_resource.weekly_transfer_LTR,
        }
        # For DR duplication, additional bandwidth is required from
        # the backup bandwidth.
        if self.task_type in [TaskType.replication_source, TaskType.replication_target]:
            resource_data["nic_dr"] = year_resource.nic_utilization
        # For cloud duplication, additional bandwidth restrictions
        # apply.  We treat this as a separate additional resource.
        # So cloud duplication eats into the bandwidth
        # available for CC in addition to appliance NIC bandwidth.
        if self.task_type in [TaskType.ltr_only_copy, TaskType.ltr_with_msdp_copy]:
            resource_data["nic_cloud"] = year_resource.nic_utilization
        self.resources = resource_data


def ltr_tasks_for_workload(
    workload, domain_name, site_name, appliance_spec, window_sizes, year
):
    ltr_tasks = []

    if site_name == workload.site_name and workload.ltr_enabled:
        if workload.local_enabled:
            task_type = TaskType.ltr_with_msdp_copy
        else:
            task_type = TaskType.ltr_only_copy
        ltr_tasks = [
            Task(
                task_type,
                workload.site_name,
                WindowType.replication,
                workload.replications_per_week(year),
                workload,
                year,
            )
        ]
    for tsk in ltr_tasks:
        tsk.calculate_volume()
        tsk.calculate_resources(appliance_spec, window_sizes)

    return ltr_tasks


def media_tasks_for_workload(
    workload, domain_name, site_name, appliance_spec, window_sizes, year
):
    all_tasks = []
    full_tasks = []
    incremental_tasks = []
    log_backup_tasks = []
    replication_tasks = []

    if site_name == workload.site_name and workload.local_enabled:
        full_tasks = [
            Task(
                TaskType.full_backup,
                workload.site_name,
                WindowType.full,
                workload.fulls_per_week,
                workload,
                year,
            )
        ]
    if site_name == workload.site_name and workload.incrementals_per_week > 0:
        incremental_tasks = [
            Task(
                TaskType.incremental_backup,
                workload.site_name,
                WindowType.incremental,
                workload.incrementals_per_week,
                workload,
                year,
            )
        ]
    if site_name == workload.site_name and workload.log_backups_per_week > 0:
        log_backup_tasks = [
            Task(
                TaskType.log_backup,
                workload.site_name,
                WindowType.incremental,
                workload.log_backups_per_week,
                workload,
                year,
            )
        ]
    if site_name == workload.site_name and workload.dr_enabled:
        replication_tasks = [
            Task(
                TaskType.replication_source,
                workload.site_name,
                WindowType.replication,
                workload.replications_per_week(year),
                workload,
                year,
            )
        ]
    elif site_name == workload.dr_dest and workload.dr_enabled:
        replication_tasks = [
            Task(
                TaskType.replication_target,
                workload.dr_dest,
                WindowType.replication,
                workload.replications_per_week(year),
                workload,
                year,
            )
        ]

    if (
        0 < workload.log_backup_frequency < constants.MINUTES_PER_DAY
        and replication_tasks
        and replication_tasks[0].task_type == TaskType.replication_source
    ):
        logger.info(
            "Setting duplex of workload: %s at site: %s for year: %s",
            workload.name,
            site_name,
            year,
        )
        for task_list in [
            full_tasks,
            incremental_tasks,
            replication_tasks,
            log_backup_tasks,
        ]:
            for t in task_list:
                t.duplex = TaskDuplexType.full

    all_tasks = full_tasks + incremental_tasks + log_backup_tasks + replication_tasks
    for tsk in all_tasks:
        tsk.calculate_volume()
        tsk.calculate_resources(appliance_spec, window_sizes)

    return all_tasks


def primary_tasks_for_workload(
    workload, domain_name, site_name, appliance_spec, window_sizes, year
):
    all_tasks = []
    file_insertion_full_task = []
    file_insertion_incr_task = []
    file_insertion_log_task = []
    image_expiration_task = []
    image_import_task = []
    image_export_task = []
    image_replication_task = []
    catalog_compression_task = []
    catalog_backup_task = []

    backups_per_week = (
        workload.fulls_per_week
        + workload.incrementals_per_week
        + workload.log_backups_per_week
    )
    if domain_name == workload.domain and site_name == workload.site_name:
        file_insertion_full_task = [
            MasterTask(
                MasterTaskType.file_insertion_full,
                workload.site_name,
                WindowType.master,
                workload.fulls_per_week,
                workload,
                year,
            )
        ]
        file_insertion_incr_task = [
            MasterTask(
                MasterTaskType.file_insertion_incr,
                workload.site_name,
                WindowType.master,
                workload.incrementals_per_week,
                workload,
                year,
            )
        ]
        file_insertion_log_task = [
            MasterTask(
                MasterTaskType.file_insertion_log,
                workload.site_name,
                WindowType.master,
                workload.log_backups_per_week,
                workload,
                year,
            )
        ]
        image_expiration_task = [  # noqa: F841
            MasterTask(
                MasterTaskType.image_expiration,
                workload.site_name,
                WindowType.master,
                int(workload.backed_up_images(year) // constants.WEEKS_PER_YEAR),
                workload,
                year,
            )
        ]
        image_import_task = [  # noqa: F841
            MasterTask(
                MasterTaskType.image_import,
                workload.site_name,
                WindowType.master,
                backups_per_week,
                workload,
                year,
            )
        ]
        image_export_task = [  # noqa: F841
            MasterTask(
                MasterTaskType.image_export,
                workload.site_name,
                WindowType.master,
                workload.replications_per_week(year),
                workload,
                year,
            )
        ]
        image_replication_task = [  # noqa: F841
            MasterTask(
                MasterTaskType.image_replication,
                workload.site_name,
                WindowType.master,
                workload.replications_per_week(year),
                workload,
                year,
            )
        ]
        catalog_compression_task = [  # noqa: F841
            MasterTask(
                MasterTaskType.catalog_compression,
                workload.site_name,
                WindowType.master,
                int(workload.backed_up_images(year) // constants.WEEKS_PER_YEAR),
                workload,
                year,
            )
        ]
        catalog_backup_task = [  # noqa: F841
            MasterTask(
                MasterTaskType.catalog_backup,
                workload.site_name,
                WindowType.master,
                int(workload.backed_up_images(year) // constants.WEEKS_PER_YEAR),
                workload,
                year,
            )
        ]

    all_tasks = (
        file_insertion_full_task + file_insertion_incr_task + file_insertion_log_task
    )
    for tsk in all_tasks:
        tsk.calculate_master_volume()
        tsk.calculate_master_resources(appliance_spec, window_sizes)

    return all_tasks
