"""Canonical aggregate runtime configuration.

Composes the per-domain option dataclasses into a single immutable
:class:`RuntimeOptions` value. Consumers (CLI, recorder, dashboard)
read the field they care about and ignore the rest — no need to
thread thirty kwargs through every constructor.

The struct is intentionally frozen so it's safe to share across
threads + cheap to hash for replay metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from asyncviz.configuration.runtime_browser import BrowserOptions
from asyncviz.configuration.runtime_dashboard import DashboardOptions
from asyncviz.configuration.runtime_monitoring import MonitoringOptions
from asyncviz.configuration.runtime_network import NetworkOptions
from asyncviz.configuration.runtime_recording import RuntimeRecordingOptions
from asyncviz.configuration.runtime_replay import ReplayOptions
from asyncviz.configuration.runtime_security import SecurityOptions
from asyncviz.configuration.runtime_warning import WarningOptions


@dataclass(frozen=True, slots=True)
class RuntimeOptions:
    """Top-level resolved options for one AsyncViz invocation."""

    network: NetworkOptions = field(default_factory=NetworkOptions)
    dashboard: DashboardOptions = field(default_factory=DashboardOptions)
    browser: BrowserOptions = field(default_factory=BrowserOptions)
    monitoring: MonitoringOptions = field(default_factory=MonitoringOptions)
    warning: WarningOptions = field(default_factory=WarningOptions)
    recording: RuntimeRecordingOptions = field(default_factory=RuntimeRecordingOptions)
    replay: ReplayOptions = field(default_factory=ReplayOptions)
    security: SecurityOptions = field(default_factory=SecurityOptions)
    profile_name: str | None = None
    """Optional name of the profile that seeded these options.
    Recorded in diagnostics + replay metadata."""

    # ── Convenience accessors ─────────────────────────────────────

    @property
    def dashboard_url(self) -> str:
        return self.network.base_url

    # ── Mutation helpers ──────────────────────────────────────────

    def with_overrides(self, **kwargs: Any) -> RuntimeOptions:
        """Return a copy with the named domain options replaced.

        ``options.with_overrides(browser=BrowserOptions(policy="never"))``
        keeps every other domain untouched. Useful in tests + plugin
        adapters that only care about one slice.
        """
        return replace(self, **kwargs)

    # ── Serialization ─────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe view of every domain.

        ``Path`` becomes ``str``, tuples become lists. Sorted by
        domain name for deterministic snapshot output.
        """
        from asyncviz.configuration.runtime_serialization import options_to_dict

        return options_to_dict(self)


def default_runtime_options() -> RuntimeOptions:
    """Return the default :class:`RuntimeOptions` (all domains at defaults)."""
    return RuntimeOptions()


# Convenience re-exports for users that just want the leaf types.
__all__ = [
    "BrowserOptions",
    "DashboardOptions",
    "MonitoringOptions",
    "NetworkOptions",
    "Path",
    "ReplayOptions",
    "RuntimeOptions",
    "RuntimeRecordingOptions",
    "SecurityOptions",
    "WarningOptions",
    "default_runtime_options",
]
