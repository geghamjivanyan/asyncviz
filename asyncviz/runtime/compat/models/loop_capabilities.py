"""Frozen capability snapshot describing the active event loop.

The compatibility manager probes the loop once + freezes the result.
Capabilities are *boolean* — either the feature is present and the
runtime can use it, or it's absent and the runtime takes a documented
fallback path. The shape is intentionally narrow; adding a new
capability is one field, one probe, one default-False fallback.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.runtime.compat.models.loop_kind import LoopKind


@dataclass(frozen=True, slots=True)
class LoopCapabilities:
    """Immutable view of what the active loop can do."""

    kind: LoopKind
    implementation: str
    """Module path the loop class lives in (e.g.
    ``"asyncio.unix_events"``, ``"uvloop.loop"``)."""

    version: str
    """Free-form version identifier — ``"uvloop=0.21.0"`` /
    ``"cpython=3.13.0"``. Used by the report, never parsed."""

    supports_task_factory: bool
    supports_call_soon_threadsafe: bool
    supports_create_task: bool
    supports_run_in_executor: bool
    supports_set_debug: bool
    supports_get_clock_resolution: bool
    supports_create_unix_connection: bool
    supports_signal_handlers: bool

    monotonic_clock_resolution_ns: int
    """Best-effort clock resolution — used by the drift tolerance
    check. ``0`` when the loop refuses to disclose."""

    replay_safe: bool
    """``True`` when the loop's timing semantics match the asyncio
    contract closely enough that the replay layer can target it."""


def asyncio_baseline_capabilities() -> LoopCapabilities:
    """Conservative defaults — what stock asyncio always provides."""
    import sys

    return LoopCapabilities(
        kind=LoopKind.ASYNCIO,
        implementation="asyncio",
        version=f"cpython={sys.version.split()[0]}",
        supports_task_factory=True,
        supports_call_soon_threadsafe=True,
        supports_create_task=True,
        supports_run_in_executor=True,
        supports_set_debug=True,
        supports_get_clock_resolution=False,
        supports_create_unix_connection=True,
        supports_signal_handlers=sys.platform != "win32",
        monotonic_clock_resolution_ns=1_000,
        replay_safe=True,
    )


def unknown_capabilities() -> LoopCapabilities:
    """Returned when probing failed entirely."""
    return LoopCapabilities(
        kind=LoopKind.UNKNOWN,
        implementation="<unknown>",
        version="<unknown>",
        supports_task_factory=False,
        supports_call_soon_threadsafe=False,
        supports_create_task=False,
        supports_run_in_executor=False,
        supports_set_debug=False,
        supports_get_clock_resolution=False,
        supports_create_unix_connection=False,
        supports_signal_handlers=False,
        monotonic_clock_resolution_ns=0,
        replay_safe=False,
    )
