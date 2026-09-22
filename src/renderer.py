"""Renderer chinh: ghep cac thanh phan thanh video MP4 hoan chinh.

Pipeline render:
    1. Tao "Ken Burns videos" cho tung scene (FFmpeg + zoompan, color grading, vignette).
    2. Ghep cac scene video thanh 1 video dai (concat).
    3. Mix giong doc + background music.
    4. Burn subtitle vao (neu cau hinh).
    5. Encode final MP4.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from .exceptions import RenderError
from .ken_burns import KenBurnsPlan, build_zoompan_filter, plan_ken_burns
from .scene_segmenter import Scene
from .subtitle_generator import generate_ass, generate_subtitles
from .tts_engine import AudioSegment


log = logging.getLogger(__name__)


def _ffmpeg_path(cfg: Dict[str, Any]) -> str:
    """Lay ffmpeg binary tu config hoac PATH."""
    custom = (cfg.get("ffmpeg") or {}).get("binary", "")
    if custom:
        return custom
    found = shutil.which("ffmpeg")
    if not found:
        raise RenderError(
            "Khong tim thay ffmpeg. Cai dat FFmpeg hoac set ffmpeg.binary trong config.yaml."
        )
    return found


def _run(cmd: List[str], log_path: Optional[Path] = None) -> None:
    """Chay subprocess va raise neu loi."""
    log.debug("Run: %s", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if log_path is not None:
            log_path.write_bytes(result.stderr or b"")
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or b"").decode(errors="ignore")
        raise RenderError(f"FFmpeg that bai: {stderr[-1000:]}\nCmd: {' '.join(cmd)}")
    except FileNotFoundError as e:
        raise RenderError(f"Khong the chay ffmpeg: {e}")


def _color_grading_filter(cfg: Dict[str, Any]) -> str:
    """Tra ve chuoi filter color grading (eq, colorbalance, vignette)."""
    grading = cfg.get("color_grading", {})
    if not grading.get("enabled", True):
        return ""

    contrast = float(grading.get("contrast", 1.0))
    saturation = float(grading.get("saturation", 1.0))
    brightness = float(grading.get("brightness", 0.0))
    gamma = float(grading.get("gamma", 1.0))
    warm = float(grading.get("warm_tone", 0.0))

    parts = []
    # eq filter
    eq_parts = []
    if abs(contrast - 1.0) > 0.001:
        eq_parts.append(f"contrast={contrast}")
    if abs(saturation - 1.0) > 0.001:
        eq_parts.append(f"saturation={saturation}")
    if abs(brightness) > 0.001:
        eq_parts.append(f"brightness={brightness}")
    if abs(gamma - 1.0) > 0.001:
        eq_parts.append(f"gamma={gamma}")
    if eq_parts:
        parts.append("eq=" + ":".join(eq_parts))

    # Warm tone (dung colorbalance)
    if warm > 0.001:
        # rs= red shadows, gs=green shadows, bs=blue shadows
        # Tang shadows red, giam blue de tao tone am
        parts.append(f"colorbalance=rs={warm}:bs={-warm}")

    # Vignette
    vcfg = grading.get("vignette", {})
    if vcfg.get("enabled", True):
        intensity = float(vcfg.get("intensity", 0.15))
        if intensity > 0:
            # Vignette: PI/4 + angle, x0/y0=vi tri, mode
            parts.append(f"vignette=angle=PI/4:mode=forward:x0=0.5:y0=0.5")

    return ",".join(parts)


def render_scene_clips(
    scenes: List[Scene],
    plans: List[KenBurnsPlan],
    cfg: Dict[str, Any],
    temp_dir: Path,
) -> List[Path]:
    """Render moi scene thanh 1 clip MP4 (Ken Burns + color grading).

    Args:
        scenes: Danh sach Scene co image_path.
        plans: Ke hoach Ken Burns.
        cfg: Config dict.
        temp_dir: Thu muc temp de ghi file trung gian.

    Returns:
        Danh sach Path den clip output cho moi scene.
    """
    temp_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg = _ffmpeg_path(cfg)

    color_filter = _color_grading_filter(cfg)
    fps = int(cfg.get("render", {}).get("fps", 24))
    width = int(cfg.get("render", {}).get("width", 1920))
    height = int(cfg.get("render", {}).get("height", 1080))

    zoom_filters = build_zoompan_filter(plans, cfg.get("ken_burns", {}))
    # zoom_filters co the rong - khi do khong dung zoompan
    use_zoompan = any(zoom_filters)

    clips: List[Path] = []
    for sc, plan, zoom_filter in zip(scenes, plans, zoom_filters):
        if sc.image_path is None:
            raise RenderError(f"Scene {sc.index} chua co image_path")

        out_clip = temp_dir / f"clip_{sc.index:03d}.mp4"
        # Filter chain:
        #   [0:v] -> scale cover (fill frame) -> crop center -> format
        # scale cover dam bao image luon fill toan bo frame, crop center de dat dung size.
        # Khong dung zoompan (da bi bug khi iw==ow).
        vf = (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            f"setsar=1,format=yuv420p"
        )
        if color_filter:
            vf += f",{color_filter}"
        if zoom_filter:
            # Neu muon zoompan (tuong lai), append - hien tai khong su dung
            vf = f"{zoom_filter},{vf}"

        n_frames = max(1, int(sc.duration * fps))
        cmd = [
            ffmpeg, "-y",
            "-loop", "1",
            "-t", f"{sc.duration:.3f}",
            "-i", str(sc.image_path),
            "-vf", vf,
            "-frames:v", str(n_frames),
            "-r", str(fps),
            "-an",
            "-c:v", "libx264",
            "-preset", str(cfg.get("render", {}).get("preset", "medium")),
            "-crf", str(cfg.get("render", {}).get("crf", 20)),
            "-pix_fmt", "yuv420p",
            str(out_clip),
        ]
        log.info("Render scene %02d (%s, %.1fs) -> %s", sc.index, sc.ken_burns_direction, sc.duration, out_clip.name)
        _run(cmd)
        clips.append(out_clip)

    return clips


def concatenate_clips(
    clips: List[Path],
    output_path: Path,
    cfg: Dict[str, Any],
) -> Path:
    """Ghep cac clip thanh 1 video dai (khong co audio).

    Args:
        clips: Danh sach clip MP4.
        output_path: File video output.
        cfg: Config dict.

    Returns:
        Path den file video da ghep.
    """
    if not clips:
        raise RenderError("Khong co clip nao de ghep.")
    if len(clips) == 1:
        shutil.copy2(clips[0], output_path)
        return output_path

    ffmpeg = _ffmpeg_path(cfg)
    list_file = output_path.with_suffix(".txt")
    with list_file.open("w", encoding="utf-8") as f:
        for c in clips:
            # FFmpeg concat demuxer can absolute path escaped
            p = str(c.resolve()).replace("\\", "/").replace("'", r"\'")
            f.write(f"file '{p}'\n")

    cmd = [
        ffmpeg, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(output_path),
    ]
    log.info("Concat %d clips -> %s", len(clips), output_path.name)
    _run(cmd)

    # Don dep
    try:
        list_file.unlink()
    except OSError:
        pass

    return output_path


def build_filter_complex(
    voice_path: Path,
    music_path: Optional[Path],
    cfg: Dict[str, Any],
    duration: float,
) -> str:
    """Xay dung filter_complex de mix audio (voice + music) va them subtitle.

    Returns:
        Chuoi filter_complex.
    """
    parts: List[str] = []
    audio_inputs = []
    audio_labels = []

    # Voice input
    parts.append(f"[1:a]aresample=22050,pan=mono|c0=c0[v]")
    audio_inputs.append("v")
    audio_labels.append("[vout]")

    # Music input (optional)
    if music_path is not None:
        parts.append(f"[2:a]aresample=22050[m]")
        # Mix voice + music
        parts.append(f"[v][m]amix=inputs=2:duration=first:weights=1 0.85,volume=2[aout]")
    else:
        parts.append("[v]anull[aout]")

    return ";".join(parts)


def render_final(
    video_path: Path,
    voice_path: Path,
    music_path: Optional[Path],
    output_path: Path,
    cfg: Dict[str, Any],
    duration: float,
    subtitle_ass: Optional[Path] = None,
) -> Path:
    """Render final: video + voice + music + (optional subtitle).

    Args:
        video_path: Video da ghep tu clips.
        voice_path: File WAV giong doc tong hop.
        music_path: File WAV background music (optional).
        output_path: File MP4 cuoi cung.
        cfg: Config dict.
        duration: Tong thoi luong video (giay).
        subtitle_ass: File .ASS neu muon burn subtitle (optional).

    Returns:
        Path den file output.
    """
    ffmpeg = _ffmpeg_path(cfg)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    render_cfg = cfg.get("render", {})
    vcodec = render_cfg.get("video_codec", "libx264")
    preset = render_cfg.get("preset", "medium")
    crf = render_cfg.get("crf", 20)
    pix_fmt = render_cfg.get("pixel_format", "yuv420p")
    acodec = render_cfg.get("audio_codec", "aac")
    audio_bitrate = render_cfg.get("audio_bitrate", "192k")

    # Subtitle burn-in (neu co file .ass)
    # De tranh loi parse path co ky tu dac biet tren Windows, copy file ASS
    # sang thu muc temp (path ngan) truoc khi truyen cho ffmpeg.
    ass_for_ffmpeg: Optional[Path] = None
    if subtitle_ass is not None and subtitle_ass.exists():
        ass_for_ffmpeg = subtitle_ass

    # Xay dung filter_complex (gom audio mix + subtitle burn-in neu co)
    filter_parts: List[str] = []
    output_audio = "[aout]"

    # Voice-only: không có music, chỉ lấy voice thuần
    if music_path is not None:
        filter_parts.append("[1:a]aresample=22050[v]")
        filter_parts.append("[2:a]aresample=22050[m]")
        filter_parts.append(
            "[v][m]amix=inputs=2:duration=first:weights=1 1,volume=1.5[aout]"
        )
    else:
        # Voice-only: chỉ giữ voice, loại bỏ hoàn toàn music
        filter_parts.append("[1:a]aresample=22050,aformat=sample_fmts=fltp[aout]")

    video_label = "0:v"
    if ass_for_ffmpeg is not None:
        # Copy file ASS vao cung thu muc voi file video output (path tuyet doi).
        # Sau do se dung path tuong doi so voi cwd khi goi ffmpeg.
        ass_target = subtitle_ass.parent / "_subs_for_ffmpeg.ass" if subtitle_ass else None
        if ass_target is not None:
            try:
                ass_target.write_bytes(ass_for_ffmpeg.read_bytes())
            except OSError:
                ass_target = ass_for_ffmpeg
        else:
            ass_target = ass_for_ffmpeg

        # Path tuong doi so voi cwd (cwd = project root khi chay pipeline.py).
        # Neu khong the lay relative, fallback dung absolute path voi escape.
        try:
            ass_path_str = os.path.relpath(str(ass_target.resolve())).replace("\\", "/")
        except ValueError:
            ass_path_str = str(ass_target.resolve()).replace("\\", "/").replace(":", r"\:")

        video_label = "[vsub]"
        filter_parts.append(f"[0:v]subtitles={ass_path_str}{video_label}")

    filter_complex = ";".join(filter_parts)

    cmd = [
        ffmpeg, "-y",
        "-i", str(video_path),
        "-i", str(voice_path),
    ]
    if music_path is not None:
        cmd += ["-i", str(music_path)]

    cmd += ["-filter_complex", filter_complex]
    cmd += ["-map", video_label, "-map", output_audio]
    cmd += [
        "-c:v", vcodec,
        "-preset", preset,
        "-crf", str(crf),
        "-pix_fmt", pix_fmt,
        "-c:a", acodec,
        "-b:a", audio_bitrate,
        str(output_path),
    ]

    log.info("Final render -> %s", output_path.name)
    _run(cmd)
    return output_path


def render_full_pipeline(
    scenes: List[Scene],
    audio_segments: List[AudioSegment],
    cfg: Dict[str, Any],
    temp_dir: Path,
    voice_full_path: Path,
    music_track_path: Optional[Path],
    subtitle_path: Optional[Path],
    output_path: Path,
    total_duration: float,
) -> Path:
    """Render toan bo pipeline.

    Args:
        scenes: Danh sach Scene.
        audio_segments: Audio segments (de logging).
        cfg: Config.
        temp_dir: Thu muc temp.
        voice_full_path: File WAV giong doc tong hop.
        music_track_path: File nhac (optional).
        subtitle_path: File subtitle ASS (optional).
        output_path: File MP4 cuoi.
        total_duration: Tong thoi luong.

    Returns:
        Path den file MP4 output.
    """
    fps = int(cfg.get("render", {}).get("fps", 24))
    width = int(cfg.get("render", {}).get("width", 1920))
    height = int(cfg.get("render", {}).get("height", 1080))

    # 1. Plan Ken Burns
    plans = plan_ken_burns(
        scenes=scenes,
        ken_burns_cfg=cfg.get("ken_burns", {}),
        fps=fps,
        width=width,
        height=height,
        seed=42,
    )

    # 2. Render moi scene thanh clip
    clips = render_scene_clips(scenes, plans, cfg, temp_dir)

    # 3. Concat clips
    concatenated = temp_dir / "concatenated.mp4"
    concatenate_clips(clips, concatenated, cfg)

    # 4. Final render (them voice, music, subtitle)
    subtitle_ass = subtitle_path if cfg.get("subtitle", {}).get("burn_in", True) else None
    if subtitle_ass is not None and not subtitle_ass.exists():
        subtitle_ass = None

    final = render_final(
        video_path=concatenated,
        voice_path=voice_full_path,
        music_path=music_track_path,
        output_path=output_path,
        cfg=cfg,
        duration=total_duration,
        subtitle_ass=subtitle_ass,
    )

    return final
