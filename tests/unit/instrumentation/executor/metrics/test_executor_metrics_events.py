"""Round-trip + registry-wiring tests for executor-metrics events."""

from __future__ import annotations

import pytest

from asyncviz.runtime.events.models import (
    EVENT_REGISTRY,
    EXECUTOR_METRICS_EVENT_TYPES,
    EventType,
    from_dict,
    to_dict,
)
from asyncviz.runtime.events.models.executor_metrics import (
    ExecutorContentionDetectedEvent,
    ExecutorLatencySpikeDetectedEvent,
    ExecutorMetricsUpdatedEvent,
    ExecutorSaturationChangedEvent,
)

_BASE = {
    "executor_id": "e-1",
    "executor_kind": "Thread",
    "max_workers": 4,
    "sequence": 7,
    "snapshot": {"executor_id": "e-1", "active_workers": 2},
}


@pytest.mark.parametrize(
    ("cls", "extra"),
    [
        (
            ExecutorMetricsUpdatedEvent,
            {
                "active_workers": 2,
                "peak_active_workers": 3,
                "utilization_ratio": 0.5,
                "submissions": 10,
                "completions": 8,
                "failures": 1,
                "cancellations": 1,
                "submission_rate": 5.0,
                "completion_rate": 4.0,
                "backlog": 0,
                "mean_submission_latency_seconds": 0.01,
                "p95_submission_latency_seconds": 0.05,
                "mean_execution_duration_seconds": 0.1,
                "p95_execution_duration_seconds": 0.3,
                "saturation_score": 0.42,
                "saturation_level": "warning",
            },
        ),
        (
            ExecutorSaturationChangedEvent,
            {
                "previous_level": "calm",
                "new_level": "warning",
                "saturation_score": 0.72,
                "utilization_ratio": 0.8,
                "backlog": 4,
            },
        ),
        (
            ExecutorContentionDetectedEvent,
            {
                "active_workers": 4,
                "utilization_ratio": 1.0,
            },
        ),
        (
            ExecutorLatencySpikeDetectedEvent,
            {
                "submission_latency_seconds": 0.5,
                "threshold_seconds": 0.25,
                "active_workers": 2,
            },
        ),
    ],
)
def test_executor_metrics_events_round_trip(cls, extra) -> None:  # type: ignore[no-untyped-def]
    event = cls(**_BASE, **extra)
    payload = to_dict(event)
    restored = from_dict(payload)
    assert type(restored) is cls
    assert restored.model_dump() == event.model_dump()


def test_event_types_match_enum() -> None:
    expected = {
        EventType.EXECUTOR_METRICS_UPDATED.value,
        EventType.EXECUTOR_SATURATION_CHANGED.value,
        EventType.EXECUTOR_CONTENTION_DETECTED.value,
        EventType.EXECUTOR_LATENCY_SPIKE_DETECTED.value,
    }
    assert set(EXECUTOR_METRICS_EVENT_TYPES) == expected


def test_event_registry_contains_every_metrics_event() -> None:
    for type_name in EXECUTOR_METRICS_EVENT_TYPES:
        assert type_name in EVENT_REGISTRY, f"missing event registry entry for {type_name}"
