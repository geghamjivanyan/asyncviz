from __future__ import annotations

import json
import threading

import pytest
from fastapi.testclient import TestClient

from asyncviz.config import AsyncVizConfig
from asyncviz.dashboard import create_app
from asyncviz.dashboard.snapshots import (
    SNAPSHOT_PROTOCOL_VERSION,
    HydrationOptions,
    RuntimeSnapshot,
    SnapshotConsistency,
    SnapshotMetadata,
    SnapshotMetrics,
    SnapshotService,
)
from asyncviz.runtime.clock import (
    RuntimeClock,
    reset_runtime_clock,
    set_default_runtime_clock,
)
from asyncviz.runtime.events.models import (
    TaskCompletedEvent,
    TaskCreatedEvent,
    TaskStartedEvent,
)
from asyncviz.runtime.metrics import RuntimeMetricsAggregator
from asyncviz.runtime.replay import EventReplayBuffer
from asyncviz.runtime.state import RuntimeStateStore
from asyncviz.runtime.tasks import TaskRegistry
from asyncviz.runtime.timeline import TimelineSegmentEngine
from asyncviz.runtime.warnings import RuntimeWarningManager


@pytest.fixture(autouse=True)
def _fresh_clock():
    reset_runtime_clock()
    clock = RuntimeClock()
    set_default_runtime_clock(clock)
    yield clock
    reset_runtime_clock()


def _build_service(_fresh_clock: RuntimeClock) -> tuple[SnapshotService, RuntimeStateStore]:
    """Construct a SnapshotService bound to a fresh in-process runtime.

    Uses the real services (no fakes) so determinism + composition can
    be tested against the same code paths the dashboard uses.
    """
    registry = TaskRegistry()
    state_store = RuntimeStateStore(registry, clock=_fresh_clock)
    timeline = TimelineSegmentEngine(clock=_fresh_clock)
    aggregator = RuntimeMetricsAggregator(
        registry,
        clock=_fresh_clock,
        timeline_engine=timeline,
    )
    warnings = RuntimeWarningManager(
        registry,
        aggregator=aggregator,
        clock=_fresh_clock,
    )
    replay = EventReplayBuffer(clock=_fresh_clock)
    # Wire each sink onto the store's state-change stream so the snapshot
    # sees a consistent view across sources.
    timeline.bind(state_store)
    aggregator.bind(state_store)
    warnings.bind(state_store)
    replay.bind(state_store)

    service = SnapshotService(
        clock=_fresh_clock,
        state_store=state_store,
        timeline_engine=timeline,
        metrics_aggregator=aggregator,
        warning_manager=warnings,
        replay_buffer=replay,
    )
    return service, state_store


def _apply(store: RuntimeStateStore, clock: RuntimeClock, event) -> int:
    """Apply ``event`` via ``store`` with a freshly allocated sequence.

    In production the queue allocates sequences at publish time; tests
    that bypass the queue replicate the same shape by pulling one off
    the clock directly.
    """
    sequence = clock.next_sequence()
    store.apply(event, sequence=sequence)
    return sequence


# ── HydrationOptions ──────────────────────────────────────────────────────


def test_hydration_options_default_is_full() -> None:
    opts = HydrationOptions()
    assert opts.is_full is True


def test_hydration_options_any_off_makes_filtered() -> None:
    assert HydrationOptions(include_timeline=False).is_full is False
    assert HydrationOptions(include_metrics=False).is_full is False
    assert HydrationOptions(include_replay=False).is_full is False


# ── SnapshotMetrics ───────────────────────────────────────────────────────


def test_snapshot_metrics_records_durations_and_sizes() -> None:
    metrics = SnapshotMetrics()
    metrics.record_generation(
        duration_ns=1_000_000, payload_bytes=4096, filtered=False, sources_skipped=0
    )
    metrics.record_generation(
        duration_ns=3_000_000, payload_bytes=8192, filtered=True, sources_skipped=2
    )
    snap = metrics.snapshot()
    assert snap.snapshots_generated == 2
    assert snap.full_snapshots == 1
    assert snap.filtered_snapshots == 1
    assert snap.total_generation_ns == 4_000_000
    assert snap.max_generation_ns == 3_000_000
    assert snap.last_generation_ns == 3_000_000
    assert snap.last_payload_bytes == 8192
    assert snap.max_payload_bytes == 8192
    assert snap.sources_skipped == 2
    assert snap.average_generation_ns == pytest.approx(2_000_000.0)


def test_snapshot_metrics_reset_clears() -> None:
    metrics = SnapshotMetrics()
    metrics.record_generation(duration_ns=10, payload_bytes=10, filtered=False, sources_skipped=0)
    metrics.reset()
    assert metrics.snapshot().snapshots_generated == 0


# ── SnapshotService.capture: shape + identity ─────────────────────────────


def test_capture_full_snapshot_shape(_fresh_clock: RuntimeClock) -> None:
    service, _ = _build_service(_fresh_clock)
    snap = service.capture()
    assert isinstance(snap, RuntimeSnapshot)
    assert isinstance(snap.metadata, SnapshotMetadata)
    assert isinstance(snap.consistency, SnapshotConsistency)
    assert snap.metadata.snapshot_version == SNAPSHOT_PROTOCOL_VERSION
    assert snap.metadata.is_full is True
    assert snap.metadata.runtime_id == str(_fresh_clock.runtime_id)
    # Every sub-snapshot is materialized when ``is_full`` is true.
    assert snap.state is not None
    assert snap.timeline is not None
    assert snap.metrics is not None
    assert snap.warnings is not None
    assert snap.replay is not None
    assert snap.clock is not None


def test_capture_metadata_includes_payload_bytes_and_duration(
    _fresh_clock: RuntimeClock,
) -> None:
    service, _ = _build_service(_fresh_clock)
    snap = service.capture()
    assert snap.metadata.payload_bytes > 0
    # Payload size should match the actual serialized JSON the endpoint emits.
    serialized = snap.model_dump_json()
    # The size measurement uses the same path; allow a small delta because
    # the metadata is updated in place after measurement (snapshot_id
    # changes nothing, but duration_ns + payload_bytes are now non-zero).
    assert abs(len(serialized) - snap.metadata.payload_bytes) < 200
    assert snap.metadata.generation_duration_ns > 0


def test_capture_metadata_classifies_included_and_skipped(
    _fresh_clock: RuntimeClock,
) -> None:
    service, _ = _build_service(_fresh_clock)
    snap = service.capture(
        HydrationOptions(
            include_timeline=False,
            include_metrics=False,
            include_replay=False,
        )
    )
    assert snap.timeline is None
    assert snap.metrics is None
    assert snap.replay is None
    assert "timeline" in snap.metadata.skipped_sources
    assert "metrics" in snap.metadata.skipped_sources
    assert "replay" in snap.metadata.skipped_sources
    assert "state" in snap.metadata.included_sources
    assert snap.metadata.is_full is False
    # Sources are sorted so the wire representation is deterministic.
    assert snap.metadata.included_sources == sorted(snap.metadata.included_sources)
    assert snap.metadata.skipped_sources == sorted(snap.metadata.skipped_sources)


def test_capture_consistency_pins_last_sequence(_fresh_clock: RuntimeClock) -> None:
    service, store = _build_service(_fresh_clock)
    _apply(store, _fresh_clock, TaskCreatedEvent(task_id="t1"))
    _apply(store, _fresh_clock, TaskStartedEvent(task_id="t1"))
    _apply(store, _fresh_clock, TaskCompletedEvent(task_id="t1", duration_seconds=0.1))
    snap = service.capture()
    assert snap.consistency.last_sequence == _fresh_clock.current_sequence
    assert snap.state is not None
    assert snap.state.last_sequence == snap.consistency.last_sequence


def test_capture_consistency_carries_last_event_id(_fresh_clock: RuntimeClock) -> None:
    service, store = _build_service(_fresh_clock)
    _apply(store, _fresh_clock, TaskCreatedEvent(task_id="t1"))
    snap = service.capture()
    assert snap.state is not None
    assert snap.consistency.last_event_id == snap.state.last_event_id


# ── Determinism + immutability ────────────────────────────────────────────


def test_capture_back_to_back_is_idempotent_modulo_clock(
    _fresh_clock: RuntimeClock,
) -> None:
    service, store = _build_service(_fresh_clock)
    _apply(store, _fresh_clock, TaskCreatedEvent(task_id="t1"))
    snap_a = service.capture()
    snap_b = service.capture()
    # ``last_sequence`` is stable when no events fired between captures.
    assert snap_a.consistency.last_sequence == snap_b.consistency.last_sequence
    # Materialized content is identical — only the generation timestamps
    # in each sub-snapshot differ between back-to-back captures.
    assert snap_a.state is not None and snap_b.state is not None
    assert snap_a.state.tasks == snap_b.state.tasks
    assert snap_a.state.last_event_id == snap_b.state.last_event_id
    # Metadata identity changes per-capture (snapshot_id is fresh each time).
    assert snap_a.metadata.snapshot_id != snap_b.metadata.snapshot_id


def test_runtime_snapshot_is_frozen(_fresh_clock: RuntimeClock) -> None:
    from pydantic import ValidationError

    service, _ = _build_service(_fresh_clock)
    snap = service.capture()
    with pytest.raises(ValidationError):
        snap.metadata.snapshot_id = "mutated"  # type: ignore[misc]


def test_runtime_snapshot_serializes_to_stable_json(
    _fresh_clock: RuntimeClock,
) -> None:
    service, store = _build_service(_fresh_clock)
    _apply(store, _fresh_clock, TaskCreatedEvent(task_id="t1"))
    snap = service.capture()
    # Stable means the same model dumps to byte-identical JSON twice.
    payload_a = snap.model_dump_json()
    payload_b = snap.model_dump_json()
    assert payload_a == payload_b
    # And parseable.
    json.loads(payload_a)


# ── Replay-window awareness ───────────────────────────────────────────────


def test_capture_marks_replay_window_hit_when_cursor_in_retention(
    _fresh_clock: RuntimeClock,
) -> None:
    service, store = _build_service(_fresh_clock)
    _apply(store, _fresh_clock, TaskCreatedEvent(task_id="t1"))
    _apply(store, _fresh_clock, TaskCreatedEvent(task_id="t2"))
    # ``since_sequence`` must be >= the buffer's oldest retained sequence.
    oldest = service.capture().consistency.oldest_retained_sequence
    assert oldest is not None
    snap = service.capture(HydrationOptions(since_sequence=oldest))
    assert snap.consistency.replay_window_hit is True


def test_capture_marks_replay_window_miss_when_cursor_before_retention(
    _fresh_clock: RuntimeClock,
) -> None:
    service, _store = _build_service(_fresh_clock)
    # No events applied → oldest_sequence is None → miss is expected.
    snap = service.capture(HydrationOptions(since_sequence=5))
    assert snap.consistency.replay_window_hit is False


# ── Concurrency: serializes captures ──────────────────────────────────────


def test_concurrent_captures_complete_cleanly(_fresh_clock: RuntimeClock) -> None:
    service, store = _build_service(_fresh_clock)
    for i in range(5):
        _apply(store, _fresh_clock, TaskCreatedEvent(task_id=f"t{i}"))

    results: list[RuntimeSnapshot] = []
    errors: list[Exception] = []

    def worker():
        try:
            results.append(service.capture())
        except Exception as exc:  # surfacing thread-internal exceptions
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert len(results) == 8
    # Each capture must see the same ``last_sequence`` because nothing
    # mutates the runtime between them — proves the lock serializes.
    sequences = {snap.consistency.last_sequence for snap in results}
    assert sequences == {_fresh_clock.current_sequence}


# ── /api/runtime/snapshot endpoint ────────────────────────────────────────


@pytest.fixture
def app():
    return create_app(AsyncVizConfig(frontend_mode="api-only"))


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


def test_snapshot_endpoint_returns_canonical_shape(client) -> None:
    response = client.get("/api/runtime/snapshot")
    assert response.status_code == 200
    data = response.json()
    assert "metadata" in data
    assert "consistency" in data
    assert "clock" in data
    assert data["metadata"]["snapshot_version"] == SNAPSHOT_PROTOCOL_VERSION
    assert data["metadata"]["is_full"] is True
    # All sub-snapshots present in full mode.
    for key in ("state", "timeline", "metrics", "warnings", "replay", "queue"):
        assert data[key] is not None


def test_snapshot_endpoint_runtime_id_matches_clock(client) -> None:
    data = client.get("/api/runtime/snapshot").json()
    assert data["metadata"]["runtime_id"] == data["clock"]["runtime_id"]


def test_snapshot_endpoint_consistency_pins_last_sequence(client) -> None:
    data = client.get("/api/runtime/snapshot").json()
    assert data["consistency"]["last_sequence"] == data["state"]["last_sequence"]


def test_snapshot_endpoint_filters_via_query_params(client) -> None:
    response = client.get("/api/runtime/snapshot?include_timeline=false&include_replay=false")
    data = response.json()
    assert data["timeline"] is None
    assert data["replay"] is None
    assert data["metadata"]["is_full"] is False
    assert "timeline" in data["metadata"]["skipped_sources"]
    assert "replay" in data["metadata"]["skipped_sources"]


def test_snapshot_endpoint_evaluates_warnings_by_default(client) -> None:
    data = client.get("/api/runtime/snapshot").json()
    assert data["warnings"] is not None
    # ``active`` exists and is a list; even empty it must serialize as [].
    assert isinstance(data["warnings"]["active"], list)


def test_snapshot_endpoint_since_sequence_records_window_status(client) -> None:
    data = client.get("/api/runtime/snapshot?since_sequence=999999").json()
    assert data["consistency"]["replay_window_hit"] is False


# ── /api/runtime/snapshot/metrics endpoint ────────────────────────────────


def test_snapshot_metrics_endpoint_counts_generations(client) -> None:
    # Generate three snapshots — two full, one filtered.
    client.get("/api/runtime/snapshot")
    client.get("/api/runtime/snapshot")
    client.get("/api/runtime/snapshot?include_timeline=false")
    response = client.get("/api/runtime/snapshot/metrics")
    assert response.status_code == 200
    data = response.json()
    assert data["snapshots_generated"] >= 3
    assert data["full_snapshots"] >= 2
    assert data["filtered_snapshots"] >= 1
    assert data["average_generation_ns"] > 0
    assert data["last_payload_bytes"] > 0


# ── Wiring: service is reachable through BackendAppState ─────────────────


def test_backend_state_exposes_snapshot_service(app) -> None:
    assert app.state.backend.snapshot_service is app.state.snapshot_service


def test_snapshot_service_metrics_increments_on_capture(app) -> None:
    service = app.state.snapshot_service
    before = service.metrics_snapshot().snapshots_generated
    service.capture()
    service.capture()
    after = service.metrics_snapshot().snapshots_generated
    assert after - before == 2
