"""Alembic environment: runs migrations using the application's settings and models."""

from alembic import context
from sqlalchemy import create_engine

from documind.config import get_settings
from documind.db.models import Base
from documind.logging_config import configure_logging

config = context.config
configure_logging()

# What autogenerate and `alembic check` compare the database against.
target_metadata = Base.metadata


def get_database_url() -> str:
    # The test suite passes its own database; the command line uses the application settings.
    return config.attributes.get("database_url") or get_settings().database_url


def run_migrations_offline() -> None:
    """Emit the SQL to stdout instead of running it (`alembic upgrade head --sql`)."""
    context.configure(url=get_database_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Connect to the database and run the migrations inside one transaction."""
    engine = create_engine(get_database_url())
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
