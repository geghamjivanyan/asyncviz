#!/usr/bin/env bash
# Produce a production frontend bundle and embed it into the Python package.
. "$(dirname "$0")/../utils/lib.sh"
require_cmd npm
cd "${REPO_ROOT}/frontend"

if [ ! -d node_modules ]; then
  log "Installing frontend dependencies"
  "${REPO_ROOT}/scripts/frontend/install.sh"
fi

log "Building frontend (vite production)"
npm run --silent build

"${REPO_ROOT}/scripts/frontend/sync-static.sh"
"${REPO_ROOT}/scripts/frontend/verify-static.sh"
