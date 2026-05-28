"""Shared fixtures for stack-capture tests."""

from __future__ import annotations

from asyncviz.runtime.monitoring.blocking.blocking_classifier import (
    BlockingClassifier,
    BlockingSeverity,
)
from asyncviz.runtime.monitoring.blocking.blocking_detector import DetectionOutcome
from asyncviz.runtime.monitoring.blocking.blocking_escalation import EscalationOutcome
from asyncviz.runtime.monitoring.blocking.blocking_windows import (
    BlockingWindowSnapshot,
    WindowTransition,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_sampler import (
    RawFrame,
    StaticFrameProvider,
)
from asyncviz.runtime.monitoring.event_loop.lag_measurement import calculate_lag
from asyncviz.runtime.monitoring.event_loop.lag_thresholds import (
    LagSeverity,
    LagThresholdEvaluation,
)


def measurement(lag_ns: int, *, index: int = 0, scheduled_ns: int = 0):
    return calculate_lag(
        scheduled_ns=scheduled_ns,
        actual_ns=scheduled_ns + lag_ns,
        interval_ns=1_000_000,
        sample_index=index,
        runtime_id="r",
    )


def build_outcome(
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
    window_opened: BlockingWindowSnapshot | None = None,
) -> DetectionOutcome:
    """Build a fully-populated :class:`DetectionOutcome` for tests.

    Drives the engine without needing a real lag monitor + detector
    chain. The classification fields are derived from ``severity``;
    callers can override the escalation + window state directly.
    """
    lag_to_lag_sev = {
        BlockingSeverity.NONE: LagSeverity.NORMAL,
        BlockingSeverity.WARNING: LagSeverity.WARNING,
        BlockingSeverity.CRITICAL: LagSeverity.CRITICAL,
        BlockingSeverity.FREEZE: LagSeverity.FREEZE,
    }
    m = measurement(lag_ns, index=index, scheduled_ns=scheduled_ns)
    eval_ = LagThresholdEvaluation(
        severity=lag_to_lag_sev[severity],
        breached=severity is not BlockingSeverity.NONE,
        lag_ns=lag_ns,
        threshold_ns=threshold_ns,
    )
    classifier = BlockingClassifier()
    classification = classifier.classify(m, eval_)
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
        opened=window_opened,
        extended=None,
        closed=None,
        active=window,
    )
    from asyncviz.runtime.monitoring.blocking.blocking_cooldown import CooldownDecision

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


def make_window(window_id: str = "r:bw:1", peak: BlockingSeverity = BlockingSeverity.CRITICAL):
    return BlockingWindowSnapshot(
        window_id=window_id,
        runtime_id="r",
        open_sample_index=0,
        close_sample_index=None,
        open_monotonic_ns=0,
        close_monotonic_ns=None,
        peak_lag_ns=50_000_000,
        peak_severity=peak,
        violation_count=1,
        escalation_count=0,
        closed=False,
    )


def user_frame(
    *,
    function: str = "do_work",
    module: str = "myapp.code",
    filename: str = "/tmp/app.py",
    lineno: int = 42,
    co_flags: int = 0,
) -> RawFrame:
    return RawFrame(
        filename=filename,
        module=module,
        function=function,
        lineno=lineno,
        co_flags=co_flags,
    )


def asyncio_frame() -> RawFrame:
    return RawFrame(
        filename="/usr/lib/python/asyncio/base_events.py",
        module="asyncio.base_events",
        function="_run_once",
        lineno=100,
        co_flags=0,
    )


def static_provider(*frames: RawFrame) -> StaticFrameProvider:
    return StaticFrameProvider(list(frames))
