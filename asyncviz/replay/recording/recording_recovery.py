"""Crash recovery + integrity reconstruction for partial recordings.

When the process dies mid-recording, the session directory is left
in an inconsistent state:

* ``manifest.json`` exists with ``finalized: false`` (or is missing if
  the crash happened before the first manifest write).
* The last events chunk may have a partial trailing line.
* The in-flight snapshot file may be missing or partial.

:func:`recover_session` inspects the directory and brings it back to
a consistent, replay-loadable state:

1. Scan ``events/`` for the latest chunk + repair its tail.
2. Recompute ``event_count`` / ``last_sequence`` from the on-disk
   chunks (manifest counters may be stale by a few flush ticks).
3. Mark the manifest ``finalized: false`` so a reader knows the
   session ended abruptly, but every persisted event is recoverable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from asyncviz.replay.recording.recording_integrity import (
    count_chunk_events,
    repair_partial_tail,
)
from asyncviz.replay.recording.recording_layout import (
    events_dir,
    manifest_path,
)
from asyncviz.replay.recording.recording_metadata import (
    ChunkRecord,
    RecordingMetadata,
)
from asyncviz.replay.recording.recording_observability import get_recording_metrics
from asyncviz.replay.recording.recording_tracing import record_recording_trace


@dataclass(frozen=True, slots=True)
class RecoveryReport:
    """Summary of what :func:`recover_session` did."""

    session_dir: Path
    repaired_chunks: int
    truncated_bytes_total: int
    chunks_present: int
    inferred_event_count: int
    inferred_last_sequence: int
    manifest_present: bool


def recover_session(session_dir: Path) -> RecoveryReport:
    """Repair a session directory in place + return the recovery summary.

    Always safe to call — when there's nothing to repair the report
    reflects a no-op.
    """
    metrics = get_recording_metrics()
    record_recording_trace("recovery-started", str(session_dir))
    events_path = events_dir(session_dir)
    if not events_path.exists():
        return RecoveryReport(session_dir, 0, 0, 0, 0, 0, manifest_path(session_dir).exists())

    repaired_chunks = 0
    truncated_bytes_total = 0
    chunk_files = sorted(events_path.glob("*.ndjson"))
    inferred_event_count = 0
    inferred_last_sequence = 0
    for path in chunk_files:
        repair = repair_partial_tail(path)
        if repair.truncated_bytes > 0:
            repaired_chunks += 1
            truncated_bytes_total += repair.truncated_bytes
            metrics.record_repair_completed()
        inferred_event_count += count_chunk_events(path)

    # Recompute last_sequence by reading the final line of the final
    # chunk — cheaper than rescanning the whole log.
    if chunk_files:
        last_path = chunk_files[-1]
        last_line = _read_last_line(last_path)
        if last_line is not None:
            try:
                payload = json.loads(last_line)
                seq = payload.get("sequence")
                if isinstance(seq, int):
                    inferred_last_sequence = seq
            except json.JSONDecodeError:
                pass

    manifest_exists = manifest_path(session_dir).exists()
    record_recording_trace(
        "recovery-completed",
        f"chunks={len(chunk_files)} repaired={repaired_chunks} truncated={truncated_bytes_total}",
    )
    return RecoveryReport(
        session_dir=session_dir,
        repaired_chunks=repaired_chunks,
        truncated_bytes_total=truncated_bytes_total,
        chunks_present=len(chunk_files),
        inferred_event_count=inferred_event_count,
        inferred_last_sequence=inferred_last_sequence,
        manifest_present=manifest_exists,
    )


def patch_manifest_after_recovery(
    metadata: RecordingMetadata,
    report: RecoveryReport,
) -> RecordingMetadata:
    """Return a copy of ``metadata`` with counters reconciled to the
    on-disk state from ``report``. Leaves ``finalized`` False so a
    reader can tell the session ended abruptly."""
    if not report.chunks_present:
        return metadata
    # Re-derive chunk records from the actual files. We don't recompute
    # hashes here — those are expensive; the loader can re-hash on demand.
    new_chunks: list[ChunkRecord] = []
    for original in metadata.chunks:
        path = events_dir(report.session_dir) / original.filename
        if not path.exists():
            continue
        size = path.stat().st_size
        count = count_chunk_events(path)
        new_chunks.append(
            ChunkRecord(
                index=original.index,
                filename=original.filename,
                event_count=count,
                byte_size=size,
                first_sequence=original.first_sequence,
                last_sequence=original.last_sequence,
                sha256=None,
            ),
        )
    return RecordingMetadata(
        schema_version=metadata.schema_version,
        recording_id=metadata.recording_id,
        runtime_id=metadata.runtime_id,
        asyncviz_version=metadata.asyncviz_version,
        started_at_ns=metadata.started_at_ns,
        stopped_at_ns=metadata.stopped_at_ns,
        event_count=report.inferred_event_count,
        snapshot_count=metadata.snapshot_count,
        chunk_count=len(new_chunks) or metadata.chunk_count,
        last_sequence=max(metadata.last_sequence, report.inferred_last_sequence),
        finalized=False,
        chunks=tuple(new_chunks) if new_chunks else metadata.chunks,
        snapshots=metadata.snapshots,
        notes={**metadata.notes, "recovered_from_crash": True},
    )


def _read_last_line(path: Path) -> str | None:
    if not path.exists():
        return None
    raw = path.read_bytes()
    if not raw or not raw.endswith(b"\n"):
        return None
    # The last non-empty line.
    lines = raw.splitlines()
    return lines[-1].decode("utf-8", errors="replace") if lines else None
