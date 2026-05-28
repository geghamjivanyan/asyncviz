#!/usr/bin/env bash
# Production build of the dashboard.
. "$(dirname "$0")/../utils/lib.sh"
require_cmd npm
cd "${REPO_ROOT}/frontend"
exec npm run --silent build
