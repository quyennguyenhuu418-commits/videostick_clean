"""TTS engine: Kokoro-82M (Apache 2.0) local onnx.

Wrapper don gian cho kokoro-onnx (https://github.com/thewh1teagle/kokoro-onnx).

Thiet ke:
    - Load model mot lan (lazy init) va cache.
    - Cung cap interface giong voi Piper engine de pipeline.py khong can
      thay doi logic khi chuyen engine.
    - Su dung espeak-ng bundled trong kokoro-onnx (da copy sang
      assets/espeak-ng-data neu can).

Voices (v1.0):
    am_adam     - American male, trầm ấm, gần Adam/AXEN nhất (recommend)
    am_michael  - American male, trầm, rõ ràng
    am_onyx     - American male, trầm sâu
    am_echo     - American male, trung tính
    bm_george   - British male, trầm trung (documentary)
    bm_lewis    - British male, sang trọng
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import wave
from pathlib import Path
from typing import Optional

from .exceptions import AssetNotFoundError, TTSError

log = logging.getLogger(__name__)


KOKORO_VOICES = {
    "am_adam":    "American male, trầm ấm, gần Adam/AXEN nhất",
    "am_michael": "American male, trầm rõ ràng",
    "am_onyx":    "American male, trầm sâu, authoritative",
    "am_echo":    "American male, trung tính",
    "am_fenrir":  "American male, trầm trung",
    "am_liam":    "American male, trung-cao",
    "am_puck":    "American male, trung-cao, dynamic",
    "am_santa":   "American male, festive",
    "am_eric":    "American male, trung tính",
    "bm_george":  "British male, trầm trung (documentary)",
    "bm_lewis":   "British male, sang trọng (lifestyle/business)",
    "bm_daniel":  "British male, ấm",
    "bm_fable":   "British male, kể chuyện",
}

DEFAULT_MODEL_NAME = "kokoro-v1.0.onnx"
DEFAULT_VOICES_NAME = "voices-v1.0.bin"


class KokoroEngine:
    """Kokoro-82M TTS engine wrapper.

    Su dung:
        engine = KokoroEngine(model_dir="assets/kokoro")
        wav_path = engine.synthesize(
            text="Hello world",
            voice="am_adam",
            speed=1.0,
            lang="en-us",
            output_path=Path("out.wav"),
        )
    """

    def __init__(
        self,
        model_dir: str | os.PathLike[str],
        model_name: str = DEFAULT_MODEL_NAME,
        voices_name: str = DEFAULT_VOICES_NAME,
        espeak_data_dir: Optional[str | os.PathLike[str]] = None,
    ) -> None:
        """Khoi tao engine, load model neu co the.

        Args:
            model_dir: Thu muc chua model Kokoro (assets/kokoro).
            model_name: Ten file .onnx.
            voices_name: Ten file voices .bin.
            espeak_data_dir: Duong den espeak-ng-data (neu None, auto-detect).

        Raises:
            AssetNotFoundError: Neu khong tim thay model/voices file.
            TTSError: Neu khong cai duoc kokoro-onnx hoac load loi.
        """
        self.model_dir = Path(model_dir)
        self.model_path = self.model_dir / model_name
        self.voices_path = self.model_dir / voices_name

        if not self.model_path.is_file():
            raise AssetNotFoundError(
                f"Khong tim thay Kokoro model: {self.model_path}. "
                f"Hay tai tu https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX "
                f"va dat vao {self.model_dir}/"
            )
        if not self.voices_path.is_file():
            raise AssetNotFoundError(
                f"Khong tim thay Kokoro voices file: {self.voices_path}. "
                f"Hay dat file voices-v1.0.bin vao {self.model_dir}/"
            )

        # Setup espeak-ng data path
        self._setup_espeak_data(espeak_data_dir)

        # Load model (lazy import de tranh loi khi chua cai kokoro-onnx)
        try:
            from kokoro_onnx import Kokoro  # type: ignore
        except ImportError as e:
            raise TTSError(
                "Chua cai kokoro-onnx. Chay: pip install kokoro-onnx soundfile"
            ) from e

        log.info("Loading Kokoro model from %s", self.model_path.name)
        try:
            self._kokoro = Kokoro(str(self.model_path), str(self.voices_path))
        except Exception as e:
            raise TTSError(f"Khong load duoc Kokoro model: {e}") from e

        log.info("Kokoro engine ready (%d voices available)", len(self.get_voices()))

    def _setup_espeak_data(self, espeak_data_dir: Optional[str | os.PathLike[str]]) -> None:
        """Thiet lap ESPEAK_DATA_PATH cho process hien tai.

        Uu tien:
            1. espeak_data_dir neu user chi dinh.
            2. assets/espeak-ng-data (project local).
            3. espeak-ng bundled trong kokoro-onnx (copy neu can).
        """
        target: Optional[Path] = None

        if espeak_data_dir is not None:
            p = Path(espeak_data_dir)
            if p.is_dir():
                target = p

        if target is None:
            project_espeak = self.model_dir.parent / "espeak-ng-data"
            if project_espeak.is_dir():
                target = project_espeak

        if target is None:
            # Thu copy espeak-ng bundled trong kokoro-onnx package
            try:
                import kokoro_onnx
                bundled = Path(kokoro_onnx.__file__).parent / "espeak-ng-data"
                if bundled.is_dir():
                    project_espeak = self.model_dir.parent / "espeak-ng-data"
                    project_espeak.mkdir(parents=True, exist_ok=True)
                    if not any(project_espeak.iterdir()):
                        shutil.copytree(str(bundled), str(project_espeak),
                                        dirs_exist_ok=True)
                        log.info("Copied espeak-ng-data to %s", project_espeak)
                    target = project_espeak
            except ImportError:
                pass

        if target is not None:
            os.environ["ESPEAK_DATA_PATH"] = str(target.resolve())
            log.debug("ESPEAK_DATA_PATH = %s", target)

    def get_voices(self) -> list[str]:
        """Tra ve danh sach voice co san trong model."""
        try:
            return list(self._kokoro.get_voices())
        except Exception:
            return list(KOKORO_VOICES.keys())

    def is_available(self) -> bool:
        """Engine da load thanh cong chua."""
        return hasattr(self, "_kokoro") and self._kokoro is not None

    def synthesize(
        self,
        text: str,
        voice: str = "am_adam",
        speed: float = 1.0,
        lang: str = "en-us",
        output_path: Optional[Path] = None,
    ) -> tuple[Path, float]:
        """Tong hop 1 doan text thanh file WAV.

        Args:
            text: Van ban can doc.
            voice: Voice name (vd: 'am_adam', 'am_michael').
            speed: 0.5 - 2.0 (1.0 = binh thuong).
            lang: Language code (en-us, en-gb, ...).
            output_path: Path output WAV (None = tao file tam).

        Returns:
            (path_wav, duration_seconds).
        """
        if not text or not text.strip():
            raise TTSError("Empty text for TTS synthesis.")

        # Clamp speed theo khoang cho phep cua Kokoro
        speed = max(0.5, min(2.0, float(speed)))

        if output_path is None:
            import tempfile
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.close()
            output_path = Path(tmp.name)
        else:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            samples, sample_rate = self._kokoro.create(
                text.strip(),
                voice=voice,
                speed=speed,
                lang=lang,
            )
        except Exception as e:
            raise TTSError(f"Kokoro synthesize failed: {e}") from e

        # Ghi ra WAV (16-bit PCM mono/stereo giong sample_rate)
        try:
            import numpy as np
            # samples co the la float32 [-1, 1] hoac int16
            if samples.dtype == np.float32 or samples.dtype == np.float64:
                audio_int16 = (np.clip(samples, -1.0, 1.0) * 32767.0).astype(np.int16)
            else:
                audio_int16 = samples.astype(np.int16)

            n_channels = 1 if audio_int16.ndim == 1 else audio_int16.shape[1]

            with wave.open(str(output_path), "wb") as wf:
                wf.setnchannels(n_channels)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(int(sample_rate))
                wf.writeframes(audio_int16.tobytes())

            duration = len(audio_int16) / float(sample_rate)
            log.debug("Kokoro: voice=%s, dur=%.2fs, rate=%d", voice, duration, sample_rate)
            return output_path, duration

        except Exception as e:
            raise TTSError(f"Khong ghi duoc WAV file: {e}") from e


def is_kokoro_available(model_dir: Optional[Path] = None) -> bool:
    """Kiem tra nhanh: Kokoro co the khoi tao khong.

    Args:
        model_dir: Thu muc model. Neu None, kiem tra package pip.
    """
    try:
        import kokoro_onnx  # noqa: F401
    except ImportError:
        return False

    if model_dir is None:
        return True  # Package co, con model file kiem tra sau

    return (Path(model_dir) / DEFAULT_MODEL_NAME).is_file() and \
           (Path(model_dir) / DEFAULT_VOICES_NAME).is_file()
