"""Integration tests for ``asyncviz record`` driving a real subprocess.

Spawns the canonical CLI, records a short target into a temp bundle,
and validates the on-disk artifact. The recorder runs alongside the
embedded dashboard so this test also exercises the live/offline
coexistence path.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from asyncviz.runtime.replay.artifacts import open_bundle, validate_bundle

_REPO_ROOT = Path(__file__).resolve().parents[3]


_TARGET = """\
import asyncio
import time

async def child(i):
    await asyncio.sleep(0.05)
    return i

async def main():
    tasks = [asyncio.create_task(child(i), name=f"worker-{i}") for i in range(4)]
    print("results:", await asyncio.gather(*tasks))
    time.sleep(0.4)  # give the recorder time to flush.

asyncio.run(main())
"""


def _env() -> dict[str, str]:
    e = os.environ.copy()
    e.setdefault("ASYNCVIZ_NO_BROWSER", "1")
    return e


@pytest.mark.integration
def test_record_command_produces_valid_bundle(tmp_path: Path) -> None:
    script = tmp_path / "target.py"
    script.write_text(_TARGET, encoding="utf-8")
    bundle = tmp_path / "session.avz"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "asyncviz",
            "record",
            "--port",
            "8975",
            "--browser",
            "never",
            "--quiet",
            "--output",
            str(bundle),
            "--chunk-events",
            "16",
            "--flush-interval",
            "0.1",
            "--meta",
            "test=integration",
            str(script),
        ],
        capture_output=True,
        text=True,
        env=_env(),
        cwd=str(_REPO_ROOT),
        timeout=30,
    )
    assert result.returncode == 0, result.stderr

    report = validate_bundle(bundle)
    assert report.ok, f"validation failed: {report.issues!r}"

    opened = open_bundle(bundle)
    assert opened.is_finalized
    # We created 4 tasks ⇒ at least 4 task.created + 4 task.completed events.
    assert opened.manifest.event_count >= 8

    runtime_meta = opened.load_meta("runtime")
    assert runtime_meta is not None
    assert runtime_meta["target"]["kind"] == "script"
    assert runtime_meta["target"]["value"] == str(script)
    # ``--meta`` flows into the bundle-level manifest extras.
    assert opened.manifest.extras["test"] == "integration"

    # Snapshot was requested by default.
    snap = opened.load_snapshot("runtime")
    assert snap is not None
    # Sequences are monotonic.
    seqs = [f["sequence"] for f in opened.iter_frames()]
    assert seqs == sorted(seqs)


@pytest.mark.integration
def test_record_with_event_filter_drops_unwanted(tmp_path: Path) -> None:
    script = tmp_path / "target.py"
    script.write_text(_TARGET, encoding="utf-8")
    bundle = tmp_path / "session.avz"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "asyncviz",
            "record",
            "--port",
            "8976",
            "--browser",
            "never",
            "--quiet",
            "--output",
            str(bundle),
            "--chunk-events",
            "16",
            "--include-event",
            "asyncio.task.created",
            str(script),
        ],
        capture_output=True,
        text=True,
        env=_env(),
        cwd=str(_REPO_ROOT),
        timeout=30,
    )
    assert result.returncode == 0, result.stderr

    opened = open_bundle(bundle)
    event_types = {f["event_type"] for f in opened.iter_frames()}
    assert event_types == {"asyncio.task.created"}


@pytest.mark.integration
def test_record_help_lists_recording_flags() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "asyncviz", "record", "--help"],
        capture_output=True,
        text=True,
        env=_env(),
        cwd=str(_REPO_ROOT),
        timeout=10,
    )
    assert result.returncode == 0
    out = result.stdout
    assert "--output" in out
    assert "--compress" in out
    assert "--chunk-events" in out
    assert "--exclude-event" in out
