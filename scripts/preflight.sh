#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

command -v docker >/dev/null 2>&1 || fail "Docker CLI is not installed."
command -v stat >/dev/null 2>&1 || fail "stat is required for permission checks."

docker info >/dev/null 2>&1 || fail "Docker Engine is unavailable; check the selected Docker context/socket. No configuration was changed."

[[ -f .env ]] || fail ".env is missing. Create it from .env.example and set local values without printing them."
env_mode="$(stat -c '%a' .env)"
(( (8#$env_mode & 077) == 0 )) || fail ".env permissions grant group/other access; restrict it to the owner (for example chmod 600 .env)."

for key in POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD DATABASE_URL JWT_SECRET ADMIN_EMAIL ADMIN_PASSWORD CORS_ORIGINS; do
  grep -q "^${key}=" .env || fail "A required environment key is missing from .env (key names only; values are not displayed)."
done

if grep -Eq '^(POSTGRES_PASSWORD|DATABASE_URL|JWT_SECRET|ADMIN_PASSWORD)=.*CHANGE_THIS' .env; then
  fail ".env still contains a placeholder value; no value was displayed."
fi

python3 - <<'PY'
from pathlib import Path
from urllib.parse import unquote, urlsplit

values = {}
for line in Path(".env").read_text().splitlines():
    key, separator, value = line.partition("=")
    if not separator:
        continue
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    values[key.strip()] = value

try:
    database_password = urlsplit(values["DATABASE_URL"]).password
except (KeyError, ValueError):
    raise SystemExit("FAIL: DATABASE_URL could not be parsed; no values were displayed.")

if not database_password or unquote(database_password) != values.get("POSTGRES_PASSWORD"):
    raise SystemExit("FAIL: POSTGRES_PASSWORD and DATABASE_URL password do not match.")
PY

docker compose config --quiet || fail "Docker Compose configuration is invalid."
printf '%s\n' "PASS: Docker Engine reachable; local environment file is private and populated; Compose configuration is valid."
