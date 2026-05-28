from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from asyncviz.runtime.clock import get_runtime_clock

PROTOCOL_VERSION = "1.0"


def _envelope_timestamp() -> float:
    """Wall-clock seconds, sourced from the canonical :class:`RuntimeClock`.

    Centralizing here means every server→client frame agrees on "now" with
    every event flowing through the bus.
    """
    return get_runtime_clock().now()


MessageType = Literal[
    "heartbeat",
    "system_status",
    "runtime_snapshot",
    "runtime_event",
    "metrics_delta",
    "warning_delta",
    "timeline_delta",
    "protocol_error",
    "replay_status",
]


class Envelope(BaseModel):
    """Outer wire frame for every server→client message.

    Future extensions (runtime events, snapshots, command responses) all flow
    through this envelope so the frontend has a single dispatch surface.

    ``sequence`` is optional and only stamped on ordered streams (runtime
    events). It is **monotonically increasing within a single connection
    lifetime of the bridge**; the frontend can use it to dedupe events that
    arrived before the on-connect snapshot.
    """

    model_config = ConfigDict(frozen=True)

    protocol_version: str = PROTOCOL_VERSION
    type: MessageType
    timestamp: float = Field(default_factory=_envelope_timestamp)
    sequence: int | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class HeartbeatPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    server_uptime_seconds: float
    connected_clients: int


class SystemStatusPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    runtime_status: str
    debug: bool


class RuntimeSnapshotPayload(BaseModel):
    """Authoritative state of the runtime at the moment of broadcast.

    The frontend treats the snapshot as the source of truth for ``tasks`` —
    replacing whatever was bootstrapped from /api — and uses
    ``last_sequence`` to drop redundant ``runtime_event`` frames that
    arrived before the snapshot.

    ``clock`` carries the current :class:`ClockSnapshot` so reconnecting
    clients re-sync their local time view (uptime, current sequence,
    ``runtime_id``) in a single round-trip.
    """

    model_config = ConfigDict(frozen=True)

    protocol_version: str = PROTOCOL_VERSION
    last_sequence: int
    tasks: list[dict[str, Any]] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    clock: dict[str, Any] | None = None
    queue: dict[str, Any] | None = None
    state: dict[str, Any] | None = None


def heartbeat(uptime_seconds: float, connected_clients: int) -> Envelope:
    return Envelope(
        type="heartbeat",
        payload=HeartbeatPayload(
            server_uptime_seconds=uptime_seconds,
            connected_clients=connected_clients,
        ).model_dump(),
    )


def system_status(runtime_status: str, *, debug: bool) -> Envelope:
    return Envelope(
        type="system_status",
        payload=SystemStatusPayload(runtime_status=runtime_status, debug=debug).model_dump(),
    )


def runtime_event(payload: dict[str, Any], *, sequence: int | None = None) -> Envelope:
    """Wrap a serialized :class:`RuntimeEvent` for transport over /ws.

    The inner ``payload`` is whatever ``asyncviz.runtime.events.models.to_dict``
    produced — the frontend dispatches on ``payload["event_type"]``.
    """
    return Envelope(type="runtime_event", payload=payload, sequence=sequence)


def runtime_snapshot(
    *,
    last_sequence: int,
    tasks: list[dict[str, Any]],
    metrics: dict[str, Any] | None = None,
    clock: dict[str, Any] | None = None,
    queue: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
) -> Envelope:
    payload = RuntimeSnapshotPayload(
        last_sequence=last_sequence,
        tasks=tasks,
        metrics=metrics or {},
        clock=clock,
        queue=queue,
        state=state,
    )
    return Envelope(type="runtime_snapshot", payload=payload.model_dump())


def metrics_delta(payload: dict[str, Any], *, sequence: int | None = None) -> Envelope:
    """Wrap a :class:`MetricsDelta` for transport over /ws.

    The inner ``payload`` is a JSON-safe view of the aggregator's
    :class:`MetricsDelta` — counter changes + duration_added_seconds +
    terminal_state. Frontend live charts fold this over the existing
    aggregate snapshot.
    """
    return Envelope(type="metrics_delta", payload=payload, sequence=sequence)


def warning_delta(payload: dict[str, Any], *, sequence: int | None = None) -> Envelope:
    """Wrap a :class:`WarningDeltaModel` for transport over /ws.

    Carries the affected :class:`ActiveWarning` plus the lifecycle change
    (``activated`` / ``updated`` / ``deduplicated`` / ``resolved`` /
    ``expired``). Toast UIs filter by severity client-side.
    """
    return Envelope(type="warning_delta", payload=payload, sequence=sequence)


def timeline_delta(payload: dict[str, Any], *, sequence: int | None = None) -> Envelope:
    """Wrap a :class:`TimelineDeltaModel` for transport over /ws.

    Carries one of the timeline lifecycle transitions (segment opened /
    closed / span finalized). Frontend timeline renderers apply each
    delta to the locally-cached :class:`TimelineSnapshot`.
    """
    return Envelope(type="timeline_delta", payload=payload, sequence=sequence)


def replay_status(payload: dict[str, Any]) -> Envelope:
    """Wrap a :class:`ReplayStatusPayload` for transport over /ws.

    Emitted by ``asyncviz replay`` to drive the frontend's replay
    timeline controls. Carries the loaded recording's session window
    (sequence + monotonic span), the playback engine's current
    snapshot (state / speed / position / framesDispatched / paused),
    and operator-facing recording metadata (bundle id, runtime id,
    counts). The frontend's :class:`WebSocketReplayEngineBridge`
    consumes this and updates the replay store so the UI transitions
    out of its "no recording loaded" baseline.

    Carries no ``sequence`` — these envelopes describe overall
    playback state, not an ordered runtime event stream, so the
    central sequence cursor doesn't apply.
    """
    return Envelope(type="replay_status", payload=payload)


def protocol_error(*, code: str, message: str, details: dict[str, Any] | None = None) -> Envelope:
    """Surface a typed websocket protocol error envelope.

    Used by the gateway to communicate handshake / subscription failures
    before closing the connection. Mirrors the canonical REST
    :class:`APIErrorResponse` shape so frontend code can handle errors
    uniformly across transports.
    """
    return Envelope(
        type="protocol_error",
        payload={
            "code": code,
            "message": message,
            "details": details or {},
        },
    )
