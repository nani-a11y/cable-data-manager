#!/usr/bin/env bash
# ==============================================================================
# CABLE DATA MANAGER — RESTORE UTILITY
#
# Verifies encrypted backup manifest & SHA-256 checksum, decrypts archive,
# validates custom-format archive structure via pg_restore --list, and safely
# restores schema and data into a target PostgreSQL database.
#
# Production protection:
# - Rejects production restoration by default.
# - Requires explicit safety flag AND interactive confirmation for production.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# ------------------------------------------------------------------------------
# Defaults
# ------------------------------------------------------------------------------
BACKUP_FILE=""
TARGET_DB=""
MANIFEST_FILE=""
GPG_KEY_FILE=""
FORCE_PRODUCTION=false
OVERWRITE_EXISTING=false
COMPOSE_FILE="${COMPOSE_FILE:-${PROJECT_ROOT}/docker-compose.prod.yml}"
COMPOSE_PROJECT="${COMPOSE_PROJECT:-cable-manager-phase1}"
POSTGRES_SERVICE="${POSTGRES_SERVICE:-db}"
ENV_FILE="${ENV_FILE:-${PROJECT_ROOT}/.env}"

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
# Parse Arguments
# ------------------------------------------------------------------------------
print_usage() {
  cat <<EOF
Usage: $(basename "$0") --backup-file <path> --target-db <db_name> [options]

Required Arguments:
  --backup-file <path>    Path to .dump.gpg encrypted backup file
  --target-db <name>      Target database name for restoration (defaults safely to disposable)

Optional Arguments:
  --manifest <path>       Path to .manifest file (defaults to matching .dump.gpg name)
  --gpg-key <path>        Path to private GPG key file to import before decrypting
  --overwrite-existing    Allow restoring into an existing database
  --force-production-restore-i-know-what-i-am-doing
                          Explicit safety override required to target production database
  --compose-project <name> Docker Compose project name (default: cable-manager-phase1)
  --compose-file <path>   Docker Compose file (default: docker-compose.prod.yml)
  --postgres-service <name> PostgreSQL container service name (default: db)
  --env-file <path>       Path to .env file for database credentials
  -h, --help              Show this help message
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backup-file) BACKUP_FILE="$2"; shift 2 ;;
    --target-db) TARGET_DB="$2"; shift 2 ;;
    --manifest) MANIFEST_FILE="$2"; shift 2 ;;
    --gpg-key) GPG_KEY_FILE="$2"; shift 2 ;;
    --force-production-restore-i-know-what-i-am-doing) FORCE_PRODUCTION=true; shift ;;
    --overwrite-existing) OVERWRITE_EXISTING=true; shift ;;
    --compose-project) COMPOSE_PROJECT="$2"; shift 2 ;;
    --compose-file) COMPOSE_FILE="$2"; shift 2 ;;
    --postgres-service) POSTGRES_SERVICE="$2"; shift 2 ;;
    --env-file) ENV_FILE="$2"; shift 2 ;;
    -h|--help) print_usage; exit 0 ;;
    *) log_error "Unknown argument: $1"; print_usage; exit 1 ;;
  esac
done

if [[ -z "$BACKUP_FILE" || -z "$TARGET_DB" ]]; then
  log_error "Both --backup-file and --target-db must be specified."
  print_usage
  exit 1
fi

if [[ ! "$TARGET_DB" =~ ^[a-zA-Z0-9_]+$ ]]; then
  log_error "Invalid target database name '$TARGET_DB'. Only alphanumeric characters and underscores are allowed."
  exit 1
fi

# ------------------------------------------------------------------------------
# Source Environment if Available
# ------------------------------------------------------------------------------
POSTGRES_DB="cable_manager"
POSTGRES_USER="cable_admin"

if [[ -f "$ENV_FILE" ]]; then
  while IFS='=' read -r key val || [[ -n "$key" ]]; do
    [[ "$key" =~ ^#.*$ || -z "$key" ]] && continue
    val="${val%\"}"
    val="${val#\"}"
    val="${val%\'}"
    val="${val#\'}"
    case "$key" in
      POSTGRES_DB) POSTGRES_DB="$val" ;;
      POSTGRES_USER) POSTGRES_USER="$val" ;;
    esac
  done < "$ENV_FILE"
fi

# ------------------------------------------------------------------------------
# Production Safety Boundary Check
# ------------------------------------------------------------------------------
is_production_target=false
if [[ "$TARGET_DB" == "$POSTGRES_DB" || "$TARGET_DB" == "cable_manager" || "$TARGET_DB" == "cable_prod" ]]; then
  is_production_target=true
fi

if [[ "$is_production_target" == "true" ]]; then
  if [[ "$FORCE_PRODUCTION" != "true" ]]; then
    log_error "REFUSED: Restoring directly into production database '$TARGET_DB' is blocked by default."
    log_error "To restore into production, you must supply the explicit flag:"
    log_error "  --force-production-restore-i-know-what-i-am-doing"
    log_error "Recommendation: Restore into an isolated disposable database (e.g., '${TARGET_DB}_restore_test') to inspect data first."
    exit 10
  fi

  # Interactive confirmation requirement
  log_warn "==================================================================="
  log_warn "CRITICAL WARNING: Target database '$TARGET_DB' is a PRODUCTION DATABASE."
  log_warn "Existing customer records and payment history may be overwritten!"
  log_warn "==================================================================="

  if [[ -t 0 ]]; then
    printf 'Type "RESTORE PRODUCTION DATABASE" to confirm: '
    read -r confirmation
    if [[ "$confirmation" != "RESTORE PRODUCTION DATABASE" ]]; then
      log_error "Confirmation mismatch. Aborting restore."
      exit 11
    fi
  else
    if [[ "${CONFIRM_PRODUCTION_RESTORE:-}" != "I_CONFIRM_OVERWRITE_PRODUCTION" ]]; then
      log_error "Non-interactive environment detected without CONFIRM_PRODUCTION_RESTORE=I_CONFIRM_OVERWRITE_PRODUCTION. Aborting."
      exit 11
    fi
  fi
fi

# ------------------------------------------------------------------------------
# Validate Backup File & Manifest Checksum
# ------------------------------------------------------------------------------
if [[ ! -f "$BACKUP_FILE" ]]; then
  log_error "Backup file not found: $BACKUP_FILE"
  exit 2
fi

if [[ -z "$MANIFEST_FILE" ]]; then
  if [[ "$BACKUP_FILE" == *.dump.gpg ]]; then
    MANIFEST_FILE="${BACKUP_FILE%.dump.gpg}.manifest"
  else
    MANIFEST_FILE="${BACKUP_FILE}.manifest"
  fi
fi

if [[ -f "$MANIFEST_FILE" ]]; then
  log_info "Verifying SHA-256 checksum and metadata against manifest: $MANIFEST_FILE"
  EXPECTED_CHECKSUM=""
  EXPECTED_ENC_FILE=""
  while IFS='=' read -r key val || [[ -n "$key" ]]; do
    clean_key="${key// /}"
    clean_val="${val// /}"
    case "$clean_key" in
      sha256_checksum) EXPECTED_CHECKSUM="$clean_val" ;;
      encrypted_file) EXPECTED_ENC_FILE="$clean_val" ;;
    esac
  done < "$MANIFEST_FILE"

  if [[ -n "$EXPECTED_ENC_FILE" ]]; then
    ACTUAL_BASENAME="$(basename "$BACKUP_FILE")"
    if [[ "$EXPECTED_ENC_FILE" != "$ACTUAL_BASENAME" ]]; then
      log_error "MANIFEST MISMATCH! Manifest belongs to '$EXPECTED_ENC_FILE', but backup target is '$ACTUAL_BASENAME'."
      exit 3
    fi
  fi

  if [[ -n "$EXPECTED_CHECKSUM" ]]; then
    ACTUAL_CHECKSUM="$(sha256sum "$BACKUP_FILE" | awk '{print $1}')"
    if [[ "$EXPECTED_CHECKSUM" != "$ACTUAL_CHECKSUM" ]]; then
      log_error "CHECKSUM MISMATCH! Backup file is corrupted or modified."
      log_error "  Expected: $EXPECTED_CHECKSUM"
      log_error "  Actual:   $ACTUAL_CHECKSUM"
      exit 3
    fi
    log_info "Checksum verification PASSED ($ACTUAL_CHECKSUM)."
  else
    log_warn "Manifest found but sha256_checksum key was not parsed; proceeding with caution."
  fi
else
  log_warn "No manifest file found at $MANIFEST_FILE; checksum verification skipped."
fi

# ------------------------------------------------------------------------------
# Import Private GPG Key (if supplied)
# ------------------------------------------------------------------------------
if [[ -n "$GPG_KEY_FILE" ]]; then
  if [[ ! -f "$GPG_KEY_FILE" ]]; then
    log_error "Provided GPG key file does not exist: $GPG_KEY_FILE"
    exit 4
  fi
  log_info "Importing recovery GPG key into temporary keyring..."
  gpg --batch --import "$GPG_KEY_FILE"
fi

# ------------------------------------------------------------------------------
# Decrypt Archive to Secure Temporary Storage
# ------------------------------------------------------------------------------
TMP_RESTORE_DIR="$(mktemp -d -t cable_restore_XXXXXX)"
chmod 0700 "$TMP_RESTORE_DIR"

cleanup() {
  local exit_code=$?
  if [[ -d "$TMP_RESTORE_DIR" ]]; then
    rm -rf "$TMP_RESTORE_DIR"
  fi
  if [[ $exit_code -ne 0 ]]; then
    log_error "Restore aborted or encountered an error (exit code $exit_code)."
  fi
}
trap cleanup EXIT INT TERM

DECRYPTED_DUMP="${TMP_RESTORE_DIR}/archive.dump"
log_info "Decrypting backup archive..."

if ! gpg --batch --yes --decrypt --output "$DECRYPTED_DUMP" "$BACKUP_FILE" 2>/dev/null; then
  log_error "GPG decryption failed. Ensure the corresponding private key is present in keyring."
  exit 5
fi

if [[ ! -s "$DECRYPTED_DUMP" ]]; then
  log_error "Decrypted dump file is empty or missing."
  exit 5
fi

# ------------------------------------------------------------------------------
# Validate Custom-Format Archive Structure
# ------------------------------------------------------------------------------
log_info "Validating archive format using pg_restore --list..."
set +e
docker compose -p "$COMPOSE_PROJECT" -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
  pg_restore --list < "$DECRYPTED_DUMP" >/dev/null 2>&1
VALIDATE_STATUS=$?
set -e

if [[ $VALIDATE_STATUS -ne 0 ]]; then
  log_error "pg_restore archive validation failed! The decrypted file is not a valid PostgreSQL custom-format archive."
  exit 6
fi
log_info "Archive header and table of contents validated successfully."

# ------------------------------------------------------------------------------
# Target Database Check & Creation
# ------------------------------------------------------------------------------
log_info "Checking target database '$TARGET_DB'..."
DB_EXISTS="$(docker compose -p "$COMPOSE_PROJECT" -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
  psql -U "$POSTGRES_USER" -d postgres -t -A -c "SELECT 1 FROM pg_database WHERE datname = '${TARGET_DB}';" 2>/dev/null | tr -d '\r')"

if [[ "$DB_EXISTS" != "1" ]]; then
  log_info "Target database '$TARGET_DB' does not exist. Creating..."
  docker compose -p "$COMPOSE_PROJECT" -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
    psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE \"${TARGET_DB}\";" >/dev/null
else
  log_info "Target database '$TARGET_DB' already exists."
  # Check if database has existing tables
  TABLE_COUNT="$(docker compose -p "$COMPOSE_PROJECT" -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
    psql -U "$POSTGRES_USER" -d "$TARGET_DB" -t -A -c "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | tr -d '\r')"

  if [[ -n "$TABLE_COUNT" && "$TABLE_COUNT" -gt 0 ]]; then
    if [[ "$OVERWRITE_EXISTING" != "true" ]]; then
      log_error "Target database '$TARGET_DB' contains $TABLE_COUNT existing tables and --overwrite-existing was not specified."
      log_error "Aborting to prevent accidental data corruption or schema collisions."
      exit 7
    else
      log_warn "Target database contains $TABLE_COUNT tables. --overwrite-existing is set; proceeding with restore."
    fi
  fi
fi

# ------------------------------------------------------------------------------
# Execute Restoration
# ------------------------------------------------------------------------------
log_info "Restoring data into database '$TARGET_DB'..."
set +e
docker compose -p "$COMPOSE_PROJECT" -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
  pg_restore -U "$POSTGRES_USER" -d "$TARGET_DB" --no-owner --no-privileges --clean --if-exists < "$DECRYPTED_DUMP" >/dev/null 2>&1
RESTORE_STATUS=$?
set -e

# Note: pg_restore returns 0 on complete success, or 1 if warnings (e.g. drop table if exists when table didn't exist)
if [[ $RESTORE_STATUS -gt 1 ]]; then
  log_error "pg_restore failed with exit code $RESTORE_STATUS."
  exit 8
fi

# ------------------------------------------------------------------------------
# Verify Post-Restore Integrity
# ------------------------------------------------------------------------------
log_info "Verifying restored database integrity..."

ALEMBIC_VERSION="$(docker compose -p "$COMPOSE_PROJECT" -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
  psql -U "$POSTGRES_USER" -d "$TARGET_DB" -t -A -c "SELECT version_num FROM alembic_version LIMIT 1;" 2>/dev/null | tr -d '\r' || echo "UNKNOWN")"

CUSTOMER_COUNT="$(docker compose -p "$COMPOSE_PROJECT" -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
  psql -U "$POSTGRES_USER" -d "$TARGET_DB" -t -A -c "SELECT count(*) FROM customers;" 2>/dev/null | tr -d '\r' || echo "0")"

INVOICE_COUNT="$(docker compose -p "$COMPOSE_PROJECT" -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
  psql -U "$POSTGRES_USER" -d "$TARGET_DB" -t -A -c "SELECT count(*) FROM invoices;" 2>/dev/null | tr -d '\r' || echo "0")"

PAYMENT_COUNT="$(docker compose -p "$COMPOSE_PROJECT" -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
  psql -U "$POSTGRES_USER" -d "$TARGET_DB" -t -A -c "SELECT count(*) FROM payments;" 2>/dev/null | tr -d '\r' || echo "0")"

ALLOCATION_COUNT="$(docker compose -p "$COMPOSE_PROJECT" -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
  psql -U "$POSTGRES_USER" -d "$TARGET_DB" -t -A -c "SELECT count(*) FROM payment_allocations;" 2>/dev/null | tr -d '\r' || echo "0")"

log_info "==================================================================="
log_info "RESTORATION COMPLETED SUCCESSFULLY"
log_info "  Target Database:        $TARGET_DB"
log_info "  Alembic Head Version:   $ALEMBIC_VERSION"
log_info "  Customer Records:       $CUSTOMER_COUNT"
log_info "  Invoice Records:        $INVOICE_COUNT"
log_info "  Payment Records:        $PAYMENT_COUNT"
log_info "  Allocation Records:     $ALLOCATION_COUNT"
log_info "==================================================================="

exit 0
