"""Consecutive-violation escalation state machine.

Implements two upgrades:

* ``N`` consecutive WARNINGs → re-classify as CRITICAL.
* ``M`` consecutive CRITICALs (or escalated-WARNINGS) → re-classify as
  FREEZE.

The state machine is purely a function of the classification stream —
no clock reads, no timers. This keeps replay deterministic: feed the
same classifications in the same order, get the same escalations.

Escalations are *re-classifications*, not separate events: the
detector's downstream pipeline (cooldowns, windows, event emission)
operates on the escalated severity so a single notification reflects
the true pressure level. Tracking transitions independently lets us
emit dedicated escalation events (see :mod:`blocking_events`) without
polluting the violation stream.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from asyncviz.runtime.monitoring.blocking.blocking_classifier import (
    BlockingClassification,
    BlockingSeverity,
)
from asyncviz.runtime.monitoring.blocking.blocking_thresholds import BlockingThresholdPolicy


@dataclass(frozen=True, slots=True)
class EscalationOutcome:
    """The escalation stage's verdict on one classification.

    * ``effective_severity`` — the (possibly upgraded) severity the rest
      of the pipeline should use.
    * ``escalated`` — true when ``effective_severity > source_severity``.
    * ``escalation_from`` / ``escalation_to`` — set only when ``escalated``.
    * ``consecutive_*`` — the post-update counters.
    """

    classification: BlockingClassification
    effective_severity: BlockingSeverity
    escalated: bool
    escalation_from: BlockingSeverity | None
    escalation_to: BlockingSeverity | None
    consecutive_warning: int
    consecutive_critical: int
    consecutive_freeze: int


class EscalationEngine:
    """Stateful counter; thread-safe.

    Single lock guards all counters because the detector pipeline runs
    on the asyncio loop today and any cross-thread contention is rare.
    The hot path is one comparison + one increment per measurement.
    """

    __slots__ = (
        "_consecutive_critical",
        "_consecutive_freeze",
        "_consecutive_warning",
        "_lock",
        "_policy",
    )

    def __init__(self, policy: BlockingThresholdPolicy) -> None:
        self._policy = policy
        self._lock = threading.Lock()
        self._consecutive_warning = 0
        self._consecutive_critical = 0
        self._consecutive_freeze = 0

    @property
    def policy(self) -> BlockingThresholdPolicy:
        return self._policy

    def configure(self, policy: BlockingThresholdPolicy) -> None:
        """Swap the policy. Counters are preserved across reconfigure."""
        with self._lock:
            self._policy = policy

    def reset(self) -> None:
        with self._lock:
            self._consecutive_warning = 0
            self._consecutive_critical = 0
            self._consecutive_freeze = 0

    def consecutive_counts(self) -> tuple[int, int, int]:
        with self._lock:
            return (
                self._consecutive_warning,
                self._consecutive_critical,
                self._consecutive_freeze,
            )

    def process(self, classification: BlockingClassification) -> EscalationOutcome:
        """Update counters and decide the effective severity.

        Updates are atomic-ish under the single lock. The returned
        outcome carries the post-update counters so downstream stages
        don't need to re-read the engine.
        """
        with self._lock:
            source = classification.severity
            policy = self._policy

            # 1. Update raw counters from the *source* severity. This
            #    keeps the escalation logic decoupled from itself —
            #    escalating to CRITICAL doesn't bump the WARNING
            #    counter again.
            if source >= BlockingSeverity.WARNING:
                self._consecutive_warning += 1
            else:
                self._consecutive_warning = 0
            if source >= BlockingSeverity.CRITICAL:
                self._consecutive_critical += 1
            else:
                self._consecutive_critical = 0
            if source >= BlockingSeverity.FREEZE:
                self._consecutive_freeze += 1
            else:
                self._consecutive_freeze = 0

            # 2. Decide the effective severity. Apply escalations in
            #    ascending order; the most-severe outcome wins.
            effective = source
            if (
                effective is BlockingSeverity.WARNING
                and self._consecutive_warning >= policy.escalation_warning_threshold
            ):
                effective = BlockingSeverity.CRITICAL
            if (
                effective is BlockingSeverity.CRITICAL
                and self._consecutive_critical >= policy.escalation_critical_threshold
            ):
                effective = BlockingSeverity.FREEZE

            escalated = effective > source
            return EscalationOutcome(
                classification=classification,
                effective_severity=effective,
                escalated=escalated,
                escalation_from=source if escalated else None,
                escalation_to=effective if escalated else None,
                consecutive_warning=self._consecutive_warning,
                consecutive_critical=self._consecutive_critical,
                consecutive_freeze=self._consecutive_freeze,
            )
