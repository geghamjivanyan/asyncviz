"""Environment-variable layer for the runtime-options resolver.

Maps every ``ASYNCVIZ_*`` variable the canonical resolver knows about
into a typed :class:`RuntimeOptions` patch. Pure / side-effect-free —
tests inject a fresh ``environ`` dict to exercise every branch
without touching the live process environment.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from asyncviz.configuration.runtime_dashboard import FrontendMode, LogLevel
from asyncviz.configuration.runtime_metadata import ProvenanceMap
from asyncviz.configuration.runtime_options import RuntimeOptions
from asyncviz.configuration.runtime_sources import OptionSource
from asyncviz.utils.env import parse_bool, parse_float, parse_int

ENV_PREFIX = "ASYNCVIZ_"


def _maybe(env: Mapping[str, str], key: str) -> str | None:
    value = env.get(key)
    if value is None:
        return None
    return value


def _parse_log_level(raw: str) -> LogLevel:
    normalized = raw.strip().upper()
    if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ValueError(
            f"log_level must be one of DEBUG/INFO/WARNING/ERROR/CRITICAL, got {raw!r}",
        )
    return normalized  # type: ignore[return-value]


def _parse_frontend_mode(raw: str) -> FrontendMode:
    normalized = raw.strip().lower()
    if normalized not in {"auto", "embedded", "api-only"}:
        raise ValueError(
            f"frontend_mode must be auto/embedded/api-only, got {raw!r}",
        )
    return normalized  # type: ignore[return-value]


def _parse_browser_policy(raw: str) -> str:
    normalized = raw.strip().lower()
    if normalized not in {"auto", "always", "never"}:
        raise ValueError(
            f"browser policy must be auto/always/never, got {raw!r}",
        )
    return normalized


def apply_environment(
    base: RuntimeOptions,
    environ: Mapping[str, str] | None = None,
    *,
    provenance: ProvenanceMap | None = None,
) -> RuntimeOptions:
    """Layer env vars on top of ``base`` and return the new options.

    Delegates to the canonical
    :func:`asyncviz.configuration.environment.load_and_apply` so the
    declarative registry is the single source of truth for which env
    vars the resolver recognises. The legacy inline branches below
    remain only as a defensive fallback (e.g. when callers wrap the
    function from a non-os.environ source that the registry isn't
    aware of yet).
    """
    env = dict(environ) if environ is not None else {}
    record = provenance if provenance is not None else ProvenanceMap()

    if env:
        # Canonical path — the new env loader handles every registered
        # spec + records provenance with the right source tag.
        from asyncviz.configuration.environment import (
            EnvironmentConfigurationLoader,
            apply_loader_result,
            get_environment_metrics,
            record_loader_provenance,
        )

        loader = EnvironmentConfigurationLoader()
        result = loader.load(env)
        get_environment_metrics().record_load()
        get_environment_metrics().record_parsed(result.parsed.parsed_count)
        get_environment_metrics().record_failed(result.parsed.failed_count)
        get_environment_metrics().record_skipped(result.parsed.skipped_count)
        applied = apply_loader_result(base, result, provenance=record)
        record_loader_provenance(record, result.successes)
        get_environment_metrics().record_override(applied.applied_count)
        return applied.options

    network = base.network
    dashboard = base.dashboard
    browser = base.browser
    monitoring = base.monitoring
    recording = base.recording

    # ── network ─────────────────────────────────────────────────
    if (raw := _maybe(env, f"{ENV_PREFIX}HOST")) is not None:
        network = replace(network, host=raw)
        record.record("network.host", value=raw, source=OptionSource.ENVIRONMENT, raw_text=raw)
    if (raw := _maybe(env, f"{ENV_PREFIX}PORT")) is not None:
        port = parse_int(raw, network.port)
        network = replace(network, port=port)
        record.record("network.port", value=port, source=OptionSource.ENVIRONMENT, raw_text=raw)

    # ── dashboard ───────────────────────────────────────────────
    if (raw := _maybe(env, f"{ENV_PREFIX}DEBUG")) is not None:
        value = parse_bool(raw, dashboard.debug)
        dashboard = replace(dashboard, debug=value)
        record.record("dashboard.debug", value=value, source=OptionSource.ENVIRONMENT, raw_text=raw)
    if (raw := _maybe(env, f"{ENV_PREFIX}HEARTBEAT_INTERVAL")) is not None:
        value = parse_float(raw, dashboard.heartbeat_interval_seconds)
        dashboard = replace(dashboard, heartbeat_interval_seconds=value)
        record.record(
            "dashboard.heartbeat_interval_seconds",
            value=value,
            source=OptionSource.ENVIRONMENT,
            raw_text=raw,
        )
    if (raw := _maybe(env, f"{ENV_PREFIX}STARTUP_TIMEOUT")) is not None:
        value = parse_float(raw, dashboard.startup_timeout_seconds)
        dashboard = replace(dashboard, startup_timeout_seconds=value)
        record.record(
            "dashboard.startup_timeout_seconds",
            value=value,
            source=OptionSource.ENVIRONMENT,
            raw_text=raw,
        )
    if (raw := _maybe(env, f"{ENV_PREFIX}LOG_LEVEL")) is not None and raw.strip() != "":
        value = _parse_log_level(raw)
        dashboard = replace(dashboard, log_level=value)
        record.record(
            "dashboard.log_level",
            value=value,
            source=OptionSource.ENVIRONMENT,
            raw_text=raw,
        )
    if (raw := _maybe(env, f"{ENV_PREFIX}FRONTEND_MODE")) is not None and raw.strip() != "":
        value = _parse_frontend_mode(raw)
        dashboard = replace(dashboard, frontend_mode=value)
        record.record(
            "dashboard.frontend_mode",
            value=value,
            source=OptionSource.ENVIRONMENT,
            raw_text=raw,
        )

    # ── browser ─────────────────────────────────────────────────
    if (raw := _maybe(env, f"{ENV_PREFIX}BROWSER")) is not None and raw.strip() != "":
        value = _parse_browser_policy(raw)
        browser = replace(browser, policy=value)  # type: ignore[arg-type]
        record.record("browser.policy", value=value, source=OptionSource.ENVIRONMENT, raw_text=raw)
    if (raw := _maybe(env, f"{ENV_PREFIX}NO_BROWSER")) is not None and raw.strip() != "":
        # Treat truthy values as a hard-off → force policy=never.
        value = parse_bool(raw, False)
        if value:
            browser = replace(browser, policy="never")
            record.record(
                "browser.policy",
                value="never",
                source=OptionSource.ENVIRONMENT,
                raw_text=raw,
            )

    # ── monitoring ─────────────────────────────────────────────
    if (raw := _maybe(env, f"{ENV_PREFIX}ENABLE_INSTRUMENTATION")) is not None:
        value = parse_bool(raw, monitoring.enable_instrumentation)
        monitoring = replace(monitoring, enable_instrumentation=value)
        record.record(
            "monitoring.enable_instrumentation",
            value=value,
            source=OptionSource.ENVIRONMENT,
            raw_text=raw,
        )

    # ── recording ─────────────────────────────────────────────
    if (raw := _maybe(env, f"{ENV_PREFIX}RECORDING_OUTPUT")) is not None and raw.strip() != "":
        recording = replace(recording, enabled=True, output_path=Path(raw))
        record.record(
            "recording.output_path",
            value=str(Path(raw)),
            source=OptionSource.ENVIRONMENT,
            raw_text=raw,
        )
        record.record(
            "recording.enabled",
            value=True,
            source=OptionSource.ENVIRONMENT,
            raw_text=raw,
        )

    return base.with_overrides(
        network=network,
        dashboard=dashboard,
        browser=browser,
        monitoring=monitoring,
        recording=recording,
    )


def env_kwargs_for_overrides(updates: dict[str, Any]) -> dict[str, Any]:
    """Helper for tests + plugins — pass through unchanged."""
    return dict(updates)
