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
  trap 'kill $BACK_PID $FRONT_PID' INT TERM
  wait
else
  docker compose up --build
fi
