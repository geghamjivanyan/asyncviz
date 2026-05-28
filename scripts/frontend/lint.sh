#!/usr/bin/env bash
# ESLint + Prettier format check.
. "$(dirname "$0")/../utils/lib.sh"
require_cmd npm
cd "${REPO_ROOT}/frontend"
log "eslint"
npm run --silent lint
log "prettier --check"
npm run --silent format:check
ok "Frontend lint passed."
