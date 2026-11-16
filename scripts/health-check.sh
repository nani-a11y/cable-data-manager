#!/usr/bin/env bash
set -uo pipefail

backend_health_url="${BACKEND_HEALTH_URL:-http://localhost:8000/health}"
frontend_url="${FRONTEND_URL:-http://localhost:5173/}"
failed=0

check_http_200() {
  local label="$1"
  local url="$2"
  local status

  if status="$(curl -sS --max-time 5 -o /dev/null -w '%{http_code}' "$url")" && [[ "$status" == "200" ]]; then
    printf 'PASS: %s returned HTTP 200.\n' "$label"
  else
    printf 'FAIL: %s did not return HTTP 200 (status %s).\n' "$label" "${status:-000}" >&2
    failed=1
  fi
}

command -v curl >/dev/null 2>&1 || {
  printf '%s\n' "FAIL: curl is required." >&2
  exit 1
}

check_http_200 "Backend health" "$backend_health_url"
check_http_200 "Frontend" "$frontend_url"
exit "$failed"
