"""Cac exception rieng cho VideoStick."""


class VideoStickError(Exception):
    """Base exception cho toan pipeline."""


class ConfigError(VideoStickError):
    """Loi lien quan den config."""


class InputError(VideoStickError):
    """Loi lien quan den input (anh, kich ban)."""


class TTSError(VideoStickError):
    """Loi lien quan den TTS engine."""


class RenderError(VideoStickError):
    """Loi lien quan den render FFmpeg."""


class AssetNotFoundError(VideoStickError):
    """Khong tim thay asset (voice model, music, font)."""
