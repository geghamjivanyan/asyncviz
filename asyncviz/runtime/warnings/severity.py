"""Severity helpers.

Re-exports :class:`WarningSeverity` from the events module so the warning
system has a stable import path and adds a numeric ordering primitive
for "is this more severe than that?" comparisons (e.g., escalation rules).
"""

from __future__ import annotations

from asyncviz.runtime.events.models.enums import WarningSeverity

#: Numeric ordering — higher = more severe.
SEVERITY_ORDER: dict[WarningSeverity, int] = {
    WarningSeverity.INFO: 0,
    WarningSeverity.WARNING: 1,
    WarningSeverity.ERROR: 2,
    WarningSeverity.CRITICAL: 3,
}


def severity_rank(severity: WarningSeverity) -> int:
    return SEVERITY_ORDER[severity]


def is_at_least(severity: WarningSeverity, threshold: WarningSeverity) -> bool:
    return severity_rank(severity) >= severity_rank(threshold)


def max_severity(*severities: WarningSeverity) -> WarningSeverity:
    """Highest severity among the arguments. Raises on empty input."""
    if not severities:
        raise ValueError("at least one severity required")
    return max(severities, key=severity_rank)


__all__ = [
    "SEVERITY_ORDER",
    "WarningSeverity",
    "is_at_least",
    "max_severity",
    "severity_rank",
]
