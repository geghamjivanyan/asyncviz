"""End-to-end :class:`RuntimeRecorder` lifecycle tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from asyncviz.replay.recording import (
    RecordingConfig,
    RecordingStream,
    RuntimeRecorder,
    export_session_to_zip,
    read_manifest,
)
from asyncviz.runtime.events import EventBus
from asyncviz.runtime.events.models import TaskCreatedEvent


@pytest.mark.asyncio
async def test_records_bus_events_and_finalizes_manifest(
    bus: EventBus, basic_config: RecordingConfig,
) -> None:
    recorder = RuntimeRecorder(config=basic_config, bus=bus)
    recorder.start()
    for i in range(5):
        bus.publish(TaskCreatedEvent(task_id=f"t-{i}", task_name=f"name-{i}"))
    await bus.join()
    recorder.stop()
    manifest = read_manifest(recorder.session_dir)
    assert manifest is not None
    assert manifest.finalized is True
    assert manifest.event_count == 5
    assert manifest.last_sequence == 5
    stream = RecordingStream(recorder.session_dir)
    frames = list(stream)
    assert len(frames) == 5
    assert [f.sequence for f in frames] == [1, 2, 3, 4, 5]
    for frame in frames:
        assert frame.event_type == "asyncio.task.created"
        assert frame.payload["event_type"] == "asyncio.task.created"


@pytest.mark.asyncio
async def test_start_is_idempotent(
    bus: EventBus, basic_config: RecordingConfig,
) -> None:
    recorder = RuntimeRecorder(config=basic_config, bus=bus)
    recorder.start()
    recorder.start()  # no-op
    recorder.stop()


@pytest.mark.asyncio
async def test_stop_is_idempotent(
    bus: EventBus, basic_config: RecordingConfig,
) -> None:
    recorder = RuntimeRecorder(config=basic_config, bus=bus)
    recorder.start()
    recorder.stop()
    recorder.stop()  # no-op


@pytest.mark.asyncio
async def test_snapshot_capture_at_start_and_stop(
    bus: EventBus, recording_root: Path,
) -> None:
    cfg = RecordingConfig(
        root_dir=recording_root,
        snapshot_on_start=True,
        snapshot_on_stop=True,
    )

    snapshot_payload = {"tasks": ["t-1", "t-2"], "tick": 0}

    def provider() -> dict:
        snapshot_payload["tick"] += 1
        return dict(snapshot_payload)

    recorder = RuntimeRecorder(
        config=cfg, bus=bus, snapshot_provider=provider,
    )
    recorder.start()
    bus.publish(TaskCreatedEvent(task_id="t-1", task_name="t-1"))
    await bus.join()
    recorder.stop()
    manifest = read_manifest(recorder.session_dir)
    assert manifest is not None
    assert manifest.snapshot_count == 2
    snapshot_dir = recorder.session_dir / "snapshots"
    assert len(list(snapshot_dir.glob("*.json"))) == 2


@pytest.mark.asyncio
async def test_high_throughput_workload_preserves_order(
    bus: EventBus, basic_config: RecordingConfig,
) -> None:
    recorder = RuntimeRecorder(config=basic_config, bus=bus)
    recorder.start()
    N = 200
    for i in range(N):
        bus.publish(TaskCreatedEvent(task_id=f"t-{i}", task_name=f"t-{i}"))
    await bus.join()
    recorder.stop()
    frames = list(RecordingStream(recorder.session_dir))
    assert len(frames) == N
    assert [f.sequence for f in frames] == list(range(1, N + 1))


@pytest.mark.asyncio
async def test_rotation_creates_multiple_chunks(
    bus: EventBus, recording_root: Path,
) -> None:
    cfg = RecordingConfig(
        root_dir=recording_root,
        buffer_capacity=128,
        flush_interval_seconds=0.05,
        max_chunk_events=10,
        max_chunk_bytes=0,
        snapshot_on_start=False,
        snapshot_on_stop=False,
    )
    recorder = RuntimeRecorder(config=cfg, bus=bus)
    recorder.start()
    for i in range(30):
        bus.publish(TaskCreatedEvent(task_id=f"t-{i}", task_name=f"t-{i}"))
    await bus.join()
    recorder.stop()
    chunks = sorted((recorder.session_dir / "events").glob("*.ndjson"))
    assert len(chunks) >= 3
    # Replay still observes all events in order.
    frames = list(RecordingStream(recorder.session_dir))
    assert len(frames) == 30
    assert [f.sequence for f in frames] == list(range(1, 31))


@pytest.mark.asyncio
async def test_recorder_without_bus_supports_manual_append(
    basic_config: RecordingConfig,
) -> None:
    recorder = RuntimeRecorder(config=basic_config, bus=None)
    recorder.start()
    for i in range(3):
        recorder.append_event(
            TaskCreatedEvent(task_id=f"t-{i}", task_name=f"name-{i}"),
        )
    recorder.stop()
    frames = list(RecordingStream(recorder.session_dir))
    assert [f.sequence for f in frames] == [1, 2, 3]


@pytest.mark.asyncio
async def test_export_session_to_zip_round_trip(
    bus: EventBus, basic_config: RecordingConfig, tmp_path: Path,
) -> None:
    recorder = RuntimeRecorder(config=basic_config, bus=bus)
    recorder.start()
    bus.publish(TaskCreatedEvent(task_id="t-1", task_name="t-1"))
    await bus.join()
    recorder.stop()
    bundle = tmp_path / "bundle.zip"
    result = export_session_to_zip(recorder.session_dir, bundle)
    assert bundle.exists()
    assert result.files_included >= 2  # manifest + 1 chunk minimum


@pytest.mark.asyncio
async def test_recorder_disable_does_not_emit_events(
    bus: EventBus, basic_config: RecordingConfig,
) -> None:
    """Recorder that never starts records nothing — no manifest, no
    chunks, no error from the bus path."""
    recorder = RuntimeRecorder(config=basic_config, bus=bus)
    # Don't start.
    bus.publish(TaskCreatedEvent(task_id="t-1", task_name="t-1"))
    await bus.join()
    chunks = list((recorder.session_dir / "events").glob("*.ndjson"))
    # The writer pre-creates an empty chunk file during construction,
    # but no events should have been written.
    for chunk in chunks:
        assert chunk.stat().st_size == 0
