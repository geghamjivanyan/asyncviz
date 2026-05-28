"""Resilience-layer invariants."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from asyncviz.runtime.resilience.failure_domain import FailureDomainSnapshot
from asyncviz.runtime.resilience.models.breaker_state import BreakerState
from asyncviz.runtime.resilience.recovery_supervisor import SupervisorSnapshot

IntegrityViolationKind = Literal[
    "negative-counter",
    "open-without-trip",
    "abandoned-with-closed-breaker",
    "quarantine-without-policy",
    "history-inconsistent",
]


class IsolationIntegrityError(Exception):
    """Raised by :func:`assert_isolation_clean`."""


@dataclass(frozen=True, slots=True)
class IntegrityFinding:
    kind: IntegrityViolationKind
    detail: str


def check_domain(snapshot: FailureDomainSnapshot) -> tuple[IntegrityFinding, ...]:
    findings: list[IntegrityFinding] = []
    counters = (
        ("total_failures", snapshot.total_failures),
        ("total_successes", snapshot.total_successes),
        ("trips", snapshot.breaker.trips),
        ("transitions", snapshot.breaker.transitions),
        ("failures_in_window", snapshot.breaker.failures_in_window),
    )
    for name, value in counters:
        if value < 0:
            findings.append(
                IntegrityFinding(
                    kind="negative-counter",
                    detail=f"{snapshot.name}.{name}={value}",
                ),
            )
    if (
        snapshot.breaker.state == BreakerState.OPEN
        and snapshot.breaker.trips == 0
    ):
        findings.append(
            IntegrityFinding(
                kind="open-without-trip",
                detail=snapshot.name,
            ),
        )
    return tuple(findings)


def check_supervisor(snapshot: SupervisorSnapshot) -> tuple[IntegrityFinding, ...]:
    findings: list[IntegrityFinding] = []
    if snapshot.attempts < 0 or snapshot.successes < 0 or snapshot.failures < 0:
        findings.append(
            IntegrityFinding(
                kind="negative-counter",
                detail=f"{snapshot.subsystem}.attempts={snapshot.attempts}",
            ),
        )
    if snapshot.abandoned and snapshot.attempts == 0:
        findings.append(
            IntegrityFinding(
                kind="history-inconsistent",
                detail=f"{snapshot.subsystem} abandoned with zero attempts",
            ),
        )
    return tuple(findings)


def assert_isolation_clean(
    domains: tuple[FailureDomainSnapshot, ...],
    supervisors: tuple[SupervisorSnapshot, ...] = (),
) -> None:
    findings: list[IntegrityFinding] = []
    for domain in domains:
        findings.extend(check_domain(domain))
    for supervisor in supervisors:
        findings.extend(check_supervisor(supervisor))
    if findings:
        joined = "; ".join(f"{f.kind}({f.detail})" for f in findings)
        raise IsolationIntegrityError(joined)
