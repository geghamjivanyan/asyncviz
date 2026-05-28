"""Programmatic-override helpers used by the resolver + tests.

The resolver applies overrides from two places:

* ``apply_api_overrides`` — kwargs passed to :func:`asyncviz.start`
  or other Python-API entry points. Recorded with
  :attr:`OptionSource.API_KWARGS`.
* ``apply_cli_overrides`` — values resolved from argparse. Recorded
  with :attr:`OptionSource.CLI`.

Both helpers are *additive* — only the explicitly provided fields
get overridden so callers don't accidentally reset unrelated
values to a default.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from asyncviz.configuration.runtime_metadata import ProvenanceMap
from asyncviz.configuration.runtime_options import RuntimeOptions
from asyncviz.configuration.runtime_sources import OptionSource

# Mapping of top-level kwarg names → ``(domain, field)`` so we can
# apply API kwargs without a 30-line switch.
_API_KEY_MAP: dict[str, tuple[str, str]] = {
    "host": ("network", "host"),
    "port": ("network", "port"),
    "debug": ("dashboard", "debug"),
    "heartbeat_interval": ("dashboard", "heartbeat_interval_seconds"),
    "startup_timeout": ("dashboard", "startup_timeout_seconds"),
    "log_level": ("dashboard", "log_level"),
    "frontend_mode": ("dashboard", "frontend_mode"),
    "enable_instrumentation": ("monitoring", "enable_instrumentation"),
}


def apply_api_overrides(
    base: RuntimeOptions,
    overrides: dict[str, Any],
    *,
    provenance: ProvenanceMap | None = None,
) -> RuntimeOptions:
    """Apply :func:`asyncviz.start` kwargs to ``base``.

    Unknown kwargs are silently ignored — the caller's responsibility
    to validate. This keeps the helper stable when new kwargs land
    upstream without immediate options-layer changes.
    """
    record = provenance if provenance is not None else ProvenanceMap()
    if not overrides:
        return base

    network = base.network
    dashboard = base.dashboard
    browser = base.browser
    monitoring = base.monitoring
    recording = base.recording

    for key, value in overrides.items():
        if value is None:
            continue
        # ``open_browser=True`` legacy → BrowserOptions.policy="auto" / "never"
        if key == "open_browser":
            policy: str = "auto" if value else "never"
            browser = replace(browser, policy=policy)  # type: ignore[arg-type]
            record.record("browser.policy", value=policy, source=OptionSource.API_KWARGS)
            continue

        mapping = _API_KEY_MAP.get(key)
        if mapping is None:
            continue
        domain, attr = mapping
        if domain == "network":
            network = replace(network, **{attr: value})
        elif domain == "dashboard":
            dashboard = replace(dashboard, **{attr: value})
        elif domain == "monitoring":
            monitoring = replace(monitoring, **{attr: value})
        record.record(f"{domain}.{attr}", value=value, source=OptionSource.API_KWARGS)

    return base.with_overrides(
        network=network,
        dashboard=dashboard,
        browser=browser,
        monitoring=monitoring,
        recording=recording,
    )


def apply_cli_overrides(
    base: RuntimeOptions,
    overrides: dict[str, Any],
    *,
    provenance: ProvenanceMap | None = None,
) -> RuntimeOptions:
    """Apply explicit CLI flag values to ``base``.

    Same shape as :func:`apply_api_overrides` but records every entry
    with :attr:`OptionSource.CLI` so the diagnostics endpoint can
    distinguish "user typed this" from "API caller passed this".
    """
    record = provenance if provenance is not None else ProvenanceMap()
    if not overrides:
        return base

    # Reuse api-mapping logic but bump the source to CLI.
    network = base.network
    dashboard = base.dashboard
    browser = base.browser
    monitoring = base.monitoring
    recording = base.recording

    for key, value in overrides.items():
        if value is None:
            continue
        if key == "browser":
            browser = replace(browser, policy=value)  # type: ignore[arg-type]
            record.record("browser.policy", value=value, source=OptionSource.CLI)
            continue
        if key == "no_dashboard" and value:
            dashboard = replace(dashboard, frontend_mode="api-only")
            record.record(
                "dashboard.frontend_mode",
                value="api-only",
                source=OptionSource.CLI,
            )
            continue
        if key == "no_instrumentation" and value:
            monitoring = replace(monitoring, enable_instrumentation=False)
            record.record(
                "monitoring.enable_instrumentation",
                value=False,
                source=OptionSource.CLI,
            )
            continue
        if key == "recording_output":
            recording = replace(
                recording,
                enabled=True,
                output_path=Path(value) if value else None,
            )
            record.record(
                "recording.output_path",
                value=str(value),
                source=OptionSource.CLI,
            )
            record.record("recording.enabled", value=True, source=OptionSource.CLI)
            continue

        mapping = _API_KEY_MAP.get(key)
        if mapping is None:
            continue
        domain, attr = mapping
        if domain == "network":
            network = replace(network, **{attr: value})
        elif domain == "dashboard":
            dashboard = replace(dashboard, **{attr: value})
        elif domain == "monitoring":
            monitoring = replace(monitoring, **{attr: value})
        record.record(f"{domain}.{attr}", value=value, source=OptionSource.CLI)

    return RuntimeOptions(
        network=network,
        dashboard=dashboard,
        browser=browser,
        monitoring=monitoring,
        warning=base.warning,
        recording=recording,
        replay=base.replay,
        security=base.security,
        profile_name=base.profile_name,
    )
