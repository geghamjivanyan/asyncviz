"""Resilience integration scenario.

Drives the live :class:`RuntimeFailureManager` through a sequence of
faults + confirms the documented behaviour holds at the integration
boundary:

* replay corruption → quarantine + mode unchanged,
* reducer storm → breaker open → ``degraded``,
* recorder collapse → breaker open → ``emergency`` + data-loss
  events tracked.
"""

from __future__ import annotations

import contextlib

from asyncviz.runtime.resilience import (  # type: ignore[import-not-found]
    RuntimeFailureManager,
)
from tests.integration.harness.scenario_context import IntegrationContext


async def run_resilience_integration(context: IntegrationContext) -> None:
    mgr = RuntimeFailureManager()

    replay = mgr.replay()
    with contextlib.suppress(ValueError), replay.isolate_decode(payload_kind="frame-corrupted"):
        raise ValueError("corrupted-frame: bad checksum")
    context.record(
        "operation",
        f"replay-quarantine={replay.quarantined_frames()}",
    )

    for index in range(20):
        with mgr.boundary("reducer", payload_kind=f"r-{index}"):
            raise TimeoutError("reducer timeout")
    context.record("overload", f"reducer-mode={mgr.mode()}")

    recorder = mgr.recorder()
    for index in range(8):
        with recorder.isolate_write(payload_kind=f"chk-{index}"):
            raise OSError(28, "no space")
    context.record("emergency", f"recorder-mode={mgr.mode()}")
    context.record(
        "custom",
        f"data-loss={recorder.data_loss_events()}",
        value=float(recorder.data_loss_events()),
    )

    diag = mgr.diagnostics()
    context.record(
        "custom",
        f"breaker-trips={diag.metrics.breaker_trips}",
        value=float(diag.metrics.breaker_trips),
    )
