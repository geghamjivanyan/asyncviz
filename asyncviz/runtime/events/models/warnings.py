from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from asyncviz.runtime.events.models.base import RuntimeEvent
from asyncviz.runtime.events.models.enums import WarningSeverity


class WarningEvent(RuntimeEvent):
    event_type: Literal["runtime.warning"] = "runtime.warning"
    severity: WarningSeverity = WarningSeverity.WARNING
    message: str
    category: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
