import os
import tempfile
import sqlalchemy as sa
from alembic import command
from alembic.config import Config


def test_alembic_upgrade_and_downgrade_disposable():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "disposable_migration.db")
        db_url = f"sqlite:///{db_path}"

        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        alembic_ini = os.path.join(backend_dir, "alembic.ini")

        alembic_cfg = Config(alembic_ini)
        alembic_cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)

        old_url = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = db_url

        try:
            # 1. Upgrade to head on clean disposable DB
            command.upgrade(alembic_cfg, "head")

            engine = sa.create_engine(db_url)
            inspector = sa.inspect(engine)
            tables = inspector.get_table_names()
            assert "admin_users" in tables
            assert "business_settings" in tables
            assert "alembic_version" in tables

            # Verify admin_users columns
            admin_cols = {col["name"] for col in inspector.get_columns("admin_users")}
            assert {"id", "email", "password_hash", "is_active", "created_at"}.issubset(admin_cols)

            # Verify business_settings columns
            bs_cols = {col["name"] for col in inspector.get_columns("business_settings")}
            assert {
                "id", "business_name", "contact_number", "email", "address",
                "service_areas", "currency_code", "timezone",
                "default_monthly_amount", "billing_day", "grace_period_days",
                "late_payment_policy", "created_at", "updated_at"
            }.issubset(bs_cols)

            # 2. Downgrade to 0001_initial_admin_users
            command.downgrade(alembic_cfg, "0001_initial_admin_users")
            inspector = sa.inspect(engine)
            tables_mid = inspector.get_table_names()
            assert "business_settings" not in tables_mid
            assert "admin_users" in tables_mid

            # 3. Downgrade to base
            command.downgrade(alembic_cfg, "base")
            inspector = sa.inspect(engine)
            tables_after = inspector.get_table_names()
            assert "admin_users" not in tables_after

            engine.dispose()
        finally:
            if old_url:
                os.environ["DATABASE_URL"] = old_url
            else:
                os.environ.pop("DATABASE_URL", None)
