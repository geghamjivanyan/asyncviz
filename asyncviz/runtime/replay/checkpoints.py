"""Replay checkpoints — paired snapshots + sequence numbers."""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ReplayCheckpoint:
    """A snapshot pinned to a specific replay sequence.

    The dashboard fast-forward path uses checkpoints to skip the replay
    log for the bulk of recorded history — apply the checkpoint, then
    only replay events with ``sequence > checkpoint.sequence``.

    All snapshot fields are dicts of pre-serialized JSON so the
    checkpoint is self-contained and easily persisted in a future
    replay-recording layer.
    """

    checkpoint_id: str
    sequence: int
    monotonic_ns: int
    wall_seconds: float
    runtime_id: str
    state: dict[str, Any] | None
    timeline: dict[str, Any] | None
    metrics: dict[str, Any] | None
    warnings: dict[str, Any] | None
    label: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "sequence": self.sequence,
            "monotonic_ns": self.monotonic_ns,
            "wall_seconds": self.wall_seconds,
            "runtime_id": self.runtime_id,
            "state": self.state,
            "timeline": self.timeline,
            "metrics": self.metrics,
            "warnings": self.warnings,
            "label": self.label,
        }


class CheckpointStore:
    """Bounded ring of :class:`ReplayCheckpoint`.

    Holds the last ``capacity`` checkpoints in append order. Replays
    typically only need the most recent one — older checkpoints are kept
    as a debugging aid (e.g. comparing the state at two earlier moments).
    """

    def __init__(self, *, capacity: int = 16) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self._lock = threading.Lock()
        self._capacity = capacity
        self._checkpoints: deque[ReplayCheckpoint] = deque(maxlen=capacity)
        self._by_id: dict[str, ReplayCheckpoint] = {}

    def add(self, checkpoint: ReplayCheckpoint) -> None:
        with self._lock:
            if len(self._checkpoints) == self._capacity and self._checkpoints:
                evicted = self._checkpoints[0]
                self._by_id.pop(evicted.checkpoint_id, None)
            self._checkpoints.append(checkpoint)
            self._by_id[checkpoint.checkpoint_id] = checkpoint

    def clear(self) -> None:
        with self._lock:
            self._checkpoints.clear()
            self._by_id.clear()

    def latest(self) -> ReplayCheckpoint | None:
        with self._lock:
            return self._checkpoints[-1] if self._checkpoints else None

    def find_for_replay(self, *, since_sequence: int) -> ReplayCheckpoint | None:
        """Return the freshest checkpoint with ``sequence <= since_sequence``.

        Lets the bridge offer "fast-forward to checkpoint X, then stream
        the gap" semantics to a reconnecting client.
        """
        with self._lock:
            candidate: ReplayCheckpoint | None = None
            for checkpoint in self._checkpoints:
                if checkpoint.sequence <= since_sequence:
                    candidate = checkpoint
                else:
                    break  # checkpoints are in append (sequence) order
            return candidate

    def get(self, checkpoint_id: str) -> ReplayCheckpoint | None:
        with self._lock:
            return self._by_id.get(checkpoint_id)

    def snapshot(self) -> tuple[ReplayCheckpoint, ...]:
        with self._lock:
            return tuple(self._checkpoints)

    def __len__(self) -> int:
        with self._lock:
            return len(self._checkpoints)
