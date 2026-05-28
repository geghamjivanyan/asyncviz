"""Canonical replay event loader.

Read-side façade for the recording layer + the NDJSON format layer.
Open a session, iterate frames, seek by sequence or timestamp,
rebuild state at a point in time. Public API lives on
:class:`ReplayEventLoader`; the lower-level pieces are exported here
for tooling that wants finer control.
"""

from asyncviz.replay.loading.models.frame_adapter import (
    AutoDetectFrameAdapter,
    CanonicalFrameAdapter,
    FrameAdapter,
    FrameAdapterError,
    LegacyRecordingFrameAdapter,
    select_frame_adapter,
)
from asyncviz.replay.loading.models.replay_session import (
    ReplaySession,
    ReplaySessionSummary,
)
from asyncviz.replay.loading.replay_backpressure import (
    DEFAULT_MAX_BUFFER_FRAMES,
    BufferCap,
    ReplayBufferOverflowError,
    enforce_buffer_cap,
)
from asyncviz.replay.loading.replay_chunk_loader import (
    ChunkReadReport,
    ReplayChunkLoader,
)
from asyncviz.replay.loading.replay_configuration import (
    FrameFormat,
    ReplayLoaderConfig,
)
from asyncviz.replay.loading.replay_cursor import ReplayCursor
from asyncviz.replay.loading.replay_diagnostics import (
    ReplayLoaderDiagnostics,
    build_loader_diagnostics,
)
from asyncviz.replay.loading.replay_filtering import (
    FrameFilter,
    FramePredicate,
    all_of,
    any_of,
    by_event_type,
    by_frame_type,
    by_recording_id,
    by_runtime_id,
    by_sequence_range,
    by_timestamp_range,
    chain,
    not_,
)
from asyncviz.replay.loading.replay_index import ReplayIndex
from asyncviz.replay.loading.replay_integrity_loader import (
    ChunkIntegrityVerdict,
    IntegrityReport,
    verify_chunk,
    verify_session,
)
from asyncviz.replay.loading.replay_iterator import (
    ReplayIterator,
    ReplayIteratorState,
)
from asyncviz.replay.loading.replay_loader import ReplayEventLoader
from asyncviz.replay.loading.replay_manifest_loader import (
    ManifestLoadError,
    ManifestLoadResult,
    load_manifest,
    load_manifest_or_rebuild,
)
from asyncviz.replay.loading.replay_observability import (
    ReplayLoaderMetricsSnapshot,
    get_loader_metrics,
    get_loader_metrics_snapshot,
    reset_loader_metrics,
)
from asyncviz.replay.loading.replay_recovery_loader import (
    ChunkHealth,
    RecoveringChunkLoader,
    inspect_chunk,
)
from asyncviz.replay.loading.replay_seek import (
    SeekPlan,
    SeekResult,
    execute_seek,
    iter_from_cursor,
    plan_sequence_seek,
    seek_to_sequence,
    seek_to_timestamp,
)
from asyncviz.replay.loading.replay_snapshot_index import (
    ReplaySnapshotIndex,
    SnapshotEntry,
    load_snapshot_payload,
)
from asyncviz.replay.loading.replay_state_loader import (
    Reducer,
    StateReconstructionResult,
    default_collecting_reducer,
    reconstruct_state,
)
from asyncviz.replay.loading.replay_stream import (
    ReplayStream,
    StreamProgress,
)
from asyncviz.replay.loading.replay_tracing import (
    ReplayTraceEntry,
    ReplayTraceKind,
    clear_replay_trace,
    get_replay_trace,
    is_replay_trace_enabled,
    record_replay_trace,
    set_replay_trace_enabled,
)
from asyncviz.replay.loading.replay_validation_loader import (
    ValidationIssue,
    ValidationReport,
    validate_loader_stream,
)
from asyncviz.replay.loading.replay_windowing import ReplayWindow

__all__ = [
    "DEFAULT_MAX_BUFFER_FRAMES",
    "AutoDetectFrameAdapter",
    "BufferCap",
    "CanonicalFrameAdapter",
    "ChunkHealth",
    "ChunkIntegrityVerdict",
    "ChunkReadReport",
    "FrameAdapter",
    "FrameAdapterError",
    "FrameFilter",
    "FrameFormat",
    "FramePredicate",
    "IntegrityReport",
    "LegacyRecordingFrameAdapter",
    "ManifestLoadError",
    "ManifestLoadResult",
    "RecoveringChunkLoader",
    "Reducer",
    "ReplayBufferOverflowError",
    "ReplayChunkLoader",
    "ReplayCursor",
    "ReplayEventLoader",
    "ReplayIndex",
    "ReplayIterator",
    "ReplayIteratorState",
    "ReplayLoaderConfig",
    "ReplayLoaderDiagnostics",
    "ReplayLoaderMetricsSnapshot",
    "ReplaySession",
    "ReplaySessionSummary",
    "ReplaySnapshotIndex",
    "ReplayStream",
    "ReplayTraceEntry",
    "ReplayTraceKind",
    "ReplayWindow",
    "SeekPlan",
    "SeekResult",
    "SnapshotEntry",
    "StateReconstructionResult",
    "StreamProgress",
    "ValidationIssue",
    "ValidationReport",
    "all_of",
    "any_of",
    "build_loader_diagnostics",
    "by_event_type",
    "by_frame_type",
    "by_recording_id",
    "by_runtime_id",
    "by_sequence_range",
    "by_timestamp_range",
    "chain",
    "clear_replay_trace",
    "default_collecting_reducer",
    "enforce_buffer_cap",
    "execute_seek",
    "get_loader_metrics",
    "get_loader_metrics_snapshot",
    "get_replay_trace",
    "inspect_chunk",
    "is_replay_trace_enabled",
    "iter_from_cursor",
    "load_manifest",
    "load_manifest_or_rebuild",
    "load_snapshot_payload",
    "not_",
    "plan_sequence_seek",
    "reconstruct_state",
    "record_replay_trace",
    "reset_loader_metrics",
    "seek_to_sequence",
    "seek_to_timestamp",
    "select_frame_adapter",
    "set_replay_trace_enabled",
    "validate_loader_stream",
    "verify_chunk",
    "verify_session",
]
