#!/usr/bin/env bash
# Verify backend and frontend API endpoints.
# Usage: ./scripts/verify-apis.sh [backend_url] [frontend_url]
#        ./scripts/verify-apis.sh backend   # backend only
# Default: backend http://localhost:8000, frontend http://localhost:3000

set -e
BACKEND="${1:-http://localhost:8000}"
FRONTEND="${2:-http://localhost:3000}"
BACKEND_ONLY=false
[[ "$1" == "backend" ]] && BACKEND_ONLY=true && BACKEND="http://localhost:8000"

red() { printf "\033[31m%s\033[0m\n" "$1"; }
green() { printf "\033[32m%s\033[0m\n" "$1"; }
bold() { printf "\033[1m%s\033[0m\n" "$1"; }

ok=0
fail=0

check() {
  local method="$1"
  local url="$2"
  local expect="$3"
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" "$url" 2>/dev/null || echo "000")
  if [[ "$code" == "$expect" ]]; then
    green "  OK $method $url -> $code"
    ((ok++)) || true
    return 0
  else
    red "  FAIL $method $url -> $code (expected $expect)"
    ((fail++)) || true
    return 1
  fi
}

bold "=== Backend ($BACKEND) ==="
check GET "$BACKEND/" "200"
check GET "$BACKEND/health" "200"
check GET "$BACKEND/docs" "200"
check GET "$BACKEND/auth/me" "401"
check GET "$BACKEND/workspaces/" "200"
check GET "$BACKEND/documents/" "200"
check GET "$BACKEND/auth/me" "401"

if [[ "$BACKEND_ONLY" != "true" ]]; then
  bold "=== Frontend API ($FRONTEND) ==="
  check GET "$FRONTEND/api/workspaces" "200"
  check GET "$FRONTEND/api/documents" "200"
  echo ""
  echo "If frontend returns 500: stop dev server, run: rm -rf .next && npm run dev"
fi

bold "=== Summary ==="
if [[ $fail -eq 0 ]]; then
  green "All $ok checks passed."
  exit 0
else
  red "$fail check(s) failed, $ok passed."
  exit 1
fi
