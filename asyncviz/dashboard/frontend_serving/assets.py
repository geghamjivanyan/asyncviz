"""Path-safe asset lookup for the static frontend bundle.

A single :class:`AssetResolver` handles every filesystem question the
service has to answer: "does this path resolve inside the static
root?", "does the file exist?", "is it an immutable hashed asset or
a loose stable-URL file?".

Resolution is intentionally minimal — no streaming, no negotiation,
no precompressed-variant lookup yet. Those plug in here when needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from asyncviz.dashboard.frontend_serving.cache import CachePolicy
from asyncviz.dashboard.frontend_serving.exceptions import (
    PathTraversalRejectedError,
)


@dataclass(frozen=True, slots=True)
class ResolvedAsset:
    """One successful resolution. Carries the on-disk path + cache policy.

    ``relative`` is the path under the static root (used by the
    diagnostics endpoint to surface "what was served"); ``policy``
    drives the ``Cache-Control`` header.
    """

    path: Path
    relative: str
    policy: CachePolicy


class AssetResolver:
    """Resolve request paths against a fixed static root.

    The root is captured at construction. The resolver doesn't reload
    the directory between requests — bundles are immutable for the
    lifetime of a deployment, and a redeploy restarts the process.
    """

    __slots__ = ("_assets_dirname", "_static_dir", "_static_resolved")

    def __init__(self, static_dir: Path, *, assets_dirname: str = "assets") -> None:
        self._static_dir = static_dir
        # ``resolve()`` collapses ``..`` and symlinks so the containment
        # check at lookup time is a pure prefix comparison.
        self._static_resolved = static_dir.resolve()
        self._assets_dirname = assets_dirname

    @property
    def static_dir(self) -> Path:
        return self._static_dir

    @property
    def assets_dir(self) -> Path:
        return self._static_dir / self._assets_dirname

    @property
    def index_path(self) -> Path:
        return self._static_dir / "index.html"

    def is_assets_path(self, relative: str) -> bool:
        """Whether ``relative`` lives inside ``/assets/``.

        Used to decide between an immutable-cache response and a short
        cache for loose files (favicon, etc.).
        """
        return relative.startswith(f"{self._assets_dirname}/")

    def resolve(self, relative: str) -> ResolvedAsset | None:
        """Look up ``relative`` inside the static root.

        Returns ``None`` if no file matches. Raises
        :class:`PathTraversalRejectedError` if the resolved path
        escapes the root — callers translate that into a 404.

        ``relative`` is the path stripped of its leading slash. An
        empty string resolves to ``index.html``.
        """
        if not relative:
            return self._resolve_index()

        candidate = (self._static_dir / relative).resolve()
        try:
            candidate.relative_to(self._static_resolved)
        except ValueError as exc:
            # Path escaped the static root — refuse loudly.
            raise PathTraversalRejectedError(
                f"resolved path {candidate!s} escapes static root {self._static_resolved!s}"
            ) from exc

        if not candidate.is_file():
            return None

        if self.is_assets_path(relative):
            policy = CachePolicy.IMMUTABLE
        elif relative == "index.html":
            policy = CachePolicy.NO_CACHE
        else:
            policy = CachePolicy.SHORT
        return ResolvedAsset(path=candidate, relative=relative, policy=policy)

    def _resolve_index(self) -> ResolvedAsset | None:
        index = self.index_path
        if not index.is_file():
            return None
        return ResolvedAsset(path=index, relative="index.html", policy=CachePolicy.NO_CACHE)

    def has_bundle(self) -> bool:
        """``True`` when the bundle's ``index.html`` exists."""
        return self.index_path.is_file()

    def has_assets_dir(self) -> bool:
        return self.assets_dir.is_dir()

    def asset_count(self) -> int:
        """Count of files directly inside ``/assets/``.

        Used by the diagnostics endpoint. Returns ``0`` if no assets
        directory is present.
        """
        if not self.has_assets_dir():
            return 0
        return sum(1 for child in self.assets_dir.iterdir() if child.is_file())

    def asset_size_bytes(self) -> int:
        """Total bytes across every direct child of ``/assets/``.

        Operationally useful for spotting bundle bloat across
        deployments.
        """
        if not self.has_assets_dir():
            return 0
        return sum(child.stat().st_size for child in self.assets_dir.iterdir() if child.is_file())

    def asset_names(self) -> list[str]:
        """Sorted list of asset basenames under ``/assets/``.

        Stable ordering so the diagnostics payload doesn't churn
        between calls.
        """
        if not self.has_assets_dir():
            return []
        return sorted(child.name for child in self.assets_dir.iterdir() if child.is_file())
