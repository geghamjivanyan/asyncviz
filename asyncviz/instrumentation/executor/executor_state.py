"""Helpers that classify + inspect executor instances."""

from __future__ import annotations

import concurrent.futures
from typing import Any

from asyncviz.instrumentation.executor.executor_metadata import ExecutorKind


def classify_executor(
    executor: Any,
    *,
    is_default: bool = False,
) -> ExecutorKind:
    """Best-effort classification of ``executor``.

    Pass ``is_default=True`` for the loop's lazily-allocated default
    executor — the one ``run_in_executor(None, ...)`` falls back to.
    """
    if is_default:
        return "default"
    if isinstance(executor, concurrent.futures.ProcessPoolExecutor):
        return "Process"
    if isinstance(executor, concurrent.futures.ThreadPoolExecutor):
        return "Thread"
    if isinstance(executor, concurrent.futures.Executor):
        return "custom"
    return "unknown"


def read_max_workers(executor: Any) -> int | None:
    """Return the executor's ``_max_workers`` if exposed, else None."""
    raw = getattr(executor, "_max_workers", None)
    if isinstance(raw, int) and raw > 0:
        return raw
    return None


def read_thread_name_prefix(executor: Any) -> str | None:
    """Return the executor's ``_thread_name_prefix`` if exposed."""
    raw = getattr(executor, "_thread_name_prefix", None)
    if isinstance(raw, str) and raw:
        return raw
    return None


def read_callable_name(func: Any) -> str | None:
    """Return the callable's qualname when available."""
    name = getattr(func, "__qualname__", None) or getattr(func, "__name__", None)
    if isinstance(name, str) and name:
        return name
    return None
