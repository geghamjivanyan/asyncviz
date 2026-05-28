#!/usr/bin/env bash
# Full frontend CI pipeline: lint + format check + typecheck + build.
. "$(dirname "$0")/../utils/lib.sh"
"${REPO_ROOT}/scripts/frontend/lint.sh"
log "tsc -b --noEmit"
"${REPO_ROOT}/scripts/frontend/typecheck.sh"
log "vite build"
"${REPO_ROOT}/scripts/frontend/build.sh"
ok "Frontend CI complete."
