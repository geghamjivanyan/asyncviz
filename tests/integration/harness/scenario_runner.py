"""Bounded scenario execution helpers.

Scenarios are async callables that take an :class:`IntegrationContext`
and run end-to-end. The helpers here wrap that call in a wall-clock
budget guard + return the same context the scenario mutated, so the
runner can aggregate signals into an :class:`IntegrationOutcome`.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable

from tests.integration.harness.scenario_context import IntegrationContext

ScenarioCallable = Callable[[IntegrationContext], Awaitable[None]]


async def run_scenario_async(
    scenario: ScenarioCallable,
    context: IntegrationContext,
) -> tuple[IntegrationContext, float, bool, str]:
    """Execute ``scenario(context)`` with a budget guard.

    Returns ``(context, duration_s, errored, error_detail)``.
    """
    start = time.monotonic()
    errored = False
    detail = ""
    try:
        await asyncio.wait_for(scenario(context), context.config.scenario_budget_s)
    except TimeoutError:
        errored = True
        detail = f"scenario budget {context.config.scenario_budget_s}s exceeded"
    except Exception as exc:
        errored = True
        detail = f"{type(exc).__name__}: {exc}"
    return context, time.monotonic() - start, errored, detail
