"""Build-manifest discovery for the embedded frontend.

Vite emits ``dist/.vite/manifest.json`` when its ``build.manifest``
option is on. If that file is present we read it; if not, we scan
the assets directory and infer a synthetic manifest from filenames.
Either way the consumer (diagnostics endpoint, future
build-version display) sees the same :class:`FrontendManifest` shape.

The synthetic fallback lets the rest of the system rely on a single
"manifest exists" abstraction even before the frontend is reconfigured
to emit a real one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from asyncviz.dashboard.frontend_serving.exceptions import ManifestLoadError
from asyncviz.utils.logging import get_logger

logger = get_logger("dashboard.frontend_serving.manifest")


@dataclass(frozen=True, slots=True)
class ManifestEntry:
    """One entry in the build manifest.

    ``file`` is the relative path under the static root (e.g.
    ``assets/index-AbC123.js``). ``is_entry`` flags the top-level
    SPA bootstrap module — the bundle browsers load first.
    """

    file: str
    name: str
    is_entry: bool = False
    css: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class FrontendManifest:
    """Resolved view of the frontend build manifest.

    ``source`` is the audit string that tells operators where the
    manifest came from: ``"vite"`` for a real Vite manifest, ``"scan"``
    for the synthetic fallback, ``"missing"`` when neither path
    succeeded.
    """

    source: str
    entries: tuple[ManifestEntry, ...] = field(default_factory=tuple)

    @property
    def entry(self) -> ManifestEntry | None:
        """The primary entry module, if one is marked."""
        for entry in self.entries:
            if entry.is_entry:
                return entry
        return self.entries[0] if self.entries else None

    @property
    def js_files(self) -> tuple[str, ...]:
        return tuple(e.file for e in self.entries if e.file.endswith(".js"))

    @property
    def css_files(self) -> tuple[str, ...]:
        return tuple(e.file for e in self.entries if e.file.endswith(".css"))

    @property
    def is_empty(self) -> bool:
        return len(self.entries) == 0


def load_manifest(manifest_path: Path, *, static_dir: Path) -> FrontendManifest:
    """Load the Vite manifest at ``manifest_path``.

    Returns the :class:`FrontendManifest`. Raises
    :class:`ManifestLoadError` if the file exists but is unparseable —
    the service catches and degrades.
    """
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestLoadError(
            f"failed to read Vite manifest at {manifest_path!s}: {exc}"
        ) from exc

    if not isinstance(raw, dict):
        raise ManifestLoadError(f"Vite manifest at {manifest_path!s} is not a JSON object")

    entries: list[ManifestEntry] = []
    for name, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        file = entry.get("file")
        if not isinstance(file, str):
            continue
        css = tuple(c for c in entry.get("css", []) if isinstance(c, str))
        is_entry = bool(entry.get("isEntry", False))
        entries.append(ManifestEntry(file=file, name=name, is_entry=is_entry, css=css))

    # Deterministic ordering: entry first, then alphabetical by file.
    entries.sort(key=lambda e: (not e.is_entry, e.file))
    logger.debug(
        "loaded Vite manifest at %s (%d entries) for %s",
        manifest_path,
        len(entries),
        static_dir,
    )
    return FrontendManifest(source="vite", entries=tuple(entries))


def discover_manifest(static_dir: Path, assets_dir: Path) -> FrontendManifest:
    """Build a synthetic manifest by scanning ``assets_dir``.

    Used when no Vite manifest is on disk. Marks the first ``.js``
    file as the entry module — Vite hashed bundles are unambiguous in
    a single-entry app, which is the only deployment shape AsyncViz
    supports today.
    """
    if not assets_dir.is_dir():
        return FrontendManifest(source="missing", entries=())

    files = sorted(child.name for child in assets_dir.iterdir() if child.is_file())
    if not files:
        return FrontendManifest(source="missing", entries=())

    entries: list[ManifestEntry] = []
    first_js_seen = False
    for name in files:
        rel = f"{assets_dir.name}/{name}"
        is_entry = False
        if name.endswith(".js") and not first_js_seen:
            is_entry = True
            first_js_seen = True
        entries.append(ManifestEntry(file=rel, name=name, is_entry=is_entry))
    # Same ordering rule as ``load_manifest`` so the wire shape is
    # consistent regardless of which path produced it.
    entries.sort(key=lambda e: (not e.is_entry, e.file))
    logger.debug("discovered synthetic manifest from %s (%d entries)", assets_dir, len(entries))
    return FrontendManifest(source="scan", entries=tuple(entries))
