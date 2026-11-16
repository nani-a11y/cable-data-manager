import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Interpret the config file for Python logging.
if context.config.config_file_name is not None:
    fileConfig(context.config.config_file_name)

from app.database import Base
from app.models import (  # noqa: F401 - register models in Base.metadata
    AdminUser,
    BusinessSettings,
    Customer,
    Invoice,
    Payment,
    PaymentAllocation,
)
from app.config import settings

target_metadata = Base.metadata

def get_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        try:
            url = settings.database_url
        except Exception:
            url = "postgresql+psycopg://cable_admin:password@localhost:5432/cable_manager"
    return url

def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    configuration = context.config.get_section(context.config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
