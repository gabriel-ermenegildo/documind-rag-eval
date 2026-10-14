"""Database engine, session factory and connectivity check."""

import logging
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from documind.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_engine() -> Engine:
    """Return the process-wide engine. No connection is opened until first use."""
    settings = get_settings()
    return create_engine(
        settings.database_url,
        # Replace pooled connections that died (e.g. after a database restart).
        pool_pre_ping=True,
        connect_args={"connect_timeout": settings.database_connect_timeout_seconds},
    )


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    """Return the factory that creates sessions bound to the process-wide engine."""
    return sessionmaker(bind=get_engine())


def check_database(session: Session) -> bool:
    """Return True if the database answers a trivial query, False otherwise."""
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        # No traceback: the cause is in the message, and a polled endpoint would flood the log.
        logger.error("Database health check failed: %s", exc)
        return False
    return True
