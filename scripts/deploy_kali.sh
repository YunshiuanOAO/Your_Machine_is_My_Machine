#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"

python3 -m venv .venv
. .venv/bin/activate

python -m pip install --upgrade pip
if [ -f requirements.txt ]; then
  python -m pip install -r requirements.txt
fi

python -m pytest tests

cat > deploy_info.txt <<EOF
deployed_at=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
app_dir=$APP_DIR
python=$(python --version)
EOF

echo "[deploy] OK: $APP_DIR"

