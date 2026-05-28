"""Framework-level fixtures."""

from __future__ import annotations

import pytest

from tests.integration._framework import (
    clear_integration_trace,
    reset_integration_metrics,
    set_integration_trace_enabled,
)


@pytest.fixture(autouse=True)
def _reset_integration_globals() -> None:
    reset_integration_metrics()
    clear_integration_trace()
    set_integration_trace_enabled(False)
