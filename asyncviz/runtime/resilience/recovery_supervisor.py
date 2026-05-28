"""Recovery supervisor.

When a breaker trips, the supervisor coordinates the recovery
attempt sequence:

1. Wait ``policy.open_duration_s`` — handled by the breaker itself.
2. When the breaker transitions to ``half_open``, invoke the
   subsystem's registered recovery callback.
3. On success, the breaker closes; record the outcome.
4. On failure, increment the attempt counter; if it exceeds
   ``policy.max_recovery_attempts`` mark the subsystem as
   *abandoned* — no further attempts until an operator clears it.

The supervisor is **not** an autonomous loop — it is driven by the
manager. This keeps the timing model deterministic: a recovery
attempt only happens when the manager calls
``supervisor.attempt(...)``. Driving from a background task is left
to the bootstrap layer.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from asyncviz.runtime.resilience.failure_domain import FailureDomain
from asyncviz.runtime.resilience.models.breaker_state import BreakerState
from asyncviz.runtime.resilience.models.recovery_outcome import (
    RecoveryOutcome,
    RecoveryVerdict,
)

SyncRecoveryHook = Callable[[FailureDomain], bool]
AsyncRecoveryHook = Callable[[FailureDomain], Awaitable[bool]]


@dataclass(frozen=True, slots=True)
class SupervisorSnapshot:
    subsystem: str
    attempts: int
    successes: int
    failures: int
    last_verdict: RecoveryVerdict | None
    abandoned: bool


class RecoverySupervisor:
    """Per-subsystem recovery coordinator."""

    __slots__ = (
        "_abandoned",
        "_async_hook",
        "_attempts",
        "_domain",
        "_failures",
        "_history",
        "_hook",
        "_last_verdict",
        "_lock",
        "_successes",
    )

    def __init__(self, domain: FailureDomain) -> None:
        self._domain = domain
        self._lock = threading.Lock()
        self._hook: SyncRecoveryHook | None = None
        self._async_hook: AsyncRecoveryHook | None = None
        self._attempts = 0
        self._successes = 0
        self._failures = 0
        self._abandoned = False
        self._last_verdict: RecoveryVerdict | None = None
        self._history: list[RecoveryOutcome] = []

    def register(self, hook: SyncRecoveryHook) -> None:
        with self._lock:
            self._hook = hook

    def register_async(self, hook: AsyncRecoveryHook) -> None:
        with self._lock:
            self._async_hook = hook

    def clear_hooks(self) -> None:
        with self._lock:
            self._hook = None
            self._async_hook = None

    def abandoned(self) -> bool:
        with self._lock:
            return self._abandoned

    def reset_abandoned(self) -> None:
        with self._lock:
            self._abandoned = False
            self._attempts = 0

    def attempt(self) -> RecoveryOutcome:
        """Run a synchronous recovery attempt.

        Returns the outcome; callers (the manager) inspect the
        verdict to decide whether to keep trying.
        """
        with self._lock:
            if self._abandoned:
                return self._record_outcome("abandoned", 0.0, detail="already abandoned")
            if self._domain.breaker.state == BreakerState.CLOSED:
                return self._record_outcome("skipped", 0.0, detail="breaker already closed")
            hook = self._hook
            if hook is None:
                return self._record_outcome(
                    "deferred",
                    0.0,
                    detail="no sync recovery hook registered",
                )
            self._attempts += 1
        return self._invoke_sync(hook)

    async def attempt_async(self) -> RecoveryOutcome:
        with self._lock:
            if self._abandoned:
                return self._record_outcome("abandoned", 0.0, detail="already abandoned")
            if self._domain.breaker.state == BreakerState.CLOSED:
                return self._record_outcome("skipped", 0.0, detail="breaker already closed")
            hook = self._async_hook
            sync_hook = self._hook
            if hook is None and sync_hook is None:
                return self._record_outcome(
                    "deferred",
                    0.0,
                    detail="no recovery hook registered",
                )
            self._attempts += 1
        if hook is None:
            assert sync_hook is not None
            return self._invoke_sync(sync_hook)
        return await self._invoke_async(hook)

    def history(self) -> tuple[RecoveryOutcome, ...]:
        with self._lock:
            return tuple(self._history)

    def snapshot(self) -> SupervisorSnapshot:
        with self._lock:
            return SupervisorSnapshot(
                subsystem=self._domain.name,
                attempts=self._attempts,
                successes=self._successes,
                failures=self._failures,
                last_verdict=self._last_verdict,
                abandoned=self._abandoned,
            )

    # ── internals ────────────────────────────────────────────────

    def _invoke_sync(self, hook: SyncRecoveryHook) -> RecoveryOutcome:
        start = time.monotonic()
        try:
            ok = bool(hook(self._domain))
        except Exception as exc:
            duration = time.monotonic() - start
            return self._finalize_outcome(False, duration, detail=str(exc)[:200])
        duration = time.monotonic() - start
        return self._finalize_outcome(ok, duration, detail="ok" if ok else "hook returned false")

    async def _invoke_async(self, hook: AsyncRecoveryHook) -> RecoveryOutcome:
        start = time.monotonic()
        try:
            ok = bool(await hook(self._domain))
        except Exception as exc:
            duration = time.monotonic() - start
            return self._finalize_outcome(False, duration, detail=str(exc)[:200])
        duration = time.monotonic() - start
        return self._finalize_outcome(ok, duration, detail="ok" if ok else "hook returned false")

    def _finalize_outcome(
        self,
        ok: bool,
        duration_s: float,
        *,
        detail: str,
    ) -> RecoveryOutcome:
        with self._lock:
            if ok:
                self._successes += 1
                # Slam the breaker closed to short-circuit any waiting
                # admission decisions — the hook says we're healthy.
                self._domain.breaker.force_close()
                return self._record_outcome("succeeded", duration_s, detail=detail)
            self._failures += 1
            if self._attempts >= self._domain.policy.max_recovery_attempts:
                self._abandoned = True
                return self._record_outcome("abandoned", duration_s, detail=detail)
            return self._record_outcome("failed", duration_s, detail=detail)

    def _record_outcome(
        self,
        verdict: RecoveryVerdict,
        duration_s: float,
        *,
        detail: str,
    ) -> RecoveryOutcome:
        outcome = RecoveryOutcome(
            subsystem=self._domain.name,
            attempt=self._attempts,
            verdict=verdict,
            duration_s=duration_s,
            detail=detail,
        )
        self._last_verdict = verdict
        self._history.append(outcome)
        if len(self._history) > 64:
            self._history.pop(0)
        return outcome
