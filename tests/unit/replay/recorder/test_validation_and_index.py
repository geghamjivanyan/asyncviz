from __future__ import annotations

import json
from pathlib import Path

from asyncviz.runtime.events.models import GenericEvent
from asyncviz.runtime.replay.artifacts import build_index, open_bundle, validate_bundle
from asyncviz.runtime.replay.artifacts.replay_layout import INCOMPLETE_MARKER
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


def _meta() -> RuntimeMeta:
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


def _ch(seq: int) -> StateChange:
    ev = GenericEvent(event_type="asyncio.task.created", payload={"i": seq})
    return StateChange(
        event=ev,
        sequence=seq,
        last_sequence=seq,
        decision="APPLY",
        event_type=ev.event_type,
        event_id=str(ev.event_id),
    )


def _record(tmp_path: Path, *, chunk_events: int = 2, n: int = 5) -> Path:
    cfg = RecorderConfig(
        output_path=tmp_path / "session.avz",
        compression=CompressionMode.NONE,
        chunk_events=chunk_events,
        chunk_bytes=0,
    )
    store = _StubStore()
    rec = ReplayRecorder(cfg, state_store=store)
    rec.start(runtime_meta=_meta)
    for i in range(1, n + 1):
        store.listener(_ch(i))
    rec.stop()
    return cfg.output_path


def test_validate_bundle_clean(tmp_path: Path) -> None:
    root = _record(tmp_path)
    report = validate_bundle(root)
    assert report.ok
    assert report.chunk_count > 0
    assert report.event_count == 5
    assert report.finalized is True


def test_validate_bundle_detects_missing_chunk(tmp_path: Path) -> None:
    root = _record(tmp_path)
    bundle = open_bundle(root)
    first_chunk = bundle.manifest.chunks[0]
    (root / first_chunk.file).unlink()
    report = validate_bundle(root)
    assert not report.ok
    assert any(issue.code == "missing-chunk" for issue in report.errors)


def test_validate_bundle_detects_hash_mismatch(tmp_path: Path) -> None:
    root = _record(tmp_path)
    bundle = open_bundle(root)
    chunk_path = root / bundle.manifest.chunks[0].file
    chunk_path.write_bytes(b"tampered\n")
    report = validate_bundle(root)
    assert not report.ok
    assert any(issue.code in {"hash-mismatch", "size-mismatch"} for issue in report.errors)


def test_validate_bundle_warns_on_incomplete_marker(tmp_path: Path) -> None:
    root = _record(tmp_path)
    (root / INCOMPLETE_MARKER).write_text("synthesised\n")
    report = validate_bundle(root)
    assert report.ok  # warnings only
    assert any(issue.code == "incomplete" for issue in report.warnings)


def test_validate_bundle_handles_missing_root(tmp_path: Path) -> None:
    report = validate_bundle(tmp_path / "nope.avz")
    assert not report.ok
    assert any(issue.code == "missing" for issue in report.errors)


def test_index_resolves_chunk_by_sequence(tmp_path: Path) -> None:
    root = _record(tmp_path, chunk_events=2, n=5)
    bundle = open_bundle(root)
    index = build_index(bundle.manifest)
    found = index.chunk_for(3)
    assert found is not None
    assert found.chunk.sequence_start <= 3 <= found.chunk.sequence_end
    assert index.chunk_for(0) is None
    assert index.chunk_for(99) is None


def test_manifest_round_trip(tmp_path: Path) -> None:
    root = _record(tmp_path)
    bundle = open_bundle(root)
    manifest_payload = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest_payload["schema_version"] == 1
    assert manifest_payload["finalized"] is True
    assert manifest_payload["event_count"] == bundle.manifest.event_count
