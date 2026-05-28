#!/usr/bin/env bash
# Sanity-check the embedded frontend bundle.
. "$(dirname "$0")/../utils/lib.sh"
STATIC="${REPO_ROOT}/asyncviz/dashboard/static"

if [ ! -f "${STATIC}/index.html" ]; then
  err "Embedded frontend is missing index.html (looked in ${STATIC})"
  exit 1
fi

if [ ! -d "${STATIC}/assets" ]; then
  warn "No assets/ directory inside ${STATIC} — proceeding (minimal build)"
fi

file_count=$(find "${STATIC}" -type f -not -name '.gitkeep' | wc -l | tr -d ' ')
ok "Embedded frontend OK (${file_count} files)"
