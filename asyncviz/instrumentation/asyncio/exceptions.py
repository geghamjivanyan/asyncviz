from __future__ import annotations


class InstrumentationError(Exception):
    """Base class for instrumentation failures.

    Production code never raises these into user paths — they're caught
    inside the patched ``create_task`` wrapper and logged at DEBUG.
    """


class PatcherStateError(InstrumentationError):
    """Raised for misuse of the patcher API (e.g. unpatch without patch)."""
