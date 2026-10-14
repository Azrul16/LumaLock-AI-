"""Rotating technical logs; image data and prompt content are never logged here."""

import logging
from logging.handlers import RotatingFileHandler

from lumalock.core.config import data_dir


def configure_logging() -> None:
    directory = data_dir() / "logs"
    directory.mkdir(exist_ok=True)
    handler = RotatingFileHandler(
        directory / "lumalock.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logging.getLogger("lumalock").setLevel(logging.INFO)
    logging.getLogger("lumalock").addHandler(handler)
