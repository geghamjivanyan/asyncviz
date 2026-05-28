from __future__ import annotations

import json
from pathlib import Path

from asyncviz.configuration import (
    NetworkOptions,
    RuntimeRecordingOptions,
    default_runtime_options,
    diff_options,
    options_to_dict,
    options_to_json,
)


def test_options_to_dict_is_json_serializable() -> None:
    payload = options_to_dict(default_runtime_options())
    json.dumps(payload)  # would raise otherwise.
    assert "network" in payload
    assert payload["network"]["host"] == "127.0.0.1"


def test_options_to_json_is_sorted_and_deterministic() -> None:
    options = default_runtime_options()
    encoded_a = options_to_json(options)
    encoded_b = options_to_json(options)
    assert encoded_a == encoded_b  # byte-stable


def test_options_to_dict_normalizes_paths_and_tuples() -> None:
    options = default_runtime_options().with_overrides(
        recording=RuntimeRecordingOptions(
            enabled=True,
            output_path=Path("/tmp/x.avz"),
            exclude_event_types=("asyncio.task.created",),
        ),
    )
    payload = options_to_dict(options)
    assert payload["recording"]["output_path"] == "/tmp/x.avz"
    assert payload["recording"]["exclude_event_types"] == ["asyncio.task.created"]


def test_diff_options_reports_changed_fields_only() -> None:
    base = default_runtime_options()
    overridden = base.with_overrides(network=NetworkOptions(host="0.0.0.0", port=9000))
    diff = diff_options(base, overridden)
    assert diff["network.host"] == ("127.0.0.1", "0.0.0.0")
    assert diff["network.port"] == (8877, 9000)
    # Unchanged domains stay out.
    assert not any(key.startswith("dashboard.") for key in diff)


def test_diff_options_empty_for_identical_options() -> None:
    options = default_runtime_options()
    assert diff_options(options, options) == {}
