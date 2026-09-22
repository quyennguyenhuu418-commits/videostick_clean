"""Style presets cho VideoStick.

Hien tai cung cap preset 'axen' (Adam/AXEN YouTube channel style):
    - 1080p24 cinematic
    - Color grading am, saturation giam, contrast tang nhe
    - Vignette
    - Ken Burns zoom nhe, toc do cham
    - Subtitle bold, outline den
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class StylePreset:
    """Preset hoan chinh cho 1 style."""

    name: str
    description: str
    config_overrides: Dict[str, Any] = field(default_factory=dict)


def get_preset(name: str = "axen") -> StylePreset:
    """Tra ve preset theo ten."""
    presets = {
        "axen": StylePreset(
            name="axen",
            description="Adam/AXEN-style cinematic storytelling: 1080p24, warm tone, vignette, slow Ken Burns.",
            config_overrides={
                "render": {
                    "width": 1920,
                    "height": 1080,
                    "fps": 24,
                    "video_codec": "libx264",
                    "preset": "slow",
                    "crf": 18,
                    "pixel_format": "yuv420p",
                    "audio_codec": "aac",
                    "audio_bitrate": "192k",
                },
                "ken_burns": {
                    "enabled": True,
                    "zoom_min": 1.0,
                    "zoom_max": 1.15,
                    "zoom_step": 0.0015,
                    "directions": [
                        "zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "pan_down",
                    ],
                },
                "color_grading": {
                    "enabled": False,
                    "contrast": 1.0,
                    "saturation": 1.0,
                    "brightness": 0.0,
                    "gamma": 1.0,
                    "warm_tone": 0.0,
                    "vignette": {"enabled": False, "intensity": 0.0},
                },
                "subtitle": {
                    "enabled": False,
                    "burn_in": False,
                    "font_size": 52,
                    "font_color": "&H00FFFFFF",
                    "outline_color": "&H00000000",
                    "outline_thickness": 2,
                    "position": "bottom",
                    "margin_v": 60,
                },
                "tts": {
                    "engine": "kokoro",
                    "language": "en",
                    "speed": 0.90,
                    "pitch_shift": -1.0,
                    "noise_scale": 0.667,
                    "length_scale": 1.0,
                    "kokoro": {
                        "voice": "am_onyx",
                        "speed": 0.90,
                        "lang": "en-us",
                    },
                },
                "music": {
                    "enabled": False,
                    "volume": 0.0,
                    "fade_in": 3.0,
                    "fade_out": 4.0,
                },
                "timing": {
                    "words_per_minute": 170,
                    "min_scene_duration": 3.0,
                    "max_scene_duration": 15.0,
                    "silence_padding": 0.4,
                },
            },
        ),
        "draft": StylePreset(
            name="draft",
            description="Render nhanh de test pipeline (CRF cao, preset nhanh).",
            config_overrides={
                "render": {"preset": "ultrafast", "crf": 23},
            },
        ),
    }
    return presets.get(name, presets["axen"])


def apply_preset(base_config: Dict[str, Any], preset_name: str = "axen") -> Dict[str, Any]:
    """Merge preset overrides len base config (deep merge nhe)."""
    preset = get_preset(preset_name)
    out = _deep_copy(base_config)
    for k, v in preset.config_overrides.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k].update(v)
        else:
            out[k] = v
    return out


def _deep_copy(obj):
    """Deep copy nhe cho nested dict/list."""
    if isinstance(obj, dict):
        return {k: _deep_copy(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_copy(v) for v in obj]
    return obj
