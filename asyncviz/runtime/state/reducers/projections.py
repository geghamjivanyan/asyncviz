"""Projection invalidation hints.

Projections (lineage_tree, coroutine_groups, cancellations_by_origin) are
materialized on-demand at snapshot time today. As the catalog grows, lazy
recomputation becomes the bottleneck — so reducers proactively emit
*invalidation hints* identifying which projections their mutation touched.

A projection cache (future work) can consult these to skip work; today
we just track the counters in :class:`ProjectionInvalidationBus` so the
metrics surface "is this projection actually being touched?"
"""

from __future__ import annotations

import threading
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum


class ProjectionName(StrEnum):
    """Names of every projection a reducer might invalidate.

    Adding a new projection requires adding a value here plus updating the
    reducers that should mark it dirty. The :func:`ProjectionInvalidationBus.metrics`
    output is keyed on these values, so the wire shape stays stable.
    """

    LINEAGE_TREE = "lineage_tree"
    COROUTINE_GROUPS = "coroutine_groups"
    CANCELLATIONS_BY_ORIGIN = "cancellations_by_origin"
    INDEX_VIEW = "index_view"


@dataclass(frozen=True, slots=True)
class InvalidationMetrics:
    """Per-projection invalidation counts."""

    counts: dict[str, int]


class ProjectionInvalidationBus:
    """Threadsafe per-projection counter.

    Reducers call :meth:`mark` to record that an apply touched a projection.
    A future projection cache would also subscribe via :meth:`subscribe`
    to drop its cached copy; the subscriber API is reserved today and not
    used by the live path, so we keep it tiny.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counts: Counter[str] = Counter()

    def mark(self, *projections: ProjectionName | str) -> None:
        if not projections:
            return
        with self._lock:
            for name in projections:
                key = name.value if isinstance(name, ProjectionName) else name
                self._counts[key] += 1

    def reset(self) -> None:
        with self._lock:
            self._counts.clear()

    def metrics(self) -> InvalidationMetrics:
        with self._lock:
            return InvalidationMetrics(counts=dict(self._counts))
