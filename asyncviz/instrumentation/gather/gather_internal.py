"""Per-call opt-out marker for internal AsyncViz ``asyncio.gather`` use.

Several internal subsystems (the event bus dispatcher, the queue
dispatcher, the websocket broadcaster) fan out work to subscribers via
``asyncio.gather``. Once gather is patched, those calls would emit
``asyncio.gather.*`` events into the bus — which the dispatcher would
fan out via gather, which would emit more events, etc. Same event-
amplification hazard the queue + semaphore patchers solved earlier.

The fix is a task-local ``ContextVar`` plus a context-manager helper.
Internal call sites wrap their ``await asyncio.gather(...)`` in
``suppress_gather_instrumentation()``; the patched gather honours the
flag and short-circuits to the original gather with zero event emission.

``ContextVar`` is the right scope (not thread-local) because asyncio
gather works on cooperating tasks — a thread-local would suppress
parallel tasks on the same loop.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from contextvars import ContextVar

_in_internal_gather: ContextVar[bool] = ContextVar(
    "_in_internal_gather", default=False,
)


def is_internal_gather() -> bool:
    """``True`` when the calling context is marked as an internal gather."""
    return _in_internal_gather.get()


@contextlib.contextmanager
def suppress_gather_instrumentation() -> Iterator[None]:
    """Suppress :func:`asyncio.gather` instrumentation for the duration of
    the ``with`` block.

    Re-entrant: nested ``with`` blocks reset cleanly via the ContextVar
    token. Safe to call when the gather patcher isn't installed.
    """
    token = _in_internal_gather.set(True)
    try:
        yield
    finally:
        _in_internal_gather.reset(token)
