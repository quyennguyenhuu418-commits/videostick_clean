"""Config loader cho VideoStick."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml


DEFAULT_CONFIG_PATH = "config.yaml"


def load_config(config_path: str | os.PathLike[str] = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    """Doc file config.yaml va tra ve dict.

    Args:
        config_path: Duong dan tuyet doi hoac tuong doi den file config.

    Returns:
        Dict chua toan bo config.

    Raises:
        FileNotFoundError: Neu file khong ton tai.
        yaml.YAMLError: Neu file loi cu phap YAML.
    """
    cfg_path = Path(config_path)
    if not cfg_path.is_file():
        raise FileNotFoundError(f"Khong tim thay file config: {cfg_path.resolve()}")

    with cfg_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    # Resolve duong dan tuong doi so voi thu muc chua config.yaml
    root = cfg_path.resolve().parent
    cfg = _resolve_paths(cfg, root)

    return cfg


def _resolve_paths(node: Any, root: Path) -> Any:
    """De quy chuyen doi cac string duong dan thanh Path tuy y.

    Thuc te khong can chuyen doi sang Path vi cac module khac tu xu ly,
    nhung ta co the chuan hoa de dam bao tuong doi deu tinh tu root.
    """
    # Hien tai giu nguyen string de khong pha api; cac module se tu resolve.
    return node
