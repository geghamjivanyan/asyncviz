"""Detector-side threshold policy.

Re-exports :class:`LagSeverity` indirectly through the classifier and
adds detector-only knobs that don't belong on the lag monitor's
threshold object:

* **min_violation_threshold**          — the minimum severity that even
  counts as a violation. Defaults to ``WARNING`` so NORMAL samples
  flow through without bookkeeping. Set to ``CRITICAL`` to ignore
  micro-warnings; set to ``NONE`` to record every classification.
* **window_open_severity**             — the severity at which a new
  blocking window opens. Defaults to ``WARNING``.
* **window_close_consecutive_normals** — how many consecutive ``NONE``
  classifications close an open window. Avoids closing+re-opening on
  a single transient recovery.
* **escalation_warning_threshold**     — N consecutive WARNINGs that
  upgrade the classification to CRITICAL. Implements monotonic
  pressure: prolonged warning pain → escalated severity even if
  individual measurements don't cross the next threshold.
* **escalation_critical_threshold**    — N consecutive CRITICALs that
  upgrade to FREEZE.

All knobs are integers/enums so the policy stays replay-safe — no
clock-derived defaults.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.runtime.monitoring.blocking.blocking_classifier import BlockingSeverity


@dataclass(frozen=True, slots=True)
class BlockingThresholdPolicy:
    """Detector-only threshold knobs. Separate from :class:`LagThresholds`.

    Frozen so the orchestrator can swap configurations atomically.
    """

    min_violation_severity: BlockingSeverity = BlockingSeverity.WARNING
    window_open_severity: BlockingSeverity = BlockingSeverity.WARNING
    window_close_consecutive_normals: int = 2
    escalation_warning_threshold: int = 5
    escalation_critical_threshold: int = 3

    def __post_init__(self) -> None:
        if self.window_close_consecutive_normals < 1:
            raise ValueError(
                "window_close_consecutive_normals must be >= 1 "
                f"(got {self.window_close_consecutive_normals})"
            )
        if self.escalation_warning_threshold < 1:
            raise ValueError(
                f"escalation_warning_threshold must be >= 1 "
                f"(got {self.escalation_warning_threshold})"
            )
        if self.escalation_critical_threshold < 1:
            raise ValueError(
                f"escalation_critical_threshold must be >= 1 "
                f"(got {self.escalation_critical_threshold})"
            )
        if self.window_open_severity is BlockingSeverity.NONE:
            raise ValueError("window_open_severity must be > NONE")

    def is_violation(self, severity: BlockingSeverity) -> bool:
        return severity >= self.min_violation_severity

    def should_open_window(self, severity: BlockingSeverity) -> bool:
        return severity >= self.window_open_severity

    def to_dict(self) -> dict[str, object]:
        return {
            "min_violation_severity": self.min_violation_severity.name,
            "window_open_severity": self.window_open_severity.name,
            "window_close_consecutive_normals": self.window_close_consecutive_normals,
            "escalation_warning_threshold": self.escalation_warning_threshold,
            "escalation_critical_threshold": self.escalation_critical_threshold,
        }
