"""Typed metadata records for instrumented executors + work items."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

#: Classification of an executor instance.
#: ``Thread`` is the stdlib ``concurrent.futures.ThreadPoolExecutor``.
#: ``Process`` is ``ProcessPoolExecutor``.
#: ``default`` is the loop's lazily-allocated default thread pool —
#: the one ``run_in_executor(None, ...)`` falls back to.
#: ``custom`` covers user subclasses + executors we can't otherwise
#: classify. ``unknown`` is the defensive fallback for objects that
#: don't look like executors at all (e.g. test doubles).
ExecutorKind = Literal["Thread", "Process", "default", "custom", "unknown"]


@dataclass(frozen=True, slots=True)
class ExecutorIdentity:
    """Stable identity record for one instrumented executor."""

    executor_id: str
    """Monotonic ``e-N`` id allocated by the registry."""

    object_id: int
    """``id(executor)`` at registration time."""

    executor_kind: ExecutorKind
    max_workers: int | None
    """``None`` when the executor doesn't expose a worker cap."""

    thread_name_prefix: str | None
    created_at_ns: int
    creator_task_id: str | None
    name: str | None = None


@dataclass(frozen=True, slots=True)
class WorkItemIdentity:
    """Per-submission identity for one ``run_in_executor`` call."""

    work_item_id: str
    """Monotonic ``w-N`` id allocated by the work-item registry."""

    executor_id: str
    submitting_task_id: str | None
    submitted_at_ns: int
    callable_name: str | None
    """``func.__qualname__`` when available; ``None`` otherwise.
    Never includes module path or repr, to keep the payload tight."""


@dataclass(frozen=True, slots=True)
class WorkItemSnapshot:
    """Frozen view of a work item's progress at event time."""

    work_item_id: str
    executor_id: str
    started: bool
    completed: bool
    cancelled: bool
    failed: bool
    duration_ns: int | None
