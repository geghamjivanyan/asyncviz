from __future__ import annotations

import json

import pytest

from asyncviz.runtime.clock import RuntimeClock, reset_runtime_clock, set_default_runtime_clock
from asyncviz.runtime.events.models import (
    TaskCancelledEvent,
    TaskCompletedEvent,
    TaskCreatedEvent,
)
from asyncviz.runtime.events.models.enums import WarningSeverity
from asyncviz.runtime.metrics import RuntimeMetricsAggregator
from asyncviz.runtime.state import RuntimeStateStore
from asyncviz.runtime.tasks import TaskRegistry
from asyncviz.runtime.warnings import (
    CancellationOriginDetector,
    DedupDecision,
    DeepLineageDetector,
    DetectorContext,
    DetectorRegistrationError,
    ExcessiveActiveTasksDetector,
    ExpirationPolicy,
    RuntimeWarningManager,
    SlowTaskDetector,
    WarningChange,
    WarningDelta,
    WarningLifecycle,
    WarningSnapshot,
    count_by_severity,
    evaluate_dedup,
    fresh_warning_id,
    is_at_least,
    max_severity,
)


@pytest.fixture(autouse=True)
def _fresh_clock():
    reset_runtime_clock()
    clock = RuntimeClock()
    set_default_runtime_clock(clock)
    yield clock
    reset_runtime_clock()


@pytest.fixture
def manager(_fresh_clock: RuntimeClock) -> RuntimeWarningManager:
    registry = TaskRegistry()
    aggregator = RuntimeMetricsAggregator(registry, clock=_fresh_clock)
    return RuntimeWarningManager(registry, aggregator=aggregator, clock=_fresh_clock)


# ── Severity helpers ──────────────────────────────────────────────────────


def test_is_at_least_strict_ordering() -> None:
    assert is_at_least(WarningSeverity.ERROR, WarningSeverity.WARNING)
    assert is_at_least(WarningSeverity.CRITICAL, WarningSeverity.CRITICAL)
    assert not is_at_least(WarningSeverity.INFO, WarningSeverity.WARNING)


def test_max_severity_picks_highest() -> None:
    assert max_severity(WarningSeverity.INFO, WarningSeverity.ERROR) is WarningSeverity.ERROR


# ── Deduplication ─────────────────────────────────────────────────────────


def test_dedup_activate_when_no_existing() -> None:
    result = evaluate_dedup(warning_key="x", existing=None, sequence=1)
    assert result.decision is DedupDecision.ACTIVATE


def test_dedup_refresh_when_active_existing() -> None:
    existing = WarningLifecycle(
        warning_id=fresh_warning_id(),
        warning_key="x",
        warning_type="t",
        severity=WarningSeverity.WARNING,
        detector="d",
        message="m",
        created_sequence=1,
        created_monotonic_ns=100,
        created_at_wall=0.0,
        last_observed_sequence=2,
        last_observed_monotonic_ns=200,
        last_observed_wall=0.0,
    )
    result = evaluate_dedup(warning_key="x", existing=existing, sequence=3)
    assert result.decision is DedupDecision.REFRESH


def test_dedup_suppresses_stale_sequence() -> None:
    existing = WarningLifecycle(
        warning_id=fresh_warning_id(),
        warning_key="x",
        warning_type="t",
        severity=WarningSeverity.WARNING,
        detector="d",
        message="m",
        created_sequence=10,
        created_monotonic_ns=100,
        created_at_wall=0.0,
        last_observed_sequence=10,
        last_observed_monotonic_ns=100,
        last_observed_wall=0.0,
    )
    result = evaluate_dedup(warning_key="x", existing=existing, sequence=5)
    assert result.decision is DedupDecision.SUPPRESS


def test_dedup_reactivates_after_resolve() -> None:
    existing = WarningLifecycle(
        warning_id=fresh_warning_id(),
        warning_key="x",
        warning_type="t",
        severity=WarningSeverity.WARNING,
        detector="d",
        message="m",
        created_sequence=1,
        created_monotonic_ns=100,
        created_at_wall=0.0,
        last_observed_sequence=2,
        last_observed_monotonic_ns=200,
        last_observed_wall=0.0,
        resolved=True,
    )
    result = evaluate_dedup(warning_key="x", existing=existing, sequence=10)
    assert result.decision is DedupDecision.ACTIVATE


# ── Detector — slow task ──────────────────────────────────────────────────


def test_slow_task_detector_fires_above_threshold() -> None:
    registry = TaskRegistry()
    detector = SlowTaskDetector(threshold_seconds=0.05)
    ctx = DetectorContext(registry=registry, aggregator=None)
    event = TaskCompletedEvent(task_id="t1", duration_seconds=0.10)
    triggers = list(detector.evaluate_event(ctx, event, sequence=1))
    assert len(triggers) == 1
    assert triggers[0].warning_type == "slow_task"
    assert triggers[0].warning_key == "slow_task:t1"
    assert triggers[0].severity is WarningSeverity.WARNING


def test_slow_task_detector_silent_below_threshold() -> None:
    registry = TaskRegistry()
    detector = SlowTaskDetector(threshold_seconds=1.0)
    ctx = DetectorContext(registry=registry, aggregator=None)
    event = TaskCompletedEvent(task_id="t1", duration_seconds=0.01)
    triggers = list(detector.evaluate_event(ctx, event, sequence=1))
    assert triggers == []


def test_cancellation_origin_detector_fires_for_unusual_origins() -> None:
    detector = CancellationOriginDetector()
    ctx = DetectorContext(registry=TaskRegistry(), aggregator=None)
    event = TaskCancelledEvent(task_id="t1", duration_seconds=0.01, cancellation_origin="timeout")
    triggers = list(detector.evaluate_event(ctx, event, sequence=1))
    assert len(triggers) == 1
    assert triggers[0].severity is WarningSeverity.INFO


def test_cancellation_origin_detector_silent_for_explicit(
    _fresh_clock: RuntimeClock,
) -> None:
    detector = CancellationOriginDetector()
    ctx = DetectorContext(registry=TaskRegistry(), aggregator=None)
    event = TaskCancelledEvent(task_id="t1", duration_seconds=0.01, cancellation_origin="explicit")
    assert list(detector.evaluate_event(ctx, event, sequence=1)) == []


# ── Detector — snapshot-driven ────────────────────────────────────────────


def test_excessive_active_tasks_detector_fires_above_threshold(
    _fresh_clock: RuntimeClock,
) -> None:
    registry = TaskRegistry()
    aggregator = RuntimeMetricsAggregator(registry, clock=_fresh_clock)
    for i in range(3):
        aggregator.apply_event(TaskCreatedEvent(task_id=f"t{i}"), sequence=i + 1)
    detector = ExcessiveActiveTasksDetector(threshold=2)
    ctx = DetectorContext(registry=registry, aggregator=aggregator)
    triggers = list(
        detector.evaluate_snapshot(
            ctx, sequence=10, monotonic_ns=_fresh_clock.monotonic_ns(), wall_seconds=0.0
        )
    )
    assert len(triggers) == 1
    assert triggers[0].warning_type == "excessive_active_tasks"
    assert triggers[0].severity is WarningSeverity.ERROR


def test_deep_lineage_detector_fires_when_chain_too_deep(
    _fresh_clock: RuntimeClock,
) -> None:
    from asyncviz.runtime.tasks import TaskMetadata

    registry = TaskRegistry()
    registry.register("t0")
    for i in range(1, 6):
        registry.register(f"t{i}", metadata=TaskMetadata(parent_task_id=f"t{i - 1}"))
    aggregator = RuntimeMetricsAggregator(registry, clock=_fresh_clock)
    detector = DeepLineageDetector(threshold=3)
    ctx = DetectorContext(registry=registry, aggregator=aggregator)
    triggers = list(
        detector.evaluate_snapshot(
            ctx, sequence=10, monotonic_ns=_fresh_clock.monotonic_ns(), wall_seconds=0.0
        )
    )
    assert len(triggers) == 1
    assert triggers[0].warning_key == "deep_lineage:depth_>=3"


# ── Manager — lifecycle ────────────────────────────────────────────────────


def test_manager_activates_warning_on_event(manager: RuntimeWarningManager) -> None:
    manager.apply_event(
        TaskCompletedEvent(task_id="slow", duration_seconds=10.0),
        sequence=1,
    )
    active = manager.active_view()
    assert len(active) == 1
    assert active[0].warning_type == "slow_task"


def test_manager_deduplicates_repeat_triggers(manager: RuntimeWarningManager) -> None:
    # Same task slow twice — different event_ids, same warning_key.
    manager.apply_event(
        TaskCompletedEvent(task_id="slow", duration_seconds=10.0),
        sequence=1,
    )
    # The second event is for the same task with the same warning_key →
    # registry rejects the second COMPLETED, but the slow-task detector
    # would still fire if we crafted a fresh task. Use the same task here
    # and simulate a re-trigger via the synthetic ``manager._apply_trigger``.
    from asyncviz.runtime.warnings.normalization import WarningTrigger

    trigger = WarningTrigger(
        warning_type="slow_task",
        warning_key="slow_task:slow",
        severity=WarningSeverity.WARNING,
        message="repeat",
        detector="slow_task",
        sequence=2,
        monotonic_ns=200,
        wall_seconds=0.0,
        related_task_ids=("slow",),
        lineage_root_id=None,
        metadata={"duration_seconds": 12.0},
    )
    manager._apply_trigger(trigger)  # type: ignore[attr-defined]
    active = manager.active_view()
    assert len(active) == 1
    assert active[0].occurrence_count == 2


def test_manager_emits_delta_on_activate(manager: RuntimeWarningManager) -> None:
    deltas: list[WarningDelta] = []
    manager.subscribe(deltas.append)
    manager.apply_event(
        TaskCompletedEvent(task_id="slow", duration_seconds=10.0),
        sequence=1,
    )
    assert any(d.change is WarningChange.ACTIVATED for d in deltas)


def test_manager_resolves_warning_explicitly(manager: RuntimeWarningManager) -> None:
    manager.apply_event(
        TaskCompletedEvent(task_id="slow", duration_seconds=10.0),
        sequence=1,
    )
    warning = manager.active_view()[0]
    assert manager.resolve_warning(warning.warning_id, sequence=5) is True
    assert manager.resolve_warning(warning.warning_id, sequence=6) is False  # already resolved


def test_manager_isolates_subscriber_failures(manager: RuntimeWarningManager) -> None:
    received: list[WarningDelta] = []

    def bad(_: WarningDelta) -> None:
        raise RuntimeError("boom")

    manager.subscribe(bad)
    manager.subscribe(received.append)
    manager.apply_event(
        TaskCompletedEvent(task_id="slow", duration_seconds=10.0),
        sequence=1,
    )
    assert len(received) == 1
    self_metrics = manager.self_metrics_snapshot()
    assert self_metrics.subscription_failures == 1


# ── Manager — snapshot-driven evaluation ──────────────────────────────────


def test_evaluate_resolves_warnings_no_longer_firing(_fresh_clock: RuntimeClock) -> None:
    registry = TaskRegistry()
    aggregator = RuntimeMetricsAggregator(registry, clock=_fresh_clock)
    # Threshold = 2; create 3 tasks to trigger.
    detector = ExcessiveActiveTasksDetector(threshold=2)
    manager = RuntimeWarningManager(
        registry,
        aggregator=aggregator,
        clock=_fresh_clock,
        detectors=[detector],
    )
    for i in range(3):
        aggregator.apply_event(TaskCreatedEvent(task_id=f"t{i}"), sequence=i + 1)
    manager.evaluate()
    assert len(manager.active_view()) == 1

    # Drop active count by completing two tasks.
    aggregator.apply_event(TaskCompletedEvent(task_id="t0", duration_seconds=0.01), sequence=10)
    aggregator.apply_event(TaskCompletedEvent(task_id="t1", duration_seconds=0.01), sequence=11)
    manager.evaluate()
    assert len(manager.active_view()) == 0
    assert len(manager.resolved_view()) == 1


def test_evaluate_does_not_double_fire_when_threshold_unchanged(
    _fresh_clock: RuntimeClock,
) -> None:
    registry = TaskRegistry()
    aggregator = RuntimeMetricsAggregator(registry, clock=_fresh_clock)
    detector = ExcessiveActiveTasksDetector(threshold=1)
    manager = RuntimeWarningManager(
        registry,
        aggregator=aggregator,
        clock=_fresh_clock,
        detectors=[detector],
    )
    aggregator.apply_event(TaskCreatedEvent(task_id="t0"), sequence=1)
    aggregator.apply_event(TaskCreatedEvent(task_id="t1"), sequence=2)
    manager.evaluate()
    first = manager.active_view()
    assert len(first) == 1
    # Calling evaluate again: same condition, same warning. Should refresh
    # (occurrence_count bumps) not create a second warning.
    manager.evaluate()
    after = manager.active_view()
    assert len(after) == 1
    assert after[0].occurrence_count >= 2


# ── Expiration ────────────────────────────────────────────────────────────


def test_expiration_marks_old_warning_expired(_fresh_clock: RuntimeClock) -> None:
    registry = TaskRegistry()
    aggregator = RuntimeMetricsAggregator(registry, clock=_fresh_clock)
    # Very short TTL so we can simulate expiration in-test.
    manager = RuntimeWarningManager(
        registry,
        aggregator=aggregator,
        clock=_fresh_clock,
        expiration=ExpirationPolicy(ttl_seconds=0.0),
    )
    manager.apply_event(TaskCompletedEvent(task_id="slow", duration_seconds=10.0), sequence=1)
    assert len(manager.active_view()) == 1
    manager.snapshot()  # sweep_expired runs here
    assert len(manager.active_view()) == 0
    assert len(manager.resolved_view()) == 1
    assert manager.resolved_view()[0].expired is True


# ── Snapshot ──────────────────────────────────────────────────────────────


def test_snapshot_round_trips_through_pydantic(manager: RuntimeWarningManager) -> None:
    manager.apply_event(TaskCompletedEvent(task_id="slow", duration_seconds=10.0), sequence=1)
    snap = manager.snapshot()
    assert isinstance(snap, WarningSnapshot)
    raw = snap.model_dump_json()
    rebuilt = WarningSnapshot.model_validate(json.loads(raw))
    assert len(rebuilt.active) == 1
    assert rebuilt.active[0].warning_type == "slow_task"
    assert rebuilt.counts_by_severity.warning == 1
    assert rebuilt.counts_by_type.get("slow_task") == 1


def test_snapshot_self_metrics_present(manager: RuntimeWarningManager) -> None:
    manager.apply_event(TaskCompletedEvent(task_id="slow", duration_seconds=10.0), sequence=1)
    snap = manager.snapshot()
    assert snap.self_metrics.warnings_emitted == 1
    assert snap.self_metrics.snapshots_emitted >= 1
    assert snap.self_metrics.detectors_registered == len(manager.detectors)


# ── Queries ───────────────────────────────────────────────────────────────


def test_query_get_warnings_for_task(manager: RuntimeWarningManager) -> None:
    manager.apply_event(TaskCompletedEvent(task_id="slow", duration_seconds=10.0), sequence=1)
    rows = manager.queries.get_warnings_for_task("slow")
    assert len(rows) == 1


def test_query_get_warnings_by_severity(manager: RuntimeWarningManager) -> None:
    manager.apply_event(TaskCompletedEvent(task_id="slow", duration_seconds=10.0), sequence=1)
    rows = manager.queries.get_warnings_by_severity(WarningSeverity.WARNING)
    assert len(rows) == 1
    assert rows[0].warning_type == "slow_task"


# ── Detector registry ─────────────────────────────────────────────────────


def test_detector_registry_rejects_duplicates(manager: RuntimeWarningManager) -> None:
    with pytest.raises(DetectorRegistrationError):
        manager.register_detector(SlowTaskDetector())


def test_detector_unregister(manager: RuntimeWarningManager) -> None:
    assert manager.unregister_detector("slow_task") is True
    # second time fails
    assert manager.unregister_detector("slow_task") is False


# ── State-store integration ───────────────────────────────────────────────


def test_manager_bound_to_state_store(_fresh_clock: RuntimeClock) -> None:
    store = RuntimeStateStore(TaskRegistry())
    aggregator = RuntimeMetricsAggregator(store.registry, clock=_fresh_clock)
    aggregator.bind(store)
    manager = RuntimeWarningManager(
        store.registry,
        aggregator=aggregator,
        clock=_fresh_clock,
    )
    manager.bind(store)
    store.apply(TaskCreatedEvent(task_id="t1"), sequence=1)
    store.apply(TaskCompletedEvent(task_id="t1", duration_seconds=10.0), sequence=2)
    active = manager.active_view()
    assert any(w.warning_type == "slow_task" for w in active)


# ── Rebuild ───────────────────────────────────────────────────────────────


def test_rebuild_clears_and_replays(manager: RuntimeWarningManager) -> None:
    manager.apply_event(TaskCompletedEvent(task_id="slow", duration_seconds=10.0), sequence=1)
    assert len(manager.active_view()) == 1
    manager.rebuild(())
    assert manager.active_view() == ()
    # Lifetime counters reset on rebuild.
    metrics = manager.self_metrics_snapshot()
    assert metrics.warnings_emitted == 0


# ── Severity counts projection ────────────────────────────────────────────


def test_count_by_severity_projection() -> None:
    warnings = [
        WarningLifecycle(
            warning_id=fresh_warning_id(),
            warning_key=f"k{i}",
            warning_type="t",
            severity=severity,
            detector="d",
            message="m",
            created_sequence=i + 1,
            created_monotonic_ns=100,
            created_at_wall=0.0,
            last_observed_sequence=i + 1,
            last_observed_monotonic_ns=100,
            last_observed_wall=0.0,
        )
        for i, severity in enumerate(
            [
                WarningSeverity.INFO,
                WarningSeverity.WARNING,
                WarningSeverity.WARNING,
                WarningSeverity.CRITICAL,
            ]
        )
    ]
    counts = count_by_severity(warnings)
    assert counts.info == 1
    assert counts.warning == 2
    assert counts.critical == 1
    assert counts.error == 0
