from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from asyncviz.runtime.events.models.enums import TaskState


@dataclass(slots=True)
class TaskMetadata:
    """Optional context attached at task registration.

    Mutable on purpose — instrumentation can enrich a task after creation
    (e.g. add tags discovered mid-run). The :class:`TaskRegistry` owns the
    write-side locking; consumers should treat instances obtained via
    snapshots as read-only.
    """

    coroutine_name: str | None = None
    task_name: str | None = None
    parent_task_id: str | None = None
    asyncio_task_id: int | None = None
    runtime_id: uuid.UUID | None = None
    tags: dict[str, str] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RuntimeTask:
    """In-memory record for an observed asyncio task.

    Mutated only by the :class:`TaskRegistry` under its lock. External
    callers must consume :class:`TaskSnapshot` instances; mutating a
    ``RuntimeTask`` out of band is undefined behavior.

    Lineage fields (``root_task_id``, ``depth``, ``ancestor_chain``,
    ``child_count``) are owned by the :class:`LineageTracker` composed
    inside the registry. They are mirrored onto the task record so
    snapshots and the wire protocol see them without an extra lookup.
    """

    task_id: str
    state: TaskState
    created_at: float
    updated_at: float
    asyncio_task_id: int | None = None
    coroutine_name: str | None = None
    task_name: str | None = None
    parent_task_id: str | None = None
    root_task_id: str | None = None
    depth: int = 0
    ancestor_chain: tuple[str, ...] = ()
    child_count: int = 0
    completed_at: float | None = None
    duration_seconds: float | None = None
    exception_type: str | None = None
    exception_message: str | None = None
    cancellation_origin: str | None = None
    runtime_id: uuid.UUID | None = None
    tags: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        task_id: str,
        *,
        metadata: TaskMetadata | None = None,
        state: TaskState = TaskState.CREATED,
    ) -> RuntimeTask:
        now = time.time()
        md = metadata or TaskMetadata()
        return cls(
            task_id=task_id,
            state=state,
            created_at=now,
            updated_at=now,
            asyncio_task_id=md.asyncio_task_id,
            coroutine_name=md.coroutine_name,
            task_name=md.task_name,
            parent_task_id=md.parent_task_id,
            root_task_id=task_id,
            depth=0,
            ancestor_chain=(),
            child_count=0,
            runtime_id=md.runtime_id,
            tags=dict(md.tags),
            metadata=dict(md.extra),
        )


class TaskSnapshot(BaseModel):
    """Immutable, JSON-safe view of a :class:`RuntimeTask`.

    This is the shape the frontend will mirror. Field names and types are
    part of the public protocol — coordinate with the TypeScript types.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str
    state: TaskState
    created_at: float
    updated_at: float
    asyncio_task_id: int | None = None
    coroutine_name: str | None = None
    task_name: str | None = None
    parent_task_id: str | None = None
    root_task_id: str | None = None
    depth: int = 0
    ancestor_chain: list[str] = Field(default_factory=list)
    child_count: int = 0
    completed_at: float | None = None
    duration_seconds: float | None = None
    exception_type: str | None = None
    exception_message: str | None = None
    cancellation_origin: str | None = None
    runtime_id: uuid.UUID | None = None
    tags: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_task(cls, task: RuntimeTask) -> TaskSnapshot:
        return cls(
            task_id=task.task_id,
            state=task.state,
            created_at=task.created_at,
            updated_at=task.updated_at,
            asyncio_task_id=task.asyncio_task_id,
            coroutine_name=task.coroutine_name,
            task_name=task.task_name,
            parent_task_id=task.parent_task_id,
            root_task_id=task.root_task_id,
            depth=task.depth,
            ancestor_chain=list(task.ancestor_chain),
            child_count=task.child_count,
            completed_at=task.completed_at,
            duration_seconds=task.duration_seconds,
            exception_type=task.exception_type,
            exception_message=task.exception_message,
            cancellation_origin=task.cancellation_origin,
            runtime_id=task.runtime_id,
            tags=dict(task.tags),
            metadata=dict(task.metadata),
        )
