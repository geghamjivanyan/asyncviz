"""Per-scenario runtime context.

Mirrors the stress-layer ``ScenarioContext``: a single object that
carries config, deterministic RNG, metrics, and a signal buffer.
Scenarios receive one of these from the runner; they never build
one themselves.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Literal

from asyncviz.stress.utils.deterministic_rng import (  # type: ignore[import-not-found]
    DeterministicRng,
)
from tests.integration.integration_configuration import IntegrationConfig
from tests.integration.integration_models import IntegrationScenarioSpec
from tests.integration.integration_observability import IntegrationMetrics
from tests.integration.integration_tracing import record_integration_trace

IntegrationSignalKind = Literal[
    "operation",
    "failure",
    "replay-frame",
    "render-frame",
    "render-drop",
    "overload",
    "emergency",
    "custom",
]


@dataclass(frozen=True, slots=True)
class IntegrationSignal:
    kind: IntegrationSignalKind
    detail: str = ""
    value: float = 0.0


@dataclass(slots=True)
class IntegrationContext:
    spec: IntegrationScenarioSpec
    config: IntegrationConfig
    metrics: IntegrationMetrics
    rng: DeterministicRng
    started_at_ns: int = field(default_factory=time.monotonic_ns)
    _signals: list[IntegrationSignal] = field(default_factory=list)

    def record(
        self,
        kind: IntegrationSignalKind,
        detail: str = "",
        value: float = 0.0,
    ) -> None:
        self._signals.append(IntegrationSignal(kind=kind, detail=detail, value=value))
        record_integration_trace("diagnostic", f"{self.spec.name}:{kind}:{detail}")

    def signals(self) -> tuple[IntegrationSignal, ...]:
        return tuple(self._signals)

    def signal_count(self, kind: IntegrationSignalKind) -> int:
        return sum(1 for s in self._signals if s.kind == kind)

    def elapsed_s(self) -> float:
        return (time.monotonic_ns() - self.started_at_ns) / 1e9

    @property
    def name(self) -> str:
        return self.spec.name


def derive_scenario_seed(base_seed: int, scenario_name: str) -> int:
    """Stable per-scenario seed — identical inputs → identical streams."""
    payload = f"{base_seed}::{scenario_name}".encode()
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return int.from_bytes(digest, "big")
