from __future__ import annotations

from typing import Literal

from asyncviz.runtime.events.models.base import RuntimeEvent
from asyncviz.runtime.events.models.enums import RuntimeState


class RuntimeStartedEvent(RuntimeEvent):
    event_type: Literal["runtime.started"] = "runtime.started"
    runtime_state: RuntimeState = RuntimeState.RUNNING


class RuntimeStoppedEvent(RuntimeEvent):
    event_type: Literal["runtime.stopped"] = "runtime.stopped"
    runtime_state: RuntimeState = RuntimeState.STOPPED
    uptime_seconds: float = 0.0


class LoopBlockedEvent(RuntimeEvent):
    event_type: Literal["asyncio.loop.blocked"] = "asyncio.loop.blocked"
    blocked_seconds: float
    task_id: str | None = None
