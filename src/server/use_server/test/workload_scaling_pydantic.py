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


from typing import List, Optional
from pydantic import (
    BaseModel,
    ConfigDict,
    PositiveInt,
    PositiveFloat,
    NonNegativeFloat,
    NonNegativeInt,
)


class Size(BaseModel):
    value: NonNegativeFloat
    unit: str


class Retention(BaseModel):
    local: list
    dr: list
    cloud: list


class StorageYearlyMetrics(BaseModel):
    size: PositiveFloat
    site_name: str
    additional_full: NonNegativeFloat
    initial_full: NonNegativeFloat
    incrementals: NonNegativeFloat
    monthly_full: NonNegativeFloat
    annual_full: NonNegativeFloat
    total_full: NonNegativeFloat
    total_current: NonNegativeFloat
    initial_full_pre_dedupe: NonNegativeFloat
    incrementals_pre_dedupe: NonNegativeFloat
    additional_full_pre_dedupe: NonNegativeFloat
    monthly_full_pre_dedupe: NonNegativeFloat
    annual_full_pre_dedupe: NonNegativeFloat
    total_full_pre_dedupe: NonNegativeFloat
    total_current_pre_dedupe: NonNegativeFloat
    worst_case_total: NonNegativeFloat
    year: NonNegativeInt


class YearlyCatalogueSize(BaseModel):
    catalog_size: Size
    catalog_nfiles: NonNegativeInt
    catalog_nimages: NonNegativeInt


class WorkloadScaling(BaseModel):
    """all the capacity values are in KIBs"""

    model_config = ConfigDict(extra="forbid")

    attr: dict
    num_instances: PositiveInt
    name: str
    type: str
    slp_name: str
    workload_isolation: bool
    domain: str
    orig_domain: str
    site_name: str
    front_end_nw: str
    workload_size: PositiveInt
    growth_rate: PositiveFloat
    change_rate: PositiveFloat
    backup_location_policy: str
    dr_dest: Optional[str]
    dr_nw: Optional[str]
    ltr_nw: str
    client_dedup: str
    dedupe_ratio: NonNegativeFloat
    initial_dedupe_ratio: PositiveFloat
    addl_full_dedupe_ratio: PositiveFloat
    fulls_per_week: NonNegativeInt
    log_backup_incremental_level: str
    backup_incremental_level: str
    incrementals_per_week: NonNegativeInt
    log_backup_capable: str
    log_backup_frequency: PositiveInt
    log_backups_per_week: PositiveFloat
    min_size_dup_jobs: Size
    max_size_dup_jobs: Size
    force_small_dup_jobs: NonNegativeInt
    retention: Retention
    files: NonNegativeInt
    files_per_channel: NonNegativeInt
    channels: NonNegativeInt
    number_of_streams: NonNegativeInt
    yearly_sizes: list
    dr_sizes: list
    cloud_sizes: list
    master_yearly_tasks: dict
    media_yearly_tasks: dict
    ltr_yearly_tasks: dict
    m_resources: dict
    media_resources: dict
    master_yearly_resources: dict
    media_yearly_resources: dict
    ltr_yearly_resources: dict
    master_resources: List[StorageYearlyMetrics]
    domain_adjusted: bool
    yearly_catalog_sizes: list
    yearly_files: List[int]


class AsyncSizeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: str
    tasks: list
    workload_results: List[WorkloadScaling]


def schema_validator(json_dict):
    try:
        AsyncSizeResponse(**json_dict)
        return True
    except Exception as e:
        print("Exception occured while validating schema", e)
        return False
