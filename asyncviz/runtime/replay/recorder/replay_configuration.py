"""Typed recorder configuration.

Carries every knob the recorder honours. The CLI translates user
flags into this struct, tests build one directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from asyncviz.runtime.replay.recorder.replay_backpressure import (
    BackpressureMode,
)
from asyncviz.runtime.replay.recorder.replay_compression import (
    CompressionMode,
)

#: Default events-per-chunk threshold. Chosen so a 4-byte runtime
#: spitting at 1k events/sec rolls a chunk every few seconds.
DEFAULT_CHUNK_EVENTS: int = 4096

#: Default bytes-per-chunk threshold. Whichever threshold trips
#: first wins.
DEFAULT_CHUNK_BYTES: int = 4 * 1024 * 1024  # 4 MiB

#: Default in-memory queue capacity (events). Bounds the recorder's
#: memory footprint independent of the runtime's event rate.
DEFAULT_QUEUE_CAPACITY: int = 16_384


@dataclass(frozen=True, slots=True)
class RecorderConfig:
    """Resolved configuration for one recording session."""

    output_path: Path
    """Destination bundle directory. Created on start; populated
    incrementally as chunks roll."""

    compression: CompressionMode = CompressionMode.GZIP
    """Per-chunk compression. ``GZIP`` is the default — wins on disk
    + on egress without hurting throughput at typical event rates."""

    chunk_events: int = DEFAULT_CHUNK_EVENTS
    """Roll a chunk after this many events."""

    chunk_bytes: int = DEFAULT_CHUNK_BYTES
    """Roll a chunk after this many serialized bytes (uncompressed)."""

    queue_capacity: int = DEFAULT_QUEUE_CAPACITY
    """In-memory backpressure queue depth."""

    backpressure: BackpressureMode = BackpressureMode.DROP_NEWEST
    """How to behave when the queue is full."""

    flush_interval_seconds: float = 1.0
    """How often the writer wakes up to flush even when the chunk
    thresholds haven't tripped — keeps the on-disk artifact close to
    live."""

    capture_runtime_snapshot: bool = True
    """Write a ``snapshots/runtime-final.json`` at stop time."""

    capture_warning_snapshot: bool = True
    """Write a ``snapshots/warnings-final.json`` at stop time."""

    include_event_types: tuple[str, ...] | None = None
    """When set, only events whose ``event_type`` is in the tuple are
    recorded. ``None`` records everything (canonical default)."""

    exclude_event_types: tuple[str, ...] = field(default_factory=tuple)
    """``event_type`` strings to filter out. Wins over ``include``
    when both apply."""

    metadata_overrides: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    """Free-form key/value pairs surfaced verbatim in ``meta/runtime.json``.
    Useful for CI runs ("build_id", "branch", "trigger")."""

    def filter_allows(self, event_type: str) -> bool:
        """``True`` if the event_type passes the include + exclude filters."""
        if event_type in self.exclude_event_types:
            return False
        if self.include_event_types is None:
            return True
        return event_type in self.include_event_types
