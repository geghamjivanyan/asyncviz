from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from asyncviz.config import AsyncVizConfig


class _BackgroundUvicornServer(uvicorn.Server):
    """A uvicorn server that does *not* install signal handlers.

    Uvicorn's default ``install_signal_handlers`` calls ``signal.signal``,
    which only works on the main thread. The embedded supervisor runs uvicorn
    in a background thread, so we suppress the install step entirely — the
    supervisor handles shutdown via ``server.should_exit``.
    """

    def install_signal_handlers(self) -> None:
        return


def build_server(app: FastAPI, config: AsyncVizConfig) -> uvicorn.Server:
    uv_config = uvicorn.Config(
        app=app,
        host=config.host,
        port=config.port,
        log_level="debug" if config.debug else "info",
        access_log=config.debug,
        lifespan="on",
    )
    return _BackgroundUvicornServer(uv_config)
