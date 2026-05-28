#!/usr/bin/env bash
# Repository health check.
. "$(dirname "$0")/../utils/lib.sh"

status=0

check_python() {
  local py
  py="$(command -v python3 || true)"
  if [ -z "$py" ]; then
    err "python3 not found on PATH"
    return 1
  fi
  local version
  version="$("$py" -c 'import sys; print(".".join(str(p) for p in sys.version_info[:3]))')"
  local major minor
  major="$("$py" -c 'import sys; print(sys.version_info.major)')"
  minor="$("$py" -c 'import sys; print(sys.version_info.minor)')"
  if [ "$major" -lt 3 ] || { [ "$major" -eq 3 ] && [ "$minor" -lt 12 ]; }; then
    err "Python ${version} found; AsyncViz requires >= 3.12"
    return 1
  fi
  ok "Python ${version}"
}

check_node() {
  if ! command -v node >/dev/null 2>&1; then
    err "node not found on PATH"
    return 1
  fi
  local v
  v="$(node --version)"
  local major
  major="$(printf '%s' "$v" | sed -E 's/^v([0-9]+).*/\1/')"
  if [ "$major" -lt 20 ]; then
    err "Node ${v} found; AsyncViz requires >= 20"
    return 1
  fi
  ok "Node ${v}"
}

check_npm() {
  if ! command -v npm >/dev/null 2>&1; then
    err "npm not found on PATH"
    return 1
  fi
  ok "npm $(npm --version)"
}

check_venv() {
  if [ -x "${REPO_ROOT}/.venv/bin/python" ]; then
    ok ".venv present"
  else
    warn ".venv not found — run \`make install\` to create it"
  fi
}

check_node_modules() {
  if [ -d "${REPO_ROOT}/frontend/node_modules" ]; then
    ok "frontend/node_modules present"
  else
    warn "frontend/node_modules missing — run \`make install\` to populate it"
  fi
}

log "AsyncViz environment check"
check_python      || status=1
check_node        || status=1
check_npm         || status=1
check_venv
check_node_modules
"${REPO_ROOT}/scripts/utils/check-ports.sh" || status=1

if [ "$status" -ne 0 ]; then
  err "Doctor reported issues."
fi
exit "$status"
