"""Top-level orchestrator for ``asyncviz run``.

Responsibilities:

* validate the config + emit a startup banner,
* compute the subprocess argv + env,
* invoke the runner,
* schedule the browser open,
* translate the subprocess return code into a CLI exit code.

The launcher is the *only* CLI module that talks to all the others;
keeping it small and procedural makes it easy to follow end-to-end.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from asyncviz.cli.browser import (
    BrowserLaunchConfig,
    BrowserLauncher,
    build_dashboard_url,
)
from asyncviz.cli.configuration import RunCliConfig, validate_run_config
from asyncviz.cli.exit_codes import ExitCode
from asyncviz.cli.output import error, info, log, ok
from asyncviz.cli.runtime.diagnostics import record_lifecycle_event
from asyncviz.cli.runtime.instrumentation_injection import build_bootstrap_command
from asyncviz.cli.runtime.observability import get_cli_metrics
from asyncviz.cli.runtime.process_environment import build_subprocess_environment
from asyncviz.cli.runtime.subprocess_runner import (
    SubprocessOutcome,
    SubprocessRunner,
)


@dataclass(frozen=True, slots=True)
class LauncherOutcome:
    """End-state surfaced to the calling command."""

    exit_code: int
    subprocess_outcome: SubprocessOutcome | None
    dashboard_url: str | None


class RunLauncher:
    """High-level orchestrator for ``asyncviz run``."""

    def __init__(self, config: RunCliConfig) -> None:
        self.config = config
        self.runner = SubprocessRunner(shutdown_timeout=config.shutdown_timeout)

    def launch(self) -> LauncherOutcome:
        config = self.config
        get_cli_metrics().record_run_started()
        started_at = time.monotonic()
        try:
            validate_run_config(config)
        except Exception as exc:
            error(str(exc))
            get_cli_metrics().record_run_outcome(ok=False)
            return LauncherOutcome(
                exit_code=int(ExitCode.CONFIGURATION_ERROR),
                subprocess_outcome=None,
                dashboard_url=None,
            )
        record_lifecycle_event("config-validated", config.target.display_name())

        dashboard_url: str | None = None
        if not config.no_dashboard:
            dashboard_url = build_dashboard_url(host=config.host, port=config.port)

        if not config.quiet:
            self._emit_banner(dashboard_url)

        # Resolve browser preference *before* spawning so the user
        # sees the decision in the banner. The actual open is best-
        # effort — we never block the subprocess on it. The launcher
        # additionally waits for the dashboard's ``/api/health/live``
        # endpoint before issuing the open so the operator never sees
        # a "this site can't be reached" race.
        if not config.no_dashboard and dashboard_url is not None:
            launch_cfg = BrowserLaunchConfig(
                url=dashboard_url,
                policy=config.browser,  # type: ignore[arg-type]
                readiness_url=f"{dashboard_url.rstrip('/')}/api/health/live",
                readiness_timeout_seconds=max(1.0, config.startup_timeout),
            )
            outcome = BrowserLauncher().launch_async(launch_cfg)
            get_cli_metrics().record_browser_launch(opened=outcome.launched)
            if outcome.launched:
                record_lifecycle_event("browser-launched", dashboard_url)
            else:
                record_lifecycle_event("browser-skipped", outcome.detail)

        argv = build_bootstrap_command(config)
        env = build_subprocess_environment(config)
        try:
            subprocess_outcome = self.runner.run(argv, env=env, cwd=config.cwd)
        except FileNotFoundError as exc:
            error(f"failed to launch interpreter {argv[0]!r}: {exc}")
            get_cli_metrics().record_run_outcome(ok=False)
            return LauncherOutcome(
                exit_code=int(ExitCode.SUBPROCESS_LAUNCH_FAILURE),
                subprocess_outcome=None,
                dashboard_url=dashboard_url,
            )
        except OSError as exc:
            error(f"subprocess spawn failed: {exc}")
            get_cli_metrics().record_run_outcome(ok=False)
            return LauncherOutcome(
                exit_code=int(ExitCode.SUBPROCESS_LAUNCH_FAILURE),
                subprocess_outcome=None,
                dashboard_url=dashboard_url,
            )

        total_ms = (time.monotonic() - started_at) * 1000
        get_cli_metrics().record_run_durations(
            total_ms=total_ms,
            subprocess_ms=subprocess_outcome.duration_seconds * 1000,
        )

        exit_code = ExitCode.from_subprocess(subprocess_outcome.return_code)
        succeeded = exit_code == ExitCode.OK
        get_cli_metrics().record_run_outcome(ok=succeeded)

        if subprocess_outcome.timed_out_at_shutdown:
            error("subprocess did not exit cleanly within the shutdown timeout")
        if not config.quiet:
            if succeeded:
                ok(f"target exited cleanly ({subprocess_outcome.duration_seconds:.2f}s)")
            else:
                error(
                    f"target exited with code {subprocess_outcome.return_code} "
                    f"({subprocess_outcome.duration_seconds:.2f}s)",
                )

        return LauncherOutcome(
            exit_code=int(exit_code),
            subprocess_outcome=subprocess_outcome,
            dashboard_url=dashboard_url,
        )

    def _emit_banner(self, dashboard_url: str | None) -> None:
        config = self.config
        log("AsyncViz")
        info(f"target           {config.target.kind}={config.target.display_name()}")
        if dashboard_url is not None:
            info(f"dashboard        {dashboard_url}")
        else:
            info("dashboard        disabled (--no-dashboard)")
        info(f"instrumentation  {'on' if config.enable_instrumentation else 'off'}")
        info(f"browser          {config.browser}")


def run_target(config: RunCliConfig) -> LauncherOutcome:
    """Convenience entry point used by the ``run`` command."""
    return RunLauncher(config).launch()
