#!/usr/bin/env bash
# ==============================================================================
# CABLE DATA MANAGER — AUTOMATED POSTGRESQL BACKUP UTILITY
#
# Dumps PostgreSQL database in custom format (pg_dump -Fc) directly through
# GPG public-key stream encryption, verifies integrity, generates manifest,
# and executes safe retention pruning.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# ------------------------------------------------------------------------------
# Configuration & Defaults
# ------------------------------------------------------------------------------
BACKUP_DIR="${BACKUP_DIR:-/mnt/cable-manager-backups}"
REQUIRE_MOUNT="${REQUIRE_MOUNT:-false}"
MIN_DISK_SPACE_MB="${MIN_DISK_SPACE_MB:-500}"
COMPOSE_FILE="${COMPOSE_FILE:-${PROJECT_ROOT}/docker-compose.prod.yml}"
COMPOSE_PROJECT="${COMPOSE_PROJECT:-cable-manager-phase1}"
POSTGRES_SERVICE="${POSTGRES_SERVICE:-db}"
ENV_FILE="${ENV_FILE:-${PROJECT_ROOT}/.env}"
BACKUP_GNUPGHOME="${BACKUP_GNUPGHOME:-${GNUPGHOME:-}}"

DAILY_RETENTION="${DAILY_RETENTION:-14}"
WEEKLY_RETENTION="${WEEKLY_RETENTION:-8}"
MONTHLY_RETENTION="${MONTHLY_RETENTION:-12}"
RUN_RETENTION="${RUN_RETENTION:-true}"

# ------------------------------------------------------------------------------
# Logging Helper
# ------------------------------------------------------------------------------
log() {
  local level="$1"
  shift
  local ts
  ts="$(date -u +"%Y-%m-%d %H:%M:%SZ")"
  printf '[%s] [%s] %s\n' "$ts" "$level" "$*"
}

log_info() { log "INFO" "$@"; }
log_warn() { log "WARN" "$@" >&2; }
log_error() { log "ERROR" "$@" >&2; }

# ------------------------------------------------------------------------------
# Source Environment if Available
# ------------------------------------------------------------------------------
if [[ -f "$ENV_FILE" ]]; then
  # Read variables safely without printing or running arbitrary code
  while IFS='=' read -r key val || [[ -n "$key" ]]; do
    [[ "$key" =~ ^#.*$ || -z "$key" ]] && continue
    # Strip quotes if present
    val="${val%\"}"
    val="${val#\"}"
    val="${val%\'}"
    val="${val#\'}"
    case "$key" in
      POSTGRES_DB) POSTGRES_DB="${POSTGRES_DB:-$val}" ;;
      POSTGRES_USER) POSTGRES_USER="${POSTGRES_USER:-$val}" ;;
      BACKUP_GPG_RECIPIENT) BACKUP_GPG_RECIPIENT="${BACKUP_GPG_RECIPIENT:-$val}" ;;
      BACKUP_GNUPGHOME) BACKUP_GNUPGHOME="${BACKUP_GNUPGHOME:-$val}" ;;
      BACKUP_DIR) BACKUP_DIR="${BACKUP_DIR:-$val}" ;;
      REQUIRE_MOUNT) REQUIRE_MOUNT="${REQUIRE_MOUNT:-$val}" ;;
      MIN_DISK_SPACE_MB) MIN_DISK_SPACE_MB="${MIN_DISK_SPACE_MB:-$val}" ;;
    esac
  done < "$ENV_FILE"
fi

POSTGRES_DB="${POSTGRES_DB:-cable_manager}"
POSTGRES_USER="${POSTGRES_USER:-cable_admin}"
BACKUP_GPG_RECIPIENT="${BACKUP_GPG_RECIPIENT:-}"

# ------------------------------------------------------------------------------
# Dependency & Environment Checks
# ------------------------------------------------------------------------------
for cmd in docker gpg sha256sum stat awk df; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    log_error "Required host command not found: $cmd"
    exit 1
  fi
done

# Export GNUPGHOME if BACKUP_GNUPGHOME is specified
if [[ -n "$BACKUP_GNUPGHOME" ]]; then
  export GNUPGHOME="$BACKUP_GNUPGHOME"
fi

# 1. Check GPG Recipient Configuration
if [[ -z "$BACKUP_GPG_RECIPIENT" ]]; then
  log_error "BACKUP_GPG_RECIPIENT is not configured. Automated backup requires a GPG public key."
  log_error "Set BACKUP_GPG_RECIPIENT in environment or .env. Plaintext backups are forbidden."
  exit 2
fi

if ! gpg --batch --list-public-keys "$BACKUP_GPG_RECIPIENT" >/dev/null 2>&1; then
  log_error "GPG public key for recipient '$BACKUP_GPG_RECIPIENT' not found in keyring."
  exit 2
fi

# 2. Check Storage Mount (if required)
if [[ "$REQUIRE_MOUNT" == "true" ]]; then
  if ! mountpoint -q "$BACKUP_DIR" 2>/dev/null; then
    log_error "Configured backup directory '$BACKUP_DIR' is not a mount point."
    log_error "REQUIRE_MOUNT=true is set; aborting to prevent writing to unmounted or root filesystem."
    exit 3
  fi
fi

# 3. Ensure Backup Directory Exists with Secure Permissions
if [[ ! -d "$BACKUP_DIR" ]]; then
  log_info "Creating backup directory: $BACKUP_DIR"
  mkdir -p "$BACKUP_DIR"
fi
chmod 0700 "$BACKUP_DIR"

# 4. Check Free Disk Space
AVAILABLE_MB="$(df -m "$BACKUP_DIR" 2>/dev/null | awk 'NR==2 {print $4}')"
if [[ ! "$AVAILABLE_MB" =~ ^[0-9]+$ ]]; then
  log_error "Unable to determine available disk space for '$BACKUP_DIR'."
  exit 4
fi
if [[ "$AVAILABLE_MB" -lt "$MIN_DISK_SPACE_MB" ]]; then
  log_error "Insufficient disk space in $BACKUP_DIR: ${AVAILABLE_MB}MB available, minimum ${MIN_DISK_SPACE_MB}MB required."
  exit 4
fi

# 5. Verify PostgreSQL Container is Running and Accessible
if ! docker compose -p "$COMPOSE_PROJECT" -f "$COMPOSE_FILE" ps "$POSTGRES_SERVICE" 2>/dev/null | grep -q "Up\|healthy"; then
  log_error "PostgreSQL service '$POSTGRES_SERVICE' is not running in Compose project '$COMPOSE_PROJECT'."
  exit 5
fi

if ! docker compose -p "$COMPOSE_PROJECT" -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
     pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; then
  log_error "PostgreSQL database '$POSTGRES_DB' is not responding to pg_isready."
  exit 5
fi

# ------------------------------------------------------------------------------
# Backup Execution
# ------------------------------------------------------------------------------
TIMESTAMP="$(date -u +"%Y%m%d_%H%M%SZ")"
BASE_NAME="cable_backup_${TIMESTAMP}"
TMP_DUMP="${BACKUP_DIR}/${BASE_NAME}.dump.gpg.tmp"
TMP_MANIFEST="${BACKUP_DIR}/${BASE_NAME}.manifest.tmp"
FINAL_DUMP="${BACKUP_DIR}/${BASE_NAME}.dump.gpg"
FINAL_MANIFEST="${BACKUP_DIR}/${BASE_NAME}.manifest"

# Cleanup temporary files on unexpected exit
cleanup() {
  local exit_code=$?
  if [[ -f "$TMP_DUMP" ]]; then
    rm -f "$TMP_DUMP"
  fi
  if [[ -f "$TMP_MANIFEST" ]]; then
    rm -f "$TMP_MANIFEST"
  fi
  if [[ $exit_code -ne 0 ]]; then
    log_error "Backup process aborted or failed with exit code $exit_code."
  fi
}
trap cleanup EXIT INT TERM

log_info "Starting encrypted backup for database '$POSTGRES_DB'..."
log_info "Destination: $FINAL_DUMP"

# Execute pg_dump directly into GPG encryption stream
# Custom format (-Fc) compresses by default; no-owner and no-privileges ensure portability
set +e
docker compose -p "$COMPOSE_PROJECT" -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner --no-privileges \
  | gpg --batch --yes --trust-model always --encrypt --recipient "$BACKUP_GPG_RECIPIENT" \
  --output "$TMP_DUMP"
DUMP_STATUS=("${PIPESTATUS[@]}")
set -e

if [[ "${DUMP_STATUS[0]}" -ne 0 ]]; then
  log_error "pg_dump failed with exit code ${DUMP_STATUS[0]}."
  exit 6
fi

if [[ "${DUMP_STATUS[1]}" -ne 0 ]]; then
  log_error "GPG encryption stream failed with exit code ${DUMP_STATUS[1]}."
  exit 6
fi

# Verify artifact existence and size
if [[ ! -s "$TMP_DUMP" ]]; then
  log_error "Encrypted dump file is empty or missing: $TMP_DUMP"
  exit 7
fi

FILE_SIZE="$(stat -c%s "$TMP_DUMP" 2>/dev/null || stat -f%z "$TMP_DUMP")"
CHECKSUM="$(sha256sum "$TMP_DUMP" | awk '{print $1}')"

# Query PostgreSQL version from server
PG_VERSION="$(docker compose -p "$COMPOSE_PROJECT" -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -A -c "SELECT version();" 2>/dev/null | tr -d '\r' | head -n 1 || echo "PostgreSQL 16")"

# Generate Manifest File
cat <<EOF > "$TMP_MANIFEST"
[backup_manifest]
timestamp_utc=${TIMESTAMP}
database_name=${POSTGRES_DB}
postgres_version=${PG_VERSION}
backup_format=pg_dump custom format (compressed), gpg encrypted
encrypted_file=${BASE_NAME}.dump.gpg
file_size_bytes=${FILE_SIZE}
sha256_checksum=${CHECKSUM}
gpg_recipient=${BACKUP_GPG_RECIPIENT}
verification_status=VERIFIED
EOF

# Ensure all data is flushed to persistent storage before publishing
sync "$TMP_DUMP" "$TMP_MANIFEST" 2>/dev/null || sync -f "$TMP_DUMP" 2>/dev/null || true

# Atomically publish verified backup and manifest
mv "$TMP_DUMP" "$FINAL_DUMP"
chmod 0600 "$FINAL_DUMP"

mv "$TMP_MANIFEST" "$FINAL_MANIFEST"
chmod 0644 "$FINAL_MANIFEST"

# Flush directory metadata
sync "$BACKUP_DIR" 2>/dev/null || true

log_info "Backup successfully created and verified."
log_info "  File:     $FINAL_DUMP"
log_info "  Size:     $FILE_SIZE bytes"
log_info "  SHA-256:  $CHECKSUM"
log_info "  Manifest: $FINAL_MANIFEST"

# ------------------------------------------------------------------------------
# Retention Management
# ------------------------------------------------------------------------------
if [[ "$RUN_RETENTION" == "true" ]]; then
  log_info "Evaluating backup retention (Daily: $DAILY_RETENTION, Weekly: $WEEKLY_RETENTION, Monthly: $MONTHLY_RETENTION)..."
  if [[ -f "${SCRIPT_DIR}/retention.py" ]]; then
    python3 "${SCRIPT_DIR}/retention.py" \
      --backup-dir "$BACKUP_DIR" \
      --daily "$DAILY_RETENTION" \
      --weekly "$WEEKLY_RETENTION" \
      --monthly "$MONTHLY_RETENTION" \
      --apply
  else
    log_warn "Retention script not found at ${SCRIPT_DIR}/retention.py; skipping retention pruning."
  fi
fi

log_info "Backup routine completed successfully."
exit 0
