"""Deduplication helpers.

A warning's ``warning_key`` is the dedup primary key. Detectors construct
deterministic keys (e.g., ``"slow_task:abc123"``) so repeated triggers
collapse onto the same :class:`WarningLifecycle` rather than spamming
new warnings.

This module exposes the policy decision (suppress vs. activate vs. refresh)
so the manager and tests can drive it cleanly.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from asyncviz.runtime.warnings.lifecycle import WarningLifecycle


class DedupDecision(StrEnum):
    """Outcome of :func:`evaluate_dedup`."""

    ACTIVATE = "activate"
    REFRESH = "refresh"
    SUPPRESS = "suppress"


@dataclass(frozen=True, slots=True)
class DedupResult:
    """The dedup verdict plus the (optional) existing lifecycle record."""

    decision: DedupDecision
    existing: WarningLifecycle | None


def evaluate_dedup(
    *,
    warning_key: str,
    existing: WarningLifecycle | None,
    sequence: int | None,
) -> DedupResult:
    """Decide what to do with a trigger for ``warning_key``.

    Rules:

    * Unknown key + no existing → ACTIVATE (new warning).
    * Known key + existing not resolved → REFRESH (bump counters).
    * Known key + existing resolved → ACTIVATE (re-open as a new warning
      with the same key but a new ``warning_id``).
    * Stale trigger (sequence <= last_observed_sequence) → SUPPRESS.
    """
    if existing is None:
        return DedupResult(decision=DedupDecision.ACTIVATE, existing=None)

    if (
        sequence is not None
        and existing.last_observed_sequence is not None
        and sequence <= existing.last_observed_sequence
    ):
        return DedupResult(decision=DedupDecision.SUPPRESS, existing=existing)

    if existing.resolved:
        return DedupResult(decision=DedupDecision.ACTIVATE, existing=existing)

    return DedupResult(decision=DedupDecision.REFRESH, existing=existing)


__all__ = ["DedupDecision", "DedupResult", "evaluate_dedup"]
