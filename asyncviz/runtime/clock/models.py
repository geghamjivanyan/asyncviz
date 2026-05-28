from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class ClockSnapshot(BaseModel):
    """JSON-safe snapshot of a :class:`RuntimeClock` at a moment in time.

    Surfaced via ``/api/runtime/clock`` and embedded in runtime metrics
    payloads. Field names are part of the public protocol — coordinate with
    the TypeScript ``ClockSnapshot`` type.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    runtime_id: uuid.UUID
    started_at_wall_seconds: float
    started_at_monotonic_ns: int
    wall_now_seconds: float
    wall_now_iso: str
    monotonic_now_ns: int
    monotonic_now_seconds: float
    uptime_seconds: float
    uptime_ns: int
    current_sequence: int


class ClockMetricsSnapshot(BaseModel):
    """Lightweight throughput-style counters on the clock.

    Kept separate from :class:`ClockSnapshot` so transports that only want
    counters (Prometheus, future ``/metrics``) don't have to pull a full
    timestamp triple every scrape.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    runtime_id: uuid.UUID
    sequence_issued: int
    timestamps_issued: int
    uptime_seconds: float
