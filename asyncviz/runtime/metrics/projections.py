"""Cross-cutting projections — coroutine groups, top-N rankings, etc."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from asyncviz.runtime.tasks import TaskSnapshot


@dataclass(frozen=True, slots=True)
class CoroutineMetricsRow:
    """Per-coroutine roll-up row."""

    coroutine_name: str
    task_count: int
    active_count: int
    completed_count: int
    cancelled_count: int
    failed_count: int
    completed_total_duration_seconds: float
    completed_avg_duration_seconds: float | None
    max_duration_seconds: float | None


def aggregate_coroutine_groups(tasks: Iterable[TaskSnapshot]) -> list[CoroutineMetricsRow]:
    """Group ``tasks`` by ``coroutine_name`` and roll up the basic stats.

    Sorted by ``task_count`` descending so callers see the busiest
    coroutines first.
    """
    grouped: dict[str, list[TaskSnapshot]] = defaultdict(list)
    for snap in tasks:
        key = snap.coroutine_name or "<anonymous>"
        grouped[key].append(snap)

    out: list[CoroutineMetricsRow] = []
    for name, group in grouped.items():
        active = sum(1 for t in group if t.state.value in ("created", "running", "waiting"))
        completed = [t for t in group if t.state.value == "completed"]
        cancelled = sum(1 for t in group if t.state.value == "cancelled")
        failed = sum(1 for t in group if t.state.value == "failed")
        completed_durations = [
            t.duration_seconds for t in completed if t.duration_seconds is not None
        ]
        total = sum(completed_durations)
        avg = (total / len(completed_durations)) if completed_durations else None
        max_d = max(
            (t.duration_seconds for t in group if t.duration_seconds is not None),
            default=None,
        )
        out.append(
            CoroutineMetricsRow(
                coroutine_name=name,
                task_count=len(group),
                active_count=active,
                completed_count=len(completed),
                cancelled_count=cancelled,
                failed_count=failed,
                completed_total_duration_seconds=total,
                completed_avg_duration_seconds=avg,
                max_duration_seconds=max_d,
            )
        )
    out.sort(key=lambda row: (-row.task_count, row.coroutine_name))
    return out


def longest_running_tasks(
    tasks: Iterable[TaskSnapshot],
    *,
    limit: int = 10,
) -> list[TaskSnapshot]:
    """Top-N task snapshots by ``duration_seconds`` (terminal tasks only)."""
    candidates = [t for t in tasks if t.duration_seconds is not None]
    candidates.sort(key=lambda t: t.duration_seconds or 0.0, reverse=True)
    return candidates[:limit]


def shortest_running_tasks(
    tasks: Iterable[TaskSnapshot],
    *,
    limit: int = 10,
) -> list[TaskSnapshot]:
    """Bottom-N task snapshots by ``duration_seconds``."""
    candidates = [t for t in tasks if t.duration_seconds is not None]
    candidates.sort(key=lambda t: t.duration_seconds or 0.0)
    return candidates[:limit]
