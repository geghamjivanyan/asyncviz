"""Replay-recording runtime options.

Mirrors :class:`asyncviz.runtime.replay.recorder.RecorderConfig` but
keeps the schema flat + string-typed so it serializes cleanly into
config-files / replay metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from asyncviz.configuration.runtime_defaults import (
    DEFAULT_RECORDING_CHUNK_BYTES,
    DEFAULT_RECORDING_CHUNK_EVENTS,
    DEFAULT_RECORDING_COMPRESSION,
    DEFAULT_RECORDING_ENABLED,
    DEFAULT_RECORDING_FLUSH_INTERVAL_SECONDS,
    DEFAULT_RECORDING_QUEUE_CAPACITY,
)

CompressionMode = Literal["none", "gzip"]
BackpressureMode = Literal["drop_newest", "drop_oldest"]


@dataclass(frozen=True, slots=True)
class RuntimeRecordingOptions:
    """Replay-recording knobs surfaced to the operator.

    Named ``RuntimeRecordingOptions`` (not ``RecordingOptions``) so
    it doesn't clash with the legacy
    :class:`asyncviz.cli.configuration.RecordingOptions` — the CLI
    facade still consumes the legacy struct until Task 7.x rewires
    it to read this one directly.
    """

    enabled: bool = DEFAULT_RECORDING_ENABLED
    output_path: Path | None = None
    compression: CompressionMode = DEFAULT_RECORDING_COMPRESSION
    chunk_events: int = DEFAULT_RECORDING_CHUNK_EVENTS
    chunk_bytes: int = DEFAULT_RECORDING_CHUNK_BYTES
    queue_capacity: int = DEFAULT_RECORDING_QUEUE_CAPACITY
    flush_interval_seconds: float = DEFAULT_RECORDING_FLUSH_INTERVAL_SECONDS
    backpressure: BackpressureMode = "drop_newest"
    include_event_types: tuple[str, ...] | None = None
    exclude_event_types: tuple[str, ...] = field(default_factory=tuple)
    capture_runtime_snapshot: bool = True
    capture_warning_snapshot: bool = True
    metadata_overrides: tuple[tuple[str, str], ...] = field(default_factory=tuple)
