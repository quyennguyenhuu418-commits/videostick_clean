"""Scene segmenter: parse script.txt thanh danh sach Scene.

File script.txt co format:
    [img_01.jpg] Noi dung kich ban cho anh 1.
    Co the nhieu dong se duoc noi thanh mot doan.
    [img_02.jpg] Noi dung cho anh 2.

Chap nhan ca dang:
    [img_01] Noi dung...    (khong can .jpg)
    img_01.jpg Noi dung...  (khong can ngoac vuong)
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .exceptions import InputError


@dataclass
class Scene:
    """Mot scene tuong ung voi mot anh + mot doan text."""

    index: int
    image_filename: str           # Ten file (vd: "img_01.jpg")
    image_path: Optional[Path]    # Path day du sau khi resolve
    text: str                     # Noi dung kich ban
    duration: float = 0.0         # Thoi luong (giay), se tinh o buoc sau
    audio_path: Optional[Path] = None  # File WAV/TTS sau khi sinh
    audio_duration: float = 0.0   # Do dai audio TTS that (giay), cap nhat sau TTS
    ken_burns_direction: str = "zoom_in"
    start_time: float = 0.0       # Thoi diem bat dau trong video tong
    end_time: float = 0.0         # Thoi diem ket thuc

    def __post_init__(self) -> None:
        if self.image_path is not None:
            self.image_path = Path(self.image_path)


_HEADER_PATTERN_BRACKET = re.compile(r"^\s*\[\s*([^\]]+?)\s*\]\s*(.*)$")
_HEADER_PATTERN_PLAIN = re.compile(r"^\s*([\w\-./\\]+\.(?:jpg|jpeg|png|webp|bmp))\s+(.*)$", re.IGNORECASE)
_BLANK_LINE = re.compile(r"^\s*$")


def parse_script(script_path: str | os.PathLike[str]) -> List[Scene]:
    """Parse file script.txt va tra ve danh sach Scene.

    Args:
        script_path: Duong den file script.txt.

    Returns:
        Danh sach Scene theo thu tu xuat hien.

    Raises:
        InputError: Neu file khong ton tai hoac khong co scene nao hop le.
    """
    p = Path(script_path)
    if not p.is_file():
        raise InputError(f"Khong tim thay file kich ban: {p.resolve()}")

    raw = p.read_text(encoding="utf-8")
    scenes = _parse_text(raw)

    if not scenes:
        raise InputError(
            f"File kich ban {p} khong co scene nao. "
            "Kiem tra dinh dang [ten_anh.jpg] Noi dung..."
        )

    return scenes


def _parse_text(text: str) -> List[Scene]:
    """Noi dung parse chinh."""
    lines = text.splitlines()
    scenes: List[Scene] = []
    current_filename: Optional[str] = None
    current_text_lines: List[str] = []

    def _flush() -> None:
        nonlocal current_filename, current_text_lines
        if current_filename is None:
            current_text_lines = []
            return
        merged = " ".join(line.strip() for line in current_text_lines if line.strip())
        scenes.append(
            Scene(
                index=len(scenes) + 1,
                image_filename=current_filename,
                image_path=None,
                text=merged,
            )
        )
        current_filename = None
        current_text_lines = []

    for line in lines:
        # Bo qua comment va dong trong
        if line.lstrip().startswith("#"):
            continue

        # Thu khop dang [ten_anh] text
        m_bracket = _HEADER_PATTERN_BRACKET.match(line)
        if m_bracket:
            _flush()
            current_filename = m_bracket.group(1).strip()
            first_text = m_bracket.group(2).strip()
            current_text_lines = [first_text] if first_text else []
            continue

        # Thu khop dang ten_anh.jpg text
        m_plain = _HEADER_PATTERN_PLAIN.match(line)
        if m_plain:
            _flush()
            current_filename = m_plain.group(1).strip()
            first_text = m_plain.group(2).strip()
            current_text_lines = [first_text] if first_text else []
            continue

        # Neu khong phai header: append vao scene hien tai (neu co)
        if current_filename is not None and not _BLANK_LINE.match(line):
            current_text_lines.append(line)

    _flush()
    return scenes


def resolve_image_paths(scenes: List[Scene], images_dir: str | os.PathLike[str]) -> List[Scene]:
    """Gan duong dan tuyet doi cho tung scene dua tren images_dir.

    Co gang giai quyet ca truong hop nguoi dung chi ghi "img_01" (khong co extension).

    Args:
        scenes: Danh sach Scene tu parse_script.
        images_dir: Thu muc chua anh.

    Returns:
        Danh sach Scene da co image_path (Path tuy doi).

    Raises:
        InputError: Neu khong tim thay file anh cua bat ky scene nao.
    """
    img_dir = Path(images_dir)
    if not img_dir.is_dir():
        raise InputError(f"Thu muc anh khong ton tai: {img_dir.resolve()}")

    # Map ten file (lowercase) -> Path that ton tai
    available = {p.name.lower(): p for p in img_dir.iterdir() if p.is_file()}

    missing: List[str] = []
    for sc in scenes:
        target = sc.image_filename
        # Thu nguyen ten
        if target.lower() in available:
            sc.image_path = available[target.lower()]
            continue

        # Thu them extension
        stem = Path(target).stem
        matched: Optional[Path] = None
        for ext in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
            cand = img_dir / (stem + ext)
            if cand.exists():
                matched = cand
                break
        if matched is None:
            missing.append(sc.image_filename)
        else:
            sc.image_path = matched

    if missing:
        raise InputError(
            f"Khong tim thay {len(missing)} file anh trong {img_dir}: {missing[:5]}"
            + ("..." if len(missing) > 5 else "")
        )

    return scenes
