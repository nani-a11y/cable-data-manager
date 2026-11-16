#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"

printf '%s\n' 'Checking already-running backend dependencies...'
docker compose exec -T backend python -m pip check
printf '%s\n' 'Checking already-running frontend dependencies...'
docker compose exec -T frontend npm ls --depth=0
