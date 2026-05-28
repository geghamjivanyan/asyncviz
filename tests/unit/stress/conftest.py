"""Shared fixtures for stress-layer tests."""

from __future__ import annotations

import pytest

from asyncviz.stress import (
    clear_stress_trace,
    reset_stress_metrics,
    set_stress_trace_enabled,
)


@pytest.fixture(autouse=True)
def _reset_stress_globals() -> None:
    reset_stress_metrics()
    clear_stress_trace()
    set_stress_trace_enabled(False)
