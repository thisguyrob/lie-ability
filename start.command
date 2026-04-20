#!/bin/bash
set -e
cd "$(dirname "$0")"

PYTHON=$(which python3)

if [ -z "$PYTHON" ]; then
    echo "Python 3 not found. Install with: brew install python"
    exit 1
fi

# Auto-install tkinter if missing (Homebrew Python doesn't bundle it)
if ! "$PYTHON" -c "import tkinter" 2>/dev/null; then
    PY_VER=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    echo "tkinter not found — installing python-tk@${PY_VER} via Homebrew..."
    brew install "python-tk@${PY_VER}"
fi

# Create venv if not present
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    "$PYTHON" -m venv .venv
fi

source .venv/bin/activate
pip install -q -r requirements.txt

echo ""
echo "Select launch mode:"
echo "  1) main   — normal run, logs suppressed"
echo "  2) dev    — Flask request logs visible"
echo "  3) debug  — verbose debug logging"
echo ""
read -p "Choice [1]: " choice
choice=${choice:-1}

case $choice in
    2) LAUNCH_MODE=dev ;;
    3) LAUNCH_MODE=debug ;;
    *) LAUNCH_MODE=main ;;
esac

LAUNCH_MODE=$LAUNCH_MODE python app.py
