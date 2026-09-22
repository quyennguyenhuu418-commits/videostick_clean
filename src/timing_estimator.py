"""Tinh toan thoi luong tung scene dua tren do dai text.

Chien luoc:
    - Uoc luong so tu (words) va so am tiet (syllables).
    - Su dung toc do noi (WPM) trong config de tinh duration ban dau.
    - Clamp duration trong khoang [min_scene_duration, max_scene_duration].
    - Sau khi TTS sinh file audio that, cap nhat lai duration theo do dai audio
      (xu ly o buoc khac).
"""

from __future__ import annotations

import re
from typing import Iterable, List

from .scene_segmenter import Scene


# Dem "tu" cho ca tieng Anh (split theo whitespace) va tieng Viet (theo khoang trang + ky tu dac biet).
def count_words(text: str) -> int:
    """Dem so tu trong text (co xu ly tieng Viet)."""
    if not text:
        return 0
    # Tach theo whitespace va dau cau
    tokens = re.split(r"[\s,.!?;:()\"'-]+", text.strip())
    return sum(1 for t in tokens if t)


def count_syllables_vi(text: str) -> int:
    """Uoc luong so am tiet tieng Viet (moi tu tieng Viet ~ 1-3 am tiet).

    Su dung heuristic: dem cac nguyen am lien tiep trong moi tu.
    """
    if not text:
        return 0

    vowels = "aeiouyAEIOUY"
    # Them cac nguyen am co dau tieng Viet
    vi_vowels = "ăâêôơưĂÂÊÔƠƯáàảãạắằẳẵặấầẩẫậéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ"
    all_vowels = vowels + vi_vowels

    words = re.findall(r"\w+", text, flags=re.UNICODE)
    total = 0
    for w in words:
        # Dem nhom nguyen am lien tiep
        groups = re.findall(f"[{all_vowels}]+", w)
        total += max(1, len(groups))
    return total


def estimate_text_duration(text: str, words_per_minute: int, language: str = "vi") -> float:
    """Uoc luong thoi gian doc mot doan text.

    Args:
        text: Noi dung kich ban.
        words_per_minute: Toc do noi (default 140).
        language: "vi" | "en". Tieng Viet tinh theo am tiet, tieng Anh theo tu.

    Returns:
        Thoi gian uoc luong (giay).
    """
    if not text or words_per_minute <= 0:
        return 0.0

    if language == "vi":
        syllables = count_syllables_vi(text)
        # Tieng Viet: trung binh ~ 3.5 am tiet / giay cho giong cham
        # => 210 syllables/min
        return (syllables / max(words_per_minute, 1)) * 60.0
    else:
        words = count_words(text)
        return (words / max(words_per_minute, 1)) * 60.0


def estimate_scene_duration(scene: Scene, words_per_minute: int, language: str) -> float:
    """Uoc luong duration cho 1 scene (giay)."""
    return estimate_text_duration(scene.text, words_per_minute, language)


def clamp_duration(duration: float, min_d: float, max_d: float) -> float:
    """Clamp duration trong khoang [min_d, max_d]."""
    return max(min_d, min(duration, max_d))


def compute_durations(
    scenes: List[Scene],
    timing_cfg: dict,
    language: str = "vi",
) -> List[Scene]:
    """Tinh duration cho tat ca scene va gan lai start/end.

    Args:
        scenes: Danh sach Scene (da co text).
        timing_cfg: Dict timing tu config.
        language: "vi" | "en".

    Returns:
        Danh sach Scene da duoc set duration, start_time, end_time.
    """
    wpm = int(timing_cfg.get("words_per_minute", 140))
    min_d = float(timing_cfg.get("min_scene_duration", 4.0))
    max_d = float(timing_cfg.get("max_scene_duration", 15.0))
    silence = float(timing_cfg.get("silence_padding", 0.5))

    cursor = 0.0
    for sc in scenes:
        raw = estimate_scene_duration(sc, wpm, language)
        sc.duration = clamp_duration(raw, min_d, max_d)
        sc.start_time = cursor
        sc.end_time = cursor + sc.duration
        cursor = sc.end_time + silence

    return scenes


def refine_with_audio_durations(scenes: List[Scene], silence_padding: float = 0.5) -> List[Scene]:
    """Sau khi TTS sinh audio that, cap nhat duration theo do dai file audio.

    Args:
        scenes: Danh sach Scene co audio_path tro den file WAV.
        silence_padding: Khoang lang chen giua cac scene.

    Returns:
        Danh sach Scene da duoc cap nhat.
    """
    cursor = 0.0
    for sc in scenes:
        if sc.audio_path is not None and sc.audio_path.exists():
            # Su dung do dai audio thuc (giay). Module ben ngoai se set gia tri nay
            # thong qua audio_duration neu can.
            audio_dur = getattr(sc, "audio_duration", None)
            if isinstance(audio_dur, (int, float)) and audio_dur > 0:
                sc.duration = float(audio_dur)
        sc.start_time = cursor
        sc.end_time = cursor + sc.duration
        cursor = sc.end_time + silence_padding

    return scenes


def total_duration(scenes: Iterable[Scene]) -> float:
    """Tong thoi luong video (giay)."""
    last = 0.0
    for sc in scenes:
        last = max(last, sc.end_time)
    return last
