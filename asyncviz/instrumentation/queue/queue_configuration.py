"""Typed configuration for queue instrumentation.

The patcher consumes this dataclass — the public API
``QueueInstrumentationEngine`` accepts it so tests + adapters can
toggle behaviour without monkey-patching module-level constants.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QueueInstrumentationConfig:
    """Knobs for the queue patcher."""

    emit_created: bool = True
    """When ``False`` we don't emit ``asyncio.queue.created`` events."""

    emit_put_get: bool = True
    """When ``False`` we don't emit ``put`` / ``get`` events. The
    ``full_wait`` / ``empty_wait`` / ``task_done`` / ``cancelled``
    events stay on so backpressure diagnostics still work."""

    emit_wait_events: bool = True
    emit_task_done: bool = True
    emit_cancelled: bool = True

    capture_creator_task_id: bool = True
    """When ``True``, ``QueueCreatedEvent`` records the runtime-task-id
    of the task that instantiated the queue."""

    redact_payloads: bool = True
    """Reserved — queue events never carry user payloads today. The
    flag exists so a future "inspect-mode" can opt-in to capturing
    repr() snippets."""

    trace_on_init: bool = False
    """When ``True``, ``set_queue_trace_enabled(True)`` runs as part
    of ``patch()`` — useful for one-shot diagnostics scripts."""

    max_blocked_lists_observed: int = 4096
    """Defensive cap on the size of ``_putters`` / ``_getters`` we'll
    iterate before reporting. Queues bigger than this likely indicate
    a runtime bug; we still emit but stop counting."""


DEFAULT_QUEUE_CONFIG = QueueInstrumentationConfig()
