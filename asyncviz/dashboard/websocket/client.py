from __future__ import annotations

from dataclasses import dataclass

from fastapi import WebSocket

from asyncviz.dashboard.websocket.shutdown_filter import is_expected_websocket_close


@dataclass(slots=True)
class WebSocketClient:
    """Typed wrapper around a connected WebSocket.

    The ``ConnectionManager`` is the only thing that should construct or
    mutate these — routes interact with them through the manager.
    """

    id: str
    socket: WebSocket

    async def send_text(self, payload: str) -> None:
        await self.socket.send_text(payload)

    async def close(self, *, code: int = 1000) -> None:
        """Close the socket, tolerating peer-initiated close races.

        Starlette's ``socket.close()`` can raise across a small set of
        graceful-shutdown races:

        * ``RuntimeError`` — Starlette already finalized the close
          ("Cannot call ``send`` once a close message has been sent").
        * :class:`websockets.exceptions.ConnectionClosed{Error,OK}` —
          the underlying ``websockets`` library reports the close
          frame race ("sent 1000 (OK); no close frame received").
        * :class:`starlette.websockets.WebSocketDisconnect` — the
          framework saw the disconnect first and turned it into a
          structured exception.

        All three are normal shutdown artefacts — they mean the
        connection IS closed, just not on the path the caller
        expected. Real failures (transport errors, protocol bugs)
        are NOT in :func:`is_expected_websocket_close` and re-raise
        unchanged.
        """
        try:
            await self.socket.close(code=code)
        except BaseException as exc:
            if is_expected_websocket_close(exc):
                return
            raise
