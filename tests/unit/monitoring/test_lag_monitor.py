from __future__ import annotations

import asyncio

from asyncviz.runtime.clock import RuntimeClock
from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.monitoring.event_loop import (
    LAG_THRESHOLD_BREACH_EVENT_TYPE,
    EventLoopLagMonitor,
    LagConfiguration,
    LagMonitorState,
    LagSeverity,
    LagThresholds,
)
from asyncviz.runtime.monitoring.event_loop.lag_measurement import calculate_lag
from asyncviz.runtime.monitoring.event_loop.utils.fake_clock import FakeMonotonicClock


def _measure(lag_ns: int, *, index: int = 0):
    return calculate_lag(
        scheduled_ns=0,
        actual_ns=lag_ns,
        interval_ns=100_000_000,
        sample_index=index,
        runtime_id="r",
    )


# ── apply_measurement ────────────────────────────────────────────────────


def test_apply_measurement_updates_statistics_and_metrics() -> None:
    clock = RuntimeClock()
    fake = FakeMonotonicClock()
    m = EventLoopLagMonitor(
        runtime_clock=clock,
        monotonic_clock=fake,
        configuration=LagConfiguration.default(),
    )
    m.apply_measurement(_measure(10_000_000))  # 10ms
    stats = m.statistics_snapshot()
    metrics = m.metrics_snapshot()
    assert stats.sample_count == 1
    assert metrics.samples_recorded == 1
    assert metrics.samples_attempted == 1


def test_apply_measurement_returns_threshold_evaluation() -> None:
    clock = RuntimeClock()
    cfg = LagConfiguration(
        thresholds=LagThresholds(warning_seconds=0.001, critical_seconds=0.01, freeze_seconds=0.1)
    )
    m = EventLoopLagMonitor(runtime_clock=clock, configuration=cfg)
    e = m.apply_measurement(_measure(50_000_000))  # 50ms → CRITICAL
    assert e.severity is LagSeverity.CRITICAL
    assert e.breached is True


def test_threshold_hits_tracked_in_metrics() -> None:
    clock = RuntimeClock()
    cfg = LagConfiguration(
        thresholds=LagThresholds(warning_seconds=0.001, critical_seconds=0.01, freeze_seconds=0.1)
    )
    m = EventLoopLagMonitor(runtime_clock=clock, configuration=cfg)
    m.apply_measurement(_measure(5_000_000))  # 5ms → WARNING
    m.apply_measurement(_measure(50_000_000))  # 50ms → CRITICAL
    m.apply_measurement(_measure(500_000_000))  # 500ms → FREEZE
    metrics = m.metrics_snapshot()
    assert metrics.warning_threshold_hits == 3  # warning + critical + freeze
    assert metrics.critical_threshold_hits == 2  # critical + freeze
    assert metrics.freeze_threshold_hits == 1


# ── event emission ──────────────────────────────────────────────────────


def test_threshold_breach_emits_event_via_emitter() -> None:
    clock = RuntimeClock()
    emitted: list[RuntimeEvent] = []
    cfg = LagConfiguration(
        thresholds=LagThresholds(warning_seconds=0.001, critical_seconds=0.01, freeze_seconds=0.1),
        emit_measurement_events=False,
        emit_threshold_breach_events=True,
    )

    def emit(e):
        emitted.append(e)
        return True

    m = EventLoopLagMonitor(runtime_clock=clock, configuration=cfg, event_emitter=emit)
    m.apply_measurement(_measure(50_000_000))  # CRITICAL
    assert len(emitted) == 1
    assert emitted[0].event_type == LAG_THRESHOLD_BREACH_EVENT_TYPE


def test_no_event_on_normal_measurement() -> None:
    clock = RuntimeClock()
    emitted: list[RuntimeEvent] = []
    m = EventLoopLagMonitor(
        runtime_clock=clock,
        configuration=LagConfiguration.default(),
        event_emitter=lambda e: emitted.append(e) or True,
    )
    m.apply_measurement(_measure(1_000_000))  # 1ms → NORMAL
    assert emitted == []


def test_measurement_events_emitted_when_enabled() -> None:
    clock = RuntimeClock()
    emitted: list[RuntimeEvent] = []
    cfg = LagConfiguration(
        emit_measurement_events=True,
        emit_threshold_breach_events=False,
    )
    m = EventLoopLagMonitor(
        runtime_clock=clock,
        configuration=cfg,
        event_emitter=lambda e: emitted.append(e) or True,
    )
    m.apply_measurement(_measure(100))
    assert len(emitted) == 1


def test_emitter_returning_false_counts_as_drop() -> None:
    clock = RuntimeClock()
    cfg = LagConfiguration(
        thresholds=LagThresholds(warning_seconds=0.001, critical_seconds=0.01, freeze_seconds=0.1),
        emit_threshold_breach_events=True,
    )
    m = EventLoopLagMonitor(runtime_clock=clock, configuration=cfg, event_emitter=lambda _: False)
    m.apply_measurement(_measure(50_000_000))
    metrics = m.metrics_snapshot()
    assert metrics.threshold_breach_events_emitted == 0
    assert metrics.measurement_events_dropped == 1


def test_emitter_exception_does_not_propagate() -> None:
    clock = RuntimeClock()
    cfg = LagConfiguration(
        thresholds=LagThresholds(warning_seconds=0.001, critical_seconds=0.01, freeze_seconds=0.1),
    )

    def raising_emit(_):
        raise RuntimeError("downstream failure")

    m = EventLoopLagMonitor(runtime_clock=clock, configuration=cfg, event_emitter=raising_emit)
    # Should not raise.
    m.apply_measurement(_measure(50_000_000))


# ── listeners ────────────────────────────────────────────────────────────


def test_subscribe_invokes_listener_per_sample() -> None:
    clock = RuntimeClock()
    m = EventLoopLagMonitor(runtime_clock=clock, configuration=LagConfiguration.default())
    seen: list = []
    sid = m.subscribe(lambda meas, evald: seen.append((meas.lag_ns, evald.severity)))
    m.apply_measurement(_measure(100))
    m.apply_measurement(_measure(200))
    assert len(seen) == 2
    assert m.unsubscribe(sid) is True
    m.apply_measurement(_measure(300))
    assert len(seen) == 2


def test_listener_exception_does_not_break_pipeline() -> None:
    clock = RuntimeClock()
    m = EventLoopLagMonitor(runtime_clock=clock, configuration=LagConfiguration.default())
    m.subscribe(lambda meas, evald: (_ for _ in ()).throw(RuntimeError("listener bug")))
    # Should not raise; statistics still updated.
    m.apply_measurement(_measure(100))
    assert m.statistics_snapshot().sample_count == 1


# ── reconfigure ──────────────────────────────────────────────────────────


def test_reconfigure_swaps_thresholds_atomically() -> None:
    clock = RuntimeClock()
    m = EventLoopLagMonitor(runtime_clock=clock, configuration=LagConfiguration.default())
    e1 = m.apply_measurement(_measure(40_000_000))  # 40ms — below 50ms default warning
    assert e1.severity is LagSeverity.NORMAL
    m.reconfigure(
        LagConfiguration(
            thresholds=LagThresholds(warning_seconds=0.01, critical_seconds=0.1, freeze_seconds=1.0)
        )
    )
    e2 = m.apply_measurement(_measure(40_000_000))  # 40ms — now above 10ms warning
    assert e2.severity is LagSeverity.WARNING


def test_reconfigure_rebuilds_statistics_when_window_changes() -> None:
    clock = RuntimeClock()
    m = EventLoopLagMonitor(
        runtime_clock=clock, configuration=LagConfiguration(statistics_window=4)
    )
    m.apply_measurement(_measure(100))
    assert m.statistics_snapshot().window_capacity == 4
    m.reconfigure(LagConfiguration(statistics_window=16))
    assert m.statistics_snapshot().window_capacity == 16
    # New window starts fresh — the prior sample is gone.
    assert m.statistics_snapshot().sample_count == 0


def test_reconfigure_increments_metric() -> None:
    clock = RuntimeClock()
    m = EventLoopLagMonitor(runtime_clock=clock, configuration=LagConfiguration.default())
    m.reconfigure(LagConfiguration(sample_interval_seconds=0.05))
    snap = m.metrics_snapshot()
    assert snap.reconfigurations == 1


# ── lifecycle ────────────────────────────────────────────────────────────


async def test_start_and_stop_cleanly() -> None:
    clock = RuntimeClock()
    m = EventLoopLagMonitor(
        runtime_clock=clock,
        configuration=LagConfiguration(sample_interval_seconds=0.01),
    )
    assert m.state is LagMonitorState.IDLE
    await m.start()
    assert m.state is LagMonitorState.RUNNING
    await asyncio.sleep(0.05)
    await m.stop()
    assert m.state is LagMonitorState.STOPPED


async def test_double_start_is_idempotent() -> None:
    clock = RuntimeClock()
    m = EventLoopLagMonitor(
        runtime_clock=clock,
        configuration=LagConfiguration(sample_interval_seconds=0.01),
    )
    await m.start()
    await m.start()
    assert m.state is LagMonitorState.RUNNING
    await m.stop()


async def test_stop_before_start_is_safe() -> None:
    clock = RuntimeClock()
    m = EventLoopLagMonitor(
        runtime_clock=clock,
        configuration=LagConfiguration(sample_interval_seconds=0.01),
    )
    await m.stop()
    assert m.state is LagMonitorState.STOPPED


async def test_scheduler_actually_takes_samples() -> None:
    clock = RuntimeClock()
    m = EventLoopLagMonitor(
        runtime_clock=clock,
        configuration=LagConfiguration(sample_interval_seconds=0.01),
    )
    await m.start()
    await asyncio.sleep(0.1)
    await m.stop()
    snap = m.statistics_snapshot()
    assert snap.sample_count >= 3  # at least a few samples in 100ms with 10ms cadence


# ── snapshots ────────────────────────────────────────────────────────────


def test_snapshot_carries_all_subsystems() -> None:
    clock = RuntimeClock()
    m = EventLoopLagMonitor(runtime_clock=clock, configuration=LagConfiguration.default())
    m.apply_measurement(_measure(1_000))
    snap = m.snapshot()
    assert snap.runtime_id == str(clock.runtime_id)
    assert snap.state is LagMonitorState.IDLE  # never started
    assert snap.statistics.sample_count == 1
    assert snap.last_measurement is not None
    assert snap.last_measurement.lag_ns == 1_000


def test_diagnostics_snapshot_includes_trace_records_when_enabled() -> None:
    clock = RuntimeClock()
    m = EventLoopLagMonitor(
        runtime_clock=clock,
        configuration=LagConfiguration(trace_enabled=True),
    )
    m.apply_measurement(_measure(100))
    diag = m.diagnostics_snapshot()
    assert diag.trace_enabled is True
    assert len(diag.trace_records) >= 1


def test_diagnostics_snapshot_to_dict_is_json_safe() -> None:
    clock = RuntimeClock()
    m = EventLoopLagMonitor(runtime_clock=clock, configuration=LagConfiguration.default())
    m.apply_measurement(_measure(100))
    d = m.diagnostics_snapshot().to_dict()
    import json

    json.dumps(d)  # must not raise


# ── replay safety ────────────────────────────────────────────────────────


def test_two_monitors_with_identical_sequence_produce_identical_snapshots() -> None:
    """Replay: same measurements in same order → same snapshot."""
    cfg = LagConfiguration(
        thresholds=LagThresholds(warning_seconds=0.001, critical_seconds=0.01, freeze_seconds=0.1),
        statistics_window=8,
        emit_measurement_events=False,
        emit_threshold_breach_events=False,
    )
    lags = [100, 200, 50_000_000, 300, 400]
    measurements = [_measure(lag, index=i) for i, lag in enumerate(lags)]

    def replay() -> dict:
        c = RuntimeClock()
        m = EventLoopLagMonitor(runtime_clock=c, configuration=cfg)
        for meas in measurements:
            m.apply_measurement(meas)
        snap = m.snapshot()
        # Strip runtime_id (different per RuntimeClock construction) +
        # generated_at_monotonic_ns (clock dependent).
        d = snap.to_dict()
        d.pop("runtime_id")
        d.pop("generated_at_monotonic_ns")
        if d["last_measurement"] is not None:
            d["last_measurement"].pop("runtime_id", None)
        return d

    assert replay() == replay()
