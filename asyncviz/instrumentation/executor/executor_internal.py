"""Per-call opt-out marker for internal AsyncViz ``run_in_executor`` use.

AsyncViz doesn't currently dispatch any work through executors
internally — but the marker is provided for symmetry with the gather
patcher, so future internal subsystems can wrap their calls without
triggering event amplification.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from contextvars import ContextVar

_in_internal_executor: ContextVar[bool] = ContextVar(
    "_in_internal_executor", default=False,
)


def is_internal_executor_call() -> bool:
    """``True`` when the calling context is marked as an internal call."""
    return _in_internal_executor.get()


@contextlib.contextmanager
def suppress_executor_instrumentation() -> Iterator[None]:
    """Suppress :func:`run_in_executor` instrumentation for the duration
    of the ``with`` block.

    Re-entrant: nested ``with`` blocks reset cleanly via the ContextVar
    token. Safe to call when the executor patcher isn't installed.
    """
    token = _in_internal_executor.set(True)
    try:
        yield
    finally:
        _in_internal_executor.reset(token)
