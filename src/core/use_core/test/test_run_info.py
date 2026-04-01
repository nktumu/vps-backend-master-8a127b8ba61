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

from unittest.mock import patch

import pytest

from use_core import constants
from use_core import run_info
from use_core import utils


class MockRunConfig:
    def __init__(
        self,
        dedup_ratio: float,
        kb_transferred: int,
        num_streams: int,
        workload_type: str,
        task: str,
        io_duplex: str,
    ) -> None:
        self.dedup_ratio = dedup_ratio
        self.kb_transferred = kb_transferred
        self.num_streams = num_streams
        self.workload_type = workload_type
        self.task = task
        self.io_duplex = io_duplex


class MockApplianceConfig:
    def __init__(
        self, appliance: str, site_version: str, memory: int, num_drives: int = 4
    ) -> None:
        self.appliance = appliance
        self.site_version = site_version
        self.number_of_total_drives = num_drives
        self.memory = memory


@pytest.fixture
def ri():
    mock_run_config = MockRunConfig(
        0.47, 1000000, 10, "VMWare", "backup", "TaskDuplexType.half"
    )
    mock_appliance_config = MockApplianceConfig(
        "5150",
        constants.DEFAULT_SOFTWARE_VERSION,
        utils.Size.from_string("64GiB"),
    )
    return run_info.RunInfo(
        mock_run_config,
        mock_appliance_config,
        retrain=True,
        root_data_dir="src/main/python/conf/data",
        model_dir="src/main/python/conf/models",
    )


@pytest.fixture
def ri_with_extra_drives():
    mock_run_config = MockRunConfig(
        0.47, 1000000, 10, "VMWare", "backup", "TaskDuplexType.half"
    )
    mock_appliance_config = MockApplianceConfig(
        "5150",
        constants.DEFAULT_SOFTWARE_VERSION,
        utils.Size.from_string("64GiB"),
        num_drives=16,
    )
    return run_info.RunInfo(
        mock_run_config,
        mock_appliance_config,
        retrain=True,
        root_data_dir="src/main/python/conf/data",
        model_dir="src/main/python/conf/models",
    )


@pytest.fixture
def ri2():
    mock_run_config = MockRunConfig(
        0.93, 1000000, 5, "oracle", "backup", "TaskDuplexType.half"
    )
    mock_appliance_config = MockApplianceConfig(
        "5150",
        constants.DEFAULT_SOFTWARE_VERSION,
        utils.Size.from_string("64GiB"),
    )
    return run_info.RunInfo(
        mock_run_config,
        mock_appliance_config,
        retrain=True,
        root_data_dir="src/main/python/conf/data",
        model_dir="src/main/python/conf/models",
    )


def test_cpu_usage_is_int(ri):
    assert type(ri.cpu_usage()) is int


def test_memory_overhead_is_int(ri):
    assert type(ri.memory_overhead()) is int


def test_memory_usage_is_int(ri):
    assert type(ri.memory_usage()) is int


def test_network_usage_is_int(ri):
    assert type(ri.network_usage()) is int


def test_io_operations_is_int(ri):
    assert type(ri.io_operations()) is int


def test_memory_model_vmware(ri):
    assert ri.memory_usage() == 23_000_000


def test_memory_model_oracle(ri2):
    assert ri2.memory_usage() == 1_500_000


@patch("use_core.constants.ADDL_DISK_IOPS_SCALE", 0.9)
def test_iops_increase_with_disks(ri, ri_with_extra_drives):
    assert ri_with_extra_drives.available_iops() > ri.available_iops()


@patch("use_core.constants.ADDL_DISK_IOPS_SCALE", 0)
def test_iops_scaling_works(ri, ri_with_extra_drives):
    assert ri_with_extra_drives.available_iops() == ri.available_iops()
