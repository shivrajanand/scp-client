"""
Application logging setup.

Per spec section 33, logs must be useful for troubleshooting without ever
exposing secrets. This module installs a redacting filter as defense in
depth, in addition to callers simply never logging password values.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

_REDACT_PATTERNS = [
    re.compile(r"(password\s*[:=]\s*)(\S+)", re.IGNORECASE),
    re.compile(r"(passwd\s*[:=]\s*)(\S+)", re.IGNORECASE),
    re.compile(r"(pwd\s*[:=]\s*)(\S+)", re.IGNORECASE),
]


class RedactingFilter(logging.Filter):
    """Scrubs anything that looks like `password: ...` from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            return True

        redacted = message
        for pattern in _REDACT_PATTERNS:
            redacted = pattern.sub(r"\1********", redacted)

        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


def setup_logging(log_dir: Path = None, level: int = logging.INFO) -> logging.Logger:
    """Configure root application logging with console + optional file handler."""
    logger = logging.getLogger("scp_client")
    logger.setLevel(level)

    if logger.handlers:
        # Already configured (e.g. re-entrant call during tests).
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    redactor = RedactingFilter()

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(redactor)
    logger.addHandler(console_handler)

    if log_dir is not None:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_dir / "scp_client.log", encoding="utf-8")
            file_handler.setFormatter(formatter)
            file_handler.addFilter(redactor)
            logger.addHandler(file_handler)
        except OSError:
            # Non-fatal: fall back to console-only logging.
            pass

    return logger
