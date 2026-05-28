"""On-disk layout constants for the published frontend bundle.

The published bundle lives inside the ``asyncviz/dashboard/static``
package directory. Layout:

    asyncviz/dashboard/static/
    ├── index.html                          # SPA entry point.
    ├── assets/                             # Vite-emitted hashed assets.
    │   ├── index-<hash>.js
    │   └── index-<hash>.css
    ├── .vite/manifest.json                 # Vite's native manifest (if emitted).
    ├── build.json                          # AsyncViz publish manifest
    │                                       # (written by AssetPublisher).
    └── .gitkeep                            # Placeholder so git keeps the dir.

A *published* bundle satisfies the constraints in :data:`REQUIRED_FILES`
and produces a ``build.json`` whose schema version matches
:data:`ASSET_MANIFEST_VERSION`. Consumers (validator, runtime
resolver, diagnostics) all read these constants so renaming a file
ripples through one place.
"""

from __future__ import annotations

from typing import Final

#: Bumped whenever the on-disk manifest schema changes.
ASSET_MANIFEST_VERSION: Final[int] = 1

#: Filename of the asset-publish manifest, written next to ``index.html``.
ASSET_MANIFEST_FILENAME: Final[str] = "build.json"

#: Vite's native manifest path (relative to the static dir).
VITE_MANIFEST_FILENAME: Final[str] = ".vite/manifest.json"

#: SPA entry point file.
INDEX_HTML: Final[str] = "index.html"

#: Subdirectory that holds Vite's hashed assets.
ASSETS_DIRECTORY: Final[str] = "assets"

#: Files that must exist for the bundle to be considered "published".
REQUIRED_FILES: Final[tuple[str, ...]] = (INDEX_HTML,)

#: Files we always skip during publishing + validation (build noise).
IGNORED_FILES: Final[frozenset[str]] = frozenset({".DS_Store", ".gitkeep"})


def asset_relative_path(*parts: str) -> str:
    """Join path components using POSIX separators.

    All asset paths inside the manifest are POSIX-formatted so the
    bundle is portable across platforms.
    """
    return "/".join(parts)
