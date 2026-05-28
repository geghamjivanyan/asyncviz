"""Runtime-tunable knobs for the event-loop lag monitor.

Configuration is a frozen value type. The monitor reads it at construction
time; runtime reconfiguration goes through ``EventLoopLagMonitor.reconfigure``
which atomically swaps the bound config and re-derives any nanosecond
counts so the scheduler observes the change at the next deadline.

Defaults are chosen for low overhead on a normal asyncio app:

* 200 ms sample interval → 5 samples per second, ~0 measurable cost.
* 50 ms / 250 ms / 1 s thresholds — empirically useful tiers for
  interactive apps.
* 256-sample rolling window — ~50 s of history at the default cadence.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from asyncviz.runtime.monitoring.event_loop.lag_thresholds import LagThresholds

#: 200 ms — five samples per second. The asyncio scheduler can wake a
#: callback at this cadence without measurable overhead on any non-toy
#: workload.
DEFAULT_SAMPLE_INTERVAL_SECONDS: float = 0.2

#: 50 ms — anything below is noise on a normal multi-tasked loop.
DEFAULT_WARNING_LAG_SECONDS: float = 0.05

#: 250 ms — interactive UIs notice this. Worth a warning event.
DEFAULT_CRITICAL_LAG_SECONDS: float = 0.25

#: 1 s — sustained block; runtime is effectively frozen for users.
DEFAULT_FREEZE_LAG_SECONDS: float = 1.0

#: 256 samples x 200 ms = ~51 s of history. Wide enough for p99 to
#: stabilize, tight enough to keep allocation cheap.
DEFAULT_STATISTICS_WINDOW: int = 256

#: Drop policy: how many *consecutive* missed-deadline samples the
#: scheduler tolerates before recording a sampler outage. Counts in
#: monitor self-metrics; does not stop the monitor.
DEFAULT_MAX_CONSECUTIVE_DROPS: int = 8

#: Hard cap on queued lag events the monitor will accept before applying
#: backpressure (dropping new samples until the consumer catches up).
#: Stops the monitor from amplifying lag when the bus is itself slow.
DEFAULT_MAX_PENDING_EVENTS: int = 512


@dataclass(frozen=True, slots=True)
class LagConfiguration:
    """Frozen knobs for the lag monitor.

    Construct directly or via :meth:`default`. The monitor reads this at
    start; pass to :meth:`EventLoopLagMonitor.reconfigure` to swap atomically.

    Fields:

    * ``sample_interval_seconds``     — cadence between samples.
    * ``thresholds``                  — :class:`LagThresholds` instance.
    * ``statistics_window``           — rolling-window capacity.
    * ``max_consecutive_drops``       — outage threshold.
    * ``max_pending_events``          — backpressure cap.
    * ``emit_measurement_events``     — publish per-sample events?
    * ``emit_threshold_breach_events``— publish on threshold trips?
    * ``trace_enabled``               — opt-in debug ring.
    """

    sample_interval_seconds: float = DEFAULT_SAMPLE_INTERVAL_SECONDS
    thresholds: LagThresholds = field(default_factory=LagThresholds)
    statistics_window: int = DEFAULT_STATISTICS_WINDOW
    max_consecutive_drops: int = DEFAULT_MAX_CONSECUTIVE_DROPS
    max_pending_events: int = DEFAULT_MAX_PENDING_EVENTS
    emit_measurement_events: bool = False
    emit_threshold_breach_events: bool = True
    trace_enabled: bool = False

    def __post_init__(self) -> None:
        if self.sample_interval_seconds <= 0:
            raise ValueError(
                f"sample_interval_seconds must be > 0 (got {self.sample_interval_seconds})"
            )
        if self.statistics_window <= 0:
            raise ValueError(f"statistics_window must be > 0 (got {self.statistics_window})")
        if self.max_consecutive_drops < 0:
            raise ValueError(
                f"max_consecutive_drops must be >= 0 (got {self.max_consecutive_drops})"
            )
        if self.max_pending_events < 0:
            raise ValueError(f"max_pending_events must be >= 0 (got {self.max_pending_events})")

    @classmethod
    def default(cls) -> LagConfiguration:
        """The recommended default — defaults for every tunable."""
        return cls()

    def with_interval(self, seconds: float) -> LagConfiguration:
        """Return a copy with a different sample interval."""
        return LagConfiguration(
            sample_interval_seconds=seconds,
            thresholds=self.thresholds,
            statistics_window=self.statistics_window,
            max_consecutive_drops=self.max_consecutive_drops,
            max_pending_events=self.max_pending_events,
            emit_measurement_events=self.emit_measurement_events,
            emit_threshold_breach_events=self.emit_threshold_breach_events,
            trace_enabled=self.trace_enabled,
        )

    def with_thresholds(self, thresholds: LagThresholds) -> LagConfiguration:
        return LagConfiguration(
            sample_interval_seconds=self.sample_interval_seconds,
            thresholds=thresholds,
            statistics_window=self.statistics_window,
            max_consecutive_drops=self.max_consecutive_drops,
            max_pending_events=self.max_pending_events,
            emit_measurement_events=self.emit_measurement_events,
            emit_threshold_breach_events=self.emit_threshold_breach_events,
            trace_enabled=self.trace_enabled,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "sample_interval_seconds": self.sample_interval_seconds,
            "thresholds": self.thresholds.to_dict(),
            "statistics_window": self.statistics_window,
            "max_consecutive_drops": self.max_consecutive_drops,
            "max_pending_events": self.max_pending_events,
            "emit_measurement_events": self.emit_measurement_events,
            "emit_threshold_breach_events": self.emit_threshold_breach_events,
            "trace_enabled": self.trace_enabled,
        }
