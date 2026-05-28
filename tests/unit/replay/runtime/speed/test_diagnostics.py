"""Speed diagnostics + tracing tests."""

from __future__ import annotations

from asyncviz.replay.runtime.speed import (
    ReplaySpeedController,
    clear_speed_trace,
    get_speed_trace,
    is_speed_trace_enabled,
    set_speed_trace_enabled,
)


def test_diagnostics_reflects_state_and_history(
    controller: ReplaySpeedController,
) -> None:
    controller.set_speed(2.0)
    controller.set_speed(4.0)
    diag = controller.diagnostics()
    assert diag.metrics.applied >= 2
    assert diag.phase.current_speed == 4.0
    assert len(diag.recent_history) >= 2
    assert diag.profile.default_speed == 1.0


def test_tracing_disabled_by_default() -> None:
    assert not is_speed_trace_enabled()


def test_tracing_captures_lifecycle(
    controller: ReplaySpeedController,
) -> None:
    set_speed_trace_enabled(True)
    try:
        controller.set_speed(2.0)
        controller.increase_speed()
        controller.restore_default()
        kinds = {entry.kind for entry in get_speed_trace()}
        assert "speed-requested" in kinds
        assert "speed-applied" in kinds
        assert "preset-cycled" in kinds
        assert "default-restored" in kinds
    finally:
        set_speed_trace_enabled(False)
        clear_speed_trace()
