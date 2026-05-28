from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from fastapi import APIRouter, WebSocket

from asyncviz.utils.logging import get_logger

if TYPE_CHECKING:
    from asyncviz.dashboard.websocket.gateway import WebSocketGateway

logger = get_logger("dashboard.routes.websocket")

router = APIRouter()


def _resolve_gateway(websocket: WebSocket) -> WebSocketGateway | None:
    """Pull the gateway from the typed backend state, if present.

    Falls through to ``app.state.websocket_gateway`` for test apps that
    didn't construct the typed backend container.
    """
    backend = getattr(websocket.app.state, "backend", None)
    if backend is not None:
        return getattr(backend, "websocket_gateway", None)
    return getattr(websocket.app.state, "websocket_gateway", None)


@router.websocket("/ws")
async def runtime_stream(
    websocket: WebSocket,
    since_sequence: int = 0,
) -> None:
    """Open the runtime stream, optionally requesting reconnect replay.

    Delegates to :class:`WebSocketGateway` for the heavy lifting:

      * Accept the socket via :class:`ConnectionManager`.
      * Allocate a typed :class:`WebSocketSession`.
      * Run the replay-aware handshake (snapshot / replay / live-only).
      * Transition into live streaming; bridge broadcasts handle the rest.
      * Tear down + count metrics on disconnect.

    Query param ``since_sequence`` (default ``0``) is the resume cursor:
    the gateway consults the replay buffer for the gap if non-zero.
    """
    gateway = _resolve_gateway(websocket)
    if gateway is None:
        # Defensive fallback for app instances that pre-date the gateway
        # (e.g. some unit tests). Accept + close gracefully so the client
        # sees a stable failure mode.
        await websocket.accept()
        await websocket.close()
        return

    session = await gateway.connect(websocket)
    try:
        with contextlib.suppress(Exception):
            await gateway.handshake(session, since_sequence=since_sequence)
        await gateway.keep_alive(session, websocket)
    finally:
        await gateway.disconnect(session)
