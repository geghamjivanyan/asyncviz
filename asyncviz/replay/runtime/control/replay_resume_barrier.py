"""Awaitable barrier for resume requests.

Symmetric to :class:`PauseBarrier`. Resolves when the coordinator
observes the engine transition back to ``PLAYING``.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass


class ResumeBarrierTimeoutError(TimeoutError):
    """Raised when ``ResumeBarrier.wait(timeout=...)`` elapses."""


@dataclass(frozen=True, slots=True)
class ResumeBarrierResolution:
    """What the barrier resolved with."""

    request_id: int
    resumed_at_sequence: int
    resumed_at_monotonic_ns: int
    latency_ns: int


class ResumeBarrier:
    """Awaitable handle for one pending resume request."""

    __slots__ = ("_event", "_request_id", "_requested_at_ns", "_resolution")

    def __init__(self, request_id: int) -> None:
        self._request_id = request_id
        self._requested_at_ns = time.monotonic_ns()
        self._event = asyncio.Event()
        self._resolution: ResumeBarrierResolution | None = None

    @property
    def request_id(self) -> int:
        return self._request_id

    @property
    def resolved(self) -> bool:
        return self._event.is_set()

    @property
    def resolution(self) -> ResumeBarrierResolution | None:
        return self._resolution

    def resolve(
        self,
        *,
        resumed_at_sequence: int,
        resumed_at_monotonic_ns: int,
    ) -> ResumeBarrierResolution:
        if self._resolution is not None:
            return self._resolution
        latency_ns = max(0, time.monotonic_ns() - self._requested_at_ns)
        self._resolution = ResumeBarrierResolution(
            request_id=self._request_id,
            resumed_at_sequence=resumed_at_sequence,
            resumed_at_monotonic_ns=resumed_at_monotonic_ns,
            latency_ns=latency_ns,
        )
        self._event.set()
        return self._resolution

    async def wait(
        self,
        *,
        timeout: float | None = None,  # noqa: ASYNC109 — explicit API timeout
    ) -> ResumeBarrierResolution:
        if timeout is None:
            await self._event.wait()
        else:
            try:
                await asyncio.wait_for(self._event.wait(), timeout=timeout)
            except TimeoutError as exc:
                raise ResumeBarrierTimeoutError(
                    f"resume request {self._request_id} did not resolve within {timeout}s",
                ) from exc
        assert self._resolution is not None
        return self._resolution
