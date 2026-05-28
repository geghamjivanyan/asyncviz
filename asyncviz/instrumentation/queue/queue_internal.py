"""Per-instance opt-out marker for internal AsyncViz queues.

The patcher in :mod:`asyncviz.instrumentation.queue.queue_patch` rewrites
class methods on ``asyncio.Queue`` (+ subclasses). That means every queue
in the process — including the bus's own dispatch queue + the internal
event channel — picks up the instrumented methods.

The thread-local re-entrancy guard catches *direct* recursion (an
emit-publish chain inside one call stack), but it does not catch the
case where the bus's dispatcher pulls an event off the queue on a
separate async task: that ``get()`` is itself instrumented + emits a
"queue.get" event back through the bus, which puts it back on the
queue, which the dispatcher pulls again — an infinite event-amplification
loop with no shared call stack to gate on.

The fix is a per-instance opt-out flag. Internal wrappers that own an
``asyncio.Queue`` (``EventChannel``, ``BoundedEventQueue``) tag the
queue at construction; the patcher checks the tag and short-circuits
to the original methods without emitting events.
"""

from __future__ import annotations

import contextlib

#: Attribute name used to flag a queue as internal to AsyncViz. Chosen
#: with a leading underscore + ``asyncviz`` prefix so it's both visibly
#: private and namespaced — collisions with user code are highly
#: unlikely.
_INTERNAL_ATTR = "_asyncviz_internal_queue"


def mark_queue_internal(queue: object) -> None:
    """Flag ``queue`` so the AsyncViz queue patcher will skip emitting
    events for any operation against it.

    Safe to call on any object — failures (frozen instances, slot-only
    classes) are swallowed because the marker is an optimization, not a
    correctness requirement.
    """
    with contextlib.suppress(AttributeError, TypeError):
        setattr(queue, _INTERNAL_ATTR, True)


def is_queue_internal(queue: object) -> bool:
    """Return ``True`` if ``queue`` has been marked as internal."""
    return bool(getattr(queue, _INTERNAL_ATTR, False))
