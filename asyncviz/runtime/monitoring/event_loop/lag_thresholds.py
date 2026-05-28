"""Threshold policy + severity evaluation for lag measurements.

Three escalation tiers:

* :attr:`LagSeverity.NORMAL`   — below warning threshold.
* :attr:`LagSeverity.WARNING`  — interesting; surfaced to diagnostics.
* :attr:`LagSeverity.CRITICAL` — emit a warning event.
* :attr:`LagSeverity.FREEZE`   — sustained loop block; downstream
  diagnostics flag the runtime as frozen.

Thresholds are stored as integer nanoseconds for cheap comparison; the
public constructor accepts seconds for ergonomics. Replay-safe: the
same inputs always produce the same severity, with no monotonic-clock
side effects.

Warning emission is intentionally *not* wired here — the monitor delegates
that to the runtime warning manager when integrated. This module only
returns a value; consumers decide what to do with it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from asyncviz.runtime.monitoring.event_loop.lag_clock import LagClock


class LagSeverity(IntEnum):
    """Threshold tier for one measurement.

    Ordered numerically — ``CRITICAL > WARNING > NORMAL`` etc — so callers
    can compare severities directly (e.g. ``severity >= LagSeverity.WARNING``).
    """

    NORMAL = 0
    WARNING = 1
    CRITICAL = 2
    FREEZE = 3


@dataclass(frozen=True, slots=True)
class LagThresholdEvaluation:
    """The outcome of evaluating one measurement against thresholds.

    Returned by :meth:`LagThresholds.evaluate`. ``breached`` is
    ``severity > NORMAL``; provided as a separate field so the hot
    path doesn't repeat the comparison.
    """

    severity: LagSeverity
    breached: bool
    lag_ns: int
    threshold_ns: int


class LagThresholds:
    """Configurable threshold policy.

    Constructor accepts seconds for readability; internally everything
    is stored as integer nanoseconds. Comparisons are inclusive of the
    threshold (``lag_ns >= threshold_ns`` triggers).

    All threshold tiers are *optional* — pass ``None`` to disable one. A
    disabled tier is treated as "never trips" by :meth:`evaluate`.
    """

    __slots__ = ("_critical_ns", "_freeze_ns", "_warning_ns")

    def __init__(
        self,
        *,
        warning_seconds: float | None = 0.05,
        critical_seconds: float | None = 0.25,
        freeze_seconds: float | None = 1.0,
    ) -> None:
        self._warning_ns = self._convert(warning_seconds)
        self._critical_ns = self._convert(critical_seconds)
        self._freeze_ns = self._convert(freeze_seconds)
        self._validate_monotonic()

    @staticmethod
    def _convert(seconds: float | None) -> int | None:
        if seconds is None:
            return None
        if seconds < 0:
            raise ValueError(f"threshold seconds must be non-negative (got {seconds})")
        return LagClock.seconds_to_ns(seconds)

    def _validate_monotonic(self) -> None:
        """Ensure warning <= critical <= freeze when all are set.

        Out-of-order thresholds would produce nonsensical severities (a
        measurement could be ``CRITICAL`` but not ``WARNING``). Caught
        early so misconfiguration surfaces at construction, not at the
        first sample.
        """
        ordered = [
            ("warning", self._warning_ns),
            ("critical", self._critical_ns),
            ("freeze", self._freeze_ns),
        ]
        previous_name: str | None = None
        previous_value: int | None = None
        for name, value in ordered:
            if value is None:
                continue
            if previous_value is not None and value < previous_value:
                raise ValueError(
                    f"threshold ordering invalid: {name}({value}ns) < "
                    f"{previous_name}({previous_value}ns)"
                )
            previous_name = name
            previous_value = value

    # ── reads ────────────────────────────────────────────────────────────
    @property
    def warning_ns(self) -> int | None:
        return self._warning_ns

    @property
    def critical_ns(self) -> int | None:
        return self._critical_ns

    @property
    def freeze_ns(self) -> int | None:
        return self._freeze_ns

    # ── evaluation ───────────────────────────────────────────────────────
    def evaluate(self, lag_ns: int) -> LagThresholdEvaluation:
        """Classify ``lag_ns`` into a severity + the threshold it tripped."""
        if self._freeze_ns is not None and lag_ns >= self._freeze_ns:
            return LagThresholdEvaluation(
                severity=LagSeverity.FREEZE,
                breached=True,
                lag_ns=lag_ns,
                threshold_ns=self._freeze_ns,
            )
        if self._critical_ns is not None and lag_ns >= self._critical_ns:
            return LagThresholdEvaluation(
                severity=LagSeverity.CRITICAL,
                breached=True,
                lag_ns=lag_ns,
                threshold_ns=self._critical_ns,
            )
        if self._warning_ns is not None and lag_ns >= self._warning_ns:
            return LagThresholdEvaluation(
                severity=LagSeverity.WARNING,
                breached=True,
                lag_ns=lag_ns,
                threshold_ns=self._warning_ns,
            )
        return LagThresholdEvaluation(
            severity=LagSeverity.NORMAL,
            breached=False,
            lag_ns=lag_ns,
            threshold_ns=0,
        )

    # ── serialization ────────────────────────────────────────────────────
    def to_dict(self) -> dict[str, int | None]:
        return {
            "warning_ns": self._warning_ns,
            "critical_ns": self._critical_ns,
            "freeze_ns": self._freeze_ns,
        }
