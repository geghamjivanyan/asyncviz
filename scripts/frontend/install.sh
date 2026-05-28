#!/usr/bin/env bash
# Install frontend dependencies. Uses npm ci when CI=true and a lockfile exists.
. "$(dirname "$0")/../utils/lib.sh"
require_cmd node npm
cd "${REPO_ROOT}/frontend"

if [ "${CI:-}" = "true" ] && [ -f package-lock.json ]; then
  log "npm ci"
  exec npm ci
fi

log "npm install"
exec npm install
