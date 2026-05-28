"""Signal fingerprint helper tests."""

from __future__ import annotations

from tests.integration._framework import (
    build_test_context,
    fingerprint_signals,
    lean_test_config,
    signals_match,
)
from tests.integration.integration_models import IntegrationScenarioSpec


def _ctx():
    return build_test_context(
        spec=IntegrationScenarioSpec(name="x", category="runtime"),
        config=lean_test_config(),
    )


def test_empty_streams_match() -> None:
    a = _ctx()
    b = _ctx()
    assert signals_match(a.signals(), b.signals())


def test_identical_streams_match() -> None:
    a = _ctx()
    b = _ctx()
    for ctx in (a, b):
        for index in range(8):
            ctx.record("operation", f"task:{index}")
    assert signals_match(a.signals(), b.signals())


def test_differing_streams_do_not_match() -> None:
    a = _ctx()
    b = _ctx()
    a.record("operation", "alpha")
    b.record("operation", "beta")
    assert not signals_match(a.signals(), b.signals())


def test_fingerprint_records_breakdown() -> None:
    ctx = _ctx()
    ctx.record("operation", "x")
    ctx.record("operation", "y")
    ctx.record("failure", "z")
    fp = fingerprint_signals(ctx.signals())
    assert fp.signal_count == 3
    assert fp.by_kind == {"operation": 2, "failure": 1}
