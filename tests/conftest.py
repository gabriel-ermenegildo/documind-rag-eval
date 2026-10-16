from collections.abc import Callable, Iterator, Sequence
from pathlib import Path

import pymupdf
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


@pytest.fixture
def make_pdf() -> Callable[..., bytes]:
    """Build a small synthetic PDF in memory: one page per string, "" for a blank page.

    Tests never use real PDFs, so the repository carries no copyrighted documents.
    """

    def build(pages: Sequence[str], title: str | None = None) -> bytes:
        with pymupdf.open() as pdf:
            for text in pages:
                page = pdf.new_page()
                if text:
                    page.insert_text((72, 72), text)
            if title is not None:
                pdf.set_metadata({"title": title})
            return pdf.tobytes()

    return build


@pytest.fixture
def make_scanned_pdf() -> Callable[[], bytes]:
    """Build a PDF whose only page is an image, like a scan: there is no text layer."""

    def build() -> bytes:
        with pymupdf.open() as pdf:
            page = pdf.new_page()
            pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 40), False)
            pixmap.clear_with(200)
            page.insert_image(pymupdf.Rect(72, 72, 272, 272), pixmap=pixmap)
            return pdf.tobytes()

    return build


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
