"""Track grouping projections."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from asyncviz.runtime.timeline.models import LifecycleSpan, TimelineTrack


def project_per_task_tracks(spans: Iterable[LifecycleSpan]) -> list[TimelineTrack]:
    """One track per task — the simplest grouping.

    Used by the inspector + "single-task focus" view. Tracks are sorted by
    the span's ``created_at_monotonic_ns`` so playback order matches
    appearance order on screen.
    """
    spans = list(spans)
    spans.sort(key=lambda s: (s.created_at_monotonic_ns, s.task_id))
    return [
        TimelineTrack(
            track_id=f"task:{span.task_id}",
            track_type="task",
            label=span.task_name or span.coroutine_name or span.task_id,
            spans=[span],
            earliest_monotonic_ns=span.created_at_monotonic_ns,
            latest_monotonic_ns=_span_latest_ns(span),
        )
        for span in spans
    ]


def project_root_tracks(spans: Iterable[LifecycleSpan]) -> list[TimelineTrack]:
    """One track per root task — every descendant in the same lane.

    Spans within a track are sorted by ``(depth, created_at)`` so child
    tasks land below their parent in DFS order.
    """
    grouped: dict[str, list[LifecycleSpan]] = defaultdict(list)
    for span in spans:
        root = span.root_task_id or span.task_id
        grouped[root].append(span)

    tracks: list[TimelineTrack] = []
    for root, group in grouped.items():
        group.sort(
            key=lambda s: (s.depth, s.created_at_monotonic_ns, s.task_id),
        )
        earliest = min(s.created_at_monotonic_ns for s in group)
        latest = max(_span_latest_ns(s) for s in group)
        root_span = next((s for s in group if s.task_id == root), group[0])
        tracks.append(
            TimelineTrack(
                track_id=f"root:{root}",
                track_type="root",
                label=root_span.task_name or root_span.coroutine_name or root,
                spans=group,
                earliest_monotonic_ns=earliest,
                latest_monotonic_ns=latest,
            )
        )
    tracks.sort(key=lambda t: (t.earliest_monotonic_ns, t.track_id))
    return tracks


def project_coroutine_tracks(spans: Iterable[LifecycleSpan]) -> list[TimelineTrack]:
    """One track per ``coroutine_name`` — useful for "which code path is hot?"."""
    grouped: dict[str, list[LifecycleSpan]] = defaultdict(list)
    for span in spans:
        key = span.coroutine_name or "<anonymous>"
        grouped[key].append(span)

    tracks: list[TimelineTrack] = []
    for name, group in grouped.items():
        group.sort(key=lambda s: (s.created_at_monotonic_ns, s.task_id))
        earliest = min(s.created_at_monotonic_ns for s in group)
        latest = max(_span_latest_ns(s) for s in group)
        tracks.append(
            TimelineTrack(
                track_id=f"coroutine:{name}",
                track_type="coroutine",
                label=name,
                spans=group,
                earliest_monotonic_ns=earliest,
                latest_monotonic_ns=latest,
            )
        )
    tracks.sort(key=lambda t: (t.label, t.earliest_monotonic_ns))
    return tracks


def _span_latest_ns(span: LifecycleSpan) -> int:
    if span.terminated_at_monotonic_ns is not None:
        return span.terminated_at_monotonic_ns
    if span.active_segment is not None:
        return span.active_segment.monotonic_start_ns + span.total_duration_ns
    return span.created_at_monotonic_ns + span.total_duration_ns
