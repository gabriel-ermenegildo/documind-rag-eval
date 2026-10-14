"""Application settings, loaded from environment variables and the .env file."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    """Every configurable value of the application lives here.

    Precedence, highest first: environment variables, the .env file, the defaults below.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Default matches the Postgres published by docker-compose.yml on host port 5433.
    database_url: str = "postgresql+psycopg://documind:documind@localhost:5433/documind"
    log_level: LogLevel = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings, read once and then cached."""
    return Settings()
