from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from documind.api.deps import get_session
from documind.api.main import create_app

pytestmark = pytest.mark.integration

# Nothing listens on port 1, so connecting fails for real: no mock involved.
UNREACHABLE_DATABASE_URL = "postgresql+psycopg://documind:documind@127.0.0.1:1/documind"
# Keeps the failing test fast; the driver raises anything below 2 seconds to 2.
CONNECT_TIMEOUT_SECONDS = 2


def client_using(engine: Engine) -> TestClient:
    """Build the app with its database sessions bound to the given engine."""

    def session_from_engine() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = session_from_engine
    return TestClient(app)


def test_health_is_ok_when_the_database_answers(db_engine):
    response = client_using(db_engine).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok"}


def test_health_is_503_when_the_database_is_unreachable():
    unreachable_engine = create_engine(
        UNREACHABLE_DATABASE_URL, connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS}
    )

    response = client_using(unreachable_engine).get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "error", "db": "error"}
