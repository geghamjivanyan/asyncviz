"""High-level helpers to bind the recorder to a live runtime.

Lifts the boilerplate (build meta providers, fetch snapshot
functions, swallow exceptions) so the CLI bootstrap layer can wire
recording in a few lines.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from asyncviz.runtime.replay.recorder.replay_configuration import RecorderConfig
from asyncviz.runtime.replay.recorder.replay_metadata import (
    PackagingMeta,
    RuntimeMeta,
)
from asyncviz.runtime.replay.recorder.replay_recorder import ReplayRecorder


@dataclass(frozen=True, slots=True)
class TargetDescription:
    """Caller-supplied target metadata for ``meta/runtime.json``."""

    kind: str
    value: str
    argv: tuple[str, ...]


def start_recorder_for_runtime(
    config: RecorderConfig,
    *,
    runtime: object,
    target: TargetDescription,
    asyncviz_version: str,
    host: str,
    port: int,
    extras: dict[str, str] | None = None,
    runtime_options: object | None = None,
) -> ReplayRecorder:
    """Construct + start a :class:`ReplayRecorder` bound to ``runtime``.

    ``runtime`` is expected to be an :class:`AsyncVizRuntime` (it
    exposes ``services.state_store``, ``services.warning_manager``,
    etc.) — but the function only relies on duck-typed access so
    tests can pass a lightweight stand-in.
    """
    services = getattr(runtime, "services", None)
    state_store = getattr(services, "state_store", None) if services else None
    if state_store is None:
        raise RuntimeError("runtime does not expose a state_store; cannot record")

    started_at_wall = datetime.now(UTC).isoformat(timespec="seconds")
    started_at_monotonic_ns = _safe_monotonic_ns(services)
    runtime_id = _safe_runtime_id(services)

    # Project ``runtime_options`` into the metadata extras so the
    # replay bundle records the configuration the runtime was started
    # with. ``RuntimeMeta.extras`` is ``dict[str, str]``, so the
    # options tree is serialized to a JSON string under
    # ``"runtime_options_json"``.
    options_extras: dict[str, str] = {str(k): str(v) for k, v in (extras or {}).items()}
    if runtime_options is not None:
        try:
            from asyncviz.configuration import options_to_json

            options_extras["runtime_options_json"] = options_to_json(runtime_options)  # type: ignore[arg-type]
        except Exception:  # pragma: no cover — best-effort
            pass

    def runtime_meta_provider() -> RuntimeMeta:
        return RuntimeMeta(
            runtime_id=runtime_id,
            asyncviz_version=asyncviz_version,
            started_at_wall_iso=started_at_wall,
            finished_at_wall_iso=datetime.now(UTC).isoformat(timespec="seconds"),
            started_at_monotonic_ns=started_at_monotonic_ns,
            finished_at_monotonic_ns=_safe_monotonic_ns(services),
            host=host,
            port=port,
            target={
                "kind": target.kind,
                "value": target.value,
                "argv": list(target.argv),
            },
            extras=options_extras,
        )

    def packaging_meta_provider() -> PackagingMeta | None:
        try:
            from asyncviz.packaging import build_packaging_diagnostics

            return PackagingMeta(payload=build_packaging_diagnostics().to_dict())
        except Exception:  # pragma: no cover — best-effort
            return None

    runtime_snapshot_provider: Callable[[], dict | None] | None = None
    if config.capture_runtime_snapshot and state_store is not None:
        def _runtime_snapshot() -> dict | None:
            try:
                snap = state_store.snapshot()
                # The snapshot is a pydantic model; ``model_dump`` is
                # the canonical JSON-safe serializer.
                dump = getattr(snap, "model_dump", None)
                if callable(dump):
                    return dump(mode="json")
                return snap if isinstance(snap, dict) else None
            except Exception:  # pragma: no cover
                return None

        runtime_snapshot_provider = _runtime_snapshot

    warning_snapshot_provider: Callable[[], dict | None] | None = None
    if config.capture_warning_snapshot:
        emitter = getattr(services, "blocking_warning_emitter", None)
        if emitter is not None:
            def _warning_snapshot() -> dict | None:
                snapshot_fn = getattr(emitter, "snapshot", None)
                if not callable(snapshot_fn):
                    return None
                try:
                    snap = snapshot_fn()
                except Exception:  # pragma: no cover
                    return None
                dump = getattr(snap, "model_dump", None)
                if callable(dump):
                    return dump(mode="json")
                return snap if isinstance(snap, dict) else None

            warning_snapshot_provider = _warning_snapshot

    recorder = ReplayRecorder(config, state_store=state_store)
    recorder.start(
        runtime_meta=runtime_meta_provider,
        packaging_meta=packaging_meta_provider,
        runtime_snapshot=runtime_snapshot_provider,
        warning_snapshot=warning_snapshot_provider,
    )
    return recorder


def finalize_recorder(recorder: ReplayRecorder | None) -> None:
    """``stop()`` the recorder if it exists. Idempotent + exception-safe."""
    if recorder is None:
        return
    import contextlib

    with contextlib.suppress(Exception):  # pragma: no cover — best-effort
        recorder.stop()


def _safe_monotonic_ns(services: object | None) -> int:
    if services is None:
        return 0
    clock = getattr(services, "runtime_clock", None)
    if clock is None:
        return 0
    fn = getattr(clock, "monotonic_ns", None)
    if not callable(fn):
        return 0
    try:
        return int(fn())
    except Exception:
        return 0


def _safe_runtime_id(services: object | None) -> str:
    if services is None:
        return "unknown"
    clock = getattr(services, "runtime_clock", None)
    if clock is None:
        return "unknown"
    rid = getattr(clock, "runtime_id", None)
    return str(rid) if rid is not None else "unknown"
