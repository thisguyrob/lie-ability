#!/usr/bin/env bash
# scripts/prep_env.sh
# ▸ Pre-download & install Lie-Ability dependencies for offline CI runs
set -euo pipefail
IFS=$'\n\t'

log() { printf "\033[1;36m▶ %s\033[0m\n" "$*"; }

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# --------------------------------------------------------------------
# 1. Python (backend + tools)
# --------------------------------------------------------------------
PY_VERSION="${PY_VERSION:-3.12}"
WHEEL_DIR="$PROJECT_ROOT/.cache/pip"
VENV_DIR="$PROJECT_ROOT/.venv"

log "Creating Python $PY_VERSION virtualenv …"
python$PY_VERSION -m venv "$VENV_DIR"
# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

log "Upgrading pip / wheel / setuptools …"
pip install -q --upgrade pip wheel setuptools

log "Downloading backend wheels to $WHEEL_DIR …"
mkdir -p "$WHEEL_DIR"
pip download -d "$WHEEL_DIR" -r backend/requirements.txt

log "Installing wheels offline …"
pip install --no-index --find-links "$WHEEL_DIR" -r backend/requirements.txt

deactivate

# --------------------------------------------------------------------
# 2. Node.js (frontend)
# --------------------------------------------------------------------
NPM_CACHE_DIR="$PROJECT_ROOT/.cache/npm"
log "Preparing Node packages with offline-friendly cache at $NPM_CACHE_DIR …"
mkdir -p "$NPM_CACHE_DIR"
cd frontend

npm config set cache "$NPM_CACHE_DIR"

if [[ ! -f package-lock.json ]]; then
  log "No package-lock.json found — running npm install to generate one"
  npm install --no-audit --progress=false
  log "Committing generated package-lock.json (if using git)"
  # Uncomment next line if you want the script to auto-add it (requires git)
  # git add package-lock.json && git commit -m "chore: add package-lock.json"
else
  npm ci --prefer-offline --no-audit --progress=false
fi

cd "$PROJECT_ROOT"

# --------------------------------------------------------------------
# 3. Optional: build frontend once so dist/ is ready for offline Docker
# --------------------------------------------------------------------
log "Building production frontend bundle …"
cd frontend
npm run build
cd "$PROJECT_ROOT"

log "✅ Dependency preparation complete.
Next runs can set:
  PIP_NO_INDEX=1
  NPM_CONFIG_CACHE=$NPM_CACHE_DIR
and skip the network entirely."
