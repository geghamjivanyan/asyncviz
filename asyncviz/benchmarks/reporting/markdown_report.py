"""Markdown summary suitable for PR comments + standalone reading."""

from __future__ import annotations

from pathlib import Path

from asyncviz.benchmarks.benchmark_models import BenchmarkSuiteResult
from asyncviz.benchmarks.benchmark_thresholds import (
    label_for,
    summarize_regressions,
)


def render_markdown(suite: BenchmarkSuiteResult) -> str:
    summary = summarize_regressions(suite)
    lines: list[str] = []
    env = suite.environment
    lines.append("# AsyncViz Benchmark Report")
    lines.append("")
    lines.append(f"- Python: `{env.python_version}`")
    lines.append(f"- Platform: `{env.platform}`")
    lines.append(f"- AsyncViz: `{env.asyncviz_version}`")
    lines.append(f"- CPU count: `{env.cpu_count}`")
    lines.append(f"- Asyncio loop: `{env.asyncio_loop}`")
    lines.append("")
    lines.append("## Regression Summary")
    lines.append("")
    lines.append(f"- ✓ Improved: **{summary.improved}**")
    lines.append(f"- = Stable: **{summary.stable}**")
    lines.append(f"- ✗ Regressed: **{summary.regressed}**")
    lines.append(f"- · No baseline: **{summary.no_baseline}**")
    if summary.worst_regression is not None:
        worst = summary.worst_regression
        lines.append(
            f"- ⚠️ Worst regression: **{worst.spec_name}** ({worst.delta_ratio:+.1%} vs baseline)",
        )
    lines.append("")
    lines.append("## Results")
    lines.append("")
    header = (
        "| Benchmark | Category | Status | p50 (µs) | p95 (µs) "
        "| p99 (µs) | Samples | CV | Verdict |"
    )
    lines.append(header)
    lines.append("|---|---|---|---:|---:|---:|---:|---:|---|")
    for result in suite.results:
        outcome = result.outcome
        stats = outcome.statistics
        verdict_text = (
            label_for(result.comparison.verdict) if result.comparison is not None else "—"
        )
        if stats is None:
            lines.append(
                f"| `{outcome.spec_name}` | {outcome.category} | "
                f"{outcome.status} | — | — | — | — | — | {verdict_text} |",
            )
            continue
        lines.append(
            f"| `{outcome.spec_name}` | {outcome.category} | {outcome.status} | "
            f"{stats.median_ns / 1_000:.2f} | "
            f"{stats.p95_ns / 1_000:.2f} | "
            f"{stats.p99_ns / 1_000:.2f} | "
            f"{stats.sample_count} | "
            f"{stats.coefficient_of_variation:.3f} | "
            f"{verdict_text} |",
        )
    lines.append("")
    if suite.failures:
        lines.append("## Failures")
        lines.append("")
        for result in suite.failures:
            lines.append(
                f"- **{result.outcome.spec_name}** "
                f"({result.outcome.status}): {result.outcome.error_detail}",
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def write_markdown_report(path: Path, suite: BenchmarkSuiteResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(suite), encoding="utf-8")
