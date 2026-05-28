"""Compose the warning snapshot from the manager's working set."""

from __future__ import annotations

from collections.abc import Iterable

from asyncviz.runtime.clock import RuntimeClock
from asyncviz.runtime.warnings.lifecycle import WarningLifecycle
from asyncviz.runtime.warnings.models import (
    ActiveWarning,
    WarningSelfMetricsModel,
    WarningSnapshot,
)
from asyncviz.runtime.warnings.projections import count_by_severity, count_by_type


def lifecycle_to_active(lifecycle: WarningLifecycle) -> ActiveWarning:
    """Materialize a Pydantic :class:`ActiveWarning` from working state."""
    return ActiveWarning(
        warning_id=lifecycle.warning_id,
        warning_key=lifecycle.warning_key,
        warning_type=lifecycle.warning_type,
        severity=lifecycle.severity,
        message=lifecycle.message,
        detector=lifecycle.detector,
        created_sequence=lifecycle.created_sequence,
        created_monotonic_ns=lifecycle.created_monotonic_ns,
        created_at_wall=lifecycle.created_at_wall,
        last_observed_sequence=lifecycle.last_observed_sequence,
        last_observed_monotonic_ns=lifecycle.last_observed_monotonic_ns,
        last_observed_wall=lifecycle.last_observed_wall,
        occurrence_count=lifecycle.occurrence_count,
        resolved=lifecycle.resolved,
        resolved_sequence=lifecycle.resolved_sequence,
        resolved_monotonic_ns=lifecycle.resolved_monotonic_ns,
        resolved_at_wall=lifecycle.resolved_at_wall,
        expired=lifecycle.expired,
        related_task_ids=list(lifecycle.related_task_ids),
        lineage_root_id=lifecycle.lineage_root_id,
        metadata=dict(lifecycle.metadata),
        runtime_id=lifecycle.runtime_id,
    )


def build_warning_snapshot(
    active: Iterable[WarningLifecycle],
    resolved: Iterable[WarningLifecycle],
    self_metrics: WarningSelfMetricsModel,
    clock: RuntimeClock,
    *,
    last_sequence: int,
) -> WarningSnapshot:
    """Compose the canonical :class:`WarningSnapshot` from working state."""
    active_list = sorted(
        active,
        key=lambda w: (-_severity_rank_value(w), w.created_monotonic_ns, w.warning_id),
    )
    resolved_list = sorted(
        resolved,
        key=lambda w: (w.resolved_monotonic_ns or 0, w.warning_id),
    )

    counts_severity = count_by_severity(active_list)
    counts_type = count_by_type(active_list)

    active_models = [lifecycle_to_active(w) for w in active_list]
    resolved_models = [lifecycle_to_active(w) for w in resolved_list]

    return WarningSnapshot(
        generated_at=clock.now(),
        generated_at_monotonic_ns=clock.monotonic_ns(),
        runtime_id=str(clock.runtime_id),
        last_sequence=last_sequence,
        active=active_models,
        resolved=resolved_models,
        counts_by_severity=counts_severity,
        counts_by_type=counts_type,
        self_metrics=self_metrics,
    )


def _severity_rank_value(lifecycle: WarningLifecycle) -> int:
    from asyncviz.runtime.warnings.severity import severity_rank

    return severity_rank(lifecycle.severity)
