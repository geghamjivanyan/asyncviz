"""Per-env-var provenance bridge.

Bridges the loader's :class:`LoaderResult` to the canonical
:class:`ProvenanceMap` used by the rest of the configuration layer.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.configuration.environment.environment_loader import LoadedEnvVar
from asyncviz.configuration.environment.environment_security import (
    REDACTED_VALUE,
    is_secret_key,
)
from asyncviz.configuration.runtime_metadata import ProvenanceMap
from asyncviz.configuration.runtime_sources import OptionSource


@dataclass(frozen=True, slots=True)
class EnvironmentProvenanceEntry:
    env_name: str
    option_path: str
    raw_value: str
    parsed_value: object
    redacted: bool


def record_loader_provenance(
    provenance: ProvenanceMap,
    loaded: tuple[LoadedEnvVar, ...],
) -> tuple[EnvironmentProvenanceEntry, ...]:
    """Record every successful env load in ``provenance`` + return a
    structured per-var view for the diagnostics layer."""
    entries: list[EnvironmentProvenanceEntry] = []
    for item in loaded:
        if not item.outcome.ok:
            continue
        redacted = item.spec.secret or is_secret_key(item.env_name)
        value = REDACTED_VALUE if redacted else item.outcome.value
        raw = REDACTED_VALUE if redacted else item.outcome.raw
        provenance.record(
            item.spec.target,
            value=value,
            source=OptionSource.ENVIRONMENT,
            raw_text=raw,
        )
        entries.append(
            EnvironmentProvenanceEntry(
                env_name=item.env_name,
                option_path=item.spec.target,
                raw_value=str(raw),
                parsed_value=value,
                redacted=redacted,
            ),
        )
    return tuple(entries)
