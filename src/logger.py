"""Thiet lap logger cho toan pipeline."""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional


def setup_logging(config: Optional[Dict[str, Any]] = None) -> logging.Logger:
    """Tao va cau hinh logger goc.

    Args:
        config: Dict logging tu config.yaml. Neu None, su dung mac dinh INFO.

    Returns:
        logging.Logger (root).
    """
    log_cfg = (config or {}).get("logging", {})
    level_str = log_cfg.get("level", "INFO").upper()
    level = getattr(logging, level_str, logging.INFO)

    log_file = log_cfg.get("file", "logs/pipeline.log")
    console_enabled = log_cfg.get("console", True)

    # Dam bao thu muc logs ton tai
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level)

    # Xoa cac handler cu neu co (tranh duplicate khi goi nhieu lan)
    for h in list(root.handlers):
        root.removeHandler(h)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler
    file_handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # Console handler
    if console_enabled:
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(level)
        console.setFormatter(formatter)
        root.addHandler(console)

    return root


def get_logger(name: str) -> logging.Logger:
    """Tao logger con voi ten tuy chinh."""
    return logging.getLogger(name)
