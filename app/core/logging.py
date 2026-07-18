"""Structured logging configuration for the application."""

import logging
import sys

from app.config import get_settings

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def configure_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    root.addHandler(handler)

    # Quiet down noisy third-party loggers.
    for noisy_logger in ("httpx", "sentence_transformers", "chromadb", "urllib3"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
