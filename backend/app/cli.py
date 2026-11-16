import argparse
import getpass
import sys
from sqlalchemy import func
from .config import settings
from .database import SessionLocal
from .models import AdminUser
from .security import hash_password, validate_admin_password


def reset_admin_password(
    email: str | None = None,
    db=None,
) -> int:
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        target_email = (email or settings.admin_email).strip().lower()
        admin = db.query(AdminUser).filter(func.lower(AdminUser.email) == target_email).first()
        if not admin:
            print(f"Error: Admin user with email '{target_email}' does not exist.", file=sys.stderr)
            return 1

        new_password = getpass.getpass("Enter new admin password: ")
        confirm_password = getpass.getpass("Confirm new admin password: ")

        if new_password != confirm_password:
            print("Error: Passwords do not match.", file=sys.stderr)
            return 1

        try:
            validate_admin_password(new_password)
        except ValueError as val_err:
            print(f"Error: Password policy violation: {val_err}", file=sys.stderr)
            return 1

        admin.password_hash = hash_password(new_password)
        admin.is_active = True
        db.commit()
        print(f"Success: Password for admin '{target_email}' has been successfully reset.")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"Error: Failed to reset admin password: {exc}", file=sys.stderr)
        return 1
    finally:
        if close_db:
            db.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description="Cable Data Manager Administration CLI",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    reset_parser = subparsers.add_parser(
        "reset-admin-password",
        help="Reset the password for an existing administrator account.",
    )
    reset_parser.add_argument(
        "--email",
        type=str,
        default=None,
        help="Email address of the administrator (defaults to ADMIN_EMAIL in settings).",
    )

    args = parser.parse_args(argv)

    if args.subcommand == "reset-admin-password":
        return reset_admin_password(email=args.email)

    return 0


if __name__ == "__main__":
    sys.exit(main())
