"""Sampling-marker event.

Emitted by the sampler when a drop window closes so replay
reconstruction has explicit "events were sampled out here"
information. The marker carries:

* the sequence range it covers,
* how many events were retained vs dropped,
* per-priority counts so replay tooling can render the gap with
  appropriate styling (a STATE drop is benign; a STRUCTURAL drop
  is a warning).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from asyncviz.runtime.sampling.models.sampling_priority import SamplingPriority

SAMPLING_MARKER_EVENT_TYPE = "asyncviz.sampling.marker"
"""Reserved synthetic event type used by the sampler. Recorder /
replay engine treat it specially — it's a metadata frame, not a
real runtime event."""


@dataclass(frozen=True, slots=True)
class SamplingMarker:
    """One window's summary."""

    first_sequence: int
    last_sequence: int
    retained: int
    dropped: int
    dropped_by_priority: dict[SamplingPriority, int] = field(
        default_factory=dict,
    )
    reason_summary: str = ""

    @property
    def total(self) -> int:
        return self.retained + self.dropped

    def to_payload(self) -> dict:
        """JSON-safe payload for embedding in a marker event."""
        return {
            "first_sequence": self.first_sequence,
            "last_sequence": self.last_sequence,
            "retained": self.retained,
            "dropped": self.dropped,
            "dropped_by_priority": {
                str(int(p)): count
                for p, count in self.dropped_by_priority.items()
            },
            "reason_summary": self.reason_summary,
        }
