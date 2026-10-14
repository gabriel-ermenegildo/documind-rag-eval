"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from documind import __version__
from documind.api.routes import health
from documind.db.session import get_engine
from documind.logging_config import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    # Close pooled database connections on shutdown.
    get_engine().dispose()


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(title="DocuMind", version=__version__, lifespan=lifespan)
    app.include_router(health.router)
    return app


app = create_app()
