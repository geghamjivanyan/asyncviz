"""Alternate-event-loop compatibility configuration.

The compatibility layer is deliberately opt-in: by default the
runtime detects the active loop, records its capabilities, and
proceeds without installing anything. Operators that want uvloop
acceleration set ``prefer_uvloop=True`` (or call
:meth:`LoopCompatibilityManager.install_uvloop`); the layer then
attempts an *atomic* installation + falls back to stock asyncio if
anything goes wrong.

Three presets cover the realistic range:

* :func:`default_config` — production-balanced. Detects + reports
  but does not install.
* :func:`prefer_uvloop_config` — install uvloop where available;
  fall back gracefully on platforms that lack it (Windows, PyPy,
  ``--no-uvloop`` environments).
* :func:`strict_asyncio_config` — explicitly disable uvloop. Used
  on platforms where determinism trumps throughput (the replay
  comparison harness).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

LoopPreference = Literal["auto", "uvloop", "asyncio"]
"""Operator-facing preference. ``auto`` defers to the runtime; the
other two pin the choice."""

DEFAULT_PROBE_TIMEOUT_S: Final[float] = 0.05
"""Maximum wall-clock cost of capability probing. Probing is one-shot
and cached; this guards against pathological introspection paths."""

DEFAULT_CLOCK_DRIFT_TOLERANCE_NS: Final[int] = 50_000_000
"""Max acceptable difference between :func:`time.monotonic_ns` and
``loop.time()`` (50ms). Above this we record a drift warning + the
replay bridge consults its own monotonic source."""

DEFAULT_TRACE_CAPACITY: Final[int] = 256


@dataclass(frozen=True, slots=True)
class LoopCompatConfig:
    """Immutable compatibility-layer configuration."""

    preference: LoopPreference = "auto"
    """``auto``/``uvloop``/``asyncio``. ``auto`` means the manager
    detects + reports but does not install."""

    install_on_attach: bool = False
    """When ``True`` + ``preference="uvloop"``, the manager tries to
    install uvloop the first time it attaches to a runtime."""

    probe_timeout_s: float = DEFAULT_PROBE_TIMEOUT_S
    clock_drift_tolerance_ns: int = DEFAULT_CLOCK_DRIFT_TOLERANCE_NS

    record_websocket_anomalies: bool = True
    """Toggle for the websocket cadence bridge — disable when the
    application does not stream over websockets."""

    record_scheduler_anomalies: bool = True
    """Toggle for the scheduler bridge — disable in latency-critical
    deployments where the bookkeeping cost is unacceptable."""

    fallback_on_install_failure: bool = True
    """When ``True``, an install error logs + records a metric but
    does not propagate. When ``False``, the install raises."""

    trace_capacity: int = DEFAULT_TRACE_CAPACITY


def default_config() -> LoopCompatConfig:
    """Production-balanced default — detect, report, do not install."""
    return LoopCompatConfig()


def prefer_uvloop_config() -> LoopCompatConfig:
    """Install uvloop where available."""
    return LoopCompatConfig(
        preference="uvloop",
        install_on_attach=True,
        fallback_on_install_failure=True,
    )


def strict_asyncio_config() -> LoopCompatConfig:
    """Explicitly disable uvloop — used by the replay comparison
    harness so determinism is guaranteed."""
    return LoopCompatConfig(
        preference="asyncio",
        install_on_attach=False,
        fallback_on_install_failure=False,
    )
