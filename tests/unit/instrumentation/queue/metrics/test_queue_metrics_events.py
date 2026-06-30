"""Round-trip + registry-wiring tests for the queue-metrics event models."""

from __future__ import annotations

import pytest

from asyncviz.runtime.events.models import (
    EVENT_REGISTRY,
    QUEUE_METRICS_EVENT_TYPES,
    EventType,
    from_dict,
    to_dict,
)
from asyncviz.runtime.events.models.queue_metrics import (
    QueueContentionDetectedEvent,
    QueueMetricsUpdatedEvent,
    QueuePressureChangedEvent,
    QueueSaturationDetectedEvent,
)

_BASE_SNAPSHOT = {
    "queue_id": "q-1",
    "queue_kind": "Queue",
    "maxsize": 4,
    "sequence": 7,
    "snapshot": {"current_size": 3, "maxsize": 4},
}


@pytest.mark.parametrize(
    ("cls", "extra"),
    [
        (
            QueueMetricsUpdatedEvent,
            {
                "current_size": 3,
                "peak_size": 4,
                "occupancy_ratio": 0.75,
                "put_rate": 12.5,
                "get_rate": 8.1,
                "put_count": 100,
                "get_count": 87,
                "producer_consumer_delta": 13,
                "pressure_score": 0.6,
                "pressure_level": "warning",
            },
        ),
        (
            QueuePressureChangedEvent,
            {
                "previous_level": "calm",
                "new_level": "warning",
                "pressure_score": 0.62,
                "occupancy_ratio": 0.7,
                "blocked_producers": 2,
                "blocked_consumers": 0,
            },
        ),
        (
            QueueContentionDetectedEvent,
            {
                "blocked_producers": 4,
                "blocked_consumers": 0,
                "blocked_put_total": 12,
                "blocked_get_total": 0,
                "contention_kind": "producers",
            },
        ),
        (
            QueueSaturationDetectedEvent,
            {"occupancy_ratio": 0.95, "current_size": 19, "threshold": 0.9},
        ),
    ],
)
def test_queue_metrics_events_round_trip(cls, extra) -> None:  # type: ignore[no-untyped-def]
    event = cls(**_BASE_SNAPSHOT, **extra)
    payload = to_dict(event)
    restored = from_dict(payload)
    assert type(restored) is cls
    assert restored.model_dump() == event.model_dump()


def test_queue_metrics_event_types_match_event_type_enum() -> None:
    expected = {
        EventType.QUEUE_METRICS_UPDATED.value,
        EventType.QUEUE_PRESSURE_CHANGED.value,
        EventType.QUEUE_CONTENTION_DETECTED.value,
        EventType.QUEUE_SATURATION_DETECTED.value,
    }
    assert set(QUEUE_METRICS_EVENT_TYPES) == expected


def test_event_registry_contains_every_metrics_event() -> None:
    for type_name in QUEUE_METRICS_EVENT_TYPES:
        assert type_name in EVENT_REGISTRY, f"missing event registry entry for {type_name}"
