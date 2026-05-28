"""Canonical asset resolver for the embedded AsyncViz frontend.

The package ships its compiled dashboard at
``asyncviz/dashboard/static/`` — wheel installs put it inside
``site-packages``, editable installs leave it in the source tree.
This module is the single place that knows how to locate the bundle
and verify that the embedded artifacts are present.

Resolution order:

1. ``importlib.resources.files("asyncviz.dashboard") / "static"`` —
   works for plain site-packages installs and zipapp/PyInstaller
   bundles via the :class:`importlib.abc.Traversable` interface.
2. ``Path(__file__).parent.parent / "dashboard" / "static"`` — the
   editable-install + source-checkout fallback. Hit only when
   :mod:`importlib.resources` fails, which is rare today but possible
   in frozen apps.

Callers should not poke ``__file__`` or read environment variables —
both paths are routed through :func:`locate_frontend_bundle` so the
behavior is identical regardless of how the package was installed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Literal

from asyncviz.utils.logging import get_logger

logger = get_logger("packaging.assets")

# ── Constants ────────────────────────────────────────────────────────────

_OWNER_PACKAGE = "asyncviz.dashboard"
_STATIC_DIRNAME = "static"
_INDEX_FILENAME = "index.html"
_ASSETS_DIRNAME = "assets"

#: Files that must exist for the bundle to be considered "embedded".
_REQUIRED_BUNDLE_FILES = (_INDEX_FILENAME,)

# ── Install-shape taxonomy ──────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class EditableInstall:
    """Editable / source-checkout shape — files live in the working tree."""

    kind: Literal["editable"] = "editable"


@dataclass(frozen=True, slots=True)
class PackagedInstall:
    """Wheel or sdist install — files live inside ``site-packages``."""

    kind: Literal["packaged"] = "packaged"


@dataclass(frozen=True, slots=True)
class UnknownInstall:
    """Install shape could not be classified — caller should treat as
    "best effort" and assume the bundle may or may not be present."""

    kind: Literal["unknown"] = "unknown"


InstallShape = EditableInstall | PackagedInstall | UnknownInstall
"""Tagged union summarizing where the package files actually live."""


@dataclass(frozen=True, slots=True)
class AssetResolution:
    """Result of :func:`locate_frontend_bundle`.

    Carries the resolved bundle directory + a classification of the
    install shape + whether the bundle was actually present at
    resolution time.
    """

    bundle_dir: Path
    index_path: Path
    assets_dir: Path
    install_shape: InstallShape
    is_embedded: bool
    #: Resolution audit — keeps the chosen probe path in metadata so
    #: the diagnostics endpoint can report which fallback fired.
    resolved_via: Literal["importlib.resources", "file-fallback"]
    #: Files that were expected but missing. Empty when the bundle is
    #: fully present.
    missing: tuple[str, ...] = field(default_factory=tuple)


# ── Resolution ──────────────────────────────────────────────────────────


def _classify_install(bundle_dir: Path) -> InstallShape:
    """Decide whether the package lives in site-packages or a source tree."""
    text = str(bundle_dir).replace("\\", "/")
    if "/site-packages/" in text or text.endswith("/site-packages"):
        return PackagedInstall()
    # Heuristic: a development checkout typically lives next to a
    # ``pyproject.toml`` two directories up from the bundle.
    candidate_root = bundle_dir.parent.parent.parent
    if (candidate_root / "pyproject.toml").is_file():
        return EditableInstall()
    return UnknownInstall()


def _required_missing(bundle_dir: Path) -> tuple[str, ...]:
    """Return the required-bundle files that are missing."""
    return tuple(name for name in _REQUIRED_BUNDLE_FILES if not (bundle_dir / name).is_file())


def locate_frontend_bundle() -> AssetResolution:
    """Return the canonical embedded-frontend resolution.

    The function always returns an :class:`AssetResolution` — callers
    must check :attr:`AssetResolution.is_embedded` before assuming the
    bundle exists. This keeps the runtime startup path crash-free when
    the dashboard is installed without the frontend embedded
    (api-only deployments).
    """
    bundle_dir, resolved_via = _resolve_bundle_dir()
    install_shape = _classify_install(bundle_dir)
    missing = _required_missing(bundle_dir) if bundle_dir.is_dir() else _REQUIRED_BUNDLE_FILES
    is_embedded = len(missing) == 0
    return AssetResolution(
        bundle_dir=bundle_dir,
        index_path=bundle_dir / _INDEX_FILENAME,
        assets_dir=bundle_dir / _ASSETS_DIRNAME,
        install_shape=install_shape,
        is_embedded=is_embedded,
        resolved_via=resolved_via,
        missing=missing,
    )


def _resolve_bundle_dir() -> tuple[Path, Literal["importlib.resources", "file-fallback"]]:
    """Find the bundle directory; return (path, audit-label)."""
    try:
        traversable = resources.files(_OWNER_PACKAGE) / _STATIC_DIRNAME
        return Path(str(traversable)), "importlib.resources"
    except Exception as exc:  # pragma: no cover — defensive fallback
        logger.debug("importlib.resources lookup failed: %s", exc)
        # ``assets.py`` lives at ``asyncviz/packaging/assets.py`` →
        # static dir sits at ``asyncviz/dashboard/static``.
        return (
            Path(__file__).resolve().parent.parent / "dashboard" / _STATIC_DIRNAME,
            "file-fallback",
        )


# ── Lookups + iteration ─────────────────────────────────────────────────


def resolve_frontend_asset(relative: str) -> Path | None:
    """Resolve a single asset path relative to the bundle root.

    Returns ``None`` when the requested file is outside the bundle
    (path-traversal attempt) or absent. Caller is responsible for any
    cache-control / MIME logic — this helper just does path math.
    """
    if not relative:
        return None
    resolution = locate_frontend_bundle()
    bundle_root = resolution.bundle_dir.resolve()
    candidate = (bundle_root / relative).resolve()
    try:
        candidate.relative_to(bundle_root)
    except ValueError:
        # Traversal outside the bundle.
        return None
    return candidate if candidate.is_file() else None


def bundle_files(resolution: AssetResolution | None = None) -> list[Path]:
    """Enumerate every file inside the embedded bundle.

    Used by :mod:`asyncviz.packaging.wheel_validation` + the
    diagnostics endpoint. Returns a stable, sorted list so output is
    deterministic across platforms (filesystems with arbitrary
    iteration order can otherwise leak through into reports).
    """
    res = resolution or locate_frontend_bundle()
    if not res.bundle_dir.is_dir():
        return []
    paths: list[Path] = []
    for path in res.bundle_dir.rglob("*"):
        if path.is_file() and path.name != ".gitkeep":
            paths.append(path)
    paths.sort(key=lambda p: p.as_posix())
    return paths
