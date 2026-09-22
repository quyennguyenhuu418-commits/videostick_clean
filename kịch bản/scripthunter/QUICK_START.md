# HUONG DAN NHANH - ScriptHunter

## 5 Phut Setup

### 1. Install (lan dau)
```bash
cd "d:/videostick/kịch bản/scripthunter"
pip install apscheduler colorama requests beautifulsoup4 lxml
```

### 2. Chay ngay (khong can internet)
```bash
python main.py --scrape --demo --duration 12 --max-scripts 3
```

### 3. Xem ket qua
```bash
python main.py --review
python main.py --stats
```

### 4. Export script de quay
```bash
python main.py --export 1 --format txt
```

## CAC LENH THUONG DUNG

### Hang ngay
```bash
# Chay auto voi Reddit (can internet)
python main.py --scrape --platforms reddit --duration 12 --max-scripts 5

# Khong co internet?
python main.py --scrape --demo --duration 12 --max-scripts 5
```

### Loc niche
```bash
python main.py --scrape --niches true_crime --duration 12
python main.py --scrape --niches what_if science_explained --duration 15
```

### Tu dong chay
```bash
# Windows Task Scheduler (khuyen nghi)
python main.py --setup --time 08:00 14:00 20:00

# Hoac APScheduler (dev mode)
python main.py --cron --time 08:00 20:00
```

## LICH TRINH KHUYEN NGHI

### Tuan 1: Discovery (thu data that)
```bash
# Moi ngay scrape 1 lan, xem co gi hot
python main.py --scrape --platforms reddit --duration 12 --max-scripts 10

# Review nhanh
python main.py --review
python main.py --stats
```

### Tuan 2: Validate niche
```bash
# Test rieng tung niche
python main.py --scrape --niches what_if --duration 12 --max-scripts 5
python main.py --scrape --niches true_crime --duration 12 --max-scripts 5
python main.py --scrape --niches ai_workflows --duration 12 --max-scripts 5

# Xem cai nao co nhieu trends nhat
python main.py --stats
```

### Tuan 3+: Tu dong hoa
```bash
# Setup 3 lan/ngay
python main.py --setup --time 08:00 14:00 20:00

# Moi ngay chi can
python main.py --review
python main.py --export <id>
```

## NICHES DE BAT DAU

### Top 3 de bat dau:
1. **what_if** (90% viral) - "What if X?" videos
2. **science_explained** (80% viral) - Khoa hoc giai thich
3. **ai_workflows** (85% viral) - AI tools tutorials

### Tranh lam truoc (saturated):
- Generic recipes
- Generic fitness
- Daily vlogs khong co goc nhin doc dao

## VIDEO TIEP THEO SAU SCRIPTHUNTER

```bash
# Co kich ban o: kịch bản/scripthunter/scripts/exported/script_X.txt
# Buoc 1: Chuan bi assets (hinh, audio)
cd d:/videostick
python prepare_input.py "kịch bản/scripthunter/scripts/exported/script_X.txt"

# Buoc 2: Render video
python pipeline.py

# Video output: d:/videostick/output/
```

## TROUBLESHOOTING NHANH

### Loi 403 Reddit
Tool da fallback sang old.reddit.com. Neu van loi, su dung `--demo`.

### Loi Unicode
Da force UTF-8. Neu van loi tren Windows:
```powershell
chcp 65001
```

### Khong co scripts
```bash
# Kiem tra trends
python main.py --stats

# Tao them
python main.py --scrape --demo --max-scripts 10
```

## XEM THEM

- `README.md` - Huong dan day du
- `config.py` - Cau hinh chi tiet
- `data/scripthunter.db` - Database
