"""Canonical environment-variable configuration layer.

Public surface:

* :class:`EnvironmentConfigurationLoader` — walks the declarative
  registry, parses values, emits a :class:`LoaderResult`.
* :func:`load_and_apply` — fold a loader run into a
  :class:`RuntimeOptions` while tracking provenance.
* :data:`CORE_ENV_VAR_SPECS` — every env var the core loader knows
  about; consumed by the diagnostics endpoint + the future
  ``asyncviz env`` subcommand.
* :class:`EnvironmentDiagnosticsSnapshot` — composed view for the
  diagnostics endpoint.
"""

from asyncviz.configuration.environment.environment_defaults import (
    DEFAULT_NAMESPACE,
    MAX_VALUE_BYTES,
    SECRET_KEY_SUFFIXES,
)
from asyncviz.configuration.environment.environment_diagnostics import (
    EnvironmentDiagnosticsSnapshot,
    build_environment_diagnostics,
)
from asyncviz.configuration.environment.environment_loader import (
    EnvironmentConfigurationLoader,
    LoadedEnvVar,
    LoaderResult,
)
from asyncviz.configuration.environment.environment_mapping import (
    CORE_ENV_VAR_SPECS,
    EnvVarSpec,
    core_specs,
    known_env_names,
    specs_by_env_name,
)
from asyncviz.configuration.environment.environment_namespaces import (
    CORE_NAMESPACE,
    NamespaceRegistration,
    NamespaceRegistry,
    get_default_namespace_registry,
    reset_default_namespace_registry,
)
from asyncviz.configuration.environment.environment_normalization import (
    normalize_env_key,
    strip_namespace,
)
from asyncviz.configuration.environment.environment_observability import (
    EnvironmentMetricsSnapshot,
    get_environment_metrics,
    reset_environment_metrics,
)
from asyncviz.configuration.environment.environment_overrides import (
    load_with_overrides,
    overrides_to_env,
)
from asyncviz.configuration.environment.environment_parser import (
    PARSER_REGISTRY,
    Parser,
    parse_bool,
    parse_duration_ms,
    parse_duration_seconds,
    parse_enum,
    parse_float,
    parse_int,
    parse_list,
    parse_path,
    parse_string,
)
from asyncviz.configuration.environment.environment_provenance import (
    EnvironmentProvenanceEntry,
    record_loader_provenance,
)
from asyncviz.configuration.environment.environment_resolution import (
    EnvironmentApplyResult,
    apply_loader_result,
    load_and_apply,
)
from asyncviz.configuration.environment.environment_security import (
    REDACTED_VALUE,
    is_secret_key,
    redact_mapping,
    redact_value,
)
from asyncviz.configuration.environment.environment_serialization import (
    export_options_to_env,
    loader_result_to_dict,
)
from asyncviz.configuration.environment.environment_tracing import (
    EnvironmentTraceEntry,
    EnvironmentTraceKind,
    clear_environment_trace,
    get_environment_trace,
    is_environment_trace_enabled,
    record_environment_trace,
    set_environment_trace_enabled,
)
from asyncviz.configuration.environment.environment_types import (
    ParsedEnvironment,
    ParseDiagnostic,
    ParseKind,
    ParseOutcome,
)
from asyncviz.configuration.environment.environment_validation import (
    EnvironmentValidationIssue,
    EnvironmentValidationReport,
    validate_loaded,
)

__all__ = [
    "CORE_ENV_VAR_SPECS",
    "CORE_NAMESPACE",
    "DEFAULT_NAMESPACE",
    "MAX_VALUE_BYTES",
    "PARSER_REGISTRY",
    "REDACTED_VALUE",
    "SECRET_KEY_SUFFIXES",
    "EnvVarSpec",
    "EnvironmentApplyResult",
    "EnvironmentConfigurationLoader",
    "EnvironmentDiagnosticsSnapshot",
    "EnvironmentMetricsSnapshot",
    "EnvironmentProvenanceEntry",
    "EnvironmentTraceEntry",
    "EnvironmentTraceKind",
    "EnvironmentValidationIssue",
    "EnvironmentValidationReport",
    "LoadedEnvVar",
    "LoaderResult",
    "NamespaceRegistration",
    "NamespaceRegistry",
    "ParseDiagnostic",
    "ParseKind",
    "ParseOutcome",
    "ParsedEnvironment",
    "Parser",
    "apply_loader_result",
    "build_environment_diagnostics",
    "clear_environment_trace",
    "core_specs",
    "export_options_to_env",
    "get_default_namespace_registry",
    "get_environment_metrics",
    "get_environment_trace",
    "is_environment_trace_enabled",
    "is_secret_key",
    "known_env_names",
    "load_and_apply",
    "load_with_overrides",
    "loader_result_to_dict",
    "normalize_env_key",
    "overrides_to_env",
    "parse_bool",
    "parse_duration_ms",
    "parse_duration_seconds",
    "parse_enum",
    "parse_float",
    "parse_int",
    "parse_list",
    "parse_path",
    "parse_string",
    "record_environment_trace",
    "record_loader_provenance",
    "redact_mapping",
    "redact_value",
    "reset_default_namespace_registry",
    "reset_environment_metrics",
    "set_environment_trace_enabled",
    "specs_by_env_name",
    "strip_namespace",
    "validate_loaded",
]
