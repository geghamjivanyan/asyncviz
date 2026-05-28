"""Canonical NDJSON replay event format.

Stable wire protocol for the AsyncViz replay infrastructure: every
frame is one JSON object on one line, every line is independently
decodable, and every envelope carries a schema version so readers
can tell what they're being asked to decode.

The public API lives on :mod:`ndjson_format` — re-exported here for
convenience. Submodules expose the lower-level pieces (canonical
JSON encoder, payload registry, migration registry, validation,
recovery, observability) for callers that need finer control.
"""

from asyncviz.replay.format.ndjson_backpressure import (
    MAX_ENCODER_BUFFER_FRAMES,
    MAX_FRAME_LINE_BYTES,
    FrameTooLargeError,
    OverflowGuard,
    guard_line_length,
)
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
from asyncviz.replay.format.ndjson_format import (
    decode_path,
    encode_frames,
    make_runtime_event_frame,
)
from asyncviz.replay.format.ndjson_frame import ReplayFrame
from asyncviz.replay.format.ndjson_integrity import (
    StreamDigest,
    compute_frame_digest,
    verify_frame_digest,
)
from asyncviz.replay.format.ndjson_observability import (
    NdjsonFormatMetricsSnapshot,
    get_format_metrics,
    get_format_metrics_snapshot,
    reset_format_metrics,
)
from asyncviz.replay.format.ndjson_reader import NdjsonFrameReader, NdjsonReadReport
from asyncviz.replay.format.ndjson_recovery import (
    FrameRecoveryRecord,
    RecoveringDecoder,
    RecoveryOutcome,
    recover_frames,
)
from asyncviz.replay.format.ndjson_registry import (
    PayloadCodec,
    PayloadRegistry,
    get_payload_registry,
    reset_payload_registry,
)
from asyncviz.replay.format.ndjson_schema import (
    ALL_FRAME_TYPES,
    ENVELOPE_KEYS,
    MIN_READABLE_SCHEMA_VERSION,
    PROTOCOL_VERSION,
    REQUIRED_ENVELOPE_KEYS,
    SCHEMA_VERSION,
    FrameType,
    PayloadCategory,
    frame_type_category,
)
from asyncviz.replay.format.ndjson_serialization import (
    FrameEncodingError,
    build_frame,
    encode_frame,
    encode_payload,
)
from asyncviz.replay.format.ndjson_streaming import (
    StreamingFrameReader,
    StreamingReadStats,
    iter_lines,
    iter_lines_multi,
)
from asyncviz.replay.format.ndjson_tracing import (
    NdjsonTraceEntry,
    NdjsonTraceKind,
    clear_ndjson_trace,
    get_ndjson_trace,
    is_ndjson_trace_enabled,
    record_ndjson_trace,
    set_ndjson_trace_enabled,
)
from asyncviz.replay.format.ndjson_validation import (
    FrameValidationError,
    FrameValidationReport,
    SequenceValidator,
    validate_frame,
    validate_stream,
)
from asyncviz.replay.format.ndjson_versioning import (
    CompatibilityVerdict,
    MigrationKey,
    MigrationRegistry,
    PayloadMigration,
    VersioningError,
    check_envelope_compatibility,
    get_migration_registry,
    reset_migration_registry,
)
from asyncviz.replay.format.ndjson_writer import NdjsonFrameWriter

__all__ = [
    "ALL_FRAME_TYPES",
    "ENVELOPE_KEYS",
    "MAX_ENCODER_BUFFER_FRAMES",
    "MAX_FRAME_LINE_BYTES",
    "MIN_READABLE_SCHEMA_VERSION",
    "PROTOCOL_VERSION",
    "REQUIRED_ENVELOPE_KEYS",
    "SCHEMA_VERSION",
    "CompatibilityVerdict",
    "FrameDecodingError",
    "FrameEncodingError",
    "FrameRecoveryRecord",
    "FrameTooLargeError",
    "FrameType",
    "FrameValidationError",
    "FrameValidationReport",
    "MigrationKey",
    "MigrationRegistry",
    "NdjsonFormatDiagnostics",
    "NdjsonFormatMetricsSnapshot",
    "NdjsonFrameReader",
    "NdjsonFrameWriter",
    "NdjsonReadReport",
    "NdjsonTraceEntry",
    "NdjsonTraceKind",
    "OverflowGuard",
    "PayloadCategory",
    "PayloadCodec",
    "PayloadMigration",
    "PayloadRegistry",
    "RecoveringDecoder",
    "RecoveryOutcome",
    "ReplayFrame",
    "SequenceValidator",
    "StreamDigest",
    "StreamingFrameReader",
    "StreamingReadStats",
    "VersioningError",
    "build_format_diagnostics",
    "build_frame",
    "check_envelope_compatibility",
    "clear_ndjson_trace",
    "compute_frame_digest",
    "decode_frame",
    "decode_path",
    "decode_payload",
    "encode_frame",
    "encode_frames",
    "encode_payload",
    "frame_type_category",
    "get_format_metrics",
    "get_format_metrics_snapshot",
    "get_migration_registry",
    "get_ndjson_trace",
    "get_payload_registry",
    "guard_line_length",
    "is_ndjson_trace_enabled",
    "iter_decode_lines",
    "iter_lines",
    "iter_lines_multi",
    "make_runtime_event_frame",
    "migrate_payload",
    "record_ndjson_trace",
    "recover_frames",
    "reset_format_metrics",
    "reset_migration_registry",
    "reset_payload_registry",
    "set_ndjson_trace_enabled",
    "validate_frame",
    "validate_stream",
    "verify_frame_digest",
]
