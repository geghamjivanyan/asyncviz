"""Replay bookkeeper + websocket + topology tests."""

from __future__ import annotations

import pytest

from asyncviz.runtime.sampling import (
    SAMPLING_MARKER_EVENT_TYPE,
    EventSampler,
    ReplaySamplingBookkeeper,
    SamplingDecision,
    SamplingPriority,
    WebsocketSamplingController,
    default_config,
    force_retain_structural,
    marker_to_event_dict,
)


def _decision(seq: int, retain: bool, priority: SamplingPriority) -> SamplingDecision:
    return SamplingDecision(
        retain=retain,
        priority=priority,
        reason="retained-by-rate" if retain else "dropped-by-rate",
        sequence=seq,
        bucket=seq % 1024,
    )


def test_replay_bookkeeper_emits_marker_per_window() -> None:
    keeper = ReplaySamplingBookkeeper(window_size=4)
    markers = []
    for i in range(1, 9):
        m = keeper.observe(_decision(i, retain=i % 2 == 0, priority=SamplingPriority.DELTA))
        if m is not None:
            markers.append(m)
    assert len(markers) == 2
    assert all(marker.retained + marker.dropped == 4 for marker in markers)


def test_replay_bookkeeper_flush_emits_partial_window() -> None:
    keeper = ReplaySamplingBookkeeper(window_size=10)
    keeper.observe(_decision(1, retain=True, priority=SamplingPriority.STATE))
    keeper.observe(_decision(2, retain=False, priority=SamplingPriority.DELTA))
    marker = keeper.flush()
    assert marker is not None
    assert marker.retained == 1
    assert marker.dropped == 1


def test_marker_to_event_dict_carries_metadata() -> None:
    keeper = ReplaySamplingBookkeeper(window_size=2)
    keeper.observe(_decision(1, retain=False, priority=SamplingPriority.DELTA))
    # Second observation closes the window + returns the marker.
    marker = keeper.observe(_decision(2, retain=False, priority=SamplingPriority.DELTA))
    assert marker is not None
    event = marker_to_event_dict(marker, sequence=100, monotonic_ns=1_000)
    assert event["event_type"] == SAMPLING_MARKER_EVENT_TYPE
    assert event["sequence"] == 100
    assert event["payload"]["dropped"] == 2


def test_websocket_controller_engages_on_high_watermark() -> None:
    sampler = EventSampler(default_config())
    ctrl = WebsocketSamplingController(
        sampler=sampler,
        queue_high_watermark=100,
        queue_low_watermark=10,
    )
    ctrl.observe_queue_depth(50)
    assert not ctrl.engaged
    ctrl.observe_queue_depth(150)
    assert ctrl.engaged


def test_websocket_controller_releases_on_low_watermark() -> None:
    sampler = EventSampler(default_config())
    ctrl = WebsocketSamplingController(
        sampler=sampler,
        queue_high_watermark=100,
        queue_low_watermark=10,
    )
    ctrl.observe_queue_depth(200)
    assert ctrl.engaged
    ctrl.observe_queue_depth(5)
    assert not ctrl.engaged


def test_websocket_controller_validates_watermarks() -> None:
    sampler = EventSampler(default_config())
    with pytest.raises(ValueError):
        WebsocketSamplingController(
            sampler=sampler,
            queue_high_watermark=10,
            queue_low_watermark=100,
        )


def test_force_retain_structural_returns_priority_for_structural_events() -> None:
    assert force_retain_structural("asyncio.task.created") == SamplingPriority.STRUCTURAL
    assert force_retain_structural("asyncio.queue.metrics.updated") is None
