#!/usr/bin/env bash
# Destroy containers, networks, and named volumes — fresh-start helper.
. "$(dirname "$0")/../utils/lib.sh"
cd "${REPO_ROOT}"
warn "Removing AsyncViz containers, networks, and volumes (node_modules cache will be rebuilt)…"
compose down --volumes --remove-orphans
ok "Stack reset."
