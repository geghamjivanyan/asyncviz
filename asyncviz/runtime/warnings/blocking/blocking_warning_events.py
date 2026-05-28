"""Runtime-event factories for blocking warnings.

The emitter publishes one event per lifecycle transition. Wire types:

* ``runtime.warnings.blocking.opened``     — group created.
* ``runtime.warnings.blocking.escalated``  — group's severity rose.
* ``runtime.warnings.blocking.active``     — refresh during an active
  group (rate-limited via dedup).
* ``runtime.warnings.blocking.recovered``  — group closed cleanly
  (the originating freeze window closed).
* ``runtime.warnings.blocking.expired``    — recovered group sat past
  its TTL without re-opening.

All events ride on :class:`GenericEvent` so no schema changes are
required and consumers route them like any other event. The detector
in ``runtime/warnings/detectors.py`` consumes these to drive the
:class:`RuntimeWarningManager` lifecycle.
"""

from __future__ import annotations

import uuid
from typing import Any

from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.events.models.base import GenericEvent
from asyncviz.runtime.events.models.enums import EventSource
from asyncviz.runtime.warnings.blocking.blocking_warning_payloads import (
    BlockingWarningPayload,
)

BLOCKING_WARNING_OPENED_EVENT_TYPE: str = "runtime.warnings.blocking.opened"
BLOCKING_WARNING_ESCALATED_EVENT_TYPE: str = "runtime.warnings.blocking.escalated"
BLOCKING_WARNING_ACTIVE_EVENT_TYPE: str = "runtime.warnings.blocking.active"
BLOCKING_WARNING_RECOVERED_EVENT_TYPE: str = "runtime.warnings.blocking.recovered"
BLOCKING_WARNING_EXPIRED_EVENT_TYPE: str = "runtime.warnings.blocking.expired"


_TRANSITION_TO_EVENT_TYPE: dict[str, str] = {
    "opened": BLOCKING_WARNING_OPENED_EVENT_TYPE,
    "escalated": BLOCKING_WARNING_ESCALATED_EVENT_TYPE,
    "active": BLOCKING_WARNING_ACTIVE_EVENT_TYPE,
    "recovered": BLOCKING_WARNING_RECOVERED_EVENT_TYPE,
    "expired": BLOCKING_WARNING_EXPIRED_EVENT_TYPE,
}


def event_type_for_transition(transition: str) -> str:
    """Look up the wire type for a lifecycle transition.

    Raises :class:`KeyError` for unknown transitions — the emitter only
    ever calls with values from the :class:`BlockingWarningGroupState`
    enum, so a miss here means a bug.
    """
    return _TRANSITION_TO_EVENT_TYPE[transition]


def build_blocking_warning_event(
    *,
    payload: BlockingWarningPayload,
    runtime_id: uuid.UUID | None = None,
) -> RuntimeEvent:
    """Wrap a payload in the matching :class:`GenericEvent`.

    The transition string on the payload picks the event type, so
    callers don't have to keep the two in sync.
    """
    kwargs: dict[str, Any] = {
        "event_type": event_type_for_transition(payload.transition),
        "source": EventSource.RUNTIME.value,
        "payload": payload.to_dict(),
    }
    if runtime_id is not None:
        kwargs["runtime_id"] = runtime_id
    return GenericEvent(**kwargs)


BLOCKING_WARNING_EVENT_TYPES: tuple[str, ...] = (
    BLOCKING_WARNING_OPENED_EVENT_TYPE,
    BLOCKING_WARNING_ESCALATED_EVENT_TYPE,
    BLOCKING_WARNING_ACTIVE_EVENT_TYPE,
    BLOCKING_WARNING_RECOVERED_EVENT_TYPE,
    BLOCKING_WARNING_EXPIRED_EVENT_TYPE,
)


def is_blocking_warning_event(event_type: str) -> bool:
    """True iff ``event_type`` is one of the emitter's wire types."""
    return event_type in _TRANSITION_TO_EVENT_TYPE.values()
