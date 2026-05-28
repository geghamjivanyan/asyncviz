"""Loader-side stream validation.

Wraps the format-layer :class:`SequenceValidator` so loader callers
get one ergonomic interface: a generator that yields *valid* frames
and accumulates a structured report of any violations. Default
policy is to *tolerate* gaps (since the recording's drop-newest
policy creates legitimate gaps) but flag duplicates + out-of-order
sequences as hard violations.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

from asyncviz.replay.format import ReplayFrame, SequenceValidator
from asyncviz.replay.loading.replay_observability import get_loader_metrics
from asyncviz.replay.loading.replay_tracing import record_replay_trace


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """One per-frame violation."""

    sequence: int
    reason: str


@dataclass(slots=True)
class ValidationReport:
    """Mutable report — appended to as validation proceeds."""

    issues: list[ValidationIssue] = field(default_factory=list)
    valid_count: int = 0

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def clean(self) -> bool:
        return not self.issues


def validate_loader_stream(
    frames: Iterable[ReplayFrame],
    *,
    allow_gaps: bool = True,
    strict: bool = False,
) -> tuple[Iterator[ReplayFrame], ValidationReport]:
    """Wrap ``frames`` in a validating generator.

    Returns ``(iterator, report)``. The iterator yields only frames
    that passed the sequence check (when ``strict=False``); the
    report accumulates issues as iteration progresses.

    When ``strict=True``, the first issue raises a :class:`ValueError`
    so ingest pipelines can fail loudly.
    """
    report = ValidationReport()

    def _walk() -> Iterator[ReplayFrame]:
        sv = SequenceValidator(allow_gaps=allow_gaps)
        for frame in frames:
            clean, reason = sv.observe(frame)
            if clean:
                report.valid_count += 1
                yield frame
                continue
            issue = ValidationIssue(sequence=frame.sequence, reason=reason)
            report.issues.append(issue)
            get_loader_metrics().record_sequence_violation()
            record_replay_trace("frame-dropped", f"seq={frame.sequence} {reason}")
            if strict:
                raise ValueError(f"replay validation failed at sequence {frame.sequence}: {reason}")

    return _walk(), report
