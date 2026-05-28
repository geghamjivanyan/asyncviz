from __future__ import annotations

from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.events.models import TaskFailedEvent
from asyncviz.runtime.events.models.enums import TaskState
from asyncviz.runtime.state.reducers.base import ReducerContext, ReducerResult
from asyncviz.runtime.state.reducers.lifecycle import safe_target_transition
from asyncviz.runtime.state.reducers.projections import ProjectionName


class TaskFailedReducer:
    event_type: type[RuntimeEvent] = TaskFailedEvent
    name: str = "asyncio.task.failed"

    def apply(self, ctx: ReducerContext, event: RuntimeEvent) -> ReducerResult:
        assert isinstance(event, TaskFailedEvent)
        return safe_target_transition(
            ctx,
            task_id=event.task_id,
            target=TaskState.FAILED,
            reducer_name=self.name,
            event=event,
            projections=(
                ProjectionName.LINEAGE_TREE,
                ProjectionName.COROUTINE_GROUPS,
                ProjectionName.INDEX_VIEW,
            ),
        )
