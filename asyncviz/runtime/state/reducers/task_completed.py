from __future__ import annotations

from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.events.models import TaskCompletedEvent
from asyncviz.runtime.events.models.enums import TaskState
from asyncviz.runtime.state.reducers.base import ReducerContext, ReducerResult
from asyncviz.runtime.state.reducers.lifecycle import safe_target_transition
from asyncviz.runtime.state.reducers.projections import ProjectionName


class TaskCompletedReducer:
    event_type: type[RuntimeEvent] = TaskCompletedEvent
    name: str = "asyncio.task.completed"

    def apply(self, ctx: ReducerContext, event: RuntimeEvent) -> ReducerResult:
        assert isinstance(event, TaskCompletedEvent)
        # Terminal events also touch the coroutine_groups projection because
        # average-duration calculations move when a task completes.
        return safe_target_transition(
            ctx,
            task_id=event.task_id,
            target=TaskState.COMPLETED,
            reducer_name=self.name,
            event=event,
            projections=(
                ProjectionName.LINEAGE_TREE,
                ProjectionName.COROUTINE_GROUPS,
                ProjectionName.INDEX_VIEW,
            ),
        )
