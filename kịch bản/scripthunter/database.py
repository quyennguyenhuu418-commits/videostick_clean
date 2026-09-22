"""
Database Module - ScriptHunter
Manage storage of trends, scripts and metadata
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import DB_PATH


@dataclass
class Trend:
    """Represents a trending topic/content"""
    id: Optional[int] = None
    platform: str = ""
    source_id: str = ""
    title: str = ""
    content: str = ""
    url: str = ""
    author: str = ""
    score: int = 0
    comments: int = 0
    views: int = 0
    engagement_rate: float = 0.0
    viral_score: float = 0.0
    hook_type: str = ""
    niche: str = ""
    tags: str = ""
    created_at: str = ""
    fetched_at: str = ""
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class Script:
    """Represents a generated script"""
    id: Optional[int] = None
    trend_id: Optional[int] = None
    title: str = ""
    duration_minutes: int = 0
    hook: str = ""
    content: str = ""
    structure: str = ""
    tags: str = ""
    status: str = "draft"
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""
    viral_score: float = 0.0
    quality_score: float = 0.0
    
    def to_dict(self) -> Dict:
        return asdict(self)


class Database:
    """Database manager for ScriptHunter"""
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self):
        """Initialize database tables"""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trends (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    source_id TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT,
                    url TEXT,
                    author TEXT,
                    score INTEGER DEFAULT 0,
                    comments INTEGER DEFAULT 0,
                    views INTEGER DEFAULT 0,
                    engagement_rate REAL DEFAULT 0.0,
                    viral_score REAL DEFAULT 0.0,
                    hook_type TEXT,
                    niche TEXT,
                    tags TEXT,
                    created_at TEXT,
                    fetched_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(platform, source_id)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scripts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trend_id INTEGER,
                    title TEXT NOT NULL,
                    duration_minutes INTEGER DEFAULT 10,
                    hook TEXT,
                    content TEXT,
                    structure TEXT,
                    tags TEXT,
                    status TEXT DEFAULT 'draft',
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    viral_score REAL DEFAULT 0.0,
                    quality_score REAL DEFAULT 0.0,
                    FOREIGN KEY (trend_id) REFERENCES trends(id)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS niches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    keywords TEXT,
                    min_competition REAL DEFAULT 0.0,
                    viral_potential REAL DEFAULT 0.0,
                    last_checked TEXT,
                    is_active INTEGER DEFAULT 1
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS execution_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_type TEXT,
                    platforms TEXT,
                    trends_found INTEGER DEFAULT 0,
                    scripts_generated INTEGER DEFAULT 0,
                    status TEXT,
                    error_message TEXT,
                    started_at TEXT,
                    completed_at TEXT
                )
            """)
            
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trends_platform ON trends(platform)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trends_viral ON trends(viral_score DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trends_niche ON trends(niche)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_scripts_status ON scripts(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_scripts_viral ON scripts(viral_score DESC)")
            
            niches = [
                ("true_crime", "True crime and unsolved mysteries", "mystery,crime,unsolved,detective,investigation", 0.85),
                ("micro_documentary", "60-second deep dives into obscure topics", "history,science,facts,deep dive,explained", 0.80),
                ("what_if", "Historical and hypothetical scenarios", "what if,alternate history,hypothetical,imagine", 0.90),
                ("engineering_fails", "Engineering failures and lessons", "engineering,disaster,failure,collapse,lesson", 0.75),
                ("ai_workflows", "AI tool tutorials and workflows", "AI,automation,productivity,tool,tutorial", 0.85),
                ("senior_tech", "Technology for older audiences", "seniors,elderly,technology,smartphone,tutorial", 0.70),
                ("village_cooking", "Slow living and village cooking", "village,cooking,traditional,slow living,recipe", 0.80),
                ("paradoxes", "Mind-bending paradoxes and puzzles", "paradox,mystery,puzzle,riddle,thinking", 0.85),
                ("anime_analysis", "Anime and game alternate theories", "anime,theory,alternate,game,fandom", 0.75),
                ("science_explained", "Complex science made simple", "science,physics,biology,explained,discovery", 0.80),
            ]
            
            for niche in niches:
                conn.execute(
                    "INSERT OR IGNORE INTO niches (name, description, keywords, viral_potential) VALUES (?, ?, ?, ?)",
                    niche
                )
            
            conn.commit()
    
    def save_trend(self, trend: Trend) -> int:
        """Save or update a trend"""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT OR REPLACE INTO trends 
                (platform, source_id, title, content, url, author, score, comments, views,
                 engagement_rate, viral_score, hook_type, niche, tags, created_at, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trend.platform, trend.source_id, trend.title, trend.content, trend.url,
                trend.author, trend.score, trend.comments, trend.views, trend.engagement_rate,
                trend.viral_score, trend.hook_type, trend.niche, trend.tags, 
                trend.created_at, datetime.now().isoformat()
            ))
            conn.commit()
            return cursor.lastrowid
    
    def get_trends(
        self, 
        platform: Optional[str] = None,
        niche: Optional[str] = None,
        min_viral: float = 0.0,
        limit: int = 50,
        days_back: int = 7
    ) -> List[Trend]:
        """Get trends with filters"""
        query = "SELECT * FROM trends WHERE 1=1"
        params = []
        
        if platform:
            query += " AND platform = ?"
            params.append(platform)
        if niche:
            query += " AND niche = ?"
            params.append(niche)
        if min_viral > 0:
            query += " AND viral_score >= ?"
            params.append(min_viral)
        if days_back > 0:
            cutoff = (datetime.now() - timedelta(days=days_back)).isoformat()
            query += " AND fetched_at >= ?"
            params.append(cutoff)
        
        query += " ORDER BY viral_score DESC LIMIT ?"
        params.append(limit)
        
        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [Trend(**dict(row)) for row in rows]
    
    def get_trend_by_source(self, platform: str, source_id: str) -> Optional[Trend]:
        """Get a specific trend by source ID"""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM trends WHERE platform = ? AND source_id = ?",
                (platform, source_id)
            ).fetchone()
            return Trend(**dict(row)) if row else None
    
    def save_script(self, script: Script) -> int:
        """Save or update a script"""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            if script.id:
                conn.execute("""
                    UPDATE scripts SET 
                        trend_id = ?, title = ?, duration_minutes = ?, hook = ?,
                        content = ?, structure = ?, tags = ?, status = ?, notes = ?,
                        updated_at = ?, viral_score = ?, quality_score = ?
                    WHERE id = ?
                """, (
                    script.trend_id, script.title, script.duration_minutes, script.hook,
                    script.content, script.structure, script.tags, script.status, script.notes,
                    now, script.viral_score, script.quality_score, script.id
                ))
                conn.commit()
                return script.id
            else:
                cursor = conn.execute("""
                    INSERT INTO scripts 
                    (trend_id, title, duration_minutes, hook, content, structure, tags, 
                     status, notes, viral_score, quality_score, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    script.trend_id, script.title, script.duration_minutes, script.hook,
                    script.content, script.structure, script.tags, script.status, script.notes,
                    script.viral_score, script.quality_score, now, now
                ))
                conn.commit()
                return cursor.lastrowid
    
    def get_scripts(
        self,
        status: Optional[str] = None,
        min_viral: float = 0.0,
        limit: int = 20
    ) -> List[Script]:
        """Get scripts with filters"""
        query = "SELECT * FROM scripts WHERE 1=1"
        params = []
        
        if status:
            query += " AND status = ?"
            params.append(status)
        if min_viral > 0:
            query += " AND viral_score >= ?"
            params.append(min_viral)
        
        query += " ORDER BY viral_score DESC, created_at DESC LIMIT ?"
        params.append(limit)
        
        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [Script(**dict(row)) for row in rows]
    
    def get_script_by_id(self, script_id: int) -> Optional[Script]:
        """Get a script by ID"""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM scripts WHERE id = ?", (script_id,)).fetchone()
            return Script(**dict(row)) if row else None
    
    def update_script_status(self, script_id: int, status: str, notes: str = "") -> bool:
        """Update script status"""
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE scripts SET status = ?, notes = ?, updated_at = ? WHERE id = ?",
                (status, notes, datetime.now().isoformat(), script_id)
            )
            conn.commit()
            return True
    
    def get_niches(self, active_only: bool = True) -> List[Dict]:
        """Get all niches"""
        query = "SELECT * FROM niches"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY viral_potential DESC"
        
        with self._get_connection() as conn:
            rows = conn.execute(query).fetchall()
            return [dict(row) for row in rows]
    
    def update_niche_stats(self, niche_name: str, competition: float, potential: float):
        """Update niche statistics"""
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE niches SET min_competition = ?, viral_potential = ?, last_checked = ?
                WHERE name = ?
            """, (competition, potential, datetime.now().isoformat(), niche_name))
            conn.commit()
    
    def log_execution(
        self,
        run_type: str,
        platforms: List[str],
        trends_found: int,
        scripts_generated: int,
        status: str,
        error: str = ""
    ) -> int:
        """Log execution"""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO execution_log 
                (run_type, platforms, trends_found, scripts_generated, status, 
                 error_message, started_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (run_type, json.dumps(platforms), trends_found, scripts_generated,
                  status, error, now, now))
            conn.commit()
            return cursor.lastrowid
    
    def get_execution_history(self, limit: int = 10) -> List[Dict]:
        """Get execution history"""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM execution_log ORDER BY started_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(row) for row in rows]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        with self._get_connection() as conn:
            stats = {}
            
            stats['trends_by_platform'] = {}
            cursor = conn.execute("SELECT platform, COUNT(*) as count FROM trends GROUP BY platform")
            for row in cursor.fetchall():
                stats['trends_by_platform'][row[0]] = row[1]
            
            stats['scripts_by_status'] = {}
            cursor = conn.execute("SELECT status, COUNT(*) as count FROM scripts GROUP BY status")
            for row in cursor.fetchall():
                stats['scripts_by_status'][row[0]] = row[1]
            
            stats['top_trends'] = []
            cursor = conn.execute("SELECT title, viral_score, niche FROM trends ORDER BY viral_score DESC LIMIT 5")
            for row in cursor.fetchall():
                stats['top_trends'].append({'title': row[0], 'viral_score': row[1], 'niche': row[2]})
            
            stats['top_scripts'] = []
            cursor = conn.execute("SELECT title, viral_score, status, duration_minutes FROM scripts ORDER BY viral_score DESC LIMIT 5")
            for row in cursor.fetchall():
                stats['top_scripts'].append({'title': row[0], 'viral_score': row[1], 'status': row[2], 'duration_minutes': row[3]})
            
            stats['total_trends'] = conn.execute("SELECT COUNT(*) FROM trends").fetchone()[0]
            stats['total_scripts'] = conn.execute("SELECT COUNT(*) FROM scripts").fetchone()[0]
            
            return stats


if __name__ == "__main__":
    db = Database()
    print("Database initialized successfully!")
    print("Stats:", db.get_stats())
