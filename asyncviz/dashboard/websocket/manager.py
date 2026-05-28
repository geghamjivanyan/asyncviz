from __future__ import annotations

import asyncio
import uuid

from fastapi import WebSocket

from asyncviz.dashboard.websocket.client import WebSocketClient
from asyncviz.dashboard.websocket.protocol import Envelope
from asyncviz.dashboard.websocket.shutdown_filter import is_expected_websocket_close
from asyncviz.utils.logging import get_logger

logger = get_logger("dashboard.websocket.manager")


class ConnectionManager:
    """Tracks connected dashboard clients and broadcasts envelopes to them.

    The manager owns the only mutable client registry; routes receive it via
    FastAPI dependencies. ``broadcast`` is best-effort — clients that fail
    a send are evicted so the next round runs against a clean set.
    """

    def __init__(self) -> None:
        self._clients: dict[str, WebSocketClient] = {}
        self._lock = asyncio.Lock()

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def connect(self, websocket: WebSocket) -> WebSocketClient:
        await websocket.accept()
        client = WebSocketClient(id=uuid.uuid4().hex, socket=websocket)
        async with self._lock:
            self._clients[client.id] = client
        logger.debug("client %s connected (count=%d)", client.id, self.client_count)
        return client

    async def disconnect(self, client_id: str) -> None:
        async with self._lock:
            client = self._clients.pop(client_id, None)
        if client is None:
            return
        try:
            await client.close()
        except BaseException as exc:
            if is_expected_websocket_close(exc):
                logger.debug(
                    "client %s expected-close artefact: %s", client_id, exc,
                )
            else:
                logger.warning("client %s raised during close: %s", client_id, exc)
        logger.debug("client %s disconnected (count=%d)", client_id, self.client_count)

    async def disconnect_all(self) -> None:
        """Close every connected client, tolerating per-client races.

        A failure on one client must NOT short-circuit the loop —
        every other client still needs to be closed during shutdown.
        Expected close artefacts (peer already gone away, close
        handshake racing with our cancel) are logged at DEBUG via
        :func:`is_expected_websocket_close`; anything else surfaces at
        WARNING so a real teardown bug stays visible.
        """
        async with self._lock:
            clients = list(self._clients.values())
            self._clients.clear()
        for client in clients:
            try:
                await client.close()
            except BaseException as exc:
                if is_expected_websocket_close(exc):
                    logger.debug(
                        "client %s expected-close artefact during shutdown: %s",
                        client.id,
                        exc,
                    )
                else:
                    logger.warning(
                        "client %s raised during shutdown close: %s",
                        client.id,
                        exc,
                    )
        if clients:
            logger.debug("disconnected %d clients on shutdown", len(clients))

    async def broadcast(self, envelope: Envelope) -> int:
        """Send ``envelope`` to every connected client. Returns the count delivered."""
        text = envelope.model_dump_json()
        async with self._lock:
            clients = list(self._clients.values())
        if not clients:
            return 0

        # Internal fanout — suppress gather instrumentation so the
        # broadcast loop doesn't push ``asyncio.gather.*`` events back
        # through the bus on every tick.
        from asyncviz.instrumentation.gather import suppress_gather_instrumentation

        with suppress_gather_instrumentation():
            results = await asyncio.gather(
                *(self._safe_send(client, text) for client in clients),
                return_exceptions=False,
            )
        delivered = sum(1 for ok in results if ok)
        dead = [client.id for client, ok in zip(clients, results, strict=True) if not ok]
        for cid in dead:
            await self.disconnect(cid)
        return delivered

    @staticmethod
    async def _safe_send(client: WebSocketClient, text: str) -> bool:
        try:
            await client.send_text(text)
        except Exception as exc:
            logger.debug("dropping client %s after send failure: %s", client.id, exc)
            return False
        return True
