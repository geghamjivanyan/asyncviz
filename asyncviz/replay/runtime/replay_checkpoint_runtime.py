"""Engine-side checkpoints.

The recording layer's snapshots are captured at write time. During
*playback*, the engine takes its *own* periodic state checkpoints
so a seek backward can resume from the most recent in-memory
checkpoint instead of re-reading + re-reducing snapshot frames from
disk.

Checkpoints are kept in a bounded LRU keyed by sequence so memory
stays bounded under long replay sessions.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Final

from asyncviz.replay.runtime.models.runtime_state import VirtualRuntimeState

DEFAULT_CHECKPOINT_RING_CAPACITY: Final[int] = 32


@dataclass(frozen=True, slots=True)
class Checkpoint:
    """One in-memory state checkpoint."""

    sequence: int
    monotonic_ns: int
    state: VirtualRuntimeState


class CheckpointRuntime:
    """Bounded LRU of (sequence → state) checkpoints."""

    __slots__ = ("_capacity", "_checkpoints", "_lock")

    def __init__(self, capacity: int = DEFAULT_CHECKPOINT_RING_CAPACITY) -> None:
        if capacity < 1:
            raise ValueError("checkpoint capacity must be >= 1")
        self._capacity = capacity
        self._lock = threading.Lock()
        self._checkpoints: OrderedDict[int, Checkpoint] = OrderedDict()

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._checkpoints)

    def record(self, state: VirtualRuntimeState) -> Checkpoint:
        cp = Checkpoint(
            sequence=state.last_sequence,
            monotonic_ns=state.last_monotonic_ns,
            state=state,
        )
        with self._lock:
            if cp.sequence in self._checkpoints:
                self._checkpoints.move_to_end(cp.sequence)
            self._checkpoints[cp.sequence] = cp
            while len(self._checkpoints) > self._capacity:
                self._checkpoints.popitem(last=False)
        return cp

    def nearest_at_or_before(self, sequence: int) -> Checkpoint | None:
        with self._lock:
            best: Checkpoint | None = None
            for seq, cp in self._checkpoints.items():
                if seq <= sequence and (best is None or seq > best.sequence):
                    best = cp
        return best

    def clear(self) -> None:
        with self._lock:
            self._checkpoints.clear()

    def all(self) -> tuple[Checkpoint, ...]:
        with self._lock:
            return tuple(self._checkpoints.values())
