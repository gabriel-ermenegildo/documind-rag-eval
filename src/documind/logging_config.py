"""Logging setup shared by the API and the migration runner."""

import logging

from documind.config import get_settings

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging() -> None:
    """Configure the root logger. Does nothing if it already has handlers (e.g. under pytest)."""
    logging.basicConfig(level=get_settings().log_level, format=LOG_FORMAT)
