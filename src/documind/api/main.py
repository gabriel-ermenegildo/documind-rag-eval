"""FastAPI application factory."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from documind import __version__
from documind.api.routes import health
from documind.config import get_settings
from documind.db.session import get_engine

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    # Close pooled database connections on shutdown.
    get_engine().dispose()


def create_app() -> FastAPI:
    logging.basicConfig(level=get_settings().log_level, format=LOG_FORMAT)

    app = FastAPI(title="DocuMind", version=__version__, lifespan=lifespan)
    app.include_router(health.router)
    return app


app = create_app()
