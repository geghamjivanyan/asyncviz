"""Typed configuration for :class:`FrontendServingService`.

Wraps the :class:`AsyncVizConfig.frontend_mode` literal in a richer
shape so the service stays decoupled from the global config and can
be exercised with custom directories in tests without monkey-patching
module-level constants.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from asyncviz.config import FrontendMode
from asyncviz.dashboard.frontend_serving.packaging import locate_static_dir


@dataclass(frozen=True, slots=True)
class FrontendServingConfig:
    """How the service should locate and serve the frontend bundle.

    ``static_dir`` defaults to the package-discovered location so the
    common path is "construct the config with no args". Tests override
    it directly to point at a temp directory; the service itself never
    reads global module state.
    """

    static_dir: Path
    mode: FrontendMode = "auto"

    @classmethod
    def default(cls, *, mode: FrontendMode = "auto") -> FrontendServingConfig:
        """Build a config with the package-discovered static directory."""
        return cls(static_dir=locate_static_dir(), mode=mode)

    @property
    def index_path(self) -> Path:
        return self.static_dir / "index.html"

    @property
    def assets_dir(self) -> Path:
        return self.static_dir / "assets"

    @property
    def manifest_path(self) -> Path:
        """Vite emits its manifest at ``.vite/manifest.json`` when enabled.

        The path is computed unconditionally — the service checks
        :attr:`Path.is_file` before reading and falls back to
        filesystem discovery when the manifest is absent.
        """
        return self.static_dir / ".vite" / "manifest.json"

    def is_bundle_present(self) -> bool:
        """``True`` when the bundle's ``index.html`` exists on disk."""
        return self.index_path.is_file()
