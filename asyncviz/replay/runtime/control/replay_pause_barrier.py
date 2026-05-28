"""Awaitable barrier that fires when the engine actually pauses.

The use case: a caller asks for pause-at-sequence and wants to
``await`` until the engine reaches that point and stops. Rather
than polling the state holder, the caller gets back a
:class:`PauseBarrier` whose ``wait()`` resolves once the
coordinator has observed the transition to ``PAUSED``.

Each barrier corresponds to one :class:`PauseRequest` (matched by
``request_id``). Multiple in-flight requests get their own
barriers; the coordinator fires the right one when the engine
acknowledges.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass


class PauseBarrierTimeoutError(TimeoutError):
    """Raised when ``PauseBarrier.wait(timeout=...)`` elapses."""


@dataclass(frozen=True, slots=True)
class PauseBarrierResolution:
    """What the barrier resolved with."""

    request_id: int
    paused_at_sequence: int
    paused_at_monotonic_ns: int
    latency_ns: int


class PauseBarrier:
    """Awaitable handle for one pending pause request."""

    __slots__ = ("_event", "_request_id", "_requested_at_ns", "_resolution")

    def __init__(self, request_id: int) -> None:
        self._request_id = request_id
        self._requested_at_ns = time.monotonic_ns()
        self._event = asyncio.Event()
        self._resolution: PauseBarrierResolution | None = None

    @property
    def request_id(self) -> int:
        return self._request_id

    @property
    def resolved(self) -> bool:
        return self._event.is_set()

    @property
    def resolution(self) -> PauseBarrierResolution | None:
        return self._resolution

    def resolve(
        self, *, paused_at_sequence: int, paused_at_monotonic_ns: int,
    ) -> PauseBarrierResolution:
        """Coordinator-only — fires the barrier."""
        if self._resolution is not None:
            return self._resolution
        latency_ns = max(0, time.monotonic_ns() - self._requested_at_ns)
        self._resolution = PauseBarrierResolution(
            request_id=self._request_id,
            paused_at_sequence=paused_at_sequence,
            paused_at_monotonic_ns=paused_at_monotonic_ns,
            latency_ns=latency_ns,
        )
        self._event.set()
        return self._resolution

    async def wait(
        self,
        *,
        timeout: float | None = None,  # noqa: ASYNC109 — explicit API timeout
    ) -> PauseBarrierResolution:
        """Suspend until the barrier fires or ``timeout`` elapses."""
        if timeout is None:
            await self._event.wait()
        else:
            try:
                await asyncio.wait_for(self._event.wait(), timeout=timeout)
            except TimeoutError as exc:
                raise PauseBarrierTimeoutError(
                    f"pause request {self._request_id} did not resolve within {timeout}s",
                ) from exc
        assert self._resolution is not None  # set by resolve()
        return self._resolution
