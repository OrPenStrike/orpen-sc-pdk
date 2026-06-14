"""Package logger."""

from __future__ import annotations

import logging

LOGGER_NAME = "orpen_sc_pdk"

logger = logging.getLogger(LOGGER_NAME)
logger.addHandler(logging.NullHandler())


def configure_logger(level: int | str = logging.INFO) -> logging.Logger:
    """Configure and return the package logger for command-line helpers."""

    logging.basicConfig(level=level, format="%(levelname)s:%(name)s:%(message)s")
    logger.setLevel(level)
    return logger
