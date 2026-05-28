from __future__ import annotations

import pytest

from asyncviz.cli.exit_codes import ExitCode


def test_canonical_exit_codes_have_unix_friendly_values() -> None:
    assert ExitCode.OK == 0
    assert ExitCode.USAGE_ERROR == 2
    assert ExitCode.INTERRUPTED == 130
    assert ExitCode.TERMINATED == 143


@pytest.mark.parametrize(
    "return_code,expected",
    [
        (0, ExitCode.OK),
        (130, ExitCode.INTERRUPTED),
        (143, ExitCode.TERMINATED),
        (42, ExitCode.SUBPROCESS_CRASHED),
    ],
)
def test_from_subprocess_maps_well_known(return_code: int, expected: ExitCode) -> None:
    assert ExitCode.from_subprocess(return_code) == expected


def test_from_subprocess_preserves_signal_codes() -> None:
    # POSIX: child killed by signal N → process.returncode = -N.
    # We surface 128+N to match shell convention.
    assert ExitCode.from_subprocess(-9) == 137  # SIGKILL → 128+9
