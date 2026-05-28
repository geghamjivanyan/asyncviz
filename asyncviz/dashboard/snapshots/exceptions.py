from __future__ import annotations


class SnapshotError(Exception):
    """Base class for every :class:`SnapshotService` failure."""


class SnapshotUnavailableError(SnapshotError):
    """Raised when a required upstream snapshot source is missing."""


class SnapshotConsistencyError(SnapshotError):
    """Raised when the aggregated snapshot cannot satisfy its consistency contract.

    Today this is reserved for the future cross-source sequence-reconciliation
    path. The current generation pipeline is wholly local (everything reads
    from in-process services under a single lock), so it can't trip yet.
    """
