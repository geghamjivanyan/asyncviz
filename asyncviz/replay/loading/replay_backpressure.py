"""Loader-side safety caps.

The loader is pull-based, so the only place unbounded memory growth
could happen is when a caller materializes frames into a list /
deque. The guards here are advisory — :func:`enforce_buffer_cap`
raises before crossing a threshold so misuse fails loudly instead
of OOM-ing.

Distinct from the format layer's :data:`MAX_FRAME_LINE_BYTES`,
which guards per-*line* size; this module guards per-*buffer* size.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

DEFAULT_MAX_BUFFER_FRAMES: Final[int] = 4096


class ReplayBufferOverflowError(RuntimeError):
    """Raised when a buffered loader exceeds its frame cap."""


@dataclass(slots=True)
class BufferCap:
    """Lightweight counter used by buffered loaders."""

    capacity: int = DEFAULT_MAX_BUFFER_FRAMES
    _depth: int = 0

    @property
    def depth(self) -> int:
        return self._depth

    @property
    def at_capacity(self) -> bool:
        return self._depth >= self.capacity

    def add(self, count: int = 1) -> None:
        self._depth += count
        if self._depth > self.capacity:
            raise ReplayBufferOverflowError(
                f"replay buffer exceeded capacity {self.capacity} (depth={self._depth})",
            )

    def remove(self, count: int = 1) -> None:
        self._depth = max(0, self._depth - count)

    def reset(self) -> None:
        self._depth = 0


def enforce_buffer_cap(depth: int, capacity: int) -> None:
    """One-shot check — used by helpers that buffer ahead of decode."""
    if depth >= capacity:
        raise ReplayBufferOverflowError(
            f"replay buffer would exceed capacity {capacity} (would-be depth={depth})",
        )
