"""Shared fixtures for resilience tests."""

from __future__ import annotations

import pytest

from asyncviz.runtime.resilience import (
    clear_isolation_trace,
    reset_isolation_metrics,
    set_isolation_trace_enabled,
)


@pytest.fixture(autouse=True)
def _reset_resilience_globals() -> None:
    reset_isolation_metrics()
    clear_isolation_trace()
    set_isolation_trace_enabled(False)
