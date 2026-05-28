"""Canonical static frontend serving for AsyncViz.

Public surface:

* :class:`FrontendServingService` — orchestrator that resolves the
  embedded bundle, builds the manifest, and mounts SPA + asset
  routes onto a FastAPI app.
* :class:`FrontendServingConfig` — typed wrapper around
  ``frontend_mode`` + the static directory path.
* :class:`AssetResolver` — path-safe filesystem lookup.
* :class:`FrontendManifest` / :class:`ManifestEntry` — build manifest
  view (Vite manifest.json or a synthetic filesystem scan).
* :class:`CachePolicy` + ``CACHE_*`` constants — cache-control header
  taxonomy.
* :class:`FrontendServingMetrics` / :class:`FrontendServingMetricsSnapshot`
  — observability counters.
* Pydantic wire models — :class:`FrontendInfoResponse`,
  :class:`FrontendServingMetricsResponse`,
  :class:`FrontendManifestEntry`,
  :const:`FRONTEND_PROTOCOL_VERSION`.
* exceptions — :class:`FrontendServingError`,
  :class:`FrontendBundleMissingError`, :class:`ManifestLoadError`,
  :class:`PathTraversalRejectedError`.
"""

from asyncviz.dashboard.frontend_serving.assets import (
    AssetResolver,
    ResolvedAsset,
)
from asyncviz.dashboard.frontend_serving.cache import (
    CACHE_IMMUTABLE,
    CACHE_NO_CACHE,
    CACHE_SHORT,
    CachePolicy,
    header_for,
)
from asyncviz.dashboard.frontend_serving.configuration import (
    FrontendServingConfig,
)
from asyncviz.dashboard.frontend_serving.exceptions import (
    FrontendBundleMissingError,
    FrontendServingError,
    ManifestLoadError,
    PathTraversalRejectedError,
)
from asyncviz.dashboard.frontend_serving.manifest import (
    FrontendManifest,
    ManifestEntry,
    discover_manifest,
    load_manifest,
)
from asyncviz.dashboard.frontend_serving.metrics import (
    FrontendServingMetrics,
    FrontendServingMetricsSnapshot,
)
from asyncviz.dashboard.frontend_serving.models import (
    FRONTEND_PROTOCOL_VERSION,
    FrontendInfoResponse,
    FrontendManifestEntry,
    FrontendServingMetricsResponse,
)
from asyncviz.dashboard.frontend_serving.packaging import locate_static_dir
from asyncviz.dashboard.frontend_serving.service import FrontendServingService
from asyncviz.dashboard.frontend_serving.spa import (
    RESERVED_PREFIXES,
    is_reserved_path,
)

__all__ = [
    "CACHE_IMMUTABLE",
    "CACHE_NO_CACHE",
    "CACHE_SHORT",
    "FRONTEND_PROTOCOL_VERSION",
    "RESERVED_PREFIXES",
    "AssetResolver",
    "CachePolicy",
    "FrontendBundleMissingError",
    "FrontendInfoResponse",
    "FrontendManifest",
    "FrontendManifestEntry",
    "FrontendServingConfig",
    "FrontendServingError",
    "FrontendServingMetrics",
    "FrontendServingMetricsResponse",
    "FrontendServingMetricsSnapshot",
    "FrontendServingService",
    "ManifestEntry",
    "ManifestLoadError",
    "PathTraversalRejectedError",
    "ResolvedAsset",
    "discover_manifest",
    "header_for",
    "is_reserved_path",
    "load_manifest",
    "locate_static_dir",
]
