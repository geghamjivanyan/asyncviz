from __future__ import annotations

from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.events.models import TaskWaitingEvent
from asyncviz.runtime.events.models.enums import TaskState
from asyncviz.runtime.state.reducers.base import ReducerContext, ReducerResult
from asyncviz.runtime.state.reducers.lifecycle import safe_target_transition


class TaskWaitingReducer:
    event_type: type[RuntimeEvent] = TaskWaitingEvent
    name: str = "asyncio.task.waiting"

    def apply(self, ctx: ReducerContext, event: RuntimeEvent) -> ReducerResult:
        assert isinstance(event, TaskWaitingEvent)
        return safe_target_transition(
            ctx,
            task_id=event.task_id,
            target=TaskState.WAITING,
            reducer_name=self.name,
            event=event,
        )
