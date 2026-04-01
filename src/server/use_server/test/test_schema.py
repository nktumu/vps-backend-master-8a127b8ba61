# VERITAS: Copyright (c) 2021 Veritas Technologies LLC. All rights reserved.
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

import jsonschema
import openapi_schema_validator
import pytest

from use_server.services import json_service


@pytest.mark.parametrize(
    "schema_checker",
    [
        openapi_schema_validator.OAS30Validator,  # uses legacy definition of exclusiveMin/Max
        # openapi_schema_validator.OAS31Validator,  # based on 2020-12, but requires openapi_schema_validator 0.3.0
        # jsonschema.Draft3Validator,               # legacy format for 'required': https://datatracker.ietf.org/doc/html/draft-fge-json-schema-validation-00#appendix-A
        jsonschema.Draft4Validator,  # legacy format for exclusiveMin/Max, but works with 'minimum'/'maximum'
        jsonschema.Draft6Validator,
        jsonschema.Draft7Validator,
        # jsonschema.Draft201909Validator,           # jsonschema 2019-09 validator seems to have a bug with anyOf/allOf
        jsonschema.Draft202012Validator,
    ],
)
@pytest.mark.parametrize("schema_file", json_service.list_all_data("schemas"))
def test_schema(schema_file, schema_checker):
    schema = json_service.get_data("schemas", schema_file)
    schema_checker(schema)


@pytest.mark.parametrize(
    "example_file", json_service.list_all_data("example_responses")
)
def test_examples(example_file, async_size_response_validator):
    example = json_service.get_data("example_responses", example_file)
    async_size_response_validator.validate(example)
