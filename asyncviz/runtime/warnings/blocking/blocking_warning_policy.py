"""Policy — should this detection outcome surface as a blocking warning?

The emitter delegates one decision per outcome to the policy:

* gate by minimum severity.
* require a freeze window or honour the ``include_no_window`` flag.
* require escalation when the configured mode demands it.

The policy is stateless — it's a pure function of the outcome + the
configured knobs. Replay-deterministic by construction.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.runtime.monitoring.blocking import BlockingSeverity, DetectionOutcome


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    accept: bool
    reason: str


class BlockingWarningPolicy:
    """Outcome → accept/reject filter.

    Defaults: open a group on any CRITICAL+ violation; refresh on every
    follow-up violation in the same window. WARNINGs are ignored
    unless explicitly opted in.
    """

    __slots__ = (
        "_escalations_only",
        "_include_no_window",
        "_min_severity",
    )

    def __init__(
        self,
        *,
        min_severity: BlockingSeverity = BlockingSeverity.CRITICAL,
        include_no_window: bool = False,
        escalations_only: bool = False,
    ) -> None:
        self._min_severity = min_severity
        self._include_no_window = include_no_window
        self._escalations_only = escalations_only

    @property
    def min_severity(self) -> BlockingSeverity:
        return self._min_severity

    @property
    def include_no_window(self) -> bool:
        return self._include_no_window

    @property
    def escalations_only(self) -> bool:
        return self._escalations_only

    def evaluate(self, outcome: DetectionOutcome) -> PolicyDecision:
        if outcome.effective_severity is BlockingSeverity.NONE:
            return PolicyDecision(accept=False, reason="severity_none")
        if outcome.effective_severity < self._min_severity:
            return PolicyDecision(accept=False, reason="below_min_severity")
        # Window gating. The emitter still tracks the outcome under
        # an "_no_window_" bucket when ``include_no_window`` is true so
        # operator-relevant freezes outside the detector's freeze
        # windows still surface.
        active_window = outcome.window_transition.active or outcome.window_transition.opened
        if active_window is None and not self._include_no_window:
            return PolicyDecision(accept=False, reason="no_window")
        if self._escalations_only and not outcome.escalated:
            # Still allow opens — without that, no group ever forms.
            # An open is signaled by the *first* outcome for a window;
            # we don't have group state here, so we delegate that
            # decision back to the emitter (it knows if the group is
            # new). In escalations_only mode we accept escalations
            # unconditionally and let the emitter accept opens
            # explicitly.
            return PolicyDecision(accept=False, reason="escalations_only_non_escalation")
        return PolicyDecision(accept=True, reason="accepted")

    def to_dict(self) -> dict[str, object]:
        return {
            "min_severity": self._min_severity.name,
            "include_no_window": self._include_no_window,
            "escalations_only": self._escalations_only,
        }
