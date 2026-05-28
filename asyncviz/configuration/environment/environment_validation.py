"""Post-parse validation hooks for the env loader.

The per-parser code already rejects ill-typed inputs. This module
adds cross-cutting checks (range bounds, enum-compatible values)
that don't fit naturally into a single parser.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from asyncviz.configuration.environment.environment_loader import LoadedEnvVar


@dataclass(frozen=True, slots=True)
class EnvironmentValidationIssue:
    env_name: str
    message: str


@dataclass(frozen=True, slots=True)
class EnvironmentValidationReport:
    issues: tuple[EnvironmentValidationIssue, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return len(self.issues) == 0


def _check_port(item: LoadedEnvVar) -> EnvironmentValidationIssue | None:
    if item.spec.target != "network.port":
        return None
    if not item.outcome.ok:
        return None
    value = int(item.outcome.value)
    if not (1 <= value <= 65535):
        return EnvironmentValidationIssue(
            env_name=item.env_name,
            message=f"port {value} outside the valid 1..65535 range",
        )
    return None


def _check_duration_positive(item: LoadedEnvVar) -> EnvironmentValidationIssue | None:
    if item.spec.kind.value not in {"duration_ms", "duration_seconds"}:
        return None
    if not item.outcome.ok:
        return None
    value = float(item.outcome.value)
    if value < 0:
        return EnvironmentValidationIssue(
            env_name=item.env_name,
            message=f"duration must be non-negative, got {value}",
        )
    return None


_CHECKS = (_check_port, _check_duration_positive)


def validate_loaded(loaded: Sequence[LoadedEnvVar]) -> EnvironmentValidationReport:
    issues: list[EnvironmentValidationIssue] = []
    for item in loaded:
        for check in _CHECKS:
            issue = check(item)
            if issue is not None:
                issues.append(issue)
    return EnvironmentValidationReport(issues=tuple(issues))
