"""Apply a :class:`LoaderResult` to a :class:`RuntimeOptions`.

Splits the "parse env" step (handled by the loader) from the "fold
into options" step. The split is what lets:

* Tests assert on parser outcomes without applying them anywhere.
* The diagnostics endpoint render parsed env vars even when the
  resolver chose not to apply them (validation failure, override
  precedence).
* Future config-file / secret-provider sources reuse the *applier*
  with their own loaders.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from asyncviz.configuration.environment.environment_loader import (
    EnvironmentConfigurationLoader,
    LoadedEnvVar,
    LoaderResult,
)
from asyncviz.configuration.runtime_metadata import ProvenanceMap
from asyncviz.configuration.runtime_options import RuntimeOptions
from asyncviz.configuration.runtime_sources import OptionSource


@dataclass(frozen=True, slots=True)
class EnvironmentApplyResult:
    """Outcome of applying a loader result to a RuntimeOptions tree."""

    options: RuntimeOptions
    applied_count: int
    failed_count: int
    loader_result: LoaderResult


def apply_loader_result(
    base: RuntimeOptions,
    result: LoaderResult,
    *,
    provenance: ProvenanceMap | None = None,
) -> EnvironmentApplyResult:
    """Fold the loader's successful entries into ``base``.

    Failures are surfaced via :attr:`EnvironmentApplyResult.failed_count`
    but never raise — the caller chooses how strict to be.
    """
    record = provenance if provenance is not None else ProvenanceMap()
    options = base
    applied = 0
    for item in result.loaded:
        if not item.outcome.ok:
            continue
        new_options = _apply_one(options, item, record=record)
        if new_options is not None:
            options = new_options
            applied += 1
    return EnvironmentApplyResult(
        options=options,
        applied_count=applied,
        failed_count=result.parsed.failed_count,
        loader_result=result,
    )


def load_and_apply(
    base: RuntimeOptions,
    environ: dict[str, str],
    *,
    provenance: ProvenanceMap | None = None,
    loader: EnvironmentConfigurationLoader | None = None,
) -> EnvironmentApplyResult:
    """Convenience helper: load + apply in one call."""
    env_loader = loader or EnvironmentConfigurationLoader()
    return apply_loader_result(
        base,
        env_loader.load(environ),
        provenance=provenance,
    )


# ── internals ──────────────────────────────────────────────────────


def _apply_one(
    options: RuntimeOptions,
    item: LoadedEnvVar,
    *,
    record: ProvenanceMap,
) -> RuntimeOptions | None:
    """Apply one loaded var; return the new options or ``None`` on
    no-op (target unrecognised)."""
    target = item.spec.target
    value: Any = item.outcome.value

    domain_name, _, attr = target.partition(".")
    if not attr:
        return None

    # Special cases that don't map 1:1.
    if target == "browser.policy" and item.spec.env_name.endswith("_NO_BROWSER"):
        # Truthy NO_BROWSER means "force never".
        if not value:
            return None
        new_browser = replace(options.browser, policy="never")
        new_options = options.with_overrides(browser=new_browser)
        record.record(
            "browser.policy",
            value="never",
            source=OptionSource.ENVIRONMENT,
            raw_text=item.outcome.raw,
        )
        return new_options

    if target == "recording.output_path":
        new_recording = replace(
            options.recording,
            enabled=True,
            output_path=Path(str(value)) if value is not None else None,
        )
        new_options = options.with_overrides(recording=new_recording)
        record.record(
            "recording.output_path",
            value=str(value),
            source=OptionSource.ENVIRONMENT,
            raw_text=item.outcome.raw,
        )
        record.record(
            "recording.enabled",
            value=True,
            source=OptionSource.ENVIRONMENT,
            raw_text=item.outcome.raw,
        )
        return new_options

    if domain_name == "recording" and attr == "include_event_types":
        new_recording = replace(options.recording, include_event_types=tuple(value or ()))
        return _commit_domain(options, "recording", new_recording, target, value, item, record)
    if domain_name == "recording" and attr == "exclude_event_types":
        new_recording = replace(options.recording, exclude_event_types=tuple(value or ()))
        return _commit_domain(options, "recording", new_recording, target, value, item, record)

    domain = getattr(options, domain_name, None)
    if domain is None:
        return None
    if attr not in domain.__dataclass_fields__:
        return None

    new_domain = replace(domain, **{attr: value})
    new_options = options.with_overrides(**{domain_name: new_domain})
    record.record(
        target,
        value=value if not item.spec.secret else "<redacted>",
        source=OptionSource.ENVIRONMENT,
        raw_text=item.outcome.raw if not item.spec.secret else None,
    )
    return new_options


def _commit_domain(
    options: RuntimeOptions,
    domain_name: str,
    new_domain: Any,
    target: str,
    value: Any,
    item: LoadedEnvVar,
    record: ProvenanceMap,
) -> RuntimeOptions:
    new_options = options.with_overrides(**{domain_name: new_domain})
    record.record(
        target,
        value=value,
        source=OptionSource.ENVIRONMENT,
        raw_text=item.outcome.raw if not item.spec.secret else None,
    )
    return new_options


# Convenience access — used in tests.
def known_recording_specs() -> tuple[str, ...]:
    from asyncviz.configuration.environment.environment_mapping import CORE_ENV_VAR_SPECS

    return tuple(
        spec.env_name for spec in CORE_ENV_VAR_SPECS if spec.target.startswith("recording.")
    )
