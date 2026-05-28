"""Runtime-event factories for lag-monitor output.

The monitor never builds events directly — it calls these factories so
the wire shape is centralized and stable across consumers (websocket
bridge, replay buffer, future timeline overlays). Both event types use
the existing :class:`GenericEvent` envelope (no schema changes required)
with a typed ``event_type`` string and a normalized payload.

Event types:

* ``runtime.monitoring.lag.sample``   — one measurement (rare in
  production; opt-in via :attr:`LagConfiguration.emit_measurement_events`).
* ``runtime.monitoring.lag.threshold``— a measurement that tripped a
  threshold; emitted by default.
"""

from __future__ import annotations

import uuid
from typing import Any

from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.events.models.base import GenericEvent
from asyncviz.runtime.events.models.enums import EventSource
from asyncviz.runtime.monitoring.event_loop.lag_measurement import LagMeasurement
from asyncviz.runtime.monitoring.event_loop.lag_thresholds import (
    LagSeverity,
    LagThresholdEvaluation,
)

LAG_MEASUREMENT_EVENT_TYPE: str = "runtime.monitoring.lag.sample"
LAG_THRESHOLD_BREACH_EVENT_TYPE: str = "runtime.monitoring.lag.threshold"


def _measurement_payload(measurement: LagMeasurement) -> dict[str, Any]:
    return measurement.to_dict()


def build_lag_measurement_event(
    measurement: LagMeasurement,
    *,
    runtime_id: uuid.UUID | None = None,
) -> RuntimeEvent:
    """Build a sample event from a measurement.

    Used only when ``emit_measurement_events`` is on. The payload is the
    full ``measurement.to_dict()`` so consumers don't need to know the
    measurement type — they can read the dict.
    """
    payload: dict[str, Any] = {"measurement": _measurement_payload(measurement)}
    kwargs: dict[str, Any] = {
        "event_type": LAG_MEASUREMENT_EVENT_TYPE,
        "source": EventSource.RUNTIME.value,
        "payload": payload,
    }
    if runtime_id is not None:
        kwargs["runtime_id"] = runtime_id
    return GenericEvent(**kwargs)


def build_lag_threshold_breach_event(
    measurement: LagMeasurement,
    evaluation: LagThresholdEvaluation,
    *,
    runtime_id: uuid.UUID | None = None,
) -> RuntimeEvent:
    """Build a threshold-breach event.

    Emitted whenever a measurement's severity is ``>= WARNING``. The
    payload carries enough context for the warning manager to derive a
    stable dedup key and human-readable message.
    """
    payload: dict[str, Any] = {
        "measurement": _measurement_payload(measurement),
        "severity": evaluation.severity.name,
        "severity_value": int(evaluation.severity),
        "threshold_ns": evaluation.threshold_ns,
        "lag_ns": evaluation.lag_ns,
        "breached": evaluation.breached,
    }
    kwargs: dict[str, Any] = {
        "event_type": LAG_THRESHOLD_BREACH_EVENT_TYPE,
        "source": EventSource.RUNTIME.value,
        "payload": payload,
    }
    if runtime_id is not None:
        kwargs["runtime_id"] = runtime_id
    return GenericEvent(**kwargs)


def severity_to_warning_severity(severity: LagSeverity) -> str:
    """Map a :class:`LagSeverity` to the canonical warning-severity string.

    Returned values come from :class:`asyncviz.runtime.events.models.enums.WarningSeverity`
    — kept as strings here to avoid a circular import. The warning
    manager re-validates the value when it constructs the lifecycle.
    """
    if severity is LagSeverity.FREEZE:
        return "critical"
    if severity is LagSeverity.CRITICAL:
        return "error"
    if severity is LagSeverity.WARNING:
        return "warning"
    return "info"
