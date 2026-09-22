"""Sinh filter cho image scene (scale cover + crop).

Ken Burns da bi bug voi zoompan khi iw == ow (anh 1920x1080 + output 1920x1080).
Vi vay, su dung scale+cover+crop don gian de dam bao image fill full frame.
Motion chi dung fade-in/out giua cac scene.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from typing import List

from .scene_segmenter import Scene


log = logging.getLogger(__name__)


KEN_BURNS_DIRECTIONS = (
    "fade",          # motion = fade-in/fade-out
)


@dataclass
class KenBurnsPlan:
    """Ke hoach render cho 1 scene (hien tai chi fade)."""

    scene_index: int
    direction: str = "fade"
    duration: float = 0.0
    fps: int = 24
    width: int = 1920
    height: int = 1080


def plan_ken_burns(
    scenes: List[Scene],
    ken_burns_cfg: dict,
    fps: int,
    width: int,
    height: int,
    seed: int | None = None,
) -> List[KenBurnsPlan]:
    """Tra ve ke hoach fade cho moi scene (khong con pan/zoom)."""
    if not scenes:
        return []
    return [
        KenBurnsPlan(
            scene_index=sc.index,
            direction="fade",
            duration=sc.duration,
            fps=fps,
            width=width,
            height=height,
        )
        for sc in scenes
    ]


def build_zoompan_filter(
    plans: List[KenBurnsPlan],
    ken_burns_cfg: dict,
) -> List[str]:
    """Tra ve filter rong (khong dung zoompan) - scale cover se duoc lam sau."""
    return ["" for _ in plans]
