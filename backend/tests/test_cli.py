import pytest
from app.cli import main, reset_admin_password
from app.models import AdminUser
from app.security import hash_password, verify_password


def test_cli_reset_admin_password_interactive_success(test_db, capsys, monkeypatch):
    email = "cli-admin@example.com"
    old_password = "oldPassword123!"
    admin = AdminUser(
        email=email,
        password_hash=hash_password(old_password),
        is_active=True,
    )
    test_db.add(admin)
    test_db.commit()

    new_password = "brandNewSecurePassword456!"
    # Mock getpass to supply the password and confirmation interactively
    prompts = [new_password, new_password]
    monkeypatch.setattr("getpass.getpass", lambda prompt="": prompts.pop(0))

    exit_code = reset_admin_password(email=email, db=test_db)
    assert exit_code == 0

    # Verify the password hash in the database was updated and matches new_password
    test_db.refresh(admin)
    assert verify_password(new_password, admin.password_hash)
    assert not verify_password(old_password, admin.password_hash)

    captured = capsys.readouterr()
    assert "Success: Password for admin 'cli-admin@example.com' has been successfully reset." in captured.out
    assert new_password not in captured.out
    assert admin.password_hash not in captured.out


def test_cli_reset_nonexistent_admin_fails(test_db, capsys):
    initial_count = test_db.query(AdminUser).count()
    exit_code = reset_admin_password(email="ghost@example.com", db=test_db)
    assert exit_code == 1
    # Verify no new admin was created
    assert test_db.query(AdminUser).count() == initial_count

    captured = capsys.readouterr()
    assert "Error: Admin user with email 'ghost@example.com' does not exist." in captured.err


def test_cli_reset_password_too_short(test_db, capsys, monkeypatch):
    email = "shortpass-admin@example.com"
    admin = AdminUser(
        email=email,
        password_hash=hash_password("validOldPassword123!"),
        is_active=True,
    )
    test_db.add(admin)
    test_db.commit()

    # Password has fewer than 12 characters
    prompts = ["ShortPass1!", "ShortPass1!"]
    monkeypatch.setattr("getpass.getpass", lambda prompt="": prompts.pop(0))

    exit_code = reset_admin_password(email=email, db=test_db)
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "Password policy violation: Password must be at least 12 characters long" in captured.err


def test_cli_reset_password_weak_or_trivial(test_db, capsys, monkeypatch):
    email = "weakpass-admin@example.com"
    admin = AdminUser(
        email=email,
        password_hash=hash_password("validOldPassword123!"),
        is_active=True,
    )
    test_db.add(admin)
    test_db.commit()

    # Password is 12 chars but repeating single character
    prompts = ["aaaaaaaaaaaa", "aaaaaaaaaaaa"]
    monkeypatch.setattr("getpass.getpass", lambda prompt="": prompts.pop(0))

    exit_code = reset_admin_password(email=email, db=test_db)
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "Password policy violation" in captured.err


def test_cli_reset_password_mismatch(test_db, capsys, monkeypatch):
    email = "mismatch-admin@example.com"
    admin = AdminUser(
        email=email,
        password_hash=hash_password("validOldPassword123!"),
        is_active=True,
    )
    test_db.add(admin)
    test_db.commit()

    prompts = ["ValidNewPassword123!", "MismatchingPassword123!"]
    monkeypatch.setattr("getpass.getpass", lambda prompt="": prompts.pop(0))

    exit_code = reset_admin_password(email=email, db=test_db)
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "Passwords do not match" in captured.err


def test_cli_rejects_plaintext_password_cli_argument(capsys):
    # The CLI parser must refuse --password to prevent credential leakage in process lists
    with pytest.raises(SystemExit) as exc_info:
        main(["reset-admin-password", "--email", "admin@example.com", "--password", "insecurePlaintext"])
    assert exc_info.value.code == 2

    captured = capsys.readouterr()
    assert "unrecognized arguments: --password" in captured.err


def test_cli_transaction_rollback_on_failure(test_db, capsys, monkeypatch):
    email = "rollback-admin@example.com"
    old_password = "initialValidPassword123!"
    admin = AdminUser(
        email=email,
        password_hash=hash_password(old_password),
        is_active=True,
    )
    test_db.add(admin)
    test_db.commit()

    new_password = "attemptedValidSecretPass999!"
    prompts = [new_password, new_password]
    monkeypatch.setattr("getpass.getpass", lambda prompt="": prompts.pop(0))

    # Force commit to fail
    def mock_commit():
        raise RuntimeError("Simulated database disk full error")

    monkeypatch.setattr(test_db, "commit", mock_commit)

    exit_code = reset_admin_password(email=email, db=test_db)
    assert exit_code == 1

    # Verify rollback kept the old password
    test_db.refresh(admin)
    assert verify_password(old_password, admin.password_hash)

    captured = capsys.readouterr()
    assert "Failed to reset admin password: Simulated database disk full error" in captured.err
