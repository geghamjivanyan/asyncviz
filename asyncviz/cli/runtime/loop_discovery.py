"""User-loop discovery for the CLI bootstrap.

The dashboard server runs on its own daemon-thread event loop
(uvicorn). The lag-monitoring sampler — by construction — measures
the loop it is bound to. If we bound it to the uvicorn loop the
sampler would see the dashboard's traffic, not the user workload's
blocking calls. So we have to bind the sampler to the loop that
actually runs the user's coroutines.

This module owns the discovery side of that contract: install a hook
before ``runpy.run_path`` so the FIRST asyncio event loop created on
the main thread (i.e. the loop that ``asyncio.run(main())`` will use)
fires a one-shot callback. The callback hands the loop reference to
:meth:`EventLoopLagMonitor.bind_to_loop_threadsafe`, which starts the
sampler on that loop.

Implementation note: we install a delegating
:class:`asyncio.AbstractEventLoopPolicy` rather than replace the
policy outright. Any user-installed policy (uvloop's, gevent's,
trio-asyncio's) still works — its loop class is preserved; we only
intercept the moment of creation to capture the resulting loop
object.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable

from asyncviz.utils.logging import get_logger

logger = get_logger("cli.runtime.loop_discovery")


LoopCallback = Callable[[asyncio.AbstractEventLoop], None]


class _DelegatingLoopPolicy(asyncio.AbstractEventLoopPolicy):
    """Forwards every policy call to a wrapped policy, but intercepts
    :meth:`new_event_loop` to fire a one-shot capture callback.

    Only the first loop created on the **main thread** triggers the
    callback. Background-thread loops (e.g. the uvicorn server's loop
    if it's reconstructed mid-run) are ignored — the lag monitor's
    contract is specifically about the loop that runs user code.
    """

    def __init__(
        self,
        inner: asyncio.AbstractEventLoopPolicy,
        on_main_thread_loop: LoopCallback,
        main_thread_id: int,
    ) -> None:
        self._inner = inner
        self._on_main_thread_loop = on_main_thread_loop
        self._main_thread_id = main_thread_id
        self._fired = False
        self._fired_lock = threading.Lock()

    # ── delegating surface ───────────────────────────────────────────
    def get_event_loop(self) -> asyncio.AbstractEventLoop:
        return self._inner.get_event_loop()

    def set_event_loop(self, loop: asyncio.AbstractEventLoop | None) -> None:
        self._inner.set_event_loop(loop)

    def new_event_loop(self) -> asyncio.AbstractEventLoop:
        loop = self._inner.new_event_loop()
        if threading.get_ident() == self._main_thread_id:
            self._maybe_fire(loop)
        return loop

    # Forward the optional child-watcher methods so subclasses with
    # special unix handling (e.g. CPython's default policy) keep
    # working. These are deprecated in Python 3.14 but harmless to
    # delegate via dynamic dispatch — anything missing on a stripped
    # policy raises AttributeError exactly as it would without the
    # wrapper.
    def get_child_watcher(self):  # pragma: no cover — deprecated path
        return self._inner.get_child_watcher()  # type: ignore[attr-defined]

    def set_child_watcher(self, watcher):  # pragma: no cover — deprecated
        self._inner.set_child_watcher(watcher)  # type: ignore[attr-defined]

    # ── one-shot capture ─────────────────────────────────────────────
    def _maybe_fire(self, loop: asyncio.AbstractEventLoop) -> None:
        with self._fired_lock:
            if self._fired:
                return
            self._fired = True
        try:
            self._on_main_thread_loop(loop)
        except Exception:
            logger.exception("loop-discovery callback raised; ignoring")


class _LoopDiscoveryHandle:
    """Lifetime token for the policy override.

    Restores the previous policy on :meth:`uninstall`. Idempotent.
    """

    def __init__(
        self,
        previous_policy: asyncio.AbstractEventLoopPolicy,
        active_policy: _DelegatingLoopPolicy,
    ) -> None:
        self._previous = previous_policy
        self._active = active_policy
        self._uninstalled = False

    def uninstall(self) -> None:
        if self._uninstalled:
            return
        self._uninstalled = True
        try:
            asyncio.set_event_loop_policy(self._previous)
        except Exception:
            logger.exception("loop-discovery policy restore raised; ignoring")

    @property
    def fired(self) -> bool:
        """``True`` once the main-thread loop has been observed."""
        return self._active._fired  # pyright: ignore[reportPrivateUsage]


def install_main_thread_loop_discovery(
    on_main_thread_loop: LoopCallback,
) -> _LoopDiscoveryHandle:
    """Install a one-shot main-thread loop-creation hook.

    Returns a handle whose :meth:`uninstall` restores the previous
    policy. Safe to call from any thread, but the captured "main
    thread id" is the calling thread's id — call this from the
    process's main thread (which the CLI bootstrap entry is).

    The callback runs on whichever thread created the loop, which for
    ``asyncio.run`` is the same thread the user script was invoked
    on. The callback must therefore be thread-safe: it should not
    call into the dashboard's loop directly — use
    :meth:`EventLoopLagMonitor.bind_to_loop_threadsafe` (which itself
    uses ``asyncio.run_coroutine_threadsafe``).
    """
    previous = asyncio.get_event_loop_policy()
    wrapper = _DelegatingLoopPolicy(
        inner=previous,
        on_main_thread_loop=on_main_thread_loop,
        main_thread_id=threading.get_ident(),
    )
    asyncio.set_event_loop_policy(wrapper)
    logger.debug("loop discovery installed (wrapping %s)", type(previous).__name__)
    return _LoopDiscoveryHandle(previous_policy=previous, active_policy=wrapper)
