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

from use_server.services import json_service


def check_schema(schema_name: str, spec: str = None) -> jsonschema.Validator:
    schema = json_service.get_data("schemas", schema_name)

    if isinstance(spec, str) and spec.isidentifier():
        validator = getattr(jsonschema, spec + "Validator")
    else:
        validator = jsonschema.validators.validator_for(schema)
    validator.check_schema(schema)
    return validator


def list_validation_errors(instance: dict, schema_name: str):
    schema_uri = json_service.get_uri("schemas", schema_name)
    schema = json_service.get_data("schemas", schema_name)
    validator_class = jsonschema.validators.validator_for(schema)
    resolver = jsonschema.RefResolver(schema_uri, schema)
    validator = validator_class(schema, resolver=resolver)
    errors = validator.iter_errors(instance=instance)
    return [err.message for err in errors]
