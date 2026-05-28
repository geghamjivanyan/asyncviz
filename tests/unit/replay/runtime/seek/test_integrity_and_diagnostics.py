"""Integrity + diagnostics tests."""

from __future__ import annotations

from asyncviz.replay.runtime.models.runtime_state import VirtualRuntimeState
from asyncviz.replay.runtime.seek import (
    ReplaySeekCoordinator,
    SeekResult,
    check_seek_result,
    clear_seek_trace,
    get_seek_trace,
    set_seek_trace_enabled,
)


def test_integrity_check_passes_for_clean_result() -> None:
    result = SeekResult(
        request_id=1,
        target_sequence=10,
        landed_sequence=10,
        landed_monotonic_ns=1000,
        used_cache=False,
        used_checkpoint=False,
        used_snapshot=False,
        frames_replayed=5,
        latency_ns=100,
    )
    state = VirtualRuntimeState(last_sequence=10, last_monotonic_ns=1000)
    violation = check_seek_result(
        target_sequence=10,
        result=result,
        state=state,
        previous_monotonic_ns=500,
    )
    assert violation is None


def test_integrity_check_flags_exact_only_mismatch() -> None:
    result = SeekResult(
        request_id=1,
        target_sequence=10,
        landed_sequence=11,
        landed_monotonic_ns=1100,
        used_cache=False,
        used_checkpoint=False,
        used_snapshot=False,
        frames_replayed=6,
        latency_ns=100,
    )
    state = VirtualRuntimeState(last_sequence=11)
    violation = check_seek_result(
        target_sequence=10,
        result=result,
        state=state,
        previous_monotonic_ns=0,
        strategy="exact_only",
    )
    assert violation is not None
    assert violation.kind == "sequence_mismatch"


def test_diagnostics_returns_combined_view(
    coordinator: ReplaySeekCoordinator,
) -> None:
    coordinator.seek_to_sequence(5)
    diag = coordinator.diagnostics()
    assert diag.metrics.seeks_completed >= 1
    assert diag.cache.size >= 1
    assert diag.state.state.value == "completed"


def test_tracing_captures_seek_lifecycle(
    coordinator: ReplaySeekCoordinator,
) -> None:
    set_seek_trace_enabled(True)
    try:
        coordinator.seek_to_sequence(5)
        kinds = {entry.kind for entry in get_seek_trace()}
        assert "seek-requested" in kinds
        assert "seek-completed" in kinds
    finally:
        set_seek_trace_enabled(False)
        clear_seek_trace()
