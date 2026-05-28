"""Canonical CLI exit codes.

We standardize on a small enum so every command surfaces deterministic
exit semantics for shell-script users + CI pipelines. The values mirror
the conventional Unix range (``0`` = success, ``1`` = generic failure,
``2`` = usage error per the GNU/argparse convention).

Subprocess-failure codes deliberately stay distinct so callers can
``echo $?`` and distinguish "the CLI couldn't launch the target" from
"the target itself failed".
"""

from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    """Canonical AsyncViz CLI exit codes."""

    OK = 0
    """Command succeeded."""

    GENERIC_FAILURE = 1
    """Unspecified failure — last-resort, prefer a specific code below."""

    USAGE_ERROR = 2
    """Argparse rejected the invocation (GNU convention)."""

    CONFIGURATION_ERROR = 3
    """CLI configuration failed validation (bad host/port/path/etc.)."""

    BOOTSTRAP_FAILURE = 10
    """Dashboard runtime bootstrap raised before the target ran."""

    TARGET_NOT_FOUND = 11
    """Target script / module could not be resolved."""

    SUBPROCESS_LAUNCH_FAILURE = 12
    """The launcher failed to spawn the subprocess (OSError, ENOENT)."""

    SUBPROCESS_CRASHED = 13
    """The user's target exited with a non-zero status — we forward it."""

    INTERRUPTED = 130
    """Standard SIGINT (Ctrl-C) exit code."""

    TERMINATED = 143
    """Standard SIGTERM exit code."""

    @classmethod
    def from_subprocess(cls, return_code: int) -> ExitCode | int:
        """Map a subprocess's return code to a CLI exit code.

        Pass-through for zero (success) + signal-style negative codes;
        otherwise we report :attr:`SUBPROCESS_CRASHED` so callers can
        distinguish a CLI failure from a target failure if they care.
        """
        if return_code == 0:
            return cls.OK
        if return_code == 130:
            return cls.INTERRUPTED
        if return_code == 143:
            return cls.TERMINATED
        # Negative codes (POSIX) mean killed by signal; preserve them.
        if return_code < 0:
            return 128 + (-return_code)
        return cls.SUBPROCESS_CRASHED
