"""Capture policy — should this detection outcome produce a stack capture?

Decoupled from the engine so:

* tests can drive policy decisions without spinning the engine.
* future adaptive policies (e.g. "capture every Nth violation",
  "always capture the first frame of a window then sample") slot in by
  swapping the policy instance.

All decisions are pure functions of the detection outcome + a small
amount of internal counters (e.g. captures-per-window). Decisions are
replay-deterministic when the input outcome sequence is.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from asyncviz.runtime.monitoring.blocking.blocking_classifier import BlockingSeverity
from asyncviz.runtime.monitoring.blocking.blocking_detector import DetectionOutcome


@dataclass(frozen=True, slots=True)
class CaptureDecision:
    """Outcome of one policy check.

    * ``capture``     — caller should walk the stack.
    * ``trigger``     — short string label for the event payload
      (``"violation_open"``, ``"escalation"``, ``"freeze_extend"``,
      ``"first_in_window"``, etc.). Carried into the captured stack so
      the UI can group captures by reason.
    * ``reason``      — human-friendly note for diagnostics tracing.
    """

    capture: bool
    trigger: str
    reason: str


class StackCapturePolicy:
    """Severity + window-aware capture policy.

    Captures fire on:

    * the *first* violation of a window (highest signal).
    * any escalation transition.
    * additional samples within a window — up to ``max_captures_per_window``.
    * any violation at severity >= ``always_capture_severity``
      (escapes the per-window cap so freezes always paged).

    Counters reset when a new window opens (matched by ``window_id``).
    Captures fired outside a window obey the captures-per-window cap
    keyed off a synthetic "no_window" bucket.
    """

    __slots__ = (
        "_always_capture_severity",
        "_capture_outside_windows",
        "_capture_warning",
        "_captures_by_window",
        "_lock",
        "_max_captures_per_window",
        "_min_severity",
    )

    def __init__(
        self,
        *,
        min_severity: BlockingSeverity = BlockingSeverity.CRITICAL,
        always_capture_severity: BlockingSeverity = BlockingSeverity.FREEZE,
        max_captures_per_window: int = 3,
        capture_outside_windows: bool = True,
        capture_warning: bool = False,
    ) -> None:
        if max_captures_per_window < 1:
            raise ValueError(
                f"max_captures_per_window must be >= 1 (got {max_captures_per_window})"
            )
        self._min_severity = min_severity
        self._always_capture_severity = always_capture_severity
        self._max_captures_per_window = max_captures_per_window
        self._capture_outside_windows = capture_outside_windows
        self._capture_warning = capture_warning
        self._lock = threading.Lock()
        self._captures_by_window: dict[str, int] = {}

    @property
    def min_severity(self) -> BlockingSeverity:
        return self._min_severity

    @property
    def always_capture_severity(self) -> BlockingSeverity:
        return self._always_capture_severity

    @property
    def max_captures_per_window(self) -> int:
        return self._max_captures_per_window

    def reset(self) -> None:
        with self._lock:
            self._captures_by_window.clear()

    def to_dict(self) -> dict[str, object]:
        return {
            "min_severity": self._min_severity.name,
            "always_capture_severity": self._always_capture_severity.name,
            "max_captures_per_window": self._max_captures_per_window,
            "capture_outside_windows": self._capture_outside_windows,
            "capture_warning": self._capture_warning,
        }

    def decide(self, outcome: DetectionOutcome) -> CaptureDecision:
        """Decide whether ``outcome`` should produce a stack capture."""
        severity = outcome.effective_severity
        if severity is BlockingSeverity.NONE:
            return CaptureDecision(capture=False, trigger="", reason="severity_none")
        # Quick out: below configured minimum severity. The
        # ``capture_warning`` opt-in still requires a WARNING-or-higher
        # severity, so the predicate folds both checks.
        below_min = severity < self._min_severity
        warning_opt_in = self._capture_warning and severity >= BlockingSeverity.WARNING
        if below_min and not warning_opt_in:
            return CaptureDecision(capture=False, trigger="", reason="below_min_severity")

        # Always-capture severity bypasses the per-window cap.
        if severity >= self._always_capture_severity:
            self._tick_window(outcome)
            return CaptureDecision(
                capture=True,
                trigger="freeze" if severity is BlockingSeverity.FREEZE else "always_severity",
                reason="always_capture_severity_met",
            )

        # Escalation transitions always capture (within cap accounting).
        if outcome.escalated:
            self._tick_window(outcome)
            return CaptureDecision(
                capture=True,
                trigger="escalation",
                reason="escalation_transition",
            )

        # Per-window cap. The first capture of a new window is always
        # taken; later captures consume the budget.
        window_id = self._window_key(outcome)
        with self._lock:
            taken = self._captures_by_window.get(window_id, 0)
            if taken == 0:
                self._captures_by_window[window_id] = 1
                trigger = "first_in_window" if outcome.window_transition.opened else "first"
                return CaptureDecision(
                    capture=True,
                    trigger=trigger,
                    reason="first_capture_for_window",
                )
            if taken >= self._max_captures_per_window:
                return CaptureDecision(
                    capture=False,
                    trigger="",
                    reason="window_capture_cap_hit",
                )
            self._captures_by_window[window_id] = taken + 1
            return CaptureDecision(
                capture=True,
                trigger="violation",
                reason="window_cap_available",
            )

    def _tick_window(self, outcome: DetectionOutcome) -> None:
        window_id = self._window_key(outcome)
        with self._lock:
            self._captures_by_window[window_id] = self._captures_by_window.get(window_id, 0) + 1

    def _window_key(self, outcome: DetectionOutcome) -> str:
        active = outcome.window_transition.active or outcome.window_transition.opened
        if active is not None:
            return active.window_id
        if not self._capture_outside_windows:
            return "_disabled_outside_"
        return "_no_window_"
