#!/usr/bin/env bash
set -e

USE_NATIVE=false
if [[ "$1" == "-n" || "$1" == "--native" ]]; then
  USE_NATIVE=true
elif ! command -v docker >/dev/null; then
  USE_NATIVE=true
fi

if [ "$USE_NATIVE" = true ]; then
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r backend/requirements.txt
  (cd frontend && npm install)
  uvicorn backend.main:app --reload &
  BACK_PID=$!
  (cd frontend && npm run dev) &
  FRONT_PID=$!

  # Attempt to open the host view automatically
  if command -v xdg-open >/dev/null; then
    xdg-open http://localhost:5173/host >/dev/null 2>&1 &
  elif command -v open >/dev/null; then
    open http://localhost:5173/host >/dev/null 2>&1 &
  fi

  echo "Player view: http://localhost:5173"
  echo "Host view: http://localhost:5173/host"

  trap 'kill $BACK_PID $FRONT_PID' INT TERM
  wait
else
  docker compose up --build
fi
