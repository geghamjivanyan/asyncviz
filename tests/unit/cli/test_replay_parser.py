"""Tests for the ``asyncviz replay`` subcommand parser.

Exercises the namespace → :class:`ReplayCliConfig` conversion + the
defaults the parser inherits from the shared ``DEFAULT_*`` constants.
The launcher itself is exercised via the end-to-end integration test
in :mod:`tests/integration/test_replay_command.py`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from asyncviz.cli.parser import parse


def test_parse_replay_with_bundle_only() -> None:
    cmd, _ = parse(["replay", "bundle.avz"])
    assert cmd.command == "replay"
    assert cmd.replay_config is not None
    cfg = cmd.replay_config
    assert cfg.bundle_path == Path("bundle.avz")
    # Defaults — the launcher would inherit these.
    assert cfg.speed == 1.0
    assert cfg.autoplay is True
    assert cfg.verify_integrity is True
    assert cfg.rebuild_manifest_if_missing is False


def test_parse_replay_speed_and_no_autoplay() -> None:
    cmd, _ = parse(["replay", "bundle.avz", "--speed", "2.5", "--no-autoplay"])
    assert cmd.replay_config is not None
    assert cmd.replay_config.speed == 2.5
    assert cmd.replay_config.autoplay is False


def test_parse_replay_dashboard_flags() -> None:
    cmd, _ = parse(
        [
            "replay",
            "/tmp/bundle.avz",
            "--host",
            "0.0.0.0",
            "--port",
            "9999",
            "--browser",
            "never",
            "--startup-timeout",
            "1.25",
        ],
    )
    assert cmd.replay_config is not None
    cfg = cmd.replay_config
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 9999
    assert cfg.browser == "never"
    assert cfg.startup_timeout == 1.25
    assert cfg.dashboard_url == "http://0.0.0.0:9999"


def test_parse_replay_no_integrity_and_rebuild_manifest() -> None:
    cmd, _ = parse(
        [
            "replay",
            "bundle.avz",
            "--no-integrity",
            "--rebuild-manifest",
        ],
    )
    assert cmd.replay_config is not None
    assert cmd.replay_config.verify_integrity is False
    assert cmd.replay_config.rebuild_manifest_if_missing is True


def test_parse_replay_quiet_debug_log_level() -> None:
    cmd, _ = parse(
        [
            "replay",
            "bundle.avz",
            "--quiet",
            "--debug",
            "--log-level",
            "WARNING",
        ],
    )
    assert cmd.replay_config is not None
    cfg = cmd.replay_config
    assert cfg.quiet is True
    assert cfg.debug is True
    assert cfg.log_level == "WARNING"


def test_parse_replay_requires_bundle_path() -> None:
    with pytest.raises(SystemExit):
        parse(["replay"])


def test_parse_replay_rejects_unknown_browser_choice() -> None:
    with pytest.raises(SystemExit):
        parse(["replay", "bundle.avz", "--browser", "sometimes"])
