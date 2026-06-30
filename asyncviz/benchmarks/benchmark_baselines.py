"""Baseline persistence + comparison.

A baseline is a JSON file mapping benchmark names → p95 ns. The
runner consumes this via :meth:`BenchmarkRunner.set_baselines`; the
CLI writes one out after a clean run so subsequent runs have
something to compare against.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from asyncviz.benchmarks.benchmark_models import BenchmarkSuiteResult

BASELINE_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class BaselineFile:
    """Parsed view of a baseline JSON."""

    schema_version: int
    captured_at_wall_ns: int
    asyncviz_version: str
    p95_ns_by_name: dict[str, int]
    metadata: dict[str, str] = field(default_factory=dict)

    def get(self, name: str) -> int | None:
        return self.p95_ns_by_name.get(name)


def write_baseline(
    path: Path,
    suite: BenchmarkSuiteResult,
    *,
    metadata: dict[str, str] | None = None,
) -> BaselineFile:
    """Build a baseline file from a suite result + persist it."""
    p95_map = {
        result.outcome.spec_name: result.outcome.statistics.p95_ns
        for result in suite.results
        if result.outcome.statistics is not None and result.outcome.status == "ok"
    }
    baseline = BaselineFile(
        schema_version=BASELINE_SCHEMA_VERSION,
        captured_at_wall_ns=time.time_ns(),
        asyncviz_version=suite.environment.asyncviz_version,
        p95_ns_by_name=p95_map,
        metadata=dict(metadata or {}),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": baseline.schema_version,
        "captured_at_wall_ns": baseline.captured_at_wall_ns,
        "asyncviz_version": baseline.asyncviz_version,
        "p95_ns_by_name": baseline.p95_ns_by_name,
        "metadata": baseline.metadata,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return baseline


def read_baseline(path: Path) -> BaselineFile | None:
    """Read a baseline file. Returns ``None`` if missing."""
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    schema = int(raw.get("schema_version", 0))
    if schema != BASELINE_SCHEMA_VERSION:
        raise ValueError(
            f"baseline at {path} has schema_version={schema} (expected {BASELINE_SCHEMA_VERSION})",
        )
    return BaselineFile(
        schema_version=schema,
        captured_at_wall_ns=int(raw.get("captured_at_wall_ns", 0)),
        asyncviz_version=str(raw.get("asyncviz_version", "")),
        p95_ns_by_name={str(k): int(v) for k, v in raw.get("p95_ns_by_name", {}).items()},
        metadata={str(k): str(v) for k, v in raw.get("metadata", {}).items()},
    )
