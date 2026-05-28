"""Runtime orchestration primitives used by the ``run`` command.

The CLI deliberately separates the four moving parts:

* :mod:`process_environment` — env-var derivation for the subprocess.
* :mod:`instrumentation_injection` — bootstrap snippet generation.
* :mod:`subprocess_runner` — process spawn + signal forwarding + exit.
* :mod:`launcher` — orchestrator that glues the above together.

Splitting them keeps each unit unit-testable without touching real
subprocesses.
"""

from asyncviz.cli.runtime.bootstrap_entry import (
    BOOTSTRAP_ENV_PREFIX,
    BootstrapTargetSpec,
    cli_bootstrap_main,
)
from asyncviz.cli.runtime.diagnostics import (
    CliLifecycleEvent,
    CliRuntimeDiagnostics,
    record_lifecycle_event,
)
from asyncviz.cli.runtime.instrumentation_injection import (
    build_bootstrap_command,
)
from asyncviz.cli.runtime.launcher import (
    LauncherOutcome,
    RunLauncher,
    run_target,
)
from asyncviz.cli.runtime.lifecycle import (
    SignalForwarder,
    install_signal_forwarder,
)
from asyncviz.cli.runtime.observability import (
    CliMetricsSnapshot,
    get_cli_metrics,
    reset_cli_metrics,
)
from asyncviz.cli.runtime.process_environment import (
    build_subprocess_environment,
)
from asyncviz.cli.runtime.subprocess_runner import (
    SubprocessOutcome,
    SubprocessRunner,
)

__all__ = [
    "BOOTSTRAP_ENV_PREFIX",
    "BootstrapTargetSpec",
    "CliLifecycleEvent",
    "CliMetricsSnapshot",
    "CliRuntimeDiagnostics",
    "LauncherOutcome",
    "RunLauncher",
    "SignalForwarder",
    "SubprocessOutcome",
    "SubprocessRunner",
    "build_bootstrap_command",
    "build_subprocess_environment",
    "cli_bootstrap_main",
    "get_cli_metrics",
    "install_signal_forwarder",
    "record_lifecycle_event",
    "reset_cli_metrics",
    "run_target",
]
