"""Round-trip env-var serialization.

Two flows live here:

* ``export_options_to_env(options)`` → dict[str,str] that, when fed
  back through the loader, reconstructs the option subset. Used by
  the CLI bootstrap to propagate config into the subprocess +
  by the future ``asyncviz config dump --shell`` command.
* ``loader_result_to_dict(result)`` — JSON-safe view of one loader
  run; consumed by the diagnostics endpoint.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from asyncviz.configuration.environment.environment_loader import LoaderResult
from asyncviz.configuration.environment.environment_mapping import (
    CORE_ENV_VAR_SPECS,
    EnvVarSpec,
)
from asyncviz.configuration.environment.environment_security import REDACTED_VALUE
from asyncviz.configuration.environment.environment_types import ParseKind
from asyncviz.configuration.runtime_options import RuntimeOptions


def loader_result_to_dict(result: LoaderResult) -> dict[str, Any]:
    """Return a JSON-safe summary of the loader run."""
    return {
        "namespace": result.namespace,
        "parsed_count": result.parsed.parsed_count,
        "skipped_count": result.parsed.skipped_count,
        "failed_count": result.parsed.failed_count,
        "successes": [
            {
                "env_name": item.env_name,
                "target": item.spec.target,
                "kind": item.outcome.kind.value,
                "value": (REDACTED_VALUE if item.spec.secret else _normalize(item.outcome.value)),
                "raw": REDACTED_VALUE if item.spec.secret else item.outcome.raw,
            }
            for item in result.successes
        ],
        "failures": [
            {
                "env_name": item.env_name,
                "target": item.spec.target,
                "kind": item.outcome.kind.value,
                "error": item.outcome.error,
            }
            for item in result.failures
        ],
        "diagnostics": [asdict(d) for d in result.parsed.diagnostics],
    }


def export_options_to_env(
    options: RuntimeOptions,
    *,
    specs: tuple[EnvVarSpec, ...] = CORE_ENV_VAR_SPECS,
) -> dict[str, str]:
    """Emit a dict that, fed through the loader, reproduces ``options``.

    Only options whose value differs from the canonical defaults are
    emitted — that keeps the resulting env footprint minimal and
    matches the "diff from defaults" semantics in the diagnostics
    endpoint.
    """
    from asyncviz.configuration.runtime_options import default_runtime_options

    defaults = default_runtime_options()
    out: dict[str, str] = {}
    for spec in specs:
        if spec.secret:
            continue
        current = _get_dotted(options, spec.target)
        baseline = _get_dotted(defaults, spec.target)
        if current == baseline:
            continue
        out[spec.env_name] = _emit_for_kind(spec.kind, current)
    return out


# ── internals ─────────────────────────────────────────────────────


def _normalize(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_normalize(v) for v in value]
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    if hasattr(value, "__fspath__"):
        return str(value)
    return value


def _get_dotted(options: RuntimeOptions, dotted: str) -> Any:
    parts = dotted.split(".")
    cur: Any = options
    for part in parts:
        cur = getattr(cur, part, None)
        if cur is None:
            return None
    return cur


def _emit_for_kind(kind: ParseKind, value: Any) -> str:
    if value is None:
        return ""
    if kind is ParseKind.BOOL:
        return "1" if bool(value) else "0"
    if kind is ParseKind.LIST:
        if isinstance(value, (list, tuple)):
            return ",".join(str(v) for v in value)
        return str(value)
    if kind is ParseKind.PATH:
        return str(value)
    return str(value)
