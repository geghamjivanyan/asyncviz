"""Tests for the websocket shutdown exception filter + the hardened
:class:`ConnectionManager` / :class:`WebSocketClient` close paths.

The filter is a polish-level shutdown-hygiene mechanism — it swallows
inherent graceful-close noise that the ``websockets`` library and
asyncio together emit during teardown, while leaving real failures
loud. These tests pin every classification the filter is supposed to
make, plus the per-client hardening that prevents one bad close from
short-circuiting :meth:`ConnectionManager.disconnect_all`.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import pytest

from asyncviz.dashboard.websocket.shutdown_filter import (
    WebSocketShutdownExceptionFilter,
    install_shutdown_exception_filter,
    is_expected_websocket_close,
)

# ── classification ───────────────────────────────────────────────────────


class _LocalConnectionClosedError(Exception):
    """Stand-in matching the qualname tracking ``is_expected_websocket_close``
    uses for ``websockets.exceptions.ConnectionClosedError`` so the
    test doesn't depend on the library being installed."""

    pass


# Set the qualname/module so the classifier sees a "match".
_LocalConnectionClosedError.__module__ = "websockets.exceptions"
_LocalConnectionClosedError.__qualname__ = "ConnectionClosedError"


class _LocalConnectionClosedOK(Exception):
    pass


_LocalConnectionClosedOK.__module__ = "websockets.exceptions"
_LocalConnectionClosedOK.__qualname__ = "ConnectionClosedOK"


class _LocalWebSocketDisconnect(Exception):
    pass


_LocalWebSocketDisconnect.__module__ = "starlette.websockets"
_LocalWebSocketDisconnect.__qualname__ = "WebSocketDisconnect"


def test_classifies_cancelled_error_as_expected() -> None:
    assert is_expected_websocket_close(asyncio.CancelledError()) is True


def test_classifies_known_websockets_exceptions() -> None:
    assert is_expected_websocket_close(_LocalConnectionClosedError()) is True
    assert is_expected_websocket_close(_LocalConnectionClosedOK()) is True


def test_classifies_websocket_disconnect_qualname() -> None:
    assert is_expected_websocket_close(_LocalWebSocketDisconnect()) is True


def test_classifies_close_frame_message_text_even_when_wrapped() -> None:
    # A library wrapping the original exception in a different type
    # but preserving the canonical close-frame string still counts.
    wrapped = RuntimeError("sent 1000 (OK); no close frame received")
    assert is_expected_websocket_close(wrapped) is True


def test_classifies_starlette_asgi_re_close_race() -> None:
    """Real symptom observed under stress + SIGINT: the route handler
    exits via WebSocketDisconnect (Starlette already sent the close);
    ``ConnectionManager.disconnect_all`` then calls close again and
    Starlette raises a RuntimeError with this exact phrasing. It IS
    a graceful-close artefact — the close did happen, just not on the
    code path our second close() expected.
    """
    msg = (
        "Unexpected ASGI message 'websocket.close', after sending "
        "'websocket.close' or response already completed."
    )
    assert is_expected_websocket_close(RuntimeError(msg)) is True


def test_classifies_starlette_re_send_after_close() -> None:
    msg = 'Cannot call "send" once a close message has been sent.'
    assert is_expected_websocket_close(RuntimeError(msg)) is True


def test_classifies_websocket_not_connected_runtimerror() -> None:
    msg = 'WebSocket is not connected. Need to call "accept" first.'
    assert is_expected_websocket_close(RuntimeError(msg)) is True


def test_does_not_classify_real_errors_as_expected() -> None:
    assert is_expected_websocket_close(ValueError("malformed envelope")) is False
    assert is_expected_websocket_close(KeyError("missing field")) is False
    assert is_expected_websocket_close(RuntimeError("unrelated failure")) is False
    assert is_expected_websocket_close(None) is False


def test_classifies_subclasses_of_known_types() -> None:
    class _MyCustomDisconnect(_LocalWebSocketDisconnect):
        pass

    assert is_expected_websocket_close(_MyCustomDisconnect()) is True


# ── filter handler behavior ──────────────────────────────────────────────


def _ctx(exc: BaseException | None = None, **extra: Any) -> dict[str, Any]:
    ctx: dict[str, Any] = {"message": "test", **extra}
    if exc is not None:
        ctx["exception"] = exc
    return ctx


@pytest.mark.asyncio
async def test_filter_swallows_expected_exception() -> None:
    forwarded: list[dict[str, Any]] = []

    def previous(loop: Any, context: dict[str, Any]) -> None:
        forwarded.append(context)

    flt = WebSocketShutdownExceptionFilter(previous_handler=previous)
    flt(asyncio.get_event_loop(), _ctx(_LocalConnectionClosedError()))
    flt(asyncio.get_event_loop(), _ctx(asyncio.CancelledError()))
    assert flt.suppressed == 2
    assert flt.forwarded == 0
    assert forwarded == []


@pytest.mark.asyncio
async def test_filter_forwards_real_errors_to_previous_handler() -> None:
    forwarded: list[dict[str, Any]] = []

    def previous(loop: Any, context: dict[str, Any]) -> None:
        forwarded.append(context)

    flt = WebSocketShutdownExceptionFilter(previous_handler=previous)
    flt(asyncio.get_event_loop(), _ctx(ValueError("real bug")))
    assert flt.suppressed == 0
    assert flt.forwarded == 1
    assert isinstance(forwarded[0]["exception"], ValueError)


@pytest.mark.asyncio
async def test_filter_handles_exception_via_task_slot() -> None:
    """The "Task exception was never retrieved" path carries the
    exception on the task itself, not in ``context['exception']``.
    """

    class _FakeTask:
        def __init__(self, exc: BaseException) -> None:
            self._exc = exc

        def exception(self) -> BaseException:
            return self._exc

    forwarded: list[dict[str, Any]] = []

    def previous(loop: Any, context: dict[str, Any]) -> None:
        forwarded.append(context)

    flt = WebSocketShutdownExceptionFilter(previous_handler=previous)
    flt(
        asyncio.get_event_loop(),
        {
            "message": "Task exception was never retrieved",
            "task": _FakeTask(_LocalConnectionClosedError()),
        },
    )
    assert flt.suppressed == 1
    assert flt.forwarded == 0
    assert forwarded == []


@pytest.mark.asyncio
async def test_filter_forwards_when_task_carries_unexpected_exception() -> None:
    class _FakeTask:
        def __init__(self, exc: BaseException) -> None:
            self._exc = exc

        def exception(self) -> BaseException:
            return self._exc

    forwarded: list[dict[str, Any]] = []

    def previous(loop: Any, context: dict[str, Any]) -> None:
        forwarded.append(context)

    flt = WebSocketShutdownExceptionFilter(previous_handler=previous)
    flt(
        asyncio.get_event_loop(),
        {"message": "Task exception was never retrieved", "task": _FakeTask(ValueError("oops"))},
    )
    assert flt.suppressed == 0
    assert flt.forwarded == 1


# ── context-manager install / uninstall ──────────────────────────────────


@pytest.mark.asyncio
async def test_install_shutdown_exception_filter_restores_previous_handler() -> None:
    loop = asyncio.get_running_loop()
    original_calls: list[dict[str, Any]] = []

    def original(loop_: Any, context: dict[str, Any]) -> None:
        original_calls.append(context)

    loop.set_exception_handler(original)

    with install_shutdown_exception_filter() as flt:
        loop.call_exception_handler(_ctx(_LocalConnectionClosedError()))
        loop.call_exception_handler(_ctx(ValueError("real")))
        assert flt.suppressed == 1
        assert flt.forwarded == 1
        # The forwarded one went to ``original``.
        assert len(original_calls) == 1

    # After the context, the original handler is back in place.
    assert loop.get_exception_handler() is original
    loop.set_exception_handler(None)


@pytest.mark.asyncio
async def test_filter_routes_swallowed_messages_to_debug_only() -> None:
    """Suppressed exceptions log at DEBUG so operators don't see them
    at the default INFO level. Forwarded ones bypass our logger
    entirely so the default formatting kicks in.
    """
    test_logger = logging.getLogger("test.ws_filter")
    test_logger.setLevel(logging.DEBUG)
    test_logger.propagate = False
    captured: list[logging.LogRecord] = []
    handler = logging.Handler()
    handler.emit = captured.append  # type: ignore[method-assign]
    test_logger.addHandler(handler)

    forwarded: list[dict[str, Any]] = []

    def previous(loop: Any, context: dict[str, Any]) -> None:
        forwarded.append(context)

    flt = WebSocketShutdownExceptionFilter(
        previous_handler=previous,
        logger_override=test_logger,
    )
    flt(asyncio.get_event_loop(), _ctx(_LocalConnectionClosedError("graceful")))
    debug_records = [r for r in captured if r.levelno == logging.DEBUG]
    assert len(debug_records) == 1
    assert "ws-close noise" in debug_records[0].getMessage()


# ── hardened manager close paths ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_manager_disconnect_all_continues_past_failing_client() -> None:
    """If one client.close() raises an UNEXPECTED exception the loop
    must still close the rest. The expected-close path is logged at
    DEBUG; the unexpected path at WARNING.
    """
    from asyncviz.dashboard.websocket.manager import ConnectionManager

    closed_ids: list[str] = []

    class _RaisingSocket:
        def __init__(self, *, exc: BaseException | None = None) -> None:
            self._exc = exc

        async def close(self, *, code: int = 1000) -> None:
            if self._exc is not None:
                raise self._exc

    manager = ConnectionManager()
    # Inject three synthetic clients without going through the real
    # WebSocket accept path — only ``close`` is exercised here.
    from asyncviz.dashboard.websocket.client import WebSocketClient

    good = WebSocketClient(id="good", socket=_RaisingSocket())  # type: ignore[arg-type]

    class _TrackingSocket(_RaisingSocket):
        def __init__(self, name: str) -> None:
            super().__init__()
            self.name = name

        async def close(self, *, code: int = 1000) -> None:
            closed_ids.append(self.name)

    good.socket = _TrackingSocket("good")  # type: ignore[assignment]
    bad = WebSocketClient(
        id="bad",
        socket=_RaisingSocket(exc=RuntimeError("not an expected close")),  # type: ignore[arg-type]
    )
    expected_close = WebSocketClient(
        id="expected-close",
        socket=_RaisingSocket(exc=_LocalConnectionClosedError()),  # type: ignore[arg-type]
    )
    # Insert directly into the registry.
    manager._clients[good.id] = good  # type: ignore[attr-defined]
    manager._clients[bad.id] = bad  # type: ignore[attr-defined]
    manager._clients[expected_close.id] = expected_close  # type: ignore[attr-defined]

    await manager.disconnect_all()
    # The good client's close ran.
    assert closed_ids == ["good"]
    # Every client was removed from the registry.
    assert manager.client_count == 0


@pytest.mark.asyncio
async def test_websocket_client_close_swallows_expected_close_only() -> None:
    """``WebSocketClient.close`` must let real failures through but
    swallow the graceful-close set."""
    from asyncviz.dashboard.websocket.client import WebSocketClient

    class _RaisingSocket:
        def __init__(self, exc: BaseException) -> None:
            self._exc = exc

        async def close(self, *, code: int = 1000) -> None:
            raise self._exc

    # Expected — should NOT raise.
    expected = WebSocketClient(
        id="x",
        socket=_RaisingSocket(_LocalConnectionClosedError()),  # type: ignore[arg-type]
    )
    await expected.close()

    # Unexpected — must propagate.
    bad = WebSocketClient(
        id="x",
        socket=_RaisingSocket(ValueError("real bug")),  # type: ignore[arg-type]
    )
    with pytest.raises(ValueError, match="real bug"):
        await bad.close()
