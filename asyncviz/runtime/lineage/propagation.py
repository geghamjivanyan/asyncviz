"""Cancellation-ancestry propagation hooks.

Today this module is intentionally minimal — it reserves the surface so the
:class:`CancellationContext` can plug into it later without re-shaping the
import graph.

The plan:

* When a cancellation fires on a task that has children, the propagation
  walker enqueues the descendants for "origin = parent" attribution.
* The walker is iterative and bounded; it shares the
  :func:`asyncviz.runtime.lineage.ancestry.iter_subtree` algorithm so the
  two stay in sync.

For 1.12 we expose only the data types and a no-op default propagator.
Real propagation lands when the cancellation engine wires through here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class CancellationPropagationEvent:
    """One step in the cancellation walk.

    Reserved for the v2 cancellation engine. The ``ancestor_task_id`` is the
    cancellation source; ``task_id`` is the descendant being attributed.
    """

    task_id: str
    ancestor_task_id: str
    depth_from_ancestor: int


class CancellationPropagator(Protocol):
    """Strategy for attributing parent cancellations to descendants.

    Implementations are stateless and side-effect-free. The actual mutation
    (registry update, event emission) is handled by the caller.
    """

    def propagate(  # pragma: no cover - protocol
        self, source_task_id: str, /
    ) -> list[CancellationPropagationEvent]: ...


class NullPropagator:
    """Default propagator: returns no events.

    The cancellation engine swaps this for a real implementation once
    ancestry-aware cancellation rolls in. Tests can pass this in to make
    behavior explicit.
    """

    def propagate(self, source_task_id: str, /) -> list[CancellationPropagationEvent]:
        del source_task_id
        return []
