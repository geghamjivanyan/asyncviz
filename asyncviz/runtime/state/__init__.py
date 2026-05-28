"""Canonical runtime state store.

Public surface:

* :class:`RuntimeStateStore` — the derived-state model. One per runtime;
  hooked to the event bus via :func:`bind_store_to_event_bus`.
* :class:`RuntimeStateSnapshot` — replay-safe Pydantic snapshot.
* :class:`StateChange` / :class:`StateSubscription` — subscription types.
* :class:`StateStoreMetrics` / :class:`StateStoreMetricsSnapshot` — observability.
* :class:`ReconciliationPolicy` / :class:`ReconciliationDecision` — dedup +
  stale-event policy. Swappable; the default is sequence-aware.
* Reducers — pure functions over the registry, exposed for tests.
* Projections — derived views materialized into the snapshot.

Design rule: a runtime has exactly **one** :class:`RuntimeStateStore`. It
composes the :class:`TaskRegistry` and :class:`LineageTracker` rather than
duplicating their indexes. Mutations go through ``apply(event)``; reads
through :attr:`queries`, :meth:`snapshot`, or :meth:`metrics_snapshot`.
"""

from asyncviz.runtime.state.exceptions import (
    StaleEventError,
    StateRebuildError,
    StateStoreError,
    UnknownProjectionError,
)
from asyncviz.runtime.state.indexes import StateIndexView, build_index_view, is_active_state
from asyncviz.runtime.state.lifecycle import bind_store_to_event_bus
from asyncviz.runtime.state.metrics import StateStoreMetrics, StateStoreMetricsSnapshot
from asyncviz.runtime.state.models import (
    RuntimeLineageSummary,
    RuntimeStateMetrics,
    RuntimeStateSnapshot,
)
from asyncviz.runtime.state.normalization import (
    TASK_EVENT_TYPES,
    NormalizedEvent,
    normalize_event,
)
from asyncviz.runtime.state.projections import (
    cancellations_by_origin_projection,
    coroutine_groups_projection,
    default_projections,
    lineage_tree_projection,
)
from asyncviz.runtime.state.queries import StateQueryService
from asyncviz.runtime.state.reconciliation import (
    ReconciliationDecision,
    ReconciliationPolicy,
)
from asyncviz.runtime.state.reducers import (
    REDUCERS,
    InvalidTransitionError,
    ProjectionInvalidationBus,
    ProjectionName,
    Reducer,
    ReducerContext,
    ReducerError,
    ReducerMetrics,
    ReducerMetricsSnapshot,
    ReducerRegistry,
    ReducerResult,
    TerminalStateLockedError,
    TransitionHistory,
    TransitionRecord,
    UnknownReducerError,
    build_default_registry,
    evaluate_transition,
    find_reducer,
)
from asyncviz.runtime.state.snapshots import build_runtime_snapshot
from asyncviz.runtime.state.store import RuntimeStateStore
from asyncviz.runtime.state.subscriptions import (
    StateChange,
    StateListener,
    StateSubscription,
    StateSubscriptionRegistry,
)

__all__ = [
    "REDUCERS",
    "TASK_EVENT_TYPES",
    "InvalidTransitionError",
    "NormalizedEvent",
    "ProjectionInvalidationBus",
    "ProjectionName",
    "ReconciliationDecision",
    "ReconciliationPolicy",
    "Reducer",
    "ReducerContext",
    "ReducerError",
    "ReducerMetrics",
    "ReducerMetricsSnapshot",
    "ReducerRegistry",
    "ReducerResult",
    "RuntimeLineageSummary",
    "RuntimeStateMetrics",
    "RuntimeStateSnapshot",
    "RuntimeStateStore",
    "StaleEventError",
    "StateChange",
    "StateIndexView",
    "StateListener",
    "StateQueryService",
    "StateRebuildError",
    "StateStoreError",
    "StateStoreMetrics",
    "StateStoreMetricsSnapshot",
    "StateSubscription",
    "StateSubscriptionRegistry",
    "TerminalStateLockedError",
    "TransitionHistory",
    "TransitionRecord",
    "UnknownProjectionError",
    "UnknownReducerError",
    "bind_store_to_event_bus",
    "build_default_registry",
    "build_index_view",
    "build_runtime_snapshot",
    "cancellations_by_origin_projection",
    "coroutine_groups_projection",
    "default_projections",
    "evaluate_transition",
    "find_reducer",
    "is_active_state",
    "lineage_tree_projection",
    "normalize_event",
]
