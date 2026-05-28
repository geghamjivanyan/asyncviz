"""Shutdown-window asyncio exception filter for websocket noise.

During clean dashboard / replay shutdown there are a handful of
inherent races inside the websocket stack:

* Our :class:`ConnectionManager` initiates ``socket.close()`` from
  one task while a route handler is still awaiting ``receive_text()``
  on the same socket.
* The underlying ``websockets`` library's internal transfer-data
  task may collect a :class:`websockets.exceptions.ConnectionClosedError`
  ("sent 1000 (OK); no close frame received") AFTER the consumer
  has stopped awaiting it.
* Starlette / uvicorn may finalize the close handshake post-cancel,
  reporting ``WebSocketDisconnect`` or transport-level
  ``ConnectionResetError`` on a task whose owner already returned.

In every case the runtime DID shut down cleanly — there's just an
exception on a background task whose only consumer was the
already-completed shutdown coroutine. Python's asyncio emits a
"Task exception was never retrieved" message at GC time and the
default exception handler writes it to stderr as a noisy traceback.

This module narrows the noise without hiding real bugs:

* :func:`is_expected_websocket_close` is the single source of truth
  for "expected during graceful shutdown" classification. Anything
  outside that set bubbles up to the loop's previous (default)
  exception handler unchanged.

* :func:`install_shutdown_exception_filter` is a context manager
  that swaps the loop's exception handler for the duration of the
  shutdown window. On exit, the original handler is restored — so
  any new exception during normal operation logs at its full
  verbosity, exactly as before.

The filter is invoked from :class:`RuntimeShutdownCoordinator` so
the install window matches the canonical shutdown phase. Tests can
construct it directly to assert classification behavior.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Iterator
from typing import Any

from asyncviz.utils.logging import get_logger

logger = get_logger("dashboard.websocket.shutdown_filter")


# ── Expected-close classification ────────────────────────────────────────


# Module names whose exceptions we treat as "expected close" without
# importing them at module load. ``websockets`` is the wire library
# uvicorn delegates to; importing it lazily keeps this module
# dependency-light for tests that stub out the websocket stack.
_EXPECTED_EXCEPTION_TYPES: tuple[str, ...] = (
    "websockets.exceptions.ConnectionClosed",
    "websockets.exceptions.ConnectionClosedOK",
    "websockets.exceptions.ConnectionClosedError",
    "starlette.websockets.WebSocketDisconnect",
    "fastapi.websockets.WebSocketDisconnect",  # re-export shim
)

#: Substring matches in exception ``str`` form that signal an expected
#: close. Used only when the type-name check doesn't match — for
#: ``RuntimeError`` from Starlette / wrapped close exceptions / OS
#: errors that surface after the framework already finalized teardown.
_EXPECTED_MESSAGE_SUBSTRINGS: tuple[str, ...] = (
    # websockets-library close-frame races.
    "sent 1000 (OK); no close frame received",
    "received 1000 (OK)",
    # Starlette ASGI re-close / re-send race: a route handler exited
    # and Starlette finalized the close; our ``disconnect_all`` then
    # tries to close again and the ASGI layer raises a RuntimeError
    # with one of these phrases.
    "Unexpected ASGI message 'websocket.close'",
    "Unexpected ASGI message 'websocket.send'",
    "after sending 'websocket.close'",
    "after sending 'websocket.disconnect'",
    "Cannot call \"send\" once a close message has been sent",
    "WebSocket is not connected",
    # Generic disconnect markers.
    "websocket disconnect",
)


def is_expected_websocket_close(exc: BaseException | None) -> bool:
    """Return ``True`` when ``exc`` is a known graceful-close artefact.

    Three signals, any one of which is sufficient:

    1. ``CancelledError`` — always an expected shutdown artefact
       when seen on a background task during the shutdown window.
    2. Exception type qualname is in :data:`_EXPECTED_EXCEPTION_TYPES`.
    3. The string form contains a known graceful-close marker
       (websockets' close-frame text). Catches cases where the
       exception was wrapped in a different class.

    Anything else returns ``False`` and the loop's default exception
    handler runs.
    """
    if exc is None:
        return False
    if isinstance(exc, asyncio.CancelledError):
        return True
    # Build the fully-qualified type name and walk the MRO so subclasses
    # of the listed types match too without forcing an import.
    for cls in type(exc).__mro__:
        qualname = f"{cls.__module__}.{cls.__qualname__}"
        if qualname in _EXPECTED_EXCEPTION_TYPES:
            return True
    text = str(exc)
    if not text:
        return False
    for marker in _EXPECTED_MESSAGE_SUBSTRINGS:
        if marker in text:
            return True
    return False


# ── Loop exception handler ───────────────────────────────────────────────


class WebSocketShutdownExceptionFilter:
    """Loop-level asyncio exception handler used during shutdown.

    Installed via :func:`install_shutdown_exception_filter`. When the
    asyncio loop reports an unhandled exception (from
    ``Task.__del__``, ``Future.__del__``, ``call_soon`` callbacks,
    etc.), this handler:

    * Routes recognized expected-close noise to DEBUG with a single
      one-line summary — useful for diagnostics, invisible at the
      default INFO level.
    * Defers everything else to the previously-installed handler (or
      the loop default).

    Counters expose how many exceptions were swallowed vs. forwarded
    so a regression that suddenly hides real bugs is observable.
    """

    __slots__ = ("_forwarded", "_logger", "_previous_handler", "_suppressed")

    def __init__(
        self,
        *,
        previous_handler: Any = None,
        logger_override: logging.Logger | None = None,
    ) -> None:
        self._previous_handler = previous_handler
        self._logger = logger_override or logger
        self._suppressed = 0
        self._forwarded = 0

    @property
    def suppressed(self) -> int:
        return self._suppressed

    @property
    def forwarded(self) -> int:
        return self._forwarded

    def __call__(
        self,
        loop: asyncio.AbstractEventLoop,
        context: dict[str, Any],
    ) -> None:
        if self._classify_as_expected(context):
            self._suppressed += 1
            self._logger.debug(
                "suppressed expected ws-close noise: %s",
                context.get("message") or _summarize_exception(context.get("exception")),
            )
            return
        self._forwarded += 1
        if self._previous_handler is not None:
            self._previous_handler(loop, context)
        else:
            loop.default_exception_handler(context)

    def _classify_as_expected(self, context: dict[str, Any]) -> bool:
        # asyncio populates ``exception`` directly on most paths; the
        # "Task exception was never retrieved" path carries the
        # exception via the ``task`` / ``future`` slot instead, so check
        # both.
        candidate = context.get("exception")
        if is_expected_websocket_close(candidate):
            return True
        for key in ("task", "future"):
            fut = context.get(key)
            if fut is None:
                continue
            with contextlib.suppress(Exception):
                exc = fut.exception() if hasattr(fut, "exception") else None
                if is_expected_websocket_close(exc):
                    return True
        return False


def _summarize_exception(exc: BaseException | None) -> str:
    if exc is None:
        return "<no exception>"
    return f"{type(exc).__qualname__}: {exc}"


@contextlib.contextmanager
def install_shutdown_exception_filter(
    *,
    loop: asyncio.AbstractEventLoop | None = None,
    logger_override: logging.Logger | None = None,
) -> Iterator[WebSocketShutdownExceptionFilter]:
    """Install the shutdown filter on the current loop.

    Usage::

        async def shutdown(...):
            with install_shutdown_exception_filter() as flt:
                await stop_services()
            logger.debug("shutdown filter suppressed=%s forwarded=%s",
                         flt.suppressed, flt.forwarded)

    The filter is scoped — outside the ``with`` block the loop's
    previous exception handler is restored. If ``loop`` is omitted
    the currently-running loop is used; ``RuntimeError`` propagates if
    there isn't one (the caller must be on a loop).
    """
    active_loop = loop or asyncio.get_event_loop()
    previous = active_loop.get_exception_handler()
    filter_handler = WebSocketShutdownExceptionFilter(
        previous_handler=previous,
        logger_override=logger_override,
    )
    active_loop.set_exception_handler(filter_handler)
    try:
        yield filter_handler
    finally:
        active_loop.set_exception_handler(previous)
