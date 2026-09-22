"""Sinh file .srt subtitle cho cac scene.

Thuat toan:
    - Moi scene co duration (giay) va text.
    - Chia text thanh cac cum (chunk) co ~ 8-12 tu/cum (moi dong subtitle).
    - Phan bo thoi gian deu cho cac cum theo ty le so tu.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

from .scene_segmenter import Scene


_WORDS_PER_LINE = 10  # so tu toi da tren 1 dong subtitle
_MAX_LINE_LENGTH = 42  # ky tu toi da 1 dong (truong hop subtitle tieng Viet)


def _split_text_into_lines(text: str, words_per_line: int = _WORDS_PER_LINE, max_len: int = _MAX_LINE_LENGTH) -> List[str]:
    """Chia text thanh nhieu dong subtitle ngan."""
    words = text.split()
    if not words:
        return []

    lines: List[str] = []
    current: List[str] = []
    cur_len = 0

    for w in words:
        # Neu them tu nay vuot qua max_len -> dong moi
        projected_len = cur_len + (1 if current else 0) + len(w)
        if current and (len(current) >= words_per_line or projected_len > max_len):
            lines.append(" ".join(current))
            current = [w]
            cur_len = len(w)
        else:
            current.append(w)
            cur_len = projected_len

    if current:
        lines.append(" ".join(current))

    return lines


def _format_timestamp(seconds: float) -> str:
    """Dinh dang thoi gian SRT: HH:MM:SS,mmm."""
    if seconds < 0:
        seconds = 0.0
    millis = int(round((seconds - int(seconds)) * 1000))
    total = int(seconds)
    hh = total // 3600
    mm = (total % 3600) // 60
    ss = total % 60
    return f"{hh:02d}:{mm:02d}:{ss:02d},{millis:03d}"


def _count_words(lines: List[str]) -> List[int]:
    return [len(line.split()) for line in lines]


def generate_subtitles(scenes: List[Scene], output_path: str | os.PathLike[str]) -> Path:
    """Sinh file .srt tu danh sach Scene.

    Args:
        scenes: Danh sach Scene co start_time, end_time, duration, text.
        output_path: Duong den file .srt can ghi.

    Returns:
        Path den file .srt da ghi.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    entries: List[str] = []
    sub_index = 1

    for sc in scenes:
        lines = _split_text_into_lines(sc.text)
        if not lines:
            continue

        durations = _count_words(lines)
        total_words = sum(durations)
        if total_words <= 0:
            continue

        cursor = sc.start_time
        scene_dur = max(sc.duration, 0.5)

        for line, w in zip(lines, durations):
            seg_dur = scene_dur * (w / total_words)
            start = cursor
            end = cursor + seg_dur

            entries.append(f"{sub_index}")
            entries.append(f"{_format_timestamp(start)} --> {_format_timestamp(end)}")
            entries.append(line)
            entries.append("")

            cursor = end
            sub_index += 1

    out.write_text("\n".join(entries), encoding="utf-8")
    return out


def generate_ass(scenes: List[Scene], output_path: str | os.PathLike[str], sub_cfg: dict) -> Path:
    """Sinh file .ASS (Advanced SubStation Alpha) cho ffmpeg subtitles filter.

    Format .ASS cho phep tuy chinh font, color, outline, position tot hon SRT.

    Args:
        scenes: Danh sach Scene.
        output_path: File .ASS output.
        sub_cfg: Dict subtitle tu config.

    Returns:
        Path den file .ASS.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    font = sub_cfg.get("font", "Arial")
    # Lay ten font tu path neu co
    if font and ("/" in font or "\\" in font):
        font = Path(font).stem

    font_size = int(sub_cfg.get("font_size", 48))
    primary = sub_cfg.get("font_color", "&H00FFFFFF")
    outline = sub_cfg.get("outline_color", "&H00000000")
    outline_thick = int(sub_cfg.get("outline_thickness", 2))
    position = sub_cfg.get("position", "bottom")
    margin_v = int(sub_cfg.get("margin_v", 60))

    align_map = {"bottom": 2, "center": 5, "top": 8}
    alignment = align_map.get(position, 2)

    header = f"""[Script Info]
ScriptType: V4.00+
PlayResX: 1920
PlayResY: 1080
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{font_size},{primary},&H000000FF,{outline},&H80000000,-1,0,0,0,100,100,0,0,1,{outline_thick},1,{alignment},40,40,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events: List[str] = []
    for sc in scenes:
        lines = _split_text_into_lines(sc.text)
        if not lines:
            continue
        durations = _count_words(lines)
        total_words = sum(durations) or 1
        cursor = sc.start_time
        scene_dur = max(sc.duration, 0.5)
        for line, w in zip(lines, durations):
            seg_dur = scene_dur * (w / total_words)
            start = cursor
            end = cursor + seg_dur
            text = line.replace("\n", "\\N")
            events.append(
                f"Dialogue: 0,{_format_timestamp(start)},{_format_timestamp(end)},Default,,0,0,0,,{text}"
            )
            cursor = end

    out.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    return out


def _format_timestamp(seconds: float) -> str:
    """ASS timestamp: H:MM:SS.cc (centiseconds)."""
    if seconds < 0:
        seconds = 0.0
    cs = int(round((seconds - int(seconds)) * 100))
    total = int(seconds)
    hh = total // 3600
    mm = (total % 3600) // 60
    ss = total % 60
    return f"{hh:d}:{mm:02d}:{ss:02d}.{cs:02d}"
