"""Overload → degradation → recovery cycle.

Pushes a synthetic event storm through the backpressure controller
and confirms the resilience manager picks up the corresponding
backpressure suggestion when one is wired in.
"""

from __future__ import annotations

from asyncviz.runtime.resilience import (  # type: ignore[import-not-found]
    RuntimeFailureManager,
)
from tests.integration.harness.scenario_context import IntegrationContext


async def run_overload_recovery(context: IntegrationContext) -> None:
    mgr = RuntimeFailureManager()
    suggestions: list[str] = []
    mgr.backpressure_bridge().subscribe(lambda s: suggestions.append(s.runtime_mode))

    # Storm the reducer until the breaker trips.
    for index in range(30):
        with mgr.boundary("reducer", payload_kind=f"r-{index}"):
            raise TimeoutError("reducer timeout")
    context.record("overload", f"mode={mgr.mode()}")

    mgr.register_recovery("reducer", lambda _domain: True)
    outcome = mgr.attempt_recovery("reducer")
    context.record(
        "operation",
        f"recovery={outcome.verdict}",
    )
    context.record(
        "custom",
        f"suggestion-history={suggestions}",
    )
