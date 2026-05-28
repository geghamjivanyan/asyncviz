#!/usr/bin/env bash
# Run the Vite dev server.
. "$(dirname "$0")/../utils/lib.sh"
require_cmd npm
cd "${REPO_ROOT}/frontend"
exec npm run dev -- "$@"
