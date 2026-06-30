"""Canonical stress runner.

The :class:`StressRunner` is the top-level façade. It:

1. Resolves which scenarios to execute (filter by name / category).
2. Constructs a :class:`ScenarioContext` per scenario with a
   deterministic per-scenario seed.
3. Executes the scenario inside a wall-clock budget guard.
4. Aggregates the resulting signals into a :class:`StressOutcome`
   (with threshold validation + survivability score).
5. Returns the outcomes; surfaces a structured report via
   :class:`StressScalabilityReport`.

The runner is async-first: scenarios are coroutines. Multiple
scenarios run *sequentially* by default — each storm dominates the
runtime, so parallel execution defeats the purpose. Operators that
want parallel execution can run the runner in multiple processes.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
import tracemalloc
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from asyncviz.stress.failure_injection.failure_registry import (
    FailureInjectionRegistry,
)
from asyncviz.stress.harness.scenario_context import (
    ScenarioContext,
    derive_scenario_seed,
)
from asyncviz.stress.models.stress_outcome import (
    ScalabilityViolation,
    StressOutcome,
)
from asyncviz.stress.models.stress_scenario import (
    ScenarioCategory,
    StressScenarioSpec,
)
from asyncviz.stress.stress_configuration import StressConfig, default_config
from asyncviz.stress.stress_observability import (
    StressMetrics,
    get_stress_metrics,
)
from asyncviz.stress.stress_registry import (
    RegisteredScenario,
    StressScenarioRegistry,
    default_stress_registry,
)
from asyncviz.stress.stress_thresholds import (
    compute_survivability_score,
    evaluate_violations,
    verdict_for,
)
from asyncviz.stress.stress_tracing import record_stress_trace
from asyncviz.stress.utils.deterministic_rng import DeterministicRng


@dataclass(frozen=True, slots=True)
class StressRunInputs:
    """Optional knobs for :meth:`StressRunner.run`."""

    category: ScenarioCategory | None = None
    only: tuple[str, ...] = ()
    skip: tuple[str, ...] = ()
    warn_only: bool = False
    """If ``True``, violations downgrade to ``warned`` instead of
    ``failed``. Useful for soaks where we want the report but not
    a CI gate."""


class StressRunner:
    """Top-level stress orchestration façade."""

    __slots__ = (
        "_config",
        "_metrics",
        "_registry",
    )

    def __init__(
        self,
        *,
        config: StressConfig | None = None,
        registry: StressScenarioRegistry | None = None,
        metrics: StressMetrics | None = None,
    ) -> None:
        self._config = config if config is not None else default_config()
        self._registry = registry if registry is not None else default_stress_registry()
        self._metrics = metrics if metrics is not None else get_stress_metrics()

    @property
    def config(self) -> StressConfig:
        return self._config

    @property
    def registry(self) -> StressScenarioRegistry:
        return self._registry

    @property
    def metrics(self) -> StressMetrics:
        return self._metrics

    # ── orchestration ────────────────────────────────────────────

    async def run(
        self,
        inputs: StressRunInputs | None = None,
    ) -> tuple[StressOutcome, ...]:
        run_inputs = inputs or StressRunInputs()
        scenarios = self._select(run_inputs)
        outcomes: list[StressOutcome] = []
        for entry in scenarios:
            outcome = await self.run_scenario(entry, warn_only=run_inputs.warn_only)
            outcomes.append(outcome)
        return tuple(outcomes)

    async def run_scenario(
        self,
        entry: RegisteredScenario,
        *,
        warn_only: bool = False,
    ) -> StressOutcome:
        spec = entry.spec
        self._metrics.record_scenario_started(spec.category)
        record_stress_trace("scenario-started", spec.name)
        seed = derive_scenario_seed(
            self._config.failure_injection.seed,
            spec.name,
        )
        context = ScenarioContext(
            spec=spec,
            config=self._config,
            metrics=self._metrics,
            failure_injection=FailureInjectionRegistry(self._config.failure_injection),
            rng=DeterministicRng(seed),
        )
        tracing = self._config.thresholds.max_memory_growth_bytes is not None
        tracemalloc_was_running = tracemalloc.is_tracing()
        if tracing and not tracemalloc_was_running:
            tracemalloc.start()
        baseline_bytes = 0
        if tracing:
            baseline_bytes = tracemalloc.get_traced_memory()[0]
        started = time.monotonic()
        errored = False
        error_detail = ""
        try:
            await asyncio.wait_for(entry.runner(context), self._config.scenario_budget_s)
        except TimeoutError:
            errored = True
            error_detail = f"scenario exceeded budget ({self._config.scenario_budget_s}s)"
            record_stress_trace("scenario-errored", f"{spec.name}: timeout")
        except Exception as exc:
            errored = True
            error_detail = f"{type(exc).__name__}: {exc}"
            record_stress_trace("scenario-errored", f"{spec.name}: {error_detail}")
        duration_s = time.monotonic() - started
        peak_bytes = 0
        if tracing:
            current, peak = tracemalloc.get_traced_memory()
            peak_bytes = max(0, peak - baseline_bytes)
            if not tracemalloc_was_running:
                tracemalloc.stop()
            _ = current  # unused

        outcome = self._aggregate_outcome(
            spec=spec,
            context=context,
            duration_s=duration_s,
            errored=errored,
            error_detail=error_detail,
            warn_only=warn_only,
            peak_bytes=peak_bytes,
        )
        self._metrics.record_scenario_completed()
        self._metrics.record_scenario_verdict(outcome.verdict)
        for _ in outcome.violations:
            self._metrics.record_threshold_violation()
        self._metrics.record_survivability_score(outcome.survivability_score)
        record_stress_trace(
            "scenario-completed",
            f"{spec.name}: verdict={outcome.verdict} duration={duration_s:.3f}s",
        )
        return outcome

    # ── selection ────────────────────────────────────────────────

    def _select(
        self,
        inputs: StressRunInputs,
    ) -> Sequence[RegisteredScenario]:
        all_entries = self._registry.all()
        only_set = set(inputs.only)
        skip_set = set(inputs.skip)
        results: list[RegisteredScenario] = []
        for entry in all_entries:
            if inputs.category is not None and entry.spec.category != inputs.category:
                continue
            if only_set and entry.spec.name not in only_set:
                continue
            if entry.spec.name in skip_set:
                continue
            results.append(entry)
        return results

    # ── aggregation ──────────────────────────────────────────────

    def _aggregate_outcome(
        self,
        *,
        spec: StressScenarioSpec,
        context: ScenarioContext,
        duration_s: float,
        errored: bool,
        error_detail: str,
        warn_only: bool,
        peak_bytes: int,
    ) -> StressOutcome:
        signals = context.signals()
        operations_completed = sum(1 for s in signals if s.kind == "operation")
        operations_failed = sum(1 for s in signals if s.kind == "failure")
        overload_transitions = sum(1 for s in signals if s.kind == "overload")
        emergency_actions = sum(1 for s in signals if s.kind == "emergency")
        websocket_disconnects = sum(1 for s in signals if s.kind == "websocket-disconnect")
        replay_frames = sum(1 for s in signals if s.kind == "replay-frame")
        render_frames = sum(1 for s in signals if s.kind == "render-frame")
        dropped_frames = sum(
            1 for s in signals if s.kind == "failure" and "render-frame-overrun" in s.detail
        )
        websocket_backlog = next(
            (
                int(s.value)
                for s in reversed(signals)
                if s.kind == "custom" and "backlog_peak" in s.detail
            ),
            0,
        )
        survivability_score = compute_survivability_score(
            operations_completed=operations_completed,
            operations_failed=operations_failed,
            overload_transitions=overload_transitions,
            emergency_actions=emergency_actions,
            websocket_disconnects=websocket_disconnects,
        )
        fps = (render_frames / duration_s) if (render_frames > 0 and duration_s > 0) else None
        violations: tuple[ScalabilityViolation, ...] = ()
        if not errored:
            violations = evaluate_violations(
                thresholds=self._config.thresholds,
                dropped_frames=dropped_frames,
                replay_drift_ms=0.0,
                websocket_backlog=websocket_backlog,
                memory_growth_bytes=peak_bytes,
                fps=fps,
                emergency_transitions=emergency_actions,
                survivability_score=survivability_score,
            )
        verdict = verdict_for(violations, errored=errored, warn_only=warn_only)
        return StressOutcome(
            spec=spec,
            verdict=verdict,
            duration_s=duration_s,
            operations_completed=operations_completed,
            operations_failed=operations_failed,
            overload_transitions=overload_transitions,
            emergency_actions=emergency_actions,
            websocket_disconnects=websocket_disconnects,
            replay_frames_streamed=replay_frames,
            render_frames_rendered=render_frames,
            peak_memory_bytes=peak_bytes,
            survivability_score=survivability_score,
            violations=violations,
            error_detail=error_detail,
        )


async def run_default_suite(
    *,
    config: StressConfig | None = None,
    inputs: StressRunInputs | None = None,
) -> tuple[StressOutcome, ...]:
    """Convenience: build a runner with defaults + execute."""
    runner = StressRunner(config=config)
    return await runner.run(inputs)


def iter_scenarios(
    registry: StressScenarioRegistry | None = None,
) -> Iterable[RegisteredScenario]:
    """Iterate over the registered scenarios."""
    target = registry if registry is not None else default_stress_registry()
    return target.all()


# Ensure the runner can be GC'd cleanly even if tracemalloc was started.
with contextlib.suppress(Exception):
    _ = tracemalloc
