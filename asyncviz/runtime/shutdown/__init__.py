"""Canonical graceful shutdown system for AsyncViz.

Public surface:

* :class:`RuntimeShutdownCoordinator` — orchestrator that runs the
  full teardown sequence: websocket notification + drain, replay
  finalization, deterministic service stop, observability.
* :class:`ShutdownPhase` — canonical lifecycle states (``IDLE``,
  ``DRAINING``, ``FINALIZING``, ``STOPPING``, ``STOPPED``,
  ``FAILED``).
* :class:`ShutdownTimeouts` — per-step + total timeout policy.
* :class:`ShutdownReport` / :class:`PhaseTiming` — post-shutdown
  structured report.
* :class:`ShutdownMetrics` / :class:`ShutdownMetricsSnapshot` —
  process-lifetime counters.
* Pydantic wire models — :class:`ShutdownStatusResponse`,
  :class:`ShutdownReportPayload`, :class:`PhaseTimingPayload`,
  :class:`ShutdownMetricsResponse`,
  :const:`SHUTDOWN_PROTOCOL_VERSION`.
* exceptions — :class:`ShutdownError`,
  :class:`ShutdownAlreadyRunningError`, :class:`ShutdownTimeoutError`,
  :class:`ShutdownNotCompletedError`.
"""

from asyncviz.runtime.shutdown.coordinator import RuntimeShutdownCoordinator
from asyncviz.runtime.shutdown.exceptions import (
    ShutdownAlreadyRunningError,
    ShutdownError,
    ShutdownNotCompletedError,
    ShutdownTimeoutError,
)
from asyncviz.runtime.shutdown.metrics import (
    PhaseTiming,
    ShutdownMetrics,
    ShutdownMetricsSnapshot,
    ShutdownReport,
)
from asyncviz.runtime.shutdown.models import (
    SHUTDOWN_PROTOCOL_VERSION,
    PhaseTimingPayload,
    ShutdownMetricsResponse,
    ShutdownReportPayload,
    ShutdownStatusResponse,
)
from asyncviz.runtime.shutdown.status import (
    ShutdownPhase,
    is_in_progress,
    is_terminal,
    phase_index,
)
from asyncviz.runtime.shutdown.timeouts import ShutdownTimeouts

__all__ = [
    "SHUTDOWN_PROTOCOL_VERSION",
    "PhaseTiming",
    "PhaseTimingPayload",
    "RuntimeShutdownCoordinator",
    "ShutdownAlreadyRunningError",
    "ShutdownError",
    "ShutdownMetrics",
    "ShutdownMetricsResponse",
    "ShutdownMetricsSnapshot",
    "ShutdownNotCompletedError",
    "ShutdownPhase",
    "ShutdownReport",
    "ShutdownReportPayload",
    "ShutdownStatusResponse",
    "ShutdownTimeoutError",
    "ShutdownTimeouts",
    "is_in_progress",
    "is_terminal",
    "phase_index",
]
