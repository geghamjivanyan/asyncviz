"""Decorator-driven integration scenario registry."""

from __future__ import annotations

import threading
from dataclasses import dataclass

from tests.integration.harness.scenario_runner import ScenarioCallable
from tests.integration.integration_models import (
    IntegrationCategory,
    IntegrationScenarioSpec,
)


@dataclass(frozen=True, slots=True)
class RegisteredScenario:
    spec: IntegrationScenarioSpec
    runner: ScenarioCallable


class IntegrationRegistry:
    __slots__ = ("_entries", "_lock")

    def __init__(self) -> None:
        self._entries: dict[str, RegisteredScenario] = {}
        self._lock = threading.Lock()

    def register(
        self,
        spec: IntegrationScenarioSpec,
        runner: ScenarioCallable,
    ) -> None:
        with self._lock:
            if spec.name in self._entries:
                raise ValueError(f"scenario already registered: {spec.name}")
            self._entries[spec.name] = RegisteredScenario(spec=spec, runner=runner)

    def get(self, name: str) -> RegisteredScenario | None:
        with self._lock:
            return self._entries.get(name)

    def all(self) -> tuple[RegisteredScenario, ...]:
        with self._lock:
            return tuple(self._entries.values())

    def by_category(
        self,
        category: IntegrationCategory,
    ) -> tuple[RegisteredScenario, ...]:
        with self._lock:
            return tuple(
                entry for entry in self._entries.values() if entry.spec.category == category
            )

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def __contains__(self, name: str) -> bool:
        with self._lock:
            return name in self._entries

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)


_default = IntegrationRegistry()
_default_lock = threading.Lock()


def default_integration_registry() -> IntegrationRegistry:
    with _default_lock:
        return _default


def reset_default_registry() -> None:
    with _default_lock:
        _default.clear()


def register_scenario(
    spec: IntegrationScenarioSpec,
    runner: ScenarioCallable,
    *,
    registry: IntegrationRegistry | None = None,
) -> None:
    target = registry if registry is not None else default_integration_registry()
    target.register(spec, runner)
