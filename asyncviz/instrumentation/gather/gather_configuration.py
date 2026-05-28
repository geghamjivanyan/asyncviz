"""Typed configuration for gather instrumentation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GatherInstrumentationConfig:
    """Knobs for :class:`GatherInstrumentationEngine`."""

    emit_created: bool = True
    emit_child_attached: bool = True
    """Emit one ``gather.child.attached`` event per child after wiring."""
    emit_wait_started: bool = True
    emit_child_completed: bool = True
    """Emit ``gather.child.completed`` for every child as it transitions
    to done. Set to ``False`` on extremely high-fanout workloads where
    the per-child event volume is too noisy."""
    emit_completed: bool = True
    emit_cancelled: bool = True
    emit_failed: bool = True

    capture_parent_task_id: bool = True
    """Read the awaiter's runtime_task_id at gather invocation."""

    capture_exception_type: bool = True
    """Record the exception class *name* (never the message) on
    ``gather.failed``. Disable on hardened production runtimes that
    can't take any introspection cost."""


DEFAULT_GATHER_CONFIG = GatherInstrumentationConfig()
