#!/usr/bin/env bash
# Run the full repository validation matrix locally.
. "$(dirname "$0")/../utils/lib.sh"
log "Backend CI"
"${REPO_ROOT}/scripts/ci/backend.sh"
log "Frontend CI"
"${REPO_ROOT}/scripts/ci/frontend.sh"
ok "Repository validation passed."
