from __future__ import annotations

from typing import Literal

from pydantic import Field

from asyncviz.runtime.events.models.base import RuntimeEvent


class MetricEvent(RuntimeEvent):
    event_type: Literal["runtime.metric"] = "runtime.metric"
    name: str
    value: float
    unit: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)
