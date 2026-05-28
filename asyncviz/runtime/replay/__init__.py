"""Canonical event replay buffer.

Public surface:

* :class:`EventReplayBuffer` — the canonical replay log + checkpoint store.
* :class:`ReplayFrame` — immutable per-event record.
* :class:`ReplayCheckpoint` — sequence-pinned subsystem snapshot.
* :class:`ReplaySnapshot` / :class:`ReplayBatchModel` /
  :class:`ReplayWindowModel` / :class:`ReplayCheckpointModel` /
  :class:`ReplayFrameModel` / :class:`ReplaySelfMetricsModel` — Pydantic
  wire models. Coordinate with the TypeScript ``Replay*`` interfaces.
* :class:`FrameRetention`, :class:`CheckpointStore` — primitives.
* Reconstruction: :func:`replay_into_state_store`, :func:`replay_into_metrics`,
  :func:`replay_into_warning_manager`.
* exceptions — :class:`ReplayError`, :class:`ReplayWindowMissError`,
  :class:`ReplayCheckpointError`, :class:`ReplayReconstructionError`.

Design rule: a runtime has exactly **one** :class:`EventReplayBuffer`. It
subscribes to the state store's :class:`StateChange` stream and is the
authoritative log for sequence-windowed replay queries.
"""

from asyncviz.runtime.replay.buffer import EventReplayBuffer
from asyncviz.runtime.replay.checkpoints import CheckpointStore, ReplayCheckpoint
from asyncviz.runtime.replay.exceptions import (
    ReplayCheckpointError,
    ReplayError,
    ReplayReconstructionError,
    ReplayWindowMissError,
)
from asyncviz.runtime.replay.frames import ReplayFrame, frame_from_event
from asyncviz.runtime.replay.indexing import (
    build_batch,
    build_window,
    checkpoint_to_model,
    frame_to_model,
)
from asyncviz.runtime.replay.models import (
    ReplayBatchModel,
    ReplayCheckpointModel,
    ReplayFrameModel,
    ReplaySelfMetricsModel,
    ReplaySnapshot,
    ReplayWindowModel,
)
from asyncviz.runtime.replay.reconstruction import (
    replay_into_metrics,
    replay_into_state_store,
    replay_into_warning_manager,
)
from asyncviz.runtime.replay.retention import DEFAULT_FRAME_LIMIT, FrameRetention
from asyncviz.runtime.replay.streaming import (
    ReplayListener,
    ReplaySubscription,
    ReplaySubscriptionRegistry,
)

__all__ = [
    "DEFAULT_FRAME_LIMIT",
    "CheckpointStore",
    "EventReplayBuffer",
    "FrameRetention",
    "ReplayBatchModel",
    "ReplayCheckpoint",
    "ReplayCheckpointError",
    "ReplayCheckpointModel",
    "ReplayError",
    "ReplayFrame",
    "ReplayFrameModel",
    "ReplayListener",
    "ReplayReconstructionError",
    "ReplaySelfMetricsModel",
    "ReplaySnapshot",
    "ReplaySubscription",
    "ReplaySubscriptionRegistry",
    "ReplayWindowMissError",
    "ReplayWindowModel",
    "build_batch",
    "build_window",
    "checkpoint_to_model",
    "frame_from_event",
    "frame_to_model",
    "replay_into_metrics",
    "replay_into_state_store",
    "replay_into_warning_manager",
]
