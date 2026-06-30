"""End-to-end behaviour tests for :class:`ExecutorMetricsEngine`."""

from __future__ import annotations

import asyncio

import pytest

from asyncviz.instrumentation.executor.metrics import (
    ExecutorMetricsConfig,
    ExecutorMetricsEngine,
    rebuild_executor_metrics_from_events,
)
from asyncviz.runtime.events import EventBus
from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.events.models.executor import (
    ExecutorRegisteredEvent,
    ExecutorWorkCancelledEvent,
    ExecutorWorkCompletedEvent,
    ExecutorWorkFailedEvent,
    ExecutorWorkStartedEvent,
    ExecutorWorkSubmittedEvent,
)
from asyncviz.runtime.events.models.executor_metrics import (
    ExecutorMetricsUpdatedEvent,
)

# ── helpers ─────────────────────────────────────────────────────────────


def _registered(eid: str = "e-1", *, max_workers: int | None = 4) -> ExecutorRegisteredEvent:
    return ExecutorRegisteredEvent(
        executor_id=eid,
        executor_kind="Thread",
        snapshot={"executor_id": eid, "executor_kind": "Thread"},
        max_workers=max_workers,
        thread_name_prefix="p",
    )


def _submitted(eid: str = "e-1", wid: str = "w-1") -> ExecutorWorkSubmittedEvent:
    return ExecutorWorkSubmittedEvent(
        executor_id=eid,
        executor_kind="Thread",
        snapshot={"work_item_id": wid, "executor_id": eid},
        work_item_id=wid,
        submitting_task_id="t-1",
        callable_name="f",
    )


def _started(
    eid: str = "e-1",
    wid: str = "w-1",
    *,
    latency: float | None = 0.01,
) -> ExecutorWorkStartedEvent:
    return ExecutorWorkStartedEvent(
        executor_id=eid,
        executor_kind="Thread",
        snapshot={"work_item_id": wid, "executor_id": eid},
        work_item_id=wid,
        submitting_task_id="t-1",
        callable_name="f",
        worker_thread_name="Thread-1",
        submission_latency_seconds=latency,
    )


def _completed(
    eid: str = "e-1",
    wid: str = "w-1",
    *,
    duration: float | None = 0.05,
) -> ExecutorWorkCompletedEvent:
    return ExecutorWorkCompletedEvent(
        executor_id=eid,
        executor_kind="Thread",
        snapshot={"work_item_id": wid, "executor_id": eid},
        work_item_id=wid,
        submitting_task_id="t-1",
        callable_name="f",
        worker_thread_name="Thread-1",
        duration_seconds=duration,
    )


def _failed(eid: str = "e-1", wid: str = "w-1") -> ExecutorWorkFailedEvent:
    return ExecutorWorkFailedEvent(
        executor_id=eid,
        executor_kind="Thread",
        snapshot={"work_item_id": wid, "executor_id": eid},
        work_item_id=wid,
        submitting_task_id="t-1",
        callable_name="f",
        worker_thread_name="Thread-1",
        duration_seconds=0.01,
        exception_type="ValueError",
    )


def _cancelled(eid: str = "e-1", wid: str = "w-1") -> ExecutorWorkCancelledEvent:
    return ExecutorWorkCancelledEvent(
        executor_id=eid,
        executor_kind="Thread",
        snapshot={"work_item_id": wid, "executor_id": eid},
        work_item_id=wid,
        submitting_task_id="t-1",
        callable_name="f",
        duration_seconds=0.0,
    )


# ── basic ingest ────────────────────────────────────────────────────────


def test_apply_ignores_non_executor_events(
    engine_unbound: ExecutorMetricsEngine,
) -> None:
    event = RuntimeEvent.of("asyncio.task.created", task_id="t-1")
    assert engine_unbound.apply_event(event) is False
    snap = engine_unbound.snapshot()
    assert snap.self_metrics.events_ignored == 1


def test_first_event_registers_an_executor(
    engine_unbound: ExecutorMetricsEngine,
) -> None:
    engine_unbound.apply_event(_registered())
    snap = engine_unbound.snapshot()
    assert len(snap.executors) == 1
    record = snap.executors[0]
    assert record.executor_id == "e-1"
    assert record.executor_kind == "Thread"
    assert record.max_workers == 4


def test_lifecycle_updates_active_workers_and_throughput(
    engine_unbound: ExecutorMetricsEngine,
) -> None:
    engine_unbound.apply_event(_registered())
    for i in range(3):
        wid = f"w-{i + 1}"
        engine_unbound.apply_event(_submitted("e-1", wid))
        engine_unbound.apply_event(_started("e-1", wid))
    record = engine_unbound.snapshot_executor("e-1")
    assert record is not None
    assert record.utilization.active_workers == 3
    assert record.utilization.peak_active_workers == 3
    assert record.throughput.submissions == 3
    assert record.throughput.completions == 0
    assert record.throughput.backlog == 3


def test_completed_event_decrements_active_workers(
    engine_unbound: ExecutorMetricsEngine,
) -> None:
    engine_unbound.apply_event(_registered())
    engine_unbound.apply_event(_submitted())
    engine_unbound.apply_event(_started())
    engine_unbound.apply_event(_completed())
    record = engine_unbound.snapshot_executor("e-1")
    assert record is not None
    assert record.utilization.active_workers == 0
    assert record.throughput.completions == 1


def test_failed_event_decrements_and_increments_failures(
    engine_unbound: ExecutorMetricsEngine,
) -> None:
    engine_unbound.apply_event(_registered())
    engine_unbound.apply_event(_submitted())
    engine_unbound.apply_event(_started())
    engine_unbound.apply_event(_failed())
    record = engine_unbound.snapshot_executor("e-1")
    assert record is not None
    assert record.utilization.active_workers == 0
    assert record.throughput.failures == 1


def test_cancelled_event_only_bumps_throughput(
    engine_unbound: ExecutorMetricsEngine,
) -> None:
    engine_unbound.apply_event(_registered())
    engine_unbound.apply_event(_submitted())
    engine_unbound.apply_event(_cancelled())
    record = engine_unbound.snapshot_executor("e-1")
    assert record is not None
    # Cancelled work that never started doesn't decrement.
    assert record.utilization.active_workers == 0
    assert record.throughput.cancellations == 1


def test_submission_latency_digest_populates(
    engine_unbound: ExecutorMetricsEngine,
) -> None:
    engine_unbound.apply_event(_registered())
    engine_unbound.apply_event(_submitted("e-1", "w-1"))
    engine_unbound.apply_event(_started("e-1", "w-1", latency=0.03))
    record = engine_unbound.snapshot_executor("e-1")
    assert record is not None
    assert record.submission_latency.count == 1
    assert record.submission_latency.mean_seconds == pytest.approx(0.03)


# ── saturation transitions ──────────────────────────────────────────────


def test_saturation_changed_emits_on_level_transition(
    engine_unbound: ExecutorMetricsEngine,
) -> None:
    seen: list = []
    engine_unbound.subscribe(
        lambda delta: seen.append(delta) if delta.kind == "saturation-changed" else None,
    )
    # 2-worker pool driven to fully utilized + with submission latency
    # spike so the score crosses the warning threshold.
    engine_unbound.apply_event(_registered(max_workers=2))
    for i in range(2):
        wid = f"w-{i + 1}"
        engine_unbound.apply_event(_submitted("e-1", wid))
        engine_unbound.apply_event(_started("e-1", wid, latency=0.5))
    assert any(d.new_level in {"warning", "critical"} for d in seen)


# ── contention edge ─────────────────────────────────────────────────────


def test_contention_edge_fires_once_on_threshold_cross(
    engine_unbound: ExecutorMetricsEngine,
) -> None:
    seen: list = []
    engine_unbound.subscribe(
        lambda d: seen.append(d) if d.kind == "contention-detected" else None,
    )
    engine_unbound.apply_event(_registered(max_workers=2))
    # 1 worker = 0.5 ratio (below 0.9 threshold)
    engine_unbound.apply_event(_submitted("e-1", "w-1"))
    engine_unbound.apply_event(_started("e-1", "w-1"))
    assert seen == []
    # 2nd worker = 1.0 ratio (above threshold) — edge fires.
    engine_unbound.apply_event(_submitted("e-1", "w-2"))
    engine_unbound.apply_event(_started("e-1", "w-2"))
    assert len(seen) == 1
    # Another start would also keep us above, but we can't go above with
    # a 2-worker pool unless decrement-then-cross-again happens.
    # Verify a drop-then-resaturate re-fires.
    engine_unbound.apply_event(_completed("e-1", "w-1"))
    engine_unbound.apply_event(_submitted("e-1", "w-3"))
    engine_unbound.apply_event(_started("e-1", "w-3"))
    assert len(seen) == 2


# ── latency spike ───────────────────────────────────────────────────────


def test_latency_spike_fires_when_threshold_exceeded(
    engine_unbound: ExecutorMetricsEngine,
) -> None:
    seen: list = []
    engine_unbound.subscribe(
        lambda d: seen.append(d) if d.kind == "latency-spike-detected" else None,
    )
    engine_unbound.apply_event(_registered())
    engine_unbound.apply_event(_submitted())
    engine_unbound.apply_event(_started(latency=0.5))  # > 0.25 default
    assert len(seen) == 1


# ── debounce ────────────────────────────────────────────────────────────


def test_updated_event_respects_debounce() -> None:
    engine = ExecutorMetricsEngine(
        bus=None,
        config=ExecutorMetricsConfig(
            updated_min_interval_seconds=999.0,
            updated_min_event_delta=5,
            saturation_warning_threshold=2.0,  # never trip
            saturation_critical_threshold=3.0,
            contention_active_worker_ratio=2.0,
            latency_spike_threshold_seconds=999.0,
        ),
    )
    updates: list = []
    engine.subscribe(lambda d: updates.append(d) if d.kind == "updated" else None)
    engine.apply_event(_registered())
    # First event always emits (last_emit_monotonic == 0.0 short-circuits).
    assert len(updates) == 1
    # 4 more events — below the delta threshold of 5 since the last emission.
    for i in range(2, 6):
        engine.apply_event(_submitted("e-1", f"w-{i}"))
    assert len(updates) == 1
    # 5th event since last emission → trips the delta threshold.
    engine.apply_event(_submitted("e-1", "w-6"))
    assert len(updates) == 2


# ── rebuild ──────────────────────────────────────────────────────────────


def test_rebuild_is_deterministic() -> None:
    events = [
        _registered(),
        _submitted("e-1", "w-1"),
        _started("e-1", "w-1"),
        _completed("e-1", "w-1"),
        _submitted("e-1", "w-2"),
        _started("e-1", "w-2"),
    ]
    _e1, snap1, applied1 = rebuild_executor_metrics_from_events(events)
    _e2, snap2, applied2 = rebuild_executor_metrics_from_events(events)
    assert applied1 == applied2 == 6
    assert snap1.executors[0].to_dict() == snap2.executors[0].to_dict()


def test_rebuild_silently_does_not_emit() -> None:
    fired: list = []
    engine = ExecutorMetricsEngine(bus=None, emit_during_apply=False)
    engine.subscribe(lambda d: fired.append(d))
    engine.rebuild_from_events([_registered(), _submitted(), _started()])
    assert fired == []
    record = engine.snapshot_executor("e-1")
    assert record is not None
    assert record.utilization.active_workers == 1


# ── backpressure / safety ────────────────────────────────────────────────


def test_max_tracked_executors_evicts() -> None:
    engine = ExecutorMetricsEngine(
        bus=None,
        config=ExecutorMetricsConfig(max_tracked_executors=2),
    )
    engine.apply_event(_registered("e-1"))
    engine.apply_event(_registered("e-2"))
    engine.apply_event(_registered("e-3"))
    snap = engine.snapshot()
    assert {e.executor_id for e in snap.executors} == {"e-1", "e-2"}
    assert snap.self_metrics.executors_evicted == 1


# ── bus integration ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_engine_subscribes_to_bus_executor_events(
    bus: EventBus,
    fast_emit_config: ExecutorMetricsConfig,
) -> None:
    engine = ExecutorMetricsEngine(bus=bus, config=fast_emit_config)
    engine.start()
    try:
        events: list = []
        bus.subscribe(
            lambda e: events.append(e),
            event_types={"asyncio.executor.metrics.updated"},
        )
        bus.publish(_registered())
        bus.publish(_submitted())
        bus.publish(_started())
        bus.publish(_completed())
        await asyncio.sleep(0)
        await bus.join()
        assert any(isinstance(e, ExecutorMetricsUpdatedEvent) for e in events)
    finally:
        engine.stop()


@pytest.mark.asyncio
async def test_engine_stop_unsubscribes(bus: EventBus) -> None:
    engine = ExecutorMetricsEngine(bus=bus)
    engine.start()
    engine.stop()
    bus.publish(_registered())
    await bus.join()
    snap = engine.snapshot()
    assert snap.self_metrics.events_observed == 0


# ── snapshot round-trip ──────────────────────────────────────────────────


def test_snapshot_is_json_safe(engine_unbound: ExecutorMetricsEngine) -> None:
    import json

    engine_unbound.apply_event(_registered())
    engine_unbound.apply_event(_submitted())
    engine_unbound.apply_event(_started())
    body = engine_unbound.snapshot().to_dict()
    payload = json.dumps(body)
    restored = json.loads(payload)
    assert restored["executors"][0]["executor_id"] == "e-1"
