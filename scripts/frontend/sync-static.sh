#!/usr/bin/env bash
# Copy frontend/dist → asyncviz/dashboard/static for embedded distribution.
# Idempotent: clears any previous embed first, preserves the .gitkeep marker.
. "$(dirname "$0")/../utils/lib.sh"

DIST="${REPO_ROOT}/frontend/dist"
STATIC="${REPO_ROOT}/asyncviz/dashboard/static"

if [ ! -f "${DIST}/index.html" ]; then
  err "No frontend build found at ${DIST}. Run \`scripts/frontend/build-prod.sh\` first."
  exit 1
fi

log "Clearing embedded static directory"
find "${STATIC}" -mindepth 1 -not -name '.gitkeep' -delete 2>/dev/null || true
mkdir -p "${STATIC}"

log "Copying frontend bundle"
cp -R "${DIST}/." "${STATIC}/"

ok "Frontend embedded at ${STATIC}"
