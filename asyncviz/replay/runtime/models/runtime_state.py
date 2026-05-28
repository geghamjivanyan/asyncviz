"""Virtual runtime state.

What a replay reconstructs. The state is split into namespaced
domains (tasks, queues, semaphores, executors, dependencies, …) so
multiple reducers can coexist without trampling each other. Each
domain holds a plain dict the reducer owns end-to-end.

Why dicts rather than typed dataclasses per domain: replay needs to
remain decoupled from the dashboard's evolving model surface. A
dict-of-dicts is the lowest common denominator that lets the engine
ship reconstructed state across threads, processes, or the wire
without versioning the engine API every time a dashboard panel adds
a field.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class VirtualRuntimeState:
    """Immutable snapshot of the virtual runtime."""

    last_sequence: int = 0
    last_monotonic_ns: int = 0
    frames_applied: int = 0
    domains: dict[str, dict[str, Any]] = field(default_factory=dict)
    """Per-domain state. ``{"tasks": {...}, "queues": {...}, ...}``"""

    notes: dict[str, str] = field(default_factory=dict)
    """Optional metadata bag — recording id, run id, version, etc."""

    def with_advance(
        self, *, sequence: int, monotonic_ns: int,
    ) -> VirtualRuntimeState:
        return VirtualRuntimeState(
            last_sequence=sequence,
            last_monotonic_ns=monotonic_ns,
            frames_applied=self.frames_applied + 1,
            domains=self.domains,
            notes=self.notes,
        )

    def with_domain(self, name: str, payload: dict[str, Any]) -> VirtualRuntimeState:
        next_domains = dict(self.domains)
        next_domains[name] = payload
        return VirtualRuntimeState(
            last_sequence=self.last_sequence,
            last_monotonic_ns=self.last_monotonic_ns,
            frames_applied=self.frames_applied,
            domains=next_domains,
            notes=self.notes,
        )

    def with_notes(self, notes: dict[str, str]) -> VirtualRuntimeState:
        return VirtualRuntimeState(
            last_sequence=self.last_sequence,
            last_monotonic_ns=self.last_monotonic_ns,
            frames_applied=self.frames_applied,
            domains=self.domains,
            notes=dict(notes),
        )

    @staticmethod
    def empty() -> VirtualRuntimeState:
        return VirtualRuntimeState()

    @staticmethod
    def from_dict(data: dict[str, Any]) -> VirtualRuntimeState:
        """Restore from a snapshot payload (typically a snapshot
        frame's ``payload`` dict)."""
        return VirtualRuntimeState(
            last_sequence=int(data.get("last_sequence", 0)),
            last_monotonic_ns=int(data.get("last_monotonic_ns", 0)),
            frames_applied=int(data.get("frames_applied", 0)),
            domains=dict(data.get("domains", {})),
            notes=dict(data.get("notes", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "last_sequence": self.last_sequence,
            "last_monotonic_ns": self.last_monotonic_ns,
            "frames_applied": self.frames_applied,
            "domains": dict(self.domains),
            "notes": dict(self.notes),
        }
