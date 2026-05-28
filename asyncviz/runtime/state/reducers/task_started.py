from __future__ import annotations

from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.events.models import TaskStartedEvent
from asyncviz.runtime.events.models.enums import TaskState
from asyncviz.runtime.state.reducers.base import ReducerContext, ReducerResult
from asyncviz.runtime.state.reducers.lifecycle import safe_target_transition


class TaskStartedReducer:
    event_type: type[RuntimeEvent] = TaskStartedEvent
    name: str = "asyncio.task.started"

    def apply(self, ctx: ReducerContext, event: RuntimeEvent) -> ReducerResult:
        assert isinstance(event, TaskStartedEvent)
        return safe_target_transition(
            ctx,
            task_id=event.task_id,
            target=TaskState.RUNNING,
            reducer_name=self.name,
            event=event,
        )
