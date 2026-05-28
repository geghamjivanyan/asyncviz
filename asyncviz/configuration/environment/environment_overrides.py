"""Programmatic overrides that mimic env vars.

Used by tests + plugin adapters that want to feed env-shaped values
through the canonical loader without setting real env vars.
"""

from __future__ import annotations

from asyncviz.configuration.environment.environment_defaults import (
    DEFAULT_NAMESPACE,
)
from asyncviz.configuration.environment.environment_loader import (
    EnvironmentConfigurationLoader,
    LoaderResult,
)
from asyncviz.configuration.environment.environment_normalization import (
    normalize_env_key,
)


def overrides_to_env(
    overrides: dict[str, str],
    *,
    namespace: str = DEFAULT_NAMESPACE,
) -> dict[str, str]:
    """Normalize free-form override keys into canonical env-var names.

    Lets callers write ``{"port": "9000"}`` instead of
    ``{"ASYNCVIZ_PORT": "9000"}`` without losing precedence.
    """
    prefix = namespace if namespace.endswith("_") else namespace + "_"
    out: dict[str, str] = {}
    for key, value in overrides.items():
        normalized = normalize_env_key(key)
        if not normalized.startswith(prefix):
            normalized = f"{prefix}{normalized}"
        out[normalized] = str(value)
    return out


def load_with_overrides(
    environ: dict[str, str],
    overrides: dict[str, str],
    *,
    loader: EnvironmentConfigurationLoader | None = None,
) -> LoaderResult:
    """Apply ``overrides`` on top of ``environ`` + load.

    Overrides always win when keys collide — that's the conventional
    "test override" behaviour.
    """
    merged = dict(environ)
    merged.update(overrides_to_env(overrides))
    return (loader or EnvironmentConfigurationLoader()).load(merged)
