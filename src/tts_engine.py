"""TTS engine: factory + Piper implementation.

Thiet ke:
    - Factory `get_tts_engine(name, ...)` tra ve engine phu hop (Piper hoac Kokoro).
    - PiperEngine: code goc, tach rieng de de bao tri.
    - Pipeline.py goi qua factory, khong can biet engine cu the.

Engine ho tro:
    - "piper": piper-tts + onnx (hien tai)
    - "kokoro": kokoro-onnx (Apache 2.0, chat luong cao hon)

Fallback neu khong co model: tao WAV silence de pipeline van chay duoc.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .exceptions import AssetNotFoundError, TTSError
from .scene_segmenter import Scene

log = logging.getLogger(__name__)

SUPPORTED_ENGINES = ("piper", "kokoro")


@dataclass
class AudioSegment:
    """Moi audio cho 1 scene."""

    scene_index: int
    wav_path: Path
    duration: float  # giay


# =========================================================================
# Piper Engine (giu tu code goc)
# =========================================================================

def _have_piper() -> bool:
    """Kiem tra piper-tts da duoc cai dat chua."""
    try:
        import piper  # noqa: F401
        return True
    except Exception:
        return False


def _resolve_piper_voice(voice_dir: Path, voice_name: str) -> tuple[Path, Path]:
    """Tim file .onnx va .onnx.json trong thu muc voice_dir."""
    if not voice_dir.is_dir():
        raise AssetNotFoundError(f"Thu muc voice khong ton tai: {voice_dir}")

    candidates_onnx = list(voice_dir.glob(f"{voice_name}*.onnx"))
    candidates_json = list(voice_dir.glob(f"{voice_name}*.onnx.json"))
    if not candidates_onnx:
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


def _find_ffmpeg() -> Optional[str]:
    import shutil
    return shutil.which("ffmpeg")


def _apply_speed_atempo(wav_path: Path, speed: float, output_path: Path) -> Path:
    """Ap dung toc do (speed != 1.0) bang ffmpeg atempo."""
    if abs(speed - 1.0) < 0.01:
        if wav_path != output_path:
            shutil.copy2(wav_path, output_path)
        return output_path

    ffmpeg_bin = _find_ffmpeg()
    if not ffmpeg_bin:
        log.warning("Khong tim thay ffmpeg; giu nguyen toc do audio.")
        shutil.copy2(wav_path, output_path)
        return output_path

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
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        raise TTSError(f"Loi ffmpeg atempo: {e.stderr.decode(errors='ignore')[:300]}")
    return output_path


def _apply_pitch_shift(wav_path: Path, semitones: float, output_path: Path) -> Path:
    """Ap dung pitch shift bang ffmpeg asetrate + aresample."""
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
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        raise TTSError(f"Loi ffmpeg pitch shift: {e.stderr.decode(errors='ignore')[:300]}")
    return output_path


def _write_silence_wav(wav_path: Path, duration: float, sample_rate: int = 22050) -> None:
    """Tao file WAV im lang voi duration cho truoc."""
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    n_frames = max(0, int(duration * sample_rate))
    silence = b"\x00\x00" * n_frames
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(silence)


def _piper_synthesize(text: str, onnx_path: Path, json_path: Path, output_wav: Path, cfg: dict) -> Path:
    """Tong hop giong doc bang Piper."""
    import piper
    from piper import PiperVoice
    from piper.config import SynthesisConfig

    # Fix piper load() tren Windows user co dau/khong ASCII
    project_espeak_dir = Path(__file__).resolve().parent.parent / "assets" / "espeak-ng-data"
    if not project_espeak_dir.is_dir():
        bundled = Path(piper.__file__).parent / "espeak-ng-data"
        if bundled.is_dir():
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


# =========================================================================
# Factory + public API
# =========================================================================

class PiperEngineWrapper:
    """Adapter de PiperEngine co cung interface voi KokoroEngine.

    Luon load model ngay (Piper rat nhanh) -> pipeline behavior giong cu.
    """

    def __init__(self, voice_dir: Path, voice_name: str, cfg: dict):
        self.voice_dir = Path(voice_dir)
        self.voice_name = voice_name
        self.cfg = cfg
        self._onnx_path: Optional[Path] = None
        self._json_path: Optional[Path] = None
        self._available = False

        if _have_piper():
            try:
                self._onnx_path, self._json_path = _resolve_piper_voice(
                    self.voice_dir, self.voice_name
                )
                self._available = True
                log.info("Piper voice model: %s", self._onnx_path.name)
            except AssetNotFoundError as e:
                log.warning("%s. Fallback: silence WAV.", e)

    def is_available(self) -> bool:
        return self._available

    def get_voices(self) -> list[str]:
        """Tra ve cac voice tim thay trong voice_dir."""
        if not self.voice_dir.is_dir():
            return []
        return sorted([p.stem.replace(".onnx", "")
                       for p in self.voice_dir.glob("*.onnx")
                       if p.is_file()])

    def synthesize(
        self,
        text: str,
        voice: str = "",
        speed: float = 1.0,
        lang: str = "en",
        output_path: Optional[Path] = None,
    ) -> tuple[Path, float]:
        if not self._available or self._onnx_path is None:
            raise TTSError("Piper engine khong kha dung (thieu model hoac package).")

        if output_path is None:
            import tempfile
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.close()
            output_path = Path(tmp.name)
        else:
            output_path.parent.mkdir(parents=True, exist_ok=True)

        _piper_synthesize(
            text,
            self._onnx_path,
            self._json_path,  # type: ignore[arg-type]
            output_path,
            self.cfg,
        )
        return output_path, _get_audio_duration(output_path)


def get_tts_engine(
    engine_name: str,
    voice_dir: Path,
    tts_cfg: dict,
    kokoro_model_dir: Optional[Path] = None,
):
    """Factory: tra ve engine instance.

    Args:
        engine_name: "piper" hoac "kokoro".
        voice_dir: Thu muc voice cho Piper (assets/voices).
        tts_cfg: Dict tts tu config (engine, voice_model, speed, ...).
        kokoro_model_dir: Thu muc Kokoro model (assets/kokoro).

    Returns:
        Engine object co method: is_available(), get_voices(),
        synthesize(text, voice, speed, lang, output_path).

    Raises:
        TTSError: Neu engine_name khong ho tro.
    """
    engine_name = (engine_name or "piper").lower().strip()

    if engine_name == "piper":
        voice_name = tts_cfg.get("voice_model", "")
        return PiperEngineWrapper(voice_dir, voice_name, tts_cfg)

    if engine_name == "kokoro":
        from .tts_kokoro import KokoroEngine
        if kokoro_model_dir is None:
            kokoro_model_dir = voice_dir.parent / "kokoro"
        return KokoroEngine(
            model_dir=kokoro_model_dir,
            espeak_data_dir=voice_dir.parent / "espeak-ng-data",
        )

    raise TTSError(
        f"Engine '{engine_name}' khong ho tro. "
        f"Chon mot trong: {', '.join(SUPPORTED_ENGINES)}"
    )


# =========================================================================
# Public API (giu tuong thich voi code cu)
# =========================================================================

def synth_scenes(
    scenes: List[Scene],
    output_dir: str | os.PathLike[str],
    tts_cfg: dict,
    voice_dir: str | os.PathLike[str],
    kokoro_model_dir: Optional[str | os.PathLike[str]] = None,
) -> List[AudioSegment]:
    """Tong hop giong doc cho tat ca scene.

    Args:
        scenes: Danh sach Scene co text.
        output_dir: Thu muc xuat WAV.
        tts_cfg: Dict tts tu config.yaml (co the chua `engine` key).
        voice_dir: Thu muc chua Piper voice model (assets/voices).
        kokoro_model_dir: Thu muc Kokoro (mac dinh: assets/kokoro).

    Returns:
        Danh sach AudioSegment theo thu tu scene.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    voice_dir = Path(voice_dir)
    if kokoro_model_dir is None:
        kokoro_model_dir = voice_dir.parent / "kokoro"
    kokoro_model_dir = Path(kokoro_model_dir)

    engine_name = tts_cfg.get("engine", "piper")
    engine = None
    engine_available = False

    try:
        engine = get_tts_engine(
            engine_name,
            voice_dir,
            tts_cfg,
            kokoro_model_dir,
        )
        engine_available = engine.is_available()
        if engine_available:
            log.info("TTS engine: %s", engine_name)
        else:
            log.warning("Engine %s khong kha dung (thieu model). Fallback silence.", engine_name)
    except TTSError as e:
        log.error("Khong khoi tao duoc engine '%s': %s. Fallback silence.", engine_name, e)
    except Exception as e:
        log.error("Loi bat khi khoi tao engine: %s. Fallback silence.", e)

    # Engine-specific params
    if engine_name == "kokoro":
        default_voice = tts_cfg.get("kokoro", {}).get("voice", "am_adam")
        default_speed = float(tts_cfg.get("kokoro", {}).get("speed", tts_cfg.get("speed", 1.0)))
        default_lang = tts_cfg.get("kokoro", {}).get("lang", "en-us")
        # Kokoro khong can pitch shift
        pitch_shift = 0.0
    else:
        default_voice = ""  # Piper dung voice da load
        default_speed = float(tts_cfg.get("speed", 1.0))
        default_lang = tts_cfg.get("language", "en")
        pitch_shift = float(tts_cfg.get("pitch_shift", 0.0))

    segments: List[AudioSegment] = []

    for sc in scenes:
        raw_wav = out_dir / f"scene_{sc.index:03d}_raw.wav"
        speed_wav = out_dir / f"scene_{sc.index:03d}_speed.wav"
        final_wav = out_dir / f"scene_{sc.index:03d}.wav"

        if engine_available and engine is not None:
            try:
                voice = default_voice
                # Piper: giu nguyen voice da load (bo qua voice param)
                if engine_name == "piper":
                    voice = ""

                engine.synthesize(
                    text=sc.text,
                    voice=voice,
                    speed=default_speed,
                    lang=default_lang,
                    output_path=raw_wav,
                )
            except Exception as e:
                log.error("Loi TTS scene %s: %s. Fallback silence.", sc.index, e)
                _write_silence_wav(raw_wav, sc.duration or 4.0)
        else:
            _write_silence_wav(raw_wav, sc.duration or 4.0)

        # Speed va pitch chi can thiet cho Piper (Kokoro da ap speed truc tiep)
        if engine_name == "piper":
            _apply_speed_atempo(raw_wav, default_speed, speed_wav)
            _apply_pitch_shift(speed_wav, pitch_shift, final_wav)
        else:
            # Kokoro: chi can doi ten file
            shutil.move(str(raw_wav), str(final_wav))

        dur = _get_audio_duration(final_wav)
        if dur <= 0:
            dur = sc.duration

        sc.audio_path = final_wav
        sc.audio_duration = dur

        segments.append(AudioSegment(
            scene_index=sc.index,
            wav_path=final_wav,
            duration=dur,
        ))
        log.info("TTS [%s] scene %02d | dur=%.2fs | %s",
                 engine_name, sc.index, dur, final_wav.name)

    return segments


def concatenate_segments(segments: List[AudioSegment], output_path: Path, silence_padding: float = 0.5) -> Path:
    """Noi cac segment WAV thanh 1 file WAV dai."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not segments:
        _write_silence_wav(output_path, 0.0)
        return output_path

    sample_rate = 22050
    sample_width = 2
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
                if (wf.getframerate() != sample_rate or
                        wf.getsampwidth() != sample_width or
                        wf.getnchannels() != n_channels):
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
