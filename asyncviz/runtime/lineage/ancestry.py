"""Pure-function helpers for walking the lineage graph.

Kept separate from :class:`LineageTracker` so the algorithmic bits can be
tested in isolation against a dict-of-sets adjacency representation.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Iterator

from asyncviz.runtime.lineage.exceptions import LineageDepthExceededError

#: Defensive cap. Practical asyncio workloads stay under a few hundred deep;
#: a higher number would only ever fire on instrumentation bugs or replay
#: corruption.
DEFAULT_MAX_DEPTH: int = 8192


def walk_ancestors(
    task_id: str,
    parent_of: dict[str, str | None],
    *,
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> Iterator[str]:
    """Yield ``task_id``'s ancestors, closest-first.

    Walks ``parent_of`` iteratively. Guards against cycles by counting steps;
    if the walk exceeds ``max_depth`` it raises
    :class:`LineageDepthExceededError`. The walk terminates at the first
    ``None`` parent (root reached).
    """
    visited: set[str] = set()
    current = parent_of.get(task_id)
    steps = 0
    while current is not None:
        if current in visited:
            # Cycle detected. We were the caller's invariant violation; raise
            # so it surfaces in tests and metrics rather than hanging.
            raise LineageDepthExceededError(
                f"cycle detected at {current!r} while walking ancestors of {task_id!r}"
            )
        if steps >= max_depth:
            raise LineageDepthExceededError(
                f"ancestry depth ceiling ({max_depth}) exceeded for {task_id!r}"
            )
        visited.add(current)
        yield current
        current = parent_of.get(current)
        steps += 1


def compute_root(
    task_id: str,
    parent_of: dict[str, str | None],
    *,
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> str:
    """Return the topmost ancestor of ``task_id`` (or ``task_id`` itself when root)."""
    last_seen = task_id
    for ancestor in walk_ancestors(task_id, parent_of, max_depth=max_depth):
        last_seen = ancestor
    return last_seen


def compute_depth(
    task_id: str,
    parent_of: dict[str, str | None],
    *,
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> int:
    """Distance to the root: ``0`` for roots, ``1`` for direct children, …"""
    depth = 0
    for _ in walk_ancestors(task_id, parent_of, max_depth=max_depth):
        depth += 1
    return depth


def iter_subtree(
    task_id: str,
    children_of: dict[str, set[str]],
) -> Iterator[str]:
    """BFS iterator over ``task_id`` and all its descendants.

    Visits every descendant exactly once. Iterative (no recursion) so deeply
    nested trees don't blow the stack.
    """
    queue: deque[str] = deque([task_id])
    seen: set[str] = set()
    while queue:
        node = queue.popleft()
        if node in seen:
            continue
        seen.add(node)
        yield node
        for child in children_of.get(node, ()):
            if child not in seen:
                queue.append(child)


def descendants_of(
    task_id: str,
    children_of: dict[str, set[str]],
) -> list[str]:
    """All descendants of ``task_id`` (excluding ``task_id`` itself), BFS order."""
    return [node for node in iter_subtree(task_id, children_of) if node != task_id]


def detect_cycle(
    candidate_parent: str,
    candidate_child: str,
    parent_of: dict[str, str | None],
    *,
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> bool:
    """``True`` iff registering ``candidate_child`` under ``candidate_parent`` would form a cycle.

    Specifically: the child cannot already be (transitively) an ancestor of
    the candidate parent. Self-parenting is also a cycle.
    """
    if candidate_parent == candidate_child:
        return True
    if candidate_parent not in parent_of:
        return False  # parent isn't tracked → can't be in a cycle yet
    try:
        for ancestor in walk_ancestors(candidate_parent, parent_of, max_depth=max_depth):
            if ancestor == candidate_child:
                return True
    except LineageDepthExceededError:
        # Already broken; treat as cycle so the caller bails out.
        return True
    return False


def ancestors_tuple(
    task_id: str,
    parent_of: dict[str, str | None],
    *,
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> tuple[str, ...]:
    """Materialize :func:`walk_ancestors` into an immutable tuple (closest-first)."""
    return tuple(walk_ancestors(task_id, parent_of, max_depth=max_depth))


def roots_in(parent_of: dict[str, str | None]) -> Iterable[str]:
    """Tasks whose ``parent_task_id`` is ``None``."""
    return (tid for tid, parent in parent_of.items() if parent is None)
