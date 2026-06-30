"""Canonical IntegrationRunner.

Top-level façade that takes scenarios from the registry, executes
them under the configured budget, optionally runs each one twice for
determinism + once more under uvloop, and produces a structured
report.

The runner never mutates global state outside its own metrics +
trace ring; identical inputs produce identical reports.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from asyncviz.runtime.compat import (  # type: ignore[import-not-found]
    is_uvloop_available,
)
from asyncviz.stress.utils.deterministic_rng import (  # type: ignore[import-not-found]
    DeterministicRng,
)
from tests.integration.harness.scenario_context import (
    IntegrationContext,
    derive_scenario_seed,
)
from tests.integration.harness.scenario_runner import run_scenario_async
from tests.integration.integration_configuration import (
    IntegrationConfig,
    default_config,
)
from tests.integration.integration_models import (
    IntegrationCategory,
    IntegrationOutcome,
    IntegrationScenarioSpec,
)
from tests.integration.integration_observability import (
    IntegrationMetrics,
    get_integration_metrics,
)
from tests.integration.integration_registry import (
    IntegrationRegistry,
    RegisteredScenario,
    default_integration_registry,
)
from tests.integration.integration_thresholds import (
    compute_survivability_score,
    evaluate_violations,
    verdict_for,
)
from tests.integration.integration_tracing import record_integration_trace
from tests.integration.orchestration.uvloop_matrix import run_matrix
from tests.integration.utils.signal_fingerprint import (
    fingerprint_signals,
)


@dataclass(frozen=True, slots=True)
class IntegrationRunInputs:
    category: IntegrationCategory | None = None
    only: tuple[str, ...] = ()
    skip: tuple[str, ...] = ()
    warn_only: bool = False
    determinism: bool = True
    uvloop_matrix: bool = True


class IntegrationRunner:
    __slots__ = ("_config", "_metrics", "_registry")

    def __init__(
        self,
        *,
        config: IntegrationConfig | None = None,
        registry: IntegrationRegistry | None = None,
        metrics: IntegrationMetrics | None = None,
    ) -> None:
        self._config = config if config is not None else default_config()
        self._registry = registry if registry is not None else default_integration_registry()
        self._metrics = metrics if metrics is not None else get_integration_metrics()

    @property
    def config(self) -> IntegrationConfig:
        return self._config

    @property
    def registry(self) -> IntegrationRegistry:
        return self._registry

    @property
    def metrics(self) -> IntegrationMetrics:
        return self._metrics

    async def run(
        self,
        inputs: IntegrationRunInputs | None = None,
    ) -> tuple[IntegrationOutcome, ...]:
        run_inputs = inputs or IntegrationRunInputs()
        entries = self._select(run_inputs)
        outcomes: list[IntegrationOutcome] = []
        for entry in entries:
            outcome = await self._run_one(entry, run_inputs)
            outcomes.append(outcome)
        return tuple(outcomes)

    async def _run_one(
        self,
        entry: RegisteredScenario,
        inputs: IntegrationRunInputs,
    ) -> IntegrationOutcome:
        spec = entry.spec
        self._metrics.record_scenario_started(spec.category)
        record_integration_trace("scenario-started", spec.name)

        context = self._make_context(spec)
        context, duration, errored, error_detail = await run_scenario_async(
            entry.runner,
            context,
        )
        determinism_diverged = False
        determinism_runs = 1
        if (
            inputs.determinism
            and spec.require_determinism
            and spec.replay_safe
            and not errored
            and self._config.determinism_runs > 1
        ):
            baseline = fingerprint_signals(context.signals())
            for run_index in range(self._config.determinism_runs - 1):
                replay_ctx = self._make_context(spec)
                replay_ctx, _, errored_replay, _ = await run_scenario_async(
                    entry.runner,
                    replay_ctx,
                )
                determinism_runs += 1
                replay_fp = fingerprint_signals(replay_ctx.signals())
                diverged = errored_replay or baseline.digest != replay_fp.digest
                self._metrics.record_determinism_run(diverged=diverged)
                if diverged:
                    determinism_diverged = True
                    record_integration_trace(
                        "determinism-run",
                        f"{spec.name}:run={run_index + 1}:DIVERGED",
                    )
                    break
                record_integration_trace(
                    "determinism-run",
                    f"{spec.name}:run={run_index + 1}:match",
                )

        uvloop_run = False
        uvloop_diverged = False
        if (
            inputs.uvloop_matrix
            and self._config.enable_uvloop_matrix
            and spec.uvloop_safe
            and not errored
            and is_uvloop_available()
        ):
            uvloop_run = True
            baseline = fingerprint_signals(context.signals())
            try:
                _, uvloop_ctx = run_matrix(
                    lambda: self._isolated_invoke(entry, spec),
                    include_uvloop=True,
                )
            except Exception:
                uvloop_diverged = True
                uvloop_ctx = None
            if uvloop_ctx is not None:
                uvloop_fp = fingerprint_signals(uvloop_ctx.signals())
                if uvloop_fp.digest != baseline.digest:
                    uvloop_diverged = True
            self._metrics.record_uvloop_run(diverged=uvloop_diverged)
            record_integration_trace(
                "uvloop-run",
                f"{spec.name}:{'DIVERGED' if uvloop_diverged else 'match'}",
            )

        outcome = self._aggregate_outcome(
            spec=spec,
            context=context,
            duration_s=duration,
            errored=errored,
            error_detail=error_detail,
            determinism_runs=determinism_runs,
            determinism_diverged=determinism_diverged,
            uvloop_matrix_run=uvloop_run,
            uvloop_diverged=uvloop_diverged,
            warn_only=inputs.warn_only,
        )
        self._metrics.record_scenario_completed()
        self._metrics.record_verdict(outcome.verdict)
        self._metrics.record_operations(
            completed=outcome.operations_completed,
            failed=outcome.operations_failed,
        )
        self._metrics.record_threshold_violations(len(outcome.violations))
        record_integration_trace(
            "scenario-completed",
            f"{spec.name}:verdict={outcome.verdict}",
        )
        return outcome

    def _make_context(self, spec: IntegrationScenarioSpec) -> IntegrationContext:
        seed = derive_scenario_seed(self._config.seed, spec.name)
        return IntegrationContext(
            spec=spec,
            config=self._config,
            metrics=self._metrics,
            rng=DeterministicRng(seed),
        )

    async def _isolated_invoke(
        self,
        entry: RegisteredScenario,
        spec: IntegrationScenarioSpec,
    ) -> IntegrationContext:
        context = self._make_context(spec)
        await entry.runner(context)
        return context

    def _select(self, inputs: IntegrationRunInputs) -> Sequence[RegisteredScenario]:
        only_set = set(inputs.only)
        skip_set = set(inputs.skip)
        results: list[RegisteredScenario] = []
        for entry in self._registry.all():
            if inputs.category is not None and entry.spec.category != inputs.category:
                continue
            if only_set and entry.spec.name not in only_set:
                continue
            if entry.spec.name in skip_set:
                continue
            results.append(entry)
        return results

    def _aggregate_outcome(
        self,
        *,
        spec: IntegrationScenarioSpec,
        context: IntegrationContext,
        duration_s: float,
        errored: bool,
        error_detail: str,
        determinism_runs: int,
        determinism_diverged: bool,
        uvloop_matrix_run: bool,
        uvloop_diverged: bool,
        warn_only: bool,
    ) -> IntegrationOutcome:
        signals = context.signals()
        operations_completed = sum(1 for s in signals if s.kind == "operation")
        operations_failed = sum(1 for s in signals if s.kind == "failure")
        replay_frames = sum(1 for s in signals if s.kind == "replay-frame")
        render_frames = sum(1 for s in signals if s.kind == "render-frame")
        render_drops = sum(1 for s in signals if s.kind == "render-drop")
        overload_transitions = sum(1 for s in signals if s.kind == "overload")
        emergency_transitions = sum(1 for s in signals if s.kind == "emergency")
        websocket_backlog = next(
            (
                int(s.value)
                for s in reversed(signals)
                if s.kind == "custom" and "backlog_peak" in s.detail
            ),
            0,
        )
        survivability = compute_survivability_score(
            operations_completed=operations_completed,
            operations_failed=operations_failed,
            overload_transitions=overload_transitions,
            emergency_actions=emergency_transitions,
        )
        violations = ()
        if not errored:
            violations = evaluate_violations(
                thresholds=self._config.thresholds,
                operations_completed=operations_completed,
                operations_failed=operations_failed,
                websocket_backlog=websocket_backlog,
                emergency_transitions=emergency_transitions,
                survivability_score=survivability,
                determinism_diverged=determinism_diverged,
                uvloop_diverged=uvloop_diverged,
            )
        verdict = verdict_for(violations, errored=errored, warn_only=warn_only)
        return IntegrationOutcome(
            spec=spec,
            verdict=verdict,
            duration_s=duration_s,
            operations_completed=operations_completed,
            operations_failed=operations_failed,
            replay_drift_ms=0.0,
            websocket_backlog_peak=websocket_backlog,
            replay_frames=replay_frames,
            render_frames=render_frames,
            render_drops=render_drops,
            overload_transitions=overload_transitions,
            emergency_transitions=emergency_transitions,
            survivability_score=survivability,
            determinism_runs=determinism_runs,
            determinism_diverged=determinism_diverged,
            uvloop_matrix_run=uvloop_matrix_run,
            uvloop_diverged=uvloop_diverged,
            violations=violations,
            error_detail=error_detail,
        )


def iter_scenarios(
    registry: IntegrationRegistry | None = None,
) -> Iterable[RegisteredScenario]:
    target = registry if registry is not None else default_integration_registry()
    return target.all()


async def run_default_suite(
    *,
    config: IntegrationConfig | None = None,
    inputs: IntegrationRunInputs | None = None,
) -> tuple[IntegrationOutcome, ...]:
    runner = IntegrationRunner(config=config)
    return await runner.run(inputs)


def run_default_suite_sync(
    *,
    config: IntegrationConfig | None = None,
    inputs: IntegrationRunInputs | None = None,
) -> tuple[IntegrationOutcome, ...]:
    return asyncio.run(run_default_suite(config=config, inputs=inputs))
