"""Decorator-driven scenario registry.

Modules declare scenarios via :func:`register_scenario` (or the
:func:`stress_scenario` decorator). The runner consumes the registry
to discover scenarios at runtime; tests can register temporary
scenarios + clear them via :func:`reset_default_registry`.
"""

from __future__ import annotations

import threading
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from asyncviz.stress.models.stress_scenario import (
    ScenarioCategory,
    ScenarioSeverity,
    StressScenarioSpec,
)

if TYPE_CHECKING:
    from asyncviz.stress.harness.scenario_context import ScenarioContext

ScenarioCallable = Callable[["ScenarioContext"], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class RegisteredScenario:
    spec: StressScenarioSpec
    runner: ScenarioCallable


class StressScenarioRegistry:
    """In-memory scenario registry."""

    __slots__ = ("_entries", "_lock")

    def __init__(self) -> None:
        self._entries: dict[str, RegisteredScenario] = {}
        self._lock = threading.Lock()

    def register(
        self,
        spec: StressScenarioSpec,
        runner: ScenarioCallable,
    ) -> None:
        with self._lock:
            if spec.name in self._entries:
                raise ValueError(f"scenario already registered: {spec.name}")
            self._entries[spec.name] = RegisteredScenario(spec=spec, runner=runner)

    def unregister(self, name: str) -> None:
        with self._lock:
            self._entries.pop(name, None)

    def get(self, name: str) -> RegisteredScenario | None:
        with self._lock:
            return self._entries.get(name)

    def all(self) -> tuple[RegisteredScenario, ...]:
        with self._lock:
            return tuple(self._entries.values())

    def by_category(self, category: ScenarioCategory) -> tuple[RegisteredScenario, ...]:
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


_default = StressScenarioRegistry()
_default_lock = threading.Lock()


def default_stress_registry() -> StressScenarioRegistry:
    with _default_lock:
        return _default


def reset_default_registry() -> None:
    with _default_lock:
        _default.clear()


def register_scenario(
    spec: StressScenarioSpec,
    runner: ScenarioCallable,
    *,
    registry: StressScenarioRegistry | None = None,
) -> None:
    target = registry if registry is not None else default_stress_registry()
    target.register(spec, runner)


def stress_scenario(
    *,
    name: str,
    category: ScenarioCategory,
    severity: ScenarioSeverity = "moderate",
    description: str = "",
    replay_safe: bool = True,
    failure_injection: bool = False,
    registry: StressScenarioRegistry | None = None,
) -> Callable[[ScenarioCallable], ScenarioCallable]:
    """Decorator that registers + returns the wrapped scenario."""

    spec = StressScenarioSpec(
        name=name,
        category=category,
        severity=severity,
        description=description,
        replay_safe=replay_safe,
        failure_injection=failure_injection,
    )

    def _wrap(fn: ScenarioCallable) -> ScenarioCallable:
        register_scenario(spec, fn, registry=registry)
        return fn

    return _wrap


def iter_categories(
    registry: StressScenarioRegistry | None = None,
) -> Iterable[ScenarioCategory]:
    """Stable iteration order over the categories the registry holds."""
    seen: set[ScenarioCategory] = set()
    target = registry if registry is not None else default_stress_registry()
    for entry in target.all():
        if entry.spec.category not in seen:
            seen.add(entry.spec.category)
            yield entry.spec.category
