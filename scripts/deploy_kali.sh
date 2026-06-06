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

PYTHON_BIN="${PYTHON_BIN:-python3.13}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  fail "$PYTHON_BIN is required for runtime deployment. Install python3.13 and python3.13-venv on Kali."
fi

if ! "$PYTHON_BIN" - <<'PY'
import sys
raise SystemExit(0 if sys.version_info[:2] == (3, 13) else 1)
PY
then
  fail "$PYTHON_BIN must be Python 3.13.x for runtime deployment."
fi

PYTHON_VERSION="$("$PYTHON_BIN" - <<'PY'
import sys
print(".".join(map(str, sys.version_info[:3])))
PY
)"

log "app_dir=$APP_DIR"
log "python=$PYTHON_BIN ($PYTHON_VERSION)"
log "venv=$VENV_DIR"
log "install_mode=$INSTALL_MODE"

"$PYTHON_BIN" -m venv "$VENV_DIR" || fail "Failed to create venv. On Kali, install python3.13-venv."
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
