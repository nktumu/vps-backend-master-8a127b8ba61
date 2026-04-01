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
from __future__ import annotations
from enum import Enum
from functools import reduce
import json
from typing import Any

from flask.json.provider import JSONProvider

from use_core import utils
from use_core.appliance import NetworkType
from use_core.task import (
    Task,
    MasterTask,
    TaskType,
    MasterTaskType,
    TaskDuplexType,
    WindowType,
)
from use_core.workload import Workload


class ComplexEncoder(json.JSONEncoder):

    def default(self, obj):
        if isinstance(obj, (utils.Size)):
            return obj.__dict__

        if isinstance(obj, (MasterTaskType, TaskType, TaskDuplexType, WindowType)):
            return obj.name

        if isinstance(obj, (Task, MasterTask)):
            if isinstance(obj.workload, Workload):
                obj.workload = obj.workload.name
            return obj.__dict__

        if isinstance(obj, Workload):

            def convert_tuple_keys(orig: dict):
                def immutable(val):
                    return val.name if isinstance(val, Enum) else val

                def tuple_key_to_nested_dict(key: tuple, dict_val: Any):
                    return reduce(
                        lambda acc, val: {immutable(val): acc},
                        reversed(key),
                        dict_val,
                    )

                new_dict = {}
                for key, val in orig.items():
                    if isinstance(key, tuple):
                        new_dict |= tuple_key_to_nested_dict(key, val)
                    else:
                        new_dict |= {key: val}
                return new_dict

            for attribute in [
                "master_yearly_tasks",
                "media_yearly_tasks",
                "ltr_yearly_tasks",
                "m_resources",
                "media_resources",
                "master_yearly_resources",
                "media_yearly_resources",
                "ltr_yearly_resources",
            ]:
                if hasattr(obj, attribute):
                    setattr(obj, attribute, convert_tuple_keys(getattr(obj, attribute)))
            return obj.__dict__

        if isinstance(obj, NetworkType):
            return str(obj)
        # Let the base class default method raise the TypeError
        return super().default(obj)


class CustomJSONProvider(JSONProvider):
    def dumps(self, obj, **kwargs):
        return json.dumps(obj, **kwargs, cls=ComplexEncoder)

    def loads(self, s: str | bytes, **kwargs):
        return json.loads(s, **kwargs)
