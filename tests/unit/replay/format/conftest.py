"""Shared fixtures for the NDJSON replay format tests."""

from __future__ import annotations

import pytest

from asyncviz.replay.format import (
    clear_ndjson_trace,
    reset_format_metrics,
    reset_migration_registry,
    reset_payload_registry,
    set_ndjson_trace_enabled,
)


@pytest.fixture(autouse=True)
def _reset_format_globals() -> None:
    reset_format_metrics()
    reset_migration_registry()
    reset_payload_registry()
    clear_ndjson_trace()
    set_ndjson_trace_enabled(False)
