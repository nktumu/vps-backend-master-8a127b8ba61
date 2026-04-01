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

import pytest

from use_core import timers


@pytest.fixture
def time_ctx():
    return timers.TimerContext()


def test_timer_decorator_no_parenthesis(time_ctx):
    @timers.record_time
    def method():
        return True

    assert method()
    with pytest.raises(TypeError):
        method(time_ctx)
    assert method(time_ctx=time_ctx)


def test_timer_decorator_no_args(time_ctx):
    @timers.record_time()
    def method(time_ctx):
        assert time_ctx.event_stack[-1] == "method"
        return True

    with pytest.raises(TypeError):
        assert method()
    assert method(time_ctx)
    assert method(time_ctx=time_ctx)


def test_timer_decorator(time_ctx):
    @timers.record_time("label")
    def method():
        return True

    assert method()
    with pytest.raises(TypeError):
        method(time_ctx)
    assert method(time_ctx=time_ctx)


def test_timer_decorator_pass_args(time_ctx):
    @timers.record_time("label")
    def method(time_ctx):
        assert time_ctx.event_stack[-1] == "label"
        return True

    with pytest.raises(Exception):
        method()
    assert method(time_ctx)
    assert method(time_ctx=time_ctx)
