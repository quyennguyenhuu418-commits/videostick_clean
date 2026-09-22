# -*- coding: utf-8 -*-
"""Tao script.txt cho pipeline tu kịch bản gốc.

Usage:
    python prepare_input.py                              # Mac dinh: kịch bản/kịch bản.txt
    python prepare_input.py "kịch bản/Other Script.txt"  # Tuỳ chỉnh script + folder anh moi nhat
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


# Force UTF-8 output tren Windows console
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


KB_DIR = Path("kịch bản")
DEFAULT_SCRIPT = KB_DIR / "kịch bản.txt"
IMG_DIR = Path("img/Axen_Bundle_NoWatermark")
OUT_SCRIPT = Path("input/script.txt")
OUT_IMAGES = Path("input/images")


# Tim folder ảnh mới nhất trong img/ (uu tên folder moi nhat, fallback Axen bundle).
def resolve_image_dir() -> Path:
    """Chon folder anh: uu tien folder con moi nhat trong img/, fallback chinh img/."""
    img_root = Path("img")
    if not img_root.is_dir():
        return IMG_DIR
    # Lay cac folder con co chua anh
    subdirs_with_imgs = []
    for p in img_root.iterdir():
        if p.is_dir() and any(p.glob("*.jpg")) or any(p.glob("*.png")):
            subdirs_with_imgs.append(p)
    if not subdirs_with_imgs:
        # Khong co subfolder co anh -> dung chinh img/
        if any(img_root.glob("*.jpg")) or any(img_root.glob("*.png")):
            return img_root
        return IMG_DIR
    # Sap xep theo thoi gian sua, moi nhat truoc
    subdirs_with_imgs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return subdirs_with_imgs[0]


_ACT_PATTERN = re.compile(r"^(ACT\s+\d+.*)$", re.MULTILINE | re.IGNORECASE)


def split_into_acts(text: str) -> list[tuple[str, str]]:
    """Tach text thanh list (act_title, act_body). Phan truoc ACT 1 la PROLOGUE."""
    matches = list(_ACT_PATTERN.finditer(text))
    if not matches:
        return [("FULL", text.strip())]

    parts: list[tuple[str, str]] = []
    first_start = matches[0].start()
    prologue = text[:first_start].strip()
    if prologue:
        parts.append(("PROLOGUE", prologue))

    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        parts.append((title, body))

    return parts


# Cac dong can loai bo (metadata va section headers)
SKIP_PREFIXES = (
    "FULL SCRIPT", "TOPIC:", "TARGET:", "IMAGE COUNT",
    "TITLE:", "HOOK", "STORY BEATS",
)
SKIP_NUMERIC_BEATS = re.compile(r"^\d{2}\.\s")


def clean_act_body(body: str) -> str:
    """Don dep text cho TTS."""
    lines = []
    for line in body.splitlines():
        s = line.strip()
        if not s:
            continue
        if set(s) <= {"="}:
            continue
        if any(s.startswith(p) for p in SKIP_PREFIXES):
            continue
        if SKIP_NUMERIC_BEATS.match(s):
            continue
        # Chuan hoa ky tu dac biet
        s = s.replace("—", "-").replace("–", "-").replace("…", "...")
        s = s.replace("�", "")
        # Chi giu ky tu ASCII (bo diacritics)
        s = re.sub(r"[^\x00-\x7F]+", " ", s)
        s = re.sub(r"-+", "-", s)
        s = re.sub(r"\s+", " ", s).strip()
        if s and s not in ("-", "."):
            lines.append(s)
    return " ".join(lines)


def list_images(img_dir: Path | None = None) -> list[Path]:
    """Lay moi file anh trong img_dir, sap xep theo ten (giu ten goc)."""
    target = img_dir or IMG_DIR
    extensions = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    files = [p for p in target.iterdir() if p.is_file() and p.suffix.lower() in extensions]
    # Sap xep theo ten file (giu ten goc nguoi dung)
    return sorted(files, key=lambda p: p.name.lower())


def distribute_images(acts: list[tuple[str, str]], images: list[Path]) -> list[tuple[str, list[str], list[Path]]]:
    cleaned = [(title, clean_act_body(body)) for title, body in acts]
    cleaned = [(t, b) for t, b in cleaned if b]
    n_imgs = len(images)
    scene_distribution: list[tuple[str, list[str], list[Path]]] = []
    img_idx = 0
    chunk_size = 35  # ~35 tu / scene (~15s audio)

    for title, body in cleaned:
        words = body.split()
        if not words:
            continue
        chunks = [words[i:i + chunk_size] for i in range(0, len(words), chunk_size)]
        act_imgs = []
        for _ in chunks:
            act_imgs.append(images[img_idx % n_imgs])
            img_idx += 1
        scene_distribution.append((title, [" ".join(c) for c in chunks], act_imgs))

    return scene_distribution


def write_script(scene_distribution: list[tuple[str, list[str], list[Path]]]) -> Path:
    lines = []
    for title, chunks, imgs in scene_distribution:
        lines.append(f"# {title}")
        for chunk, img in zip(chunks, imgs):
            lines.append(f"[{img.name}] {chunk}")
        lines.append("")
    OUT_SCRIPT.parent.mkdir(parents=True, exist_ok=True)
    OUT_SCRIPT.write_text("\n".join(lines), encoding="utf-8")
    return OUT_SCRIPT


def copy_images_to_input(images: list[Path]) -> None:
    OUT_IMAGES.mkdir(parents=True, exist_ok=True)
    for f in OUT_IMAGES.iterdir():
        if f.is_file():
            f.unlink()
    for img in images:
        target = OUT_IMAGES / img.name
        target.write_bytes(img.read_bytes())


def main() -> None:
    parser = argparse.ArgumentParser(description="Chuan bi script.txt va anh input cho pipeline.")
    parser.add_argument(
        "script",
        nargs="?",
        default=None,
        help="Duong dan toi file kich ban (.txt). Mac dinh: kịch bản/kịch bản.txt",
    )
    args = parser.parse_args()

    script_path = Path(args.script) if args.script else DEFAULT_SCRIPT
    if not script_path.is_file():
        raise SystemExit(f"Khong tim thay file kich ban: {script_path}")

    img_dir = resolve_image_dir()
    print(f"[parse] Tach kich ban: {script_path}")
    raw = script_path.read_text(encoding="utf-8")
    acts = split_into_acts(raw)
    print(f"[parse] Tach duoc {len(acts)} phan (prologue + acts)")

    images = list_images(img_dir)
    print(f"[images] {len(images)} anh trong {img_dir}")

    scene_distribution = distribute_images(acts, images)
    total_scenes = sum(len(c) for _, c, _ in scene_distribution)
    print(f"[scenes] Tong {total_scenes} scene duoc tao")

    script_path = write_script(scene_distribution)
    print(f"[script] Da ghi: {script_path}")

    used_imgs = {img for _, _, imgs in scene_distribution for img in imgs}
    copy_images_to_input(list(used_imgs))
    print(f"[copy] Da copy {len(used_imgs)} anh vao {OUT_IMAGES}")


if __name__ == "__main__":
    main()
