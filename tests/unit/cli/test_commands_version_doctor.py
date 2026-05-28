from __future__ import annotations

import argparse
import json

import pytest

from asyncviz.cli.commands.doctor import run as doctor_run
from asyncviz.cli.commands.version import run as version_run
from asyncviz.cli.exit_codes import ExitCode


def _ns(**kwargs: object) -> argparse.Namespace:
    return argparse.Namespace(**kwargs)


def test_version_text(capsys: pytest.CaptureFixture[str]) -> None:
    rc = version_run(_ns(emit_json=False))
    captured = capsys.readouterr()
    assert rc == int(ExitCode.OK)
    assert "asyncviz " in captured.out
    assert "channel:" in captured.out


def test_version_json(capsys: pytest.CaptureFixture[str]) -> None:
    rc = version_run(_ns(emit_json=True))
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert rc == int(ExitCode.OK)
    assert payload["name"] == "asyncviz"
    assert "build_identity" in payload
    assert "version" in payload["build_identity"]


def test_doctor_text(capsys: pytest.CaptureFixture[str]) -> None:
    rc = doctor_run(_ns(emit_json=False))
    err = capsys.readouterr().err
    # The doctor renders to stderr; the report should mention key items.
    assert rc == int(ExitCode.OK)
    assert "AsyncViz Doctor" in err
    assert "python-version" in err
    assert "frontend-bundle" in err


def test_doctor_json(capsys: pytest.CaptureFixture[str]) -> None:
    rc = doctor_run(_ns(emit_json=True))
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert rc == int(ExitCode.OK)
    assert "checks" in payload
    assert "packaging" in payload
    assert isinstance(payload["checks"], list)
