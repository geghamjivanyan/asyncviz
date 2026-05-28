"""Typed configuration for semaphore instrumentation.

Knobs are intentionally conservative. The patcher consumes a
:class:`SemaphoreInstrumentationConfig`; the public ``__init__``
accepts it so tests + adapters can toggle behaviour without
monkey-patching module-level constants.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SemaphoreInstrumentationConfig:
    """Knobs for :class:`SemaphoreInstrumentationEngine`."""

    emit_created: bool = True
    """Emit ``asyncio.semaphore.created`` when a semaphore is constructed."""

    emit_acquire: bool = True
    """Emit ``acquire.started`` + ``acquired`` events."""

    emit_release: bool = True

    emit_cancelled: bool = True
    """Emit ``wait.cancelled`` when an in-flight ``acquire`` is cancelled."""

    emit_contention: bool = True
    """Emit a leading-edge ``contention.detected`` event when the
    waiter count rises from below ``contention_threshold`` to
    at-or-above it. Set to ``False`` to mute the noisier signal."""

    capture_creator_task_id: bool = True
    """When ``True``, ``SemaphoreCreatedEvent`` records the
    runtime-task-id of the task that instantiated the semaphore."""

    contention_threshold: int = 1
    """Number of blocked waiters required to declare contention.
    A leading-edge transition from ``< threshold`` to ``>= threshold``
    fires one event; staying above the threshold does not retrigger."""

    trace_on_init: bool = False
    """When ``True``, ``set_semaphore_trace_enabled(True)`` runs as
    part of ``patch()`` — useful for diagnostics scripts."""


DEFAULT_SEMAPHORE_CONFIG = SemaphoreInstrumentationConfig()
