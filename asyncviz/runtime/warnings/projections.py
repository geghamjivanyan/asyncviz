"""Cross-cutting projections — by severity, by task, by lineage."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable

from asyncviz.runtime.events.models.enums import WarningSeverity
from asyncviz.runtime.warnings.lifecycle import WarningLifecycle
from asyncviz.runtime.warnings.models import WarningSeverityCounts


def count_by_severity(warnings: Iterable[WarningLifecycle]) -> WarningSeverityCounts:
    counter: Counter[WarningSeverity] = Counter()
    for w in warnings:
        counter[w.severity] += 1
    return WarningSeverityCounts(
        info=counter.get(WarningSeverity.INFO, 0),
        warning=counter.get(WarningSeverity.WARNING, 0),
        error=counter.get(WarningSeverity.ERROR, 0),
        critical=counter.get(WarningSeverity.CRITICAL, 0),
    )


def count_by_type(warnings: Iterable[WarningLifecycle]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for w in warnings:
        counter[w.warning_type] += 1
    return dict(counter)


def group_by_task(
    warnings: Iterable[WarningLifecycle],
) -> dict[str, list[WarningLifecycle]]:
    """Inverted index ``task_id → [warning, ...]``.

    Tasks without related ids land in an ``""`` bucket so the caller can
    surface runtime-level warnings as a group of their own.
    """
    grouped: defaultdict[str, list[WarningLifecycle]] = defaultdict(list)
    for w in warnings:
        if not w.related_task_ids:
            grouped[""].append(w)
        else:
            for tid in w.related_task_ids:
                grouped[tid].append(w)
    return dict(grouped)


def group_by_lineage(
    warnings: Iterable[WarningLifecycle],
) -> dict[str, list[WarningLifecycle]]:
    """Inverted index ``lineage_root_id → [warning, ...]``."""
    grouped: defaultdict[str, list[WarningLifecycle]] = defaultdict(list)
    for w in warnings:
        key = w.lineage_root_id or ""
        grouped[key].append(w)
    return dict(grouped)
