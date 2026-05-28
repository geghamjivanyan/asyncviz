#!/usr/bin/env bash
# Full backend CI pipeline: lint + format check + tests with coverage.
. "$(dirname "$0")/../utils/lib.sh"
"${REPO_ROOT}/scripts/backend/lint.sh"
log "pytest --cov"
"${REPO_ROOT}/scripts/backend/test.sh" --cov --cov-report=term --cov-report=xml
ok "Backend CI complete."
