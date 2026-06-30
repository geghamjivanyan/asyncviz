"""Frame-level filter predicates.

Filters are pure functions from :class:`ReplayFrame` to ``bool``
plus a small combinator algebra (``AND``, ``OR``, ``NOT``). Keeping
them dataclasses makes them serializable (useful when the future
remote loader wants to ship filter definitions over the wire).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from asyncviz.replay.format import ReplayFrame

FramePredicate = Callable[[ReplayFrame], bool]


@dataclass(frozen=True, slots=True)
class FrameFilter:
    """One named filter — a predicate + a label for diagnostics."""

    label: str
    predicate: FramePredicate

    def __call__(self, frame: ReplayFrame) -> bool:
        return self.predicate(frame)


# ── built-in factories ────────────────────────────────────────────


def by_event_type(*types: str) -> FrameFilter:
    """Match frames whose ``payload_type`` is in ``types``."""
    type_set = frozenset(str(t) for t in types)
    return FrameFilter(
        label=f"event_type∈{{{','.join(sorted(type_set))}}}",
        predicate=lambda frame: frame.payload_type in type_set,
    )


def by_frame_type(*types: str) -> FrameFilter:
    """Match frames by envelope ``frame_type``."""
    type_set = frozenset(str(t) for t in types)
    return FrameFilter(
        label=f"frame_type∈{{{','.join(sorted(type_set))}}}",
        predicate=lambda frame: frame.frame_type in type_set,
    )


def by_sequence_range(start: int, end: int | None = None) -> FrameFilter:
    """Match frames with sequence in ``[start, end]`` (inclusive).
    ``end=None`` means unbounded above."""

    def _check(frame: ReplayFrame) -> bool:
        if frame.sequence < start:
            return False
        return end is None or frame.sequence <= end

    return FrameFilter(label=f"seq∈[{start},{end}]", predicate=_check)


def by_timestamp_range(start_ns: int, end_ns: int | None = None) -> FrameFilter:
    """Match frames with monotonic_ns in ``[start_ns, end_ns]``."""

    def _check(frame: ReplayFrame) -> bool:
        if frame.monotonic_ns < start_ns:
            return False
        return end_ns is None or frame.monotonic_ns <= end_ns

    return FrameFilter(label=f"monotonic_ns∈[{start_ns},{end_ns}]", predicate=_check)


def by_runtime_id(runtime_id: str) -> FrameFilter:
    return FrameFilter(
        label=f"runtime_id={runtime_id}",
        predicate=lambda frame: frame.runtime_id == runtime_id,
    )


def by_recording_id(recording_id: str) -> FrameFilter:
    return FrameFilter(
        label=f"recording_id={recording_id}",
        predicate=lambda frame: frame.recording_id == recording_id,
    )


# ── combinators ───────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class _CombinedFilter:
    """Internal — base for AND/OR/NOT combinators."""

    label: str
    children: tuple[FrameFilter, ...] = field(default_factory=tuple)
    mode: str = "and"
    inverted: bool = False

    def __call__(self, frame: ReplayFrame) -> bool:
        if self.mode == "and":
            result = all(child(frame) for child in self.children)
        elif self.mode == "or":
            result = any(child(frame) for child in self.children)
        else:  # not — applied to the single child
            result = not self.children[0](frame)
        return not result if self.inverted else result


def all_of(*filters: FrameFilter) -> FrameFilter:
    """Match frames that satisfy every supplied filter."""
    if not filters:
        return FrameFilter(label="all_of(<empty>)", predicate=lambda _f: True)
    combined = _CombinedFilter(
        label="all_of(" + ", ".join(f.label for f in filters) + ")",
        children=tuple(filters),
        mode="and",
    )
    return FrameFilter(label=combined.label, predicate=combined)


def any_of(*filters: FrameFilter) -> FrameFilter:
    """Match frames that satisfy at least one supplied filter."""
    if not filters:
        return FrameFilter(label="any_of(<empty>)", predicate=lambda _f: False)
    combined = _CombinedFilter(
        label="any_of(" + ", ".join(f.label for f in filters) + ")",
        children=tuple(filters),
        mode="or",
    )
    return FrameFilter(label=combined.label, predicate=combined)


def not_(inner: FrameFilter) -> FrameFilter:
    """Invert a filter."""
    combined = _CombinedFilter(
        label=f"not({inner.label})",
        children=(inner,),
        mode="not",
    )
    return FrameFilter(label=combined.label, predicate=combined)


def chain(filters: Iterable[FrameFilter]) -> FrameFilter:
    """Combine an iterable of filters into a single AND filter.
    Convenience for code that builds filters dynamically."""
    return all_of(*filters)
