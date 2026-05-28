"""Replay helpers for blocking-detector state reconstruction.

The detector's pipeline is deterministic on its inputs: given the same
sequence of ``(LagMeasurement, LagThresholdEvaluation)`` pairs, it
produces the same violations, escalations, and windows. This module
provides a small helper to drive that replay from a list of saved
inputs — used by the unit tests for the determinism assertion and by
future replay tools that need to reconstruct detector state from the
recorded lag event log.

We deliberately don't extract violations/windows from the replay log
itself: those events *are* the detector's output, so reconstructing
from them would be circular. Replay-from-lag is the canonical
direction.
"""

from __future__ import annotations

from collections.abc import Iterable

from asyncviz.runtime.monitoring.event_loop.lag_measurement import LagMeasurement
from asyncviz.runtime.monitoring.event_loop.lag_thresholds import LagThresholdEvaluation


def replay_into_detector(
    detector,  # BlockingThresholdDetector (avoids circular import)
    inputs: Iterable[tuple[LagMeasurement, LagThresholdEvaluation]],
) -> int:
    """Feed each ``(measurement, evaluation)`` pair to the detector.

    Returns the number of measurements processed. The detector applies
    its full pipeline (classify → escalate → window → cooldown → emit)
    on each input. Used by replay tools + by determinism tests.
    """
    count = 0
    for measurement, evaluation in inputs:
        detector.process(measurement, evaluation)
        count += 1
    return count
