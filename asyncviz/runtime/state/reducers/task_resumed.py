from __future__ import annotations

from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.events.models import TaskResumedEvent
from asyncviz.runtime.events.models.enums import TaskState
from asyncviz.runtime.state.reducers.base import ReducerContext, ReducerResult
from asyncviz.runtime.state.reducers.lifecycle import safe_target_transition


class TaskResumedReducer:
    event_type: type[RuntimeEvent] = TaskResumedEvent
    name: str = "asyncio.task.resumed"

    def apply(self, ctx: ReducerContext, event: RuntimeEvent) -> ReducerResult:
        assert isinstance(event, TaskResumedEvent)
        return safe_target_transition(
            ctx,
            task_id=event.task_id,
            target=TaskState.RUNNING,
            reducer_name=self.name,
            event=event,
        )
