from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import URL, Engine, create_engine, make_url, text
from sqlalchemy.exc import OperationalError

from documind.config import get_settings

MAINTENANCE_DATABASE = "postgres"
ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def _ensure_database_exists(url: URL) -> None:
    """Create the test database if it is missing. CREATE DATABASE cannot run in a transaction."""
    admin_engine = create_engine(
        url.set(database=MAINTENANCE_DATABASE), isolation_level="AUTOCOMMIT"
    )
    try:
        with admin_engine.connect() as connection:
            exists = connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}
            )
            if not exists:
                # Identifiers cannot be bound as parameters; the name comes from our own settings.
                connection.execute(text(f'CREATE DATABASE "{url.database}"'))
    finally:
        admin_engine.dispose()


@pytest.fixture(scope="session")
def test_database_url() -> URL:
    """URL of the dedicated test database, created on the real Postgres container if needed."""
    settings = get_settings()
    url = make_url(settings.test_database_url)
    if url == make_url(settings.database_url):
        pytest.fail("TEST_DATABASE_URL must not point to the development database.")

    try:
        _ensure_database_exists(url)
    except OperationalError:
        pytest.fail(
            f"Postgres is not reachable at {url.render_as_string(hide_password=True)}. "
            "Start it with `make up`."
        )
    return url


@pytest.fixture(scope="session")
def alembic_config(test_database_url: URL) -> Config:
    """Alembic configuration that targets the test database instead of the development one."""
    config = Config(ALEMBIC_INI)
    config.attributes["database_url"] = test_database_url.render_as_string(hide_password=False)
    return config


@pytest.fixture(scope="session")
def db_engine(test_database_url: URL, alembic_config: Config) -> Iterator[Engine]:
    """Engine bound to the test database, with every migration applied."""
    command.upgrade(alembic_config, "head")
    engine = create_engine(test_database_url)
    yield engine
    engine.dispose()
