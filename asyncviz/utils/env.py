from __future__ import annotations

import os
from pathlib import Path

_TRUTHY = frozenset({"1", "true", "yes", "on", "y", "t"})
_FALSY = frozenset({"0", "false", "no", "off", "n", "f"})


def parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in _TRUTHY:
        return True
    if normalized in _FALSY:
        return False
    raise ValueError(f"Cannot parse boolean from {value!r}")


def parse_int(value: str | None, default: int) -> int:
    if value is None or value.strip() == "":
        return default
    return int(value)


def parse_float(value: str | None, default: float) -> float:
    if value is None or value.strip() == "":
        return default
    return float(value)


def load_dotenv(path: Path | None = None, *, override: bool = False) -> int:
    """Populate ``os.environ`` from a ``.env`` file. Returns the count of vars set.

    Format: ``KEY=value`` per line. ``#`` introduces a comment. Surrounding
    single or double quotes around the value are stripped. Existing
    environment variables are preserved unless ``override`` is true.
    """
    target = path if path is not None else Path.cwd() / ".env"
    if not target.is_file():
        return 0

    count = 0
    for raw in target.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key or not key.isidentifier():
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if not override and key in os.environ:
            continue
        os.environ[key] = value
        count += 1
    return count
