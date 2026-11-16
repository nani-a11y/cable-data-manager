#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"

if [[ -f "backend/.venv/bin/pytest" ]]; then
  pytest_cmd="backend/.venv/bin/pytest"
elif command -v pytest >/dev/null 2>&1; then
  pytest_cmd="pytest"
else
  pytest_cmd="python3 -m pytest"
fi

PYTHONDONTWRITEBYTECODE=1 "$pytest_cmd" backend/tests -v
