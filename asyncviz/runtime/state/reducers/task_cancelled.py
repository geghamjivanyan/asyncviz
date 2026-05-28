from __future__ import annotations

from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.events.models import TaskCancelledEvent
from asyncviz.runtime.events.models.enums import TaskState
from asyncviz.runtime.state.reducers.base import ReducerContext, ReducerResult
from asyncviz.runtime.state.reducers.lifecycle import safe_target_transition
from asyncviz.runtime.state.reducers.projections import ProjectionName


class TaskCancelledReducer:
    event_type: type[RuntimeEvent] = TaskCancelledEvent
    name: str = "asyncio.task.cancelled"

    def apply(self, ctx: ReducerContext, event: RuntimeEvent) -> ReducerResult:
        assert isinstance(event, TaskCancelledEvent)
        return safe_target_transition(
            ctx,
            task_id=event.task_id,
            target=TaskState.CANCELLED,
            reducer_name=self.name,
            event=event,
            # ``cancellations_by_origin`` shifts on every cancel.
            projections=(
                ProjectionName.LINEAGE_TREE,
                ProjectionName.CANCELLATIONS_BY_ORIGIN,
                ProjectionName.COROUTINE_GROUPS,
                ProjectionName.INDEX_VIEW,
            ),
        )
