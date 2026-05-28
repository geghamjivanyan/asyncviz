"""JSON-safe serialization for :class:`RuntimeOptions`.

Used to embed the resolved configuration into:

* replay-bundle metadata (``meta/runtime.json`` ``extras``),
* the diagnostics endpoint payload,
* future config-file emission (``asyncviz config dump``).

The serializer converts every leaf into a JSON-native type — ``Path``
→ ``str``, tuples → lists, ``None`` is preserved — and sorts keys so
two identical resolutions produce byte-stable output.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from asyncviz.configuration.runtime_options import RuntimeOptions


def _normalize(value: Any) -> Any:
    """Recursively coerce ``value`` to JSON-safe primitives."""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return [_normalize(item) for item in value]
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _normalize(v) for k, v in value.items()}
    if is_dataclass(value):
        return options_to_dict(value)
    return value


def options_to_dict(options: Any) -> dict[str, Any]:
    """Convert ``options`` (any dataclass) to a sorted JSON-safe dict."""
    raw = asdict(options) if is_dataclass(options) else dict(options)
    return {key: _normalize(value) for key, value in sorted(raw.items())}


def options_to_json(options: RuntimeOptions, *, indent: int | None = None) -> str:
    """Dump ``options`` as canonical JSON."""
    return json.dumps(options_to_dict(options), ensure_ascii=False, indent=indent, sort_keys=True)


def diff_options(
    a: RuntimeOptions,
    b: RuntimeOptions,
) -> dict[str, tuple[Any, Any]]:
    """Return a dotted-key diff of two option snapshots.

    Useful for the diagnostics endpoint (``"what changed vs. the
    defaults?"``) + for the future ``asyncviz config diff`` CLI.
    """
    flat_a = _flatten(options_to_dict(a))
    flat_b = _flatten(options_to_dict(b))
    diff: dict[str, tuple[Any, Any]] = {}
    for key in sorted(set(flat_a) | set(flat_b)):
        if flat_a.get(key) != flat_b.get(key):
            diff[key] = (flat_a.get(key), flat_b.get(key))
    return diff


def _flatten(payload: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in payload.items():
        path = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
        if isinstance(value, dict):
            out.update(_flatten(value, path))
        else:
            out[path] = value
    return out
