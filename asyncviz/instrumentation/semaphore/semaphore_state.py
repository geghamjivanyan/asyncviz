"""Helpers that introspect a live ``asyncio.Semaphore`` instance.

Split from the registry + patcher so the snapshot logic can be
unit-tested with stub semaphores. Defensive: every reader has a
fall-back for the case where a subclass renames a private attribute.
"""

from __future__ import annotations

import asyncio
from typing import Any

from asyncviz.instrumentation.semaphore.semaphore_metadata import (
    SemaphoreKind,
    SemaphoreSnapshot,
)


def classify_semaphore(semaphore: Any) -> SemaphoreKind:
    """Best-effort classification of ``semaphore``'s subclass."""
    if isinstance(semaphore, asyncio.BoundedSemaphore):
        return "BoundedSemaphore"
    if isinstance(semaphore, asyncio.Semaphore):
        if semaphore.__class__ is asyncio.Semaphore:
            return "Semaphore"
        return "subclass"
    return "unknown"


def snapshot_semaphore(
    semaphore: Any,
    *,
    semaphore_id: str,
    initial_value: int,
    bound_value: int | None,
) -> SemaphoreSnapshot:
    """Build a :class:`SemaphoreSnapshot` from a live semaphore instance.

    The current permit count is exposed via ``_value`` in CPython; we
    fall back to ``0`` if the attribute is missing or non-integer (e.g.
    a fakey test double).
    """
    raw_value = getattr(semaphore, "_value", None)
    current_value = int(raw_value) if isinstance(raw_value, int) else 0
    raw_waiters = getattr(semaphore, "_waiters", None) or ()
    try:
        waiter_count = len(raw_waiters)
    except TypeError:
        waiter_count = 0
    return SemaphoreSnapshot(
        semaphore_id=semaphore_id,
        current_value=current_value,
        waiter_count=waiter_count,
        initial_value=initial_value,
        bound_value=bound_value,
    )


def read_initial_value(semaphore: Any, *args: Any, **kwargs: Any) -> int:
    """Recover the initial value passed to ``Semaphore(value=...)``.

    The standard signature is ``Semaphore(value=1)``; subclasses may
    swap positional/keyword. We honour both. Falls back to the *current*
    ``_value`` if no explicit argument was supplied.
    """
    if "value" in kwargs:
        try:
            return int(kwargs["value"])
        except (TypeError, ValueError):
            pass
    if args:
        try:
            return int(args[0])
        except (TypeError, ValueError):
            pass
    raw_value = getattr(semaphore, "_value", 1)
    return int(raw_value) if isinstance(raw_value, int) else 1


def read_bound_value(semaphore: Any, initial_value: int) -> int | None:
    """Return the ``BoundedSemaphore`` upper bound, or ``None`` for plain
    semaphores."""
    if not isinstance(semaphore, asyncio.BoundedSemaphore):
        return None
    raw_bound = getattr(semaphore, "_bound_value", None)
    if isinstance(raw_bound, int) and raw_bound > 0:
        return raw_bound
    return initial_value
