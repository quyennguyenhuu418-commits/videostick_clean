"""Tao file SRT chuan YouTube tu file SRT hien co.

Doc file SRT da sinh, sua lai format timestamp cho dung chuan SubRip,
va ghi ra file moi de upload YouTube.

YouTube SRT format:
    00:00:00,000 --> 00:00:02,510
    Text here
"""

import re
import sys
from pathlib import Path


def _fix_timestamp(ts: str) -> str:
    """Chuyen timestamp tu format ASS (H:MM:SS.cc) sang SRT chuan (HH:MM:SS,mmm).
    
    Input co the la:
        0:00:00.00  (ASS centisecond)
        0:00:39.100 (bug: 3 digits)
    """
    ts = ts.strip()
    
    # Parse flexible: H:MM:SS.fractional
    m = re.match(r"(\d+):(\d{2}):(\d{2})\.(\d+)", ts)
    if not m:
        return ts  # tra lai nguyen neu khong parse duoc
    
    hh = int(m.group(1))
    mm = int(m.group(2))
    ss = int(m.group(3))
    frac_str = m.group(4)
    
    # Chuyen fractional part thanh milliseconds
    if len(frac_str) == 2:
        # centiseconds -> milliseconds
        millis = int(frac_str) * 10
    elif len(frac_str) == 3:
        millis = int(frac_str)
    else:
        # normalize
        millis = int(float(f"0.{frac_str}") * 1000)
    
    return f"{hh:02d}:{mm:02d}:{ss:02d},{millis:03d}"


def convert_srt(input_path: Path, output_path: Path) -> None:
    """Doc file SRT hien co va ghi lai voi timestamp chuan YouTube."""
    content = input_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    
    output_lines = []
    for line in lines:
        # Tim dong timestamp: "H:MM:SS.cc --> H:MM:SS.cc"
        m = re.match(r"^(\d+:\d{2}:\d{2}\.\d+)\s*-->\s*(\d+:\d{2}:\d{2}\.\d+)$", line.strip())
        if m:
            start = _fix_timestamp(m.group(1))
            end = _fix_timestamp(m.group(2))
            output_lines.append(f"{start} --> {end}")
        else:
            output_lines.append(line.rstrip('\r'))
    
    # Ghi file voi BOM UTF-8 (YouTube khuyen dung)
    output_path.write_text("\n".join(output_lines) + "\n", encoding="utf-8-sig")
    print(f"Da ghi: {output_path}")
    print(f"So dong: {len(output_lines)}")


if __name__ == "__main__":
    project = Path(__file__).resolve().parent
    input_srt = project / "output" / "subtitles.srt"
    output_srt = project / "output" / "subtitles_youtube.srt"
    
    if not input_srt.exists():
        print(f"Khong tim thay: {input_srt}", file=sys.stderr)
        sys.exit(1)
    
    convert_srt(input_srt, output_srt)
    
    # In 10 dong dau de kiem tra
    preview = output_srt.read_text(encoding="utf-8-sig").splitlines()[:20]
    print("\n--- Preview ---")
    for l in preview:
        print(l)
