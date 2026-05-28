"""Canonical task-state reducer system.

Public surface:

* :class:`Reducer` — protocol every reducer implements.
* :class:`ReducerContext` / :class:`ReducerResult` — input/output types.
* :class:`ReducerRegistry` — typed dispatch table.
* :func:`build_default_registry` — pre-populated registry with the canonical
  task reducers (one per ``Task*Event`` class).
* :class:`TransitionHistory` / :class:`TransitionRecord` — per-task
  lifecycle history substrate for the future timeline panel.
* :class:`ProjectionInvalidationBus` / :class:`ProjectionName` — projection
  invalidation hints emitted by reducers on successful applies.
* :class:`ReducerMetrics` / :class:`ReducerMetricsSnapshot` /
  :class:`ReducerCounters` — per-reducer observability.
* :func:`evaluate_transition` / :class:`TransitionPlan` — pure validation.
* exceptions — :class:`ReducerError`, :class:`InvalidTransitionError`,
  :class:`TerminalStateLockedError`, :class:`UnknownReducerError`,
  :class:`ReducerRegistrationError`.

Legacy compatibility:

* :func:`find_reducer` and :data:`REDUCERS` keep their 2.1-era signatures so
  existing call sites (and any external integrations) keep working. New
  code should use :class:`ReducerRegistry` directly.
"""

from collections.abc import Callable

from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.events.models import (
    TaskCancelledEvent,
    TaskCompletedEvent,
    TaskCreatedEvent,
    TaskFailedEvent,
    TaskResumedEvent,
    TaskStartedEvent,
    TaskWaitingEvent,
)
from asyncviz.runtime.state.reducers.base import (
    Reducer,
    ReducerContext,
    ReducerResult,
)
from asyncviz.runtime.state.reducers.exceptions import (
    InvalidTransitionError,
    ReducerError,
    ReducerRegistrationError,
    TerminalStateLockedError,
    UnknownReducerError,
)
from asyncviz.runtime.state.reducers.metrics import (
    ReducerCounters,
    ReducerMetrics,
    ReducerMetricsSnapshot,
)
from asyncviz.runtime.state.reducers.projections import (
    InvalidationMetrics,
    ProjectionInvalidationBus,
    ProjectionName,
)
from asyncviz.runtime.state.reducers.reconciliation import (
    ReducerReconciliation,
    is_legal_transition,
    is_no_op_terminal,
)
from asyncviz.runtime.state.reducers.registry import (
    ReducerRegistry,
    build_default_registry,
)
from asyncviz.runtime.state.reducers.task_cancelled import TaskCancelledReducer
from asyncviz.runtime.state.reducers.task_completed import TaskCompletedReducer
from asyncviz.runtime.state.reducers.task_created import TaskCreatedReducer
from asyncviz.runtime.state.reducers.task_failed import TaskFailedReducer
from asyncviz.runtime.state.reducers.task_resumed import TaskResumedReducer
from asyncviz.runtime.state.reducers.task_started import TaskStartedReducer
from asyncviz.runtime.state.reducers.task_waiting import TaskWaitingReducer
from asyncviz.runtime.state.reducers.transitions import (
    DEFAULT_HISTORY_LIMIT,
    TransitionHistory,
    TransitionRecord,
)
from asyncviz.runtime.state.reducers.validation import (
    TransitionPlan,
    assert_transition,
    evaluate_transition,
    list_terminal_states,
)
from asyncviz.runtime.tasks import TaskRegistry

# ── Legacy compatibility surface ─────────────────────────────────────────
#
# Pre-2.2 callers imported ``find_reducer`` and ``REDUCERS`` directly from
# ``asyncviz.runtime.state.reducers``. Both expected the signature
# ``Callable[[TaskRegistry, RuntimeEvent], None]``. We preserve that shape
# by adapting the new class-based reducers behind the same callable.

_LEGACY_REGISTRY = build_default_registry()
_LEGACY_HISTORY = TransitionHistory()
_LEGACY_PROJECTIONS = ProjectionInvalidationBus()
_LEGACY_METRICS = ReducerMetrics()


def _legacy_invoke(reducer_cls: type[Reducer]) -> Callable[[TaskRegistry, RuntimeEvent], None]:
    def wrapper(registry: TaskRegistry, event: RuntimeEvent) -> None:
        # The legacy callable doesn't return a result; mutations happen via
        # the registry. We still use a real context so transition history /
        # metrics counters at the package level stay live for ad-hoc callers.
        ctx = ReducerContext(
            registry=registry,
            history=_LEGACY_HISTORY,
            projections=_LEGACY_PROJECTIONS,
            metrics=_LEGACY_METRICS,
            sequence=None,
        )
        reducer = _LEGACY_REGISTRY.get(event)
        if reducer is None:
            # Fall back to the registry's direct handler so unknown event
            # types still propagate (matches 2.1 behavior).
            registry.handle_event(event)
            return
        reducer.apply(ctx, event)

    wrapper.__name__ = f"legacy_{reducer_cls.__name__.lower()}"
    wrapper.__qualname__ = wrapper.__name__
    return wrapper


def reduce_task_created(registry: TaskRegistry, event: TaskCreatedEvent) -> None:
    _legacy_invoke(TaskCreatedReducer)(registry, event)


def reduce_task_started(registry: TaskRegistry, event: TaskStartedEvent) -> None:
    _legacy_invoke(TaskStartedReducer)(registry, event)


def reduce_task_waiting(registry: TaskRegistry, event: TaskWaitingEvent) -> None:
    _legacy_invoke(TaskWaitingReducer)(registry, event)


def reduce_task_resumed(registry: TaskRegistry, event: TaskResumedEvent) -> None:
    _legacy_invoke(TaskResumedReducer)(registry, event)


def reduce_task_completed(registry: TaskRegistry, event: TaskCompletedEvent) -> None:
    _legacy_invoke(TaskCompletedReducer)(registry, event)


def reduce_task_cancelled(registry: TaskRegistry, event: TaskCancelledEvent) -> None:
    _legacy_invoke(TaskCancelledReducer)(registry, event)


def reduce_task_failed(registry: TaskRegistry, event: TaskFailedEvent) -> None:
    _legacy_invoke(TaskFailedReducer)(registry, event)


REDUCERS: dict[type[RuntimeEvent], Callable[[TaskRegistry, RuntimeEvent], None]] = {
    TaskCreatedEvent: reduce_task_created,  # type: ignore[dict-item]
    TaskStartedEvent: reduce_task_started,  # type: ignore[dict-item]
    TaskWaitingEvent: reduce_task_waiting,  # type: ignore[dict-item]
    TaskResumedEvent: reduce_task_resumed,  # type: ignore[dict-item]
    TaskCompletedEvent: reduce_task_completed,  # type: ignore[dict-item]
    TaskCancelledEvent: reduce_task_cancelled,  # type: ignore[dict-item]
    TaskFailedEvent: reduce_task_failed,  # type: ignore[dict-item]
}


def find_reducer(
    event: RuntimeEvent,
) -> Callable[[TaskRegistry, RuntimeEvent], None] | None:
    """Legacy lookup. Returns the wrapper callable, or ``None``."""
    return REDUCERS.get(type(event))


__all__ = [
    "DEFAULT_HISTORY_LIMIT",
    "REDUCERS",
    "InvalidTransitionError",
    "InvalidationMetrics",
    "ProjectionInvalidationBus",
    "ProjectionName",
    "Reducer",
    "ReducerContext",
    "ReducerCounters",
    "ReducerError",
    "ReducerMetrics",
    "ReducerMetricsSnapshot",
    "ReducerReconciliation",
    "ReducerRegistrationError",
    "ReducerRegistry",
    "ReducerResult",
    "TaskCancelledReducer",
    "TaskCompletedReducer",
    "TaskCreatedReducer",
    "TaskFailedReducer",
    "TaskResumedReducer",
    "TaskStartedReducer",
    "TaskWaitingReducer",
    "TerminalStateLockedError",
    "TransitionHistory",
    "TransitionPlan",
    "TransitionRecord",
    "UnknownReducerError",
    "assert_transition",
    "build_default_registry",
    "evaluate_transition",
    "find_reducer",
    "is_legal_transition",
    "is_no_op_terminal",
    "list_terminal_states",
    "reduce_task_cancelled",
    "reduce_task_completed",
    "reduce_task_created",
    "reduce_task_failed",
    "reduce_task_resumed",
    "reduce_task_started",
    "reduce_task_waiting",
]
