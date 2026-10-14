"""FastAPI dependencies shared by the routes."""

from collections.abc import Iterator

from sqlalchemy.orm import Session

from documind.db.session import get_session_factory


def get_session() -> Iterator[Session]:
    """Yield a database session and close it when the request ends."""
    with get_session_factory()() as session:
        yield session
