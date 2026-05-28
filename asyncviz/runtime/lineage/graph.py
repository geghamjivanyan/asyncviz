"""High-level graph queries over :class:`LineageTracker` state.

Kept separate so the tracker stays focused on registration/unregistration
mutations, and the read-side traversal helpers stay easy to compose.
"""

from __future__ import annotations

from collections.abc import Iterable

from asyncviz.runtime.lineage.ancestry import descendants_of, iter_subtree, roots_in


def subtree_size(
    task_id: str,
    children_of: dict[str, set[str]],
) -> int:
    """Number of nodes in the subtree rooted at ``task_id`` (inclusive)."""
    count = 0
    for _ in iter_subtree(task_id, children_of):
        count += 1
    return count


def leaves_of(
    task_id: str,
    children_of: dict[str, set[str]],
) -> list[str]:
    """Tasks in the subtree rooted at ``task_id`` that have no children."""
    return [node for node in iter_subtree(task_id, children_of) if not children_of.get(node)]


def lineage_path(
    task_id: str,
    parent_of: dict[str, str | None],
) -> list[str]:
    """Path from the root to ``task_id``, inclusive.

    Equivalent to ``[*reversed(ancestors)] + [task_id]``. Returns ``[task_id]``
    for root tasks and unknown ids alike — the latter case is the natural
    "I'm my own root" fallback.
    """
    ancestors = []
    current: str | None = task_id
    visited: set[str] = set()
    while current is not None and current not in visited:
        ancestors.append(current)
        visited.add(current)
        current = parent_of.get(current)
    ancestors.reverse()
    return ancestors


def list_roots(parent_of: dict[str, str | None]) -> list[str]:
    """Materialize :func:`asyncviz.runtime.lineage.ancestry.roots_in`."""
    return list(roots_in(parent_of))


def export_descendants(
    task_id: str,
    children_of: dict[str, set[str]],
) -> list[str]:
    """Materialized BFS descendants list (excludes ``task_id`` itself)."""
    return descendants_of(task_id, children_of)


def export_adjacency(
    children_of: dict[str, set[str]],
) -> dict[str, list[str]]:
    """JSON-safe view of the children map, with deterministic ordering."""
    return {parent: sorted(kids) for parent, kids in children_of.items() if kids}


def filter_orphans(
    parent_of: dict[str, str | None],
    known_ids: Iterable[str],
) -> list[str]:
    """Tasks whose ``parent_task_id`` references something that isn't tracked.

    Used by metrics: a positive count means events arrived out of order or
    a parent was removed before its children, both of which we want
    observability on rather than silent inconsistency.
    """
    known = set(known_ids)
    return [tid for tid, parent in parent_of.items() if parent is not None and parent not in known]
