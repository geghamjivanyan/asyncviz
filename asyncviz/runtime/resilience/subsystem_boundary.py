"""Context-manager wrapper subsystem code uses to opt into isolation.

The boundary is the *only* place subsystems should swallow
exceptions. Wrapping a block in ``with manager.boundary("replay"):``
gives the subsystem:

* automatic classification of any raised exception,
* automatic breaker bookkeeping (success on clean exit, failure
  otherwise),
* explicit payload-quarantine semantics via ``payload_kind=``,
* graceful short-circuit when the breaker is open — either by
  setting ``admitted=False`` (the body still runs but exceptions
  are silently absorbed) or by raising
  :class:`SubsystemUnavailable` from ``__enter__`` for callers that
  want explicit "subsystem down" handling,
* deterministic + replay-safe behavior: identical inputs produce
  identical breaker state transitions.

Two flavors are provided:

* :class:`SubsystemBoundary` — synchronous context manager.
* :class:`AsyncSubsystemBoundary` — async context manager.

Both share the same admission + bookkeeping logic; only the
``__aenter__``/``__aexit__`` plumbing differs.

Behavior matrix:

+----------------+--------------------+---------------------------+
| breaker state  | swallow_unavailable| outcome                   |
+----------------+--------------------+---------------------------+
| closed         | n/a                | body runs admitted        |
| open           | True (default)     | ``__enter__`` returns,    |
|                |                    | ``admitted=False`` — the  |
|                |                    | body runs but any raised  |
|                |                    | retryable exception is    |
|                |                    | silently absorbed.        |
| open           | False              | ``__enter__`` raises      |
|                |                    | :class:`SubsystemUnavail- |
|                |                    | able` so the outer loop   |
|                |                    | can exit.                 |
+----------------+--------------------+---------------------------+
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from contextlib import AbstractAsyncContextManager, AbstractContextManager
from types import TracebackType

from asyncviz.runtime.resilience.failure_classifier import classify_exception
from asyncviz.runtime.resilience.failure_domain import FailureDomain
from asyncviz.runtime.resilience.models.failure_event import FailureEvent
from asyncviz.runtime.resilience.models.failure_kind import (
    DO_NOT_RETRY,
    FailureKind,
)


class SubsystemUnavailable(Exception):
    """Raised from ``__enter__`` when ``swallow_unavailable=False``
    and the breaker is open."""

    def __init__(self, subsystem: str, *, detail: str = "") -> None:
        super().__init__(
            f"subsystem {subsystem!r} unavailable: {detail or 'breaker is open'}",
        )
        self.subsystem = subsystem
        self.detail = detail


class _BoundaryCore:
    """Common admission + bookkeeping for both sync + async."""

    __slots__ = (
        "_admitted",
        "_domain",
        "_on_failure",
        "_payload_kind",
        "_suppress",
        "_swallow_unavailable",
    )

    def __init__(
        self,
        domain: FailureDomain,
        *,
        payload_kind: str,
        suppress: bool,
        on_failure: object,
        swallow_unavailable: bool,
    ) -> None:
        self._domain = domain
        self._payload_kind = payload_kind
        self._suppress = suppress
        self._admitted = False
        self._on_failure = on_failure
        self._swallow_unavailable = swallow_unavailable

    def _admit(self) -> None:
        now_ns = time.monotonic_ns()
        admitted = self._domain.allow_request(
            payload_kind=self._payload_kind, now_ns=now_ns,
        )
        self._admitted = admitted
        if not admitted and not self._swallow_unavailable:
            raise SubsystemUnavailable(self._domain.name)

    def _handle_exit(
        self,
        exc: BaseException | None,
    ) -> bool:
        if exc is None:
            if self._admitted:
                self._domain.record_success()
            return False
        kind = classify_exception(exc)
        if (
            kind == FailureKind.CANCELLED
            and not self._domain.policy.treat_cancelled_as_failure
        ):
            # Cancellation is structural — don't penalize the
            # breaker. Propagate the exception.
            return False
        event = FailureEvent(
            subsystem=self._domain.name,
            kind=kind,
            detail=f"{type(exc).__name__}: {str(exc)[:200]}",
            at_ns=time.monotonic_ns(),
            payload_kind=self._payload_kind,
            recoverable=kind not in DO_NOT_RETRY,
        )
        if self._admitted:
            # Normal path — penalize the breaker.
            self._domain.record_failure(event)
        # The ``on_failure`` hook fires for *every* failure observed
        # at the boundary, regardless of admission state. This is
        # what makes data-loss bookkeeping reliable: even calls that
        # ran while the breaker was open still trigger the recorder/
        # websocket adapters' note hooks.
        if self._on_failure is not None:
            with contextlib.suppress(Exception):
                self._on_failure(event)  # type: ignore[operator]
        return bool(self._suppress and kind not in DO_NOT_RETRY)


class SubsystemBoundary(AbstractContextManager["SubsystemBoundary"], _BoundaryCore):
    """Synchronous boundary context manager."""

    __slots__ = ()

    def __enter__(self) -> SubsystemBoundary:
        self._admit()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        return self._handle_exit(exc)

    @property
    def admitted(self) -> bool:
        return self._admitted


class AsyncSubsystemBoundary(AbstractAsyncContextManager["AsyncSubsystemBoundary"], _BoundaryCore):
    """Async boundary context manager."""

    __slots__ = ()

    async def __aenter__(self) -> AsyncSubsystemBoundary:
        self._admit()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        # ``__aexit__`` returning ``True`` for ``CancelledError``
        # would swallow the cancellation, which is *never* what we
        # want. The base class already returns ``False`` for
        # CancelledError; the explicit guard keeps the intent visible.
        if isinstance(exc, asyncio.CancelledError):
            self._handle_exit(exc)
            return False
        return self._handle_exit(exc)

    @property
    def admitted(self) -> bool:
        return self._admitted
