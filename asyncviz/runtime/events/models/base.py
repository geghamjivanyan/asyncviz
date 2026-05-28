from __future__ import annotations

import uuid
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from asyncviz.runtime.clock import get_runtime_clock
from asyncviz.runtime.events.models.enums import EventSource

#: Bumped when the *envelope* shape changes (new required field, removed field,
#: semantics change). Per-event-class evolution is signalled by
#: :attr:`RuntimeEvent.payload_version`.
PROTOCOL_VERSION: int = 1


def _default_wall_seconds() -> float:
    return get_runtime_clock().now()


def _default_monotonic_seconds() -> float:
    return get_runtime_clock().monotonic()


def _default_monotonic_ns() -> int:
    return get_runtime_clock().monotonic_ns()


def _default_runtime_id() -> uuid.UUID:
    return get_runtime_clock().runtime_id


class RuntimeEvent(BaseModel):
    """Canonical envelope for every event flowing through the AsyncViz bus.

    Concrete event classes inherit from this and add their own typed fields
    directly on the model (flat JSON shape — no nested ``payload`` wrapper).
    The envelope fields below are present on every event.

    Frozen for safety: an event is a value, not a mutable record.

    Timing fields are populated from the canonical :class:`RuntimeClock`:

      * ``timestamp``           — wall-clock float seconds; drift-safe (anchored
        once at clock construction, advances via monotonic delta).
      * ``monotonic_timestamp`` — float-seconds monotonic reading; the
        ordering primitive carried *on the event itself*. Strictly
        non-decreasing within a runtime.
      * ``monotonic_ns``        — same instant in integer nanoseconds; the
        nanosecond-precision source of truth (timeline / replay use this).
      * ``runtime_id``          — identity of the issuing clock; same value
        across all events from one runtime, fresh on restart.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="ignore",
        populate_by_name=True,
        validate_assignment=False,
    )

    #: The constant ``event_type`` string for this class. Subclasses redefine
    #: it as a ``Literal`` field so Pydantic emits the right discriminator.
    EVENT_TYPE_DEFAULT: ClassVar[str] = "runtime.event"

    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    event_type: str
    timestamp: float = Field(default_factory=_default_wall_seconds)
    monotonic_timestamp: float = Field(default_factory=_default_monotonic_seconds)
    monotonic_ns: int = Field(default_factory=_default_monotonic_ns)
    runtime_id: uuid.UUID = Field(default_factory=_default_runtime_id)
    source: str = EventSource.RUNTIME.value
    payload_version: int = 1

    # ── convenience constructors ─────────────────────────────────────────
    @classmethod
    def of(cls, event_type: str, **payload: Any) -> GenericEvent:
        """Shorthand for ad-hoc events.

        Returns a :class:`GenericEvent` carrying ``payload`` as a free-form
        dict. Use the typed subclasses (e.g. :class:`TaskCreatedEvent`) when
        the event has a stable schema; reach for ``of()`` for tests and
        bootstrapping code.
        """
        return GenericEvent(event_type=event_type, payload=payload)


class GenericEvent(RuntimeEvent):
    """Escape-hatch event for ad-hoc names that don't yet have a dedicated class.

    The ``payload`` field is a free-form mapping so callers can carry
    anything without inventing a new model. Newly stable event types should
    graduate to their own subclass — the wire shape stays compatible because
    the registry knows about both.
    """

    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
