from __future__ import annotations

from enum import StrEnum


class EventSource(StrEnum):
    """Where an event came from. ``source`` on the envelope is a free string in
    case future plugins use values outside this enum, but the in-tree
    publishers should pick from here.
    """

    RUNTIME = "runtime"
    INSTRUMENTATION = "instrumentation"
    LIFECYCLE = "lifecycle"
    DASHBOARD = "dashboard"
    USER = "user"


class RuntimeState(StrEnum):
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"


class TaskState(StrEnum):
    """Canonical lifecycle states for an observed asyncio task.

    ``CREATED`` matches :class:`EventType.TASK_CREATED` — the moment AsyncViz
    first sees the task. Terminal states are ``COMPLETED``, ``CANCELLED``,
    and ``FAILED``.
    """

    CREATED = "created"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class WarningSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class EventType(StrEnum):
    """Canonical hierarchical event type names.

    Convention: ``<domain>.<entity>.<verb>`` (or ``<domain>.<entity>`` for state).
    The dotted segments are part of the public protocol — never rename a
    value here without bumping ``payload_version`` on the affected event.
    """

    # Asyncio task lifecycle
    TASK_CREATED = "asyncio.task.created"
    TASK_STARTED = "asyncio.task.started"
    TASK_WAITING = "asyncio.task.waiting"
    TASK_RESUMED = "asyncio.task.resumed"
    TASK_COMPLETED = "asyncio.task.completed"
    TASK_CANCELLED = "asyncio.task.cancelled"
    TASK_FAILED = "asyncio.task.failed"

    # Asyncio event loop
    LOOP_BLOCKED = "asyncio.loop.blocked"

    # Asyncio.Queue instrumentation
    QUEUE_CREATED = "asyncio.queue.created"
    QUEUE_PUT = "asyncio.queue.put"
    QUEUE_GET = "asyncio.queue.get"
    QUEUE_FULL_WAIT = "asyncio.queue.full_wait"
    QUEUE_EMPTY_WAIT = "asyncio.queue.empty_wait"
    QUEUE_TASK_DONE = "asyncio.queue.task_done"
    QUEUE_CANCELLED = "asyncio.queue.cancelled"

    # Asyncio.Queue metrics — engine-emitted aggregates
    QUEUE_METRICS_UPDATED = "asyncio.queue.metrics.updated"
    QUEUE_PRESSURE_CHANGED = "asyncio.queue.pressure.changed"
    QUEUE_CONTENTION_DETECTED = "asyncio.queue.contention.detected"
    QUEUE_SATURATION_DETECTED = "asyncio.queue.saturation.detected"

    # Asyncio.Semaphore instrumentation
    SEMAPHORE_CREATED = "asyncio.semaphore.created"
    SEMAPHORE_ACQUIRE_STARTED = "asyncio.semaphore.acquire.started"
    SEMAPHORE_ACQUIRED = "asyncio.semaphore.acquired"
    SEMAPHORE_RELEASED = "asyncio.semaphore.released"
    SEMAPHORE_CONTENTION_DETECTED = "asyncio.semaphore.contention.detected"
    SEMAPHORE_WAIT_CANCELLED = "asyncio.semaphore.wait.cancelled"

    # Asyncio.gather instrumentation
    GATHER_CREATED = "asyncio.gather.created"
    GATHER_CHILD_ATTACHED = "asyncio.gather.child.attached"
    GATHER_WAIT_STARTED = "asyncio.gather.wait.started"
    GATHER_CHILD_COMPLETED = "asyncio.gather.child.completed"
    GATHER_COMPLETED = "asyncio.gather.completed"
    GATHER_CANCELLED = "asyncio.gather.cancelled"
    GATHER_FAILED = "asyncio.gather.failed"

    # run_in_executor instrumentation
    EXECUTOR_REGISTERED = "asyncio.executor.registered"
    EXECUTOR_WORK_SUBMITTED = "asyncio.executor.work.submitted"
    EXECUTOR_WORK_STARTED = "asyncio.executor.work.started"
    EXECUTOR_WORK_COMPLETED = "asyncio.executor.work.completed"
    EXECUTOR_WORK_FAILED = "asyncio.executor.work.failed"
    EXECUTOR_WORK_CANCELLED = "asyncio.executor.work.cancelled"

    # Executor metrics — engine-emitted aggregates
    EXECUTOR_METRICS_UPDATED = "asyncio.executor.metrics.updated"
    EXECUTOR_SATURATION_CHANGED = "asyncio.executor.saturation.changed"
    EXECUTOR_CONTENTION_DETECTED = "asyncio.executor.contention.detected"
    EXECUTOR_LATENCY_SPIKE_DETECTED = "asyncio.executor.latency.spike.detected"

    # Runtime lifecycle
    RUNTIME_STARTED = "runtime.started"
    RUNTIME_STOPPED = "runtime.stopped"

    # Generic surfaces
    RUNTIME_WARNING = "runtime.warning"
    RUNTIME_METRIC = "runtime.metric"
