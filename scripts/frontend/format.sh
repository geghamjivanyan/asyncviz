#!/usr/bin/env bash
# Auto-format the frontend (Prettier write + ESLint --fix).
. "$(dirname "$0")/../utils/lib.sh"
require_cmd npm npx
cd "${REPO_ROOT}/frontend"
log "prettier --write"
npm run --silent format
log "eslint --fix"
npx eslint . --fix
ok "Frontend formatted."
