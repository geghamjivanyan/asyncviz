"""Append-only NDJSON writer for runtime events.

Each writer instance owns one *session directory*. Events flow in via
:meth:`enqueue`, get batched by a background worker thread, and land
on disk as newline-delimited JSON inside rotating chunk files.

Rotation policy:

* Roll when the current chunk reaches ``max_chunk_bytes`` OR
  ``max_chunk_events`` (whichever trips first).
* Pre-finalize the closed chunk (hash + fsync), then open the next.

Crash safety:

* Writes go through Python's buffered IO + an explicit ``flush()``
  on the flush tick. The OS may still have data in its cache; the
  ``fsync_mode`` knob controls when we force durability.
* If the process dies mid-write, the at-most one partial line at EOF
  is recoverable by :mod:`recording_integrity` — every prior event
  in the chunk is preserved because we end each event with ``\\n``.

The writer is thread-safe: ``enqueue`` is callable from any thread
(it just appends to the bounded buffer); the worker thread is the
only one that touches the file handle.
"""

from __future__ import annotations

import io
import json
import threading
import time
from collections.abc import Iterable, Iterator
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from asyncviz.replay.recording.recording_backpressure import (
    BoundedRingBuffer,
    EnqueueResult,
)
from asyncviz.replay.recording.recording_configuration import RecordingConfig
from asyncviz.replay.recording.recording_integrity import (
    compute_chunk_hash,
    repair_partial_tail,
)
from asyncviz.replay.recording.recording_layout import (
    EVENTS_DIRNAME,
    chunk_filename,
)
from asyncviz.replay.recording.recording_metadata import ChunkRecord
from asyncviz.replay.recording.recording_observability import get_recording_metrics
from asyncviz.replay.recording.recording_paths import ensure_directory, fsync_file
from asyncviz.replay.recording.recording_tracing import record_recording_trace
from asyncviz.utils.logging import get_logger

logger = get_logger("replay.recording.writer")


@dataclass(slots=True)
class _ChunkState:
    """Mutable state for one open chunk."""

    index: int
    path: Path
    handle: io.TextIOWrapper
    byte_size: int = 0
    event_count: int = 0
    first_sequence: int = -1
    last_sequence: int = -1


@dataclass(frozen=True, slots=True)
class WriterFlushResult:
    """Result of one flush tick — what landed on disk."""

    events_persisted: int
    bytes_written: int
    chunk_rotated: bool
    completed_chunk: ChunkRecord | None = None
    """Populated when rotation happened during this flush."""


@dataclass(slots=True)
class _PendingEvent:
    """One queued event awaiting flush."""

    sequence: int
    payload: dict[str, Any]
    """Pre-serialized to a JSON-safe dict so the worker doesn't need
    to know about Pydantic models or RuntimeEvents."""

    line: str = ""
    """Pre-serialized JSON line (filled in by the enqueue path)."""

    monotonic_ns: int = 0
    event_id: str = ""


class RecordingWriter:
    """Append-only NDJSON writer with batched background flushes."""

    def __init__(self, session_dir: Path, *, config: RecordingConfig) -> None:
        self._session_dir = session_dir
        self._config = config
        self._events_dir = session_dir / EVENTS_DIRNAME
        ensure_directory(self._events_dir)
        self._buffer: BoundedRingBuffer[_PendingEvent] = BoundedRingBuffer(
            capacity=config.buffer_capacity,
            drop_policy=config.drop_policy,
        )
        self._lock = threading.RLock()
        self._chunk: _ChunkState | None = None
        self._chunks_completed: list[ChunkRecord] = []
        self._chunk_index = 0
        self._stop_event = threading.Event()
        self._worker: threading.Thread | None = None
        self._started = False
        self._last_flush_monotonic = 0.0
        self._metrics = get_recording_metrics()
        self._open_initial_chunk()

    # ── public lifecycle ──────────────────────────────────────────

    def start(self) -> None:
        """Start the background worker. Idempotent."""
        with self._lock:
            if self._started:
                return
            self._stop_event.clear()
            self._worker = threading.Thread(
                target=self._worker_loop, name="asyncviz-recording-writer", daemon=True,
            )
            self._worker.start()
            self._started = True

    def stop(self) -> None:
        """Stop the worker, drain the buffer, finalize the open chunk.
        Idempotent. Safe to call from a signal handler."""
        with self._lock:
            if not self._started:
                # Even if not started, finalize whatever the buffer holds.
                self._drain_and_finalize()
                return
            self._stop_event.set()
            worker = self._worker
        if worker is not None:
            worker.join(timeout=5.0)
        with self._lock:
            self._drain_and_finalize()
            self._started = False
            self._worker = None

    def enqueue(self, *, sequence: int, payload: dict[str, Any]) -> EnqueueResult[_PendingEvent]:
        """Queue an event for writing. Returns the policy outcome.

        ``payload`` MUST already be JSON-safe (the recorder's frame
        adapter handles that translation).
        """
        line = json.dumps(payload, separators=(",", ":")) + "\n"
        pending = _PendingEvent(
            sequence=sequence,
            payload=payload,
            line=line,
            monotonic_ns=int(payload.get("monotonic_ns", 0) or 0),
            event_id=str(payload.get("event_id", "")),
        )
        result = self._buffer.offer(pending)
        self._metrics.set_queue_depth(len(self._buffer))
        if result.action == "accepted":
            return result
        if result.action in ("dropped-newest", "dropped-oldest"):
            self._metrics.record_event_dropped()
            record_recording_trace("event-dropped", f"seq={sequence} action={result.action}")
        return result

    def flush(self) -> WriterFlushResult:
        """Synchronously drain the buffer + flush to disk. Returns
        a :class:`WriterFlushResult` summarizing what landed."""
        with self._lock:
            return self._flush_locked(drained=self._buffer.drain_all())

    # ── chunk lifecycle ───────────────────────────────────────────

    @property
    def chunks_completed(self) -> tuple[ChunkRecord, ...]:
        with self._lock:
            return tuple(self._chunks_completed)

    @property
    def current_chunk_state(self) -> ChunkRecord | None:
        with self._lock:
            if self._chunk is None:
                return None
            return _to_chunk_record(self._chunk, compute_hash=False)

    @property
    def chunk_index(self) -> int:
        with self._lock:
            return self._chunk_index

    # ── worker loop ───────────────────────────────────────────────

    def _worker_loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                batch = self._buffer.drain_batch(
                    max_items=self._config.buffer_capacity,
                    timeout=self._config.flush_interval_seconds,
                )
                if not batch:
                    continue
                with self._lock:
                    self._flush_locked(drained=batch)
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("recording writer worker died: %s", exc)

    def _flush_locked(self, *, drained: list[_PendingEvent]) -> WriterFlushResult:
        events_persisted = 0
        bytes_written = 0
        rotated = False
        completed: ChunkRecord | None = None
        if not drained and self._chunk is None:
            return WriterFlushResult(0, 0, False, None)
        if drained:
            for pending in drained:
                if self._chunk is None:
                    self._open_chunk(self._chunk_index + 1)
                # Rotation check: if the next write would exceed limits,
                # finalize current and start a new chunk first.
                if self._would_rotate(pending.line):
                    completed = self._rotate_locked()
                    rotated = True
                self._write_to_chunk(pending)
                events_persisted += 1
                bytes_written += len(pending.line)
            self._chunk.handle.flush()  # type: ignore[union-attr]
            if self._config.fsync_mode in ("interval", "always"):
                try:
                    fsync_file(self._chunk.path)  # type: ignore[union-attr]
                except Exception as exc:  # pragma: no cover — defensive
                    self._metrics.record_flush_failure()
                    record_recording_trace("flush-failed", str(exc))
                else:
                    self._metrics.record_flush_completed()
                    record_recording_trace("flush-completed", f"events={events_persisted}")
            else:
                self._metrics.record_flush_completed()
                record_recording_trace("flush-completed", f"events={events_persisted}")
            self._metrics.set_queue_depth(len(self._buffer))
        self._last_flush_monotonic = time.monotonic()
        return WriterFlushResult(events_persisted, bytes_written, rotated, completed)

    def _drain_and_finalize(self) -> None:
        # Final flush + close the open chunk.
        self._flush_locked(drained=self._buffer.drain_all())
        if self._chunk is not None:
            self._close_current_chunk()

    # ── chunk file ops ────────────────────────────────────────────

    def _open_initial_chunk(self) -> None:
        starting = self._infer_starting_index()
        if starting > 0:
            # Resume the last existing chunk in-place so that a writer
            # restarted after a crash continues appending where it left
            # off rather than orphaning a partially-filled chunk.
            self._open_chunk(starting)
        else:
            self._open_chunk(1)

    def _infer_starting_index(self) -> int:
        """Scan ``events/`` to find the last existing chunk index."""
        existing = sorted(self._events_dir.glob("*.ndjson"))
        if not existing:
            return 0
        last = existing[-1].stem
        try:
            return int(last)
        except ValueError:
            return 0

    def _open_chunk(self, index: int) -> None:
        path = self._events_dir / chunk_filename(index)
        # If a chunk file already exists (recovery scenario), repair its
        # tail and open in append mode so we don't blow away earlier events.
        if path.exists():
            repair = repair_partial_tail(path)
            if repair.truncated_bytes > 0:
                self._metrics.record_repair_completed()
                record_recording_trace(
                    "recovery-completed",
                    f"chunk={index} truncated={repair.truncated_bytes}",
                )
            handle = path.open("a", encoding="utf-8", buffering=8192)
            byte_size = path.stat().st_size
            event_count = path.read_bytes().count(b"\n")
        else:
            handle = path.open("w", encoding="utf-8", buffering=8192)
            byte_size = 0
            event_count = 0
        self._chunk = _ChunkState(
            index=index,
            path=path,
            handle=handle,
            byte_size=byte_size,
            event_count=event_count,
            first_sequence=-1,
            last_sequence=-1,
        )
        self._chunk_index = index

    def _write_to_chunk(self, pending: _PendingEvent) -> None:
        assert self._chunk is not None
        self._chunk.handle.write(pending.line)
        self._chunk.byte_size += len(pending.line)
        self._chunk.event_count += 1
        if self._chunk.first_sequence < 0:
            self._chunk.first_sequence = pending.sequence
        self._chunk.last_sequence = pending.sequence
        self._metrics.record_event_persisted(len(pending.line))

    def _would_rotate(self, next_line: str) -> bool:
        assert self._chunk is not None
        if self._chunk.event_count == 0:
            return False  # never rotate an empty chunk
        if (
            self._config.max_chunk_bytes > 0
            and self._chunk.byte_size + len(next_line) > self._config.max_chunk_bytes
        ):
            return True
        return (
            self._config.max_chunk_events > 0
            and self._chunk.event_count >= self._config.max_chunk_events
        )

    def _rotate_locked(self) -> ChunkRecord:
        completed = self._close_current_chunk()
        self._open_chunk(self._chunk_index + 1)
        self._metrics.record_rotation()
        record_recording_trace("chunk-rotated", f"completed_index={completed.index}")
        return completed

    def _close_current_chunk(self) -> ChunkRecord:
        assert self._chunk is not None
        chunk = self._chunk
        chunk.handle.flush()
        if self._config.fsync_mode in ("rotation", "always"):
            with suppress(Exception):  # defensive — fsync can fail on weird filesystems
                fsync_file(chunk.path)
        chunk.handle.close()
        record = _to_chunk_record(chunk, compute_hash=True)
        self._chunks_completed.append(record)
        self._chunk = None
        return record

    # ── observability ─────────────────────────────────────────────

    @property
    def queue_depth(self) -> int:
        return len(self._buffer)


def _to_chunk_record(state: _ChunkState, *, compute_hash: bool) -> ChunkRecord:
    sha = compute_chunk_hash(state.path) if compute_hash else None
    return ChunkRecord(
        index=state.index,
        filename=state.path.name,
        event_count=state.event_count,
        byte_size=state.byte_size,
        first_sequence=state.first_sequence,
        last_sequence=state.last_sequence,
        sha256=sha,
    )


def iter_chunk_lines(path: Path) -> Iterator[str]:
    """Yield each fully-written line of an NDJSON chunk."""
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.endswith("\n"):
                yield line.rstrip("\n")


def iter_chunk_payloads(paths: Iterable[Path]) -> Iterator[dict[str, Any]]:
    """Decode each line of each chunk into a dict. Skips malformed
    lines defensively rather than raising — the writer's integrity
    layer is responsible for keeping the file clean."""
    for path in paths:
        for line in iter_chunk_lines(path):
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue
