"""Builders for synthetic detection outcomes + captures.

Used by emitter tests + replay tools to drive the engine without
needing a live blocking detector / stack capture engine.
"""

from __future__ import annotations

from asyncviz.runtime.monitoring.blocking import (
    BlockingClassifier,
    BlockingSeverity,
    BlockingWindowSnapshot,
    CapturedFrame,
    CapturedStack,
    CapturedTaskMetadata,
    DetectionOutcome,
)
from asyncviz.runtime.monitoring.blocking.blocking_cooldown import CooldownDecision
from asyncviz.runtime.monitoring.blocking.blocking_escalation import EscalationOutcome
from asyncviz.runtime.monitoring.blocking.blocking_windows import WindowTransition
from asyncviz.runtime.monitoring.event_loop.lag_measurement import calculate_lag
from asyncviz.runtime.monitoring.event_loop.lag_thresholds import (
    LagSeverity,
    LagThresholdEvaluation,
)

_BLOCKING_TO_LAG = {
    BlockingSeverity.NONE: LagSeverity.NORMAL,
    BlockingSeverity.WARNING: LagSeverity.WARNING,
    BlockingSeverity.CRITICAL: LagSeverity.CRITICAL,
    BlockingSeverity.FREEZE: LagSeverity.FREEZE,
}


def build_synthetic_window(
    *,
    window_id: str = "r:bw:1",
    peak_severity: BlockingSeverity = BlockingSeverity.CRITICAL,
    open_ns: int = 0,
    peak_lag_ns: int = 50_000_000,
    violation_count: int = 1,
) -> BlockingWindowSnapshot:
    return BlockingWindowSnapshot(
        window_id=window_id,
        runtime_id="r",
        open_sample_index=0,
        close_sample_index=None,
        open_monotonic_ns=open_ns,
        close_monotonic_ns=None,
        peak_lag_ns=peak_lag_ns,
        peak_severity=peak_severity,
        violation_count=violation_count,
        escalation_count=0,
        closed=False,
    )


def build_synthetic_outcome(
    *,
    severity: BlockingSeverity,
    lag_ns: int = 50_000_000,
    threshold_ns: int = 10_000_000,
    index: int = 0,
    scheduled_ns: int = 0,
    escalated: bool = False,
    escalation_from: BlockingSeverity | None = None,
    escalation_to: BlockingSeverity | None = None,
    window: BlockingWindowSnapshot | None = None,
    closed_window: BlockingWindowSnapshot | None = None,
) -> DetectionOutcome:
    """Build a fully-populated :class:`DetectionOutcome` for tests."""
    m = calculate_lag(
        scheduled_ns=scheduled_ns,
        actual_ns=scheduled_ns + lag_ns,
        interval_ns=1_000_000,
        sample_index=index,
        runtime_id="r",
    )
    eval_ = LagThresholdEvaluation(
        severity=_BLOCKING_TO_LAG[severity],
        breached=severity is not BlockingSeverity.NONE,
        lag_ns=lag_ns,
        threshold_ns=threshold_ns,
    )
    classification = BlockingClassifier().classify(m, eval_)
    outcome = EscalationOutcome(
        classification=classification,
        effective_severity=severity,
        escalated=escalated,
        escalation_from=escalation_from,
        escalation_to=escalation_to,
        consecutive_warning=0,
        consecutive_critical=0,
        consecutive_freeze=0,
    )
    transition = WindowTransition(
        opened=window,
        extended=None,
        closed=closed_window,
        active=window if closed_window is None else None,
    )
    cooldown = CooldownDecision(
        severity=severity,
        suppressed=False,
        remaining_ns=0,
    )
    return DetectionOutcome(
        classification=classification,
        outcome=outcome,
        is_violation=severity is not BlockingSeverity.NONE,
        cooldown=cooldown,
        window_transition=transition,
        violation_emitted=True,
    )


def build_synthetic_capture(
    *,
    capture_id: int = 1,
    window_id: str | None = "r:bw:1",
    severity: str = "CRITICAL",
    trigger: str = "first_in_window",
    sample_index: int = 0,
    monotonic_ns: int = 100,
    task_id: str | None = "t1",
    task_name: str | None = "my-task",
    coroutine_name: str | None = "myapp.do_work",
    function: str = "handler",
) -> CapturedStack:
    frame = CapturedFrame(
        filename="/tmp/x.py",
        module="myapp",
        function=function,
        lineno=1,
        code_context=None,
        is_async=False,
        is_internal=False,
    )
    return CapturedStack(
        capture_id=capture_id,
        runtime_id="r",
        monotonic_ns=monotonic_ns,
        sample_index=sample_index,
        window_id=window_id,
        severity=severity,
        trigger=trigger,
        frames=(frame,),
        frames_total=1,
        filtered_count=0,
        thread_id=1,
        task=CapturedTaskMetadata(
            task_id=task_id,
            task_name=task_name,
            coroutine_name=coroutine_name,
        ),
    )
