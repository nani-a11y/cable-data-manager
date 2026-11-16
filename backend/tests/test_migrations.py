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
            assert "alembic_version" in tables

            columns = {col["name"] for col in inspector.get_columns("admin_users")}
            assert {"id", "email", "password_hash", "is_active", "created_at"}.issubset(columns)

            # 2. Downgrade to base
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
