"""Reusable integration fixtures.

These are *plain helpers*, not pytest fixtures — they construct
:class:`IntegrationContext` instances, build canned configurations,
and reset cross-test global state. The pytest fixtures themselves
live in ``tests/integration/conftest.py``.
"""

from __future__ import annotations

from asyncviz.stress.utils.deterministic_rng import (  # type: ignore[import-not-found]
    DeterministicRng,
)
from tests.integration.harness.scenario_context import (
    IntegrationContext,
    derive_scenario_seed,
)
from tests.integration.integration_configuration import (
    IntegrationConfig,
    default_config,
    lean_config,
)
from tests.integration.integration_models import IntegrationScenarioSpec
from tests.integration.integration_observability import (
    IntegrationMetrics,
    get_integration_metrics,
)


def build_test_context(
    *,
    spec: IntegrationScenarioSpec,
    config: IntegrationConfig | None = None,
    metrics: IntegrationMetrics | None = None,
    seed: int | None = None,
) -> IntegrationContext:
    """Construct an :class:`IntegrationContext` ready for use.

    Tests inject this directly when calling scenario callables in
    isolation (e.g. unit-testing a scenario without the runner).
    """
    cfg = config if config is not None else default_config()
    resolved_seed = seed if seed is not None else derive_scenario_seed(cfg.seed, spec.name)
    return IntegrationContext(
        spec=spec,
        config=cfg,
        metrics=metrics if metrics is not None else get_integration_metrics(),
        rng=DeterministicRng(resolved_seed),
    )


def lean_test_config() -> IntegrationConfig:
    """Shortcut — most test files want the lean config."""
    return lean_config()


__all__ = [
    "build_test_context",
    "lean_test_config",
]
