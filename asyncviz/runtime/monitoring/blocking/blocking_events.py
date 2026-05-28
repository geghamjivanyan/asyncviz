"""Runtime-event factories for blocking-detector output.

All three event types ride on the existing :class:`GenericEvent`
envelope so no schema changes are required and old clients can route
them as ``GenericEvent`` if they don't know about the new types.

Event types:

* ``runtime.monitoring.blocking.violation``     — single classified
  violation (post-cooldown).
* ``runtime.monitoring.blocking.escalation``    — severity upgrade
  triggered by consecutive-violation pressure.
* ``runtime.monitoring.blocking.window.opened`` — new blocking window.
* ``runtime.monitoring.blocking.window.closed`` — window finalization.
"""

from __future__ import annotations

import uuid
from typing import Any

from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.events.models.base import GenericEvent
from asyncviz.runtime.events.models.enums import EventSource
from asyncviz.runtime.monitoring.blocking.blocking_classifier import (
    BlockingClassification,
    BlockingSeverity,
)
from asyncviz.runtime.monitoring.blocking.blocking_escalation import EscalationOutcome
from asyncviz.runtime.monitoring.blocking.blocking_windows import BlockingWindowSnapshot

BLOCKING_VIOLATION_EVENT_TYPE: str = "runtime.monitoring.blocking.violation"
BLOCKING_ESCALATION_EVENT_TYPE: str = "runtime.monitoring.blocking.escalation"
BLOCKING_WINDOW_OPENED_EVENT_TYPE: str = "runtime.monitoring.blocking.window.opened"
BLOCKING_WINDOW_CLOSED_EVENT_TYPE: str = "runtime.monitoring.blocking.window.closed"


def _envelope_kwargs(runtime_id: uuid.UUID | None) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"source": EventSource.RUNTIME.value}
    if runtime_id is not None:
        kwargs["runtime_id"] = runtime_id
    return kwargs


def build_blocking_violation_event(
    *,
    classification: BlockingClassification,
    outcome: EscalationOutcome,
    active_window: BlockingWindowSnapshot | None,
    runtime_id: uuid.UUID | None = None,
) -> RuntimeEvent:
    """Single-violation event with classification + escalation context.

    ``active_window`` is included so downstream consumers can correlate
    the violation with the freeze it belongs to without having to
    re-derive window membership from the event stream.
    """
    payload: dict[str, Any] = {
        "classification": classification.to_dict(),
        "effective_severity": outcome.effective_severity.name,
        "effective_severity_value": int(outcome.effective_severity),
        "escalated": outcome.escalated,
        "consecutive_warning": outcome.consecutive_warning,
        "consecutive_critical": outcome.consecutive_critical,
        "consecutive_freeze": outcome.consecutive_freeze,
        "active_window": active_window.to_dict() if active_window is not None else None,
    }
    return GenericEvent(
        event_type=BLOCKING_VIOLATION_EVENT_TYPE,
        payload=payload,
        **_envelope_kwargs(runtime_id),
    )


def build_blocking_escalation_event(
    *,
    outcome: EscalationOutcome,
    active_window: BlockingWindowSnapshot | None,
    runtime_id: uuid.UUID | None = None,
) -> RuntimeEvent:
    """Severity upgrade. Only emitted when ``outcome.escalated`` is true."""
    from_severity: BlockingSeverity = outcome.escalation_from  # type: ignore[assignment]
    to_severity: BlockingSeverity = outcome.escalation_to  # type: ignore[assignment]
    payload: dict[str, Any] = {
        "from_severity": from_severity.name,
        "from_severity_value": int(from_severity),
        "to_severity": to_severity.name,
        "to_severity_value": int(to_severity),
        "classification": outcome.classification.to_dict(),
        "consecutive_warning": outcome.consecutive_warning,
        "consecutive_critical": outcome.consecutive_critical,
        "active_window": active_window.to_dict() if active_window is not None else None,
    }
    return GenericEvent(
        event_type=BLOCKING_ESCALATION_EVENT_TYPE,
        payload=payload,
        **_envelope_kwargs(runtime_id),
    )


def build_blocking_window_opened_event(
    *,
    window: BlockingWindowSnapshot,
    classification: BlockingClassification,
    runtime_id: uuid.UUID | None = None,
) -> RuntimeEvent:
    payload: dict[str, Any] = {
        "window": window.to_dict(),
        "trigger_classification": classification.to_dict(),
    }
    return GenericEvent(
        event_type=BLOCKING_WINDOW_OPENED_EVENT_TYPE,
        payload=payload,
        **_envelope_kwargs(runtime_id),
    )


def build_blocking_window_closed_event(
    *,
    window: BlockingWindowSnapshot,
    runtime_id: uuid.UUID | None = None,
) -> RuntimeEvent:
    payload: dict[str, Any] = {"window": window.to_dict()}
    return GenericEvent(
        event_type=BLOCKING_WINDOW_CLOSED_EVENT_TYPE,
        payload=payload,
        **_envelope_kwargs(runtime_id),
    )


BLOCKING_EVENT_TYPES: tuple[str, ...] = (
    BLOCKING_VIOLATION_EVENT_TYPE,
    BLOCKING_ESCALATION_EVENT_TYPE,
    BLOCKING_WINDOW_OPENED_EVENT_TYPE,
    BLOCKING_WINDOW_CLOSED_EVENT_TYPE,
)
