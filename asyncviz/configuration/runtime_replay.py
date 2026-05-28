"""In-memory replay-buffer runtime options.

Distinct from :class:`RuntimeRecordingOptions` — that struct controls
on-disk recording; this one controls the live in-memory replay log
the dashboard streams from.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.configuration.runtime_defaults import (
    DEFAULT_REPLAY_BUFFER_CAPACITY,
    DEFAULT_REPLAY_CHECKPOINT_INTERVAL_SECONDS,
    DEFAULT_REPLAY_RETENTION_SECONDS,
)


@dataclass(frozen=True, slots=True)
class ReplayOptions:
    """In-memory :class:`EventReplayBuffer` knobs."""

    buffer_capacity: int = DEFAULT_REPLAY_BUFFER_CAPACITY
    retention_seconds: float = DEFAULT_REPLAY_RETENTION_SECONDS
    checkpoint_interval_seconds: float = DEFAULT_REPLAY_CHECKPOINT_INTERVAL_SECONDS
