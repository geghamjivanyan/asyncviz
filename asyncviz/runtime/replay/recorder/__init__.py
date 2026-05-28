"""Canonical replay-recording subsystem.

The recorder turns the live event stream into a self-contained
on-disk bundle that downstream tools (replay viewer, debugger, CI
bug-report attachments) can open without a live runtime.

Public surface:

* :class:`ReplayRecorder` — top-level facade. Bind it to a
  :class:`RuntimeStateStore`, call ``start()`` / ``stop()``.
* :class:`ReplayWriter` — low-level file-IO. Each chunk is an
  append-only NDJSON (optionally gzipped) file written atomically
  via ``write + fsync + rename``.
* :class:`RecorderConfig` — typed configuration.
* :class:`ReplayBundleMetadata` — the manifest model the writer
  emits + the validator consumes.

Tooling-side counterpart is :mod:`asyncviz.runtime.replay.artifacts`.
"""

from asyncviz.runtime.replay.recorder.replay_backpressure import (
    BackpressureMode,
    BackpressureOutcome,
    BoundedRecordQueue,
)
from asyncviz.runtime.replay.recorder.replay_chunking import (
    ChunkPolicy,
)
from asyncviz.runtime.replay.recorder.replay_compression import (
    CompressionMode,
)
from asyncviz.runtime.replay.recorder.replay_configuration import (
    DEFAULT_CHUNK_BYTES,
    DEFAULT_CHUNK_EVENTS,
    DEFAULT_QUEUE_CAPACITY,
    RecorderConfig,
)
from asyncviz.runtime.replay.recorder.replay_diagnostics import (
    RecorderDiagnosticsSnapshot,
    build_recorder_diagnostics,
)
from asyncviz.runtime.replay.recorder.replay_export import (
    finalize_recorder,
    start_recorder_for_runtime,
)
from asyncviz.runtime.replay.recorder.replay_integrity import (
    finalize_marker,
    open_marker,
    sha256_file,
)
from asyncviz.runtime.replay.recorder.replay_manifest import (
    ChunkManifestEntry,
    ReplayBundleManifest,
    build_manifest,
    load_manifest,
    write_manifest,
)
from asyncviz.runtime.replay.recorder.replay_metadata import (
    PackagingMeta,
    RecorderMeta,
    RuntimeMeta,
    write_meta,
)
from asyncviz.runtime.replay.recorder.replay_metrics import (
    RecorderMetricsSnapshot,
    get_recorder_metrics,
    reset_recorder_metrics,
)
from asyncviz.runtime.replay.recorder.replay_recorder import (
    ReplayRecorder,
)
from asyncviz.runtime.replay.recorder.replay_serializer import (
    serialize_frame,
)
from asyncviz.runtime.replay.recorder.replay_statistics import (
    RecordingStatistics,
)
from asyncviz.runtime.replay.recorder.replay_tracing import (
    RecorderTraceEntry,
    clear_recorder_trace,
    get_recorder_trace,
    is_recorder_trace_enabled,
    record_recorder_trace,
    set_recorder_trace_enabled,
)
from asyncviz.runtime.replay.recorder.replay_writer import (
    ReplayWriter,
)

__all__ = [
    "DEFAULT_CHUNK_BYTES",
    "DEFAULT_CHUNK_EVENTS",
    "DEFAULT_QUEUE_CAPACITY",
    "BackpressureMode",
    "BackpressureOutcome",
    "BoundedRecordQueue",
    "ChunkManifestEntry",
    "ChunkPolicy",
    "CompressionMode",
    "PackagingMeta",
    "RecorderConfig",
    "RecorderDiagnosticsSnapshot",
    "RecorderMeta",
    "RecorderMetricsSnapshot",
    "RecorderTraceEntry",
    "RecordingStatistics",
    "ReplayBundleManifest",
    "ReplayRecorder",
    "ReplayWriter",
    "RuntimeMeta",
    "build_manifest",
    "build_recorder_diagnostics",
    "clear_recorder_trace",
    "finalize_marker",
    "finalize_recorder",
    "get_recorder_metrics",
    "get_recorder_trace",
    "is_recorder_trace_enabled",
    "load_manifest",
    "open_marker",
    "record_recorder_trace",
    "reset_recorder_metrics",
    "serialize_frame",
    "set_recorder_trace_enabled",
    "sha256_file",
    "start_recorder_for_runtime",
    "write_manifest",
    "write_meta",
]
