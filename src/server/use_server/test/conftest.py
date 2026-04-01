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

from copy import copy, deepcopy
from typing import Type
from unittest.mock import patch

from celery.result import AsyncResult
import jsonschema
import pytest

from use_server.encoders import CustomJSONProvider
from use_server.server import api


@pytest.fixture
def test_request_headers():
    request_headers = {"Content-Type": "application/json"}
    return request_headers


class SizeRequest:
    # Class for building API requests to the /size endpoint

    # All parameters are stored within the object in the same layout as the schema properties.
    # Parameters are only stored as a result of a method, either from the method parameter or required default.
    # .as_dict() response will always fill the minimum workloads and sites if not provided by a method call.

    def __init__(self, num_years: int = 1, planning_year: int = 1, **kwargs):
        self.horizon = {
            "num_years": num_years,
            "planning_year": planning_year,
        }
        for kw, val in kwargs.items():
            setattr(self, kw, val)

    def add_workload(
        self,
        name: str = None,
        preset_type_id: str = "DB2",
        size_gib: int = 1,
        num_clients: int = 1,
        slp_name: str = "default_slp",
        site: str = "default_site",
        domain: str = "default_domain",
        backup_type: str = "Local Only",
        **kwargs,
    ):
        existing_workloads = getattr(self, "workloads", [])
        new_workload = {
            "name": f"Workload_{len(existing_workloads)}" if name is None else name,
            "preset_type_id": preset_type_id,
            "size": {"value": size_gib, "unit": "GiB"},
            "number_of_clients": num_clients,
            "slp": {
                "name": slp_name,
                "site_name": site,
                "domain": domain,
                "backup_type": backup_type,
            },
            **kwargs,
        }
        self.workloads = existing_workloads + [new_workload]
        return self

    def add_site(
        self, domain: str = "default_domain", site_name: str = "default_site", **kwargs
    ):
        existing_sites = getattr(self, "site_preferences", [])
        new_site = {"domain": domain, "site_name": site_name, **kwargs}
        self.site_preferences = existing_sites + [new_site]
        return self

    def add_settings(self, **kwargs):
        self.settings = getattr(self, "settings", {}) | kwargs
        return self

    def as_dict(self):
        clone = copy(self)
        if "workloads" not in vars(self):
            clone.add_workload()
        if "site_preferences" not in vars(self):
            clone.add_site()
        return vars(clone)


@pytest.fixture
def size_request_data():
    req_appliance = {
        "appliance_model": "5150",
        "appliance_config": "5150 15TB",
        "appliance_family": "nba",
    }
    vmware_workload = {
        "preset_type_id": "VMware",
        "size": {"value": 5, "unit": "GiB"},
        "number_of_clients": 20,
        "workload_isolation": False,
        "universal_share": False,
    }
    vmware_slp = {
        "name": "default",
        "dr_dest": ["Slp1"],
        "backup_intervals": {
            "fulls_per_week": 1,
            "incrementals_per_week": 5,
            "log_backup_interval": 15,
        },
        "local_retention": {
            "incremental": 30,
            "weekly_full": 4,
            "monthly_full": 6,
            "annual_full": 0,
        },
        "dr_retention": {
            "incremental": 0,
            "weekly_full": 0,
            "monthly_full": 0,
            "annual_full": 1,
        },
        "cloud_retention": {
            "incremental": 0,
            "weekly_full": 0,
            "monthly_full": 0,
            "annual_full": 0,
        },
        "log_backup_incremental_level": "auto",
        "appliance_ltr_network": "auto",
    }
    return (
        SizeRequest(num_years=5, planning_year=3)
        .add_site(domain="Domain-1", site_name="DC1", **req_appliance)
        .add_site(domain="Domain-2", site_name="DC2", **req_appliance)
        .add_site(domain="Domain-1", site_name="Slp1", **req_appliance)
        .add_site(domain="Domain-2", site_name="Slp1", **req_appliance)
        .add_workload(
            name="DC_20_VMware_A2",
            slp={
                "domain": "Domain-1",
                "site_name": "DC1",
                "backup_type": "Local+DR",
                **vmware_slp,
            },
            **vmware_workload,
        )
        .add_workload(
            name="DC_20_VMware_A2_2",
            slp={
                "domain": "Domain-2",
                "site_name": "DC2",
                "backup_type": "Local+DR+LTR",
                "ltr_dest": "access",
                **vmware_slp,
            },
            **vmware_workload,
        )
        .as_dict()
    )


@pytest.fixture
def size_request_data_with_missing_site_pref(size_request_data):
    new_request = SizeRequest(**size_request_data)
    new_request.site_preferences = new_request.site_preferences[:-2]
    return new_request.as_dict()


@pytest.fixture
def size_request_data_with_one_missing_site_pref(size_request_data):
    new_request = SizeRequest(**size_request_data)
    new_request.site_preferences = new_request.site_preferences[:1]
    return new_request.as_dict()


@pytest.fixture
def size_request_data_with_missing_workloads(size_request_data):
    new_request = copy(size_request_data)
    del new_request["workloads"]
    return new_request


@pytest.fixture
def size_request_data_minimum():
    return SizeRequest().as_dict()


@pytest.fixture
def size_request_data_with_settings(size_request_data):
    return (
        SizeRequest(**size_request_data)
        .add_settings(
            primary_server_sizing=False,
            cloud_target_type="Access",
            display_resource_tip=True,
            **{"worst_case_excess_space_usage_for_msdp-c": 30.00},
        )
        .as_dict()
    )


@pytest.fixture
def size_request_data_with_settings_recovery_vault(size_request_data):
    return (
        SizeRequest(**size_request_data)
        .add_settings(
            primary_server_sizing=False,
            cloud_target_type="recoveryvault",
            display_resource_tip=True,
            **{"worst_case_excess_space_usage_for_msdp-c": 30.00},
        )
        .as_dict()
    )


@pytest.fixture
def set_appliance_family(request):
    def __set_appliance_family(fixture_name, family):
        fixture = deepcopy(request.getfixturevalue(fixture_name))
        fixture["site_preferences"] = [
            s | {"appliance_family": family} for s in fixture["site_preferences"]
        ]
        return fixture

    return __set_appliance_family


@pytest.fixture
def test_sku_request():
    return {
        "add": [
            {
                "name": "test_add_sku2",
                "model": "5250",
                "shelves": 0,
                "calculated_capacity": {"value": 0, "unit": "GiB"},
                "capacity": {"value": 0, "unit": "GiB"},
                "number_of_appliance_drives": 0,
                "drives_per_shelf": 0,
                "number_of_shelf_drives": 0,
                "number_of_total_drives": 0,
                "number_of_calculated_drives": 0,
                "drive_size": {"value": 0, "unit": "GiB"},
                "memory": {"value": 0, "unit": "GiB"},
                "io_config": "B",
                "one_gbe": {"count": 0, "io": 0},
                "ten_gbe_copper": {"count": 0, "io": 0},
                "ten_gbe_sfp": {"count": 0, "io": 0},
                "eight_gbfc": {"count": 0, "io": 0},
                "sixteen_gbfc": {"count": 0, "io": 0},
            },
            {
                "name": "test_add_sku1",
                "model": "5150",
                "shelves": 0,
                "calculated_capacity": {"value": 0, "unit": "GiB"},
                "capacity": {"value": 0, "unit": "GiB"},
                "number_of_appliance_drives": 0,
                "drives_per_shelf": 0,
                "number_of_shelf_drives": 0,
                "number_of_total_drives": 0,
                "number_of_calculated_drives": 0,
                "drive_size": {"value": 0, "unit": "GiB"},
                "memory": {"value": 0, "unit": "GiB"},
                "io_config": "A",
                "one_gbe": {"count": 0, "io": 0},
                "ten_gbe_copper": {"count": 0, "io": 0},
                "ten_gbe_sfp": {"count": 0, "io": 0},
                "eight_gbfc": {"count": 0, "io": 0},
                "sixteen_gbfc": {"count": 0, "io": 0},
            },
            {
                "name": "test_add_sku",
                "model": "5150",
                "shelves": 0,
                "calculated_capacity": {"value": 0, "unit": "GiB"},
                "capacity": {"value": 0, "unit": "GiB"},
                "number_of_appliance_drives": 0,
                "drives_per_shelf": 0,
                "number_of_shelf_drives": 0,
                "number_of_total_drives": 0,
                "number_of_calculated_drives": 0,
                "drive_size": {"value": 0, "unit": "GiB"},
                "memory": {"value": 0, "unit": "GiB"},
                "io_config": "A",
                "one_gbe": {"count": 0, "io": 0},
                "ten_gbe_copper": {"count": 0, "io": 0},
                "ten_gbe_sfp": {"count": 0, "io": 0},
                "eight_gbfc": {"count": 0, "io": 0},
                "sixteen_gbfc": {"count": 0, "io": 0},
            },
        ],
        "remove": ["test_add_sku"],
    }


@pytest.fixture
def test_slp_request():
    return {
        "name": "slp_test",
        "site_name": "string",
        "dr_dest": ["string"],
        "backup_type": "local only",
        "local_retention": {
            "incremental": 0,
            "weekly_full": 0,
            "monthly_full": 0,
            "annual_full": 0,
        },
        "dr_retention": {
            "incremental": 0,
            "weekly_full": 0,
            "monthly_full": 0,
            "annual_full": 0,
        },
        "cloud_retention": {
            "incremental": 0,
            "weekly_full": 0,
            "monthly_full": 0,
            "annual_full": 0,
        },
        "backup_intervals": {
            "fulls_per_week": 0,
            "incrementals_per_week": 0,
            "log_backup_interval": 0,
        },
    }


@pytest.fixture
def test_workload_type_request():
    return {
        "name": "test workload type",
        "annual_growth_rate": 0,
        "daily_change_rate": 0,
        "initial_dedup_rate": 0,
        "dedup_rate": 0,
        "addl_full_dedup_rate": 0,
        "num_files": 0,
        "num_channels": 0,
        "files_per_channel": 0,
        "log_backup_capable": True,
    }


@pytest.fixture
def test_safety_margin_request():
    return {
        "Capacity": 80,
        "CPU": 70,
        "NW": 70,
        "IO": 70,
        "Memory": 70,
        "Jobs_Per_Day": 13000,
        "DBs@15": 0,
        "VMs": 3900,
        "Streams": 195,
        "max_files": 0,
        "Max_Cal_Cap": 0,
    }


def get_schema_validator(
    schema_name: str,
    subschema_path: list = [],
    validator_class: Type[jsonschema.Validator] = None,
) -> jsonschema.Validator:
    """
    Returns a JSON Schema validator object for the named schema

    Required:
    schema_name - string name of schema located in 'json_data/schemas'

    Optional:
    subschema_path - URI path within the schema (as a list). Function will return only this subschema within the file. Example: ['path', 'to', 'subschema', '0']
    validator_class - Overrides the detected validator class, allowing for validating against a different spec version.
    """

    from pathlib import Path
    import json

    folder = "json_data/schemas"
    dest_file = "/".join([folder, schema_name + ".json"])
    uri = Path(dest_file).resolve().as_uri()
    with open(dest_file) as json_file:
        schema = json.load(json_file)
    class_from_file = jsonschema.validators.validator_for(schema)
    resolver = jsonschema.RefResolver(uri, schema)
    if subschema_path:
        for path in subschema_path:
            # URIs for lists have indexes as string, but Python lists need integers
            schema = schema[int(path)] if isinstance(schema, list) else schema[path]
        uri = "/".join([uri + "#"] + subschema_path)
        class_from_file = jsonschema.validators.validator_for(schema, class_from_file)

    validator_class = validator_class or class_from_file
    validator = validator_class(schema, resolver=resolver)
    return validator


@pytest.fixture
def error_response_validator():
    return get_schema_validator(schema_name="util", subschema_path=["$defs", "error"])


@pytest.fixture
def size_response_validator():
    return get_schema_validator(
        schema_name="size_response", subschema_path=["$defs", "success"]
    )


@pytest.fixture
def async_size_response_validator():
    return get_schema_validator(schema_name="async_size_response")


@pytest.fixture
def size_request_validator():
    return get_schema_validator(schema_name="size_request")


@pytest.fixture(autouse=True)
def flask_fixture():
    api.testing = True
    api.json = CustomJSONProvider(api)
    with api.app_context():
        yield api.test_client()


@pytest.fixture
def mock_celery_app():
    with patch("use_server.services.celery_service.app") as app_mock:
        with patch("use_server.tasks.packing_task.solve.apply_async") as async_mock:
            async_mock.return_value = AsyncResult(
                "88888888-4444-4444-4444-cccccccccccc"
            )
            yield (app_mock, async_mock)
