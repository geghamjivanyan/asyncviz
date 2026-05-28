"""Correlation helpers — stack captures + task metadata → warning group.

The emitter sees two input streams that need cross-referencing:

* Detector outcomes carry the freeze window context (window_id, peak
  lag, escalation flags). These drive group lifecycle.
* Capture stacks carry task metadata + an opaque ``capture_id``. We
  attach the capture id to the matching group so dashboard inspectors
  can pivot from a warning to its supporting traces.

The correlator is intentionally tiny — just a lookup function — so
swapping in a future implementation (distributed-trace-aware, e.g.)
doesn't require rewiring the emitter.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.runtime.monitoring.blocking import CapturedStack
from asyncviz.runtime.warnings.blocking.blocking_warning_grouping import (
    WarningGroup,
    WarningGroupRegistry,
)


@dataclass(frozen=True, slots=True)
class CorrelationResult:
    """Outcome of attaching a capture to the registry.

    ``group`` is the matched :class:`WarningGroup` (or ``None`` when no
    open group claims the capture). ``window_id`` echoes the capture's
    window for diagnostics.
    """

    group: WarningGroup | None
    window_id: str | None


class CaptureCorrelator:
    """Match a :class:`CapturedStack` to its matching warning group.

    Match rules:

    * captures with a ``window_id`` look up the open group for that
      window.
    * captures without a ``window_id`` (out-of-window captures, e.g.
      WARNING-level samples taken outside any freeze) are ignored — the
      emitter doesn't open a group for those, so there's nothing to
      attach to.

    The correlator mutates the matched group (adds the capture_id and
    fills task metadata when the group hasn't been correlated yet) and
    returns the result so the emitter can update self-metrics.
    """

    __slots__ = ("_registry",)

    def __init__(self, registry: WarningGroupRegistry) -> None:
        self._registry = registry

    def correlate(self, capture: CapturedStack) -> CorrelationResult:
        if capture.window_id is None:
            return CorrelationResult(group=None, window_id=None)
        group = self._registry.find_by_window_id(capture.window_id)
        if group is None:
            return CorrelationResult(group=None, window_id=capture.window_id)
        group.record_capture(capture.capture_id)
        group.attach_task(
            task_id=capture.task.task_id,
            task_name=capture.task.task_name,
            coroutine_name=capture.task.coroutine_name,
        )
        return CorrelationResult(group=group, window_id=capture.window_id)
