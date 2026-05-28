"""Shared per-scenario runtime context.

Scenarios receive a :class:`ScenarioContext` instead of a soup of
named arguments. The context carries:

* the active :class:`StressConfig`,
* the per-scenario :class:`FailureInjectionRegistry`,
* a :class:`DeterministicRng` seeded from the scenario name,
* the singleton :class:`StressMetrics` (so they can record signals),
* a bounded buffer of observed :class:`StressSignal`.

The context is constructed by the runner; scenarios never build one
themselves. Keeping the surface narrow means a scenario can be unit-
tested by passing a hand-built context.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from asyncviz.stress.failure_injection.failure_registry import (
    FailureInjectionRegistry,
)
from asyncviz.stress.models.stress_scenario import StressScenarioSpec
from asyncviz.stress.models.stress_signal import StressSignal, StressSignalKind
from asyncviz.stress.stress_configuration import StressConfig
from asyncviz.stress.stress_observability import StressMetrics
from asyncviz.stress.stress_tracing import record_stress_trace
from asyncviz.stress.utils.deterministic_rng import DeterministicRng

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass(slots=True)
class ScenarioContext:
    """Per-scenario services."""

    spec: StressScenarioSpec
    config: StressConfig
    metrics: StressMetrics
    failure_injection: FailureInjectionRegistry
    rng: DeterministicRng
    started_at_ns: int = field(default_factory=time.monotonic_ns)
    _signals: list[StressSignal] = field(default_factory=list)

    def record_signal(
        self,
        kind: StressSignalKind,
        detail: str = "",
        value: float = 0.0,
    ) -> None:
        """Append a stress signal + mirror to metrics + trace."""
        signal = StressSignal(kind=kind, detail=detail, value=value)
        self._signals.append(signal)
        record_stress_trace("signal", f"{kind}:{detail}")
        match kind:
            case "operation":
                self.metrics.record_operation_completed()
            case "failure":
                self.metrics.record_operation_failed()
            case "overload":
                self.metrics.record_overload_transition()
            case "emergency":
                self.metrics.record_emergency_action()
            case "websocket-disconnect":
                self.metrics.record_websocket_disconnect()
            case "replay-frame":
                self.metrics.record_replay_frame()
            case "render-frame":
                self.metrics.record_render_frame()
            case _:
                pass

    def record_signals(self, signals: Iterable[StressSignal]) -> None:
        for signal in signals:
            self.record_signal(signal.kind, signal.detail, signal.value)

    def signals(self) -> tuple[StressSignal, ...]:
        return tuple(self._signals)

    @property
    def name(self) -> str:
        return self.spec.name

    def elapsed_s(self) -> float:
        return (time.monotonic_ns() - self.started_at_ns) / 1e9


def derive_scenario_seed(base_seed: int, scenario_name: str) -> int:
    """Stable per-scenario seed from ``(base_seed, name)``."""
    payload = f"{base_seed}::{scenario_name}".encode()
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return int.from_bytes(digest, "big")
