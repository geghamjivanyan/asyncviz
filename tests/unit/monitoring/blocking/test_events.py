from __future__ import annotations

import uuid

from asyncviz.runtime.monitoring.blocking import (
    BLOCKING_ESCALATION_EVENT_TYPE,
    BLOCKING_EVENT_TYPES,
    BLOCKING_VIOLATION_EVENT_TYPE,
    BLOCKING_WINDOW_CLOSED_EVENT_TYPE,
    BLOCKING_WINDOW_OPENED_EVENT_TYPE,
    BlockingClassifier,
    BlockingSeverity,
    EscalationOutcome,
    build_blocking_escalation_event,
    build_blocking_violation_event,
    build_blocking_window_closed_event,
    build_blocking_window_opened_event,
)
from asyncviz.runtime.monitoring.blocking.blocking_windows import BlockingWindowSnapshot

from ._helpers import TIGHT_THRESHOLDS, measure


def _classify(lag_ns: int = 50_000_000):
    return BlockingClassifier().classify(measure(lag_ns), TIGHT_THRESHOLDS.evaluate(lag_ns))


def _outcome(
    *,
    escalated: bool = False,
    effective: BlockingSeverity = BlockingSeverity.CRITICAL,
) -> EscalationOutcome:
    cls = _classify()
    return EscalationOutcome(
        classification=cls,
        effective_severity=effective,
        escalated=escalated,
        escalation_from=BlockingSeverity.WARNING if escalated else None,
        escalation_to=effective if escalated else None,
        consecutive_warning=1,
        consecutive_critical=1,
        consecutive_freeze=0,
    )


def _window() -> BlockingWindowSnapshot:
    return BlockingWindowSnapshot(
        window_id="r:bw:1",
        runtime_id="r",
        open_sample_index=0,
        close_sample_index=2,
        open_monotonic_ns=0,
        close_monotonic_ns=1_000_000_000,
        peak_lag_ns=50_000_000,
        peak_severity=BlockingSeverity.CRITICAL,
        violation_count=3,
        escalation_count=1,
        closed=True,
    )


def test_event_type_constants() -> None:
    assert BLOCKING_VIOLATION_EVENT_TYPE in BLOCKING_EVENT_TYPES
    assert BLOCKING_ESCALATION_EVENT_TYPE in BLOCKING_EVENT_TYPES
    assert BLOCKING_WINDOW_OPENED_EVENT_TYPE in BLOCKING_EVENT_TYPES
    assert BLOCKING_WINDOW_CLOSED_EVENT_TYPE in BLOCKING_EVENT_TYPES
    assert len(BLOCKING_EVENT_TYPES) == 4


def test_violation_event_payload_has_classification_and_outcome() -> None:
    cls = _classify()
    out = _outcome()
    win = _window()
    e = build_blocking_violation_event(classification=cls, outcome=out, active_window=win)
    assert e.event_type == BLOCKING_VIOLATION_EVENT_TYPE
    p = e.payload
    assert p["classification"]["severity"] == "CRITICAL"
    assert p["effective_severity"] == "CRITICAL"
    assert p["active_window"]["window_id"] == "r:bw:1"


def test_violation_event_handles_missing_window() -> None:
    e = build_blocking_violation_event(
        classification=_classify(),
        outcome=_outcome(),
        active_window=None,
    )
    assert e.payload["active_window"] is None


def test_escalation_event_payload_carries_severities() -> None:
    out = _outcome(escalated=True, effective=BlockingSeverity.CRITICAL)
    e = build_blocking_escalation_event(outcome=out, active_window=None)
    assert e.event_type == BLOCKING_ESCALATION_EVENT_TYPE
    p = e.payload
    assert p["from_severity"] == "WARNING"
    assert p["to_severity"] == "CRITICAL"


def test_window_opened_event_has_trigger_and_window() -> None:
    e = build_blocking_window_opened_event(window=_window(), classification=_classify())
    assert e.event_type == BLOCKING_WINDOW_OPENED_EVENT_TYPE
    assert "window" in e.payload
    assert "trigger_classification" in e.payload


def test_window_closed_event_has_window_only() -> None:
    e = build_blocking_window_closed_event(window=_window())
    assert e.event_type == BLOCKING_WINDOW_CLOSED_EVENT_TYPE
    assert e.payload["window"]["closed"] is True


def test_runtime_id_override_propagates() -> None:
    rid = uuid.uuid4()
    e = build_blocking_violation_event(
        classification=_classify(),
        outcome=_outcome(),
        active_window=None,
        runtime_id=rid,
    )
    assert e.runtime_id == rid
