"""Canonical replay runtime engine.

Public surface for replay playback. The :class:`ReplayRuntimeEngine`
is the top-level façade; the lower-level pieces are exposed here
for tooling that wants finer control."""

from asyncviz.replay.runtime.models.engine_cursor import EngineCursor
from asyncviz.replay.runtime.models.playback_state import (
    PlaybackSnapshot,
    PlaybackState,
)
from asyncviz.replay.runtime.models.runtime_state import VirtualRuntimeState
from asyncviz.replay.runtime.replay_backpressure import (
    DEFAULT_DISPATCH_QUEUE_CAPACITY,
    DispatchGate,
    DispatchOverflowError,
    OverflowSampler,
)
from asyncviz.replay.runtime.replay_checkpoint_runtime import (
    Checkpoint,
    CheckpointRuntime,
)
from asyncviz.replay.runtime.replay_clock import (
    ReplayClock,
    ReplayClockSnapshot,
)
from asyncviz.replay.runtime.replay_configuration import (
    DEFAULT_CHECKPOINT_INTERVAL_FRAMES,
    DEFAULT_MAX_DISPATCH_QUEUE,
    ClockSource,
    PlaybackMode,
    ReplayEngineConfig,
)
from asyncviz.replay.runtime.replay_cursor_runtime import CursorRuntime
from asyncviz.replay.runtime.replay_diagnostics import (
    ReplayEngineDiagnostics,
    build_engine_diagnostics,
)
from asyncviz.replay.runtime.replay_dispatch import DispatchResult, ReplayDispatch
from asyncviz.replay.runtime.replay_event_router import (
    WILDCARD,
    FrameSubscriber,
    ReplayEventRouter,
)
from asyncviz.replay.runtime.replay_integrity_runtime import (
    IntegrityViolation,
    IntegrityViolationError,
    check_post_dispatch,
    check_pre_dispatch,
)
from asyncviz.replay.runtime.replay_observability import (
    ReplayEngineMetricsSnapshot,
    get_engine_metrics,
    get_engine_metrics_snapshot,
    reset_engine_metrics,
)
from asyncviz.replay.runtime.replay_pause import (
    PauseController,
    PauseListener,
    PauseTransition,
)
from asyncviz.replay.runtime.replay_playback import PlaybackController
from asyncviz.replay.runtime.replay_projection import (
    ProjectedView,
    Projection,
    ProjectionRegistry,
    default_projection_registry,
    project_counters,
    project_domain,
    project_domain_names,
)
from asyncviz.replay.runtime.replay_reducers import (
    Reducer,
    ReducerBinding,
    ReducerRegistry,
    domain_reducer,
)
from asyncviz.replay.runtime.replay_runtime_engine import ReplayRuntimeEngine
from asyncviz.replay.runtime.replay_scheduler import FrameSchedule, ReplayScheduler
from asyncviz.replay.runtime.replay_seek_runtime import (
    ReplaySeekRuntime,
    SeekOutcome,
)
from asyncviz.replay.runtime.replay_snapshot_runtime import (
    SnapshotRestoreResult,
    SnapshotRuntime,
)
from asyncviz.replay.runtime.replay_speed import (
    MAX_SPEED,
    MIN_SPEED,
    SpeedChange,
    SpeedController,
)
from asyncviz.replay.runtime.replay_state_store import (
    ReplayStateStore,
    StateListener,
)
from asyncviz.replay.runtime.replay_tracing import (
    ReplayEngineTraceEntry,
    ReplayEngineTraceKind,
    clear_engine_trace,
    get_engine_trace,
    is_engine_trace_enabled,
    record_engine_trace,
    set_engine_trace_enabled,
)
from asyncviz.replay.runtime.replay_websocket_bridge import (
    CollectingSink,
    NullSink,
    ReplayWebsocketBridge,
    ReplayWebsocketSink,
)

__all__ = [
    "DEFAULT_CHECKPOINT_INTERVAL_FRAMES",
    "DEFAULT_DISPATCH_QUEUE_CAPACITY",
    "DEFAULT_MAX_DISPATCH_QUEUE",
    "MAX_SPEED",
    "MIN_SPEED",
    "WILDCARD",
    "Checkpoint",
    "CheckpointRuntime",
    "ClockSource",
    "CollectingSink",
    "CursorRuntime",
    "DispatchGate",
    "DispatchOverflowError",
    "DispatchResult",
    "EngineCursor",
    "FrameSchedule",
    "FrameSubscriber",
    "IntegrityViolation",
    "IntegrityViolationError",
    "NullSink",
    "OverflowSampler",
    "PauseController",
    "PauseListener",
    "PauseTransition",
    "PlaybackController",
    "PlaybackMode",
    "PlaybackSnapshot",
    "PlaybackState",
    "ProjectedView",
    "Projection",
    "ProjectionRegistry",
    "Reducer",
    "ReducerBinding",
    "ReducerRegistry",
    "ReplayClock",
    "ReplayClockSnapshot",
    "ReplayDispatch",
    "ReplayEngineConfig",
    "ReplayEngineDiagnostics",
    "ReplayEngineMetricsSnapshot",
    "ReplayEngineTraceEntry",
    "ReplayEngineTraceKind",
    "ReplayEventRouter",
    "ReplayRuntimeEngine",
    "ReplayScheduler",
    "ReplaySeekRuntime",
    "ReplayStateStore",
    "ReplayWebsocketBridge",
    "ReplayWebsocketSink",
    "SeekOutcome",
    "SnapshotRestoreResult",
    "SnapshotRuntime",
    "SpeedChange",
    "SpeedController",
    "StateListener",
    "VirtualRuntimeState",
    "build_engine_diagnostics",
    "check_post_dispatch",
    "check_pre_dispatch",
    "clear_engine_trace",
    "default_projection_registry",
    "domain_reducer",
    "get_engine_metrics",
    "get_engine_metrics_snapshot",
    "get_engine_trace",
    "is_engine_trace_enabled",
    "project_counters",
    "project_domain",
    "project_domain_names",
    "record_engine_trace",
    "reset_engine_metrics",
    "set_engine_trace_enabled",
]
