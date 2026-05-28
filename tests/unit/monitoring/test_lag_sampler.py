from __future__ import annotations

from asyncviz.runtime.monitoring.event_loop.lag_clock import LagClock
from asyncviz.runtime.monitoring.event_loop.lag_sampler import LagSampler, SampleRequest
from asyncviz.runtime.monitoring.event_loop.utils.fake_clock import FakeMonotonicClock


def test_sampler_reads_clock_exactly_once_per_sample() -> None:
    """The sampler must take its clock reading at sample time, not before."""
    fake = FakeMonotonicClock(initial_ns=1_000)
    sampler = LagSampler(LagClock(fake))

    # Schedule a deadline at 1_500, then advance the clock to 1_800 before
    # sampling — the sample's actual_ns should reflect 1_800, not 1_500.
    fake.set_to(1_800)
    m = sampler.sample(
        SampleRequest(
            sample_index=0,
            scheduled_ns=1_500,
            interval_ns=500,
            runtime_id="r",
        )
    )
    assert m.actual_ns == 1_800
    assert m.lag_ns == 300


def test_sampler_late_wakeup_records_lag() -> None:
    fake = FakeMonotonicClock(initial_ns=0)
    sampler = LagSampler(LagClock(fake))
    fake.set_to(2_500)
    m = sampler.sample(
        SampleRequest(
            sample_index=5,
            scheduled_ns=2_000,
            interval_ns=200,
            runtime_id="r",
        )
    )
    assert m.lag_ns == 500
    assert m.sample_index == 5


def test_sampler_on_time_wakeup_records_zero_lag() -> None:
    fake = FakeMonotonicClock(initial_ns=0)
    sampler = LagSampler(LagClock(fake))
    fake.set_to(2_000)
    m = sampler.sample(
        SampleRequest(
            sample_index=0,
            scheduled_ns=2_000,
            interval_ns=200,
            runtime_id="r",
        )
    )
    assert m.lag_ns == 0


def test_sampler_clock_anomaly_clamps_to_zero() -> None:
    fake = FakeMonotonicClock(initial_ns=0)
    sampler = LagSampler(LagClock(fake))
    fake.set_to(500)
    m = sampler.sample(
        SampleRequest(
            sample_index=0,
            scheduled_ns=1_000,  # scheduled later than current "now"
            interval_ns=200,
            runtime_id="r",
        )
    )
    assert m.lag_ns == 0


def test_sampler_is_deterministic_for_same_inputs() -> None:
    """Pure measurement — equivalent inputs produce equivalent outputs."""
    fake = FakeMonotonicClock(initial_ns=100)
    sampler = LagSampler(LagClock(fake))

    fake.set_to(150)
    a = sampler.sample(
        SampleRequest(sample_index=0, scheduled_ns=120, interval_ns=30, runtime_id="r")
    )

    fake2 = FakeMonotonicClock(initial_ns=150)
    sampler2 = LagSampler(LagClock(fake2))
    b = sampler2.sample(
        SampleRequest(sample_index=0, scheduled_ns=120, interval_ns=30, runtime_id="r")
    )
    assert a == b
