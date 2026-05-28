"""Run a scenario under both asyncio + uvloop.

Each arm runs in a *dedicated worker thread* with its own event
loop so the caller can already be inside an event loop. Nesting
``asyncio.run`` calls is illegal — using threads sidesteps the
problem cleanly.

Returns a two-tuple of contexts so the caller can diff signal
counters across loops.
"""

from __future__ import annotations

import asyncio
import contextlib
import threading
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from asyncviz.runtime.compat import (  # type: ignore[import-not-found]
    is_uvloop_available,
)

if TYPE_CHECKING:
    from tests.integration.harness.scenario_context import IntegrationContext

RunFn = Callable[[], Awaitable["IntegrationContext"]]


def run_matrix(
    factory: RunFn,
    *,
    include_uvloop: bool = True,
) -> tuple[IntegrationContext, IntegrationContext | None]:
    asyncio_ctx = _run_in_worker(factory, install_uvloop=False)
    if not include_uvloop or not is_uvloop_available():
        return asyncio_ctx, None
    uvloop_ctx = _run_in_worker(factory, install_uvloop=True)
    return asyncio_ctx, uvloop_ctx


def _run_in_worker(
    factory: RunFn,
    *,
    install_uvloop: bool,
) -> IntegrationContext:
    container: dict[str, object] = {}

    def _target() -> None:
        original_policy = None
        if install_uvloop:
            import uvloop  # type: ignore[import-not-found]

            with contextlib.suppress(Exception):
                original_policy = asyncio.get_event_loop_policy()
            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            container["context"] = loop.run_until_complete(factory())
        except Exception as exc:
            container["error"] = exc
        finally:
            loop.close()
            if install_uvloop and original_policy is not None:
                with contextlib.suppress(Exception):
                    asyncio.set_event_loop_policy(original_policy)

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join()
    if "error" in container:
        raise container["error"]  # type: ignore[misc]
    return container["context"]  # type: ignore[return-value]
