"""Shared fixtures for backpressure tests."""

from __future__ import annotations

import pytest

from asyncviz.runtime.backpressure import (
    BackpressureConfig,
    EventBackpressureController,
    clear_backpressure_trace,
    reset_backpressure_metrics,
    set_backpressure_trace_enabled,
)


@pytest.fixture(autouse=True)
def _reset_backpressure_globals() -> None:
    reset_backpressure_metrics()
    clear_backpressure_trace()
    set_backpressure_trace_enabled(False)


@pytest.fixture
def fast_config() -> BackpressureConfig:
    # Smaller capacities + zero dwell time so state transitions
    # land synchronously in the tests.
    return BackpressureConfig(
        bus_capacity=10,
        websocket_capacity=8,
        recorder_capacity=20,
        reducer_capacity=6,
        elevated_threshold=0.4,
        overload_threshold=0.7,
        emergency_threshold=0.9,
        degrade_decay=0.1,  # adapts almost instantly
        recovery_hold_ns=0,  # downgrade immediately when below band
    )


@pytest.fixture
def controller(fast_config: BackpressureConfig) -> EventBackpressureController:
    ctrl = EventBackpressureController(fast_config)
    yield ctrl
    ctrl.close()
