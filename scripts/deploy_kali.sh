#!/usr/bin/env bash
set -Eeuo pipefail

log() {
  printf '[deploy] %s\n' "$*"
}

fail() {
  printf '[deploy][error] %s\n' "$*" >&2
  exit 1
}

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${VENV_DIR:-$APP_DIR/.venv}"
INSTALL_MODE="${INSTALL_MODE:-full}"

cd "$APP_DIR"

choose_python() {
  for candidate in python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      if "$candidate" - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
      then
        printf '%s\n' "$candidate"
        return 0
      fi
    fi
  done
  return 1
}

PYTHON_BIN="$(choose_python)" || fail "Python 3.11+ is required by pyproject.toml. Install python3.11 and python3.11-venv on Kali."
PYTHON_VERSION="$("$PYTHON_BIN" - <<'PY'
import sys
print(".".join(map(str, sys.version_info[:3])))
PY
)"

log "app_dir=$APP_DIR"
log "python=$PYTHON_BIN ($PYTHON_VERSION)"
log "venv=$VENV_DIR"
log "install_mode=$INSTALL_MODE"

"$PYTHON_BIN" -m venv "$VENV_DIR" || fail "Failed to create venv. On Kali, install python3.11-venv."
# shellcheck disable=SC1091
. "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip setuptools wheel

case "$INSTALL_MODE" in
  full)
    log "installing project dependencies from pyproject.toml"
    python -m pip install -e .
    python -m pip install 'pytest>=8.0.0'
    ;;
  minimal)
    log "minimal mode: installing only pytest for smoke tests"
    python -m pip install 'pytest>=8.0.0'
    ;;
  *)
    fail "Unknown INSTALL_MODE=$INSTALL_MODE. Use full or minimal."
    ;;
esac

log "running tests"
python -m pytest tests

cat > deploy_info.txt <<EOF
deployed_at=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
app_dir=$APP_DIR
python=$PYTHON_VERSION
install_mode=$INSTALL_MODE
git_sha=${GITHUB_SHA:-unknown}
EOF

log "OK"
