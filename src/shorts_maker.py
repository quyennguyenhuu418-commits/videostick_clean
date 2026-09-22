"""Auto-generate YouTube Shorts (clip 9:16 <=60s) tu video dai.

Workflow:
    1. Doc SRT -> cum subtitle co (start, end, text)
    2. Nhom cac cum lien tiep thanh segment dai 15-60 giay (khong cat giua cum)
    3. Score moi segment theo do dai cum / cum co dau cau
    4. Reframe 16:9 -> 9:16 (scale + crop giua, blur fill cot trai/phai)
    5. Burn subtitle (re-time theo segment) va xuat MP4

Chay doc lap voi pipeline chinh: khong can TTS, chi dung video + SRT da co.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

log = logging.getLogger("shorts_maker")


# =========================================================================
# Phan tich SRT
# =========================================================================

_SRT_TS_PATTERN = re.compile(
    r"(\d{1,3}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*(\d{1,3}):(\d{2}):(\d{2})[,.](\d{1,3})"
)


def _ts_to_seconds(ts: str) -> float:
    """Chuyen chuoi timestamp SRT (HH:MM:SS,mmm) sang giay."""
    m = _SRT_TS_PATTERN.match(ts.strip())
    if not m:
        return 0.0
    h, mn, s, ms = (int(x) for x in m.groups()[:4])
    return h * 3600 + mn * 60 + s + ms / 1000.0


def _seconds_to_srt_ts(sec: float) -> str:
    """Chuyen giay thanh chuoi timestamp SRT (HH:MM:SS,mmm)."""
    if sec < 0:
        sec = 0.0
    millis = int(round((sec - int(sec)) * 1000))
    total = int(sec)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d},{millis:03d}"


@dataclass
class SubtitleCue:
    index: int           # STT trong file SRT goc
    start: float         # giay
    end: float           # giay
    text: str            # noi dung (co the nhieu dong)


def parse_srt(srt_path: Path) -> List[SubtitleCue]:
    """Doc file SRT tra ve list cac SubtitleCue."""
    cues: List[SubtitleCue] = []
    if not srt_path.exists():
        return cues

    raw = srt_path.read_text(encoding="utf-8", errors="ignore").strip()
    if not raw:
        return cues

    # SRT blocks ngan cach boi 2 newline; tuy nhien co the 1 newline neu file xau
    # Tach theo regex pattern: dong index -> dong thoi gian -> text -> blank
    blocks = re.split(r"\r?\n\r?\n", raw)
    for block in blocks:
        lines = [ln.rstrip() for ln in block.splitlines() if ln.strip()]
        if len(lines) < 2:
            continue
        idx_line = lines[0]
        ts_line = lines[1]
        if "-->" not in ts_line:
            continue
        try:
            idx = int(idx_line.strip())
        except ValueError:
            idx = len(cues) + 1
        ts_match = _SRT_TS_PATTERN.search(ts_line)
        if not ts_match:
            continue
        sh, sm, ss, sms = (int(x) for x in ts_match.groups()[:4])
        eh, em, es, ems = (int(x) for x in ts_match.groups()[4:])
        start = sh * 3600 + sm * 60 + ss + sms / 1000.0
        end = eh * 3600 + em * 60 + es + ems / 1000.0
        text = "\n".join(lines[2:])
        cues.append(SubtitleCue(index=idx, start=start, end=end, text=text))
    return cues


def write_srt(cues: List[SubtitleCue], output_path: Path) -> Path:
    """Ghi danh sach SubtitleCue ra file SRT, re-index tu 1."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    for i, cue in enumerate(cues, start=1):
        lines.append(str(i))
        lines.append(f"{_seconds_to_srt_ts(cue.start)} --> {_seconds_to_srt_ts(cue.end)}")
        lines.append(cue.text)
        lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


# =========================================================================
# Segment suggestion
# =========================================================================

@dataclass
class ShortSuggestion:
    start: float
    end: float
    duration: float
    text_preview: str
    score: float = 0.0
    cue_count: int = 0
    has_hook: bool = False      # 3 giay dau co cau dich danh (hook)
    cues: List[SubtitleCue] = field(default_factory=list)


_HOOK_PATTERNS = re.compile(
    r"\b(imagine|secret|never|nobody|you won't|you must|the truth|"
    r"here's why|nobody tells|don't|why|how|what if|stop|"
    r"incredible|shocking|amazing|discover|hidden)\b",
    re.IGNORECASE,
)


def _score_segment(cues: List[SubtitleCue], duration: float) -> float:
    """Tinh diem cho segment.

    Yeu to cong:
        - Do dai trong khoang 25-55 giay (sweet spot Shorts)
        - Cum co dau cham/cau cham (sentences hoan chinh)
        - Cum dau tien co hook word
        - Tu khoa hook xuat hien trong text

    Yeu to tru:
        - Segment qua ngan (< 15s) hoac qua dai (> 60s)
    """
    if not cues:
        return 0.0

    score = 0.0

    # Do dai ly tuong
    if 25 <= duration <= 55:
        score += 5.0
    elif 15 <= duration <= 60:
        score += 3.0
    elif 15 < duration < 25:
        score += 1.0
    else:
        return 0.0  # bo qua segment khong hop le

    # So cum - nhieu cum hon = nhieu noi dung hon
    score += min(len(cues), 8) * 0.4

    # Cum co dau cau hoan chinh (=, ., !, ?)
    sentence_ends = sum(1 for c in cues if re.search(r"[.!?][\"\']?$", c.text.strip()))
    score += sentence_ends * 0.8

    # Hook trong 3s dau
    if cues:
        first_text = cues[0].text
        if _HOOK_PATTERNS.search(first_text):
            score += 3.0

    # Tu khoa hook bat ky dau
    full_text = " ".join(c.text for c in cues)
    hook_hits = len(_HOOK_PATTERNS.findall(full_text))
    score += min(hook_hits, 5) * 0.3

    # Trung binh cum dai hon 4s (noi dung day du, khong bi cat giua)
    if cues:
        avg_dur = sum((c.end - c.start) for c in cues) / len(cues)
        if avg_dur >= 2.0:
            score += 1.5

    return round(score, 2)


def suggest_shorts(
    cues: List[SubtitleCue],
    min_dur: float = 15.0,
    max_dur: float = 60.0,
    overlap_sec: float = 1.0,
    prefer_gap: bool = True,
) -> List[ShortSuggestion]:
    """Goi y cac segment short tu danh sach SubtitleCue.

    Chien luoc:
        - Di chuyen mot "cua so" qua cac cum
        - Bat dau moi segment tai dau 1 cum (bo qua nhung cum qua ngan < 0.5s)
        - Ket thuc o cuoi cum gan nhat ma tong <= max_dur
        - Tang con tro start di `overlap_sec` giay sau khi dat max_dur
        - Mot cum co the thuoc nhieu segment overlap -> user tu chon

    Args:
        cues: Danh sach SubtitleCue.
        min_dur: Do dai toi thieu (giay).
        max_dur: Do dai toi da (giay).
        overlap_sec: Buoc nhay giua 2 segment de tranh stt nhay ngay.
        prefer_gap: Neu True, uu tien ket thuc o ranh gioi cum (gap > 0.3s).

    Returns:
        Danh sach ShortSuggestion sorted theo score giam dan.
    """
    if not cues:
        return []

    # Loai bo cum bi thu hep qua (< 0.5s)
    cues = [c for c in cues if (c.end - c.start) >= 0.4]
    if not cues:
        return []

    suggestions: List[ShortSuggestion] = []
    n = len(cues)
    i = 0

    while i < n:
        # Bat dau segment tai dau cum i
        seg_start = cues[i].start
        seg_cues: List[SubtitleCue] = []

        # Mo rong segment
        j = i
        end_limit = seg_start + max_dur
        last_good_end = None

        while j < n:
            cue = cues[j]
            cue_dur = cue.end - cue.start
            tentative_end = cue.end

            # Neu qua max_dur thi dung
            if tentative_end - seg_start > max_dur:
                break
            seg_cues.append(cue)
            j += 1

            # Track diem tot: neu cum nay co gap truoc no (> 0.3s) hoac cau hoan chinh
            gap_to_next = (cues[j].start - cue.end) if j < n else 0.5
            if (gap_to_next > 0.3 or prefer_gap is False):
                if tentative_end - seg_start >= min_dur:
                    last_good_end = tentative_end

            # Neu cum nay da dat min_dur va co dau cau hoan chinh -> co the ket thuc
            if tentative_end - seg_start >= min_dur:
                txt = cue.text.strip()
                if re.search(r"[.!?][\"\']?$", txt):
                    last_good_end = tentative_end

        # Neu khong cum nao duoc them (max_dur qua ngan), bo qua
        if not seg_cues:
            i += 1
            continue

        seg_end = seg_cues[-1].end
        seg_dur = seg_end - seg_start

        # Neu segment hop le (>= min_dur)
        if seg_dur >= min_dur:
            preview = seg_cues[0].text.strip()
            if len(preview) > 80:
                preview = preview[:77] + "..."
            text_preview = preview.replace("\n", " ")

            # Has hook?
            full_first = seg_cues[0].text
            has_hook = bool(_HOOK_PATTERNS.search(full_first))

            score = _score_segment(seg_cues, seg_dur)
            if score > 0:
                suggestions.append(ShortSuggestion(
                    start=round(seg_start, 3),
                    end=round(seg_end, 3),
                    duration=round(seg_dur, 3),
                    text_preview=text_preview,
                    score=score,
                    cue_count=len(seg_cues),
                    has_hook=has_hook,
                    cues=list(seg_cues),
                ))

        # Buoc nhay: neu segment vua them la qua max_dur -> nhay qua cum cu
        # Con lai nhay bang overlap_sec de trung lap nhe
        if seg_end - seg_start >= max_dur * 0.95:
            i = j
        else:
            # Nhay den cum co start > seg_start + overlap_sec
            target = seg_start + overlap_sec
            i += 1
            while i < n and cues[i].start < target:
                i += 1

    # Sort theo score giam dan
    suggestions.sort(key=lambda s: s.score, reverse=True)
    return suggestions


# =========================================================================
# FFMPEG: Reframe 9:16 + burn subtitle
# =========================================================================

def _escape_filter_path(p: Path) -> str:
    """Escape duong dan cho ffmpeg filter (Windows-safe)."""
    s = str(p.resolve()).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
    return s


def reframe_to_vertical(
    video_path: Path,
    output_path: Path,
    start: float,
    end: float,
    target_w: int = 1080,
    target_h: int = 1920,
    *,
    burn_subtitle_ass: Optional[Path] = None,
    burn_subtitle_text: Optional[List[Tuple[float, float, str]]] = None,
    crf: int = 23,
    preset: str = "medium",
) -> Path:
    """Cat 1 doan video va reframe tu 16:9 sang 9:16 (Shorts/TikTok).

    Background fill = blurred + scaled copy cua chinh video (chiếm phan tren/duoi),
    foreground = crop chinh giua (giu ty le 9:16).

    Args:
        video_path: File MP4 nguon (16:9 hoac 4:3).
        output_path: File MP4 dich (9:16).
        start: Thoi diem bat dau (giay).
        end: Thoi diem ket thuc (giay).
        target_w: Chieu rong output (1080).
        target_h: Chieu cao output (1920).
        burn_subtitle_ass: File ASS de burn (uu tien).
        burn_subtitle_text: List (start, end, text) de burn inline (fallback khi khong co ASS).
        crf: CRF cho encode.
        preset: FFmpeg preset encode.

    Returns:
        Path den file output.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration = end - start
    if duration <= 0.5:
        raise ValueError(f"Segment qua ngan: {duration:.2f}s")

    inp = _escape_filter_path(video_path)

    # 1. Split video thanh 2 stream: foreground (crop giua) + background (blur fill)
    # 2. Overlay foreground len background canh giua
    # 3. Neu co subtitle thi them subtitles filter
    # 4. Encode

    # Tinh toan crop + scale cho foreground 9:16
    # Gia dinh input 1920x1080 -> crop 1080x1080 (cat 2 ben) -> scale 1080x1920 (cat dinh/day)
    # Tong quat: crop width = min(input_h * 9/16, input_w) * 0.95 de an toan
    # Vi khong biet input dims, su dung expression ffmpeg de tu tinh

    # Chien luoc don gian: scale input theo chieu cao target, crop width theo 9:16 o giua
    # Day la pp "fit-by-height" pho bien cho short reframe

    # ffmpeg syntax: [0:v]scale=W:H, crop=W:H, format=yuv420p[v]
    # W = target_w, H = target_h
    # scale truoc, crop sau se giu duoc 9:16

    # Build filter
    parts = []
    # Trim video truoc, roi moi scale
    parts.append(
        f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS,"
        f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
        f"crop={target_w}:{target_h},setsar=1,format=yuv420p[vfg]"
    )
    # Background: blur + scale vua khop 9:16
    parts.append(
        f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS,"
        f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
        f"boxblur=luma_radius=20:luma_power=0.8,"
        f"crop={target_w}:{target_h},setsar=1,format=yuv420p[vbg]"
    )
    # Overlay foreground len background
    parts.append(f"[vbg][vfg]overlay=x='(W-w)/2':y='(H-h)/2'[vol]")

    last_v = "[vol]"

    if burn_subtitle_ass and burn_subtitle_ass.exists():
        ass_escaped = _escape_filter_path(burn_subtitle_ass)
        parts.append(f"{last_v}subtitles='{ass_escaped}'[vsub]")
        last_v = "[vsub]"

    parts.append(f"{last_v}copy[vout]")
    # Audio: atrim (dat start = 0) + asetpts
    parts.append(f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[aout]")

    filter_complex = ";".join(parts)

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", "[aout]",
        "-c:v", "libx264",
        "-preset", preset,
        "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        str(output_path),
    ]

    log.info("FFmpeg: cat %.2fs -> %.2fs (%s)", start, end, output_path.name)
    log.debug("CMD: %s", " ".join(cmd))

    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    if result.returncode != 0:
        log.error("FFmpeg failed (returncode=%d): %s", result.returncode, result.stderr[-500:])
        raise RuntimeError(
            f"FFmpeg cut failed: {result.stderr[-500:] if result.stderr else 'no stderr'}"
        )

    return output_path


def _escape_ass_text(text: str) -> str:
    """Escape ky tu dac biet cho ASS subtitle text."""
    return text.replace("\\", r"\\").replace("\n", r"\N").replace(",", r"\,")


def build_segment_ass(
    cues: List[SubtitleCue],
    output_path: Path,
    font: str = "Inter",
    font_size: int = 64,
    margin_v: int = 220,
    primary_color: str = "&H00FFFFFF",
    outline_color: str = "&H00000000",
    outline_thick: int = 4,
) -> Path:
    """Tao file .ASS cho 1 segment short (re-time tu 0).

    Args:
        cues: SubtitleCue goc (start, end tuy y).
        output_path: File .ASS output.
        font: Ten font.
        font_size: Font size (cho 1080x1920 nen ~ 60-80).
        margin_v: Khoang cach tu day man hinh.
        primary_color: Mau chu (ASS &H format).
        outline_color: Mau outline.
        outline_thick: Do day outline.

    Returns:
        Path den file .ASS.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    header = f"""[Script Info]
ScriptType: V4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{font_size},{primary_color},&H000000FF,{outline_color},&H80000000,-1,0,0,0,100,100,0,0,1,{outline_thick},2,2,80,80,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events: List[str] = []
    for cue in cues:
        start_t = _seconds_to_srt_ts(cue.start).replace(",", ".")
        end_t = _seconds_to_srt_ts(cue.end).replace(",", ".")
        text = _escape_ass_text(cue.text)
        events.append(f"Dialogue: 0,{start_t},{end_t},Default,,0,0,0,,{text}")

    output_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    return output_path


# =========================================================================
# High-level orchestration
# =========================================================================

@dataclass
class ShortRenderResult:
    output_path: Path
    suggestion: ShortSuggestion
    success: bool = True
    error: Optional[str] = None


def cut_shorts(
    video_path: Path,
    srt_path: Path,
    output_dir: Path,
    *,
    selections: Optional[List[Tuple[float, float]]] = None,
    auto_generate: bool = False,
    num_auto: int = 3,
    target_w: int = 1080,
    target_h: int = 1920,
    crf: int = 23,
    preset: str = "medium",
    burn_subtitle: bool = True,
    font: str = "Inter",
    font_size: int = 64,
) -> List[ShortRenderResult]:
    """Cat 1 hoac nhieu short tu video dai.

    Args:
        video_path: File MP4 16:9 goc.
        srt_path: File SRT tuong ung.
        output_dir: Thu muc output (moi short la 1 file).
        selections: List (start, end) cu the. Neu None + auto_generate=True -> auto.
        auto_generate: Neu True va selections=None, tu dong pick top N segment.
        num_auto: So segment auto-pick.
        target_w, target_h: Kich thuoc output (9:16).
        crf, preset: Encode params.
        burn_subtitle: Co burn subtitle khong.
        font, font_size: Font cho subtitle.

    Returns:
        List ShortRenderResult (co output_path, success, error).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    cues = parse_srt(srt_path)
    if not cues:
        return [ShortRenderResult(
            output_path=output_dir / "empty.mp4",
            suggestion=ShortSuggestion(0, 0, 0, "Khong co SRT"),
            success=False,
            error="SRT rong hoac khong ton tai",
        )]

    # Lay danh sach segment can cut
    if selections:
        # User chon selections
        targets: List[Tuple[float, float]] = selections
        explicit = True
    elif auto_generate:
        suggestions = suggest_shorts(cues)
        if not suggestions:
            return [ShortRenderResult(
                output_path=output_dir / "no_suggestions.mp4",
                suggestion=ShortSuggestion(0, 0, 0, "Khong tim duy segment"),
                success=False,
                error="Khong the goi y segment nao",
            )]
        # Lay top N segments, dam bao khong overlap qua nhieu
        # Su dung greedy: lay segment highest score, loai bo suggestions overlap > 50%
        targets_picked: List[Tuple[float, float]] = []
        picks: List[ShortSuggestion] = []
        for sug in suggestions:
            if len(picks) >= num_auto:
                break
            overlap = False
            for s, e in targets_picked:
                overlap_dur = min(sug.end, e) - max(sug.start, s)
                if overlap_dur > 0.5 * sug.duration:
                    overlap = True
                    break
            if not overlap:
                picks.append(sug)
                targets_picked.append((sug.start, sug.end))
        targets = targets_picked
        explicit = False
    else:
        return [ShortRenderResult(
            output_path=output_dir / "no_input.mp4",
            suggestion=ShortSuggestion(0, 0, 0, "No input"),
            success=False,
            error="Phai chon selections hoac auto_generate=True",
        )]

    results: List[ShortRenderResult] = []

    for idx, (start, end) in enumerate(targets, start=1):
        # Tao suggestion dummy cho result
        seg_cues = [c for c in cues if c.start >= start - 0.5 and c.end <= end + 0.5]
        if not seg_cues:
            seg_cues = [
                SubtitleCue(index=0, start=start, end=end, text="(khong co subtitle)")
            ]
        sug = ShortSuggestion(
            start=start, end=end, duration=end - start,
            text_preview=seg_cues[0].text.strip()[:80], score=0.0,
            cue_count=len(seg_cues), cues=seg_cues,
        )

        # Build subtitle ASS (re-time tu 0, khop start segment)
        ass_file = None
        if burn_subtitle and seg_cues:
            # Re-time cues de start cua segment = 0
            rebased = [
                SubtitleCue(
                    index=i + 1,
                    start=max(0.0, c.start - start),
                    end=max(0.1, c.end - start),
                    text=c.text,
                )
                for i, c in enumerate(seg_cues)
            ]
            ass_file = output_dir / f"short_{idx:02d}.ass"
            try:
                build_segment_ass(
                    rebased, ass_file,
                    font=font, font_size=font_size,
                )
            except Exception as e:
                log.warning("Build ASS that bai: %s", e)
                ass_file = None

        output_file = output_dir / f"short_{idx:02d}.mp4"
        # Neu file da ton tai -> them timestamp suffix de tranh ghi de
        if output_file.exists():
            ts = _dt.datetime.now().strftime("%H%M%S")
            output_file = output_dir / f"short_{idx:02d}_{ts}.mp4"
        try:
            reframe_to_vertical(
                video_path=video_path,
                output_path=output_file,
                start=start,
                end=end,
                target_w=target_w,
                target_h=target_h,
                burn_subtitle_ass=ass_file,
                crf=crf,
                preset=preset,
            )
            results.append(ShortRenderResult(
                output_path=output_file,
                suggestion=sug,
                success=True,
            ))
        except Exception as e:
            log.error("Cut short %d that bai: %s", idx, e)
            results.append(ShortRenderResult(
                output_path=output_file,
                suggestion=sug,
                success=False,
                error=str(e),
            ))
        finally:
            # Don dep ASS
            if ass_file and ass_file.exists():
                try:
                    ass_file.unlink()
                except OSError:
                    pass

    return results
