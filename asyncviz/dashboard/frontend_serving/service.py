"""Canonical static frontend serving orchestrator.

The :class:`FrontendServingService` is the single place that knows
about: where the bundle lives, what its manifest says, which cache
policy applies, and how to wire the SPA catch-all into a FastAPI
app. The dashboard's :func:`create_app` constructs one of these and
calls :meth:`mount`; nothing else needs to know about static files.

Tests construct the service directly with a tmp-dir-rooted config to
exercise the full routing matrix without touching the embedded
bundle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from asyncviz.dashboard.frontend_serving.assets import AssetResolver, ResolvedAsset
from asyncviz.dashboard.frontend_serving.cache import (
    CACHE_IMMUTABLE,
    CACHE_NO_CACHE,
    CachePolicy,
    header_for,
)
from asyncviz.dashboard.frontend_serving.configuration import FrontendServingConfig
from asyncviz.dashboard.frontend_serving.exceptions import (
    PathTraversalRejectedError,
)
from asyncviz.dashboard.frontend_serving.manifest import (
    FrontendManifest,
    discover_manifest,
    load_manifest,
)
from asyncviz.dashboard.frontend_serving.metrics import FrontendServingMetrics
from asyncviz.dashboard.frontend_serving.spa import is_reserved_path
from asyncviz.utils.logging import get_logger

if TYPE_CHECKING:
    from asyncviz.dashboard.frontend_serving.metrics import (
        FrontendServingMetricsSnapshot,
    )

logger = get_logger("dashboard.frontend_serving.service")


class _ImmutableStaticFiles(StaticFiles):
    """``StaticFiles`` that pins ``Cache-Control: immutable`` on every 2xx.

    Safe because the directory only contains Vite content-hashed
    filenames — any change produces a new URL, so aggressive caching
    is correct.
    """

    def __init__(
        self,
        *args,
        metrics: FrontendServingMetrics | None = None,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._metrics = metrics

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if self._metrics is not None:
            self._metrics.record_asset_request()
            if 200 <= response.status_code < 300:
                self._metrics.record_immutable_hit()
            else:
                self._metrics.record_asset_miss()
        if response.status_code == 200:
            response.headers["Cache-Control"] = CACHE_IMMUTABLE
        return response


class FrontendServingService:
    """Wire the embedded SPA into a FastAPI app.

    Lifecycle:

    * Construct with a :class:`FrontendServingConfig`. The service
      builds an :class:`AssetResolver` and resolves the build manifest
      eagerly. Manifest resolution failures degrade gracefully — the
      service still serves the bundle; it just reports
      ``manifest_source="missing"``.
    * Call :meth:`mount` once at app construction time. After mount
      the FastAPI app routes ``/assets/*`` through ``StaticFiles`` and
      every other unmatched request through the SPA catch-all.

    Tests construct the service with a tmp-dir config + call
    :meth:`mount` against a fresh FastAPI to exercise the full routing
    matrix without monkey-patching module-level state.
    """

    def __init__(self, config: FrontendServingConfig) -> None:
        self._config = config
        self._metrics = FrontendServingMetrics()
        self._resolver = AssetResolver(config.static_dir)
        self._manifest: FrontendManifest = self._resolve_manifest()
        self._mounted: bool = False

    # ── identity ─────────────────────────────────────────────────────
    @property
    def config(self) -> FrontendServingConfig:
        return self._config

    @property
    def resolver(self) -> AssetResolver:
        return self._resolver

    @property
    def manifest(self) -> FrontendManifest:
        return self._manifest

    @property
    def metrics(self) -> FrontendServingMetrics:
        return self._metrics

    @property
    def is_mounted(self) -> bool:
        return self._mounted

    def metrics_snapshot(self) -> FrontendServingMetricsSnapshot:
        return self._metrics.snapshot()

    # ── manifest resolution ──────────────────────────────────────────
    def _resolve_manifest(self) -> FrontendManifest:
        """Try the Vite manifest first; fall back to filesystem scan.

        A bundled deployment without a real manifest still gets a
        non-empty :class:`FrontendManifest` — the source field
        distinguishes ``"vite"`` from ``"scan"``.
        """
        manifest_path = self._config.manifest_path
        if manifest_path.is_file():
            try:
                manifest = load_manifest(manifest_path, static_dir=self._config.static_dir)
                self._metrics.record_manifest_load()
                return manifest
            except Exception as exc:
                logger.warning(
                    "Vite manifest at %s failed to load (%s); falling back to filesystem scan",
                    manifest_path,
                    exc,
                )
                self._metrics.record_manifest_load(failed=True)
        return discover_manifest(self._config.static_dir, self._resolver.assets_dir)

    def reload_manifest(self) -> FrontendManifest:
        """Re-read the manifest. Used after a hot bundle swap in tests."""
        self._manifest = self._resolve_manifest()
        return self._manifest

    # ── mounting ─────────────────────────────────────────────────────
    def should_mount(self) -> bool:
        """Decide whether to attach routes to the FastAPI app.

        ``api-only`` mode skips mounting unconditionally. ``embedded``
        always mounts (caller is responsible for pre-flight
        validation). ``auto`` mounts only if a bundle is present —
        the same behavior :func:`asyncviz.dashboard.app._mount_frontend`
        always had.
        """
        mode = self._config.mode
        if mode == "api-only":
            return False
        if mode == "embedded":
            return True
        # ``auto``: mount when the bundle is on disk, else log API-only.
        return self._resolver.has_bundle()

    def mount(self, app: FastAPI) -> None:
        """Attach static + SPA routes to ``app``.

        Idempotent on a per-service basis — calling twice is a no-op
        and emits a debug log. ``api-only`` mode is a documented no-op.
        """
        if self._mounted:
            logger.debug("frontend serving already mounted; skipping")
            return
        if not self.should_mount():
            mode = self._config.mode
            if mode == "api-only":
                logger.info("frontend_mode='api-only' — skipping embedded SPA mount")
            else:
                logger.info(
                    "Frontend bundle not found at %s — running in API-only mode. "
                    "Build it with `make embed-frontend` or run the Vite dev server.",
                    self._config.static_dir,
                )
            self._mounted = True  # mark mounted so subsequent calls no-op
            return

        logger.info(
            "Serving embedded dashboard from %s (mode=%s)",
            self._config.static_dir,
            self._config.mode,
        )
        # ``/assets/`` first — mounted as a StaticFiles route so
        # Starlette routing wins before the catch-all sees the path.
        if self._resolver.has_assets_dir():
            app.mount(
                "/assets",
                _ImmutableStaticFiles(
                    directory=self._resolver.assets_dir,
                    metrics=self._metrics,
                ),
                name="dashboard-assets",
            )

        # SPA fallback — bound late so it doesn't shadow earlier
        # routes added by the application.
        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str) -> FileResponse:
            return self.serve_path(full_path)

        self._mounted = True

    # ── request-time resolution ──────────────────────────────────────
    def serve_path(self, full_path: str) -> FileResponse:
        """Resolve a SPA catch-all request to a file response.

        Routing rules, in order:

        1. Reserved backend prefixes (``api/``, ``ws``, ...) → 404.
           These should never reach here in production (FastAPI's
           router resolves them first), but the catch-all is the last
           line of defense.
        2. Path traversal attempts → 404 (typed
           :class:`PathTraversalRejectedError` under the hood).
        3. An on-disk file → served with the cache policy
           :class:`AssetResolver` decided about it. ``index.html``
           gets ``no-cache``, loose files get the one-hour cache,
           hashed files (rarely accessed through this path because
           ``/assets/`` short-circuits them) get immutable cache.
        4. Nothing matches → fall through to ``index.html`` with
           ``no-cache``. This is what makes SPA deep-linking work.

        Returns :class:`FileResponse` for success, raises
        :class:`HTTPException(404)` otherwise.
        """
        # (1) Reserved.
        if is_reserved_path(full_path):
            self._metrics.record_reserved_blocked()
            raise HTTPException(status_code=404, detail="Not Found")

        # (2) Resolve safely.
        try:
            asset = self._resolver.resolve(full_path)
        except PathTraversalRejectedError:
            self._metrics.record_path_traversal_blocked()
            raise HTTPException(status_code=404, detail="Not Found") from None

        # (3) Direct file hit.
        if asset is not None:
            return self._respond(asset)

        # (4) SPA fallback.
        return self._serve_index_fallback()

    def _respond(self, asset: ResolvedAsset) -> FileResponse:
        """Build the FileResponse + cache header for a resolved asset."""
        if asset.policy is CachePolicy.NO_CACHE and asset.relative == "index.html":
            self._metrics.record_index_served()
        elif asset.policy is CachePolicy.IMMUTABLE:
            # Hit via the SPA catch-all rather than ``/assets/`` — rare,
            # but possible if a client requests an asset by absolute
            # path outside the mounted prefix.
            self._metrics.record_immutable_hit()
        else:
            self._metrics.record_loose_hit()
        return FileResponse(
            asset.path,
            headers={"Cache-Control": header_for(asset.policy)},
        )

    def _serve_index_fallback(self) -> FileResponse:
        index = self._resolver.index_path
        if not index.is_file():
            # No bundle to fall back to — surface as 404 rather than
            # leaking a stack trace.
            raise HTTPException(status_code=404, detail="Not Found")
        self._metrics.record_spa_fallback()
        self._metrics.record_index_served()
        return FileResponse(index, headers={"Cache-Control": CACHE_NO_CACHE})


def serve_404(_: object = None) -> Response:
    """Tiny helper for tests + dependency typing. Returns a 404 response."""
    return Response(status_code=404)
