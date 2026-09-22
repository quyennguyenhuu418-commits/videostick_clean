"""VideoStick - Pipeline render video storytelling tu dong.

Usage:
    python pipeline.py [CONFIG_PATH] [--preset axen] [--clean-temp]

Vi du:
    python pipeline.py
    python pipeline.py config.yaml --preset axen
    python pipeline.py config.yaml --clean-temp
"""

from __future__ import annotations

import argparse
import datetime as _dt
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from src.config import load_config
from src.exceptions import VideoStickError
from src.logger import get_logger, setup_logging
from src.music_manager import find_music_file, prepare_background_track
from src.renderer import render_full_pipeline
from src.scene_segmenter import parse_script, resolve_image_paths
from src.style_presets import apply_preset
from src.subtitle_generator import generate_ass, generate_subtitles
from src.timing_estimator import compute_durations, refine_with_audio_durations, total_duration
from src.tts_engine import concatenate_segments, synth_scenes


def _resolve_project_paths(cfg: Dict[str, Any], project_root: Path) -> Dict[str, Path]:
    """Chuyen cac duong dan trong config thanh Path tuyet doi."""
    paths = cfg.get("paths", {})
    return {
        "input_images": project_root / paths.get("input_images", "input/images"),
        "input_script": project_root / paths.get("input_script", "input/script.txt"),
        "output_dir": project_root / paths.get("output_dir", "output"),
        "temp_dir": project_root / paths.get("temp_dir", "temp"),
        "logs_dir": project_root / paths.get("logs_dir", "logs"),
        "voice_dir": project_root / paths.get("voice_model", "assets/voices"),
        "music_dir": project_root / paths.get("music_dir", "assets/music"),
        "fonts_dir": project_root / paths.get("fonts_dir", "assets/fonts"),
    }


def main(argv: Optional[list[str]] = None) -> int:
    """Entry point chinh cua pipeline."""
    parser = argparse.ArgumentParser(description="VideoStick - render video storytelling tu dong.")
    parser.add_argument(
        "config",
        nargs="?",
        default="config.yaml",
        help="Duong den file config (mac dinh: config.yaml).",
    )
    parser.add_argument(
        "--preset",
        default="axen",
        choices=["axen", "draft"],
        help="Style preset (mac dinh: axen).",
    )
    parser.add_argument(
        "--clean-temp",
        action="store_true",
        help="Xoa thu muc temp truoc khi chay.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chi parse input va in thong tin, khong render.",
    )
    args = parser.parse_args(argv)

    # 1. Load config
    config_path = Path(args.config)
    if not config_path.is_file():
        print(f"[LOI] Khong tim thay config: {config_path.resolve()}", file=sys.stderr)
        return 2

    try:
        cfg = load_config(config_path)
    except Exception as e:
        print(f"[LOI] Khong doc duoc config: {e}", file=sys.stderr)
        return 2

    # Ap dung preset len config
    cfg = apply_preset(cfg, args.preset)

    # 2. Setup logging
    setup_logging(cfg)
    log = get_logger("pipeline")
    log.info("=" * 60)
    log.info("VideoStick pipeline bat dau (preset=%s)", args.preset)
    log.info("Config: %s", config_path.resolve())

    project_root = config_path.resolve().parent
    paths = _resolve_project_paths(cfg, project_root)

    # Dam bao cac thu muc can thiet ton tai
    for k in ("output_dir", "temp_dir", "logs_dir"):
        paths[k].mkdir(parents=True, exist_ok=True)

    if args.clean_temp and paths["temp_dir"].exists():
        shutil.rmtree(paths["temp_dir"])
        paths["temp_dir"].mkdir(parents=True, exist_ok=True)
        log.info("Da clean temp dir.")

    try:
        # 3. Parse script
        log.info("[1/6] Parse kich ban: %s", paths["input_script"])
        scenes = parse_script(paths["input_script"])
        log.info("  -> %d scene.", len(scenes))

        # 4. Resolve image paths
        log.info("[2/6] Giai quyet duong dan anh: %s", paths["input_images"])
        scenes = resolve_image_paths(scenes, paths["input_images"])

        # 5. Tinh duration
        log.info("[3/6] Tinh thoi luong scene...")
        cfg_lang = cfg.get("tts", {}).get("language", "vi")
        scenes = compute_durations(scenes, cfg.get("timing", {}), language=cfg_lang)
        for sc in scenes:
            log.info("  scene %02d | dur=%.2fs | %s", sc.index, sc.duration, sc.image_filename)

        if args.dry_run:
            total = total_duration(scenes)
            log.info("Dry run: tong thoi luong = %.2fs (%d scenes)", total, len(scenes))
            return 0

        # 6. TTS
        tts_cfg = cfg.get("tts", {})
        log.info("[4/6] Sinh giong doc (engine=%s)...", tts_cfg.get("engine", "piper"))
        audio_segments = synth_scenes(
            scenes=scenes,
            output_dir=paths["temp_dir"],
            tts_cfg=tts_cfg,
            voice_dir=paths["voice_dir"],
            kokoro_model_dir=paths["voice_dir"].parent / "kokoro",
        )
        # Cap nhat duration theo audio that
        scenes = refine_with_audio_durations(scenes, silence_padding=cfg.get("timing", {}).get("silence_padding", 0.5))

        # Noi voice thanh file dai
        voice_full = paths["temp_dir"] / "voice_full.wav"
        silence_pad = cfg.get("timing", {}).get("silence_padding", 0.5)
        concatenate_segments(audio_segments, voice_full, silence_padding=silence_pad)

        # 7. Subtitle
        log.info("[5/6] Sinh subtitle...")
        subtitle_cfg = cfg.get("subtitle", {})
        srt_path = paths["output_dir"] / "subtitles.srt"
        ass_path = paths["temp_dir"] / "subtitles.ass"
        generate_subtitles(scenes, srt_path)
        generate_ass(scenes, ass_path, subtitle_cfg)
        log.info("  -> %s", srt_path.name)

        # 8. Background music - FORCE DISABLED for voice-only
        music_path: Optional[Path] = None
        # Bỏ qua hoàn toàn music để chỉ có voice
        log.info("  -> Voice-only mode: background music disabled")
        music_cfg = cfg.get("music", {})
        if music_cfg.get("enabled", False):
            log.warning("Music config says enabled=True nhưng đang bị override sang disabled. Set music.enabled=false trong config.yaml để tắt cảnh báo này.")
        total_dur = total_duration(scenes)

        # 9. Render full pipeline
        log.info("[6/6] Render video...")
        ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = paths["output_dir"] / f"video_{ts}.mp4"

        final = render_full_pipeline(
            scenes=scenes,
            audio_segments=audio_segments,
            cfg=cfg,
            temp_dir=paths["temp_dir"],
            voice_full_path=voice_full,
            music_track_path=music_path,
            subtitle_path=ass_path if subtitle_cfg.get("burn_in", True) else None,
            output_path=output_path,
            total_duration=total_dur,
        )

        log.info("=" * 60)
        log.info("HOAN THANH! Video: %s", final.resolve())
        log.info("Subtitle: %s", srt_path.resolve())
        log.info("=" * 60)
        return 0

    except VideoStickError as e:
        log.error("[LOI Pipeline] %s", e)
        return 1
    except Exception as e:
        log.exception("Loi khong mong doi: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
