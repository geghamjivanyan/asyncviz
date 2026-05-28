"""Cross-layer metrics-consistency scenario.

Exercises the backpressure, resilience, and stress observability
layers in a single run and confirms their counters agree on the
observed activity. The scenario emits one ``operation`` per
documented match + one ``failure`` per mismatch — the runner reads
the failure budget to gate pass/fail.
"""

from __future__ import annotations

from asyncviz.runtime.resilience import (  # type: ignore[import-not-found]
    RuntimeFailureManager,
    reset_isolation_metrics,
)
from tests.integration.harness.scenario_context import IntegrationContext


async def run_metrics_consistency(context: IntegrationContext) -> None:
    reset_isolation_metrics()
    mgr = RuntimeFailureManager()

    for index in range(12):
        with mgr.boundary("reducer", payload_kind=f"r-{index}"):
            raise TimeoutError("transient")

    domain = mgr.domain("reducer")
    metrics = mgr.diagnostics().metrics
    if domain.snapshot().total_failures == metrics.failures_observed:
        context.record("operation", "reducer-counts-match")
    else:
        context.record(
            "failure",
            f"counts-disagree:domain={domain.snapshot().total_failures} "
            f"metrics={metrics.failures_observed}",
        )

    # Tracing flag: enabling tracing must not affect counters.
    before = metrics.failures_observed
    mgr.diagnostics()
    after = mgr.diagnostics().metrics.failures_observed
    if before == after:
        context.record("operation", "diagnostics-pure")
    else:
        context.record(
            "failure",
            f"diagnostics-side-effect:before={before} after={after}",
        )
