"""Per-instance opt-out marker for internal AsyncViz semaphores.

AsyncViz itself does not currently construct any ``asyncio.Semaphore``
instances — but the marker is provided for symmetry with the queue
instrumentation, so future internal use sites can opt out of
instrumentation by calling :func:`mark_semaphore_internal` on the
constructed semaphore.

The patcher checks the marker on every operation and short-circuits
to the original method without emitting events.
"""

from __future__ import annotations

import contextlib

_INTERNAL_ATTR = "_asyncviz_internal_semaphore"


def mark_semaphore_internal(semaphore: object) -> None:
    """Flag ``semaphore`` so the AsyncViz semaphore patcher will skip
    emitting events for any operation against it.

    Safe to call on any object — failures (frozen instances, slot-only
    classes) are swallowed because the marker is an optimization, not a
    correctness requirement.
    """
    with contextlib.suppress(AttributeError, TypeError):
        setattr(semaphore, _INTERNAL_ATTR, True)


def is_semaphore_internal(semaphore: object) -> bool:
    """Return ``True`` if ``semaphore`` has been marked as internal."""
    return bool(getattr(semaphore, _INTERNAL_ATTR, False))
