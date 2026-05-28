"""End-to-end orchestration helpers.

The orchestrator wires three live AsyncViz subsystems together
inside a single test scenario:

* :class:`asyncviz.runtime.backpressure.EventBackpressureController`
* :class:`asyncviz.runtime.resilience.RuntimeFailureManager`
* :class:`asyncviz.runtime.compat.LoopCompatibilityManager`

Most scenarios don't need all three, so the orchestrator builds
them lazily + tears down deterministically.
"""

from tests.integration.orchestration.runtime_orchestrator import (
    RuntimeOrchestrator,
)
from tests.integration.orchestration.uvloop_matrix import (
    run_matrix,
)

__all__ = ["RuntimeOrchestrator", "run_matrix"]
