"""Memory-optimizer configuration.

Centralizes capacities, eviction policies, and behavior flags for
every component of the memory-optimization layer. The defaults are
tuned for general-purpose runtimes; long-running deployments
override via :func:`build_config`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Literal

DEFAULT_INTERNER_CAPACITY: Final[int] = 4096
"""Soft cap on the interner's table. Beyond this, the interner
falls back to "no interning" for new strings rather than evicting
hot entries — eviction would invalidate canonical-identity
guarantees callers depend on."""

DEFAULT_POOL_CAPACITY: Final[int] = 256
DEFAULT_DEDUP_WINDOW: Final[int] = 1024
DEFAULT_REDUCER_CACHE_CAPACITY: Final[int] = 512
DEFAULT_TOPOLOGY_NODE_CAPACITY: Final[int] = 65536
DEFAULT_WEBSOCKET_BUFFER_CAPACITY: Final[int] = 16
DEFAULT_WEBSOCKET_BUFFER_BYTES: Final[int] = 64 * 1024
DEFAULT_REPLAY_CACHE_CAPACITY: Final[int] = 32

EvictionPolicy = Literal["lru", "fifo", "block"]


@dataclass(frozen=True, slots=True)
class MemoryOptimizerConfig:
    """Immutable memory-optimizer configuration."""

    interning_enabled: bool = True
    interner_capacity: int = DEFAULT_INTERNER_CAPACITY

    pooling_enabled: bool = True
    pool_capacity: int = DEFAULT_POOL_CAPACITY

    dedup_enabled: bool = True
    dedup_window: int = DEFAULT_DEDUP_WINDOW

    reducer_cache_capacity: int = DEFAULT_REDUCER_CACHE_CAPACITY
    reducer_eviction: EvictionPolicy = "lru"

    topology_node_capacity: int = DEFAULT_TOPOLOGY_NODE_CAPACITY

    websocket_buffer_count: int = DEFAULT_WEBSOCKET_BUFFER_CAPACITY
    websocket_buffer_bytes: int = DEFAULT_WEBSOCKET_BUFFER_BYTES

    replay_frame_cache_capacity: int = DEFAULT_REPLAY_CACHE_CAPACITY

    track_allocation_deltas: bool = False
    """When True, hot-path operations record tracemalloc deltas.
    Off by default — adds ~10x overhead."""

    strict_pool_safety: bool = True
    """When True, double-release on a pool token raises rather than
    being silently swallowed."""

    extras: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.interner_capacity < 1:
            raise ValueError("interner_capacity must be >= 1")
        if self.pool_capacity < 1:
            raise ValueError("pool_capacity must be >= 1")
        if self.dedup_window < 1:
            raise ValueError("dedup_window must be >= 1")
        if self.reducer_cache_capacity < 1:
            raise ValueError("reducer_cache_capacity must be >= 1")
        if self.topology_node_capacity < 1:
            raise ValueError("topology_node_capacity must be >= 1")
        if self.websocket_buffer_count < 1:
            raise ValueError("websocket_buffer_count must be >= 1")
        if self.websocket_buffer_bytes < 256:
            raise ValueError("websocket_buffer_bytes must be >= 256")
        if self.replay_frame_cache_capacity < 1:
            raise ValueError("replay_frame_cache_capacity must be >= 1")


def default_config() -> MemoryOptimizerConfig:
    return MemoryOptimizerConfig()


def lean_config() -> MemoryOptimizerConfig:
    """Tight caps for memory-constrained deployments."""
    return MemoryOptimizerConfig(
        interner_capacity=1024,
        pool_capacity=64,
        dedup_window=256,
        reducer_cache_capacity=128,
        topology_node_capacity=8192,
        websocket_buffer_count=4,
        websocket_buffer_bytes=8 * 1024,
        replay_frame_cache_capacity=8,
    )


def relaxed_config() -> MemoryOptimizerConfig:
    """Larger caps for million-event replay sessions."""
    return MemoryOptimizerConfig(
        interner_capacity=65536,
        pool_capacity=1024,
        dedup_window=8192,
        reducer_cache_capacity=4096,
        topology_node_capacity=524288,
        websocket_buffer_count=64,
        websocket_buffer_bytes=256 * 1024,
        replay_frame_cache_capacity=128,
    )
