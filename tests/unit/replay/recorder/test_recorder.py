from __future__ import annotations

from pathlib import Path

from asyncviz.runtime.events.models import GenericEvent
from asyncviz.runtime.replay.artifacts import open_bundle, validate_bundle
from asyncviz.runtime.replay.recorder import (
    CompressionMode,
    RecorderConfig,
    ReplayRecorder,
)
from asyncviz.runtime.replay.recorder.replay_metadata import RuntimeMeta
from asyncviz.runtime.state.subscriptions import StateChange


class _StubStore:
    def __init__(self) -> None:
        self.listener = None

    def subscribe(self, listener):
        self.listener = listener
        return ("sub", listener)

    def unsubscribe(self, sub) -> bool:
        self.listener = None
        return True


def _make_change(seq: int, event_type: str = "asyncio.task.created") -> StateChange:
    event = GenericEvent(event_type=event_type, payload={"seq": seq})
    return StateChange(
        event=event,
        sequence=seq,
        last_sequence=seq,
        decision="APPLY",
        event_type=event.event_type,
        event_id=str(event.event_id),
    )


def _runtime_meta_provider() -> RuntimeMeta:
    return RuntimeMeta(
        runtime_id="rt-x",
        asyncviz_version="0.0.0",
        started_at_wall_iso="",
        finished_at_wall_iso=None,
        started_at_monotonic_ns=0,
        finished_at_monotonic_ns=None,
        host="127.0.0.1",
        port=8877,
        target={"kind": "module", "value": "json", "argv": ["json"]},
    )


def test_recorder_writes_chunks_and_finalizes(tmp_path: Path) -> None:
    cfg = RecorderConfig(
        output_path=tmp_path / "session.avz",
        compression=CompressionMode.NONE,
        chunk_events=2,
        chunk_bytes=0,
        flush_interval_seconds=0.05,
    )
    store = _StubStore()
    recorder = ReplayRecorder(cfg, state_store=store)
    recorder.start(runtime_meta=_runtime_meta_provider)
    for seq in range(1, 6):
        store.listener(_make_change(seq))
    recorder.stop()

    assert recorder.statistics.events_recorded == 5
    assert recorder.statistics.chunks_written == 3  # 2+2+1
    assert recorder.statistics.finalized_cleanly is True

    bundle = open_bundle(cfg.output_path)
    assert bundle.manifest.event_count == 5
    assert len(bundle.manifest.chunks) == 3
    assert bundle.manifest.first_sequence == 1
    assert bundle.manifest.last_sequence == 5
    assert bundle.is_finalized

    seqs = [f["sequence"] for f in bundle.iter_frames()]
    assert seqs == [1, 2, 3, 4, 5]


def test_recorder_filters_events(tmp_path: Path) -> None:
    cfg = RecorderConfig(
        output_path=tmp_path / "session.avz",
        compression=CompressionMode.NONE,
        chunk_events=10,
        chunk_bytes=0,
        include_event_types=("asyncio.task.created",),
    )
    store = _StubStore()
    recorder = ReplayRecorder(cfg, state_store=store)
    recorder.start(runtime_meta=_runtime_meta_provider)
    store.listener(_make_change(1, "asyncio.task.created"))
    store.listener(_make_change(2, "asyncio.task.completed"))  # filtered out
    store.listener(_make_change(3, "asyncio.task.created"))
    recorder.stop()
    assert recorder.statistics.events_recorded == 2
    assert recorder.statistics.events_filtered == 1


def test_recorder_writes_runtime_snapshot(tmp_path: Path) -> None:
    cfg = RecorderConfig(
        output_path=tmp_path / "session.avz",
        compression=CompressionMode.NONE,
        chunk_events=10,
        chunk_bytes=0,
        capture_runtime_snapshot=True,
    )
    store = _StubStore()
    recorder = ReplayRecorder(cfg, state_store=store)
    payload = {"hello": "world", "n": 42}
    recorder.start(
        runtime_meta=_runtime_meta_provider,
        runtime_snapshot=lambda: payload,
    )
    store.listener(_make_change(1))
    recorder.stop()
    snap = open_bundle(cfg.output_path).load_snapshot("runtime")
    assert snap == payload


def test_recorder_marks_incomplete_until_finalize(tmp_path: Path) -> None:
    cfg = RecorderConfig(
        output_path=tmp_path / "session.avz",
        compression=CompressionMode.NONE,
        chunk_events=10,
        chunk_bytes=0,
    )
    store = _StubStore()
    recorder = ReplayRecorder(cfg, state_store=store)
    recorder.start(runtime_meta=_runtime_meta_provider)
    incomplete_marker = cfg.output_path / "INCOMPLETE"
    assert incomplete_marker.exists()
    recorder.stop()
    assert not incomplete_marker.exists()


def test_recorder_writes_recorder_meta(tmp_path: Path) -> None:
    cfg = RecorderConfig(
        output_path=tmp_path / "session.avz",
        compression=CompressionMode.NONE,
        chunk_events=10,
        chunk_bytes=0,
        metadata_overrides=(("ci_branch", "main"), ("ci_build", "abc123")),
    )
    store = _StubStore()
    recorder = ReplayRecorder(cfg, state_store=store)
    recorder.start(runtime_meta=_runtime_meta_provider)
    recorder.stop()
    bundle = open_bundle(cfg.output_path)
    assert bundle.manifest.extras == {"ci_branch": "main", "ci_build": "abc123"}
    recorder_meta = bundle.load_meta("recorder")
    assert recorder_meta is not None
    assert recorder_meta["config"]["chunk_events"] == 10


def test_recorder_validation_passes(tmp_path: Path) -> None:
    cfg = RecorderConfig(
        output_path=tmp_path / "session.avz",
        compression=CompressionMode.GZIP,
        chunk_events=2,
        chunk_bytes=0,
    )
    store = _StubStore()
    recorder = ReplayRecorder(cfg, state_store=store)
    recorder.start(runtime_meta=_runtime_meta_provider)
    for i in range(1, 4):
        store.listener(_make_change(i))
    recorder.stop()
    report = validate_bundle(cfg.output_path)
    assert report.ok
    assert report.event_count == 3


def test_recorder_idempotent_stop(tmp_path: Path) -> None:
    cfg = RecorderConfig(
        output_path=tmp_path / "session.avz",
        compression=CompressionMode.NONE,
        chunk_events=10,
        chunk_bytes=0,
    )
    store = _StubStore()
    recorder = ReplayRecorder(cfg, state_store=store)
    recorder.start(runtime_meta=_runtime_meta_provider)
    recorder.stop()
    recorder.stop()  # must not raise / duplicate-finalize


def test_recorder_serialized_payload_round_trips(tmp_path: Path) -> None:
    cfg = RecorderConfig(
        output_path=tmp_path / "session.avz",
        compression=CompressionMode.GZIP,
        chunk_events=10,
        chunk_bytes=0,
    )
    store = _StubStore()
    recorder = ReplayRecorder(cfg, state_store=store)
    recorder.start(runtime_meta=_runtime_meta_provider)
    store.listener(_make_change(42))
    recorder.stop()
    bundle = open_bundle(cfg.output_path)
    frames = list(bundle.iter_frames())
    assert len(frames) == 1
    assert frames[0]["sequence"] == 42
    assert frames[0]["event_type"] == "asyncio.task.created"
    # ``payload`` field is the inner event payload kwargs (not the wrapper).
    assert frames[0]["payload"].get("payload") == {"seq": 42}
