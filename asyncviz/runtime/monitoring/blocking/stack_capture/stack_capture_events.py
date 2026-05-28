"""Runtime-event factory for stack captures.

One event type:

* ``runtime.monitoring.blocking.stack_capture`` — carries the serialized
  :class:`CapturedStack` payload directly. Replay-safe: identical
  captures serialize to byte-identical payloads.

Rides on :class:`GenericEvent` so no schema changes are required and
the warning manager / replay buffer route it like any other event.
"""

from __future__ import annotations

import uuid
from typing import Any

from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.events.models.base import GenericEvent
from asyncviz.runtime.events.models.enums import EventSource

BLOCKING_STACK_CAPTURE_EVENT_TYPE: str = "runtime.monitoring.blocking.stack_capture"


def build_stack_capture_event(
    *,
    payload: dict[str, Any],
    runtime_id: uuid.UUID | None = None,
) -> RuntimeEvent:
    """Wrap a pre-serialized capture payload in a :class:`GenericEvent`.

    The payload comes from :class:`StackSerializer.serialize`, so it's
    already JSON-safe + size-bounded. We don't transform it here — the
    serializer is the single source of truth for the payload shape.
    """
    kwargs: dict[str, Any] = {
        "event_type": BLOCKING_STACK_CAPTURE_EVENT_TYPE,
        "source": EventSource.RUNTIME.value,
        "payload": payload,
    }
    if runtime_id is not None:
        kwargs["runtime_id"] = runtime_id
    return GenericEvent(**kwargs)


STACK_CAPTURE_EVENT_TYPES: tuple[str, ...] = (BLOCKING_STACK_CAPTURE_EVENT_TYPE,)
