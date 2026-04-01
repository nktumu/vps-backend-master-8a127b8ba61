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

import contextlib
import time
from functools import wraps
from inspect import getargspec


class TimerContext:
    def __init__(self):
        self.event_stack = []
        self.events = {}

    def _event_label(self):
        return " -> ".join(self.event_stack)

    def start(self, event):
        if not self.event_stack or event != self.event_stack[-1]:
            self.event_stack.append(event)
        label = self._event_label()
        self.events[label] = [time.perf_counter()]

    def stop(self, event):
        assert self.event_stack[-1] == event
        label = self._event_label()
        self.events[label].append(time.perf_counter())
        self.event_stack.pop()

    @contextlib.contextmanager
    def record(self, event):
        self.start(event)
        try:
            yield
        finally:
            self.stop(event)

    def report(self):
        summarized_events = []
        for event, times in self.events.items():
            start_time = times[0]
            if len(times) == 1:
                summarized_events.append((start_time, event, "failed"))
            else:
                duration = times[1] - start_time
                summarized_events.append((start_time, event, duration))
        return [
            (event, duration)
            for (start_time, event, duration) in sorted(summarized_events)
        ]


def record_time(*arg):
    """
    Decorator for recording a function's execution time.

    This decorator wraps the function in the provided context manager.
    The decorator can be used as a callable object like '@record_time' or as a function call like '@record_time()'.

    Arguments:
    Accepts an optional string to be used as the log entry's event name.

    Function requirements:
    The decorator will only operate on calls to the function that are passed an object of type TimerContext.
    This object must be passed as either a positional argument called 'time_ctx' in the function's argspec, or
    as a keyword argument 'time_ctx=object_name'.  The keyword argument does not require 'time_ctx' to be the
    function's argspec.
    """

    def _wrapper(func):
        @wraps(func)
        def _record(*args, **kwargs):
            try:
                accepted_args = getargspec(func).args
            except TypeError:
                accepted_args = []

            if "time_ctx" in kwargs.keys():
                time_ctx = kwargs["time_ctx"]
                if "time_ctx" not in accepted_args:
                    kwargs.pop("time_ctx")
            elif (
                "time_ctx" in accepted_args
                and len(args) > accepted_args.index("time_ctx")
                and type(args[accepted_args.index("time_ctx")]) == TimerContext
            ):
                time_ctx = args[accepted_args.index("time_ctx")]
            else:
                return func(*args, **kwargs)

            event = msg if msg is not None else func.__name__
            with time_ctx.record(event):
                return func(*args, **kwargs)

        return _record

    if len(arg) == 1 and callable(arg[0]):
        msg = None
        return _wrapper(arg[0])
    else:
        msg = arg[0] if len(arg) > 0 else None
        return _wrapper
