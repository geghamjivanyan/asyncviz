from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

import uvicorn

from asyncviz.bootstrap.services import ServiceContainer
from asyncviz.config import AsyncVizConfig
from asyncviz.utils.logging import get_logger

logger = get_logger("bootstrap.runtime")

_DEFAULT_SHUTDOWN_TIMEOUT = 5.0


@dataclass(slots=True)
class AsyncVizRuntime:
    """A single live AsyncViz runtime.

    Returned by :func:`asyncviz.start`. Holds the config it was launched with,
    the ServiceContainer (app + state + ws manager), and the background
    uvicorn server + thread. Treat this object as read-only from user code —
    use :func:`asyncviz.stop` rather than mutating ``server`` directly.
    """

    config: AsyncVizConfig
    services: ServiceContainer
    started_at: float
    server: uvicorn.Server = field(repr=False)
    thread: threading.Thread = field(repr=False)

    @property
    def dashboard_url(self) -> str:
        return self.config.dashboard_url

    @property
    def is_running(self) -> bool:
        if self.server is None or self.thread is None:
            return False
        if self.server.should_exit:
            return False
        return self.thread.is_alive()

    @property
    def uptime_seconds(self) -> float:
        return max(0.0, time.time() - self.started_at)

    def shutdown(self, timeout: float = _DEFAULT_SHUTDOWN_TIMEOUT) -> None:
        if self.server is not None:
            self.server.should_exit = True
        if self.thread is not None:
            self.thread.join(timeout=timeout)
            if self.thread.is_alive():
                logger.warning("AsyncViz server thread did not exit within %.1fs", timeout)

    def wait(self) -> None:
        if self.thread is not None:
            self.thread.join()
