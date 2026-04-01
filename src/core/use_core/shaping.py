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

import logging
import os.path
import pathlib

from . import constants
from . import run_info
from . import utils


logger = logging.getLogger(__name__)

# RunConfig and ApplianceConfig are utility classes
# that are passed to a RunInfo constructor to hold
# information about the request


class RunConfig:
    def __init__(
        self, workload_type, dedupe_ratio, kb_transferred, num_streams, task, io_duplex
    ):
        self.workload_type = workload_type
        self.dedup_ratio = dedupe_ratio
        self.kb_transferred = kb_transferred
        self.num_streams = num_streams
        self.task = task
        self.io_duplex = io_duplex


class PrimaryRunConfig:
    def __init__(self, workload_type, task, nfiles):
        self.workload_type = workload_type
        self.task = task
        self.nfiles = nfiles


def _get_abs_path(relative_path):
    return pathlib.Path(os.path.dirname(__file__)) / relative_path


def get_data_dir():
    return _get_abs_path(os.path.join("conf", "data"))


def get_model_dir():
    return _get_abs_path(os.path.join("conf", "models"))


class UtilizationValidation(Exception):
    pass


class Resources:
    @staticmethod
    def for_media(
        task_type,
        workload_type,
        workload_size,
        dedupe_ratio,
        number_of_streams,
        appliance,
        io_duplex,
    ):
        res = Resources()

        res.provider = run_info.RunInfo

        res.instance = 0
        res.nic = utils.Size.ZERO
        res.cpu = 0
        res.io = 0
        res.mem = 0
        res.mem_utilization = 0
        res.task_type = task_type
        res.nic_dr = utils.Size.ZERO
        res.nic_cloud = utils.Size.ZERO
        res.weekly_transfer_DR = 0
        res.weekly_transfer_LTR = 0
        rc_task = res.task_type.name
        if rc_task == "ltr_only_copy":
            workload_type = "ma_cc"
        elif rc_task == "ltr_with_msdp_copy":
            workload_type = "ma_msdp_cc"
        elif rc_task in [
            "file_insertion_full",
            "file_insertion_incr",
            "file_insertion_log",
            "image_expiration",
            "image_import",
            "image_export",
            "image_replication",
            "catalog_compression",
            "catalog_backup",
        ]:
            workload_type = "master"

        allowed_streams = appliance.software_safety.concurrent_streams
        if allowed_streams < number_of_streams:
            logger.debug(
                "appliance %s only allows %d streams", appliance.model, allowed_streams
            )
        number_of_streams = min(number_of_streams, allowed_streams)

        res.run_config = RunConfig(
            workload_type,
            dedupe_ratio,
            workload_size // 1000,
            number_of_streams,
            rc_task,
            io_duplex,
        )
        res.appliance_config = appliance

        return res

    @staticmethod
    def for_primary(run_config, appliance_config):
        res = Resources()

        res.provider = run_info.PrimaryRunInfo

        res.run_config = run_config
        res.appliance_config = appliance_config

        res.nic_dr = utils.Size.ZERO
        res.nic_cloud = utils.Size.ZERO

        return res

    def __str__(self):
        return str(self.__class__) + ": " + str(self.__dict__)

    def __repr__(self):
        return str(self.__class__) + ": " + str(self.__dict__)

    def internal_provider(self):
        return self.provider(
            self.run_config,
            self.appliance_config,
            root_data_dir=get_data_dir(),
            model_dir=get_model_dir(),
        )

    def shape(self):
        """ping api return values"""
        r_info = self.internal_provider()
        self.cpu = r_info.cpu_usage() + constants.EXTRA_CPU_TIME
        self.nic = utils.Size.assume_unit(r_info.network_usage(), "MiB")
        self.io = r_info.io_operations()
        self.mem = r_info.memory_usage()

    def calculate_utilizations(self, window_duration):
        self.shape()
        self.window_duration = window_duration
        self.job_duration = self.cpu
        self.cpu_utilization = float(self.cpu / window_duration)
        self.nic_utilization = self.nic / window_duration
        self.absolute_io = utils.Size.assume_unit(
            self.io * constants.SEQUENTIAL_WRITE_IO / window_duration, "KiB"
        )
        self.io_utilization = float(self.io / window_duration)
        self.mem_utilization = self.mem
        self.nic_dr_utilization = self.nic_dr / window_duration
        self.nic_cloud_utilization = self.nic_cloud / window_duration
