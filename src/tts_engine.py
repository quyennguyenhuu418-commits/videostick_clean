"""TTS engine: sinh giong doc cho tung scene bang Piper local.

Thiet ke:
    - Piper TTS sinh file WAV rieng cho tung scene.
    - Ap dung speed, pitch shift (thong qua ffmpeg atempo + asetrate neu can).
    - Neu khong co Piper model, fallback tao WAV silence voi duration tuong ung
      (de pipeline van chay duoc, nguoi dung test pipeline truoc khi co model).

Output:
    - File WAV cho tung scene tai output_dir/<scene_index>.wav
    - File WAV tong hop tai output_dir/voice_full.wav
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .exceptions import AssetNotFoundError, TTSError
from .scene_segmenter import Scene


log = logging.getLogger(__name__)


@dataclass
class AudioSegment:
    """Moi audio cho 1 scene."""

    scene_index: int
    wav_path: Path
    duration: float  # giay


def _have_piper() -> bool:
    """Kiem tra piper-tts da duoc cai dat chua."""
    try:
        import piper  # noqa: F401
        return True
    except Exception:
        return False


def _resolve_piper_voice(voice_dir: Path, voice_name: str) -> tuple[Path, Path]:
    """Tim file .onnx va .onnx.json trong thu muc voice_dir.

    Args:
        voice_dir: Thu muc assets/voices.
        voice_name: Ten model (vd: 'en_US-amy-low' hoac 'en_US-amy-low.onnx').

    Returns:
        (path_onnx, path_json).

    Raises:
        AssetNotFoundError: Neu khong tim thay.
    """
    if not voice_dir.is_dir():
        raise AssetNotFoundError(f"Thu muc voice khong ton tai: {voice_dir}")

    candidates_onnx = list(voice_dir.glob(f"{voice_name}*.onnx"))
    candidates_json = list(voice_dir.glob(f"{voice_name}*.onnx.json"))
    if not candidates_onnx:
        # Thu them: voice_name co the da co .onnx roi
        onnx_path = voice_dir / voice_name
        json_path = voice_dir / f"{voice_name}.json"
        if not onnx_path.exists():
            raise AssetNotFoundError(
                f"Khong tim thay voice model '{voice_name}' trong {voice_dir}. "
                "Hay dat file .onnx + .onnx.json vao thu muc nay."
            )
    else:
        onnx_path = candidates_onnx[0]
        json_path = candidates_json[0] if candidates_json else onnx_path.with_suffix(".onnx.json")

    if not json_path.exists():
        raise AssetNotFoundError(
            f"Tim thay voice model nhung thieu file .onnx.json: {onnx_path}"
        )

    return onnx_path, json_path


def _get_audio_duration(wav_path: Path) -> float:
    """Lay do dai file WAV (giay)."""
    try:
        with wave.open(str(wav_path), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            return frames / float(rate) if rate > 0 else 0.0
    except wave.Error as exc:
        log.warning("Khong doc duoc duration cua %s: %s", wav_path, exc)
        return 0.0


def _apply_speed_atempo(wav_path: Path, speed: float, output_path: Path) -> Path:
    """Ap dung toc do (speed != 1.0) bang ffmpeg atempo.

    Piper khong ho tro speed truc tiep nen can ffmpeg de dieu chinh.
    """
    if abs(speed - 1.0) < 0.01:
        # Khong can thay doi, copy
        if wav_path != output_path:
            shutil.copy2(wav_path, output_path)
        return output_path

    ffmpeg_bin = _find_ffmpeg()
    if not ffmpeg_bin:
        log.warning("Khong tim thay ffmpeg; giu nguyen toc do audio.")
        shutil.copy2(wav_path, output_path)
        return output_path

    # atempo chap nhan 0.5 - 2.0. Neu ngoai khoang, can chain nhieu atempo.
    chain = []
    s = speed
    while s < 0.5:
        chain.append("atempo=0.5")
        s /= 0.5
    while s > 2.0:
        chain.append("atempo=2.0")
        s /= 2.0
    chain.append(f"atempo={s:.3f}")
    filter_str = ",".join(chain)

    cmd = [
        ffmpeg_bin, "-y", "-i", str(wav_path),
        "-filter:a", filter_str,
        "-c:a", "pcm_s16le",
        str(output_path),
    ]
    log.debug("ffmpeg atempo: %s", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        raise TTSError(f"Loi ffmpeg atempo: {e.stderr.decode(errors='ignore')[:300]}")

    return output_path


def _apply_pitch_shift(wav_path: Path, semitones: float, output_path: Path) -> Path:
    """Ap dung pitch shift bang ffmpeg asetrate + aresample.

    Mot semitone = 2^(1/12) ~= 1.059463. Pitch down (am) -> giong tram hon.
    """
    if abs(semitones) < 0.05:
        if wav_path != output_path:
            shutil.copy2(wav_path, output_path)
        return output_path

    ffmpeg_bin = _find_ffmpeg()
    if not ffmpeg_bin:
        log.warning("Khong tim thay ffmpeg; giu nguyen pitch audio.")
        shutil.copy2(wav_path, output_path)
        return output_path

    factor = 2 ** (semitones / 12.0)
    cmd = [
        ffmpeg_bin, "-y", "-i", str(wav_path),
        "-filter:a", f"asetrate=22050*{factor:.6f},aresample=22050",
        "-c:a", "pcm_s16le",
        str(output_path),
    ]
    log.debug("ffmpeg pitch shift: %s", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        raise TTSError(f"Loi ffmpeg pitch shift: {e.stderr.decode(errors='ignore')[:300]}")

    return output_path


def _find_ffmpeg() -> Optional[str]:
    """Tim ffmpeg binary."""
    import shutil
    return shutil.which("ffmpeg")


def _write_silence_wav(wav_path: Path, duration: float, sample_rate: int = 22050) -> None:
    """Fallback: tao file WAV im lang voi duration cho truoc."""
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    n_frames = int(duration * sample_rate)
    import struct
    silence = b"\x00\x00" * n_frames  # 16-bit mono PCM
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(silence)


def _piper_synthesize(text: str, onnx_path: Path, json_path: Path, output_wav: Path, cfg: dict) -> Path:
    """Tong hop giong doc bang Piper (API moi - synthesize tra ve Iterable[AudioChunk])."""
    import os
    import piper
    from piper import PiperVoice
    from piper.config import SynthesisConfig

    # Fix piper load() tren Windows user co dau/khong ASCII: copy espeak-ng-data
    # sang thu muc ASCII (assets/espeak-ng-data) de espeak-ng doc duoc path.
    project_espeak_dir = Path(__file__).resolve().parent.parent / "assets" / "espeak-ng-data"
    if not project_espeak_dir.is_dir():
        bundled = Path(piper.__file__).parent / "espeak-ng-data"
        if bundled.is_dir():
            import shutil
            try:
                shutil.copytree(str(bundled), str(project_espeak_dir))
            except Exception:
                project_espeak_dir = bundled

    if project_espeak_dir.is_dir():
        os.environ["ESPEAK_DATA_PATH"] = str(project_espeak_dir.resolve())

    voice = PiperVoice.load(
        str(onnx_path),
        str(json_path),
        use_cuda=False,
    )

    syn_cfg = SynthesisConfig(
        speaker_id=int(cfg.get("speaker", 0)),
        length_scale=float(cfg.get("length_scale", 1.0)),
        noise_scale=float(cfg.get("noise_scale", 0.667)),
        noise_w_scale=float(cfg.get("noise_w_scale", 0.8)),
    )

    output_wav.parent.mkdir(parents=True, exist_ok=True)
    chunks = list(voice.synthesize(text, syn_config=syn_cfg))

    if not chunks:
        raise TTSError("Piper tra ve khong co audio chunk nao.")

    sample_rate = chunks[0].sample_rate
    sample_width = chunks[0].sample_width
    n_channels = chunks[0].sample_channels

    import numpy as np
    audio_segments = []
    for ch in chunks:
        # Lay int16 array (property lazy-load tu float32 neu can)
        audio = ch._audio_int16_array
        if audio is None:
            float_audio = ch.audio_float_array
            if float_audio is not None:
                audio = (float_audio * 32767.0).astype(np.int16)
            elif ch._audio_int16_bytes is not None:
                audio = np.frombuffer(ch._audio_int16_bytes, dtype=np.int16)
            else:
                raise TTSError("Piper chunk khong co audio data.")
        audio_segments.append(audio)

    full_audio = np.concatenate(audio_segments) if len(audio_segments) > 1 else audio_segments[0]

    with wave.open(str(output_wav), "wb") as wf:
        wf.setnchannels(n_channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(full_audio.tobytes())

    return output_wav


def synth_scenes(
    scenes: List[Scene],
    output_dir: str | os.PathLike[str],
    tts_cfg: dict,
    voice_dir: str | os.PathLike[str],
) -> List[AudioSegment]:
    """Tong hop giong doc cho tat ca scene.

    Args:
        scenes: Danh sach Scene co text.
        output_dir: Thu muc xuat WAV.
        tts_cfg: Dict tts tu config.yaml.
        voice_dir: Thu muc chua Piper voice model.

    Returns:
        Danh sach AudioSegment theo thu tu scene.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    voice_name = tts_cfg.get("voice_model", "")
    speed = float(tts_cfg.get("speed", 1.0))
    pitch = float(tts_cfg.get("pitch_shift", 0.0))

    segments: List[AudioSegment] = []

    have_piper_model = False
    onnx_path: Optional[Path] = None
    json_path: Optional[Path] = None

    if _have_piper():
        try:
            onnx_path, json_path = _resolve_piper_voice(Path(voice_dir), voice_name)
            have_piper_model = True
            log.info("Su dung Piper voice model: %s", onnx_path.name)
        except AssetNotFoundError as e:
            log.warning("%s. Fallback: tao WAV silence de pipeline van chay.", e)
    else:
        log.warning("Chua cai piper-tts. Fallback: WAV silence (khong co giong doc that).")

    for sc in scenes:
        raw_wav = out_dir / f"scene_{sc.index:03d}_raw.wav"
        speed_wav = out_dir / f"scene_{sc.index:03d}_speed.wav"
        final_wav = out_dir / f"scene_{sc.index:03d}.wav"

        if have_piper_model:
            try:
                _piper_synthesize(sc.text, onnx_path, json_path, raw_wav, tts_cfg)
            except Exception as e:
                log.error("Loi TTS scene %s: %s. Fallback silence.", sc.index, e)
                _write_silence_wav(raw_wav, sc.duration)
        else:
            _write_silence_wav(raw_wav, sc.duration or 4.0)

        _apply_speed_atempo(raw_wav, speed, speed_wav)
        _apply_pitch_shift(speed_wav, pitch, final_wav)

        dur = _get_audio_duration(final_wav)
        if dur <= 0:
            dur = sc.duration  # fallback dung estimate

        sc.audio_path = final_wav
        sc.audio_duration = dur

        segments.append(AudioSegment(
            scene_index=sc.index,
            wav_path=final_wav,
            duration=dur,
        ))
        log.info("TTS scene %02d | dur=%.2fs | %s", sc.index, dur, final_wav.name)

    return segments


def concatenate_segments(segments: List[AudioSegment], output_path: Path, silence_padding: float = 0.5) -> Path:
    """Noi cac segment WAV thanh 1 file WAV dai (co chen silence giua cac segment).

    Args:
        segments: Danh sach AudioSegment.
        output_path: File WAV output.
        silence_padding: Khoang lang giua 2 segment (giay).

    Returns:
        Path den file WAV da noi.
    """
    import struct

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not segments:
        # Tao file rong
        _write_silence_wav(output_path, 0.0)
        return output_path

    sample_rate = 22050
    sample_width = 2  # 16-bit
    n_channels = 1

    frames: List[bytes] = []
    total_samples = 0
    silence_samples = int(silence_padding * sample_rate)

    for i, seg in enumerate(segments):
        if i > 0 and silence_samples > 0:
            frames.append(b"\x00\x00" * silence_samples)
            total_samples += silence_samples

        if seg.wav_path.exists():
            with wave.open(str(seg.wav_path), "rb") as wf:
                # Dam bao cung sample rate / width / channels
                if (wf.getframerate() != sample_rate or
                        wf.getsampwidth() != sample_width or
                        wf.getnchannels() != n_channels):
                    # Chuyen doi bang ffmpeg neu khac
                    converted = _convert_wav_format(seg.wav_path, sample_rate, sample_width, n_channels)
                    with wave.open(str(converted), "rb") as wf2:
                        data = wf2.readframes(wf2.getnframes())
                else:
                    data = wf.readframes(wf.getnframes())
            frames.append(data)
            total_samples += len(data) // sample_width

    with wave.open(str(output_path), "wb") as wf:
        wf.setnchannels(n_channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        for chunk in frames:
            wf.writeframes(chunk)

    log.info("Voice full: %s (%.2fs)", output_path.name, total_samples / sample_rate)
    return output_path


def _convert_wav_format(wav_path: Path, rate: int, sampwidth: int, channels: int) -> Path:
    """Chuyen doi WAV sang format chuan (dung ffmpeg neu can)."""
    ffmpeg_bin = _find_ffmpeg()
    if not ffmpeg_bin:
        return wav_path
    out = wav_path.with_suffix(".conv.wav")
    cmd = [
        ffmpeg_bin, "-y", "-i", str(wav_path),
        "-ar", str(rate), "-ac", str(channels), "-sample_fmt", "s16",
        str(out),
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        return out
    except subprocess.CalledProcessError:
        return wav_path
