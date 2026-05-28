from __future__ import annotations

import asyncio

import pytest

from asyncviz.runtime.clock import RuntimeClock, reset_runtime_clock
from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.monitoring.blocking import BlockingSeverity
from asyncviz.runtime.warnings.blocking import (
    BLOCKING_WARNING_ACTIVE_EVENT_TYPE,
    BLOCKING_WARNING_ESCALATED_EVENT_TYPE,
    BLOCKING_WARNING_EXPIRED_EVENT_TYPE,
    BLOCKING_WARNING_OPENED_EVENT_TYPE,
    BLOCKING_WARNING_RECOVERED_EVENT_TYPE,
    BlockingWarningConfiguration,
    BlockingWarningEmitter,
    BlockingWarningEmitterState,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_replay import (
    replay_into_emitter,
)
from asyncviz.runtime.warnings.blocking.utils import (
    build_synthetic_capture,
    build_synthetic_outcome,
    build_synthetic_window,
)


@pytest.fixture(autouse=True)
def _reset_clock():
    yield
    reset_runtime_clock()


def _build_emitter(
    *,
    config: BlockingWarningConfiguration | None = None,
    sink: list | None = None,
) -> BlockingWarningEmitter:
    clock = RuntimeClock()
    emitter = BlockingWarningEmitter(
        runtime_clock=clock,
        configuration=config or BlockingWarningConfiguration.default(),
        event_emitter=((lambda e: sink.append(e) or True) if sink is not None else None),
    )
    return emitter


# ── lifecycle ───────────────────────────────────────────────────────────


def test_normal_severity_outcome_does_not_open_group() -> None:
    sink: list[RuntimeEvent] = []
    emitter = _build_emitter(sink=sink)
    emitter.on_detection(build_synthetic_outcome(severity=BlockingSeverity.NONE))
    assert emitter.metrics_snapshot().groups_opened == 0
    assert sink == []


def test_critical_outcome_opens_group_and_emits_opened_event() -> None:
    sink: list[RuntimeEvent] = []
    emitter = _build_emitter(sink=sink)
    emitter.on_detection(
        build_synthetic_outcome(
            severity=BlockingSeverity.CRITICAL,
            window=build_synthetic_window(),
        )
    )
    assert len(sink) == 1
    assert sink[0].event_type == BLOCKING_WARNING_OPENED_EVENT_TYPE
    assert emitter.metrics_snapshot().groups_opened == 1


def test_escalation_emits_escalated_event() -> None:
    sink: list[RuntimeEvent] = []
    emitter = _build_emitter(sink=sink)
    win = build_synthetic_window()
    emitter.on_detection(
        build_synthetic_outcome(severity=BlockingSeverity.CRITICAL, window=win, scheduled_ns=0)
    )
    emitter.on_detection(
        build_synthetic_outcome(
            severity=BlockingSeverity.FREEZE,
            window=win,
            scheduled_ns=100,
            escalated=True,
            escalation_from=BlockingSeverity.CRITICAL,
            escalation_to=BlockingSeverity.FREEZE,
        )
    )
    types = [e.event_type for e in sink]
    assert types == [
        BLOCKING_WARNING_OPENED_EVENT_TYPE,
        BLOCKING_WARNING_ESCALATED_EVENT_TYPE,
    ]


def test_repeat_active_refresh_is_rate_limited_by_dedup() -> None:
    """Default active cooldown is 250ms; five quick refreshes → one passes."""
    sink: list[RuntimeEvent] = []
    emitter = _build_emitter(sink=sink)
    win = build_synthetic_window()
    emitter.on_detection(
        build_synthetic_outcome(severity=BlockingSeverity.CRITICAL, window=win, scheduled_ns=0)
    )
    # Five CRITICAL refreshes within microseconds — the first establishes
    # the cooldown anchor and the remaining four are suppressed.
    for i in range(5):
        emitter.on_detection(
            build_synthetic_outcome(
                severity=BlockingSeverity.CRITICAL,
                window=win,
                scheduled_ns=1_000 * (i + 1),
            )
        )
    active_count = sum(1 for e in sink if e.event_type == BLOCKING_WARNING_ACTIVE_EVENT_TYPE)
    assert active_count == 1
    assert emitter.metrics_snapshot().suppressed_by_dedup >= 4


def test_active_after_cooldown_window_emits_again() -> None:
    sink: list[RuntimeEvent] = []
    emitter = _build_emitter(
        sink=sink,
        config=BlockingWarningConfiguration(
            min_severity=BlockingSeverity.CRITICAL,
            active_cooldown_ns=1_000,  # 1µs to keep deterministic
        ),
    )
    win = build_synthetic_window()
    emitter.on_detection(
        build_synthetic_outcome(severity=BlockingSeverity.CRITICAL, window=win, scheduled_ns=0)
    )
    emitter.on_detection(
        build_synthetic_outcome(severity=BlockingSeverity.CRITICAL, window=win, scheduled_ns=10)
    )
    # Wait beyond cooldown (scheduled_ns advances past 1µs of lag)
    emitter.on_detection(
        build_synthetic_outcome(
            severity=BlockingSeverity.CRITICAL, window=win, scheduled_ns=2_000_000
        )
    )
    active_count = sum(1 for e in sink if e.event_type == BLOCKING_WARNING_ACTIVE_EVENT_TYPE)
    assert active_count >= 1


def test_window_close_emits_recovered_event() -> None:
    sink: list[RuntimeEvent] = []
    emitter = _build_emitter(sink=sink)
    win = build_synthetic_window()
    emitter.on_detection(
        build_synthetic_outcome(severity=BlockingSeverity.CRITICAL, window=win, scheduled_ns=0)
    )
    closed = build_synthetic_window(violation_count=3)
    emitter.on_detection(
        build_synthetic_outcome(
            severity=BlockingSeverity.NONE,
            lag_ns=0,
            scheduled_ns=1_000_000_000,
            closed_window=closed,
        )
    )
    types = [e.event_type for e in sink]
    assert BLOCKING_WARNING_RECOVERED_EVENT_TYPE in types
    assert emitter.metrics_snapshot().groups_recovered == 1


def test_recovered_group_does_not_accept_new_observations() -> None:
    """A NONE-severity sample arriving after recovery doesn't refresh the group."""
    sink: list[RuntimeEvent] = []
    emitter = _build_emitter(sink=sink)
    win = build_synthetic_window()
    emitter.on_detection(
        build_synthetic_outcome(severity=BlockingSeverity.CRITICAL, window=win, scheduled_ns=0)
    )
    closed = build_synthetic_window()
    emitter.on_detection(
        build_synthetic_outcome(
            severity=BlockingSeverity.NONE, lag_ns=0, scheduled_ns=1, closed_window=closed
        )
    )
    # After recovery — another CRITICAL on the same window. Since the
    # window already closed in our synthetic flow, this would re-open
    # if anything; here we feed NONE again which should be a no-op.
    emitter.on_detection(
        build_synthetic_outcome(
            severity=BlockingSeverity.NONE, lag_ns=0, scheduled_ns=2, closed_window=closed
        )
    )
    types = [e.event_type for e in sink]
    assert types.count(BLOCKING_WARNING_RECOVERED_EVENT_TYPE) == 1


# ── correlation ─────────────────────────────────────────────────────────


def test_capture_correlation_attaches_to_active_group() -> None:
    emitter = _build_emitter()
    win = build_synthetic_window()
    emitter.on_detection(
        build_synthetic_outcome(severity=BlockingSeverity.CRITICAL, window=win, scheduled_ns=0)
    )
    cap = build_synthetic_capture(window_id=win.window_id, capture_id=42, coroutine_name="myapp.f")
    matched = emitter.on_capture(cap)
    assert matched is True
    snap = emitter.snapshot()
    assert snap.active_groups[0].capture_ids == (42,)
    assert snap.active_groups[0].coroutine_name == "myapp.f"


def test_capture_without_matching_group_is_uncorrelated() -> None:
    emitter = _build_emitter()
    cap = build_synthetic_capture(window_id="non-existent")
    matched = emitter.on_capture(cap)
    assert matched is False
    assert emitter.metrics_snapshot().captures_uncorrelated == 1


def test_capture_without_window_is_ignored() -> None:
    emitter = _build_emitter()
    cap = build_synthetic_capture(window_id=None)
    matched = emitter.on_capture(cap)
    assert matched is False


# ── expiration ──────────────────────────────────────────────────────────


def test_sweep_expirations_promotes_recovered_groups_past_ttl() -> None:
    sink: list[RuntimeEvent] = []
    config = BlockingWarningConfiguration(
        min_severity=BlockingSeverity.CRITICAL,
        expiration_ttl_ns=1_000,
    )
    emitter = _build_emitter(sink=sink, config=config)
    win = build_synthetic_window()
    emitter.on_detection(
        build_synthetic_outcome(severity=BlockingSeverity.CRITICAL, window=win, scheduled_ns=0)
    )
    closed = build_synthetic_window()
    emitter.on_detection(
        build_synthetic_outcome(
            severity=BlockingSeverity.NONE, lag_ns=0, scheduled_ns=100, closed_window=closed
        )
    )
    # Sweep at a far-future time → expire.
    expired = emitter.sweep_expirations(now_monotonic_ns=10_000_000_000)
    assert expired == 1
    types = [e.event_type for e in sink]
    assert BLOCKING_WARNING_EXPIRED_EVENT_TYPE in types


def test_sweep_does_not_expire_active_groups() -> None:
    emitter = _build_emitter()
    win = build_synthetic_window()
    emitter.on_detection(
        build_synthetic_outcome(severity=BlockingSeverity.CRITICAL, window=win, scheduled_ns=0)
    )
    expired = emitter.sweep_expirations(now_monotonic_ns=10_000_000_000)
    assert expired == 0


def test_sweep_returns_zero_when_ttl_disabled() -> None:
    emitter = _build_emitter(
        config=BlockingWarningConfiguration(
            min_severity=BlockingSeverity.CRITICAL, expiration_ttl_ns=0
        )
    )
    win = build_synthetic_window()
    emitter.on_detection(
        build_synthetic_outcome(severity=BlockingSeverity.CRITICAL, window=win, scheduled_ns=0)
    )
    closed = build_synthetic_window()
    emitter.on_detection(
        build_synthetic_outcome(
            severity=BlockingSeverity.NONE, lag_ns=0, scheduled_ns=100, closed_window=closed
        )
    )
    assert emitter.sweep_expirations(now_monotonic_ns=10_000_000_000) == 0


# ── listener / router ───────────────────────────────────────────────────


def test_listener_receives_payload() -> None:
    emitter = _build_emitter()
    seen = []
    sid = emitter.subscribe(lambda payload: seen.append(payload.transition))
    win = build_synthetic_window()
    emitter.on_detection(build_synthetic_outcome(severity=BlockingSeverity.CRITICAL, window=win))
    assert seen == ["opened"]
    emitter.unsubscribe(sid)
    emitter.on_detection(
        build_synthetic_outcome(
            severity=BlockingSeverity.CRITICAL, window=win, scheduled_ns=1_000_000_000
        )
    )
    assert seen == ["opened"]


def test_listener_exception_does_not_break_pipeline() -> None:
    emitter = _build_emitter()
    emitter.subscribe(lambda p: (_ for _ in ()).throw(RuntimeError("listener bug")))
    win = build_synthetic_window()
    emitter.on_detection(build_synthetic_outcome(severity=BlockingSeverity.CRITICAL, window=win))
    assert emitter.metrics_snapshot().listener_failures >= 1


# ── re-entry guard ──────────────────────────────────────────────────────


def test_reentry_via_listener_is_blocked() -> None:
    """A listener that triggers another emission on the same thread is blocked."""
    emitter = _build_emitter()

    def listener(payload):
        # Trigger another outcome from the listener.
        emitter.on_detection(
            build_synthetic_outcome(
                severity=BlockingSeverity.CRITICAL,
                window=build_synthetic_window(window_id="reentry-window"),
            )
        )

    emitter.subscribe(listener)
    win = build_synthetic_window()
    emitter.on_detection(build_synthetic_outcome(severity=BlockingSeverity.CRITICAL, window=win))
    # The listener's re-entry should not create a second group.
    assert emitter.metrics_snapshot().groups_opened == 1


# ── reconfigure ─────────────────────────────────────────────────────────


def test_reconfigure_swaps_policy() -> None:
    emitter = _build_emitter()
    # Initial: WARNING rejected.
    win = build_synthetic_window()
    emitter.on_detection(build_synthetic_outcome(severity=BlockingSeverity.WARNING, window=win))
    assert emitter.metrics_snapshot().groups_opened == 0
    emitter.reconfigure(BlockingWarningConfiguration(min_severity=BlockingSeverity.WARNING))
    emitter.on_detection(
        build_synthetic_outcome(
            severity=BlockingSeverity.WARNING,
            window=build_synthetic_window(window_id="w2"),
        )
    )
    assert emitter.metrics_snapshot().groups_opened == 1
    assert emitter.metrics_snapshot().reconfigurations == 1


# ── replay determinism ─────────────────────────────────────────────────


def test_two_emitters_with_identical_inputs_produce_identical_state() -> None:
    win = build_synthetic_window()
    inputs = [
        build_synthetic_outcome(severity=BlockingSeverity.CRITICAL, window=win, scheduled_ns=0),
        build_synthetic_outcome(
            severity=BlockingSeverity.FREEZE,
            window=win,
            scheduled_ns=100,
            escalated=True,
            escalation_from=BlockingSeverity.CRITICAL,
            escalation_to=BlockingSeverity.FREEZE,
        ),
        build_synthetic_capture(window_id=win.window_id, capture_id=1, coroutine_name="cor1"),
        build_synthetic_outcome(
            severity=BlockingSeverity.NONE,
            lag_ns=0,
            scheduled_ns=1_000_000,
            closed_window=win,
        ),
    ]

    def run() -> dict:
        emitter = _build_emitter()
        replay_into_emitter(emitter, inputs)
        snap = emitter.snapshot().to_dict()
        # Strip non-deterministic ids
        snap.pop("runtime_id")
        snap.pop("generated_at_monotonic_ns")
        for collection_key in ("active_groups", "recent_groups"):
            for g in snap[collection_key]:
                g.pop("runtime_id")
                g.pop("group_id")
                g.pop("warning_id")
        return snap

    assert run() == run()


# ── lifecycle ───────────────────────────────────────────────────────────


async def test_start_and_stop_cleanly() -> None:
    emitter = _build_emitter()
    assert emitter.state is BlockingWarningEmitterState.IDLE
    await emitter.start()
    assert emitter.state is BlockingWarningEmitterState.RUNNING
    await emitter.stop()
    assert emitter.state is BlockingWarningEmitterState.STOPPED


async def test_stop_closes_open_groups() -> None:
    sink: list[RuntimeEvent] = []
    emitter = _build_emitter(sink=sink)
    await emitter.start()
    win = build_synthetic_window()
    emitter.on_detection(build_synthetic_outcome(severity=BlockingSeverity.CRITICAL, window=win))
    assert emitter.snapshot().active_groups
    await emitter.stop()
    # After stop, the open group must have been recovered.
    types = [e.event_type for e in sink]
    assert BLOCKING_WARNING_RECOVERED_EVENT_TYPE in types


async def test_double_start_is_idempotent() -> None:
    emitter = _build_emitter()
    await emitter.start()
    await emitter.start()
    assert emitter.is_running is True
    await emitter.stop()


async def test_stop_before_start_is_safe() -> None:
    emitter = _build_emitter()
    await emitter.stop()
    assert emitter.state is BlockingWarningEmitterState.STOPPED


# ── snapshot ────────────────────────────────────────────────────────────


def test_snapshot_carries_all_sections() -> None:
    emitter = _build_emitter()
    win = build_synthetic_window()
    emitter.on_detection(build_synthetic_outcome(severity=BlockingSeverity.CRITICAL, window=win))
    snap = emitter.snapshot()
    d = snap.to_dict()
    for key in (
        "runtime_id",
        "state",
        "generated_at_monotonic_ns",
        "configuration",
        "statistics",
        "metrics",
        "active_groups",
        "recent_groups",
    ):
        assert key in d
    assert len(d["active_groups"]) == 1


def test_diagnostics_to_dict_is_json_safe() -> None:
    import json

    emitter = _build_emitter(
        config=BlockingWarningConfiguration(
            min_severity=BlockingSeverity.CRITICAL, trace_enabled=True
        )
    )
    win = build_synthetic_window()
    emitter.on_detection(build_synthetic_outcome(severity=BlockingSeverity.CRITICAL, window=win))
    json.dumps(emitter.diagnostics_snapshot().to_dict())


# ── group lifetime ──────────────────────────────────────────────────────


def test_group_state_transitions_through_full_lifecycle() -> None:
    sink: list[RuntimeEvent] = []
    emitter = _build_emitter(sink=sink)
    win = build_synthetic_window()
    emitter.on_detection(
        build_synthetic_outcome(severity=BlockingSeverity.CRITICAL, window=win, scheduled_ns=0)
    )
    emitter.on_detection(
        build_synthetic_outcome(
            severity=BlockingSeverity.FREEZE,
            window=win,
            scheduled_ns=100,
            escalated=True,
            escalation_from=BlockingSeverity.CRITICAL,
            escalation_to=BlockingSeverity.FREEZE,
        )
    )
    closed = build_synthetic_window()
    emitter.on_detection(
        build_synthetic_outcome(
            severity=BlockingSeverity.NONE,
            lag_ns=0,
            scheduled_ns=1_000_000,
            closed_window=closed,
        )
    )
    types = [e.event_type for e in sink]
    assert types == [
        BLOCKING_WARNING_OPENED_EVENT_TYPE,
        BLOCKING_WARNING_ESCALATED_EVENT_TYPE,
        BLOCKING_WARNING_RECOVERED_EVENT_TYPE,
    ]


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
    emitter = _build_emitter()
    sub_id = emitter.bind_to_detector(detector)
    assert sub_id is not None
    # Drive a critical measurement directly.
    m = calculate_lag(
        scheduled_ns=0,
        actual_ns=50_000_000,
        interval_ns=1_000_000,
        sample_index=0,
        runtime_id="r",
    )
    e = thresholds.evaluate(m.lag_ns)
    detector.process(m, e)
    await asyncio.sleep(0)
    assert emitter.metrics_snapshot().groups_opened >= 1


def test_unbind_is_idempotent() -> None:
    from asyncviz.runtime.monitoring.blocking import BlockingThresholdDetector

    clock = RuntimeClock()
    detector = BlockingThresholdDetector(runtime_clock=clock)
    emitter = _build_emitter()
    emitter.bind_to_detector(detector)
    assert emitter.unbind_from_detector() is True
    assert emitter.unbind_from_detector() is False
