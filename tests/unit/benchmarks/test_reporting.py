"""Reporting / export tests."""

from __future__ import annotations

import json
from pathlib import Path

from asyncviz.benchmarks import (
    BenchmarkRunner,
    benchmark,
    get_registry,
    quick_config,
)
from asyncviz.benchmarks.reporting import (
    emit_ci_summary,
    suite_to_dict,
    write_json_report,
    write_markdown_report,
)


def _build_suite():  # type: ignore[no-untyped-def]
    @benchmark(name="r.one", category="synthetic")
    def bench_one() -> None:
        return None

    runner = BenchmarkRunner(config=quick_config())
    return runner.run_suite(get_registry().all())


def test_json_report_schema(tmp_path: Path) -> None:
    suite = _build_suite()
    payload = suite_to_dict(suite)
    assert payload["schema_version"] == 1
    assert "environment" in payload
    assert "results" in payload
    assert len(payload["results"]) == 1
    path = tmp_path / "report.json"
    write_json_report(path, suite)
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == 1


def test_markdown_report_contains_expected_sections(tmp_path: Path) -> None:
    suite = _build_suite()
    path = tmp_path / "report.md"
    write_markdown_report(path, suite)
    text = path.read_text(encoding="utf-8")
    assert "# AsyncViz Benchmark Report" in text
    assert "## Regression Summary" in text
    assert "## Results" in text
    assert "r.one" in text


def test_ci_summary_emits_one_line_per_benchmark() -> None:
    suite = _build_suite()
    lines = list(emit_ci_summary(suite))
    # First line is the header, second is summary; one per result follows.
    assert len(lines) >= 3
    assert "asyncviz benchmark suite" in lines[0]
    assert "summary:" in lines[1]
