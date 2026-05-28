from __future__ import annotations


class ReplayError(Exception):
    """Base class for every :class:`EventReplayBuffer` failure."""


class ReplayWindowMissError(ReplayError):
    """Raised by strict callers when ``since_sequence`` is older than retention.

    The default ``replay_since()`` path returns a miss-marked
    :class:`ReplayBatch` rather than raising; this exception is for tools
    that prefer hard failures (replay validators, debuggers).
    """


class ReplayCheckpointError(ReplayError):
    """Raised when a checkpoint operation cannot complete coherently."""


class ReplayReconstructionError(ReplayError):
    """Raised when :func:`replay_into` finds inconsistent input."""
