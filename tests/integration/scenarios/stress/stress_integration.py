"""Stress + integration cross-validation.

Runs the stress runner with a tiny lean config inside an integration
scenario so the runtime + stress layers compose cleanly.
"""

from __future__ import annotations

import asyncviz.stress as stress  # type: ignore[import-not-found]
from tests.integration.harness.scenario_context import IntegrationContext


async def run_stress_integration(context: IntegrationContext) -> None:
    cfg = stress.lean_config()
    runner = stress.StressRunner(config=cfg)
    outcomes = await runner.run(
        stress.StressRunInputs(
            only=("synthetic.baseline", "task.creation.10k", "render.flood"),
        ),
    )
    for outcome in outcomes:
        if outcome.verdict in ("passed", "warned"):
            context.record(
                "operation",
                f"stress:{outcome.spec.name}",
                value=float(outcome.operations_completed),
            )
        else:
            context.record(
                "failure",
                f"stress:{outcome.spec.name}:{outcome.verdict}",
            )
