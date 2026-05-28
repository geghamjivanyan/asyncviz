"""Typed configuration for the runtime recorder."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

FsyncMode = Literal["never", "interval", "rotation", "always"]


@dataclass(frozen=True, slots=True)
class RecordingConfig:
    """Knobs for :class:`RuntimeRecorder` + its underlying writer.

    Defaults are tuned for "production-ish" workloads: bounded buffer,
    periodic batched flushes, rotation at ~64 MiB or 10k events
    (whichever trips first), no per-event fsync.
    """

    root_dir: Path
    """Directory under which per-session subdirectories are created."""

    buffer_capacity: int = 4096
    """Maximum number of pending events held in the writer's queue
    before the backpressure policy fires."""

    flush_interval_seconds: float = 0.5
    """Maximum time between flushes when the buffer never fills."""

    max_chunk_bytes: int = 64 * 1024 * 1024
    """Rotate to a new chunk file when the current one reaches this
    size. Set to ``0`` for unbounded chunks (not recommended — long
    sessions become hard to ship)."""

    max_chunk_events: int = 10_000
    """Rotate when this many events have landed in the current chunk.
    Set to ``0`` to disable count-based rotation."""

    fsync_mode: FsyncMode = "rotation"
    """When to call ``fsync`` on the events file:
    * ``never`` — let the OS flush; cheapest, weakest durability.
    * ``interval`` — once per flush tick.
    * ``rotation`` — only when closing a chunk (default — balances
      cost + crash safety for the common case).
    * ``always`` — every flush + every rotation."""

    snapshot_on_start: bool = True
    """Capture an initial snapshot when the recorder boots."""

    snapshot_on_stop: bool = True
    """Capture a final snapshot before finalizing the manifest."""

    snapshot_on_rotation: bool = False
    """Capture a snapshot when the events file rotates. Lets a
    future replay engine seek to chunk boundaries without scanning
    from the beginning."""

    drop_policy: Literal["drop-newest", "drop-oldest", "block"] = "drop-newest"
    """What to do when the writer queue is full:
    * ``drop-newest`` (default) — drop the incoming event, bump dropped
      counter. Cheapest; preferred under storm conditions.
    * ``drop-oldest`` — evict the oldest queued event. Keeps fresher
      view of recent history under pressure.
    * ``block`` — block the publisher. Only safe when the publisher
      is a non-loop thread; can deadlock on the loop thread."""

    enable_index: bool = True
    """Write a sequence→(chunk, byte_offset) index on finalize, so
    future replay can seek without scanning."""

    enable_tracing: bool = False
    """When ``True``, the recorder appends every lifecycle transition
    to the ring buffer in :mod:`recording_tracing`."""
