# VideoStick

Pipeline Python tự động render video storytelling từ ảnh + kịch bản — phong cách kênh YouTube Adam/AXEN (giọng đọc chậm, ảnh Ken Burns, cinematic color grading, 1080p/24fps).

## Tính năng

- **Tự động ghép ảnh + Ken Burns** — zoom/pan chuyển động mượt trên ảnh tĩnh
- **TTS local** với Piper (giọng Adam-like, nam trầm, tốc độ chậm) — không cần cloud
- **Cinematic color grading** + vignette đúng style storytelling YouTube
- **Subtitles** (.srt) tự động sinh từ kịch bản và timing giọng đọc
- **Background music** ambient/cinematic với fade in/out
- **Xuất MP4 1080p/24fps** chuẩn YouTube

## Cài đặt

### 1. Yêu cầu hệ thống

- Python 3.11+
- FFmpeg trong PATH (tải tại [ffmpeg.org](https://ffmpeg.org/download.html))
- Windows / macOS / Linux
- RAM tối thiểu 8GB

### 2. Cài Python dependencies

```bash
cd d:\videostick
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate    # macOS/Linux
pip install -r requirements.txt
```

### 3. Cài FFmpeg

**Windows:**
- Tải bản build từ [gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/)
- Giải nén và thêm vào PATH, hoặc set `binary` trong `config.yaml` trỏ tới file `ffmpeg.exe`

**macOS:** `brew install ffmpeg`

**Linux:** `sudo apt install ffmpeg`

Kiểm tra:
```bash
ffmpeg -version
```

### 4. Tải Piper Voice Model

Tạo thư mục `assets/voices/` rồi tải voice model Adam-like:

```bash
# Tạo folder
mkdir assets\voices
```

**Voice khuyến nghị (gần giọng Adam nhất có sẵn trong Piper):**

| Voice | Đặc điểm | Download |
|---|---|---|
| **en_US-joe-medium** | Nam trầm, tự nhiên, medium quality (63MB) — khuyến nghị | [onnx](https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/joe/medium/en_US-joe-medium.onnx?download=true) · [json](https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/joe/medium/en_US-joe-medium.onnx.json?download=true) |
| en_US-ryan-medium | Nam trung, rõ ràng (medium) | [onnx](https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/medium/en_US-ryan-medium.onnx?download=true) · [json](https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/medium/en_US-ryan-medium.onnx.json?download=true) |
| en_US-john-medium | Nam trung ấm (medium) | [onnx](https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/john/medium/en_US-john-medium.onnx?download=true) · [json](https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/john/medium/en_US-john-medium.onnx.json?download=true) |
| en_US-hfc_male-medium | Nam trầm từ LJSpeech corpus | [onnx](https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/hfc_male/medium/en_US-hfc_male-medium.onnx?download=true) · [json](https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/hfc_male/medium/en_US-hfc_male-medium.onnx.json?download=true) |

Đặt cả 2 file `.onnx` và `.onnx.json` vào `assets/voices/`. Cập nhật tên file trong `config.yaml` → `tts.voice_model` (bao gồm cả `.onnx`).

> **Tự động tải nhanh (PowerShell):**
> ```powershell
> cd assets\voices
> Invoke-WebRequest -Uri "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/joe/medium/en_US-joe-medium.onnx?download=true" -OutFile "en_US-joe-medium.onnx" -UseBasicParsing
> Invoke-WebRequest -Uri "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/joe/medium/en_US-joe-medium.onnx.json?download=true" -OutFile "en_US-joe-medium.onnx.json" -UseBasicParsing
> ```

> **Lưu ý về Tiếng Việt**: Piper chưa có sẵn model tiếng Việt chất lượng cao. Có thể dùng model tiếng Anh cho kịch bản EN, hoặc tự train model từ [repo Piper](https://github.com/rhasspy/piper). Khi tự train, đặt model vào `assets/voices/` và cập nhật `tts.voice_model`.

> **Lưu ý Windows**: Nếu user folder có dấu/ký tự không ASCII (vd `C:\Users\QUYÊN`), hệ thống sẽ tự động copy espeak-ng-data sang `assets/espeak-ng-data/` để tránh lỗi "Illegal byte sequence".

### 5. Chuẩn bị Background Music

Đặt 1 file nhạc ambient/cinematic (royalty-free) vào `assets/music/`:
- Định dạng: `.mp3` hoặc `.wav`
- Đề xuất: tìm "ambient cinematic background music no copyright" trên YouTube Audio Library hoặc Pixabay
- Đổi tên file thành `ambient_01.mp3` hoặc cập nhật `music.file` trong config

### 6. Chuẩn bị Font (tùy chọn)

Nếu muốn subtitle đẹp, đặt file `.ttf` vào `assets/fonts/`:
- Khuyến nghị: `Inter-Bold.ttf`, `Montserrat-Bold.ttf`, hoặc `BebasNeue-Bold.ttf`
- Tải miễn phí tại Google Fonts

Nếu không có font riêng, hệ thống sẽ dùng font mặc định.

## Sử dụng

### Bước 1 — Chuẩn bị ảnh

Thả tất cả ảnh vào `input/images/`. Đặt tên file theo thứ tự, ví dụ:
```
img_01.jpg
img_02.jpg
img_03.jpg
```

### Bước 2 — Viết kịch bản

Tạo file `input/script.txt` theo format:

```
[img_01.jpg] Có những buổi sáng, bạn thức dậy và cảm thấy mọi thứ thật nặng nề. Giống như gánh trên vai cả một đại dương.
[img_02.jpg] Bạn tự hỏi tại sao người khác lại có thể bước đi nhẹ nhõm đến thế, trong khi mình thì không.
[img_03.jpg] Nhưng sự thật là, không ai sinh ra đã hoàn hảo. Mỗi người đều đang chiến đấu với một cuộc chiến mà bạn không nhìn thấy.
```

Quy tắc:
- Mỗi dòng bắt đầu bằng `[tên_file_ảnh]` rồi đến nội dung
- Tên file phải có trong `input/images/`
- Có thể dùng dấu xuống dòng trong nội dung (sẽ được nối thành 1 đoạn văn)

### Bước 3 — Chạy pipeline

```bash
python pipeline.py
```

Pipeline sẽ tự động:
1. Đọc ảnh + kịch bản
2. Tính timing cho mỗi scene
3. Sinh giọng đọc (Piper TTS)
4. Tạo file .srt cho subtitle
5. Render video với Ken Burns + color grading
6. Ghép voice + music + subtitles
7. Xuất file MP4 vào `output/`

### Bước 4 — Lấy video

File MP4 được lưu tại `output/video_<timestamp>.mp4`. File subtitle đi kèm `output/subtitles.srt`.

## Cấu hình nâng cao

Mọi tham số (resolution, fps, voice, Ken Burns, color grading, music, subtitle) đều chỉnh trong `config.yaml`.

Một số preset hữu ích:

```yaml
# Xuất nhanh (draft)
render:
  preset: "ultrafast"
  crf: 23

# Xuất chất lượng cao
render:
  preset: "slow"
  crf: 16

# Không có music
music:
  enabled: false

# Subtitle xuất riêng (không burn vào video)
subtitle:
  burn_in: false
```

## Cấu trúc dự án

```
videostick/
├── pipeline.py              # Entry point chính
├── config.yaml              # Cấu hình
├── requirements.txt         # Python deps
├── src/
│   ├── scene_segmenter.py   # Parse script.txt
│   ├── timing_estimator.py  # Tính duration
│   ├── tts_engine.py        # Piper TTS
│   ├── subtitle_generator.py# Tạo .srt
│   ├── ken_burns.py         # FFmpeg filter
│   ├── renderer.py          # Render cuối cùng
│   ├── music_manager.py     # Quản lý music
│   └── style_presets.py     # Axen-style preset
├── assets/
│   ├── voices/              # Piper voice models
│   ├── music/               # Background music
│   └── fonts/               # Fonts
├── input/
│   ├── images/              # Ảnh đầu vào
│   └── script.txt           # Kịch bản
├── output/                  # Video xuất ra
├── logs/                    # Log
└── temp/                    # File tạm trong quá trình render
```

## Troubleshooting

### Lỗi "ffmpeg not found"
- Kiểm tra `ffmpeg -version` trong terminal
- Nếu chưa cài, cài theo hướng dẫn ở trên
- Hoặc set đường dẫn tuyệt đối trong `config.yaml` → `ffmpeg.binary`

### Lỗi Piper "model not found"
- Kiểm tra file `.onnx` và `.onnx.json` có trong `assets/voices/`
- Tên file trong config phải khớp (bao gồm cả `.onnx`)
- Voice model phải được load đúng cả 2 file

### Lỗi "Illegal byte sequence" espeak-ng (Windows)
- Xảy ra khi user folder có ký tự Unicode (vd `C:\Users\QUYÊN\`)
- Hệ thống sẽ tự động copy espeak-ng-data sang `assets/espeak-ng-data/`
- Nếu vẫn lỗi, chạy với quyền admin hoặc cài đặt lại Piper

### Lỗi "synthesis" quá chậm
- Medium model ~ 5-6s cho 1 đoạn văn 2-3 câu
- Low model nhanh hơn ~3x nhưng chất lượng kém hơn

### Video render không có tiếng
- Kiểm tra `assets/music/` có file nhạc không
- Hoặc set `music.enabled: false` trong config

### Subtitle bị lệch timing
- Điều chỉnh `tts.speed` trong config (giảm xuống 0.9 nếu đọc nhanh quá)
- Hoặc điều chỉnh `timing.words_per_minute`

### Lỗi "Image not found"
- Kiểm tra tên file trong `script.txt` phải khớp chính xác với file trong `input/images/`
- Đuôi file có phân biệt hoa/thường trên Linux/Mac

## License

MIT
