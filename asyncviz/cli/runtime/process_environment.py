"""Subprocess environment derivation.

The parent CLI builds the env dict the child should see — current env
+ AsyncViz bootstrap vars + user overrides. Pulled into its own
module so tests can assert the merge semantics without launching a
real subprocess.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from asyncviz.cli.configuration import RunCliConfig
from asyncviz.cli.runtime.bootstrap_entry import encode_bootstrap_env


def build_subprocess_environment(
    config: RunCliConfig,
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Compose the env dict for the AsyncViz bootstrap subprocess.

    Order:

    1. start with ``base_env`` (defaults to ``os.environ``),
    2. layer AsyncViz bootstrap vars derived from ``config``,
    3. layer the user's ``-e KEY=VAL`` overrides last so they win.
    """
    env: dict[str, str] = dict(base_env if base_env is not None else os.environ)
    env.update(encode_bootstrap_env(config))
    for key, value in config.env_overrides:
        env[key] = value
    # Ensure the child uses UTF-8 for stdio so emoji-bearing logs +
    # non-ASCII paths don't blow up on Windows.
    env.setdefault("PYTHONIOENCODING", "utf-8")
    # PYTHONUNBUFFERED makes the dashboard see live print() output;
    # we only set it when the user hasn't already chosen a value.
    env.setdefault("PYTHONUNBUFFERED", "1")
    return env
