"""Derived projections of virtual runtime state.

The state store holds the raw, reducer-built domain dicts.
Visualization layers often want *derived* views — counts, sorted
lists, top-N by metric. Projections are pure functions over
:class:`VirtualRuntimeState` so they can be evaluated on any
snapshot (live, captured, checkpointed) without touching the
engine."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from asyncviz.replay.runtime.models.runtime_state import VirtualRuntimeState


@dataclass(frozen=True, slots=True)
class Projection:
    """Named pure-function projection over the state."""

    name: str
    project: Callable[[VirtualRuntimeState], Any]


@dataclass(frozen=True, slots=True)
class ProjectedView:
    """One projection's output paired with the state version it
    was computed from."""

    name: str
    value: Any
    based_on_sequence: int


# ── built-in projections ──────────────────────────────────────────


def project_counters(state: VirtualRuntimeState) -> dict[str, int]:
    """Cheap status snapshot — last sequence + applied frames + per-domain entry counts."""
    domain_counts = {name: len(payload) for name, payload in state.domains.items()}
    return {
        "last_sequence": state.last_sequence,
        "frames_applied": state.frames_applied,
        "domain_counts": domain_counts,
    }


def project_domain(domain: str) -> Callable[[VirtualRuntimeState], dict[str, Any]]:
    """Build a projection that returns one domain's full dict."""

    def _project(state: VirtualRuntimeState) -> dict[str, Any]:
        return dict(state.domains.get(domain, {}))

    return _project


def project_domain_names(state: VirtualRuntimeState) -> tuple[str, ...]:
    return tuple(sorted(state.domains.keys()))


# ── registry ──────────────────────────────────────────────────────


@dataclass(slots=True)
class ProjectionRegistry:
    """Holds an ordered list of named projections.

    Use it to assemble the bundle of views one frame of UI wants
    in a single ``compute_all`` pass."""

    projections: list[Projection] = field(default_factory=list)

    def register(self, projection: Projection) -> None:
        self.projections.append(projection)

    def remove(self, name: str) -> bool:
        for i, projection in enumerate(self.projections):
            if projection.name == name:
                del self.projections[i]
                return True
        return False

    def compute_all(self, state: VirtualRuntimeState) -> tuple[ProjectedView, ...]:
        return tuple(
            ProjectedView(
                name=p.name,
                value=p.project(state),
                based_on_sequence=state.last_sequence,
            )
            for p in self.projections
        )

    def names(self) -> tuple[str, ...]:
        return tuple(p.name for p in self.projections)


def default_projection_registry() -> ProjectionRegistry:
    """Bundle the most commonly-useful projections."""
    registry = ProjectionRegistry()
    registry.register(Projection(name="counters", project=project_counters))
    registry.register(Projection(name="domain_names", project=project_domain_names))
    return registry
