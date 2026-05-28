"""Lag → blocking severity classification.

The lag monitor already produces a :class:`LagSeverity` via its threshold
policy. The blocking detector then *re-classifies* that observation into
a :class:`BlockingSeverity` so it can be reasoned about independently:

* ``LagSeverity`` is per-sample lag-vs-threshold.
* ``BlockingSeverity`` is the detector's interpretation of *what kind of
  runtime impact* this represents — it folds escalation pressure +
  freeze-window membership in later stages.

Today the base classification is a direct lift of the lag severity (one
:class:`LagSeverity` value maps to one :class:`BlockingSeverity` value),
but the indirection lets future work bolt on adaptive baselines,
anomaly scores, and runtime-specific overrides without touching the
monitor.

Replay-safe by construction: classification is a pure function of the
incoming evaluation. No clocks, no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from asyncviz.runtime.monitoring.event_loop.lag_measurement import LagMeasurement
from asyncviz.runtime.monitoring.event_loop.lag_thresholds import (
    LagSeverity,
    LagThresholdEvaluation,
)


class BlockingSeverity(IntEnum):
    """Detector-level severity tier.

    Ordered numerically (``FREEZE > CRITICAL > WARNING > NONE``) so
    consumers can compare with ``>=``. Stored as ``IntEnum`` for cheap
    serialization (an int rides through JSON without needing a custom
    encoder).
    """

    NONE = 0
    WARNING = 1
    CRITICAL = 2
    FREEZE = 3


_LAG_TO_BLOCKING: dict[LagSeverity, BlockingSeverity] = {
    LagSeverity.NORMAL: BlockingSeverity.NONE,
    LagSeverity.WARNING: BlockingSeverity.WARNING,
    LagSeverity.CRITICAL: BlockingSeverity.CRITICAL,
    LagSeverity.FREEZE: BlockingSeverity.FREEZE,
}


@dataclass(frozen=True, slots=True)
class BlockingClassification:
    """The classifier's output for one measurement.

    Carries the canonical :class:`BlockingSeverity` plus the inputs that
    produced it. Down-stream pipeline stages (escalation, windows,
    cooldowns) operate on this value rather than re-reading the lag
    monitor's structures, which keeps the contract explicit and
    replay-safe.

    ``threshold_ns`` and ``lag_ns`` are duplicated from the lag evaluation
    so consumers don't need to keep both objects alive.
    """

    severity: BlockingSeverity
    measurement: LagMeasurement
    lag_ns: int
    threshold_ns: int
    source_severity: LagSeverity

    @property
    def is_violation(self) -> bool:
        return self.severity is not BlockingSeverity.NONE

    def to_dict(self) -> dict[str, object]:
        return {
            "severity": self.severity.name,
            "severity_value": int(self.severity),
            "lag_ns": self.lag_ns,
            "threshold_ns": self.threshold_ns,
            "source_severity": self.source_severity.name,
            "sample_index": self.measurement.sample_index,
            "scheduled_ns": self.measurement.scheduled_ns,
            "actual_ns": self.measurement.actual_ns,
        }


class BlockingClassifier:
    """Stateless classifier — pure function on inputs.

    The instance exists so future implementations that *do* hold state
    (rolling baselines, anomaly scores) can swap in without changing
    consumer code. Today it just looks up the lag severity in the
    static map above.
    """

    __slots__ = ()

    def classify(
        self,
        measurement: LagMeasurement,
        evaluation: LagThresholdEvaluation,
    ) -> BlockingClassification:
        severity = _LAG_TO_BLOCKING[evaluation.severity]
        return BlockingClassification(
            severity=severity,
            measurement=measurement,
            lag_ns=evaluation.lag_ns,
            threshold_ns=evaluation.threshold_ns,
            source_severity=evaluation.severity,
        )

    @staticmethod
    def to_blocking_severity(severity: LagSeverity) -> BlockingSeverity:
        return _LAG_TO_BLOCKING[severity]
