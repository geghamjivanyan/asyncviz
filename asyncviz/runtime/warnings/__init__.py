"""Canonical runtime warning system.

Public surface:

* :class:`RuntimeWarningManager` — the analytics + diagnostics service.
* :class:`ActiveWarning` / :class:`WarningSnapshot` — Pydantic wire models.
* :class:`WarningDelta` / :class:`WarningSubscription` — streaming types.
* :class:`WarningLifecycle` — internal mutable state (exposed for tests).
* Detectors: :class:`SlowTaskDetector`, :class:`CancellationStormDetector`,
  :class:`DeepLineageDetector`, :class:`ExcessiveActiveTasksDetector`,
  :class:`CancellationOriginDetector`.
* Deduplication: :class:`DedupDecision`, :func:`evaluate_dedup`.
* Expiration: :class:`ExpirationPolicy`.
* exceptions — :class:`WarningSystemError` and friends.

Design rule: a runtime has exactly **one** :class:`RuntimeWarningManager`,
hooked to the :class:`RuntimeStateStore` via ``manager.bind(store)`` and
optionally driven against the :class:`RuntimeMetricsAggregator` for
aggregate-level detectors.
"""

from asyncviz.runtime.warnings.deduplication import (
    DedupDecision,
    DedupResult,
    evaluate_dedup,
)
from asyncviz.runtime.warnings.detectors import (
    CancellationOriginDetector,
    CancellationStormDetector,
    DeepLineageDetector,
    DetectorContext,
    ExcessiveActiveTasksDetector,
    SlowTaskDetector,
    WarningDetector,
    default_detectors,
)
from asyncviz.runtime.warnings.exceptions import (
    DetectorRegistrationError,
    UnknownWarningError,
    WarningRebuildError,
    WarningSystemError,
)
from asyncviz.runtime.warnings.expiration import (
    DEFAULT_TTL_SECONDS,
    ExpirationPolicy,
)
from asyncviz.runtime.warnings.lifecycle import WarningLifecycle, fresh_warning_id
from asyncviz.runtime.warnings.manager import RuntimeWarningManager
from asyncviz.runtime.warnings.models import (
    ActiveWarning,
    WarningDeltaModel,
    WarningSelfMetricsModel,
    WarningSeverityCounts,
    WarningSnapshot,
)
from asyncviz.runtime.warnings.normalization import (
    WarningTrigger,
    is_terminal_task_event,
)
from asyncviz.runtime.warnings.projections import (
    count_by_severity,
    count_by_type,
    group_by_lineage,
    group_by_task,
)
from asyncviz.runtime.warnings.queries import WarningQueryService
from asyncviz.runtime.warnings.severity import (
    SEVERITY_ORDER,
    WarningSeverity,
    is_at_least,
    max_severity,
    severity_rank,
)
from asyncviz.runtime.warnings.snapshots import (
    build_warning_snapshot,
    lifecycle_to_active,
)
from asyncviz.runtime.warnings.streaming import (
    WarningChange,
    WarningDelta,
    WarningListener,
    WarningSubscription,
    WarningSubscriptionRegistry,
)

__all__ = [
    "DEFAULT_TTL_SECONDS",
    "SEVERITY_ORDER",
    "ActiveWarning",
    "CancellationOriginDetector",
    "CancellationStormDetector",
    "DedupDecision",
    "DedupResult",
    "DeepLineageDetector",
    "DetectorContext",
    "DetectorRegistrationError",
    "ExcessiveActiveTasksDetector",
    "ExpirationPolicy",
    "RuntimeWarningManager",
    "SlowTaskDetector",
    "UnknownWarningError",
    "WarningChange",
    "WarningDelta",
    "WarningDeltaModel",
    "WarningDetector",
    "WarningLifecycle",
    "WarningListener",
    "WarningQueryService",
    "WarningRebuildError",
    "WarningSelfMetricsModel",
    "WarningSeverity",
    "WarningSeverityCounts",
    "WarningSnapshot",
    "WarningSubscription",
    "WarningSubscriptionRegistry",
    "WarningSystemError",
    "WarningTrigger",
    "build_warning_snapshot",
    "count_by_severity",
    "count_by_type",
    "default_detectors",
    "evaluate_dedup",
    "fresh_warning_id",
    "group_by_lineage",
    "group_by_task",
    "is_at_least",
    "is_terminal_task_event",
    "lifecycle_to_active",
    "max_severity",
    "severity_rank",
]
