"""Canonical event-memory optimization layer."""

from asyncviz.runtime.memory.compact_event_models import (
    CompactEvent,
    CompactEventCategory,
    CompactReplayFrame,
)
from asyncviz.runtime.memory.event_compaction import (
    compact_dict,
    compact_event,
)
from asyncviz.runtime.memory.event_deduplication import (
    DedupDecision,
    EventDeduplicator,
)
from asyncviz.runtime.memory.event_interning import (
    InternerStats,
    StringInterner,
    get_global_interner,
    reset_global_interner,
)
from asyncviz.runtime.memory.event_memory_layout import (
    categorize_event_type,
    compact_dict_event,
    compact_from_runtime_event,
)
from asyncviz.runtime.memory.event_pooling import (
    ObjectPool,
    PoolExhaustedError,
    PoolReleaseError,
    PoolStats,
    PoolToken,
)
from asyncviz.runtime.memory.memory_backpressure import MemoryOverflowSampler
from asyncviz.runtime.memory.memory_configuration import (
    DEFAULT_DEDUP_WINDOW,
    DEFAULT_INTERNER_CAPACITY,
    DEFAULT_POOL_CAPACITY,
    DEFAULT_REDUCER_CACHE_CAPACITY,
    DEFAULT_REPLAY_CACHE_CAPACITY,
    DEFAULT_TOPOLOGY_NODE_CAPACITY,
    DEFAULT_WEBSOCKET_BUFFER_BYTES,
    DEFAULT_WEBSOCKET_BUFFER_CAPACITY,
    EvictionPolicy,
    MemoryOptimizerConfig,
    default_config,
    lean_config,
    relaxed_config,
)
from asyncviz.runtime.memory.memory_diagnostics import (
    MemoryDiagnostics,
    build_memory_diagnostics,
)
from asyncviz.runtime.memory.memory_observability import (
    MemoryMetricsSnapshot,
    get_memory_metrics,
    get_memory_metrics_snapshot,
    reset_memory_metrics,
)
from asyncviz.runtime.memory.memory_optimizer import (
    EventMemoryOptimizer,
    get_global_optimizer,
    reset_global_optimizer,
)
from asyncviz.runtime.memory.memory_thresholds import (
    BreachListener,
    MemoryThresholdBreach,
    MemoryThresholdMonitor,
)
from asyncviz.runtime.memory.memory_tracing import (
    MemoryTraceEntry,
    MemoryTraceKind,
    clear_memory_trace,
    get_memory_trace,
    is_memory_trace_enabled,
    record_memory_trace,
    set_memory_trace_enabled,
)
from asyncviz.runtime.memory.reducer_memory import (
    BoundedReducerCache,
    ProjectionReusePool,
    get_or_compute,
)
from asyncviz.runtime.memory.replay_compaction import (
    ReplayFrameCache,
    compact_frame,
)
from asyncviz.runtime.memory.replay_memory_layout import (
    compact_replay_dict,
    compact_replay_frame,
)
from asyncviz.runtime.memory.topology_memory import (
    CompactTopology,
    TopologyStats,
)
from asyncviz.runtime.memory.websocket_memory import (
    WebsocketBufferPool,
    WebsocketBufferStats,
)

__all__ = [
    "DEFAULT_DEDUP_WINDOW",
    "DEFAULT_INTERNER_CAPACITY",
    "DEFAULT_POOL_CAPACITY",
    "DEFAULT_REDUCER_CACHE_CAPACITY",
    "DEFAULT_REPLAY_CACHE_CAPACITY",
    "DEFAULT_TOPOLOGY_NODE_CAPACITY",
    "DEFAULT_WEBSOCKET_BUFFER_BYTES",
    "DEFAULT_WEBSOCKET_BUFFER_CAPACITY",
    "BoundedReducerCache",
    "BreachListener",
    "CompactEvent",
    "CompactEventCategory",
    "CompactReplayFrame",
    "CompactTopology",
    "DedupDecision",
    "EventDeduplicator",
    "EventMemoryOptimizer",
    "EvictionPolicy",
    "InternerStats",
    "MemoryDiagnostics",
    "MemoryMetricsSnapshot",
    "MemoryOptimizerConfig",
    "MemoryOverflowSampler",
    "MemoryThresholdBreach",
    "MemoryThresholdMonitor",
    "MemoryTraceEntry",
    "MemoryTraceKind",
    "ObjectPool",
    "PoolExhaustedError",
    "PoolReleaseError",
    "PoolStats",
    "PoolToken",
    "ProjectionReusePool",
    "ReplayFrameCache",
    "StringInterner",
    "TopologyStats",
    "WebsocketBufferPool",
    "WebsocketBufferStats",
    "build_memory_diagnostics",
    "categorize_event_type",
    "clear_memory_trace",
    "compact_dict",
    "compact_dict_event",
    "compact_event",
    "compact_frame",
    "compact_from_runtime_event",
    "compact_replay_dict",
    "compact_replay_frame",
    "default_config",
    "get_global_interner",
    "get_global_optimizer",
    "get_memory_metrics",
    "get_memory_metrics_snapshot",
    "get_memory_trace",
    "get_or_compute",
    "is_memory_trace_enabled",
    "lean_config",
    "record_memory_trace",
    "relaxed_config",
    "reset_global_interner",
    "reset_global_optimizer",
    "reset_memory_metrics",
    "set_memory_trace_enabled",
]
