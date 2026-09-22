# ScriptHunter - Cong Cu Tu Dong Cao Kich Ban Viral

## Tong Quan

ScriptHunter la cong cu Python tu dong:
- **Cao trends** hang ngay tu Reddit (old.reddit.com) va YouTube
- **Phan tich** hook patterns va viral potential
- **Generate** kich ban video 9-15 phut co cau truc chuyen nghiep
- **Chay tu dong** theo lich (Windows Task Scheduler / APScheduler)

## Tai Sao Tool Nay?

**Muc tieu cua ban**: Tim noi dung co kha nang viral, it canh tranh, de hoat dong lau dai.

**Cach giai quyet**:
1. Thu thap data that tu cac nen tang viral (Reddit, YouTube)
2. Diem danh nhung chu de co engagement cao nhat
3. Tom lai thanh kich ban co the quay ngay
4. Luu lai de ban co the tham khao khi can

## Cong Cu Tham Khao Tu GitHub

Tool nay duoc xay dung dua tren cac project GitHub noi tieng:

| Tool | Stars | Hoc duoc gi |
|------|-------|-------------|
| [kastrah/trending-scraper](https://github.com/kastrah/trending-scraper) | 23k+ | Multi-platform scraping pattern |
| [prantikseal/hook-mining-engine](https://github.com/prantikseal/hook-mining-engine) | - | Hook pattern extraction |
| [openclaw-easy/ViralMint](https://github.com/openclaw-easy/ViralMint) | 103 | Trend scoring algorithms |
| [browser-use/video-use](https://github.com/browser-use/video-use) | 23k+ | Video production workflow |
| [Trend2Video-Pro](https://github.com/2417467487-hub/Trend2Video-Pro) | - | Quality review framework |

## Niche Tiem Nang 2026 (It Canh Tranh, Viral Cao)

### Top Niches Da Xac Dinh:

1. **AI Workflows** (85% viral)
   - Huong dan su dung AI cho cong viec cu the
   - Tool reviews, prompts, automation

2. **What-If Scenarios** (90% viral) - **KHUYEN NGHI BAT DAU**
   - Lich su gia dinh
   - Scenario alternate history
   - De tao content, kha nang viral cuc cao

3. **True Crime / Mystery** (85% viral)
   - Vu an lanh giong, bien mat
   - Investigation deep-dives

4. **Micro-Documentary** (80% viral)
   - Deep dives 60s vao topic hiem
   - Su kien it nguoi biet

5. **Engineering Fails** (75% viral)
   - Phan tich that bai ki thuat
   - Bai hoc tu disaster

6. **Paradoxes** (85% viral)
   - Nghi ly logic
   - Time travel, physics

7. **Science Explained** (80% viral)
   - Giai thich khoa hoc don gian
   - Discovery, phenomenon

## Cai Dat

### Buoc 1: Install dependencies
```bash
cd "d:/videostick/kịch bản/scripthunter"
pip install apscheduler colorama requests beautifulsoup4 lxml
```

### Buoc 2: (Optional) Setup Reddit API
Dat environment variables cho PRAW (de lay nhieu data hon):
```powershell
$env:REDDIT_CLIENT_ID = "your_client_id"
$env:REDDIT_CLIENT_SECRET = "your_client_secret"
$env:REDDIT_USER_AGENT = "ScriptHunter/1.0"
```

Lay credentials tai: https://www.reddit.com/prefs/apps

### Buoc 3: (Optional) Setup YouTube API
Dat environment variable:
```powershell
$env:YOUTUBE_API_KEY = "your_api_key"
```

## Cach Su Dung

### 1. Chay Demo (khong can internet)
```bash
python main.py --scrape --demo --duration 12 --max-scripts 3
```

### 2. Chay Thuc (can internet)
```bash
# Chi scrape (khong generate scripts)
python main.py --scrape --platforms reddit --no-generate

# Scrape va generate scripts 12 phut
python main.py --scrape --platforms reddit --duration 12 --max-scripts 5

# Nhieu platforms
python main.py --scrape --platforms reddit youtube --duration 10
```

### 3. Loc Theo Niche
```bash
python main.py --scrape --niches true_crime what_if --duration 15
```

### 4. Review & Export
```bash
# Xem cac scripts da generate
python main.py --review

# Export script ID 1 ra file txt
python main.py --export 1 --format txt

# Export JSON
python main.py --export 1 --format json
```

### 5. Xem Thong Ke
```bash
python main.py --stats
python main.py --niches-list
```

### 6. Setup Tu Dong Chay Hang Ngay

**Cach A: APScheduler (nen dung khi dev)**
```bash
python main.py --cron --time 08:00 14:00 20:00
```

**Cach B: Windows Task Scheduler (khuyen nghi cho production)**
```bash
python main.py --setup --time 08:00 14:00 20:00
```

## Cau Truc Output

Moi kich ban duoc generate co:
- **Hook**: Cau mo dau manh (~100 ky tu)
- **5 sections** voi duration cu the:
  - INTRO (10% - 72s)
  - CONTEXT (15% - 108s)
  - DEVELOPMENT (50% - 360s)
  - CLIMAX (15% - 108s)
  - OUTRO (10% - 72s)
- **Cue points** cho editing
- **Visual notes** cho visual production
- **Tags** cho SEO

## Workflow De Thanh Cong

### Tuan 1: Discovery
```bash
# Chay hang ngay voi demo + real data
python main.py --scrape --platforms reddit --duration 10
python main.py --scrape --demo --duration 10

# Review cac scripts
python main.py --review
python main.py --stats
```

### Tuan 2-4: Validate Niche
- Dat min-viral cao (0.5-0.7) de chi lay top trends
- Xem `top_trends` de biet niche nao dang hot
- Loc theo niche cu the de test tung cai

```bash
# Test true_crime
python main.py --scrape --niches true_crime --duration 12 --max-scripts 5

# Test what_if
python main.py --scrape --niches what_if --duration 12 --max-scripts 5
```

### Sau 1 Thang: Tu Dong Hoa
```bash
# Setup tu chay 3 lan/ngay
python main.py --setup --time 08:00 14:00 20:00

# Moi ngay chi can:
python main.py --review
python main.py --export <script_id>
```

## Tan So Chay

| Tan suat | Use case |
|----------|----------|
| 1 lan/ngay (8h sang) | Bat dau, it data |
| 2 lan/ngay (8h, 20h) | Trung binh |
| 3 lan/ngay (8h, 14h, 20h) | Nhieu niches (khuyen nghi) |
| Moi 6h | Max coverage |

## Luu Y Quan Trong

### 1. Chat Luong Hon So Luong
- Khong can tao 10 scripts/ngay neu khong quay noi
- Tao 2-3 scripts tot hang ngay con hon 10 scripts te

### 2. Validate Script
Moi script can kiem tra:
- [ ] Co hook manh trong 30 giay dau?
- [ ] Co insight moi so voi content khac?
- [ ] Co y tuong visual ro rang?
- [ ] Co the quay trong 1-2 ngay?

### 3. Niches De Bat Dau
**KHUYEN NGHI BAT DAU**:
1. **what_if** - viral 90%, content de tao, infinite ideas
2. **science_explained** - 80%, evergreen, moi tuyen
3. **ai_workflows** - 85%, demand cao, high CPM

### 4. Niches NEN TRANGH Ban Dau
- Faceless/cash cow (saturation 96.9%)
- Generic fitness (low outlier rate)
- Standard recipes (saturated)

## Troubleshooting

### Loi 403 tu Reddit
Tool da co fallback sang `old.reddit.com`. Neu van loi:
1. Set PRAW credentials (xem Cai Dat buoc 2)
2. Hoac su dung `--demo` de test

### Loi Unicode
Tool da force UTF-8. Neu PowerShell loi:
```powershell
chcp 65001
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```

### Khong co data
```bash
# Chay demo truoc
python main.py --scrape --demo

# Kiem tra stats
python main.py --stats
```

## Files Trong Thu Muc

```
scripthunter/
├── main.py                  # Entry point chinh
├── config.py                # Cau hinh (niches, schedule, etc.)
├── database.py              # SQLite database
├── analyzer.py              # Hook analyzer
├── script_generator.py      # Script generation
├── scheduler.py             # Cron job scheduler
├── demo_data.py             # Demo data generator
├── scrapers/
│   ├── reddit_scraper.py    # Reddit scraper (PRAW + old.reddit)
│   └── youtube_scraper.py   # YouTube scraper
├── data/
│   └── scripthunter.db      # Database
├── scripts/
│   └── exported/            # Scripts da export
├── logs/
│   └── scripthunter.log     # Logs
├── cache/                   # Cache
└── README.md
```

## Tiep Theo Sau Khi Co Kich Ban

Khi ban da co kich ban, su dung cac tool co san trong project:

```bash
cd d:/videostick

# Buoc 1: Chuan bi input (text, images, audio)
python prepare_input.py "kịch bản/scripthunter/scripts/exported/script_X.txt"

# Buoc 2: Chay pipeline de tao video
python pipeline.py

# Video output se o thu muc output/
```

## Thong Tin Them

### Hook Patterns Hoat Dong Tot
- **Mystery**: "Nobody knows why..."
- **Curiosity Gap**: "The thing they don't want you to know"
- **Contrarian**: "Stop doing X, here's why"
- **Shocking Stat**: "90% of people don't know this"

### Viral Score Formula
- Score 0.8+: Top tier, uu tien lam truoc
- Score 0.5-0.8: Tot, lam khi co thoi gian
- Score <0.5: Trung binh, skip

### Database Schema
- `trends`: Tat ca trends da thu thap
- `scripts`: Tat ca scripts da generate
- `niches`: 10 niches duoc cau hinh
- `execution_log`: Log cac lan chay

---

**Nguoi tao**: ScriptHunter v1.0
**Ngay tao**: Sep 2026
**License**: MIT
