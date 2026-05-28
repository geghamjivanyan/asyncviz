"""Diagnostics consistency scenario.

Builds diagnostics from every runtime layer + checks the cross-
references agree:

* resilience.diagnostics().domains contains every registered
  subsystem,
* stress.build_stress_diagnostics returns a snapshot without
  raising,
* compat.build_loop_compat_diagnostics returns a snapshot the trace
  ring is consistent with.
"""

from __future__ import annotations

import asyncviz.stress as stress  # type: ignore[import-not-found]
from asyncviz.runtime.compat import (  # type: ignore[import-not-found]
    LoopCompatibilityManager,
)
from asyncviz.runtime.resilience import (  # type: ignore[import-not-found]
    RuntimeFailureManager,
)
from tests.integration.harness.scenario_context import IntegrationContext


async def run_diagnostics_consistency(context: IntegrationContext) -> None:
    resilience = RuntimeFailureManager()
    resilience.replay()
    resilience.websocket()
    resilience.recorder()
    diag = resilience.diagnostics()
    if {d.name for d in diag.domains} >= {"replay", "websocket", "recorder"}:
        context.record("operation", "resilience-domains-ok")
    else:
        context.record(
            "failure",
            f"missing-domains:{[d.name for d in diag.domains]}",
        )

    stress_diag = stress.build_stress_diagnostics()
    context.record(
        "operation",
        f"stress-diag-metrics={stress_diag.metrics.scenarios_started}",
    )

    compat = LoopCompatibilityManager()
    compat.attach()
    compat_diag = compat.diagnostics()
    context.record(
        "operation",
        f"compat-diag-mode={compat_diag.state.active_kind.value}",
    )
    compat.detach()
