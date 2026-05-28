"""Runtime invariants on compatibility state.

Cheap checks operators can run after attaching the manager. Each
returns a structured finding instead of raising — the compatibility
layer is meant to be permissive (the alternative is "AsyncViz
refuses to start on an unfamiliar loop", which is a worse
operator experience).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from asyncviz.runtime.compat.models.loop_capabilities import LoopCapabilities
from asyncviz.runtime.compat.models.loop_kind import (
    LoopKind,
    loop_kind_supports_replay,
)

IntegrityFindingKind = Literal[
    "unknown-loop",
    "missing-task-factory",
    "missing-call-soon-threadsafe",
    "missing-create-task",
    "clock-resolution-degraded",
    "replay-not-safe",
    "stale-capabilities",
]


class LoopIntegrityError(Exception):
    """Raised by :func:`assert_compat_ok` when an invariant fails."""


@dataclass(frozen=True, slots=True)
class IntegrityFinding:
    kind: IntegrityFindingKind
    detail: str


def check_capabilities(
    capabilities: LoopCapabilities,
    *,
    require_replay: bool = False,
    min_clock_resolution_ns: int = 1_000_000_000,
) -> tuple[IntegrityFinding, ...]:
    findings: list[IntegrityFinding] = []
    if capabilities.kind == LoopKind.UNKNOWN:
        findings.append(
            IntegrityFinding(
                kind="unknown-loop",
                detail=capabilities.implementation,
            ),
        )
    if not capabilities.supports_create_task:
        findings.append(
            IntegrityFinding(
                kind="missing-create-task",
                detail=capabilities.implementation,
            ),
        )
    if not capabilities.supports_task_factory:
        findings.append(
            IntegrityFinding(
                kind="missing-task-factory",
                detail=capabilities.implementation,
            ),
        )
    if not capabilities.supports_call_soon_threadsafe:
        findings.append(
            IntegrityFinding(
                kind="missing-call-soon-threadsafe",
                detail=capabilities.implementation,
            ),
        )
    if (
        capabilities.monotonic_clock_resolution_ns > 0
        and capabilities.monotonic_clock_resolution_ns > min_clock_resolution_ns
    ):
        findings.append(
            IntegrityFinding(
                kind="clock-resolution-degraded",
                detail=f"{capabilities.monotonic_clock_resolution_ns}ns",
            ),
        )
    if require_replay and not (
        capabilities.replay_safe and loop_kind_supports_replay(capabilities.kind)
    ):
        findings.append(
            IntegrityFinding(
                kind="replay-not-safe",
                detail=capabilities.implementation,
            ),
        )
    return tuple(findings)


def assert_compat_ok(
    capabilities: LoopCapabilities,
    *,
    require_replay: bool = False,
) -> None:
    findings = check_capabilities(capabilities, require_replay=require_replay)
    if findings:
        joined = "; ".join(f"{f.kind}({f.detail})" for f in findings)
        raise LoopIntegrityError(f"loop-compat invariants failed: {joined}")
