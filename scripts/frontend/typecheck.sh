#!/usr/bin/env bash
# TypeScript strict typecheck.
. "$(dirname "$0")/../utils/lib.sh"
require_cmd npm
cd "${REPO_ROOT}/frontend"
exec npm run --silent typecheck
