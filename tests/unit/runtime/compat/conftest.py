"""Shared fixtures for loop-compat tests."""

from __future__ import annotations

import pytest

from asyncviz.runtime.compat import (
    clear_loop_compat_trace,
    reset_loop_compat_metrics,
    set_loop_compat_trace_enabled,
)


@pytest.fixture(autouse=True)
def _reset_compat_globals() -> None:
    reset_loop_compat_metrics()
    clear_loop_compat_trace()
    set_loop_compat_trace_enabled(False)
