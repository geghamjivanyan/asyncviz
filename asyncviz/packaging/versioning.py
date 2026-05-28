"""Package version + build-identity surface.

Single source of truth used by:

* ``asyncviz.__version__`` (so the package version stays consistent
  with the metadata FastAPI reports),
* the diagnostics endpoint (so frontend + backend version drift is
  visible at runtime),
* the CLI ``asyncviz --version`` flag (future task),
* the wheel validator (so it can cross-check the artifact name
  against the package metadata).

The implementation deliberately avoids importing the build backend
(``hatchling``) — production installs don't ship build tooling. We
read :mod:`importlib.metadata` for the installed package and fall
back to a hard-coded ``_FALLBACK_VERSION`` for the dev tree.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib import metadata
from typing import Any

from asyncviz.packaging.assets import (
    AssetResolution,
    locate_frontend_bundle,
)
from asyncviz.packaging.build_metadata import (
    BundleManifest,
    load_bundle_manifest,
)

# ── Constants ───────────────────────────────────────────────────────────

_PACKAGE_NAME = "asyncviz"
#: Sole hardcoded version literal. Mirrors ``[project].version`` in
#: ``pyproject.toml``; the only allowed drift is during a release bump
#: where pyproject + this file flip together.
_FALLBACK_VERSION = "0.1.0"


@dataclass(frozen=True, slots=True)
class BuildIdentity:
    """Operator-facing build summary.

    Distinct from :class:`PackageMetadata` because the build identity
    can change without the version changing (e.g. a hotfix rebuild) —
    keeping the two views separate makes the diagnostics endpoint
    self-describing without overloading semantics.
    """

    version: str
    commit: str | None
    timestamp: str | None
    channel: str
    frontend_version: str | None
    frontend_build_id: str | None


@dataclass(frozen=True, slots=True)
class PackageMetadata:
    """Resolved metadata for the installed AsyncViz package."""

    name: str
    version: str
    summary: str
    requires_python: str | None
    author: str | None
    homepage: str | None
    extras: tuple[str, ...]
    is_editable: bool
    build_identity: BuildIdentity
    asset_resolution: AssetResolution = field(repr=False)
    bundle_manifest: BundleManifest = field(repr=False)


# ── Public API ──────────────────────────────────────────────────────────


def package_version() -> str:
    """Return the package version, preferring installed metadata.

    Falls back to :data:`_FALLBACK_VERSION` when the package is not
    importable through :mod:`importlib.metadata` (e.g. when running
    out of a working tree that hasn't been ``pip install -e``'d).
    """
    try:
        return metadata.version(_PACKAGE_NAME)
    except metadata.PackageNotFoundError:
        return _FALLBACK_VERSION


def get_package_metadata() -> PackageMetadata:
    """Return the full package metadata bundle.

    Cheap to call — internals are pure-Python file reads. Caller can
    cache the result if it's invoked on a hot path (e.g. per-request
    diagnostics); we deliberately don't memoize so editable installs
    that rebuild the frontend always see fresh manifest data.
    """
    asset_resolution = locate_frontend_bundle()
    bundle_manifest = load_bundle_manifest(asset_resolution.bundle_dir)

    try:
        dist = metadata.distribution(_PACKAGE_NAME)
        meta = dist.metadata
        version = meta.get("Version", _FALLBACK_VERSION)
        summary = meta.get("Summary", "")
        requires_python = meta.get("Requires-Python")
        author = meta.get("Author") or meta.get("Author-email")
        homepage = _extract_homepage(meta)
        extras = tuple(dist.requires or ())
        is_editable = _is_editable(dist)
    except metadata.PackageNotFoundError:
        version = _FALLBACK_VERSION
        summary = (
            "Real-time runtime visualization and debugging platform "
            "for Python asyncio applications."
        )
        requires_python = ">=3.12"
        author = "AsyncViz"
        homepage = "https://github.com/asyncviz/asyncviz"
        extras = ()
        is_editable = True

    build_identity = _build_identity(version=version, manifest=bundle_manifest)

    return PackageMetadata(
        name=_PACKAGE_NAME,
        version=version,
        summary=summary,
        requires_python=requires_python,
        author=author,
        homepage=homepage,
        extras=extras,
        is_editable=is_editable,
        build_identity=build_identity,
        asset_resolution=asset_resolution,
        bundle_manifest=bundle_manifest,
    )


# ── Internals ───────────────────────────────────────────────────────────


def _extract_homepage(meta: Any) -> str | None:
    """Pull the Homepage URL out of a distribution's metadata.

    The metadata accessor returns either a string or a list of
    ``Project-URL`` entries depending on backend; we normalize to a
    single string or ``None``.
    """
    homepage = meta.get("Home-page")
    if homepage:
        return homepage
    # ``Project-URL`` may appear multiple times; the metadata mapping
    # exposes a ``get_all`` accessor only in some implementations.
    project_urls: list[str] = []
    get_all = getattr(meta, "get_all", None)
    if callable(get_all):
        project_urls = get_all("Project-URL") or []
    for entry in project_urls:
        if not entry:
            continue
        # Entries look like "Homepage, https://..."
        if "," in entry:
            label, _, url = entry.partition(",")
            if label.strip().lower() == "homepage":
                return url.strip()
    return None


def _is_editable(dist: metadata.Distribution) -> bool:
    """Detect editable installs (PEP 660).

    Editable installs ship a ``direct_url.json`` whose ``dir_info``
    section contains ``"editable": true``. Falling back to ``False``
    when the file is absent matches the way pip reports the state.
    """
    try:
        records = dist.read_text("direct_url.json")
    except Exception:
        return False
    if not records:
        return False
    try:
        import json

        payload = json.loads(records)
        return bool(payload.get("dir_info", {}).get("editable", False))
    except Exception:
        return False


def _build_identity(*, version: str, manifest: BundleManifest) -> BuildIdentity:
    """Compose the :class:`BuildIdentity` view.

    Env vars (``ASYNCVIZ_BUILD_COMMIT``, ``ASYNCVIZ_BUILD_TIMESTAMP``,
    ``ASYNCVIZ_BUILD_CHANNEL``) win when the release pipeline sets
    them; otherwise the values come from the bundle manifest + sane
    defaults so the diagnostics endpoint always has *something* to
    show.
    """
    commit = os.environ.get("ASYNCVIZ_BUILD_COMMIT") or manifest.commit
    timestamp = (
        os.environ.get("ASYNCVIZ_BUILD_TIMESTAMP")
        or manifest.built_at
        or datetime.now(UTC).isoformat(timespec="seconds")
    )
    channel = os.environ.get("ASYNCVIZ_BUILD_CHANNEL") or "dev"
    return BuildIdentity(
        version=version,
        commit=commit,
        timestamp=timestamp,
        channel=channel,
        frontend_version=manifest.frontend_version,
        frontend_build_id=manifest.build_id,
    )
