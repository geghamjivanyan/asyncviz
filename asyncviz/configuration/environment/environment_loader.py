"""Canonical environment loader.

Walks the declarative :data:`CORE_ENV_VAR_SPECS` registry, looks up
each env var (preferring the canonical name over aliases), parses
the value, and emits a typed :class:`ParsedEnvironment` bundle that
the resolver consumes.

The loader is deliberately split from the resolver so:

* Tests can run it against fake env dicts + assert on parse outcomes.
* The diagnostics endpoint can call it on the live env to render
  "here's what I parsed" without re-applying to options.
* Future config-file / secret-provider sources can plug their own
  loader behind the same :class:`ParsedEnvironment` shape.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from asyncviz.configuration.environment.environment_defaults import (
    DEFAULT_NAMESPACE,
    MAX_VALUE_BYTES,
)
from asyncviz.configuration.environment.environment_mapping import (
    CORE_ENV_VAR_SPECS,
    EnvVarSpec,
)
from asyncviz.configuration.environment.environment_types import (
    ParsedEnvironment,
    ParseDiagnostic,
    ParseOutcome,
)


@dataclass(frozen=True, slots=True)
class LoadedEnvVar:
    """Pair an env spec with the resolved parse outcome."""

    spec: EnvVarSpec
    outcome: ParseOutcome
    env_name: str
    """Which alias actually carried the value."""


@dataclass(frozen=True, slots=True)
class LoaderResult:
    """Full result of one loader invocation."""

    loaded: tuple[LoadedEnvVar, ...]
    parsed: ParsedEnvironment
    namespace: str

    @property
    def successes(self) -> tuple[LoadedEnvVar, ...]:
        return tuple(item for item in self.loaded if item.outcome.ok)

    @property
    def failures(self) -> tuple[LoadedEnvVar, ...]:
        return tuple(item for item in self.loaded if not item.outcome.ok)


@dataclass(slots=True)
class EnvironmentConfigurationLoader:
    """Pluggable environment loader.

    Tests inject ``specs`` to constrain which keys are recognized;
    the default uses the canonical core registry.
    """

    specs: tuple[EnvVarSpec, ...] = field(default_factory=lambda: CORE_ENV_VAR_SPECS)
    namespace: str = DEFAULT_NAMESPACE
    max_value_bytes: int = MAX_VALUE_BYTES

    def load(self, environ: Mapping[str, str]) -> LoaderResult:
        """Parse every recognised env var from ``environ``."""
        loaded: list[LoadedEnvVar] = []
        outcomes: list[ParseOutcome] = []
        diagnostics: list[ParseDiagnostic] = []
        parsed_count = 0
        skipped_count = 0
        failed_count = 0

        for spec in self.specs:
            env_name, raw = self._pick_value(environ, spec)
            if raw is None:
                skipped_count += 1
                continue
            if len(raw.encode("utf-8", errors="ignore")) > self.max_value_bytes:
                diagnostic = ParseDiagnostic(
                    env_key=env_name,
                    severity="error",
                    message=(
                        f"{env_name}: value exceeds max size {self.max_value_bytes} bytes; ignoring"
                    ),
                    raw=None,
                )
                diagnostics.append(diagnostic)
                failed_count += 1
                continue
            parser = spec.build_parser()
            outcome = parser(raw)
            outcomes.append(outcome)
            loaded.append(LoadedEnvVar(spec=spec, outcome=outcome, env_name=env_name))
            if outcome.ok:
                parsed_count += 1
            else:
                failed_count += 1
                diagnostics.append(
                    ParseDiagnostic(
                        env_key=env_name,
                        severity="error",
                        message=outcome.error or "parse failed",
                        raw=outcome.raw if not spec.secret else None,
                    ),
                )

        parsed = ParsedEnvironment(
            outcomes=tuple(outcomes),
            diagnostics=tuple(diagnostics),
            parsed_count=parsed_count,
            skipped_count=skipped_count,
            failed_count=failed_count,
        )
        return LoaderResult(loaded=tuple(loaded), parsed=parsed, namespace=self.namespace)

    # ── internals ──────────────────────────────────────────────

    def _pick_value(
        self,
        environ: Mapping[str, str],
        spec: EnvVarSpec,
    ) -> tuple[str, str | None]:
        """Return ``(name_used, raw_value)`` for ``spec``.

        Prefers the canonical name; falls back to aliases left-to-right.
        Empty strings are treated as "unset" so an empty env var doesn't
        accidentally trip enum validators.
        """
        for candidate in spec.all_names():
            value = environ.get(candidate)
            if value is None:
                continue
            stripped = value.strip()
            if stripped == "":
                continue
            return candidate, value
        return spec.env_name, None
