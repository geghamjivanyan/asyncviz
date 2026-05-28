"""Seek operations — by sequence and by timestamp.

The seek API is structured around a *plan*:

1. Pick a snapshot ≤ target (via the snapshot index).
2. Pick the chunk that contains the target (via the sequence index).
3. Iterate chunks from there, dropping frames until the cursor
   lands on the target.

That plan is the same for sequence and timestamp seeks; only the
target predicate differs. So we expose one engine
(:class:`SeekEngine`) and two thin entry points
(:func:`seek_to_sequence`, :func:`seek_to_timestamp`).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from asyncviz.replay.format import ReplayFrame
from asyncviz.replay.loading.models.frame_adapter import FrameAdapter
from asyncviz.replay.loading.replay_chunk_loader import ReplayChunkLoader
from asyncviz.replay.loading.replay_cursor import ReplayCursor
from asyncviz.replay.loading.replay_index import ReplayIndex
from asyncviz.replay.loading.replay_observability import get_loader_metrics
from asyncviz.replay.loading.replay_snapshot_index import (
    ReplaySnapshotIndex,
    SnapshotEntry,
)
from asyncviz.replay.loading.replay_tracing import record_replay_trace
from asyncviz.replay.recording.recording_metadata import ChunkRecord


@dataclass(frozen=True, slots=True)
class SeekPlan:
    """The chunks + snapshot a seek will use."""

    starting_chunk_index: int
    """1-based index of the first chunk to read. ``0`` when no chunk
    contains the target (e.g. seek beyond the recording)."""

    snapshot: SnapshotEntry | None
    chunks_to_scan: int


@dataclass(frozen=True, slots=True)
class SeekResult:
    """Outcome of a seek — the cursor + the frame it landed on."""

    cursor: ReplayCursor
    landed_frame: ReplayFrame | None
    chunks_scanned: int
    """How many chunks the seek had to walk to land on the target."""


def plan_sequence_seek(
    target_sequence: int,
    *,
    sequence_index: ReplayIndex,
    snapshot_index: ReplaySnapshotIndex,
    chunks: tuple[ChunkRecord, ...],
) -> SeekPlan:
    """Return the plan for landing on ``target_sequence``."""
    entry = sequence_index.chunk_for_sequence(target_sequence)
    if entry is None:
        return SeekPlan(starting_chunk_index=0, snapshot=None, chunks_to_scan=0)
    chunks_to_scan = sum(
        1 for c in chunks if c.index >= entry.chunk_index
    )
    snapshot = snapshot_index.nearest_at_or_before(target_sequence)
    return SeekPlan(
        starting_chunk_index=entry.chunk_index,
        snapshot=snapshot,
        chunks_to_scan=chunks_to_scan,
    )


def execute_seek(
    plan: SeekPlan,
    *,
    chunks: tuple[ChunkRecord, ...],
    chunk_paths: tuple[Path, ...],
    adapter: FrameAdapter,
    target_predicate: Callable[[ReplayFrame], bool],
    strict: bool = False,
) -> SeekResult:
    """Walk the plan and return the cursor landed on the first frame
    matching ``target_predicate``."""
    cursor = ReplayCursor.at_start()
    if plan.starting_chunk_index == 0:
        return SeekResult(cursor=cursor, landed_frame=None, chunks_scanned=0)
    chunks_scanned = 0
    for chunk_record, chunk_path in zip(chunks, chunk_paths, strict=True):
        if chunk_record.index < plan.starting_chunk_index:
            continue
        loader = ReplayChunkLoader(
            chunk_record, chunk_path, adapter=adapter, strict=strict,
        )
        chunks_scanned += 1
        for frame in loader.iter_frames():
            if target_predicate(frame):
                cursor = cursor.advance(
                    chunk_index=chunk_record.index,
                    sequence=frame.sequence,
                    monotonic_ns=frame.monotonic_ns,
                )
                if plan.snapshot is not None:
                    cursor = cursor.with_snapshot(plan.snapshot.record.index)
                get_loader_metrics().record_seek(chunks_scanned=chunks_scanned)
                record_replay_trace(
                    "seek-completed",
                    f"target_seq={frame.sequence} chunks={chunks_scanned}",
                )
                return SeekResult(
                    cursor=cursor,
                    landed_frame=frame,
                    chunks_scanned=chunks_scanned,
                )
    # Walked everything — nothing matched.
    get_loader_metrics().record_seek(chunks_scanned=chunks_scanned)
    record_replay_trace(
        "seek-completed", f"no-match chunks={chunks_scanned}",
    )
    return SeekResult(cursor=cursor, landed_frame=None, chunks_scanned=chunks_scanned)


# ── high-level helpers ────────────────────────────────────────────


def seek_to_sequence(
    target_sequence: int,
    *,
    sequence_index: ReplayIndex,
    snapshot_index: ReplaySnapshotIndex,
    chunks: tuple[ChunkRecord, ...],
    chunk_paths: tuple[Path, ...],
    adapter: FrameAdapter,
    strict: bool = False,
) -> SeekResult:
    record_replay_trace("seek-started", f"target_seq={target_sequence}")
    plan = plan_sequence_seek(
        target_sequence,
        sequence_index=sequence_index,
        snapshot_index=snapshot_index,
        chunks=chunks,
    )
    return execute_seek(
        plan,
        chunks=chunks,
        chunk_paths=chunk_paths,
        adapter=adapter,
        target_predicate=lambda frame: frame.sequence >= target_sequence,
        strict=strict,
    )


def seek_to_timestamp(
    target_monotonic_ns: int,
    *,
    sequence_index: ReplayIndex,
    snapshot_index: ReplaySnapshotIndex,
    chunks: tuple[ChunkRecord, ...],
    chunk_paths: tuple[Path, ...],
    adapter: FrameAdapter,
    strict: bool = False,
) -> SeekResult:
    """Land on the first frame with ``monotonic_ns >= target``.

    Timestamps don't map cleanly to chunks the way sequences do
    (chunks aren't time-ordered in their metadata), so the seek
    walks chunks in order and lets the predicate stop it. The
    snapshot lookup still uses the *sequence* of the nearest frame
    we'll touch, since snapshots are sequence-indexed."""
    record_replay_trace("seek-started", f"target_ts={target_monotonic_ns}")
    plan = SeekPlan(
        starting_chunk_index=chunks[0].index if chunks else 0,
        snapshot=None,
        chunks_to_scan=len(chunks),
    )
    result = execute_seek(
        plan,
        chunks=chunks,
        chunk_paths=chunk_paths,
        adapter=adapter,
        target_predicate=lambda frame: frame.monotonic_ns >= target_monotonic_ns,
        strict=strict,
    )
    if result.landed_frame is not None:
        snap = snapshot_index.nearest_at_or_before(result.landed_frame.sequence)
        if snap is not None:
            return SeekResult(
                cursor=result.cursor.with_snapshot(snap.record.index),
                landed_frame=result.landed_frame,
                chunks_scanned=result.chunks_scanned,
            )
    return result


def iter_from_cursor(
    cursor: ReplayCursor,
    *,
    chunks: tuple[ChunkRecord, ...],
    chunk_paths: tuple[Path, ...],
    adapter: FrameAdapter,
    strict: bool = False,
) -> Iterator[ReplayFrame]:
    """Resume iteration from the chunk a cursor pointed at, yielding
    only frames strictly after ``cursor.last_sequence``."""
    if cursor.chunk_index <= 0:
        for record, path in zip(chunks, chunk_paths, strict=True):
            loader = ReplayChunkLoader(record, path, adapter=adapter, strict=strict)
            yield from loader.iter_frames()
        return
    threshold = cursor.last_sequence
    for record, path in zip(chunks, chunk_paths, strict=True):
        if record.index < cursor.chunk_index:
            continue
        loader = ReplayChunkLoader(record, path, adapter=adapter, strict=strict)
        for frame in loader.iter_frames():
            if frame.sequence <= threshold:
                continue
            yield frame
