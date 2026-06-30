"""Core sampler tests."""

from __future__ import annotations

import pytest

from asyncviz.runtime.sampling import (
    EventSampler,
    SamplingConfig,
    SamplingPriority,
    default_config,
)


def test_off_mode_retains_everything(off_sampler: EventSampler) -> None:
    for _ in range(100):
        assert off_sampler.should_retain("asyncio.queue.metrics.updated")


def test_critical_events_always_retained(
    aggressive_sampler: EventSampler,
) -> None:
    assert all(aggressive_sampler.should_retain("runtime.warning") for _ in range(200))


def test_structural_events_always_retained_by_default(
    aggressive_sampler: EventSampler,
) -> None:
    assert all(aggressive_sampler.should_retain("asyncio.task.created") for _ in range(200))


def test_state_events_sampled_proportionally(custom_sampler: EventSampler) -> None:
    # state_retention = 0.5, expect ~50% retention.
    retained = sum(1 for _ in range(1000) if custom_sampler.should_retain("asyncio.task.waiting"))
    assert 400 < retained < 600


def test_delta_events_aggressively_sampled(custom_sampler: EventSampler) -> None:
    # delta_retention = 0.1, expect ~10% retention.
    retained = sum(
        1 for _ in range(1000) if custom_sampler.should_retain("asyncio.queue.metrics.updated")
    )
    assert 60 < retained < 140


def test_deterministic_decisions() -> None:
    sampler_a = EventSampler(default_config())
    sampler_b = EventSampler(default_config())
    decisions_a = [sampler_a.evaluate("asyncio.queue.metrics.updated") for _ in range(100)]
    decisions_b = [sampler_b.evaluate("asyncio.queue.metrics.updated") for _ in range(100)]
    # Same seed + same sequence stream → same buckets + same retain bits.
    for a, b in zip(decisions_a, decisions_b, strict=True):
        assert a.bucket == b.bucket
        assert a.retain == b.retain


def test_decision_carries_priority_and_reason(
    aggressive_sampler: EventSampler,
) -> None:
    decision = aggressive_sampler.evaluate("runtime.warning")
    assert decision.priority == SamplingPriority.CRITICAL
    assert decision.reason == "critical-priority"


def test_never_drop_allowlist_honored() -> None:
    config = SamplingConfig(
        state_retention=0.0,
        delta_retention=0.0,
        never_drop_event_types=("custom.protected.event",),
    )
    sampler = EventSampler(config)
    assert sampler.should_retain("custom.protected.event")
    decision = sampler.evaluate("custom.protected.event")
    assert decision.reason == "never-drop-event-type"


def test_reset_clears_sequence_counter() -> None:
    sampler = EventSampler(default_config())
    d1 = sampler.evaluate("asyncio.task.created")
    assert d1.sequence == 1
    sampler.reset()
    d2 = sampler.evaluate("asyncio.task.created")
    assert d2.sequence == 1


def test_invalid_config_rejected() -> None:
    with pytest.raises(ValueError):
        SamplingConfig(state_retention=2.0)
    with pytest.raises(ValueError):
        SamplingConfig(budget_window_ns=1)
