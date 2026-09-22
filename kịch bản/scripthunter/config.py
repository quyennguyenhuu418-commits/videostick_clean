"""
ScriptHunter Configuration
Configuration for automated viral script scraping tool
"""

import os
from pathlib import Path

# Base paths - use relative paths to avoid Unicode issues
BASE_DIR = Path(__file__).parent.parent.parent
SCRIPTHUNTER_DIR = Path(__file__).parent
DATA_DIR = SCRIPTHUNTER_DIR / "data"
SCRIPTS_DIR = SCRIPTHUNTER_DIR / "scripts"
LOGS_DIR = SCRIPTHUNTER_DIR / "logs"
CACHE_DIR = SCRIPTHUNTER_DIR / "cache"

# Ensure directories exist
for d in [DATA_DIR, SCRIPTS_DIR, LOGS_DIR, CACHE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Database
DB_PATH = DATA_DIR / "scripthunter.db"

# Script parameters
SCRIPT_DURATION_MIN = 9  # minutes
SCRIPT_DURATION_MAX = 15  # minutes
WORDS_PER_MINUTE = 150  # Average speaking pace

# Trending sources configuration
SOURCES = {
    "reddit": {
        "enabled": True,
        "subreddits": [
            # True Crime & Mystery
            "r/UnresolvedMysteries",
            "r/TrueCrime",
            "r/MysteriousFacts",
            "r/Creepy",
            # History & What-If
            "r/HistoryWhatIf",
            "r/todayilearned",
            "r/ExplainLikeImFive",
            # Science & Engineering
            "r/engineering",
            "r/science",
            "r/Physics",
            "r/technology",
            # AI & Tech
            "r/artificial",
            "r/ChatGPT",
            "r/technology",
            # Obscure knowledge
            "r/todayilearned",
            "r/DepthHub",
            "r/ObscureKnowledge",
        ],
        "min_score": 1000,
        "max_age_days": 7,
    },
    "youtube": {
        "enabled": True,
        "api_key": os.getenv("YOUTUBE_API_KEY", ""),
        "regions": ["US", "VN", "GB"],
        "categories": ["education", "science", "technology"],
        "min_views": 10000,
        "max_age_days": 30,
    },
    "tiktok": {
        "enabled": False,  # Requires more complex setup
        "hashtags": [
            "trending",
            "fyp",
            "viral",
            "storytime",
            "mystery",
            "history",
            "science",
        ],
    },
    "google_trends": {
        "enabled": True,
        "regions": ["US", "VN"],
        "categories": ["all"],
    },
}

# Viral Scoring Weights
VIRAL_SCORING = {
    "reddit": {
        "score_weight": 0.4,
        "comments_weight": 0.3,
        "velocity_weight": 0.3,
    },
    "youtube": {
        "views_weight": 0.4,
        "likes_weight": 0.3,
        "comments_weight": 0.3,
    },
}

# Hook Types for Analysis
HOOK_TYPES = [
    "contrarian",  # "Everyone says X, but..."
    "curiosity_gap",  # "The thing they don't want you to know"
    "shocking_stat",  # "X% of people don't know this"
    "story_open",  # # Opening with a story
    "question",  # # Rhetorical or direct question
    "pattern_interrupt",  # # Unexpected visual/text
    "pov",  # # "POV: you're..."
    "how_to",  # # "How to..."
    "mistake",  # # "Stop doing X, do this instead"
    "comparison",  # # "X vs Y"
    "timeline",  # # "What happened next will shock you"
    "mystery",  # # "Nobody knows why..."
]

# Script Structure Template
SCRIPT_STRUCTURE = {
    "intro": {
        "duration_pct": 0.10,  # 10% of total
        "purpose": "Hook viewers in first 30 seconds",
        "elements": ["dramatic_question", "contrast_setup", "promise"],
    },
    "context": {
        "duration_pct": 0.15,  # 15% of total
        "purpose": "Establish background and stakes",
        "elements": ["setting", "key_players", "timeline_setup"],
    },
    "development": {
        "duration_pct": 0.50,  # 50% of total
        "purpose": "Main content delivery",
        "elements": ["main_points", "evidence", "examples", "transitions"],
    },
    "climax": {
        "duration_pct": 0.15,  # 15% of total
        "purpose": "Peak reveal or insight",
        "elements": ["twist", "revelation", "emotional_peak"],
    },
    "outro": {
        "duration_pct": 0.10,  # 10% of total
        "purpose": "Call to action and engagement",
        "elements": ["summary", "cta", "teaser"],
    },
}

# AI Configuration (for script generation)
AI_CONFIG = {
    "provider": "openai",  # or "anthropic"
    "model": "gpt-4o-mini",
    "temperature": 0.7,
    "max_tokens": 4000,
}

# Cron Schedule
CRON_CONFIG = {
    "enabled": True,
    "times": ["08:00", "14:00", "20:00"],  # Multiple runs per day
    "platforms": ["reddit", "google_trends"],
}

# Logging
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(message)s"
LOG_FILE = LOGS_DIR / "scripthunter.log"
