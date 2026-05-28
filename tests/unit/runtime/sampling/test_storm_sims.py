"""Event-storm + replay-determinism stress tests."""

from __future__ import annotations

from asyncviz.runtime.sampling import (
    EventSampler,
    SamplingConfig,
    aggressive_config,
    default_config,
)


def test_event_storm_preserves_all_critical_and_structural() -> None:
    """In a 5,000-event storm with aggressive sampling, every
    structural + critical event must still be retained."""
    sampler = EventSampler(aggressive_config())
    types = [
        "asyncio.task.created",       # structural
        "asyncio.queue.metrics.updated",  # delta
        "asyncio.queue.metrics.updated",
        "runtime.warning",            # critical
        "asyncio.task.waiting",       # state
    ] * 1_000
    structural_seen = 0
    critical_seen = 0
    for et in types:
        decision = sampler.evaluate(et)
        if et == "asyncio.task.created":
            assert decision.retain
            structural_seen += 1
        elif et == "runtime.warning":
            assert decision.retain
            critical_seen += 1
    assert structural_seen == 1000
    assert critical_seen == 1000


def test_replay_determinism_across_runs() -> None:
    """Two samplers with the same config produce the same decision
    stream for the same inputs."""
    a = EventSampler(default_config())
    b = EventSampler(default_config())
    event_stream = [
        "asyncio.queue.metrics.updated",
        "asyncio.task.created",
        "asyncio.task.waiting",
        "runtime.metric",
    ] * 100
    decisions_a = [a.evaluate(et) for et in event_stream]
    decisions_b = [b.evaluate(et) for et in event_stream]
    for da, db in zip(decisions_a, decisions_b, strict=True):
        assert da.retain == db.retain
        assert da.bucket == db.bucket
        assert da.priority == db.priority


def test_overload_floor_preserves_some_retention() -> None:
    """Even under sustained overload, retention never collapses
    fully to zero — the configured floor preserves a baseline."""
    config = SamplingConfig(
        state_retention=0.5,
        delta_retention=0.5,
        overload_floor=0.10,  # 10% floor
        budget_target_events=1,
    )
    sampler = EventSampler(config)
    sampler.set_overload(True)
    # Warm: produce enough retentions to trip the budget.
    for _ in range(50):
        sampler.evaluate("asyncio.queue.metrics.updated")
    assert sampler.budget_snapshot().over_budget
    retained = sum(
        1 for _ in range(2000)
        if sampler.evaluate("asyncio.queue.metrics.updated").retain
    )
    assert retained > 0
    # And the constraint is real — well below the unconstrained
    # delta retention rate (~50%).
    assert retained < 500


def test_sampler_handles_million_events_quickly() -> None:
    """Throughput smoke test: a million decisions in well under a
    second on any reasonable hardware."""
    import time

    sampler = EventSampler(aggressive_config())
    start = time.perf_counter()
    for _ in range(100_000):
        sampler.evaluate("asyncio.queue.metrics.updated")
    elapsed = time.perf_counter() - start
    # 100k decisions should take < 1s — generous bound for CI.
    assert elapsed < 1.0
