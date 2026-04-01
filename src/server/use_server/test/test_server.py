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

import json
from http import HTTPStatus
from unittest.mock import patch

from flask import jsonify
import pytest

from use_core.appliance import NetworkType
from use_core.packing import FlexSizerResult, SizerContext, SizerResult
from use_core.utils import Size
from use_core.model_basis import get_model_limits
from use_server.server import api
from use_server.tasks import packing_task

api.testing = True
client = api.test_client()

app_safety_margin_url = "/v1/safety-margins"
async_size_url = "/v1/async_size"
size_url = "/v1/size"
sku_url = "/v1/skus"
slp_url = "/v1/slps"
workload_type_url = "/v1/workload-type"


def test_create_update_skus(test_sku_request, test_request_headers):
    response = client.post(
        sku_url,
        data=json.dumps(test_sku_request),
        headers=test_request_headers,
    )
    assert response.status_code == HTTPStatus.NO_CONTENT


def test_get_skus(test_request_headers):
    response = client.get(
        sku_url + "?model=5150&io_config=A",
        headers=test_request_headers,
    )
    resp = json.loads(response.data)
    print(resp)
    assert response.status_code == HTTPStatus.OK
    assert resp[0]["model"]
    assert resp[0]["io_config"]


def test_get_skus_model_filter_only(test_request_headers):
    response = client.get(
        sku_url + "?model=5150",
        headers=test_request_headers,
    )
    resp = json.loads(response.data)
    print(resp)
    assert response.status_code == HTTPStatus.OK
    assert resp[0]["model"]
    assert resp[0]["io_config"]


def test_get_skus_io_config_filter_only(test_request_headers):
    response = client.get(
        sku_url + "?io_config=A",
        headers=test_request_headers,
    )
    resp = json.loads(response.data)
    print(resp)
    assert response.status_code == HTTPStatus.OK
    assert resp[0]["model"]
    assert resp[0]["io_config"]


def test_get_all_skus(test_request_headers):
    response = client.get(
        sku_url,
        headers=test_request_headers,
    )
    resp = json.loads(response.data)
    assert resp
    assert response.status_code == HTTPStatus.OK


def test_get_skus_negative(test_request_headers):
    response = client.get(
        sku_url + "?model=5150&io_config=Z",
        headers=test_request_headers,
    )
    resp = json.loads(response.data)
    print(resp)
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_create_update_slp_route(test_slp_request, test_request_headers):
    response = client.put(
        slp_url + "/testSlp",
        data=json.dumps(test_slp_request),
        headers=test_request_headers,
    )
    assert response.status_code == HTTPStatus.NO_CONTENT


def test_get_slp_route(test_request_headers):
    response = client.get(
        slp_url + "/testSlp",
        headers=test_request_headers,
    )
    assert response.status_code == HTTPStatus.OK
    resp = json.loads(response.data)
    assert resp
    assert resp["name"]
    assert resp["site_name"]
    assert resp["dr_dest"]
    assert resp["dr_dest"][0]
    assert resp["backup_type"]
    assert resp["local_retention"]
    assert resp["local_retention"]["incremental"] >= 0
    assert resp["local_retention"]["weekly_full"] >= 0
    assert resp["local_retention"]["monthly_full"] >= 0
    assert resp["local_retention"]["annual_full"] >= 0
    assert resp["dr_retention"]
    assert resp["dr_retention"]["incremental"] >= 0
    assert resp["dr_retention"]["weekly_full"] >= 0
    assert resp["dr_retention"]["monthly_full"] >= 0
    assert resp["dr_retention"]["annual_full"] >= 0
    assert resp["cloud_retention"]
    assert resp["cloud_retention"]["incremental"] >= 0
    assert resp["cloud_retention"]["weekly_full"] >= 0
    assert resp["cloud_retention"]["monthly_full"] >= 0
    assert resp["cloud_retention"]["annual_full"] >= 0
    assert resp["backup_intervals"]
    assert resp["backup_intervals"]["fulls_per_week"] >= 0
    assert resp["backup_intervals"]["incrementals_per_week"] >= 0
    assert resp["backup_intervals"]["log_backup_interval"] >= 0


def test_get_slp_negative_route(test_request_headers):
    response = client.get(
        slp_url + "/notPresentSlp",
        headers=test_request_headers,
    )
    assert response.status_code == HTTPStatus.NOT_FOUND
    resp = json.loads(response.data)
    assert resp
    assert resp["message"] == "Named policy does not exist"


def test_get_all_slps_route(test_request_headers):
    response = client.get(
        slp_url,
        headers=test_request_headers,
    )
    assert response.status_code == HTTPStatus.OK


@pytest.mark.skip(reason="Retired for stateless container")
def test_delete_slp_route(test_request_headers):
    response = client.delete(
        slp_url + "/testSlp",
        headers=test_request_headers,
    )
    assert response.status_code == HTTPStatus.NO_CONTENT


def test_delete_slp_negative_route(test_request_headers):
    response = client.delete(
        slp_url + "/notPresentSlp",
        headers=test_request_headers,
    )
    assert response.status_code == HTTPStatus.NOT_FOUND
    resp = json.loads(response.data)
    assert resp
    assert resp["message"] == "Named policy does not exist"


def test_create_update_workload_type_route(
    test_workload_type_request, test_request_headers
):
    response = client.put(
        workload_type_url + "/testWorkload",
        data=json.dumps(test_workload_type_request),
        headers=test_request_headers,
    )
    assert response.status_code == HTTPStatus.NO_CONTENT


def test_get_workload_type_route(test_request_headers):
    response = client.get(
        workload_type_url + "/testWorkload",
        headers=test_request_headers,
    )
    assert response.status_code == HTTPStatus.OK
    resp = json.loads(response.data)
    assert resp
    assert resp["addl_full_dedup_rate"] == 0
    assert resp["annual_growth_rate"] == 0
    assert resp["daily_change_rate"] == 0
    assert resp["dedup_rate"] == 0
    assert resp["files_per_channel"] == 0
    assert resp["initial_dedup_rate"] == 0
    assert resp["log_backup_capable"]
    assert resp["name"]
    assert resp["num_channels"] == 0
    assert resp["num_files"] == 0


def test_get_workload_type_negative_route(test_request_headers):
    response = client.get(
        workload_type_url + "/notPresentWorkload",
        headers=test_request_headers,
    )
    assert response.status_code == HTTPStatus.NOT_FOUND
    resp = json.loads(response.data)
    assert resp
    assert resp["message"] == "Named workload type does not exist"


def test_get_all_workload_type_route(test_request_headers):
    response = client.get(
        workload_type_url,
        headers=test_request_headers,
    )
    assert response.status_code == HTTPStatus.OK
    resp = json.loads(response.data)
    assert resp


@pytest.mark.skip(reason="Retired for stateless container")
def test_delete_workload_type_route(test_request_headers):
    response = client.delete(
        workload_type_url + "/testWorkload",
        headers=test_request_headers,
    )
    # expect 'Request fulfilled, nothing follows'
    assert response.status_code == HTTPStatus.NO_CONTENT


def test_delete_workload_type_negative_route(test_request_headers):
    response = client.delete(
        workload_type_url + "/notPresentWorkload",
        headers=test_request_headers,
    )
    # expect 'Nothing matches the given URI'
    assert response.status_code == HTTPStatus.NOT_FOUND
    resp = json.loads(response.data)
    assert resp
    assert resp["message"] == "Named workload type does not exist"


@pytest.mark.parametrize(
    "fixture_name",
    [
        "size_request_data_minimum",
        "size_request_data",
        "size_request_data_with_settings",
    ],
)
@pytest.mark.parametrize(
    "appliance_family",
    ["nba", "flex", pytest.param("flexscale", marks=pytest.mark.skip)],
)
def test_size_route(
    test_request_headers,
    set_appliance_family,
    fixture_name,
    appliance_family,
    size_request_validator,
    size_response_validator,
):
    request_data = set_appliance_family(fixture_name, appliance_family)
    size_request_validator.validate(request_data)

    orig_pack = SizerContext.pack
    result_type = None

    def test_pack(self, *args, **kwargs):
        nonlocal result_type

        result = orig_pack(self, *args, **kwargs)
        result_type = type(result)
        return result

    with patch.object(SizerContext, "pack", test_pack):
        response = client.post(
            size_url, data=json.dumps(request_data), headers=test_request_headers
        )
        size_response_validator.validate(response.json)
        assert response.status_code == HTTPStatus.OK

    if appliance_family == "nba":
        assert result_type == SizerResult
    elif appliance_family == "flex":
        assert result_type == FlexSizerResult

    assert response.status_code == HTTPStatus.OK


def test_size_route_negative(test_request_headers):
    response = client.post(size_url, data=json.dumps({}), headers=test_request_headers)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    # The request entity is correct (thus a 400 (Bad Request) status code is inappropriate)
    # but was unable to process the contained instructions.


def test_size_route_with_missing_workloads(
    test_request_headers,
    size_request_data_with_missing_workloads,
    error_response_validator,
):
    response = client.post(
        size_url,
        data=json.dumps(size_request_data_with_missing_workloads),
        headers=test_request_headers,
    )
    error_response_validator.validate(response.json)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    # The request entity is correct (thus a 400 (Bad Request) status code is inappropriate)
    # but was unable to process the contained instructions.


def test_size_route_with_mixed_appl_family(
    test_request_headers, size_request_data, error_response_validator
):
    request = size_request_data
    request["site_preferences"][0]["appliance_family"] = "flexscale"
    response = client.post(
        size_url,
        data=json.dumps(request),
        headers=test_request_headers,
    )
    error_response_validator.validate(response.json)
    assert response.status_code == HTTPStatus.UNSUPPORTED_MEDIA_TYPE
    # The request entity is correct (thus a 400 (Bad Request) status code is inappropriate)
    # but request contents need a feature that is not supported.
    for err in response.json["errors"]:
        assert err.find("Legacy") == -1


def test_size_route_with_wrong_appl_model(
    test_request_headers, size_request_data, error_response_validator
):
    request = size_request_data
    for i, _ in enumerate(request["site_preferences"]):
        request["site_preferences"][i]["appliance_config"] = "5350-FLEX 1680TB"
        request["site_preferences"][i]["appliance_family"] = "nba"
    response = client.post(
        size_url,
        data=json.dumps(request),
        headers=test_request_headers,
    )
    error_response_validator.validate(response.json)
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    # The request entity is correct (thus a 400 (Bad Request) status code is inappropriate)
    # but request contents need a feature that is not supported.
    for err in response.json["errors"]:
        assert err.find("Legacy") == -1


def test_size_route_with_unsupported_appl_family(
    test_request_headers, size_request_data_minimum, error_response_validator
):
    request = size_request_data_minimum
    request["site_preferences"][0]["appliance_family"] = "flexscale"
    response = client.post(
        size_url,
        data=json.dumps(request),
        headers=test_request_headers,
    )
    error_response_validator.validate(response.json)
    assert response.status_code == HTTPStatus.UNSUPPORTED_MEDIA_TYPE
    # The request entity is correct (thus a 400 (Bad Request) status code is inappropriate)
    # but request contents need a feature that is not supported.
    for err in response.json["errors"]:
        assert err.find("Legacy") == -1


def test_size_route_with_larger_planning_year(
    test_request_headers, size_request_data, error_response_validator
):
    request = size_request_data
    request["horizon"]["planning_year"] = request["horizon"]["num_years"] + 1
    response = client.post(
        size_url,
        data=json.dumps(request),
        headers=test_request_headers,
    )
    error_response_validator.validate(response.json)
    assert response.status_code == HTTPStatus.UNSUPPORTED_MEDIA_TYPE
    # The request entity is correct (thus a 400 (Bad Request) status code is inappropriate)
    # but request contents need a feature that is not supported.
    for err in response.json["errors"]:
        assert err.find("Legacy") == -1


def test_size_route_with_one_missing_site_pref(
    test_request_headers, size_request_data_with_one_missing_site_pref
):
    response = client.post(
        size_url,
        data=json.dumps(size_request_data_with_one_missing_site_pref),
        headers=test_request_headers,
    )
    assert response.status_code == HTTPStatus.OK


def test_size_route_with_missing_site_pref(
    test_request_headers, size_request_data_with_missing_site_pref
):
    response = client.post(
        size_url,
        data=json.dumps(size_request_data_with_missing_site_pref),
        headers=test_request_headers,
    )
    assert response.status_code == HTTPStatus.OK


@pytest.mark.parametrize(
    "test_key",
    [
        "name",
        "preset_type_id",
        "size",
        "number_of_clients",
        "slp",
    ],
)
def test_size_route_with_missing_workload_key(
    test_key, test_request_headers, size_request_data, error_response_validator
):
    request = size_request_data
    request["workloads"][0].pop(test_key)
    response = client.post(
        size_url,
        data=json.dumps(request),
        headers=test_request_headers,
    )
    error_response_validator.validate(response.json)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    # The request entity is correct (thus a 400 (Bad Request) status code is inappropriate)
    # but was unable to process the contained instructions.
    for err in response.json["errors"]:
        assert err.find("Legacy") == -1


@pytest.mark.parametrize(
    "test_key",
    [
        "name",
        "domain",
        "site_name",
        "backup_type",
    ],
)
def test_size_route_with_missing_slp_key(
    test_key, test_request_headers, size_request_data, error_response_validator
):
    request = size_request_data
    request["workloads"][0]["slp"].pop(test_key)
    response = client.post(
        size_url,
        data=json.dumps(request),
        headers=test_request_headers,
    )
    error_response_validator.validate(response.json)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    # The request entity is correct (thus a 400 (Bad Request) status code is inappropriate)
    # but was unable to process the contained instructions.
    for err in response.json["errors"]:
        assert err.find("Legacy") == -1


@pytest.mark.parametrize(
    "test_key", ["incremental", "weekly_full", "monthly_full", "annual_full"]
)
@pytest.mark.parametrize(
    "retention_set", ["local_retention", "dr_retention", "cloud_retention"]
)
def test_size_route_with_missing_retention_key(
    test_key, retention_set, test_request_headers, size_request_data
):
    request = size_request_data
    request["workloads"][0]["slp"][retention_set].pop(test_key)
    response = client.post(
        size_url,
        data=json.dumps(request),
        headers=test_request_headers,
    )
    assert response.status_code == HTTPStatus.OK


@pytest.mark.parametrize(
    "test_key", ["fulls_per_week", "incrementals_per_week", "log_backup_interval"]
)
def test_size_route_with_missing_backup_key(
    test_key, test_request_headers, size_request_data
):
    request = size_request_data
    request["workloads"][0]["slp"]["backup_intervals"].pop(test_key)
    response = client.post(
        size_url,
        data=json.dumps(request),
        headers=test_request_headers,
    )
    assert response.status_code == HTTPStatus.OK


@pytest.mark.parametrize("test_key", ["value", "unit"])
def test_size_route_with_missing_unit_key(
    test_key, test_request_headers, size_request_data, error_response_validator
):
    request = size_request_data
    request["workloads"][0]["size"].pop(test_key)
    response = client.post(
        size_url,
        data=json.dumps(request),
        headers=test_request_headers,
    )
    error_response_validator.validate(response.json)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    # The request entity is correct (thus a 400 (Bad Request) status code is inappropriate)
    # but was unable to process the contained instructions.
    for err in response.json["errors"]:
        assert err.find("Legacy") == -1


def test_healthcheck_route():
    size_url = "/healthcheck"

    response = client.get(size_url)
    assert response.status_code == HTTPStatus.OK
    assert json.loads(response.data)["status"]


def test_create_update_app_safety_margin_route(
    test_safety_margin_request, test_request_headers
):
    response = client.put(
        app_safety_margin_url + "/app-5150",
        data=json.dumps(test_safety_margin_request),
        headers=test_request_headers,
    )
    # expect 'Request fulfilled, nothing follows'
    assert response.status_code == HTTPStatus.NO_CONTENT


def test_get_app_safety_margin_route(test_request_headers):
    response = client.get(
        app_safety_margin_url + "/app-5150",
        headers=test_request_headers,
    )
    assert response.status_code == HTTPStatus.OK
    resp = json.loads(response.data)
    assert resp
    assert resp["Capacity"] >= 50
    assert resp["CPU"] >= 50
    assert resp["NW"] >= 50
    assert resp["IO"] >= 50
    assert resp["Memory"] >= 50
    assert resp["Jobs_Per_Day"]
    assert resp["DBs@15"] >= 0
    assert resp["VMs"] >= 0
    assert resp["Streams"] >= 0
    assert resp["max_files"] >= 0
    assert resp["Max_Cal_Cap"] >= 0


def test_get_app_safety_margin_negative_route(test_request_headers):
    response = client.get(
        app_safety_margin_url + "/notPresentSafetyMargin",
        headers=test_request_headers,
    )
    # expect 'Nothing matches the given URI'
    assert response.status_code == HTTPStatus.NOT_FOUND
    resp = json.loads(response.data)
    assert resp
    assert resp["message"] == "Named appliance safety margin type type does not exist"


def test_get_all_app_safety_margin_route(test_request_headers):
    response = client.get(
        app_safety_margin_url,
        headers=test_request_headers,
    )
    assert response.status_code == HTTPStatus.OK


@pytest.mark.skip(reason="Retired for stateless container")
def test_delete_app_safety_margin_route(test_request_headers):
    response = client.delete(
        app_safety_margin_url + "/app-5150",
        headers=test_request_headers,
    )
    # expect 'Request fulfilled, nothing follows'
    assert response.status_code == HTTPStatus.NO_CONTENT


def test_delete_app_margin_safety_negative_route(test_request_headers):
    response = client.delete(
        app_safety_margin_url + "/notPresentAppSafetyMargin",
        headers=test_request_headers,
    )
    # expect 'Nothing matches the given URI'
    assert response.status_code == HTTPStatus.NOT_FOUND
    resp = json.loads(response.data)
    assert resp
    assert resp["message"] == "Named appliance safety margin type does not exist"


def test_workload_size_adjusted_for_num_clients(
    size_request_data, test_request_headers
):
    expected_sizes = {}
    for wk_input in size_request_data["workloads"]:
        input_size_val = wk_input["size"]["value"]
        input_size_unit = wk_input["size"]["unit"]
        input_num_clients = wk_input["number_of_clients"]
        expected_size = Size.assume_unit(
            input_size_val / input_num_clients, input_size_unit
        )
        expected_sizes[wk_input["name"]] = expected_size

    orig_pack = SizerContext.pack
    ctx_size = {}

    def test_pack(self, *args, **kwargs):
        for wk in self.workloads:
            ctx_size[wk.name] = wk.workload_size
        return orig_pack(self, *args, **kwargs)

    with patch.object(SizerContext, "pack", test_pack):
        response = client.post(
            size_url,
            data=json.dumps(size_request_data),
            headers=test_request_headers,
        )
        assert response.status_code == HTTPStatus.OK

    assert ctx_size == expected_sizes


def test_network_selection_honored(size_request_data, test_request_headers):
    expected_nw = {}
    for wk_input in size_request_data["workloads"]:
        wk_input["slp"]["appliance_frontend_network"] = "25GbE SFP"
        wk_input["slp"]["appliance_dr_network"] = "10GbE SFP"
        wk_input["slp"]["appliance_ltr_network"] = "1GbE"
        expected_nw[wk_input["name"]] = (
            NetworkType.twentyfive_gbe_sfp,
            NetworkType.ten_gbe_sfp,
            NetworkType.one_gbe,
        )

    orig_pack = SizerContext.pack
    ctx_nw = {}

    def test_pack(self, *args, **kwargs):
        for wk in self.workloads:
            ctx_nw[wk.name] = (wk.front_end_nw, wk.dr_nw, wk.ltr_nw)
        return orig_pack(self, *args, **kwargs)

    with patch.object(SizerContext, "pack", test_pack):
        response = client.post(
            size_url,
            data=json.dumps(size_request_data),
            headers=test_request_headers,
        )
        assert response.status_code == HTTPStatus.OK

    assert ctx_nw == expected_nw


@pytest.mark.parametrize(
    "fixture_name",
    [
        "size_request_data_minimum",
        "size_request_data",
        "size_request_data_with_settings",
        "size_request_data_with_settings_recovery_vault",
    ],
)
@pytest.mark.parametrize(
    "appliance_family",
    ["nba", "flex", pytest.param("flexscale", marks=pytest.mark.skip)],
)
def test_async_size_route(
    test_request_headers,
    set_appliance_family,
    fixture_name,
    appliance_family,
    size_request_validator,
    async_size_response_validator,
    mock_celery_app,
):
    request_data = set_appliance_family(fixture_name, appliance_family)
    size_request_validator.validate(request_data)

    post_response = client.post(
        async_size_url, data=json.dumps(request_data), headers=test_request_headers
    )
    async_size_response_validator.validate(post_response.json)
    assert post_response.status_code == HTTPStatus.ACCEPTED

    _, async_mock = mock_celery_app
    task_response = packing_task.solve(*async_mock.call_args[1]["args"])
    async_size_response_validator.validate(jsonify(task_response).json)


def test_safety_margins_honored(size_request_data, test_request_headers):
    safety_margins = {
        "model": "5150",
        "Capacity": 0.7,
        "CPU": 0.7,
        "NW": 0.7,
        "IO": 0.7,
        "Memory": 0.7,
        "Jobs_Per_Day": 1000,
        "DBs@15": 5,
        "VMs": 100,
        "Streams": 8,
        "Primary_Containers": 1,
        "MSDP_Containers": 2,
    }
    expected_safety_margins = get_model_limits()
    expected_safety_margins["5150"].update(safety_margins)

    size_request_data["safety_considerations"] = [safety_margins]

    orig_pack = SizerContext.pack
    ctx = {}

    def test_pack(self, *args, **kwargs):
        ctx["safety_margins"] = self.per_appliance_safety_margins

        return orig_pack(self, *args, **kwargs)

    with patch.object(SizerContext, "pack", test_pack):
        response = client.post(
            size_url,
            data=json.dumps(size_request_data),
            headers=test_request_headers,
        )
        assert response.status_code == HTTPStatus.OK

    assert ctx["safety_margins"] == expected_safety_margins
