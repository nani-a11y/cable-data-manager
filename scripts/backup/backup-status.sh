#!/usr/bin/env bash
# ==============================================================================
# CABLE DATA MANAGER — BACKUP STATUS & MONITORING UTILITY
#
# Inspects backup storage, reports the latest backup status, validates its
# SHA-256 manifest checksum, and displays available disk space.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

BACKUP_DIR="${BACKUP_DIR:-/mnt/cable-manager-backups}"
ENV_FILE="${ENV_FILE:-${PROJECT_ROOT}/.env}"
REQUIRE_MOUNT="${REQUIRE_MOUNT:-false}"

if [[ -f "$ENV_FILE" ]]; then
  while IFS='=' read -r key val || [[ -n "$key" ]]; do
    [[ "$key" =~ ^#.*$ || -z "$key" ]] && continue
    val="${val%\"}"
    val="${val#\"}"
    val="${val%\'}"
    val="${val#\'}"
    case "$key" in
      BACKUP_DIR) BACKUP_DIR="${BACKUP_DIR:-$val}" ;;
      REQUIRE_MOUNT) REQUIRE_MOUNT="${REQUIRE_MOUNT:-$val}" ;;
    esac
  done < "$ENV_FILE"
fi

printf "===================================================================\n"
printf " CABLE DATA MANAGER — BACKUP STATUS\n"
printf "===================================================================\n"
printf "Backup Directory: %s\n" "$BACKUP_DIR"

if [[ ! -d "$BACKUP_DIR" ]]; then
  printf "Status:           FAILED (Directory does not exist)\n"
  exit 1
fi

if [[ "$REQUIRE_MOUNT" == "true" ]]; then
  if mountpoint -q "$BACKUP_DIR" 2>/dev/null; then
    printf "Mount Status:     MOUNTED (External storage verified)\n"
  else
    printf "Mount Status:     NOT MOUNTED (External storage missing!)\n"
  fi
fi

AVAILABLE_SPACE="$(df -h "$BACKUP_DIR" | awk 'NR==2 {print $4}')"
AVAILABLE_PCT="$(df -h "$BACKUP_DIR" | awk 'NR==2 {print $5}')"
printf "Storage Space:    %s available (%s used)\n" "$AVAILABLE_SPACE" "$AVAILABLE_PCT"

TOTAL_BACKUPS="$(find "$BACKUP_DIR" -maxdepth 1 -name "cable_backup_*.dump.gpg" 2>/dev/null | wc -l)"
printf "Total Backups:    %s\n" "$TOTAL_BACKUPS"

if [[ "$TOTAL_BACKUPS" -eq 0 ]]; then
  printf "Latest Backup:    NONE FOUND\n"
  printf "Health:           WARNING (No backups have been created yet)\n"
  printf "===================================================================\n"
  exit 2
fi

LATEST_BACKUP="$(find "$BACKUP_DIR" -maxdepth 1 -name "cable_backup_*.dump.gpg" | sort | tail -n 1)"
LATEST_NAME="$(basename "$LATEST_BACKUP")"
LATEST_MANIFEST="${LATEST_BACKUP%.dump.gpg}.manifest"
LATEST_SIZE="$(stat -c%s "$LATEST_BACKUP" 2>/dev/null || stat -f%z "$LATEST_BACKUP")"

printf "\nLatest Backup Details:\n"
printf "  File:           %s\n" "$LATEST_NAME"
printf "  Size:           %s bytes\n" "$LATEST_SIZE"

if [[ -f "$LATEST_MANIFEST" ]]; then
  TIMESTAMP_UTC="$(grep "^timestamp_utc=" "$LATEST_MANIFEST" | cut -d'=' -f2 || echo "Unknown")"
  EXPECTED_SHA="$(grep "^sha256_checksum=" "$LATEST_MANIFEST" | cut -d'=' -f2 || echo "")"
  DB_NAME="$(grep "^database_name=" "$LATEST_MANIFEST" | cut -d'=' -f2 || echo "Unknown")"

  printf "  Timestamp (UTC):%s\n" "$TIMESTAMP_UTC"
  printf "  Database:       %s\n" "$DB_NAME"

  if [[ -n "$EXPECTED_SHA" ]]; then
    ACTUAL_SHA="$(sha256sum "$LATEST_BACKUP" | awk '{print $1}')"
    if [[ "$EXPECTED_SHA" == "$ACTUAL_SHA" ]]; then
      printf "  Integrity:      VERIFIED (SHA-256 match)\n"
      printf "  Checksum:       %s\n" "$ACTUAL_SHA"
      printf "\nOverall Status:   HEALTHY\n"
      printf "===================================================================\n"
      exit 0
    else
      printf "  Integrity:      CORRUPTED (Checksum mismatch!)\n"
      printf "    Expected:     %s\n" "$EXPECTED_SHA"
      printf "    Actual:       %s\n" "$ACTUAL_SHA"
      printf "\nOverall Status:   CRITICAL FAILURE\n"
      printf "===================================================================\n"
      exit 3
    fi
  else
    printf "  Integrity:      UNVERIFIED (No checksum recorded in manifest)\n"
  fi
else
  printf "  Manifest:       MISSING (%s)\n" "$(basename "$LATEST_MANIFEST")"
  printf "  Integrity:      UNVERIFIED\n"
fi

printf "===================================================================\n"
exit 0
