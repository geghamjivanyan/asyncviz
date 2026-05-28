from __future__ import annotations

from dataclasses import dataclass, field

from asyncviz.runtime.events.models.enums import TaskState
from asyncviz.runtime.tasks.state import is_terminal


@dataclass(slots=True)
class RegistryMetricsSnapshot:
    total_tasks: int
    active_tasks: int
    completed_tasks: int
    cancelled_tasks: int
    failed_tasks: int
    terminal_tasks: int
    average_duration_seconds: float | None
    average_completed_duration_seconds: float | None
    average_cancelled_duration_seconds: float | None
    average_failed_duration_seconds: float | None
    cancellations_by_origin: dict[str, int]
    rejected_transitions: int


@dataclass(slots=True)
class _DurationAccumulator:
    """Per-terminal sum + count. O(1) average via :meth:`average`."""

    count: int = 0
    total: float = 0.0

    def record(self, seconds: float) -> None:
        if seconds < 0:
            return
        self.count += 1
        self.total += seconds

    @property
    def average(self) -> float | None:
        if self.count == 0:
            return None
        return self.total / self.count


@dataclass(slots=True)
class RegistryMetrics:
    """Counters maintained by :class:`TaskRegistry`.

    All mutation happens under the registry's lock, so we don't need atomics.
    Duration accounting is split per terminal class so the dashboard can
    surface completed-vs-cancelled-vs-failed averages independently.
    """

    total: int = 0
    by_state_counts: dict[TaskState, int] = None  # type: ignore[assignment]

    # Visibility into safety nets: how many times an event triggered an
    # invalid transition (registry tolerated it, but it's useful to see).
    rejected_transitions: int = 0

    # Per-terminal duration accumulators.
    _completed: _DurationAccumulator = field(default_factory=_DurationAccumulator)
    _cancelled: _DurationAccumulator = field(default_factory=_DurationAccumulator)
    _failed: _DurationAccumulator = field(default_factory=_DurationAccumulator)

    # Cancellation-origin histogram. Key ``"unknown"`` is used when the
    # attribution layer did not stamp an origin (None).
    _cancellations_by_origin: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.by_state_counts = dict.fromkeys(TaskState, 0)

    def task_registered(self, state: TaskState) -> None:
        self.total += 1
        self.by_state_counts[state] += 1

    def task_removed(self, state: TaskState) -> None:
        self.total -= 1
        self.by_state_counts[state] -= 1

    def task_transitioned(self, old: TaskState, new: TaskState) -> None:
        self.by_state_counts[old] -= 1
        self.by_state_counts[new] += 1

    def record_duration(self, terminal: TaskState, duration_seconds: float) -> None:
        """Record a duration into the bucket for ``terminal`` (terminal state)."""
        if duration_seconds < 0:
            return
        if terminal == TaskState.COMPLETED:
            self._completed.record(duration_seconds)
        elif terminal == TaskState.CANCELLED:
            self._cancelled.record(duration_seconds)
        elif terminal == TaskState.FAILED:
            self._failed.record(duration_seconds)

    def record_rejected_transition(self) -> None:
        self.rejected_transitions += 1

    def record_cancellation_origin(self, origin: str | None) -> None:
        key = origin if origin else "unknown"
        self._cancellations_by_origin[key] = self._cancellations_by_origin.get(key, 0) + 1

    @property
    def active_count(self) -> int:
        return sum(count for state, count in self.by_state_counts.items() if not is_terminal(state))

    @property
    def terminal_count(self) -> int:
        return sum(count for state, count in self.by_state_counts.items() if is_terminal(state))

    @property
    def average_duration_seconds(self) -> float | None:
        """Average across all terminal types — unweighted."""
        total_count = self._completed.count + self._cancelled.count + self._failed.count
        if total_count == 0:
            return None
        total_sum = self._completed.total + self._cancelled.total + self._failed.total
        return total_sum / total_count

    @property
    def average_completed_duration_seconds(self) -> float | None:
        return self._completed.average

    @property
    def average_cancelled_duration_seconds(self) -> float | None:
        return self._cancelled.average

    @property
    def average_failed_duration_seconds(self) -> float | None:
        return self._failed.average

    def snapshot(self) -> RegistryMetricsSnapshot:
        counts = self.by_state_counts
        return RegistryMetricsSnapshot(
            total_tasks=self.total,
            active_tasks=self.active_count,
            completed_tasks=counts[TaskState.COMPLETED],
            cancelled_tasks=counts[TaskState.CANCELLED],
            failed_tasks=counts[TaskState.FAILED],
            terminal_tasks=self.terminal_count,
            average_duration_seconds=self.average_duration_seconds,
            average_completed_duration_seconds=self.average_completed_duration_seconds,
            average_cancelled_duration_seconds=self.average_cancelled_duration_seconds,
            average_failed_duration_seconds=self.average_failed_duration_seconds,
            cancellations_by_origin=dict(self._cancellations_by_origin),
            rejected_transitions=self.rejected_transitions,
        )
