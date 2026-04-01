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
import math
import pathlib
import sqlite3

import pandas as pd
import statsmodels.iolib
from . import constants

logger = logging.getLogger(__name__)
msdp_values = {
    "5150": 0.6,
    "5240": 0.6,
    "5250": 0.6,
    "5260-FLEX": 0.6,
    "5340": 0.6,
    "5350": 0.6,
    "5350-FLEX": 0.6,
    "5360-FLEX": 0.6,
}


class RunInfo:
    """Get (predicted) information about a given run, including CPU and memory usage.

    This class will not work if the /models directory has not yet been populated using
    /build-models.py (which is executed during make publish).

    "Constant" values derived from the data (through the training of the models) can be found in the SQLite database file /models/constants.db.

    ____________________________________________________________________________________



    Interface:
        my_run = RunInfo(run_config: RunConfig,
                         appliance_config: ApplianceConfig,
                         root_data_dir: str = None,
                         model_dir: str = None)
            This creates a new instance of the RunInfo class, corresponding to a run
            specified by `run_config` on an appliance specified by `appliance_config`.

            `run_config` is expected to be an object with member variables...
            - `dedup_ratio`: A float between 0 and 1.
            - `kb_transferred`: A nonnegative integer.
            - `num_streams`: A positive integer.
            - `workload_type`: A string. If its lowercase version is "vmware", VMWare
                               settings will be used.

            `appliance_config` is expected be an object with member variables...
            - `appliance`: A string consisting of four digits, like "5150".

            Use `root_data_dir` and `model_dir` to manually set the data and model
            folder paths, respectively. By default, they will be set to "CWD/conf/data"
            and "CWD/conf/models", where CWD is the current working directory. Most of
            the time, the actual data will be in a subdirectory of root_data_dir
            corresponding to the workload type, such as /path/to/root_data_dir/default.

            Coefficients of the current trained models, in the "c" terms originally
            used to describe the models, can be found in JSON files written to
            the models directory.


        my_run.cpu_usage() -> int
            This returns the predicted CPU usage for this run in seconds. (Imagine the
            CPU is running at full capacity for the number of seconds returned.)


        my_run.io_operations() -> int
            Return the number of Sequential 64K write IOs needed by the run.


        my_run.memory_usage() -> int
            Return the memory usage for this run, not including the overhead.


        my_run.memory_overhead() -> int
            Get the memory overhead for the appliance.


        my_run.network_usage(client_side_dedup: bool = False) -> int
            Return the number of kilobytes moved across the network. `client_side_dedup`
            toggles whether deduplication occurs on the server- or client-side.
    """

    def __init__(
        self,
        run_config,
        appliance_config,
        create_database=False,
        retrain=False,
        root_data_dir: str = None,
        model_dir: str = None,
    ) -> None:
        # Data inputs
        appliance_perf_maps = {
            "5250-FLEX": "5250",
            "5340-FLEX": "5340",
            "5340-HA": "5340",
            "5340-HA-FLEX": "5340",
            "5350-HA-FLEX": "5350-FLEX",
            "5260-FLEX": "5260-FLEX",
            "5360-FLEX": "5360-FLEX",
            "5360-HA-FLEX": "5360-FLEX",
        }

        self.appliance = appliance_perf_maps.get(
            appliance_config.appliance, appliance_config.appliance
        )
        self.site_version = appliance_config.site_version.value
        self.task = run_config.task
        self.workload = run_config.workload_type.lower()
        self.io_duplex = run_config.io_duplex

        if self.workload not in constants.WORKLOAD_TYPES:
            self.workload = "default"

        # Prediction inputs
        self.total_mem = int(appliance_config.memory)
        self.num_disks = appliance_config.number_of_total_drives
        self.dedup_ratio = run_config.dedup_ratio
        self.kb_transferred = run_config.kb_transferred
        self.num_streams = run_config.num_streams

        # Path setup
        py_dir = pathlib.Path(__file__).parent
        self.model_dir = (
            py_dir
            / "conf"
            / "models"
            / self.appliance
            / self.site_version
            / self.workload
        )

        # Model setup
        self.cpu_model = statsmodels.iolib.load_pickle(
            str(self.model_dir / "cpu-model.pkl")
        )
        self.memory_model = statsmodels.iolib.load_pickle(
            str(self.model_dir / "memory-model.pkl")
        )

        # Caching for memory overhead
        self._memory_overhead_non_msdp = None

    def cpu_usage(self) -> int:
        swapout = self._get_swapout()
        # For 5250, we decided to just make swapout have no effect since
        # the coefficient isn't siginificantly different from 0 anyway.
        # Easier to implement it here than in the model.
        if self.appliance == "5250":
            swapout = 0
        return math.ceil(
            self.cpu_model.predict(
                pd.DataFrame(
                    {
                        "dedup_ratio": [self.dedup_ratio],
                        "swapout": [swapout],
                        "kb_transferred": [self.kb_transferred],
                    }
                )
            )[0]
        )

    def io_operations(self) -> int:
        return math.ceil(
            self.network_usage(client_side_dedup=True) / constants.SEQUENTIAL_WRITE_IO
        )

    def memory_overhead(self) -> int:
        if self._memory_overhead_non_msdp is None:
            self.conn = sqlite3.connect(str(self.model_dir.parents[2] / "constants.db"))
            query = f"""select value
                        from constants_table
                        where name = 'memory_overhead_non_msdp' and
                              appliance = '{self.appliance}' and
                              site_version = '{self.site_version}' and
                              workload = '{self.workload}'"""
            self._memory_overhead_non_msdp = math.ceil(
                list(self.conn.execute(query))[0][0]
            )
            self.conn.close()

        msdp = msdp_values[self.appliance] * self.total_mem

        return int(msdp + self._memory_overhead_non_msdp)

    def available_iops(self) -> int:
        # Current IOPS data is for the 5150, which has 4 disks.  For
        # appliances with different number of disks, we make IOPS
        # scale by the number of disks.  Ideally, doubling the number
        # of disks doubles the IOPS.  To keep things potentially
        # adjustable, we make it scale by
        # constants.ADDL_DISK_IOPS_SCALE.

        iops_5150 = 5336 // 64  # 64kB blocks/sec, based on notebooks/bekb.ipynb

        if self.num_disks == 4:
            return iops_5150

        disks_scale = (self.num_disks - 4) / 4
        return int(iops_5150 * (1 + disks_scale * constants.ADDL_DISK_IOPS_SCALE))

    def memory_usage(self) -> int:
        return math.ceil(
            self.memory_model.predict(
                pd.DataFrame({"num_streams": [self.num_streams]})
            )[0]
        )

    def network_usage(self, client_side_dedup: bool = False) -> int:
        if not client_side_dedup:
            return self.kb_transferred
        else:
            return math.ceil(self.kb_transferred * (1 - self.dedup_ratio))

    def _get_swapout(self) -> int:
        if self.workload == "vmware":
            return max(
                self.memory_usage() + self.memory_overhead() - self.total_mem,
                0,
            )
        else:
            return 0


class PrimaryRunInfo:
    def __init__(
        self,
        run_config,
        appliance_config,
        root_data_dir=None,
        model_dir=None,
    ):
        self.run_config = run_config
        self.appliance_config = appliance_config

    def cpu_usage(self):
        return (
            self.run_config.nfiles
            * constants.SECONDS_PER_HOUR
            / constants.FILES_PER_HOUR
        )

    def network_usage(self):
        return 0

    def io_operations(self):
        return 0

    def memory_overhead(self):
        if self.appliance_config.appliance == "5150":
            # We'll only get here if we're targetting a 5150 Flex
            # configuration.  Because of the way the 5150 benchmark
            # was analyzed, the memory overhead is already being
            # accounted for in the media server instance.  So it does
            # not need to be additionally covered here.
            return 0
        else:
            return constants.PRIMARY_MEMORY_OVERHEAD

    def memory_usage(self):
        return constants.PRIMARY_MEMORY_USAGE


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    class MockRunConfig:
        def __init__(
            self,
            dedup_ratio: float,
            kb_transferred: int,
            num_streams: int,
            task: str,
            workload_type: str,
        ) -> None:
            self.dedup_ratio = dedup_ratio
            self.kb_transferred = kb_transferred
            self.num_streams = num_streams
            self.task = task
            self.workload_type = workload_type

    class MockApplianceConfig:
        def __init__(
            self,
            appliance: str,
            site_version: str,
            memory: int,
            number_of_total_drives: int,
        ) -> None:
            self.appliance = appliance
            self.site_version = site_version
            self.memory = memory
            self.number_of_total_drives = number_of_total_drives

    mock_run_config = MockRunConfig(
        dedup_ratio=0.0,
        kb_transferred=1024 * 1024,
        num_streams=3,
        workload_type="VMware",
        task="backup",
    )
    mock_appliance_config = MockApplianceConfig(
        appliance="5250",
        site_version=constants.SoftwareVersion.VER8_2,
        memory=256 * 1024 * 1024,
        number_of_total_drives=4,
    )
    ri = RunInfo(mock_run_config, mock_appliance_config)
    print(ri.cpu_usage())
    print(ri.memory_overhead())
    print(ri.memory_usage())
    print(ri.network_usage())
    print(ri.io_operations())
