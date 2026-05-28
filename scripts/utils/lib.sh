# shellcheck shell=bash
# Shared helpers sourced by every shell script in scripts/.
# Resolves repo root, exposes log/info/ok/warn/err, detects the venv interpreter.
# POSIX-friendly: no bashisms beyond what bash 3.2 (macOS) supports.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd -P)"
export REPO_ROOT

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  C_RESET=$'\033[0m'
  C_DIM=$'\033[2m'
  C_RED=$'\033[31m'
  C_GREEN=$'\033[32m'
  C_YELLOW=$'\033[33m'
  C_CYAN=$'\033[36m'
  C_BOLD=$'\033[1m'
else
  C_RESET=""
  C_DIM=""
  C_RED=""
  C_GREEN=""
  C_YELLOW=""
  C_CYAN=""
  C_BOLD=""
fi

log()  { printf '%s▸%s %s\n' "${C_CYAN}${C_BOLD}" "${C_RESET}" "$*"; }
info() { printf '%s•%s %s\n' "${C_DIM}" "${C_RESET}" "$*"; }
ok()   { printf '%s✓%s %s\n' "${C_GREEN}" "${C_RESET}" "$*"; }
warn() { printf '%s⚠%s %s\n' "${C_YELLOW}" "${C_RESET}" "$*" >&2; }
err()  { printf '%s✗%s %s\n' "${C_RED}" "${C_RESET}" "$*" >&2; }

require_cmd() {
  local missing=0
  for cmd in "$@"; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
      err "Missing required command: $cmd"
      missing=1
    fi
  done
  if [ "$missing" -ne 0 ]; then
    exit 127
  fi
}

detect_python() {
  if [ -x "${REPO_ROOT}/.venv/bin/python" ]; then
    printf '%s\n' "${REPO_ROOT}/.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    command -v python3
  else
    err "No Python interpreter found (looked for .venv/bin/python and python3)"
    exit 127
  fi
}

run_in_repo() {
  cd "${REPO_ROOT}"
  "$@"
}

run_in_frontend() {
  cd "${REPO_ROOT}/frontend"
  "$@"
}

# Run docker compose, auto-detecting `docker compose` plugin or the
# standalone `docker-compose` binary. All arguments forward to it.
compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  else
    err "Neither \`docker compose\` nor \`docker-compose\` is available."
    exit 127
  fi
}
