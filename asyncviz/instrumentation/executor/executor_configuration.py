"""Typed configuration for executor instrumentation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExecutorInstrumentationConfig:
    """Knobs for :class:`ExecutorInstrumentationEngine`."""

    emit_registered: bool = True
    """Emit ``executor.registered`` when a new executor is observed."""

    emit_submitted: bool = True
    emit_started: bool = True
    emit_completed: bool = True
    emit_failed: bool = True
    emit_cancelled: bool = True

    capture_submitting_task_id: bool = True
    capture_callable_name: bool = True
    capture_worker_thread_name: bool = True
    capture_exception_type: bool = True


DEFAULT_EXECUTOR_CONFIG = ExecutorInstrumentationConfig()
