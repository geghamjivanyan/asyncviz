from __future__ import annotations

import asyncio

import pytest

from asyncviz.runtime.clock import RuntimeClock, reset_runtime_clock
from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.monitoring.blocking import BlockingSeverity
from asyncviz.runtime.monitoring.blocking.stack_capture import (
    BLOCKING_STACK_CAPTURE_EVENT_TYPE,
    BlockingStackCaptureEngine,
    FilterPolicy,
    StackCaptureConfiguration,
    StackCaptureLimits,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_replay import (
    replay_into_engine,
)

from ._helpers import (
    asyncio_frame,
    build_outcome,
    make_window,
    static_provider,
    user_frame,
)


@pytest.fixture(autouse=True)
def _reset_clock():
    yield
    reset_runtime_clock()


def _build_engine(
    *,
    config: StackCaptureConfiguration | None = None,
    emit_sink: list | None = None,
    frames=None,
) -> BlockingStackCaptureEngine:
    clock = RuntimeClock()
    fp = (
        (lambda: static_provider(*frames))
        if frames is not None
        else (lambda: static_provider(user_frame(), user_frame(function="db_call")))
    )
    return BlockingStackCaptureEngine(
        runtime_clock=clock,
        configuration=config or StackCaptureConfiguration.default(),
        event_emitter=((lambda e: emit_sink.append(e) or True) if emit_sink is not None else None),
        frame_provider_factory=fp,
    )


# ── policy gate ──────────────────────────────────────────────────────────


def test_engine_skips_warning_by_default() -> None:
    engine = _build_engine()
    out = build_outcome(severity=BlockingSeverity.WARNING)
    stack = engine.on_detection(out)
    assert stack is None
    assert engine.metrics_snapshot().captures_skipped_policy == 1


def test_engine_captures_critical_by_default() -> None:
    engine = _build_engine()
    out = build_outcome(severity=BlockingSeverity.CRITICAL, window=make_window())
    stack = engine.on_detection(out)
    assert stack is not None
    assert stack.severity == "CRITICAL"
    assert stack.window_id == make_window().window_id


def test_engine_emits_event_when_emitter_present() -> None:
    sink: list[RuntimeEvent] = []
    engine = _build_engine(emit_sink=sink)
    engine.on_detection(build_outcome(severity=BlockingSeverity.CRITICAL, window=make_window()))
    assert len(sink) == 1
    assert sink[0].event_type == BLOCKING_STACK_CAPTURE_EVENT_TYPE


def test_engine_returns_stack_without_emitter_too() -> None:
    """No bus wired? Still returns the capture for in-process consumers."""
    engine = _build_engine(emit_sink=None)
    stack = engine.on_detection(build_outcome(severity=BlockingSeverity.CRITICAL))
    assert stack is not None
    assert engine.statistics_snapshot().captures_total == 1


# ── frame content ────────────────────────────────────────────────────────


def test_engine_filters_internal_frames() -> None:
    engine = _build_engine(
        frames=[user_frame(function="user"), asyncio_frame()],
    )
    stack = engine.on_detection(build_outcome(severity=BlockingSeverity.CRITICAL))
    assert stack is not None
    assert stack.filtered_count == 1
    assert [f.function for f in stack.frames] == ["user"]


def test_engine_preserves_internal_frames_when_opted_in() -> None:
    config = StackCaptureConfiguration(
        min_severity=BlockingSeverity.CRITICAL,
        filters=FilterPolicy(
            module_prefixes=("asyncio",),
            include_internal_frames=True,
        ),
    )
    engine = _build_engine(config=config, frames=[user_frame(), asyncio_frame()])
    stack = engine.on_detection(build_outcome(severity=BlockingSeverity.CRITICAL))
    assert stack is not None
    assert len(stack.frames) == 2


# ── capture cap ──────────────────────────────────────────────────────────


def test_per_window_cap_enforced() -> None:
    config = StackCaptureConfiguration(
        min_severity=BlockingSeverity.CRITICAL,
        max_captures_per_window=2,
    )
    engine = _build_engine(config=config)
    win = make_window()
    captured = [
        engine.on_detection(build_outcome(severity=BlockingSeverity.CRITICAL, window=win, index=i))
        for i in range(5)
    ]
    actual = [c for c in captured if c is not None]
    assert len(actual) == 2


def test_freeze_bypasses_cap() -> None:
    config = StackCaptureConfiguration(
        min_severity=BlockingSeverity.CRITICAL,
        max_captures_per_window=1,
    )
    engine = _build_engine(config=config)
    win = make_window()
    engine.on_detection(build_outcome(severity=BlockingSeverity.CRITICAL, window=win))
    freeze_stack = engine.on_detection(
        build_outcome(severity=BlockingSeverity.FREEZE, window=win, index=1)
    )
    assert freeze_stack is not None
    assert freeze_stack.trigger == "freeze"


# ── manual capture ──────────────────────────────────────────────────────


def test_manual_capture_bypasses_policy() -> None:
    engine = _build_engine()
    stack = engine.capture_manual(trigger="user_request")
    assert stack is not None
    assert stack.trigger == "user_request"


def test_manual_capture_returns_none_when_disabled() -> None:
    engine = _build_engine(config=StackCaptureConfiguration(enabled=False))
    assert engine.capture_manual() is None


# ── reentry ─────────────────────────────────────────────────────────────


def test_reentry_blocked_via_listener() -> None:
    """A listener that triggers capture on capture must not recurse."""
    engine = _build_engine()

    def recursing(stack):
        # Try to trigger another capture from within the listener.
        engine.capture_manual(trigger="recursive")

    engine.subscribe(recursing)
    stack = engine.on_detection(build_outcome(severity=BlockingSeverity.CRITICAL))
    assert stack is not None
    # The recursive attempt should have been blocked by the re-entry guard.
    metrics = engine.metrics_snapshot()
    assert metrics.captures_skipped_reentry >= 1


def test_listener_exception_does_not_break_pipeline() -> None:
    engine = _build_engine()
    engine.subscribe(lambda s: (_ for _ in ()).throw(RuntimeError("listener bug")))
    stack = engine.on_detection(build_outcome(severity=BlockingSeverity.CRITICAL))
    assert stack is not None
    assert engine.metrics_snapshot().handler_failures >= 1


# ── sampler / emitter exception isolation ───────────────────────────────


def test_sampler_exception_does_not_raise() -> None:
    def bad_factory():
        raise RuntimeError("provider crashed")

    clock = RuntimeClock()
    engine = BlockingStackCaptureEngine(
        runtime_clock=clock,
        configuration=StackCaptureConfiguration(),
        event_emitter=None,
        frame_provider_factory=bad_factory,
    )
    stack = engine.on_detection(build_outcome(severity=BlockingSeverity.CRITICAL))
    assert stack is None
    assert engine.metrics_snapshot().sampler_failures == 1


def test_emitter_exception_does_not_break_pipeline() -> None:
    def bad_emit(e):
        raise RuntimeError("emit crashed")

    clock = RuntimeClock()
    engine = BlockingStackCaptureEngine(
        runtime_clock=clock,
        configuration=StackCaptureConfiguration(),
        event_emitter=bad_emit,
        frame_provider_factory=lambda: static_provider(user_frame()),
    )
    stack = engine.on_detection(build_outcome(severity=BlockingSeverity.CRITICAL))
    assert stack is None  # emit failed → returned None
    assert engine.metrics_snapshot().emitter_failures == 1


# ── backpressure ────────────────────────────────────────────────────────


def test_backpressure_cap_zero_means_uncapped() -> None:
    config = StackCaptureConfiguration(max_pending_events=0)
    sink: list[RuntimeEvent] = []
    engine = _build_engine(config=config, emit_sink=sink)
    for i in range(5):
        engine.on_detection(
            build_outcome(severity=BlockingSeverity.FREEZE, window=make_window(), index=i)
        )
    assert len(sink) == 5


# ── replay determinism ─────────────────────────────────────────────────


def test_two_engines_produce_identical_recent_captures_on_same_outcomes() -> None:
    """Engine pipeline is deterministic on its input outcomes.

    We strip runtime_id + capture_id + monotonic_ns (clock-derived) and
    compare the rest. This proves that *given the same outcomes and the
    same frame provider*, the engine produces the same content.
    """
    config = StackCaptureConfiguration(min_severity=BlockingSeverity.CRITICAL)
    outcomes = [
        build_outcome(severity=BlockingSeverity.CRITICAL, window=make_window(), index=0),
        build_outcome(severity=BlockingSeverity.FREEZE, window=make_window(), index=1),
    ]

    def run() -> list[dict]:
        engine = _build_engine(config=config)
        replay_into_engine(engine, outcomes)
        recents = engine.snapshot().recent_captures
        # Strip non-deterministic identity fields.
        out = []
        for c in recents:
            d = c.to_dict()
            d.pop("capture_id")
            d.pop("runtime_id")
            d.pop("monotonic_ns")
            d.pop("thread_id")
            d["task"].pop("task_id", None)
            out.append(d)
        return out

    a = run()
    b = run()
    assert a == b


# ── reconfigure ─────────────────────────────────────────────────────────


def test_reconfigure_swaps_policy_atomically() -> None:
    engine = _build_engine(
        config=StackCaptureConfiguration(min_severity=BlockingSeverity.CRITICAL),
    )
    # Initial: WARNING below min → skipped.
    assert engine.on_detection(build_outcome(severity=BlockingSeverity.WARNING)) is None
    engine.reconfigure(
        StackCaptureConfiguration(
            min_severity=BlockingSeverity.WARNING,
            capture_warning=True,
        )
    )
    stack = engine.on_detection(build_outcome(severity=BlockingSeverity.WARNING, index=1))
    assert stack is not None
    assert engine.metrics_snapshot().reconfigurations == 1


def test_reconfigure_rebuilds_sampler_when_limits_change() -> None:
    engine = _build_engine()
    new_limits = StackCaptureLimits(max_depth=2, capture_code_context=False)
    engine.reconfigure(
        StackCaptureConfiguration(min_severity=BlockingSeverity.CRITICAL, limits=new_limits)
    )
    engine_with_many = BlockingStackCaptureEngine(
        runtime_clock=engine._runtime_clock,
        configuration=engine.configuration,
        frame_provider_factory=lambda: static_provider(
            user_frame(function="a"),
            user_frame(function="b"),
            user_frame(function="c"),
            user_frame(function="d"),
        ),
    )
    stack = engine_with_many.on_detection(build_outcome(severity=BlockingSeverity.CRITICAL))
    assert stack is not None
    assert len(stack.frames) == 2


# ── lifecycle ───────────────────────────────────────────────────────────


async def test_start_and_stop_cleanly() -> None:
    engine = _build_engine()
    await engine.start()
    assert engine.is_running is True
    await engine.stop()
    assert engine.state == "stopped"


async def test_double_start_idempotent() -> None:
    engine = _build_engine()
    await engine.start()
    await engine.start()
    assert engine.is_running is True
    await engine.stop()


async def test_stop_before_start_is_safe() -> None:
    engine = _build_engine()
    await engine.stop()
    assert engine.state == "stopped"


# ── snapshots ───────────────────────────────────────────────────────────


def test_snapshot_carries_all_sections() -> None:
    engine = _build_engine()
    engine.on_detection(build_outcome(severity=BlockingSeverity.CRITICAL))
    snap = engine.snapshot()
    d = snap.to_dict()
    for key in (
        "runtime_id",
        "state",
        "generated_at_monotonic_ns",
        "configuration",
        "statistics",
        "metrics",
        "recent_captures",
    ):
        assert key in d


def test_diagnostics_snapshot_includes_trace_when_enabled() -> None:
    engine = _build_engine(
        config=StackCaptureConfiguration(
            min_severity=BlockingSeverity.CRITICAL, trace_enabled=True
        ),
    )
    engine.on_detection(build_outcome(severity=BlockingSeverity.CRITICAL))
    diag = engine.diagnostics_snapshot()
    assert diag.trace_enabled is True
    assert len(diag.trace_records) >= 1


def test_diagnostics_snapshot_to_dict_is_json_safe() -> None:
    import json

    engine = _build_engine(
        config=StackCaptureConfiguration(
            min_severity=BlockingSeverity.CRITICAL, trace_enabled=True
        ),
    )
    engine.on_detection(build_outcome(severity=BlockingSeverity.CRITICAL))
    json.dumps(engine.diagnostics_snapshot().to_dict())


# ── detector binding ────────────────────────────────────────────────────


async def test_bind_to_detector_routes_outcomes() -> None:
    from asyncviz.runtime.monitoring.blocking import (
        BlockingDetectorConfiguration,
        BlockingThresholdDetector,
        BlockingThresholdPolicy,
    )
    from asyncviz.runtime.monitoring.event_loop.lag_measurement import calculate_lag
    from asyncviz.runtime.monitoring.event_loop.lag_thresholds import LagThresholds

    clock = RuntimeClock()
    thresholds = LagThresholds(warning_seconds=0.001, critical_seconds=0.01, freeze_seconds=0.1)
    detector = BlockingThresholdDetector(
        runtime_clock=clock,
        configuration=BlockingDetectorConfiguration(
            cooldown_warning_ns=0,
            cooldown_critical_ns=0,
            thresholds=BlockingThresholdPolicy(escalation_warning_threshold=100),
        ),
    )
    engine = _build_engine()
    sub_id = engine.bind_to_detector(detector)
    assert sub_id is not None

    # Feed a CRITICAL measurement; the detector forwards to the engine.
    m = calculate_lag(
        scheduled_ns=0,
        actual_ns=50_000_000,
        interval_ns=1_000_000,
        sample_index=0,
        runtime_id="r",
    )
    e = thresholds.evaluate(m.lag_ns)
    detector.process(m, e)
    await asyncio.sleep(0)  # flush
    snap = engine.snapshot()
    assert snap.metrics.captures_attempted >= 1


def test_unbind_idempotent() -> None:
    from asyncviz.runtime.monitoring.blocking import BlockingThresholdDetector

    clock = RuntimeClock()
    detector = BlockingThresholdDetector(runtime_clock=clock)
    engine = _build_engine()
    engine.bind_to_detector(detector)
    assert engine.unbind_from_detector() is True
    assert engine.unbind_from_detector() is False
