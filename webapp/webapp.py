"""VideoStick WebApp - Flask server cho render video qua giao dien web."""

from __future__ import annotations

import logging
import os
import random
import shutil
import string
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, Generator, Optional

import yaml
from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
)
from werkzeug.utils import secure_filename

# ---------- App setup ----------

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["UPLOAD_FOLDER"] = "webapp/uploads"
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200 MB

# ---------- Logging ----------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("webapp")


# ---------- Helpers ----------

def generate_session_id() -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=8))


def allowed_file(filename: str) -> bool:
    allowed = {".txt", ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".mp3", ".wav", ".m4a"}
    return any(filename.lower().endswith(ext) for ext in allowed)


def render_progress(session_id: str) -> Generator[Dict[str, Any], None, None]:
    """Yield SSE progress events from the pipeline log file."""
    project_root = Path(__file__).resolve().parent.parent
    log_file = project_root / "logs" / f"webapp_{session_id}.log"

    # Wait for pipeline to start writing
    for _ in range(30):
        if log_file.exists():
            break
        time.sleep(0.5)

    if not log_file.exists():
        yield {"type": "error", "message": "Pipeline khong khoi dong duoc."}
        return

    # Track file position
    pos = 0
    steps = [
        "Parse kich ban",
        "Giai quyet duong dan anh",
        "Tinh thoi luong scene",
        "Sinh giong doc",
        "Sinh subtitle",
        "Background music",
        "Render video",
        "HOAN THANH",
    ]

    for _ in range(600):  # max 5 minutes
        if log_file.exists():
            try:
                text = log_file.read_text(encoding="utf-8", errors="ignore")
                lines = text.splitlines()

                # Estimate progress
                progress = 5
                for line in lines:
                    for i, step in enumerate(steps):
                        if step in line:
                            progress = int((i + 1) / len(steps) * 100)
                            break

                # Find last non-empty line for detail
                detail = ""
                for line in reversed(lines):
                    stripped = line.strip()
                    if stripped and not stripped.startswith("="):
                        detail = stripped[-200:]
                        break

                yield {"type": "progress", "percent": progress, "detail": detail}

                if "HOAN THANH" in text:
                    # Extract output path
                    for line in lines:
                        if "Video:" in line and ".mp4" in line:
                            parts = line.split("Video:")
                            if len(parts) > 1:
                                path_part = parts[1].strip()
                                # Extract just the filename
                                for part in path_part.split():
                                    if ".mp4" in part:
                                        yield {"type": "complete", "filename": Path(part).name}
                                        break
                    yield {"type": "complete", "percent": 100}
                    return

                if "LOI" in text or "[ERROR]" in text or "[LOI]" in text.upper():
                    for line in reversed(lines):
                        if "LOI" in line or "ERROR" in line or "[LOI]" in line.upper():
                            yield {"type": "error", "message": line.strip()[-300:]}
                            return

            except Exception:
                pass

        time.sleep(1.0)

    yield {"type": "error", "message": "Timeout: pipeline chay qua 5 phut."}


# ---------- Routes ----------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/config", methods=["GET"])
def get_config():
    """Tra ve config hien tai de dien vao form."""
    project_root = Path(__file__).resolve().parent.parent
    cfg_path = project_root / "config.yaml"
    if cfg_path.exists():
        with cfg_path.open("r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    else:
        cfg = {}

    return jsonify({
        "tts": cfg.get("tts", {}),
        "render": cfg.get("render", {}),
        "subtitle": cfg.get("subtitle", {}),
        "color_grading": cfg.get("color_grading", {}),
        "ken_burns": cfg.get("ken_burns", {}),
        "music": cfg.get("music", {}),
        "timing": cfg.get("timing", {}),
        "active_preset": cfg.get("active_preset", "axen"),
        # Voice metadata
        "voice_options": {
            "piper": _list_piper_voices(),
            "kokoro": _list_kokoro_voices(),
        },
        "engine_available": {
            "piper": _is_piper_available(),
            "kokoro": _is_kokoro_available(),
        },
    })


def _list_piper_voices() -> list:
    """Quet assets/voices/ tra ve cac piper voice co san."""
    project_root = Path(__file__).resolve().parent.parent
    voice_dir = project_root / "assets" / "voices"
    if not voice_dir.is_dir():
        return []
    out = []
    for p in sorted(voice_dir.glob("*.onnx")):
        if p.is_file():
            out.append(p.stem.replace(".onnx", ""))
    return out


def _list_kokoro_voices() -> list:
    """Tra ve danh sach Kokoro voices co trong model (neu model da download)."""
    try:
        from src.tts_kokoro import KOKORO_VOICES
        return [{"id": k, "desc": v} for k, v in KOKORO_VOICES.items()]
    except Exception:
        return []


def _is_piper_available() -> bool:
    try:
        import piper  # noqa: F401
        return True
    except ImportError:
        return False


def _is_kokoro_available() -> bool:
    try:
        from src.tts_kokoro import is_kokoro_available
        return is_kokoro_available()
    except Exception:
        return False


@app.route("/api/save-config", methods=["POST"])
def save_config():
    """Luu config tu form len config.yaml."""
    data = request.get_json() or {}
    project_root = Path(__file__).resolve().parent.parent
    cfg_path = project_root / "config.yaml"

    # Read existing config
    if cfg_path.exists():
        with cfg_path.open("r", encoding="utf-8") as f:
            existing = yaml.safe_load(f) or {}
    else:
        existing = {}

    # Merge updated sections
    for section in ["tts", "render", "subtitle", "color_grading", "ken_burns", "music", "timing"]:
        if section in data:
            if section not in existing:
                existing[section] = {}
            existing[section].update(data[section])

    if "active_preset" in data:
        existing["active_preset"] = data["active_preset"]

    # Write back
    with cfg_path.open("w", encoding="utf-8") as f:
        yaml.dump(existing, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    return jsonify({"ok": True})


@app.route("/api/render", methods=["POST"])
def start_render():
    """Bat dau render: copy file va goi pipeline."""
    session_id = generate_session_id()
    project_root = Path(__file__).resolve().parent.parent
    uploads_dir = Path(app.config["UPLOAD_FOLDER"])
    uploads_dir.mkdir(parents=True, exist_ok=True)

    # Clear uploads
    for f in uploads_dir.iterdir():
        try:
            f.unlink()
        except OSError:
            pass

    # Save uploaded files
    images_dir = uploads_dir / "images"
    images_dir.mkdir(exist_ok=True)

    script_file = uploads_dir / "script.txt"
    music_file: Optional[Path] = None

    # Handle multipart form
    files = request.files
    form = request.form

    # Script text
    script_text = form.get("script_text", "").strip()
    if script_text:
        script_file.write_text(script_text, encoding="utf-8")
    elif "script_file" in files:
        f = files["script_file"]
        if f and f.filename and allowed_file(f.filename):
            script_file.write_bytes(f.read())

    # Images
    image_files = [files[k] for k in files if k.startswith("image_")]
    for idx, f in enumerate(image_files, 1):
        if f and f.filename and allowed_file(f.filename):
            ext = Path(secure_filename(f.filename)).suffix or ".jpg"
            dest = images_dir / f"Scene_{idx:03d}_1080p{ext}"
            f.save(str(dest))

    # Music
    if "music_file" in files:
        mf = files["music_file"]
        if mf and mf.filename and allowed_file(mf.filename):
            ext = Path(secure_filename(mf.filename)).suffix or ".mp3"
            music_file = uploads_dir / f"uploaded_music{ext}"
            mf.save(str(music_file))
            # Copy to assets/music
            assets_music = project_root / "assets" / "music"
            assets_music.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(music_file), str(assets_music / music_file.name))

    # Update config to point to webapp uploads
    cfg_path = project_root / "config.yaml"
    if cfg_path.exists():
        with cfg_path.open("r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    else:
        cfg = {}

    cfg["paths"] = {
        "input_images": str(uploads_dir / "images"),
        "input_script": str(script_file),
        "output_dir": str(project_root / "output"),
        "temp_dir": str(project_root / "temp"),
        "logs_dir": str(project_root / "logs"),
        "music_dir": str(project_root / "assets" / "music"),
    }

    # Apply form overrides
    tts_cfg = cfg.get("tts", {})

    # Engine selection (piper | kokoro)
    engine_val = form.get("tts_engine", "").strip().lower()
    if engine_val in ("piper", "kokoro"):
        tts_cfg["engine"] = engine_val

    for k in ["voice_model", "language", "speed", "pitch_shift", "speaker"]:
        if form.get(k):
            tts_cfg[k] = float(form[k]) if k in ("speed", "pitch_shift", "speaker") else form[k]

    # Kokoro-specific overrides
    kokoro_cfg = tts_cfg.get("kokoro", {})
    for k in ["voice", "speed", "lang"]:
        form_key = f"kokoro_{k}"
        if form.get(form_key):
            val = form[form_key]
            if k == "speed":
                val = float(val)
            kokoro_cfg[k] = val
    tts_cfg["kokoro"] = kokoro_cfg

    cfg["tts"] = tts_cfg

    sub_cfg = cfg.get("subtitle", {})
    for k in ["font_size", "position", "burn_in"]:
        if form.get(k):
            val = form[k]
            if k == "burn_in":
                val = val.lower() in ("true", "1", "yes")
            elif k == "font_size":
                val = int(val)
            sub_cfg[k] = val
    cfg["subtitle"] = sub_cfg

    render_cfg = cfg.get("render", {})
    for k in ["fps", "crf", "preset", "width", "height"]:
        if form.get(k):
            val = form[k]
            if k in ("fps", "crf", "width", "height"):
                val = int(val)
            render_cfg[k] = val
    cfg["render"] = render_cfg

    music_cfg = cfg.get("music", {})
    music_cfg["enabled"] = form.get("music_enabled", "false").lower() in ("true", "1", "yes")
    music_cfg["volume"] = float(form.get("music_volume", "0.18"))
    cfg["music"] = music_cfg

    timing_cfg = cfg.get("timing", {})
    for k in ["words_per_minute", "min_scene_duration", "max_scene_duration"]:
        if form.get(k):
            timing_cfg[k] = float(form[k]) if k != "words_per_minute" else int(form[k])
    cfg["timing"] = timing_cfg

    # Save temp config
    temp_cfg_path = project_root / "webapp_render.yaml"
    with temp_cfg_path.open("w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    # Start pipeline in background thread
    log_file = project_root / "logs" / f"webapp_{session_id}.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    def run_pipeline():
        env = os.environ.copy()
        env["PYTHONPATH"] = str(project_root)
        try:
            result = subprocess.run(
                [sys.executable, "pipeline.py", "webapp_render.yaml", "--preset", "axen"],
                cwd=str(project_root),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            with log_file.open("a", encoding="utf-8") as lf:
                lf.write(result.stdout)
                if result.returncode != 0:
                    lf.write(f"\n[LOI] Exit code: {result.returncode}\n")
                else:
                    lf.write("\nHOAN THANH\n")
        except Exception as e:
            with log_file.open("a", encoding="utf-8") as lf:
                lf.write(f"\n[LOI] Exception: {e}\n")

    thread = threading.Thread(target=run_pipeline, daemon=True)
    thread.start()

    return jsonify({"session_id": session_id, "ok": True})


@app.route("/api/progress/<session_id>")
def progress(session_id: str):
    """Server-Sent Events stream cho progress."""
    def generate():
        for event in render_progress(session_id):
            yield f"data: {event}\n\n"

    from flask import Response
    return Response(generate(), mimetype="text/event-stream")


@app.route("/api/outputs", methods=["GET"])
def list_outputs():
    """Tra ve danh sach video da render."""
    project_root = Path(__file__).resolve().parent.parent
    output_dir = project_root / "output"
    output_dir.mkdir(exist_ok=True)

    files = []
    for f in sorted(output_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True):
        files.append({
            "name": f.name,
            "size": f.stat().st_size,
            "modified": f.stat().st_mtime,
        })

    return jsonify({"files": files})


@app.route("/api/download/<path:filename>")
def download(filename: str):
    """Download video."""
    project_root = Path(__file__).resolve().parent.parent
    return send_from_directory(str(project_root / "output"), filename, as_attachment=True)


@app.route("/api/preview/<path:filename>")
def preview(filename: str):
    """Preview video stream."""
    project_root = Path(__file__).resolve().parent.parent
    return send_from_directory(str(project_root / "output"), filename)


@app.route("/api/cleanup", methods=["POST"])
def cleanup():
    """Xoa tat ca file tam va video output."""
    project_root = Path(__file__).resolve().parent.parent

    dirs_to_clean = [
        project_root / "temp",
        project_root / "webapp" / "uploads",
    ]

    count = 0
    for d in dirs_to_clean:
        if d.exists():
            for f in d.iterdir():
                try:
                    f.unlink()
                    count += 1
                except OSError:
                    pass

    # Clean output
    output_dir = project_root / "output"
    if output_dir.exists():
        for f in output_dir.glob("*.mp4"):
            try:
                f.unlink()
                count += 1
            except OSError:
                pass

    return jsonify({"ok": True, "cleaned": count})


@app.route("/api/ping", methods=["GET"])
def ping():
    return jsonify({"ok": True, "version": "1.0.0"})


# ---------- Entry point ----------

if __name__ == "__main__":
    # Check prerequisites
    project_root = Path(__file__).resolve().parent.parent
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        log.warning("ffmpeg not found in PATH. Audio processing may fail.")

    piper_ok = False
    try:
        import piper
        piper_ok = True
    except ImportError:
        log.warning("piper-tts not installed. TTS will generate silence.")

    log.info("Starting VideoStick WebApp on http://127.0.0.1:5555")
    log.info("  ffmpeg: %s", ffmpeg_path or "NOT FOUND")
    log.info("  piper:  %s", "OK" if piper_ok else "NOT INSTALLED (silence fallback)")

    app.run(host="127.0.0.1", port=5555, debug=False, threaded=True)
