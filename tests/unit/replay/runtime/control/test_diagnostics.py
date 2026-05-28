"""Diagnostics + tracing tests."""

from __future__ import annotations

import pytest

from asyncviz.replay.runtime.control import (
    ReplayPlaybackCoordinator,
    clear_coordination_trace,
    get_coordination_trace,
    is_coordination_trace_enabled,
    set_coordination_trace_enabled,
)


@pytest.mark.asyncio
async def test_diagnostics_reflects_phase_and_metrics(
    coordinator: ReplayPlaybackCoordinator,
) -> None:
    pb = coordinator.request_pause()
    coordinator.on_frame_dispatched(sequence=1, monotonic_ns=100)
    await pb.wait(timeout=1.0)
    diag = coordinator.diagnostics()
    assert diag.phase.phase.value == "paused"
    assert diag.metrics.pauses_requested >= 1
    assert diag.metrics.pauses_completed >= 1


@pytest.mark.asyncio
async def test_tracing_captures_lifecycle(
    coordinator: ReplayPlaybackCoordinator,
) -> None:
    set_coordination_trace_enabled(True)
    try:
        pb = coordinator.request_pause()
        coordinator.on_frame_dispatched(sequence=1, monotonic_ns=100)
        await pb.wait(timeout=1.0)
        rb = coordinator.request_resume()
        await rb.wait(timeout=1.0)
        kinds = {entry.kind for entry in get_coordination_trace()}
        assert "pause-requested" in kinds
        assert "pause-completed" in kinds
        assert "resume-requested" in kinds
    finally:
        set_coordination_trace_enabled(False)
        clear_coordination_trace()


def test_trace_disabled_by_default() -> None:
    assert not is_coordination_trace_enabled()
