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
import json
import logging
import typing

from . import (
    constants,
    run_info,
    shaping,
    task,
    utils,
)
from .policy import (
    DecimalPolicy,
    DecimalPolicyNoUpperBound,
    NumberPolicy,
)

logger = logging.getLogger(__name__)

MODELS_JSON_PATH = "conf/gurus/models.json"
SKU_JSON_PATH = "conf/gurus/sku.json"

RunConfig = collections.namedtuple(
    "RunConfig", "dedup_ratio kb_transferred num_streams workload_type task io_duplex"
)
ApplianceResources = collections.namedtuple(
    "ApplianceResources",
    [
        "capacity",
        "cpu",
        "memory",
        "memory_overhead",
        "primary_memory_overhead",
        "nw_1g",
        "nw_10g_copper",
        "nw_10g_sfp",
        "nw_25g_sfp",
        "nw_cloud",
        "iops",
    ],
)

SoftwareSafety = collections.namedtuple(
    "SoftwareSafety",
    [
        "jobs_per_day",
        "dbs_15min_rpo",
        "vm_clients",
        "concurrent_streams",
        "files",
        "max_cal_cap",
        "max_universal_share",
        "version",
        "images",
    ],
)


class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, utils.Size):
            obj.__dict__["veritas_class"] = "Size"
            return obj.__dict__
        elif isinstance(obj, NetworkType):
            return {"veritas_class": "NetworkType", "value": obj.value}
        # super() for objects we don't modify
        return super().default(self, obj)


class SiteHints:
    def __init__(
        self,
        disk=utils.Size.from_string("0PiB"),
        dr_dest=False,
        ltr_src=False,
        sizing_flex=False,
    ):
        self.disk = disk
        self.dr_dest = dr_dest
        self.ltr_src = ltr_src
        self.sizing_flex = sizing_flex

    def __repr__(self):
        return f"disk: {self.disk}, dr_dest: {self.dr_dest}, ltr_src: {self.ltr_src}, sizing_flex: {self.sizing_flex}"


class NetworkType(enum.Enum):
    auto = "auto"
    one_gbe = "1GbE"
    ten_gbe_copper = "10GbE Copper"
    ten_gbe_sfp = "10GbE SFP"
    twentyfive_gbe_sfp = "25GbE SFP"

    def __str__(self):
        return self.value

    def is_site_criteria(self):
        return self != NetworkType.auto


class CompatiblityError(Exception):
    pass


class ModelNetworkMatchError(Exception):
    def __init__(self, model, name, network, site_hints, flex_note=False):
        self.model = model
        self.name = name
        self.network = network
        self.site_hints = site_hints
        self.flex_note = flex_note

    def __str__(self):
        result = ["No appliance matching the requested criteria could be found:"]
        if self.name:
            result.append(f"Configuration: [{self.name}]")
        if self.model:
            result.append(f"Model: [{self.model}]")
        result.append(f"Network Type(s): [{', '.join(self.network)}]")
        if self.site_hints.sizing_flex:
            result.append("Flex appliance: Yes")
        else:
            result.append("Flex appliance: No")
        if self.flex_note:
            if self.site_hints.sizing_flex:
                result.append(
                    'If you don\'t need Flex appliances, use the "Sizing Results" button'
                )
            else:
                result.append(
                    'If you need Flex appliances, use the "Flex Sizing" button'
                )
        return "\n".join(result)


class Appliance:
    def __str__(self):
        return str(self.__class__) + ": " + str(self.__dict__)

    def __repr__(self):
        return str(self.__class__) + ": " + str(self.__dict__)

    def set_cloud_bandwidth(self, bw):
        self.cloud_bandwidth = bw

    # default is no safety margins
    def set_max_utilization(self, memory=1.0, cpu=1.0, disk=1.0, nw=1.0, io=1.0):
        self.max_memory = memory
        self.max_cpu = cpu
        self.max_disk = disk
        self.max_nw = nw
        self.max_io = 1.0

    def set_software_safety(
        self,
        jobs_per_day,
        dbs_15min_rpo,
        vm_clients,
        concurrent_streams,
        files,
        images,
        max_cal_cap,
        max_universal_share,
        lun_size=None,
        primary_containers=None,
        msdp_containers=None,
        max_catalog_size=None,
        version="Latest",
    ):
        self.software_safety = SoftwareSafety(
            jobs_per_day=jobs_per_day,
            dbs_15min_rpo=dbs_15min_rpo,
            vm_clients=vm_clients,
            concurrent_streams=concurrent_streams,
            files=files,
            images=images,
            max_cal_cap=max_cal_cap,
            max_universal_share=max_universal_share,
            version=version,
        )
        if max_cal_cap is not None:
            max_cap = utils.Size.assume_unit(max_cal_cap, "TB")
            if self.calculated_capacity > max_cap:
                logger.info(
                    'MSDP CAPPING CAPACITY - Appliance "%s" has calculated capacity %s that is larger than the capping size %s',
                    self.config_name,
                    self.calculated_capacity,
                    max_cap,
                )
                self.calculated_capacity = max_cap
        if lun_size is None:
            self.lun_size = utils.Size.assume_unit(constants.MEDIA_ROUNDUP_TIB, "TiB")
        else:
            self.lun_size = utils.Size.assume_unit(lun_size, "TiB")
        if primary_containers is None:
            self.primary_container_limit = constants.MAXIMUM_CONTAINERS
        else:
            self.primary_container_limit = primary_containers
        if msdp_containers is None:
            self.msdp_container_limit = constants.MAXIMUM_CONTAINERS
        else:
            self.msdp_container_limit = msdp_containers
        if max_catalog_size is None:
            self.max_catalog_size = None
        else:
            self.max_catalog_size = min(
                utils.Size.assume_unit(max_catalog_size, "TiB"),
                self.safe_capacity,
            )
        if max_universal_share is None:
            self.max_universal_share = constants.MAXIMUM_NUMBER_OF_UNIVERSAL_SHARE
        else:
            self.max_universal_share = max_universal_share

    def set_site_version(self, version=constants.DEFAULT_SOFTWARE_VERSION):
        self.site_version = version

    @property
    def catalog_size(self):
        return self.max_catalog_size

    @property
    def disk_capacity(self):
        return self.calculated_capacity

    @property
    def safe_capacity(self):
        return self.calculated_capacity.new_size_scaled(self.max_disk)

    @property
    def safe_filtering_capacity(self):
        return self.filtering_capacity.new_size_scaled(self.max_disk)

    @property
    def flex_capacity(self):
        return self.calculated_capacity_orig

    @property
    def msdp_cloud_capacity(self):
        return utils.Size.assume_unit(constants.MSDP_CLOUD_TOTAL_LSU_PB, "PiB")

    @property
    def msdp_cloud_capacity_recovery_vault(self):
        return utils.Size.assume_unit(constants.MSDP_CLOUD_TOTAL_LSU_PB_RV, "PiB")

    @property
    def msdp_container_size(self):
        streams = self.software_safety.concurrent_streams
        cap_by_streams = utils.Size.assume_unit(
            streams * constants.MSDP_CLOUD_MAX_FILESIZE_MB * 2, "MiB"
        )
        cap_by_lsu = utils.Size.assume_unit(constants.MSDP_CLOUD_MIN_LSU_TB, "TiB")
        return min(max(cap_by_lsu, cap_by_streams), self.safe_capacity)

    @property
    def safe_memory(self):
        return self.memory.new_size_scaled(self.max_memory)

    @property
    def memory_overhead(self):
        return self.resources.memory_overhead

    @property
    def primary_memory_overhead(self):
        return self.resources.primary_memory_overhead

    def total_duration(self, window_sizes: utils.WindowSize):
        return (
            window_sizes.full_backup
            + window_sizes.incremental_backup
            + window_sizes.replication
        )

    def duration(self, window: task.WindowType, window_sizes: utils.WindowSize):
        durations = {
            task.WindowType.full: window_sizes.full_backup,
            task.WindowType.incremental: window_sizes.incremental_backup,
            task.WindowType.replication: window_sizes.replication,
            task.WindowType.master: window_sizes.full_backup
            + window_sizes.incremental_backup,
        }

        return durations[window]

    def safe_duration(
        self, window: task.WindowType, window_sizes: utils.WindowSize
    ) -> float:
        return (
            self.duration(window, window_sizes) * self.max_cpu * constants.FUDGE_CPU_MAX
        )

    @property
    def nw_cloud(self):
        return self.resources.nw_cloud

    @property
    def nw_1g(self):
        return self.resources.nw_1g

    @property
    def safe_nw_1g(self):
        return self.nw_1g.new_size_scaled(self.max_nw * constants.FUDGE_NW_MAX)

    @property
    def nw_10g_copper(self):
        return self.resources.nw_10g_copper

    @property
    def safe_nw_10g_copper(self):
        return self.nw_10g_copper.new_size_scaled(self.max_nw * constants.FUDGE_NW_MAX)

    @property
    def nw_10g_sfp(self):
        return self.resources.nw_10g_sfp

    @property
    def safe_nw_10g_sfp(self):
        return self.nw_10g_sfp.new_size_scaled(self.max_nw * constants.FUDGE_NW_MAX)

    @property
    def nw_25g_sfp(self):
        return self.resources.nw_25g_sfp

    @property
    def safe_nw_25g_sfp(self):
        return self.nw_25g_sfp.new_size_scaled(self.max_nw * constants.FUDGE_NW_MAX)

    @property
    def iops(self):
        return self.resources.iops

    @property
    def safe_iops(self):
        return self.iops * self.max_io * constants.FUDGE_IOPS_MAX

    @property
    def auto_nw_name(self):
        if self.ten_gbe_sfp_io:
            return NetworkType.ten_gbe_sfp
        if self.ten_gbe_copper_io:
            return NetworkType.ten_gbe_copper
        return NetworkType.one_gbe

    @property
    def resources(self):
        if self._cached_resources is None:
            self._cached_resources = self.calculate_resources()
        return self._cached_resources

    def has_deployment_type(self, target_type):
        for each_model in get_model_data("standard"):
            if each_model["model"] != self.model:
                continue
            if (
                "deployment_type" in each_model
                and target_type in each_model["deployment_type"]
            ):
                return True
        return False

    def primary_reservation(self, nmedia):
        for each_model in get_model_data("standard"):
            if each_model["model"] != self.model:
                continue
            logger.debug("examining model %s", each_model["model"])
            prim_res = each_model["primary_reservation"]

            # find best fit
            candidates = [int(n) for n in prim_res if int(n) >= nmedia]
            if candidates:
                key = min(candidates)
            else:
                key = max(int(n) for n in prim_res)
            prim_res = prim_res[str(key)]

            if prim_res["memory"] is None:
                mem = None
            else:
                mem = utils.Size.from_string(prim_res["memory"])
            return {"cpu": prim_res["cpu"], "memory": mem}

    def has_networks(self, required_networks):
        for net_type in required_networks:
            if self.nw_intfs[net_type] == 0:
                return False
        return True

    def calculate_resources(self):
        run_config = RunConfig(
            0.1, 10, 10, "default", "backup", task.TaskDuplexType.half
        )
        ri = run_info.RunInfo(
            run_config,
            self,
            retrain=False,
            root_data_dir=shaping.get_data_dir(),
            model_dir=shaping.get_model_dir(),
        )
        primary_rc = shaping.PrimaryRunConfig("default", "file_insertion", 0)
        primary_res = shaping.Resources.for_primary(primary_rc, self)
        return ApplianceResources(
            capacity=self.calculated_capacity,
            cpu=100,
            memory=self.memory,
            memory_overhead=ri.memory_overhead(),
            primary_memory_overhead=primary_res.internal_provider().memory_overhead(),
            nw_cloud=self.cloud_bandwidth,
            nw_1g=utils.Size.assume_unit(self.one_gbe_io, "MB"),
            nw_10g_copper=utils.Size.assume_unit(self.ten_gbe_copper_io, "MB"),
            nw_10g_sfp=utils.Size.assume_unit(self.ten_gbe_sfp_io, "MB"),
            nw_25g_sfp=utils.Size.assume_unit(self.twentyfive_gbe_sfp_io, "MB"),
            iops=ri.available_iops(),
        )

    @property
    def supported_files(self):
        return self.master_resources["files"]

    @property
    def supported_images(self):
        return self.master_resources["images"]

    @property
    def supported_jobs_per_day(self):
        return self.master_resources["jobs/day"]

    @property
    def display_name(self):
        return f"{self.model} {self.display_capacity}"

    def _similar_except_capacity(self, other):
        if self.model != other.model:
            return False

        if self.memory != other.memory:
            return False

        if self.io_config != other.io_config:
            return False

        return True

    def _copy_safety_to(self, other):
        other.cloud_bandwidth = self.cloud_bandwidth
        other.max_memory = self.max_memory
        other.max_cpu = self.max_cpu
        other.max_disk = self.max_disk
        other.max_nw = self.max_nw
        other.max_io = self.max_io
        s = self.software_safety
        other.set_software_safety(
            jobs_per_day=s.jobs_per_day,
            dbs_15min_rpo=s.dbs_15min_rpo,
            vm_clients=s.vm_clients,
            concurrent_streams=s.concurrent_streams,
            files=s.files,
            images=s.images,
            max_cal_cap=s.max_cal_cap,
            max_universal_share=s.max_universal_share,
            lun_size=self.lun_size.to_float("TiB"),
            primary_containers=self.primary_container_limit,
            msdp_containers=self.msdp_container_limit,
            max_catalog_size=(
                self.max_catalog_size.to_float("TiB") if self.max_catalog_size else None
            ),
            version=s.version,
        )

    def rightsize(self, capacity, flex):
        """
        Return an appliance object that has the same performance
        characteristics as this, except available storage is the minimum
        required for storing the given capacity.
        """
        appls = Appliance.get_all_sku()

        similars = [ap for ap in appls if self._similar_except_capacity(ap)]

        for ap in similars:
            self._copy_safety_to(ap)

        def sort_key(ap):
            if flex:
                return ap.flex_capacity
            else:
                return ap.safe_capacity

        candidates = [ap for ap in similars if capacity <= sort_key(ap)]

        candidates.sort(key=sort_key)
        chosen = candidates[0]

        logger.info(
            "substituting %s for %s with capacity %s",
            chosen.config_name,
            self.config_name,
            capacity,
        )

        return chosen

    @staticmethod
    def from_json(appl_description):
        appl = Appliance()
        appl.config_name = appl_description["name"]
        appl.model = appl_description["model"]

        # These are the models that are fully supported.
        # Other models are sized on a best-effort basis,
        # and a warning is issued.
        appl.performance_supported = appl.model in get_models("performance_supported")
        appl.eosl = appl.model in get_models("eosl")

        # whether storage requirements should be rounded up when
        # appliance is hosting media server containers
        appl.requires_storage_roundup = appl.model in get_models("storage_roundup")

        appl.appliance = appl.model
        appl.shelves = appl_description["shelves"]
        appl.shelf_size = utils.Size.from_dict(appl_description["shelf_size"])
        appl.shelf_capacity = utils.Size.from_dict(appl_description["shelf_capacity"])
        appl.display_capacity = utils.LiteralSize.from_dict(
            appl_description["capacity"]
        )
        appl.calculated_capacity_orig = utils.Size.from_dict(
            appl_description["calculated_capacity"]
        )
        appl.calculated_capacity = utils.Size.from_dict(
            appl_description["calculated_capacity"]
        )
        appl.number_of_appliance_drives = appl_description["number_of_appliance_drives"]
        appl.drives_per_shelf = appl_description["drives_per_shelf"]
        appl.number_of_shelf_drives = appl_description["number_of_shelf_drives"]
        appl.number_of_total_drives = int(appl_description["number_of_total_drives"])
        appl.number_of_calculated_drives = appl_description[
            "number_of_calculated_drives"
        ]
        appl.drive_size = utils.Size.from_dict(appl_description["drive_size"])
        appl.memory = utils.Size.from_dict(appl_description["memory"])
        appl.io_config = appl_description["io_config"]
        appl.one_gbe_count = int(appl_description["one_gbe"]["count"])
        appl.ten_gbe_copper_count = int(appl_description["ten_gbe_copper"]["count"])
        appl.ten_gbe_sfp_count = int(appl_description["ten_gbe_sfp"]["count"])
        appl.twentyfive_gbe_sfp_count = int(
            appl_description["twentyfive_gbe_sfp"]["count"]
        )
        appl.eight_gbfc_count = appl_description["eight_gbfc"]["count"]
        appl.sixteen_gbfc_count = appl_description["sixteen_gbfc"]["count"]
        appl.one_gbe_io = int(appl_description["one_gbe"]["io"])
        appl.ten_gbe_copper_io = int(appl_description["ten_gbe_copper"]["io"])
        appl.ten_gbe_sfp_io = int(appl_description["ten_gbe_sfp"]["io"])
        appl.twentyfive_gbe_sfp_io = int(appl_description["twentyfive_gbe_sfp"]["io"])
        appl.eight_gbfc_io = int(appl_description["eight_gbfc"]["io"])
        appl.sixteen_gbfc_io = int(appl_description["sixteen_gbfc"]["io"])

        appl.nw_intfs = {
            "1GbE": appl.one_gbe_count,
            "10GbE Copper": appl.ten_gbe_copper_count,
            "10GbE SFP": appl.ten_gbe_sfp_count,
            "25GbE SFP": appl.twentyfive_gbe_sfp_count,
        }

        appl.dr_candidate = appl.model not in get_models("NOT_DR_CANDIDATE")

        appl.set_site_version(constants.DEFAULT_SOFTWARE_VERSION)

        # safety margins are zero (utilize full capacity) by default
        # not contained in the JSON
        appl.set_max_utilization(memory=1.0, cpu=1.0, disk=1.0, nw=1.0, io=1.0)
        appl.set_cloud_bandwidth(
            utils.Size.from_ratio(constants.DEFAULT_CC_BW, 8, "GiB")
        )
        appl.max_catalog_size = None
        appl.set_software_safety(
            jobs_per_day=constants.JOBS_PER_DAY,
            dbs_15min_rpo=None,
            vm_clients=constants.VM_CLIENTS,
            concurrent_streams=constants.CONCURRENT_STREAMS,
            files=constants.MAXIMUM_FILES,
            images=constants.MAXIMUM_IMAGES,
            max_cal_cap=None,
            max_universal_share=constants.MAXIMUM_NUMBER_OF_UNIVERSAL_SHARE,
        )

        appl.master_resources = {  # TODO
            "files": None,
            "images": None,
            "jobs/day": None,
        }

        appl._cached_resources = None

        return appl

    @staticmethod
    def get_all_sku(profile="standard"):
        data_path = SKU_JSON_PATH
        if profile != "standard":
            data_path = f"conf/gurus/sku-{profile}.json"
        appliance_descriptions = utils.load_json_resource(data_path)
        return [
            Appliance.from_json(appliance_descriptions[cfg])
            for cfg in appliance_descriptions.keys()
            if not cfg.startswith("labels")
        ]

    @staticmethod
    def match_config(
        config_names,
        safety=None,
        cloud_bandwidth=None,
        site_software_version=constants.DEFAULT_SOFTWARE_VERSION,
    ):
        appliance_descriptions = utils.load_json_resource(SKU_JSON_PATH)
        appls = [
            Appliance.from_json(appliance_descriptions[cfg]) for cfg in config_names
        ]
        for ap in appls:
            if cloud_bandwidth is not None:
                ap.set_cloud_bandwidth(cloud_bandwidth)
            if safety is not None:
                safety_values = safety[ap.model]
                ap.set_max_utilization(
                    memory=safety_values["Memory"],
                    cpu=safety_values["CPU"],
                    disk=safety_values["Capacity"],
                    nw=safety_values["NW"],
                    io=safety_values["IO"],
                )

                ap.set_software_safety(
                    jobs_per_day=safety_values["Jobs_Per_Day"],
                    dbs_15min_rpo=safety_values["DBs@15"],
                    vm_clients=safety_values["VMs"],
                    concurrent_streams=safety_values["Streams"],
                    files=safety_values["Files"],
                    max_cal_cap=safety_values["Max_Cal_Cap"],
                    images=safety_values["Images"],
                    lun_size=safety_values.get("LUN_Size"),
                    primary_containers=safety_values.get("Primary_Containers"),
                    msdp_containers=safety_values.get("MSDP_Containers"),
                    max_catalog_size=safety_values.get("Max_Catalog_Size"),
                    max_universal_share=safety_values.get("Max_Universal_Share"),
                )
        ap.set_site_version(site_software_version)
        return appls

    @staticmethod
    def match_name_network(
        model,
        visible_models,
        name,
        network_types,
        site_hints,
        safety_margins,
    ):
        logger.info(
            "searching for appliance, model restriction: %s,visible models: %s, name restriction: %s, network restrictions: %s, site hints: %s",
            model,
            visible_models,
            name,
            network_types,
            site_hints,
        )
        target_deployment_type = "non-flex"
        if site_hints.sizing_flex:
            target_deployment_type = "flex"
        network_type = dict((net_type, 0) for net_type in network_types)
        appliance_descriptions = [
            appl
            for appl in Appliance.get_all_sku()
            if appl.has_networks(network_types)
            and appl.has_deployment_type(target_deployment_type)
        ]
        for appl in appliance_descriptions:
            safety_values = safety_margins[appl.model]
            appl.set_max_utilization(disk=safety_values["Capacity"])
            max_cal_cap = safety_values["Max_Cal_Cap"]
            if max_cal_cap is not None:
                max_cap = utils.Size.assume_unit(max_cal_cap, "TB")
                appl.calculated_capacity = min(appl.calculated_capacity, max_cap)
            if site_hints.sizing_flex:
                appl.filtering_capacity = appl.calculated_capacity_orig
            else:
                appl.filtering_capacity = appl.calculated_capacity
            max_catalog_size = safety_values["Max_Catalog_Size"]
            appl.max_catalog_size = max_catalog_size or appl.safe_capacity

        appliance_descriptions.sort(key=lambda appl: get_model_preferences(appl.model))
        if name is not None:
            # if a display name is specified, use that and ignore everything else
            cap_appliances = [
                appl for appl in appliance_descriptions if appl.display_name == name
            ]
            if not cap_appliances:
                raise ModelNetworkMatchError(model, name, network_types, site_hints)
        else:  # display name is not specified
            if model is not None:
                candidate_models = set([model])
            else:
                if site_hints.ltr_src:
                    candidate_models = set(
                        get_models_multi(
                            {
                                "performance_supported": True,
                                "eosl": False,
                                "ltr_src": True,
                            }
                        )
                    )
                else:
                    candidate_models = set(
                        get_models_multi(
                            {
                                "performance_supported": True,
                                "eosl": False,
                                "not_dr_dest": False,
                            }
                        )
                    )
                    if not site_hints.dr_dest:
                        non_dr_models = set(
                            get_models_multi(
                                {
                                    "performance_supported": True,
                                    "eosl": False,
                                    "not_dr_dest": True,
                                }
                            )
                        )
                        candidate_models |= non_dr_models
                candidate_models = candidate_models.intersection(visible_models)
            candidate_appliances = [
                appl
                for appl in appliance_descriptions
                if appl.model in candidate_models
            ]
            if not candidate_appliances:
                raise ModelNetworkMatchError(
                    model, name, network_types, site_hints, flex_note=model is not None
                )
            # can we make do with a single appliance of the preferred model?
            max_cap_preferred = [
                appl
                for appl in candidate_appliances
                if appl.model in get_models("PREFERRED_MODEL")
                and appl.safe_capacity > site_hints.disk
            ]
            if max_cap_preferred:
                cap_appliances = max_cap_preferred
            else:
                # skip low-memory appliances for default consideration
                model_memories = collections.defaultdict(set)
                for appl in candidate_appliances:
                    model_memories[appl.model].add(appl.memory)
                min_model_memories = [
                    (model, min(memories)) for model, memories in model_memories.items()
                ]
                model_memory_counts = dict(
                    (model, len(memories)) for model, memories in model_memories.items()
                )
                candidate_appliances = [
                    appl
                    for appl in candidate_appliances
                    if model_memory_counts[appl.model] == 1
                    or (
                        model_memory_counts[appl.model] > 1
                        and (appl.model, appl.memory) not in min_model_memories
                    )
                ]

                max_cap = max(
                    appl.safe_filtering_capacity for appl in candidate_appliances
                )
                max_cap_hinted = [
                    appl.safe_filtering_capacity
                    for appl in candidate_appliances
                    if appl.safe_filtering_capacity > site_hints.disk
                ]
                if max_cap_hinted:
                    required_cap = min(max_cap_hinted)
                else:
                    required_cap = max_cap
                cap_appliances = [
                    appl
                    for appl in candidate_appliances
                    if appl.safe_filtering_capacity == required_cap
                ]

        # Prefer appliances with lower storage capacity.  For
        # appliances with identical available capacity, prefer ones
        # with lower total capacity (these may be non-linearly related
        # if max_cal_cap has been applied).
        cap_appliances.sort(
            key=lambda appl: (appl.safe_capacity, appl.calculated_capacity)
        )

        max_mem = max(appl.memory for appl in cap_appliances)
        max_mem_appliances = [appl for appl in cap_appliances if appl.memory == max_mem]

        net_matched_appliances = []
        for appl in max_mem_appliances:
            tally = 0
            for net in network_type:
                if not appl.nw_intfs[net]:
                    continue

            for net in network_type:
                if network_type[net] > appl.nw_intfs[net]:
                    tally -= 1
                elif network_type[net] < appl.nw_intfs[net]:
                    network_type[net] = appl.nw_intfs[net]
                    net_matched_appliances.clear()
                    tally += 1
                else:
                    tally += 1
            if tally >= (len(network_type) + 1) / 2:
                net_matched_appliances.append(appl)

        if not net_matched_appliances:
            raise ModelNetworkMatchError(model, name, network_types, site_hints)

        chosen = net_matched_appliances[0].config_name
        logger.info("picked appliance %s", chosen)
        return chosen

    # This is a simplified version of `match_name_network` that ignores
    # memory and network.  It is suitable only for Flex scenarios, where
    # we want to allow master server sizing to use all available storage.
    @staticmethod
    def find_management(catalog_size, media_models, safety_margins):
        logger.info(
            "looking for management server, catalog size %s, media models %s",
            catalog_size,
            media_models,
        )
        management_models = get_models("management_capable")
        if len(media_models) == 1 and media_models.issubset(management_models):
            # if there is a unique model for media servers, and that model
            # is marked as management-capable, just use that as the
            # candidate
            candidate_models = media_models
        else:
            candidate_models = management_models

        candidate_appliances = [
            appl for appl in Appliance.get_all_sku() if appl.model in candidate_models
        ]
        for appl in candidate_appliances:
            safety_values = safety_margins[appl.model]
            appl.set_max_utilization(disk=safety_values["Capacity"])
            max_catalog_size = safety_values["Max_Catalog_Size"]
            appl.max_catalog_size = max_catalog_size or appl.safe_capacity

        candidate_appliances.sort(key=lambda appl: get_model_preferences(appl.model))

        max_cap = max(appl.calculated_capacity_orig for appl in candidate_appliances)
        max_cap_hinted = [
            appl.calculated_capacity_orig
            for appl in candidate_appliances
            if appl.calculated_capacity_orig > catalog_size
        ]
        if max_cap_hinted:
            required_cap = min(max_cap_hinted)
        else:
            required_cap = max_cap
        cap_appliances = [
            appl
            for appl in candidate_appliances
            if appl.calculated_capacity_orig == required_cap
        ]

        cap_appliances.sort(
            key=lambda appl: (appl.safe_capacity, appl.calculated_capacity)
        )

        chosen = cap_appliances[0].config_name
        logger.info("picked appliance %s", chosen)
        return chosen

    def ensure_compatible_appliances(self, domain_name, site_name, workloads):
        for w in workloads:
            if (w.domain, w.site_name) != (domain_name, site_name):
                continue

            if w.ltr_enabled and self.model not in get_models(
                "CC_SUPPORTED_APPLIANCES"
            ):
                raise CompatiblityError(
                    f"""The current version of USE is not qualified
    to support Cloud Catalyst with the chosen appliance {self.model}"""
                )


@functools.lru_cache
def get_model_data(profile):
    data_path = MODELS_JSON_PATH
    if profile != "standard":
        data_path = f"conf/gurus/models-{profile}.json"

    return utils.load_json_resource(data_path)


def get_model_values(profile="standard") -> typing.Dict[str, typing.Dict[str, str]]:
    """Return the per-model safety limits."""
    model_values = {}
    for each_model in get_model_data(profile):
        fields = each_model["model_values"]
        each_model_values = {}
        for each_field in fields:
            field_name = each_field["field"]

            (value, policy_name, policy_arg, *rest) = each_field["field_values"]
            if policy_name == "DecimalPolicy":
                pol = DecimalPolicy(policy_arg)
            elif policy_name == "DecimalPolicyNoUpperBound":
                pol = DecimalPolicyNoUpperBound(policy_arg)
            elif policy_name == "NumberPolicy":
                pol = NumberPolicy(policy_arg)
            each_model_values[field_name] = (value, pol, *rest)

        each_model_model = each_model["model"]
        if each_model_model == "Management Server":
            each_model_model = constants.MANAGEMENT_SERVER_DESIGNATION
        model_values[each_model_model] = each_model_values

    return model_values


def get_models_multi(filters, profile="standard"):
    key_src_models = []
    for each_model in get_model_data(profile):
        if each_model["model"] == "Management Server":
            continue
        use_model = True
        for filter_key, expected_value in filters.items():
            if each_model.get(filter_key, False) != expected_value:
                use_model = False
                break
        if use_model:
            key_src_models.append(each_model["model"])
    return key_src_models


def get_models(filter_key, expected_value=True, profile="standard"):
    return get_models_multi({filter_key: expected_value}, profile)


def get_model_preferences(model, profile="standard"):
    for each_model in get_model_data(profile):
        if model == each_model["model"] and "model_pref" in each_model:
            return each_model["model_pref"]
    return -1


def find_primary(media_models, safe_margins=None):
    # if there is a single model throughout the domain, and it is
    # a supported primary, choose that as the primary.  Otherwise,
    # choose the default.
    if len(media_models) > 1:
        return Appliance.match_config(
            [constants.DEFAULT_MASTER_CONFIG],
            safety=safe_margins,
        )[0]

    cfg = constants.PRIMARY_CONFIGS.get(
        media_models.pop(), constants.DEFAULT_MASTER_CONFIG
    )
    return Appliance.match_config([cfg], safety=safe_margins)[0]
