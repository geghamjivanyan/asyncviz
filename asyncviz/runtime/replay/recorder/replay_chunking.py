"""Chunk-roll policy for the replay writer.

Decides when the writer should close the current chunk + start a new
one. Kept off the writer so test cases can exercise the policy with
plain integers.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ChunkPolicy:
    """Rolling chunk policy.

    Both thresholds are checked on every record. Whichever trips first
    forces a roll.
    """

    max_events: int
    max_bytes: int
    events_in_chunk: int = 0
    bytes_in_chunk: int = 0
    chunks_rolled: int = 0

    def reset_for_new_chunk(self) -> None:
        self.events_in_chunk = 0
        self.bytes_in_chunk = 0
        self.chunks_rolled += 1

    def record(self, event_size_bytes: int) -> None:
        self.events_in_chunk += 1
        self.bytes_in_chunk += event_size_bytes

    def should_roll(self) -> bool:
        if self.events_in_chunk == 0:
            return False
        if self.max_events > 0 and self.events_in_chunk >= self.max_events:
            return True
        return self.max_bytes > 0 and self.bytes_in_chunk >= self.max_bytes
