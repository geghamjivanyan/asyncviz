from __future__ import annotations


class LineageError(Exception):
    """Base class for every :class:`LineageTracker` failure."""


class CyclicAncestryError(LineageError):
    """Raised when a registration would create a cycle (``T → … → T``).

    The tracker rejects the registration and leaves the existing lineage
    untouched. In normal operation this is impossible — asyncio task ids are
    monotonic and a task can't be its own ancestor — but replay payloads
    arriving out of order make defensive checks worthwhile.
    """


class OrphanTaskError(LineageError):
    """Raised on ancestry queries against a task the tracker does not know.

    Lookup APIs that *return* ``None`` for missing tasks raise this only in
    strict mode (the registry uses ``None`` returns by default).
    """


class LineageDepthExceededError(LineageError):
    """Raised when ancestry depth would exceed the configured ceiling.

    Acts as a tripwire for runaway recursive task creation; the default
    ceiling (8192) is well above any practical asyncio workload.
    """
