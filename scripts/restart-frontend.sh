#!/bin/bash
# Clear Next.js cache and restart the frontend so API/UI changes take effect.
# Run from project root or scripts/.

set -e
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND="$PROJECT_ROOT/frontend"

echo "IntelliDocs – Restart frontend (clear cache)"
echo "============================================"

echo "Stopping anything on port 3000..."
lsof -ti :3000 | xargs kill -9 2>/dev/null || true
sleep 2

echo "Clearing Next.js cache (.next)..."
rm -rf "$FRONTEND/.next"
echo "Cache cleared."

echo "Starting frontend (npm run dev)..."
cd "$FRONTEND"
npm run dev
