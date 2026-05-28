"""Reusable scenario fixtures.

Helpers that compose configurations or pre-build :class:`ScenarioContext`
instances for unit tests + downstream extensions.
"""

from __future__ import annotations

from asyncviz.stress.failure_injection.failure_registry import (
    FailureInjectionRegistry,
)
from asyncviz.stress.harness.scenario_context import (
    ScenarioContext,
    derive_scenario_seed,
)
from asyncviz.stress.models.stress_scenario import StressScenarioSpec
from asyncviz.stress.stress_configuration import StressConfig
from asyncviz.stress.stress_observability import StressMetrics
from asyncviz.stress.utils.deterministic_rng import DeterministicRng

__all__ = ["build_test_context"]


def build_test_context(
    *,
    spec: StressScenarioSpec,
    config: StressConfig,
    metrics: StressMetrics | None = None,
    seed: int | None = None,
) -> ScenarioContext:
    """Construct a fully-wired :class:`ScenarioContext` for tests."""
    resolved_seed = seed if seed is not None else derive_scenario_seed(
        config.failure_injection.seed, spec.name,
    )
    return ScenarioContext(
        spec=spec,
        config=config,
        metrics=metrics or StressMetrics(),
        failure_injection=FailureInjectionRegistry(config.failure_injection),
        rng=DeterministicRng(resolved_seed),
    )
