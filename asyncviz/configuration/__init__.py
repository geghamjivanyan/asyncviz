"""Canonical runtime-options surface for AsyncViz.

Public exports kept small + focused. Importers typically reach for
:func:`resolve_options` (the layered resolver) and
:class:`RuntimeOptions` (the typed top-level options bundle).
"""

from asyncviz.configuration.runtime_browser import BrowserOptions, BrowserPolicy
from asyncviz.configuration.runtime_configuration import (
    from_legacy_config,
    to_legacy_config,
)
from asyncviz.configuration.runtime_dashboard import (
    DashboardOptions,
    FrontendMode,
    LogLevel,
)
from asyncviz.configuration.runtime_diagnostics import (
    ConfigurationDiagnosticsSnapshot,
    build_configuration_diagnostics,
    provenance_summary,
    render_diagnostics_lines,
)
from asyncviz.configuration.runtime_environment import (
    ENV_PREFIX,
    apply_environment,
)
from asyncviz.configuration.runtime_metadata import (
    OptionProvenance,
    ProvenanceMap,
)
from asyncviz.configuration.runtime_monitoring import MonitoringOptions
from asyncviz.configuration.runtime_network import NetworkOptions
from asyncviz.configuration.runtime_observability import (
    ConfigurationMetricsSnapshot,
    get_configuration_metrics,
    reset_configuration_metrics,
)
from asyncviz.configuration.runtime_options import (
    RuntimeOptions,
    default_runtime_options,
)
from asyncviz.configuration.runtime_overrides import (
    apply_api_overrides,
    apply_cli_overrides,
)
from asyncviz.configuration.runtime_profiles import (
    get_profile,
    list_profile_names,
    register_profile,
)
from asyncviz.configuration.runtime_recording import (
    BackpressureMode,
    CompressionMode,
    RuntimeRecordingOptions,
)
from asyncviz.configuration.runtime_replay import ReplayOptions
from asyncviz.configuration.runtime_resolution import (
    ResolvedOptions,
    resolve_options,
)
from asyncviz.configuration.runtime_security import SecurityOptions
from asyncviz.configuration.runtime_serialization import (
    diff_options,
    options_to_dict,
    options_to_json,
)
from asyncviz.configuration.runtime_sources import OptionSource
from asyncviz.configuration.runtime_tracing import (
    ConfigurationTraceEntry,
    ConfigurationTraceKind,
    clear_configuration_trace,
    get_configuration_trace,
    is_configuration_trace_enabled,
    record_configuration_trace,
    set_configuration_trace_enabled,
)
from asyncviz.configuration.runtime_validation import (
    RuntimeConfigurationError,
    ValidationIssue,
    collect_issues,
    validate_options,
)
from asyncviz.configuration.runtime_warning import WarningOptions

__all__ = [
    "ENV_PREFIX",
    "BackpressureMode",
    "BrowserOptions",
    "BrowserPolicy",
    "CompressionMode",
    "ConfigurationDiagnosticsSnapshot",
    "ConfigurationMetricsSnapshot",
    "ConfigurationTraceEntry",
    "ConfigurationTraceKind",
    "DashboardOptions",
    "FrontendMode",
    "LogLevel",
    "MonitoringOptions",
    "NetworkOptions",
    "OptionProvenance",
    "OptionSource",
    "ProvenanceMap",
    "ReplayOptions",
    "ResolvedOptions",
    "RuntimeConfigurationError",
    "RuntimeOptions",
    "RuntimeRecordingOptions",
    "SecurityOptions",
    "ValidationIssue",
    "WarningOptions",
    "apply_api_overrides",
    "apply_cli_overrides",
    "apply_environment",
    "build_configuration_diagnostics",
    "clear_configuration_trace",
    "collect_issues",
    "default_runtime_options",
    "diff_options",
    "from_legacy_config",
    "get_configuration_metrics",
    "get_configuration_trace",
    "get_profile",
    "is_configuration_trace_enabled",
    "list_profile_names",
    "options_to_dict",
    "options_to_json",
    "provenance_summary",
    "record_configuration_trace",
    "register_profile",
    "render_diagnostics_lines",
    "reset_configuration_metrics",
    "resolve_options",
    "set_configuration_trace_enabled",
    "to_legacy_config",
    "validate_options",
]
