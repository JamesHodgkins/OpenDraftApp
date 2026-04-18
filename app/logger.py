"""Application-wide logging configuration for OpenDraft."""
from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path


def configure_logging(log_dir: Path | None = None, level: int = logging.DEBUG) -> None:
    """Set up root logger with a console handler and a rotating file handler.

    Call once at application startup (before creating MainWindow).
    """
    root = logging.getLogger()
    if root.handlers:
        return  # already configured

    root.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler — WARNING and above so the terminal stays readable.
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    # File handler — full DEBUG log written to <log_dir>/opendraft.log.
    if log_dir is None:
        log_dir = Path.home() / ".opendraft" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    fh = logging.handlers.RotatingFileHandler(
        log_dir / "opendraft.log",
        maxBytes=2 * 1024 * 1024,  # 2 MB
        backupCount=3,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    root.addHandler(fh)
