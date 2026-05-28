"""Frozen failure-event record."""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.runtime.resilience.models.failure_kind import FailureKind


@dataclass(frozen=True, slots=True)
class FailureEvent:
    """A single observed subsystem failure."""

    subsystem: str
    kind: FailureKind
    detail: str
    """Short, structured detail — exception class + first 200 chars
    of the message. Never includes a full traceback (we keep traces
    in the runtime trace ring, not on every failure)."""

    at_ns: int
    payload_kind: str = ""
    """Optional payload bucket (frame type, event class) used by
    quarantine logic when ``SubsystemPolicy.quarantine_payload_kind``
    is True."""

    recoverable: bool = True
