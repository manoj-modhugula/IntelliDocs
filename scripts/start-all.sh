#!/bin/bash
# Start backend and frontend for local development.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -d "backend" ] || [ ! -d "frontend" ]; then
  echo "Run this script from the project root."
  exit 1
fi

cleanup() {
  echo
  echo "Stopping services"
  kill "${BACKEND_PID:-}" "${FRONTEND_PID:-}" 2>/dev/null || true
  exit 0
}
trap cleanup SIGINT SIGTERM

if [ ! -d "backend/venv" ]; then
  echo "Backend virtualenv not found. Run ./setup.sh first."
  exit 1
fi

echo "Starting backend"
cd backend
# shellcheck disable=SC1091
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app &
BACKEND_PID=$!
cd "$ROOT"

echo "Waiting for backend"
for _ in $(seq 1 30); do
  if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
    echo "Backend ready at http://localhost:8000"
    break
  fi
  sleep 1
done

echo "Starting frontend"
cd frontend
npm run dev &
FRONTEND_PID=$!
cd "$ROOT"

echo
echo "Frontend: http://localhost:3000"
echo "API:      http://localhost:8000"
echo "Docs:     http://localhost:8000/docs"
echo
echo "Ctrl+C stops both processes."

wait "$BACKEND_PID" "$FRONTEND_PID"
