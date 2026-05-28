"""Integrity + diagnostics tests."""

from __future__ import annotations

from asyncviz.runtime.sampling import (
    SamplingDecision,
    SamplingPriority,
    SamplingStatisticsAccumulator,
    build_sampling_diagnostics,
    check_decision,
    clear_sampling_trace,
    get_sampling_trace,
    set_sampling_trace_enabled,
)


def _decision(retain: bool, priority: SamplingPriority, seq: int = 1,
               reason: str = "retained-by-rate") -> SamplingDecision:
    return SamplingDecision(
        retain=retain,
        priority=priority,
        reason=reason if retain else "dropped-by-rate",
        sequence=seq,
        bucket=seq % 1024,
    )


def test_integrity_flags_dropped_critical() -> None:
    bad = _decision(retain=False, priority=SamplingPriority.CRITICAL, seq=1)
    violation = check_decision(bad)
    assert violation is not None
    assert violation.kind == "dropped_critical"


def test_integrity_flags_dropped_structural() -> None:
    bad = _decision(retain=False, priority=SamplingPriority.STRUCTURAL, seq=1)
    violation = check_decision(bad)
    assert violation is not None
    assert violation.kind == "dropped_structural"


def test_integrity_flags_non_monotonic_sequence() -> None:
    d = _decision(retain=True, priority=SamplingPriority.STATE, seq=5)
    violation = check_decision(d, previous_sequence=10)
    assert violation is not None
    assert violation.kind == "non_monotonic_sequence"


def test_integrity_accepts_clean_decision() -> None:
    d = _decision(retain=True, priority=SamplingPriority.STATE, seq=2)
    assert check_decision(d, previous_sequence=1) is None


def test_statistics_accumulator_aggregates_by_priority() -> None:
    accum = SamplingStatisticsAccumulator()
    accum.observe(_decision(retain=True, priority=SamplingPriority.CRITICAL))
    accum.observe(_decision(retain=True, priority=SamplingPriority.STATE))
    accum.observe(_decision(retain=False, priority=SamplingPriority.DELTA))
    snap = accum.snapshot()
    assert snap.total_observed == 3
    assert snap.total_retained == 2
    assert snap.total_dropped == 1
    assert snap.retained_by_priority[SamplingPriority.CRITICAL] == 1
    assert snap.dropped_by_priority[SamplingPriority.DELTA] == 1


def test_diagnostics_returns_combined_view() -> None:
    diag = build_sampling_diagnostics()
    assert diag.metrics is not None
    assert diag.recent_trace == ()


def test_tracing_captures_kind() -> None:
    set_sampling_trace_enabled(True)
    try:
        from asyncviz.runtime.sampling import record_sampling_trace
        record_sampling_trace("event-dropped", "test")
        kinds = {e.kind for e in get_sampling_trace()}
        assert "event-dropped" in kinds
    finally:
        set_sampling_trace_enabled(False)
        clear_sampling_trace()
