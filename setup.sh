#!/bin/bash
# Local setup for IntelliDocs.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.11+ is required."
  exit 1
fi

echo "Setting up backend"
cd backend
if [ ! -d "venv" ]; then
  python3 -m venv venv
fi
# shellcheck disable=SC1091
source venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Created backend/.env from .env.example. Fill in credentials before starting."
fi
deactivate
cd "$ROOT"

echo "Setting up frontend"
cd frontend
if [ ! -d "node_modules" ]; then
  npm install
fi
if [ ! -f ".env.local" ] && [ -f ".env.local.example" ]; then
  cp .env.local.example .env.local
fi
cd "$ROOT"

echo
echo "Setup complete."
echo
echo "Start the API:  cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000"
echo "Start the UI:   cd frontend && npm run dev"
echo "Or run:         ./scripts/start-all.sh"
echo
echo "PostgreSQL with pgvector is required. See README.md."
