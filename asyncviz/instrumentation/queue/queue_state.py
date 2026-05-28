"""Helpers that read live state out of an ``asyncio.Queue`` instance.

Splits the introspection from the registry / patcher so we can
exercise the snapshot logic with a stub queue + so future
``PriorityQueue`` / ``LifoQueue`` overrides (if they ever expose
different state) plug in here.
"""

from __future__ import annotations

import asyncio
from typing import Any

from asyncviz.instrumentation.queue.queue_metadata import (
    QueueKind,
    QueueSnapshot,
)


def classify_queue(queue: Any) -> QueueKind:
    """Best-effort classification of ``queue``'s subclass."""
    if isinstance(queue, asyncio.LifoQueue):
        return "LifoQueue"
    if isinstance(queue, asyncio.PriorityQueue):
        return "PriorityQueue"
    if isinstance(queue, asyncio.Queue):
        # subclass of asyncio.Queue that isn't one of the stdlib leaves
        if queue.__class__ is asyncio.Queue:
            return "Queue"
        return "subclass"
    return "unknown"


def snapshot_queue(queue: Any, *, queue_id: str) -> QueueSnapshot:
    """Build a :class:`QueueSnapshot` from a live queue instance.

    Defensive: blocked-task counts come from the queue's private
    deques (``_putters`` / ``_getters``). Implementations that
    rename them fall back to ``0``.
    """
    try:
        size = int(queue.qsize())
    except Exception:
        size = 0
    try:
        maxsize = int(queue.maxsize)
    except Exception:
        maxsize = 0
    blocked_putters = len(getattr(queue, "_putters", ()) or ())
    blocked_getters = len(getattr(queue, "_getters", ()) or ())
    unfinished = int(getattr(queue, "_unfinished_tasks", 0) or 0)
    return QueueSnapshot(
        queue_id=queue_id,
        size=size,
        maxsize=maxsize,
        blocked_putters=blocked_putters,
        blocked_getters=blocked_getters,
        unfinished_tasks=unfinished,
    )
