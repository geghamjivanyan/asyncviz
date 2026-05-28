from __future__ import annotations

import uuid

from asyncviz.runtime.monitoring.event_loop.lag_events import (
    LAG_MEASUREMENT_EVENT_TYPE,
    LAG_THRESHOLD_BREACH_EVENT_TYPE,
    build_lag_measurement_event,
    build_lag_threshold_breach_event,
    severity_to_warning_severity,
)
from asyncviz.runtime.monitoring.event_loop.lag_measurement import calculate_lag
from asyncviz.runtime.monitoring.event_loop.lag_thresholds import (
    LagSeverity,
    LagThresholdEvaluation,
)


def _measurement():
    return calculate_lag(
        scheduled_ns=0,
        actual_ns=50_000_000,
        interval_ns=10_000_000,
        sample_index=7,
        runtime_id="r",
    )


def test_measurement_event_carries_payload() -> None:
    e = build_lag_measurement_event(_measurement())
    assert e.event_type == LAG_MEASUREMENT_EVENT_TYPE
    assert "measurement" in e.payload
    assert e.payload["measurement"]["lag_ns"] == 50_000_000


def test_threshold_event_carries_severity_and_threshold() -> None:
    m = _measurement()
    e = build_lag_threshold_breach_event(
        m,
        LagThresholdEvaluation(
            severity=LagSeverity.CRITICAL,
            breached=True,
            lag_ns=50_000_000,
            threshold_ns=25_000_000,
        ),
    )
    assert e.event_type == LAG_THRESHOLD_BREACH_EVENT_TYPE
    p = e.payload
    assert p["severity"] == "CRITICAL"
    assert p["severity_value"] == int(LagSeverity.CRITICAL)
    assert p["threshold_ns"] == 25_000_000
    assert p["lag_ns"] == 50_000_000
    assert p["breached"] is True


def test_runtime_id_overrides_default() -> None:
    rid = uuid.uuid4()
    e = build_lag_measurement_event(_measurement(), runtime_id=rid)
    assert e.runtime_id == rid


def test_severity_to_warning_severity_mapping() -> None:
    assert severity_to_warning_severity(LagSeverity.NORMAL) == "info"
    assert severity_to_warning_severity(LagSeverity.WARNING) == "warning"
    assert severity_to_warning_severity(LagSeverity.CRITICAL) == "error"
    assert severity_to_warning_severity(LagSeverity.FREEZE) == "critical"
