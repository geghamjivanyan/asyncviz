"""Wire-envelope builders for streaming deltas.

Each delta originates as a typed value on the runtime side
(:class:`MetricsDelta`, :class:`WarningDelta`, :class:`TimelineDelta`).
This module is the single place those typed values are converted to
JSON-safe payloads ready for :class:`Envelope` transport.

Keeping the conversions in one module means the wire shape stays in
sync with the TypeScript interfaces — a change here is the one place
the frontend mirror needs to be updated.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from asyncviz.runtime.events.models import to_dict

if TYPE_CHECKING:
    from asyncviz.runtime.metrics import MetricsDelta
    from asyncviz.runtime.warnings import WarningDelta


def metrics_delta_payload(delta: MetricsDelta) -> dict[str, Any]:
    """Convert a :class:`MetricsDelta` into a JSON-safe wire payload.

    Carries the *change set* + per-event metadata. The frontend folds
    this into its locally-cached aggregate snapshot — it doesn't need
    the whole snapshot to update sparklines.
    """
    return {
        "event_type": delta.event.event_type,
        "event_id": str(delta.event.event_id),
        "sequence": delta.sequence,
        "last_sequence": delta.last_sequence,
        "monotonic_ns": delta.event.monotonic_ns,
        "wall_seconds": delta.event.timestamp,
        "changes": dict(delta.changes),
        "duration_added_seconds": delta.duration_added_seconds,
        "coroutine_name": delta.coroutine_name,
        "terminal_state": delta.terminal_state,
    }


def warning_delta_payload(delta: WarningDelta) -> dict[str, Any]:
    """Convert a :class:`WarningDelta` into a JSON-safe wire payload."""
    from asyncviz.runtime.warnings.snapshots import lifecycle_to_active

    active = lifecycle_to_active(delta.warning).model_dump(mode="json")
    return {
        "change": delta.change.value,
        "sequence": delta.sequence,
        "last_sequence": delta.last_sequence,
        "warning": active,
    }


def runtime_event_payload_from(event_obj: Any) -> dict[str, Any]:
    """Serialize one :class:`RuntimeEvent` for wire transport.

    Re-exported here so streaming consumers don't have to import the
    ``runtime.events.models`` module directly.
    """
    return to_dict(event_obj)
