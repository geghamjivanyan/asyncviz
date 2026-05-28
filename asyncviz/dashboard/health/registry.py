"""Pluggable health-probe registry.

Probes are functions, not classes — registering one is just naming
it and dropping it on the registry. Order is preserved (insertion
order), so consumers can rely on deterministic check ordering for the
diagnostics surface.

The registry runs every probe under a try/except so a misbehaving
probe doesn't take down the whole evaluation; a raise turns into a
synthetic ``UNAVAILABLE`` :class:`HealthCheckResult` with the
exception text inlined.
"""

from __future__ import annotations

import threading
from time import monotonic_ns
from typing import TYPE_CHECKING

from asyncviz.dashboard.health.checks import (
    CheckSeverity,
    HealthCheckResult,
    HealthProbe,
)
from asyncviz.dashboard.health.exceptions import DuplicateProbeError
from asyncviz.dashboard.health.status import HealthStatus
from asyncviz.utils.logging import get_logger

if TYPE_CHECKING:
    from asyncviz.dashboard.state.backend import BackendAppState

logger = get_logger("dashboard.health.registry")


class HealthCheckRegistry:
    """Holds probes + runs them in insertion order.

    Thread-safe registration + iteration. The execution loop is
    inherently sequential — health checks are cheap and the lock-free
    fast path isn't worth chasing here.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._probes: dict[str, HealthProbe] = {}

    def register(self, name: str, probe: HealthProbe) -> None:
        """Add a probe. Raises if ``name`` is already registered."""
        with self._lock:
            if name in self._probes:
                raise DuplicateProbeError(f"probe {name!r} already registered")
            self._probes[name] = probe

    def unregister(self, name: str) -> bool:
        with self._lock:
            return self._probes.pop(name, None) is not None

    def replace(self, name: str, probe: HealthProbe) -> None:
        """Idempotent replacement — for swapping a probe in tests."""
        with self._lock:
            self._probes[name] = probe

    def names(self) -> list[str]:
        with self._lock:
            return list(self._probes.keys())

    def __len__(self) -> int:
        with self._lock:
            return len(self._probes)

    def __contains__(self, name: str) -> bool:
        with self._lock:
            return name in self._probes

    def run(
        self,
        state: BackendAppState,
        *,
        names: list[str] | None = None,
    ) -> tuple[list[HealthCheckResult], int]:
        """Execute every (or a filtered subset of) probes and return their results.

        Returns ``(results, probe_failures)``. ``probe_failures`` counts
        probes that raised — they appear in ``results`` as
        ``UNAVAILABLE`` entries so the caller never has to handle a
        partial result list.

        Each probe's latency is measured *here* — probe authors don't
        need to time themselves.
        """
        with self._lock:
            selected: list[tuple[str, HealthProbe]] = (
                [(name, self._probes[name]) for name in names if name in self._probes]
                if names is not None
                else list(self._probes.items())
            )
        results: list[HealthCheckResult] = []
        failures = 0
        for name, probe in selected:
            started_ns = monotonic_ns()
            try:
                result = probe(state)
            except Exception as exc:
                failures += 1
                logger.warning("health probe %r raised: %s", name, exc)
                duration_ns = monotonic_ns() - started_ns
                results.append(
                    HealthCheckResult(
                        name=name,
                        status=HealthStatus.UNAVAILABLE,
                        severity=CheckSeverity.CRITICAL,
                        message=f"probe raised: {exc}",
                        latency_ns=duration_ns,
                        details={"exception_type": type(exc).__name__},
                    )
                )
                continue
            duration_ns = monotonic_ns() - started_ns
            # Probes don't measure their own latency — stamp it here.
            results.append(
                HealthCheckResult(
                    name=result.name,
                    status=result.status,
                    severity=result.severity,
                    message=result.message,
                    latency_ns=duration_ns,
                    details=result.details,
                )
            )
        return results, failures
