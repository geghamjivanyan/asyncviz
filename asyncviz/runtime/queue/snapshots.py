from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class QueueSnapshotResponse(BaseModel):
    """JSON-safe :class:`InternalEventQueue` snapshot for REST + websocket transport.

    Field names are part of the public protocol — coordinate with the
    TypeScript ``QueueSnapshotResponse`` definition.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    capacity: int
    depth: int
    overflow_strategy: str
    retention_capacity: int
    retained: int
    oldest_retained_sequence: int | None
    newest_retained_sequence: int | None
    running: bool
    metrics: dict[str, Any]


class ReplayResult(BaseModel):
    """Outcome of an ``events_since(sequence)`` request.

    Carries enough context for the websocket bridge to decide between
    streaming the replay events to a reconnecting client or falling back to
    a fresh snapshot.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    requested_sequence: int
    hit: bool
    oldest_available_sequence: int | None
    newest_available_sequence: int | None
    events: list[dict[str, Any]]
