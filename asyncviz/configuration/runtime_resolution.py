"""Canonical layered resolver for :class:`RuntimeOptions`.

Precedence (lowest → highest):

  defaults → profile → environment → API kwargs → CLI flags → overrides

The resolver returns a :class:`ResolvedOptions` with the final
:class:`RuntimeOptions` + a :class:`ProvenanceMap` so the
diagnostics layer can show "host came from CLI, port came from env".
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from asyncviz.configuration.runtime_environment import apply_environment
from asyncviz.configuration.runtime_metadata import ProvenanceMap
from asyncviz.configuration.runtime_options import (
    RuntimeOptions,
    default_runtime_options,
)
from asyncviz.configuration.runtime_overrides import (
    apply_api_overrides,
    apply_cli_overrides,
)
from asyncviz.configuration.runtime_profiles import get_profile
from asyncviz.configuration.runtime_sources import OptionSource


@dataclass(frozen=True, slots=True)
class ResolvedOptions:
    """Result of one resolution run.

    Carries the final :class:`RuntimeOptions` + the per-option
    provenance so consumers can answer "what supplied this value?"
    without re-running the resolver.
    """

    options: RuntimeOptions
    provenance: ProvenanceMap
    profile_name: str | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def network(self):  # type: ignore[no-untyped-def]
        return self.options.network

    @property
    def dashboard(self):  # type: ignore[no-untyped-def]
        return self.options.dashboard


def resolve_options(
    *,
    profile: str | None = None,
    environ: Mapping[str, str] | None = None,
    api_overrides: dict[str, Any] | None = None,
    cli_overrides: dict[str, Any] | None = None,
    base: RuntimeOptions | None = None,
) -> ResolvedOptions:
    """Run the canonical resolver + return the composed options.

    Every parameter is optional so callers only pass what they have:

      * ``profile`` — seed from a named profile.
      * ``environ`` — env vars (defaults to ``None`` ⇒ no env layer).
      * ``api_overrides`` — :func:`asyncviz.start` kwargs.
      * ``cli_overrides`` — argparse-derived dict.
      * ``base`` — pre-built options to start from (skips defaults +
        profile when supplied).
    """
    provenance = ProvenanceMap()
    notes: list[str] = []

    # Step 1: start from ``base`` or defaults.
    if base is not None:
        options = base
        _seed_provenance(options, provenance, source=OptionSource.DEFAULT)
    else:
        options = default_runtime_options()
        _seed_provenance(options, provenance, source=OptionSource.DEFAULT)

    # Step 2: apply named profile.
    profile_name = None
    if profile:
        profile_options = get_profile(profile)
        profile_name = profile_options.profile_name or profile
        options = _merge_into(options, profile_options, provenance, OptionSource.PROFILE)
        notes.append(f"profile={profile_name}")

    # Step 3: environment.
    if environ is not None:
        options = apply_environment(options, environ, provenance=provenance)
        notes.append("env-layered")

    # Step 4: API kwargs.
    if api_overrides:
        options = apply_api_overrides(options, api_overrides, provenance=provenance)

    # Step 5: CLI flags (highest wins).
    if cli_overrides:
        options = apply_cli_overrides(options, cli_overrides, provenance=provenance)

    if profile_name:
        options = options.with_overrides(profile_name=profile_name)

    return ResolvedOptions(
        options=options,
        provenance=provenance,
        profile_name=profile_name,
        notes=tuple(notes),
    )


def _seed_provenance(
    options: RuntimeOptions,
    provenance: ProvenanceMap,
    *,
    source: OptionSource,
) -> None:
    """Stamp every option with ``source`` so the provenance map is
    fully populated even when no override touches the value."""
    for domain_name in (
        "network",
        "dashboard",
        "browser",
        "monitoring",
        "warning",
        "recording",
        "replay",
        "security",
    ):
        domain = getattr(options, domain_name)
        for attr in domain.__dataclass_fields__:
            value = getattr(domain, attr)
            # Skip ``None`` defaults — the resolver tracks set values.
            provenance.record(f"{domain_name}.{attr}", value=value, source=source)


def _merge_into(
    base: RuntimeOptions,
    overlay: RuntimeOptions,
    provenance: ProvenanceMap,
    source: OptionSource,
) -> RuntimeOptions:
    """Copy every overlay domain on top of ``base`` + record provenance."""
    merged = base.with_overrides(
        network=overlay.network,
        dashboard=overlay.dashboard,
        browser=overlay.browser,
        monitoring=overlay.monitoring,
        warning=overlay.warning,
        recording=overlay.recording,
        replay=overlay.replay,
        security=overlay.security,
    )
    _seed_provenance(merged, provenance, source=source)
    return merged
