from __future__ import annotations

from asyncviz.runtime.monitoring.blocking.stack_capture import (
    CapturedFrame,
    CapturedStack,
    StackCaptureMetrics,
    StackCaptureStatistics,
)


def _stack(*, capture_id: int, severity: str, trigger: str, window_id: str | None = None):
    return CapturedStack(
        capture_id=capture_id,
        runtime_id="r",
        monotonic_ns=10,
        sample_index=0,
        window_id=window_id,
        severity=severity,
        trigger=trigger,
        frames=(
            CapturedFrame(
                filename="/tmp/x.py",
                module="myapp",
                function="handler",
                lineno=1,
                code_context=None,
                is_async=False,
                is_internal=False,
            ),
        ),
        frames_total=1,
        filtered_count=0,
        thread_id=1,
    )


# ── metrics ──────────────────────────────────────────────────────────────


def test_metrics_start_at_zero() -> None:
    snap = StackCaptureMetrics().snapshot()
    assert snap.captures_attempted == 0
    assert snap.captures_emitted == 0


def test_metrics_count_emissions_with_payload_aggregation() -> None:
    m = StackCaptureMetrics()
    m.record_capture_emitted(payload_bytes=100, frame_count=3, filtered_count=1, trimmed=False)
    m.record_capture_emitted(payload_bytes=200, frame_count=2, filtered_count=0, trimmed=True)
    snap = m.snapshot()
    assert snap.captures_emitted == 2
    assert snap.total_payload_bytes == 300
    assert snap.max_payload_bytes_observed == 200
    assert snap.total_frames_emitted == 5
    assert snap.total_frames_filtered == 1
    assert snap.payload_trims == 1


def test_metrics_skip_counters_partition_by_reason() -> None:
    m = StackCaptureMetrics()
    m.record_capture_skipped_policy()
    m.record_capture_skipped_reentry()
    snap = m.snapshot()
    assert snap.captures_skipped_policy == 1
    assert snap.captures_skipped_reentry == 1


def test_metrics_record_handler_failure() -> None:
    m = StackCaptureMetrics()
    m.record_handler_failure()
    assert m.snapshot().handler_failures == 1


# ── statistics ───────────────────────────────────────────────────────────


def test_statistics_track_captures_by_severity_and_trigger() -> None:
    s = StackCaptureStatistics()
    s.observe(_stack(capture_id=1, severity="CRITICAL", trigger="violation"))
    s.observe(_stack(capture_id=2, severity="CRITICAL", trigger="escalation"))
    s.observe(_stack(capture_id=3, severity="FREEZE", trigger="freeze"))
    snap = s.snapshot()
    assert snap.captures_total == 3
    assert snap.captures_by_severity["CRITICAL"] == 2
    assert snap.captures_by_severity["FREEZE"] == 1
    assert snap.captures_by_trigger["violation"] == 1
    assert snap.captures_by_trigger["escalation"] == 1


def test_statistics_track_per_window_counts() -> None:
    s = StackCaptureStatistics()
    s.observe(_stack(capture_id=1, severity="CRITICAL", trigger="x", window_id="w1"))
    s.observe(_stack(capture_id=2, severity="CRITICAL", trigger="x", window_id="w1"))
    s.observe(_stack(capture_id=3, severity="CRITICAL", trigger="x", window_id="w2"))
    snap = s.snapshot()
    assert snap.captures_per_window == {"w1": 2, "w2": 1}


def test_statistics_top_frames_ranks_by_count() -> None:
    s = StackCaptureStatistics(top_frame_limit=2)
    for _ in range(3):
        s.observe(_stack(capture_id=1, severity="CRITICAL", trigger="x"))
    snap = s.snapshot()
    assert snap.top_top_frames[0].function == "handler"
    assert snap.top_top_frames[0].count == 3


def test_statistics_recent_ring_evicts_oldest() -> None:
    s = StackCaptureStatistics(recent_capacity=2)
    s.observe(_stack(capture_id=1, severity="CRITICAL", trigger="x"))
    s.observe(_stack(capture_id=2, severity="CRITICAL", trigger="x"))
    s.observe(_stack(capture_id=3, severity="CRITICAL", trigger="x"))
    recent = s.recent()
    assert [c.capture_id for c in recent] == [2, 3]


def test_statistics_reset_clears_everything() -> None:
    s = StackCaptureStatistics()
    s.observe(_stack(capture_id=1, severity="CRITICAL", trigger="x"))
    s.reset()
    snap = s.snapshot()
    assert snap.captures_total == 0
    assert snap.captures_by_severity == {}
