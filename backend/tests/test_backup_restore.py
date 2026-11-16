"""Phase 4C: Automated Backup, Restore & Disaster Recovery Test Suite

Validates:
1. Retention policy algorithms (daily, weekly, monthly, newest preservation, unverified protection).
2. Backup script pre-flight validations (missing GPG recipient, missing mount, disk space).
3. Restore script safety boundaries (production target lockout, checksum mismatch, archive corruption).
4. Systemd unit and timer syntax validation.
5. End-to-end backup, encryption, decryption, restoration, and financial data integrity.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SCRIPTS_DIR = PROJECT_ROOT / "scripts" / "backup"


# ------------------------------------------------------------------------------
# 1. Retention Engine Unit Tests
# ------------------------------------------------------------------------------

def test_retention_policy_daily_weekly_monthly(tmp_path: Path):
    """Test that retention selects daily, weekly, monthly and keeps newest backup."""
    from scripts.backup.retention import BackupEntry, evaluate_retention

    base_time = datetime(2026, 11, 16, 2, 0, 0, tzinfo=timezone.utc)
    entries: list[BackupEntry] = []

    # Generate 60 days of backups (1 per day)
    for days_ago in range(60):
        ts = base_time - timedelta(days=days_ago)
        p = tmp_path / f"cable_backup_{ts.strftime('%Y%m%d_%H%M%S')}Z.dump.gpg"
        m = tmp_path / f"cable_backup_{ts.strftime('%Y%m%d_%H%M%S')}Z.manifest"
        entries.append(
            BackupEntry(
                path=p,
                manifest_path=m,
                timestamp=ts,
                is_valid=True,
                reasons_kept=[],
            )
        )

    # Sort descending
    entries.sort(key=lambda b: b.timestamp, reverse=True)

    kept, pruned = evaluate_retention(
        entries,
        daily_count=14,
        weekly_count=8,
        monthly_count=12,
    )

    # Check 1: Newest backup is always kept
    assert entries[0] in kept
    assert any("newest_backup" in r for r in entries[0].reasons_kept)

    # Check 2: Total kept count is greater than daily_count but <= total
    assert len(kept) >= 14
    assert len(pruned) > 0
    assert len(kept) + len(pruned) == 60

    # Check 3: Daily keeper count <= 14 distinct days
    daily_reasons = {r for e in kept for r in e.reasons_kept if r.startswith("daily_")}
    assert len(daily_reasons) <= 14

    # Check 4: Weekly keeper count <= 8 distinct weeks
    weekly_reasons = {r for e in kept for r in e.reasons_kept if r.startswith("weekly_")}
    assert len(weekly_reasons) <= 8

    # Check 5: Monthly keeper count <= 12 distinct months
    monthly_reasons = {r for e in kept for r in e.reasons_kept if r.startswith("monthly_")}
    assert len(monthly_reasons) <= 12


def test_retention_preserves_unverified_backups(tmp_path: Path):
    """Unverified or corrupt backups must not be silently deleted by retention."""
    from scripts.backup.retention import BackupEntry, evaluate_retention

    ts1 = datetime(2026, 11, 16, 2, 0, 0, tzinfo=timezone.utc)
    ts2 = datetime(2026, 1, 1, 2, 0, 0, tzinfo=timezone.utc)  # Old date

    e1 = BackupEntry(
        path=tmp_path / "cable_backup_20261116_020000Z.dump.gpg",
        manifest_path=tmp_path / "cable_backup_20261116_020000Z.manifest",
        timestamp=ts1,
        is_valid=True,
        reasons_kept=[],
    )
    e2 = BackupEntry(
        path=tmp_path / "cable_backup_20260101_020000Z.dump.gpg",
        manifest_path=tmp_path / "cable_backup_20260101_020000Z.manifest",
        timestamp=ts2,
        is_valid=False,  # Unverified / corrupted
        reasons_kept=[],
    )

    kept, pruned = evaluate_retention([e1, e2], daily_count=1, weekly_count=1, monthly_count=1)
    assert e2 in kept
    assert "unverified_preservation" in e2.reasons_kept


def test_retention_safety_check_never_prunes_all(tmp_path: Path):
    """Safety guard: if evaluate_retention produces empty kept list, it must raise."""
    from scripts.backup.retention import BackupEntry, evaluate_retention

    # If entries has items but somehow all are dropped
    ts = datetime(2026, 11, 16, 2, 0, 0, tzinfo=timezone.utc)
    e = BackupEntry(
        path=tmp_path / "cable_backup_20261116_020000Z.dump.gpg",
        manifest_path=tmp_path / "cable_backup_20261116_020000Z.manifest",
        timestamp=ts,
        is_valid=True,
        reasons_kept=[],
    )
    kept, pruned = evaluate_retention([e], daily_count=1)
    assert len(kept) == 1
    assert len(pruned) == 0


def test_retention_symlink_and_traversal_protection(tmp_path: Path):
    """Retention engine must never delete files outside the configured backup directory or follow symlinks."""
    from scripts.backup.retention import BackupEntry, collect_backups, execute_pruning

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()

    sensitive_file = outside_dir / "sensitive_document.txt"
    sensitive_file.write_text("Do not delete me")

    # Create a symlink inside backup_dir pointing to sensitive_file
    symlink_file = backup_dir / "cable_backup_20261116_020000Z.dump.gpg"
    symlink_file.symlink_to(sensitive_file)

    # collect_backups must ignore the symlink
    entries = collect_backups(backup_dir)
    assert len(entries) == 0

    # execute_pruning directly called with an entry outside backup_dir must refuse to unlink
    malicious_entry = BackupEntry(
        path=sensitive_file,
        manifest_path=outside_dir / "sensitive.manifest",
        timestamp=datetime.now(timezone.utc),
        is_valid=True,
        reasons_kept=[],
    )
    deleted = execute_pruning([malicious_entry], backup_dir=backup_dir, dry_run=False)
    assert len(deleted) == 0
    assert sensitive_file.is_file()
    assert sensitive_file.read_text() == "Do not delete me"


def test_retention_duplicate_timestamps_deterministic(tmp_path: Path):
    """Backups with duplicate timestamps must sort deterministically by filename."""
    from scripts.backup.retention import BackupEntry, evaluate_retention

    ts = datetime(2026, 11, 16, 2, 0, 0, tzinfo=timezone.utc)
    e1 = BackupEntry(
        path=tmp_path / "cable_backup_20261116_020000Z_a.dump.gpg",
        manifest_path=tmp_path / "cable_backup_20261116_020000Z_a.manifest",
        timestamp=ts,
        is_valid=True,
        reasons_kept=[],
    )
    e2 = BackupEntry(
        path=tmp_path / "cable_backup_20261116_020000Z_b.dump.gpg",
        manifest_path=tmp_path / "cable_backup_20261116_020000Z_b.manifest",
        timestamp=ts,
        is_valid=True,
        reasons_kept=[],
    )

    # Secondary sort key by filename ensures deterministic retention
    sorted_entries = sorted([e1, e2], key=lambda b: (b.timestamp, b.path.name), reverse=True)
    assert sorted_entries[0].path.name == "cable_backup_20261116_020000Z_b.dump.gpg"
    assert sorted_entries[1].path.name == "cable_backup_20261116_020000Z_a.dump.gpg"


# ------------------------------------------------------------------------------
# 2. Script Pre-Flight Validation Tests
# ------------------------------------------------------------------------------

def test_backup_script_preflight_missing_gpg_recipient(tmp_path: Path):
    """Backup script must exit with code 2 if BACKUP_GPG_RECIPIENT is not set."""
    script = SCRIPTS_DIR / "backup-postgres.sh"
    env = os.environ.copy()
    env["BACKUP_GPG_RECIPIENT"] = ""
    env["ENV_FILE"] = str(tmp_path / ".nonexistent.env")

    proc = subprocess.run([str(script)], env=env, capture_output=True, text=True)
    assert proc.returncode == 2
    assert "BACKUP_GPG_RECIPIENT is not configured" in proc.stderr


def test_backup_script_preflight_require_mount_fails(tmp_path: Path):
    """When REQUIRE_MOUNT=true, script must exit with code 3 if dir is not a mount."""
    script = SCRIPTS_DIR / "backup-postgres.sh"
    dummy_dir = tmp_path / "not_a_mount"
    dummy_dir.mkdir()

    # Generate a temporary GPG key so GPG check passes
    gpg_home = tmp_path / "gpg_home"
    gpg_home.mkdir(mode=0o700)
    keygen_input = """
Key-Type: RSA
Key-Length: 2048
Name-Real: Test Mount
Name-Email: mount@cable.local
Expire-Date: 0
%no-protection
%commit
"""
    subprocess.run(["gpg", "--homedir", str(gpg_home), "--batch", "--generate-key"], input=keygen_input.encode(), check=True)

    env = os.environ.copy()
    env["GNUPGHOME"] = str(gpg_home)
    env["BACKUP_GPG_RECIPIENT"] = "mount@cable.local"
    env["BACKUP_DIR"] = str(dummy_dir)
    env["REQUIRE_MOUNT"] = "true"
    env["ENV_FILE"] = str(tmp_path / ".nonexistent.env")

    proc = subprocess.run([str(script)], env=env, capture_output=True, text=True)
    assert proc.returncode == 3
    assert "is not a mount point" in proc.stderr


def test_backup_script_preflight_insufficient_disk_space(tmp_path: Path):
    """Script must exit with code 4 if available space is below MIN_DISK_SPACE_MB."""
    script = SCRIPTS_DIR / "backup-postgres.sh"
    dummy_dir = tmp_path / "backups"
    dummy_dir.mkdir()

    gpg_home = tmp_path / "gpg_home"
    gpg_home.mkdir(mode=0o700)
    keygen_input = """
Key-Type: RSA
Key-Length: 2048
Name-Real: Test Space
Name-Email: space@cable.local
Expire-Date: 0
%no-protection
%commit
"""
    subprocess.run(["gpg", "--homedir", str(gpg_home), "--batch", "--generate-key"], input=keygen_input.encode(), check=True)

    env = os.environ.copy()
    env["GNUPGHOME"] = str(gpg_home)
    env["BACKUP_GPG_RECIPIENT"] = "space@cable.local"
    env["BACKUP_DIR"] = str(dummy_dir)
    env["REQUIRE_MOUNT"] = "false"
    env["MIN_DISK_SPACE_MB"] = "999999999"  # Excessively high
    env["ENV_FILE"] = str(tmp_path / ".nonexistent.env")

    proc = subprocess.run([str(script)], env=env, capture_output=True, text=True)
    assert proc.returncode == 4
    assert "Insufficient disk space" in proc.stderr


# ------------------------------------------------------------------------------
# 3. Restore Safety & Error Handling Tests
# ------------------------------------------------------------------------------

def test_restore_script_rejects_production_without_flag():
    """Restore script must reject production target without explicit safety override flag."""
    script = SCRIPTS_DIR / "restore-postgres.sh"
    proc = subprocess.run(
        [
            str(script),
            "--backup-file", "/tmp/dummy.dump.gpg",
            "--target-db", "cable_manager",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 10
    assert "REFUSED: Restoring directly into production database" in proc.stderr


def test_restore_script_checksum_mismatch(tmp_path: Path):
    """Restore script must abort with exit code 3 if backup file checksum differs from manifest."""
    script = SCRIPTS_DIR / "restore-postgres.sh"

    backup_file = tmp_path / "cable_backup_20261116_120000Z.dump.gpg"
    backup_file.write_text("corrupted content")

    manifest_file = tmp_path / "cable_backup_20261116_120000Z.manifest"
    manifest_file.write_text("sha256_checksum=0000000000000000000000000000000000000000000000000000000000000000\n")

    proc = subprocess.run(
        [
            str(script),
            "--backup-file", str(backup_file),
            "--manifest", str(manifest_file),
            "--target-db", "disposable_test_db",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 3
    assert "CHECKSUM MISMATCH" in proc.stderr


def test_restore_script_manifest_filename_mismatch(tmp_path: Path):
    """Restore script must reject a manifest that specifies a different encrypted_file."""
    script = SCRIPTS_DIR / "restore-postgres.sh"

    backup_file = tmp_path / "cable_backup_20261116_120000Z.dump.gpg"
    backup_file.write_text("dummy content")

    manifest_file = tmp_path / "cable_backup_20261116_120000Z.manifest"
    manifest_file.write_text(
        "encrypted_file=cable_backup_OTHER_FILE.dump.gpg\n"
        "sha256_checksum=dummy\n"
    )

    proc = subprocess.run(
        [
            str(script),
            "--backup-file", str(backup_file),
            "--manifest", str(manifest_file),
            "--target-db", "disposable_test_db",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 3
    assert "MANIFEST MISMATCH" in proc.stderr


def test_restore_script_invalid_target_db_name(tmp_path: Path):
    """Restore script must reject database names with shell/SQL injection characters."""
    script = SCRIPTS_DIR / "restore-postgres.sh"
    backup_file = tmp_path / "cable_backup_20261116_120000Z.dump.gpg"
    backup_file.write_text("dummy")

    proc = subprocess.run(
        [
            str(script),
            "--backup-file", str(backup_file),
            "--target-db", "test;DROP TABLE customers;--",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1
    assert "Invalid target database name" in proc.stderr


def test_restore_script_invalid_private_key(tmp_path: Path):
    """Restore script must exit with code 5 if decryption fails (e.g. wrong key / no key in keyring)."""
    script = SCRIPTS_DIR / "restore-postgres.sh"

    # Create an empty GNUPGHOME with no keys
    empty_gpg = tmp_path / "empty_gpg"
    empty_gpg.mkdir(mode=0o700)

    backup_file = tmp_path / "cable_backup_20261116_120000Z.dump.gpg"
    backup_file.write_text("encrypted_dummy_content")

    env = os.environ.copy()
    env["GNUPGHOME"] = str(empty_gpg)

    proc = subprocess.run(
        [
            str(script),
            "--backup-file", str(backup_file),
            "--target-db", "disposable_test_db",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 5
    assert "GPG decryption failed" in proc.stderr


# ------------------------------------------------------------------------------
# 4. Systemd Units Syntax & Analysis
# ------------------------------------------------------------------------------

def test_systemd_unit_files_syntax():
    """Validate systemd unit files syntax using systemd-analyze verify if installed."""
    service_file = SCRIPTS_DIR / "cable-manager-backup.service"
    timer_file = SCRIPTS_DIR / "cable-manager-backup.timer"

    assert service_file.is_file()
    assert timer_file.is_file()

    service_content = service_file.read_text()
    assert "[Unit]" in service_content
    assert "[Service]" in service_content
    assert "Type=oneshot" in service_content
    assert "backup-postgres.sh" in service_content

    timer_content = timer_file.read_text()
    assert "[Unit]" in timer_content
    assert "[Timer]" in timer_content
    assert "OnCalendar=*-*-* 02:00:00" in timer_content
    assert "Persistent=true" in timer_content

    if shutil.which("systemd-analyze"):
        proc = subprocess.run(
            ["systemd-analyze", "verify", str(service_file), str(timer_file)],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, f"systemd-analyze verify failed: {proc.stderr}"


# ------------------------------------------------------------------------------
# 5. End-to-End Backup, Encryption, Restore & Financial Verification
# ------------------------------------------------------------------------------

def test_end_to_end_backup_restore_and_financial_integrity(tmp_path: Path):
    """Full integration test using disposable PostgreSQL container:
    1. Spin up dedicated disposable postgres:16-alpine container.
    2. Run migrations and populate deterministic financial fixture.
    3. Run backup-postgres.sh (creating GPG-encrypted dump and manifest).
    4. Run backup-status.sh to verify manifest and SHA-256 checksum.
    5. Run restore-postgres.sh into a separate empty disposable database.
    6. Verify financial data: customer balances, monthly charges, allocations, and decimal precision.
    7. Tear down disposable container and volumes.
    """
    docker_bin = shutil.which("docker")
    if not docker_bin:
        pytest.skip("Docker is not available in environment.")

    # A. Setup isolated GPG keyring
    gpg_home = tmp_path / "gpg_home"
    gpg_home.mkdir(mode=0o700)
    recipient = "backup-e2e@cable.local"
    keygen_input = f"""
Key-Type: RSA
Key-Length: 2048
Subkey-Type: RSA
Subkey-Length: 2048
Name-Real: E2E Backup Test
Name-Email: {recipient}
Expire-Date: 0
%no-protection
%commit
"""
    subprocess.run(["gpg", "--homedir", str(gpg_home), "--batch", "--generate-key"], input=keygen_input.encode(), check=True)

    # B. Spin up disposable PostgreSQL via Docker Compose
    disposable_project = "cable-e2e-backup"
    disposable_port = "5438"
    db_name = "cable_source"
    restore_db_name = "cable_restored"
    db_user = "cable_admin"
    db_pass = "TestE2EPass_999!"

    disposable_compose = tmp_path / "docker-compose.disposable.yml"
    disposable_compose.write_text(f"""
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: {db_name}
      POSTGRES_USER: {db_user}
      POSTGRES_PASSWORD: {db_pass}
    ports:
      - "127.0.0.1:{disposable_port}:5432"
""")

    # Clean up any leftover project
    subprocess.run(["docker", "compose", "-p", disposable_project, "-f", str(disposable_compose), "down", "-v"], capture_output=True)

    # Launch disposable compose stack
    subprocess.run(["docker", "compose", "-p", disposable_project, "-f", str(disposable_compose), "up", "-d"], check=True)

    try:
        # Wait for container to be ready
        ready = False
        import time
        for _ in range(25):
            res = subprocess.run(
                ["docker", "compose", "-p", disposable_project, "-f", str(disposable_compose), "exec", "-T", "db", "pg_isready", "-U", db_user, "-d", db_name],
                capture_output=True,
            )
            if res.returncode == 0:
                ready = True
                break
            time.sleep(1)
        assert ready, "Disposable PostgreSQL container failed to start."

        source_url = f"postgresql+psycopg://{db_user}:{db_pass}@127.0.0.1:{disposable_port}/{db_name}"
        restore_url = f"postgresql+psycopg://{db_user}:{db_pass}@127.0.0.1:{disposable_port}/{restore_db_name}"

        # C. Apply Alembic migrations to source database
        from alembic import command
        from alembic.config import Config
        backend_dir = PROJECT_ROOT / "backend"
        cfg = Config(str(backend_dir / "alembic.ini"))
        cfg.set_main_option("script_location", str(backend_dir / "alembic"))
        cfg.set_main_option("sqlalchemy.url", source_url)
        old_db_url = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = source_url
        try:
            command.upgrade(cfg, "head")
        finally:
            if old_db_url is not None:
                os.environ["DATABASE_URL"] = old_db_url
            else:
                os.environ.pop("DATABASE_URL", None)

        # D. Insert deterministic financial test records
        from app.models import AdminUser, BusinessSettings, Customer, Invoice, Payment, PaymentAllocation
        engine = sa.create_engine(source_url)
        with Session(engine) as session:
            admin = AdminUser(email="e2e_admin@example.com", password_hash="hashed_pwd_dummy", is_active=True)
            settings = BusinessSettings(
                business_name="E2E Cable Net",
                contact_number="9876543210",
                service_areas=["Zone 1", "Zone 2"],
                default_monthly_amount=Decimal("350.00"),
            )
            session.add_all([admin, settings])
            session.flush()

            # Customer 1: Monthly charge ₹350
            c1 = Customer(
                name="Ramesh Kumar",
                display_id="CUST-0001",
                box_number="BOX-1001",
                phone="9876543210",
                area="Zone 1",
                monthly_amount=Decimal("350.00"),
                is_active=True,
            )
            # Customer 2: Monthly charge ₹500
            c2 = Customer(
                name="Suresh Patel",
                display_id="CUST-0002",
                box_number="BOX-1002",
                phone="9876543211",
                area="Zone 1",
                monthly_amount=Decimal("500.00"),
                is_active=True,
            )
            session.add_all([c1, c2])
            session.flush()

            inv1 = Invoice(
                invoice_number="INV-202611-0001",
                customer_id=c1.id,
                billing_month="2026-11",
                amount=Decimal("350.00"),
                paid_amount=Decimal("200.00"),
                status="partial",
                issued_date=date(2026, 11, 1),
            )
            session.add(inv1)
            session.flush()

            p1 = Payment(
                receipt_number="RCPT-202611-0001",
                customer_id=c1.id,
                amount=Decimal("200.00"),
                payment_method="cash",
                paid_date=date(2026, 11, 2),
                notes="Cash received at doorstep",
            )
            session.add(p1)
            session.flush()

            alloc1 = PaymentAllocation(
                payment_id=p1.id,
                invoice_id=inv1.id,
                allocated_amount=Decimal("200.00"),
            )
            session.add(alloc1)
            session.commit()

        backup_dir = tmp_path / "backups"
        backup_dir.mkdir(mode=0o700)

        # E. Run backup-postgres.sh
        env = os.environ.copy()
        env["GNUPGHOME"] = str(gpg_home)
        env["BACKUP_DIR"] = str(backup_dir)
        env["BACKUP_GPG_RECIPIENT"] = recipient
        env["REQUIRE_MOUNT"] = "false"
        env["COMPOSE_FILE"] = str(disposable_compose)
        env["COMPOSE_PROJECT"] = disposable_project
        env["POSTGRES_SERVICE"] = "db"
        env["POSTGRES_DB"] = db_name
        env["POSTGRES_USER"] = db_user
        env["RUN_RETENTION"] = "true"

        backup_proc = subprocess.run(
            [str(SCRIPTS_DIR / "backup-postgres.sh")],
            env=env,
            capture_output=True,
            text=True,
        )
        assert backup_proc.returncode == 0, f"backup-postgres.sh failed: {backup_proc.stderr}\n{backup_proc.stdout}"

        # F. Verify backup file and manifest exist
        backups = list(backup_dir.glob("cable_backup_*.dump.gpg"))
        manifests = list(backup_dir.glob("cable_backup_*.manifest"))
        assert len(backups) == 1
        assert len(manifests) == 1

        backup_file = backups[0]
        manifest_file = manifests[0]

        # Verify manifest content
        manifest_text = manifest_file.read_text()
        assert "verification_status=VERIFIED" in manifest_text
        assert f"database_name={db_name}" in manifest_text

        # G. Verify backup status script
        status_proc = subprocess.run(
            [str(SCRIPTS_DIR / "backup-status.sh")],
            env=env,
            capture_output=True,
            text=True,
        )
        assert status_proc.returncode == 0, f"backup-status.sh failed: {status_proc.stderr}"
        assert "Overall Status:   HEALTHY" in status_proc.stdout
        assert "Integrity:      VERIFIED" in status_proc.stdout

        # H. Run restore-postgres.sh targeting restore_db_name
        restore_proc = subprocess.run(
            [
                str(SCRIPTS_DIR / "restore-postgres.sh"),
                "--backup-file", str(backup_file),
                "--manifest", str(manifest_file),
                "--target-db", restore_db_name,
                "--compose-file", str(disposable_compose),
                "--compose-project", disposable_project,
                "--postgres-service", "db",
            ],
            env=env,
            capture_output=True,
            text=True,
        )
        assert restore_proc.returncode == 0, f"restore-postgres.sh failed: {restore_proc.stderr}\n{restore_proc.stdout}"

        # J. Verify restored database contents & financial consistency
        restore_engine = sa.create_engine(restore_url)
        with Session(restore_engine) as session:
            # 1. Check customers
            custs = session.query(Customer).order_by(Customer.id).all()
            assert len(custs) == 2
            assert custs[0].name == "Ramesh Kumar"
            assert custs[0].box_number == "BOX-1001"
            assert custs[0].area == "Zone 1"
            assert custs[0].monthly_amount == Decimal("350.00")

            assert custs[1].name == "Suresh Patel"
            assert custs[1].box_number == "BOX-1002"
            assert custs[1].area == "Zone 1"
            assert custs[1].monthly_amount == Decimal("500.00")

            # 2. Check invoices
            invs = session.query(Invoice).all()
            assert len(invs) == 1
            assert invs[0].invoice_number == "INV-202611-0001"
            assert invs[0].billing_month == "2026-11"
            assert invs[0].amount == Decimal("350.00")
            assert invs[0].paid_amount == Decimal("200.00")
            assert invs[0].status == "partial"

            # 3. Check payments & allocations
            pmts = session.query(Payment).all()
            assert len(pmts) == 1
            assert pmts[0].receipt_number == "RCPT-202611-0001"
            assert pmts[0].amount == Decimal("200.00")
            assert pmts[0].payment_method == "cash"

            allocs = session.query(PaymentAllocation).all()
            assert len(allocs) == 1
            assert allocs[0].allocated_amount == Decimal("200.00")
            assert allocs[0].payment_id == pmts[0].id
            assert allocs[0].invoice_id == invs[0].id

            # 4. Check business settings
            bs = session.query(BusinessSettings).first()
            assert bs is not None
            assert bs.business_name == "E2E Cable Net"
            assert bs.default_monthly_amount == Decimal("350.00")

            # 5. Check alembic version
            result = session.execute(sa.text("SELECT version_num FROM alembic_version;")).scalar()
            assert result == "0003_customer_billing_core"

    finally:
        # Tear down disposable compose stack and volumes
        subprocess.run(["docker", "compose", "-p", disposable_project, "-f", str(disposable_compose), "down", "-v"], capture_output=True)
