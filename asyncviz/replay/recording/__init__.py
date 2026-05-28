"""Canonical append-oriented runtime event persistence."""

from asyncviz.replay.recording.recording_backpressure import (
    BoundedRingBuffer,
    EnqueueResult,
)
from asyncviz.replay.recording.recording_configuration import (
    FsyncMode,
    RecordingConfig,
)
from asyncviz.replay.recording.recording_diagnostics import (
    RecordingDiagnostics,
    build_recording_diagnostics,
)
from asyncviz.replay.recording.recording_export import (
    ExportResult,
    export_session_to_zip,
)
from asyncviz.replay.recording.recording_index import (
    IndexEntry,
    RecordingIndex,
    build_index_from_chunks,
    chunk_path_for_entry,
    read_index,
    write_index,
)
from asyncviz.replay.recording.recording_integrity import (
    RepairResult,
    compute_chunk_hash,
    count_chunk_events,
    repair_partial_tail,
    verify_chunk_hash,
)
from asyncviz.replay.recording.recording_layout import (
    CHUNK_DIGITS,
    EVENTS_DIRNAME,
    INDEX_FILENAME,
    MANIFEST_FILENAME,
    SCHEMA_VERSION,
    SNAPSHOTS_DIRNAME,
    chunk_filename,
    events_chunk_path,
    events_dir,
    index_path,
    manifest_path,
    snapshot_chunk_path,
    snapshots_dir,
)
from asyncviz.replay.recording.recording_manifest import (
    read_manifest,
    write_manifest,
)
from asyncviz.replay.recording.recording_metadata import (
    ChunkRecord,
    RecordingMetadata,
    SnapshotRecord,
)
from asyncviz.replay.recording.recording_observability import (
    RecordingMetricsSnapshot,
    get_recording_metrics,
    reset_recording_metrics,
)
from asyncviz.replay.recording.recording_recovery import (
    RecoveryReport,
    patch_manifest_after_recovery,
    recover_session,
)
from asyncviz.replay.recording.recording_session import (
    RecordingSession,
    SessionState,
)
from asyncviz.replay.recording.recording_stream import (
    RecordedFrame,
    RecordingStream,
)
from asyncviz.replay.recording.recording_tracing import (
    RecordingTraceEntry,
    RecordingTraceKind,
    clear_recording_trace,
    get_recording_trace,
    is_recording_trace_enabled,
    record_recording_trace,
    set_recording_trace_enabled,
)
from asyncviz.replay.recording.recording_writer import (
    RecordingWriter,
    WriterFlushResult,
    iter_chunk_lines,
    iter_chunk_payloads,
)
from asyncviz.replay.recording.runtime_recorder import RuntimeRecorder

__all__ = [
    "CHUNK_DIGITS",
    "EVENTS_DIRNAME",
    "INDEX_FILENAME",
    "MANIFEST_FILENAME",
    "SCHEMA_VERSION",
    "SNAPSHOTS_DIRNAME",
    "BoundedRingBuffer",
    "ChunkRecord",
    "EnqueueResult",
    "ExportResult",
    "FsyncMode",
    "IndexEntry",
    "RecordedFrame",
    "RecordingConfig",
    "RecordingDiagnostics",
    "RecordingIndex",
    "RecordingManifest",
    "RecordingMetadata",
    "RecordingMetricsSnapshot",
    "RecordingSession",
    "RecordingStream",
    "RecordingTraceEntry",
    "RecordingTraceKind",
    "RecordingWriter",
    "RecoveryReport",
    "RepairResult",
    "RuntimeRecorder",
    "SessionState",
    "SnapshotRecord",
    "WriterFlushResult",
    "build_index_from_chunks",
    "build_recording_diagnostics",
    "chunk_filename",
    "chunk_path_for_entry",
    "clear_recording_trace",
    "compute_chunk_hash",
    "count_chunk_events",
    "events_chunk_path",
    "events_dir",
    "export_session_to_zip",
    "get_recording_metrics",
    "get_recording_trace",
    "index_path",
    "is_recording_trace_enabled",
    "iter_chunk_lines",
    "iter_chunk_payloads",
    "manifest_path",
    "patch_manifest_after_recovery",
    "read_index",
    "read_manifest",
    "record_recording_trace",
    "recover_session",
    "repair_partial_tail",
    "reset_recording_metrics",
    "set_recording_trace_enabled",
    "snapshot_chunk_path",
    "snapshots_dir",
    "verify_chunk_hash",
    "write_index",
    "write_manifest",
]


# Re-exported alias for the manifest record-bag — keeps the public API
# stable even if the file moves.
RecordingManifest = RecordingMetadata
