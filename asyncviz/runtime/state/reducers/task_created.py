from __future__ import annotations

from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.events.models import TaskCreatedEvent
from asyncviz.runtime.events.models.enums import TaskState
from asyncviz.runtime.state.reducers.base import ReducerContext, ReducerResult
from asyncviz.runtime.state.reducers.lifecycle import accept, record_transition, reject
from asyncviz.runtime.state.reducers.projections import ProjectionName


class TaskCreatedReducer:
    """Apply a :class:`TaskCreatedEvent`.

    Semantics:

      * If the task is unknown → register it via ``registry.handle_event``,
        stamp a CREATED transition, mark lineage + index projections dirty.
      * If the task is already tracked → reject (idempotent at the registry
        layer, but the reducer level rejects so metrics surface the dedup).
    """

    event_type: type[RuntimeEvent] = TaskCreatedEvent
    name: str = "asyncio.task.created"

    def apply(self, ctx: ReducerContext, event: RuntimeEvent) -> ReducerResult:
        assert isinstance(event, TaskCreatedEvent)
        if event.task_id in ctx.registry:
            return reject(
                ctx,
                reducer_name=self.name,
                reason=f"task {event.task_id!r} already created",
                invalid_transition=True,
            )

        ctx.registry.handle_event(event)
        if event.task_id not in ctx.registry:
            return reject(
                ctx,
                reducer_name=self.name,
                reason="registry refused TaskCreatedEvent",
                invalid_transition=True,
            )

        transition = record_transition(
            ctx,
            task_id=event.task_id,
            target=TaskState.CREATED,
            event=event,
        )
        return accept(
            ctx,
            reducer_name=self.name,
            transition=transition,
            target_state=TaskState.CREATED,
            projections=(
                ProjectionName.LINEAGE_TREE,
                ProjectionName.COROUTINE_GROUPS,
                ProjectionName.INDEX_VIEW,
            ),
        )
