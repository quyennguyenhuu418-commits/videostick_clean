"""Quan ly background music: tim file nhac, loop, fade in/out."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

from .exceptions import AssetNotFoundError


log = logging.getLogger(__name__)


def find_music_file(music_cfg: dict, music_dir: str | os.PathLike[str]) -> Path | None:
    """Tim file nhac trong thu muc assets/music.

    Args:
        music_cfg: Dict music tu config.
        music_dir: Thu muc music.

    Returns:
        Path den file nhac, hoac None neu khong tim thay hoac music bi disable.
    """
    if not music_cfg.get("enabled", True):
        return None

    music_dir_path = Path(music_dir)
    if not music_dir_path.is_dir():
        log.warning("Thu muc music khong ton tai: %s", music_dir_path)
        return None

    target_name = music_cfg.get("file", "")
    if target_name:
        direct = music_dir_path / target_name
        if direct.is_file():
            return direct

    # Tim file dau tien trong thu muc
    for ext in (".mp3", ".wav", ".m4a", ".aac", ".ogg"):
        matches = list(music_dir_path.glob(f"*{ext}"))
        if matches:
            return matches[0]

    log.warning("Khong tim thay file music trong %s", music_dir_path)
    return None


def prepare_background_track(
    music_cfg: dict,
    music_path: Path,
    target_duration: float,
    output_path: Path,
) -> Path:
    """Tao track nhac dai bang target_duration (loop neu canh) co fade in/out.

    Args:
        music_cfg: Dict music config.
        music_path: File nhac nguon.
        target_duration: Tong thoi luong can (giay).
        output_path: File WAV output.

    Returns:
        Path den file output.
    """
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise AssetNotFoundError("Khong tim thay ffmpeg de xu ly background music.")

    volume = float(music_cfg.get("volume", 0.2))
    fade_in = float(music_cfg.get("fade_in", 3.0))
    fade_out = float(music_cfg.get("fade_out", 3.0))

    fade_in = min(fade_in, target_duration / 2)
    fade_out = min(fade_out, target_duration / 2)
    fade_out_start = max(0.0, target_duration - fade_out)

    # Filter graph:
    #   1. Lay input, loop neu canh de du target_duration.
    #   2. ap dung volume.
    #   3. ap dung afade in/out.
    #   4. atrim chinh xac target_duration.
    filter_complex = (
        f"[0:a]aloop=loop=-1:size=2e9,atrim=duration={target_duration}[a];"
        f"[a]volume={volume}[v];"
        f"[v]afade=t=in:st=0:d={fade_in},afade=t=out:st={fade_out_start}:d={fade_out}[out]"
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_bin, "-y",
        "-i", str(music_path),
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-c:a", "pcm_s16le",
        "-ar", "22050",
        "-ac", "1",
        str(output_path),
    ]
    log.debug("Music ffmpeg cmd: %s", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode(errors="ignore") if e.stderr else ""
        raise AssetNotFoundError(f"Loi tao background track: {stderr[:300]}")

    log.info("Background track san sang: %s (%.1fs)", output_path.name, target_duration)
    return output_path
