"""Version-stamp helpers for the published-bundle manifest.

The publisher needs three identity fields:

* ``frontend_version`` — semver-ish version read from
  ``frontend/package.json`` (falls back to ``"0.0.0+dev"``).
* ``commit`` — current git HEAD short hash (falls back to ``None``).
* ``built_at_iso`` — ISO-8601 UTC build timestamp.

Each helper is pure / side-effect-free. Failures yield ``None`` so
the publisher can still emit a manifest in offline contexts.
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def read_frontend_version(package_json: Path) -> str:
    """Parse ``"version"`` from a ``frontend/package.json``."""
    if not package_json.is_file():
        return "0.0.0+dev"
    try:
        payload = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "0.0.0+dev"
    version = payload.get("version")
    if not isinstance(version, str) or not version.strip():
        return "0.0.0+dev"
    return version


def read_git_commit(repo_root: Path) -> str | None:
    """Return the short SHA of ``HEAD`` if ``git`` is available."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(repo_root),
            check=False,
            capture_output=True,
            text=True,
            timeout=2.0,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    sha = result.stdout.strip()
    return sha or None


def current_build_timestamp() -> str:
    """ISO-8601 UTC timestamp for the manifest's ``built_at`` field."""
    return datetime.now(UTC).isoformat(timespec="seconds")
