"""High-level façade for the NDJSON replay format.

Most consumers want ergonomic encode/decode without thinking about
which submodule owns which piece. This module re-exports the small
public surface: encode/decode one frame, encode/decode a stream,
build a writer, build a reader, query diagnostics.

Internal modules are still importable directly when finer control is
needed (e.g. test fixtures that want to skip the codec and write a
raw line); the façade exists to keep day-to-day call sites short.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from asyncviz.replay.format.ndjson_deserialization import (
    FrameDecodingError,
    decode_frame,
    decode_payload,
    iter_decode_lines,
    migrate_payload,
)
from asyncviz.replay.format.ndjson_diagnostics import (
    NdjsonFormatDiagnostics,
    build_format_diagnostics,
)
from asyncviz.replay.format.ndjson_frame import ReplayFrame
from asyncviz.replay.format.ndjson_observability import (
    NdjsonFormatMetricsSnapshot,
    get_format_metrics_snapshot,
)
from asyncviz.replay.format.ndjson_reader import NdjsonFrameReader, NdjsonReadReport
from asyncviz.replay.format.ndjson_recovery import (
    RecoveringDecoder,
    RecoveryOutcome,
    recover_frames,
)
from asyncviz.replay.format.ndjson_schema import (
    PROTOCOL_VERSION,
    SCHEMA_VERSION,
    FrameType,
)
from asyncviz.replay.format.ndjson_serialization import (
    FrameEncodingError,
    build_frame,
    encode_frame,
    encode_payload,
)
from asyncviz.replay.format.ndjson_streaming import (
    StreamingFrameReader,
    iter_lines,
    iter_lines_multi,
)
from asyncviz.replay.format.ndjson_validation import (
    FrameValidationError,
    FrameValidationReport,
    SequenceValidator,
    validate_frame,
    validate_stream,
)
from asyncviz.replay.format.ndjson_writer import NdjsonFrameWriter


def encode_frames(frames: Iterable[ReplayFrame]) -> Iterator[str]:
    """Encode a stream of frames to NDJSON lines, lazily."""
    for frame in frames:
        yield encode_frame(frame)


def decode_path(path: Path, *, strict: bool = False) -> Iterator[ReplayFrame]:
    """Decode every frame in an NDJSON file. Malformed lines are
    skipped unless ``strict=True``."""
    with NdjsonFrameReader(path, strict=strict) as reader:
        yield from reader


def make_runtime_event_frame(
    *,
    sequence: int,
    monotonic_ns: int,
    event: Any,
    runtime_id: str | None = None,
    recording_id: str | None = None,
    wall_time_ns: int | None = None,
) -> ReplayFrame:
    """One-call adapter: turn a :class:`RuntimeEvent` into a
    ``runtime_event`` :class:`ReplayFrame`. Used by the recording
    bridge and by replay-export tools."""
    payload_type = getattr(event, "event_type", None) or type(event).__name__
    return build_frame(
        frame_type="runtime_event",
        sequence=sequence,
        monotonic_ns=monotonic_ns,
        payload_type=str(payload_type),
        payload=event,
        runtime_id=runtime_id,
        recording_id=recording_id,
        wall_time_ns=wall_time_ns,
    )


__all__ = [
    "PROTOCOL_VERSION",
    "SCHEMA_VERSION",
    "FrameDecodingError",
    "FrameEncodingError",
    "FrameType",
    "FrameValidationError",
    "FrameValidationReport",
    "NdjsonFormatDiagnostics",
    "NdjsonFormatMetricsSnapshot",
    "NdjsonFrameReader",
    "NdjsonFrameWriter",
    "NdjsonReadReport",
    "RecoveringDecoder",
    "RecoveryOutcome",
    "ReplayFrame",
    "SequenceValidator",
    "StreamingFrameReader",
    "build_format_diagnostics",
    "build_frame",
    "decode_frame",
    "decode_path",
    "decode_payload",
    "encode_frame",
    "encode_frames",
    "encode_payload",
    "get_format_metrics_snapshot",
    "iter_decode_lines",
    "iter_lines",
    "iter_lines_multi",
    "make_runtime_event_frame",
    "migrate_payload",
    "recover_frames",
    "validate_frame",
    "validate_stream",
]
