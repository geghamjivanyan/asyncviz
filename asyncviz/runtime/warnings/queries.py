"""Read-only convenience over the manager's working state."""

from __future__ import annotations

from typing import TYPE_CHECKING

from asyncviz.runtime.events.models.enums import WarningSeverity
from asyncviz.runtime.warnings.lifecycle import WarningLifecycle

if TYPE_CHECKING:
    from asyncviz.runtime.warnings.manager import RuntimeWarningManager


class WarningQueryService:
    """Convenience wrapper around :class:`RuntimeWarningManager` reads."""

    __slots__ = ("_manager",)

    def __init__(self, manager: RuntimeWarningManager) -> None:
        self._manager = manager

    def get_warning(self, warning_id: str) -> WarningLifecycle | None:
        return self._manager.find_by_id(warning_id)

    def get_active_warnings(self) -> list[WarningLifecycle]:
        return [w for w in self._manager.lifecycles_view() if not w.resolved]

    def get_resolved_warnings(self) -> list[WarningLifecycle]:
        return [w for w in self._manager.lifecycles_view() if w.resolved]

    def get_warnings_for_task(self, task_id: str) -> list[WarningLifecycle]:
        return [w for w in self._manager.lifecycles_view() if task_id in w.related_task_ids]

    def get_warnings_by_severity(
        self,
        severity: WarningSeverity,
    ) -> list[WarningLifecycle]:
        return [w for w in self._manager.lifecycles_view() if w.severity is severity]

    def get_warnings_by_type(self, warning_type: str) -> list[WarningLifecycle]:
        return [w for w in self._manager.lifecycles_view() if w.warning_type == warning_type]

    def get_summary(self) -> dict[str, int]:
        active = self.get_active_warnings()
        return {
            "active_total": len(active),
            "resolved_total": len(self.get_resolved_warnings()),
        }
