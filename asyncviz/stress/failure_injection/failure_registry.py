"""Deterministic failure-injection registry.

Storms register named fault sites (``websocket.send``,
``reducer.apply``, ``serializer.encode``, …) and the registry
decides whether each call should raise. Determinism is achieved by
seeding a :class:`DeterministicRng` from the configured seed + the
fault name — so the *same* set of calls fail across replays, but
different fault sites don't share fate.

The registry never mutates global state. Scenarios construct one,
use it for their duration, and discard it.
"""

from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass

from asyncviz.stress.stress_configuration import FailureInjectionConfig
from asyncviz.stress.stress_observability import get_stress_metrics
from asyncviz.stress.stress_tracing import record_stress_trace
from asyncviz.stress.utils.deterministic_rng import DeterministicRng


class StressInjectedFailure(Exception):
    """Raised by the registry when a fault site fires."""


@dataclass(frozen=True, slots=True)
class FailureSiteStats:
    name: str
    triggers: int
    invocations: int


class FailureInjectionRegistry:
    """Bounded, deterministic fault-injection coordinator."""

    __slots__ = ("_config", "_lock", "_rngs", "_sites")

    def __init__(self, config: FailureInjectionConfig) -> None:
        self._config = config
        self._sites: dict[str, dict[str, int]] = {}
        self._rngs: dict[str, DeterministicRng] = {}
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    def is_site_enabled(self, site: str) -> bool:
        if not self._config.enabled:
            return False
        mapping = {
            "websocket.disconnect": self._config.websocket_disconnects,
            "reducer.exception": self._config.reducer_exceptions,
            "replay.corruption": self._config.replay_corruption,
            "serializer.failure": self._config.serialization_failures,
            "queue.saturation": self._config.queue_saturation,
            "topology.explosion": self._config.topology_explosions,
        }
        return mapping.get(site, True)

    def maybe_inject(self, site: str, *, detail: str = "") -> bool:
        """Decide deterministically whether to fire the fault.

        Returns ``True`` when the fault fires. Callers either raise
        :class:`StressInjectedFailure` themselves or call
        :meth:`raise_if_triggered`.
        """
        with self._lock:
            stats = self._sites.setdefault(site, {"invocations": 0, "triggers": 0})
            stats["invocations"] += 1
            if not self.is_site_enabled(site):
                return False
            rng = self._rngs.get(site)
            if rng is None:
                rng = DeterministicRng(_derive_seed(self._config.seed, site))
                self._rngs[site] = rng
            fired = rng.coin(self._config.injection_rate)
            if fired:
                stats["triggers"] += 1
                get_stress_metrics().record_failure_injection()
                record_stress_trace("failure-injected", f"{site}: {detail}")
            return fired

    def raise_if_triggered(self, site: str, *, detail: str = "") -> None:
        """Convenience: maybe-inject + raise. Common call-site shape."""
        if self.maybe_inject(site, detail=detail):
            raise StressInjectedFailure(f"injected fault at {site}: {detail}")

    def stats(self) -> tuple[FailureSiteStats, ...]:
        with self._lock:
            return tuple(
                FailureSiteStats(
                    name=name,
                    triggers=stats["triggers"],
                    invocations=stats["invocations"],
                )
                for name, stats in sorted(self._sites.items())
            )

    def reset(self) -> None:
        with self._lock:
            self._sites.clear()
            self._rngs.clear()


def _derive_seed(base_seed: int, site: str) -> int:
    """Derive a per-site seed from ``(base_seed, site)``.

    Hashing is used to give distinct sites independent streams. We
    intentionally use ``hashlib.blake2b`` (cheap, available
    everywhere) instead of :func:`hash` (PYTHONHASHSEED-randomized).
    """
    payload = f"{base_seed}::{site}".encode()
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return int.from_bytes(digest, "big")
