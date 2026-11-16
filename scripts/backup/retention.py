#!/usr/bin/env python3
"""Cable Data Manager — Backup Retention Engine

Implements configurable, deterministic backup retention policies:
- Daily: Keep 1 backup per day for the last N distinct days (default: 14).
- Weekly: Keep 1 backup per week for the last N distinct weeks (default: 8).
- Monthly: Keep 1 backup per month for the last N distinct months (default: 12).

Safety Rules:
1. The newest verified backup is ALWAYS preserved.
2. Unverified or missing-manifest backups are never deleted by this automated script.
3. Cleanup never deletes all backups.
4. Only deletes files within the configured backup directory matching the backup pattern.
5. Never follows symbolic links.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys

BACKUP_REGEX = re.compile(r"^cable_backup_(\d{8})_(\d{6})Z\.dump\.gpg$")
TIMESTAMP_FORMAT = "%Y%m%d_%H%M%SZ"


@dataclass
class BackupEntry:
    path: Path
    manifest_path: Path
    timestamp: datetime
    is_valid: bool
    reasons_kept: list[str]


def parse_backup_timestamp(filename: str) -> datetime | None:
    match = BACKUP_REGEX.match(filename)
    if not match:
        return None
    ts_str = f"{match.group(1)}_{match.group(2)}Z"
    try:
        return datetime.strptime(ts_str, TIMESTAMP_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def is_manifest_verified(manifest_path: Path, expected_filename: str) -> bool:
    if not manifest_path.is_file() or manifest_path.is_symlink():
        return False
    try:
        content = manifest_path.read_text(encoding="utf-8")
        status_verified = False
        file_matches = False
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("verification_status=") and line.split("=", 1)[1].strip() == "VERIFIED":
                status_verified = True
            elif line.startswith("encrypted_file="):
                enc_file = line.split("=", 1)[1].strip()
                if enc_file == expected_filename:
                    file_matches = True
        return status_verified and file_matches
    except Exception:
        return False


def collect_backups(backup_dir: Path) -> list[BackupEntry]:
    entries: list[BackupEntry] = []
    if not backup_dir.is_dir():
        return entries

    resolved_dir = backup_dir.resolve()
    for item in sorted(backup_dir.iterdir()):
        # Never follow symlinks and ensure file is strictly inside backup_dir
        if item.is_symlink():
            continue
        if not item.is_file():
            continue
        try:
            if item.resolve().parent != resolved_dir:
                continue
        except Exception:
            continue

        ts = parse_backup_timestamp(item.name)
        if not ts:
            continue

        base_name = item.name[:-9]  # strip .dump.gpg
        manifest_path = backup_dir / f"{base_name}.manifest"
        is_verified = is_manifest_verified(manifest_path, item.name)

        entries.append(
            BackupEntry(
                path=item,
                manifest_path=manifest_path,
                timestamp=ts,
                is_valid=is_verified,
                reasons_kept=[],
            )
        )

    # Sort descending deterministically by timestamp, then filename
    entries.sort(key=lambda b: (b.timestamp, b.path.name), reverse=True)
    return entries


def evaluate_retention(
    entries: list[BackupEntry],
    daily_count: int = 14,
    weekly_count: int = 8,
    monthly_count: int = 12,
) -> tuple[list[BackupEntry], list[BackupEntry]]:
    """Evaluates which backups to keep and which to prune.

    Returns: (kept_entries, pruned_entries)
    """
    valid_entries = [e for e in entries if e.is_valid]
    if not valid_entries:
        return (entries, [])

    kept_map: dict[Path, BackupEntry] = {}

    # Rule 1: Always keep the newest verified backup
    newest = valid_entries[0]
    newest.reasons_kept.append("newest_backup")
    kept_map[newest.path] = newest

    # Rule 2: Daily policy — newest backup for each of the last N distinct days
    daily_seen: dict[str, BackupEntry] = {}
    for entry in valid_entries:
        day_str = entry.timestamp.strftime("%Y-%m-%d")
        if day_str not in daily_seen and len(daily_seen) < daily_count:
            daily_seen[day_str] = entry
            entry.reasons_kept.append(f"daily_{day_str}")
            kept_map[entry.path] = entry

    # Rule 3: Weekly policy — newest backup for each of the last N distinct ISO weeks
    weekly_seen: dict[str, BackupEntry] = {}
    for entry in valid_entries:
        year, week, _ = entry.timestamp.isocalendar()
        week_str = f"{year}-W{week:02d}"
        if week_str not in weekly_seen and len(weekly_seen) < weekly_count:
            weekly_seen[week_str] = entry
            entry.reasons_kept.append(f"weekly_{week_str}")
            kept_map[entry.path] = entry

    # Rule 4: Monthly policy — newest backup for each of the last N distinct months
    monthly_seen: dict[str, BackupEntry] = {}
    for entry in valid_entries:
        month_str = entry.timestamp.strftime("%Y-%m")
        if month_str not in monthly_seen and len(monthly_seen) < monthly_count:
            monthly_seen[month_str] = entry
            entry.reasons_kept.append(f"monthly_{month_str}")
            kept_map[entry.path] = entry

    kept: list[BackupEntry] = []
    pruned: list[BackupEntry] = []

    for entry in entries:
        if not entry.is_valid:
            # Unverified backups are preserved for operator inspection
            entry.reasons_kept.append("unverified_preservation")
            kept.append(entry)
        elif entry.path in kept_map:
            kept.append(entry)
        else:
            pruned.append(entry)

    # Absolute Safety Check: Never prune all backups
    if entries and not kept:
        raise RuntimeError("Safety failure: retention policy resulted in zero preserved backups! Aborting.")

    return kept, pruned


def execute_pruning(pruned: list[BackupEntry], backup_dir: Path, dry_run: bool = True) -> list[str]:
    deleted_files: list[str] = []
    resolved_dir = backup_dir.resolve()

    for entry in pruned:
        # Enforce containment: neither entry.path nor manifest_path can be outside backup_dir
        try:
            if entry.path.resolve().parent != resolved_dir:
                print(f"Safety warning: skipping {entry.path}; does not reside directly in {backup_dir}", file=sys.stderr)
                continue
            if entry.manifest_path.exists() and entry.manifest_path.resolve().parent != resolved_dir:
                print(f"Safety warning: skipping {entry.manifest_path}; does not reside directly in {backup_dir}", file=sys.stderr)
                continue
        except Exception as exc:
            print(f"Path resolution error on {entry.path}: {exc}", file=sys.stderr)
            continue

        if dry_run:
            deleted_files.append(str(entry.path))
            if entry.manifest_path.exists():
                deleted_files.append(str(entry.manifest_path))
        else:
            try:
                if entry.path.is_file() and not entry.path.is_symlink():
                    entry.path.unlink()
                    deleted_files.append(str(entry.path))
                if entry.manifest_path.is_file() and not entry.manifest_path.is_symlink():
                    entry.manifest_path.unlink()
                    deleted_files.append(str(entry.manifest_path))
            except Exception as exc:
                print(f"Error removing {entry.path}: {exc}", file=sys.stderr)

    return deleted_files


def main() -> int:
    parser = argparse.ArgumentParser(description="Cable Data Manager Backup Retention Manager")
    parser.add_argument("--backup-dir", type=Path, default=Path("/mnt/cable-manager-backups"), help="Directory containing backups")
    parser.add_argument("--daily", type=int, default=14, help="Number of daily backups to keep (default: 14)")
    parser.add_argument("--weekly", type=int, default=8, help="Number of weekly backups to keep (default: 8)")
    parser.add_argument("--monthly", type=int, default=12, help="Number of monthly backups to keep (default: 12)")
    parser.add_argument("--apply", action="store_true", help="Actually delete pruned backups (defaults to dry-run)")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    args = parser.parse_args()

    if not args.backup_dir.exists():
        print(f"Error: Backup directory does not exist: {args.backup_dir}", file=sys.stderr)
        return 1

    entries = collect_backups(args.backup_dir)
    try:
        kept, pruned = evaluate_retention(
            entries,
            daily_count=args.daily,
            weekly_count=args.weekly,
            monthly_count=args.monthly,
        )
    except Exception as exc:
        print(f"Retention evaluation error: {exc}", file=sys.stderr)
        return 2

    dry_run = not args.apply
    deleted = execute_pruning(pruned, backup_dir=args.backup_dir, dry_run=dry_run)

    summary = {
        "backup_dir": str(args.backup_dir),
        "total_backups_found": len(entries),
        "kept_count": len(kept),
        "pruned_count": len(pruned),
        "dry_run": dry_run,
        "deleted_files_count": len(deleted),
        "kept": [
            {
                "file": e.path.name,
                "timestamp": e.timestamp.isoformat(),
                "is_valid": e.is_valid,
                "reasons": sorted(set(e.reasons_kept)),
            }
            for e in kept
        ],
        "pruned": [
            {
                "file": e.path.name,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in pruned
        ],
    }

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"Backup Retention Analysis for {args.backup_dir}:")
        print(f"  Total backups found: {len(entries)}")
        print(f"  Backups kept:        {len(kept)}")
        print(f"  Backups pruned:      {len(pruned)} ({'DRY RUN - no files deleted' if dry_run else 'APPLIED'})")
        for p in pruned:
            action = "Would delete" if dry_run else "Deleted"
            print(f"    - {action}: {p.path.name}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
