#!/usr/bin/env bash
# Remove the embedded frontend bundle (keeps the .gitkeep marker).
. "$(dirname "$0")/../utils/lib.sh"
STATIC="${REPO_ROOT}/asyncviz/dashboard/static"
find "${STATIC}" -mindepth 1 -not -name '.gitkeep' -delete 2>/dev/null || true
ok "Embedded frontend cleared."
