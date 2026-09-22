"""
Hook Analyzer - ScriptHunter
Phân tích và trích xuất hook patterns từ trends
"""

import re
import json
import math
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import sys

from colorama import Fore, Style

sys.path.append(str(Path(__file__).parent.parent))
from database import Database, Trend
from config import HOOK_TYPES, SCRIPT_STRUCTURE


@dataclass
class HookPattern:
    """Represents a hook pattern"""
    type: str
    title: str
    elements: List[str]
    examples: List[str]
    score: float
    viral_potential: float
    engagement_rate: float
    platforms: List[str] = field(default_factory=list)


@dataclass
class TrendAnalysis:
    """Analysis results for a trend"""
    trend: Trend
    hook_type: str
    hook_confidence: float
    content_type: str
    target_niche: str
    viral_factors: List[str]
    improvement_suggestions: List[str]
    recommended_structure: Dict
    estimated_engagement: float
    competition_level: str  # low, medium, high
    best_posting_time: str
    metadata: Dict = field(default_factory=dict)


class HookAnalyzer:
    """Analyzer for hook patterns and trend analysis"""
    
    # Hook pattern definitions
    HOOK_PATTERNS = {
        "contrarian": {
            "name": "Contrarian / Flip the Script",
            "description": "Challenges conventional wisdom",
            "patterns": [
                r"stop (doing|using|believing)",
                r"everyone (says|thinks|believes|does)",
                r"they don't want you to (know|see|have)",
                r"(wrong|mistake|lie|myth)",
                r"actually the (opposite|truth|reason)",
                r"(not|isn't|doesn't) what you (think|expect|know)",
                r"here's the (truth|real|actual)",
                r"you've been (doing|thinking|using) it wrong",
            ],
            "viral_multiplier": 1.5,
        },
        "curiosity_gap": {
            "name": "Curiosity Gap",
            "description": "Creates information gap that viewers want to fill",
            "patterns": [
                r"what (they|he|she|we) don't (want|show|tell)",
                r"the (secret|hidden|buried|untold)",
                r"(nobody|no one) (knows|tells|explains|shows)",
                r"the thing about",
                r"the real reason",
                r"what (really|actually) (happened|works|exists)",
                r"here's why",
            ],
            "viral_multiplier": 1.4,
        },
        "shocking_stat": {
            "name": "Shocking Statistic",
            "description": "Uses surprising data to hook viewers",
            "patterns": [
                r"(\d+%|\d+ percent)",
                r"(\d+ in \d+)",
                r"1 out of \d+",
                r"(percent|chance|probability)",
                r"(study|research|data) (shows|reveals|proves)",
                r"(surprising|shocking|dramatically)",
            ],
            "viral_multiplier": 1.3,
        },
        "story_open": {
            "name": "Story Opening",
            "description": "Starts with a compelling narrative",
            "patterns": [
                r"(story|storytime)",
                r"(happened to me|i was|i once|i remember)",
                r"(need advice|looking for)",
                r"(tifu confession)",
                r"(when i was|i'll never forget)",
                r"this (is|made) (my|the) (worst|best|craziest)",
            ],
            "viral_multiplier": 1.35,
        },
        "question": {
            "name": "Engaging Question",
            "description": "Asks a question to provoke thought",
            "patterns": [
                r"^(why|how|what|when|where|who|can|should|does|is)",
                r"\?$",
                r"ever wondered",
                r"(have you|do you) (ever|really)",
                r"imagine if",
                r"what if (you|i|we)",
            ],
            "viral_multiplier": 1.2,
        },
        "pattern_interrupt": {
            "name": "Pattern Interrupt",
            "description": "Breaks visual/text expectations",
            "patterns": [
                r"\[.*\]",
                r"\(.*\)",
                r"(nsfw|sfw|mildly|extremely)",
                r"(oc| repost)",
                r"(not for|sensitive|trigger)",
            ],
            "viral_multiplier": 1.15,
        },
        "pov": {
            "name": "POV / Perspective",
            "description": "Places viewer in a scenario",
            "patterns": [
                r"pov:",
                r"when you (are|have|get|become|start)",
                r"as a(n)? (new|senior|former|real)",
                r"being a(n)?",
                r"day in the life",
                r"(real|honest) (truth|answer|reason)",
            ],
            "viral_multiplier": 1.25,
        },
        "mystery": {
            "name": "Mystery / Unsolved",
            "description": "Presents an unsolved puzzle",
            "patterns": [
                r"(mystery|unsolved|unexplained)",
                r"(disappeared|vanished|gone without)",
                r"(nobody knows|still don't know)",
                r"(finally|just|recently) (explained|discovered|solved)",
                r"(why|how) (did|does|is|are) (this|that|it)",
                r"the (biggest|real) question",
            ],
            "viral_multiplier": 1.45,
        },
        "timeline": {
            "name": "Timeline / Sequence",
            "description": "Builds anticipation through sequence",
            "patterns": [
                r"what (happened|followed|next|came)",
                r"(then|after|before) (that|this|i|he|she)",
                r"chronological",
                r"step by step",
                r"(the|his|her|their) (story|history|journey)",
                r"(how it|i) (was|were|got|became)",
            ],
            "viral_multiplier": 1.3,
        },
        "comparison": {
            "name": "Comparison / VS",
            "description": "Creates tension through comparison",
            "patterns": [
                r"(\w+) vs\.? (\w+)",
                r"versus",
                r"(compared to|in comparison with)",
                r"(difference between|vs)",
                r"(better|worse|more|less) than",
                r"which (one|is|should)",
            ],
            "viral_multiplier": 1.25,
        },
        "how_to": {
            "name": "How-To / Tutorial",
            "description": "Educational value proposition",
            "patterns": [
                r"how to (not |)(do|make|get|be|start)",
                r"(simple|easy|quick) way to",
                r"(beginner's|ultimate|complete) guide",
                r"the (right|best|correct) way",
                r"tutorial",
                r"(learn|master|understand) (in|how)",
            ],
            "viral_multiplier": 1.1,
        },
        "mistake": {
            "name": "Mistake / Warning",
            "description": "Highlights common errors",
            "patterns": [
                r"(common|biggest|worst|serious) (mistake|error|fail)",
                r"(stop|never|don't) (make|do|use)",
                r"(warning|caution|attention)",
                r"you (probably|probably're) (doing|thinking|using)",
                r"(signs|sign) you're (doing|about to)",
            ],
            "viral_multiplier": 1.2,
        },
    }
    
    # Content type keywords
    CONTENT_TYPES = {
        "true_crime": {
            "keywords": ["murder", "crime", "killing", "victim", "investigation", "police",
                       "missing", "disappeared", "cold case", "unsolved", "detective", "evidence",
                       "autopsy", "trial", "court", "prosecutor", "suspect", "witness"],
            "viral_score": 0.9,
        },
        "history": {
            "keywords": ["history", "ancient", "war", "empire", "century", "civilization",
                        "king", "queen", "dynasty", "revolution", "historical"],
            "viral_score": 0.85,
        },
        "what_if": {
            "keywords": ["what if", "imagine", "alternate", "hypothetical", "scenario",
                        "suppose", "in another", "if only"],
            "viral_score": 0.95,
        },
        "science": {
            "keywords": ["science", "scientific", "research", "study", "discovery", "experiment",
                        "physics", "biology", "chemistry", "nasa", "scientist", "theory"],
            "viral_score": 0.8,
        },
        "technology": {
            "keywords": ["technology", "tech", "software", "app", "computer", "ai", "robot",
                        "automation", "digital", "internet", "cyber"],
            "viral_score": 0.85,
        },
        "engineering": {
            "keywords": ["engineering", "engineer", "construction", "bridge", "building",
                        "design", "structural", "architecture", "failure", "collapse"],
            "viral_score": 0.75,
        },
        "paradox": {
            "keywords": ["paradox", "puzzle", "riddle", "dilemma", "contradiction", "impossible",
                        "infinite", "loop", "mind-bending", "logic"],
            "viral_score": 0.9,
        },
        "story": {
            "keywords": ["story", "happened", "experience", "when i", "my friend", "tifu",
                       "confession", "ama", "advice", "update"],
            "viral_score": 0.8,
        },
    }
    
    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database()
    
    def analyze_trend(self, trend: Trend) -> TrendAnalysis:
        """Analyze a single trend"""
        # Detect hook type
        hook_type, confidence = self._detect_hook_type(trend.title)
        
        # Detect content type
        content_type = self._detect_content_type(trend)
        
        # Calculate viral factors
        viral_factors = self._extract_viral_factors(trend)
        
        # Get recommendations
        suggestions = self._get_improvement_suggestions(trend, hook_type)
        
        # Determine recommended structure
        structure = self._get_recommended_structure(content_type, hook_type)
        
        # Estimate engagement
        engagement = self._estimate_engagement(trend, hook_type)
        
        # Competition level
        competition = self._assess_competition(trend)
        
        # Best posting time
        posting_time = self._get_best_posting_time(trend)
        
        return TrendAnalysis(
            trend=trend,
            hook_type=hook_type,
            hook_confidence=confidence,
            content_type=content_type,
            target_niche=trend.niche or self._match_niche(content_type),
            viral_factors=viral_factors,
            improvement_suggestions=suggestions,
            recommended_structure=structure,
            estimated_engagement=engagement,
            competition_level=competition,
            best_posting_time=posting_time,
        )
    
    def analyze_trends(self, trends: List[Trend]) -> List[TrendAnalysis]:
        """Analyze multiple trends"""
        analyses = []
        for trend in trends:
            try:
                analysis = self.analyze_trend(trend)
                analyses.append(analysis)
            except Exception as e:
                print(f"{Fore.RED}[Analyzer] Error analyzing trend: {e}{Style.RESET_ALL}")
        return analyses
    
    def _detect_hook_type(self, title: str) -> Tuple[str, float]:
        """Detect hook type from title with confidence score"""
        title_lower = title.lower()
        scores = {}
        
        for hook_type, config in self.HOOK_PATTERNS.items():
            score = 0
            matches = 0
            
            for pattern in config["patterns"]:
                if re.search(pattern, title_lower, re.IGNORECASE):
                    score += 1
                    matches += 1
            
            if matches > 0:
                # Base score from matches + multiplier
                scores[hook_type] = (matches / len(config["patterns"])) * config["viral_multiplier"]
        
        if scores:
            best_hook = max(scores.items(), key=lambda x: x[1])
            confidence = min(best_hook[1], 1.0)
            return best_hook[0], confidence
        
        return "general", 0.5
    
    def _detect_content_type(self, trend: Trend) -> str:
        """Detect content type from trend"""
        text = f"{trend.title} {trend.content}".lower()
        
        scores = {}
        for content_type, config in self.CONTENT_TYPES.items():
            score = sum(1 for kw in config["keywords"] if kw in text)
            if score > 0:
                scores[content_type] = score * config["viral_score"]
        
        if scores:
            return max(scores.items(), key=lambda x: x[1])[0]
        
        return "general"
    
    def _extract_viral_factors(self, trend: Trend) -> List[str]:
        """Extract factors that contribute to viral potential"""
        factors = []
        title = trend.title.lower()
        
        # Check for viral triggers
        triggers = {
            "Emotional Appeal": ["shocking", "amazing", "incredible", "crazy", "insane", 
                               "unbelievable", "heartwarming", "devastating"],
            "Specific Numbers": [r"\d+", r"percent", r"%"],
            "Urgency": ["now", "today", "this week", "breaking", "new", "finally"],
            "Exclusivity": ["exclusive", "leaked", "never before", "first time", "only"],
            "Controversy": ["debate", "controversial", "unpopular", "argue", "disagree"],
            "Curiosity": ["secret", "revealed", "hidden", "explained", "mystery"],
            "Practical Value": ["how to", "guide", "tutorial", "tips", "tricks", "ways"],
        }
        
        for factor, keywords in triggers.items():
            if any(kw in title for kw in keywords if len(kw) > 2):
                factors.append(factor)
        
        return factors if factors else ["Standard content"]
    
    def _get_improvement_suggestions(self, trend: Trend, hook_type: str) -> List[str]:
        """Get suggestions to improve viral potential"""
        suggestions = []
        title = trend.title
        
        # Check title length
        if len(title) < 30:
            suggestions.append("Title is too short. Add more context or a specific detail.")
        elif len(title) > 100:
            suggestions.append("Title is too long. Keep it under 80 characters for better CTR.")
        
        # Hook-specific suggestions
        hook_suggestions = {
            "contrarian": "Add a specific claim to contradict, e.g., 'stop doing X, here's why'",
            "curiosity_gap": "Create a bigger information gap. What specific thing is hidden?",
            "shocking_stat": "Lead with the most shocking number in the title",
            "story_open": "Start with a specific moment, not 'I have a story'",
            "question": "Make the question more specific to the viewer's situation",
            "mystery": "Focus on the most intriguing unanswered question",
            "timeline": "Mention the endpoint to create anticipation",
        }
        
        if hook_type in hook_suggestions:
            suggestions.append(hook_suggestions[hook_type])
        
        # Generic suggestions
        if trend.engagement_rate < 0.05:
            suggestions.append("Low engagement rate. Consider a stronger opening hook.")
        
        if trend.score < 1000:
            suggestions.append("Low base engagement. Need stronger value proposition.")
        
        return suggestions[:3]  # Return top 3
    
    def _get_recommended_structure(self, content_type: str, hook_type: str) -> Dict:
        """Get recommended script structure based on content type"""
        # Base structure from config
        structure = SCRIPT_STRUCTURE.copy()
        
        # Adjust based on content type
        if content_type == "true_crime":
            # More emphasis on development and climax
            structure["intro"]["duration_pct"] = 0.08
            structure["context"]["duration_pct"] = 0.17
            structure["development"]["duration_pct"] = 0.45
            structure["climax"]["duration_pct"] = 0.20
            structure["outro"]["duration_pct"] = 0.10
        
        elif content_type == "what_if":
            # Strong intro for hook
            structure["intro"]["duration_pct"] = 0.12
            structure["context"]["duration_pct"] = 0.13
            structure["development"]["duration_pct"] = 0.50
            structure["climax"]["duration_pct"] = 0.15
            structure["outro"]["duration_pct"] = 0.10
        
        elif content_type == "science":
            # More context setting
            structure["intro"]["duration_pct"] = 0.10
            structure["context"]["duration_pct"] = 0.20
            structure["development"]["duration_pct"] = 0.45
            structure["climax"]["duration_pct"] = 0.15
            structure["outro"]["duration_pct"] = 0.10
        
        return structure
    
    def _estimate_engagement(self, trend: Trend, hook_type: str) -> float:
        """Estimate potential engagement (0-100)"""
        base = 50.0
        
        # Platform bonus
        platform_bonus = {
            "reddit": 15,
            "youtube": 20,
            "tiktok": 25,
        }
        base += platform_bonus.get(trend.platform, 10)
        
        # Hook type bonus
        hook_bonus = {
            "contrarian": 20,
            "curiosity_gap": 25,
            "shocking_stat": 20,
            "mystery": 25,
            "story_open": 15,
            "timeline": 15,
            "comparison": 15,
            "question": 10,
            "pov": 15,
            "pattern_interrupt": 10,
        }
        base += hook_bonus.get(hook_type, 5)
        
        # Engagement metrics
        if trend.engagement_rate > 0.1:
            base += 15
        elif trend.engagement_rate > 0.05:
            base += 10
        elif trend.engagement_rate > 0.02:
            base += 5
        
        # Viral score
        base += trend.viral_score * 30
        
        return min(base, 100)
    
    def _assess_competition(self, trend: Trend) -> str:
        """Assess competition level in the niche"""
        # Check how many similar trends exist
        similar_count = len(self.db.get_trends(niche=trend.niche, limit=100) if trend.niche else [])
        
        if similar_count > 50:
            return "high"
        elif similar_count > 20:
            return "medium"
        else:
            return "low"
    
    def _get_best_posting_time(self, trend: Trend) -> str:
        """Recommend best posting time"""
        # Based on platform and content type
        if trend.platform == "reddit":
            return "Weekdays 6-9 AM, 12-2 PM, 6-9 PM (local time)"
        elif trend.platform == "youtube":
            return "Thursday-Sunday, 2-4 PM (optimal for most audiences)"
        else:
            return "Weekends 10 AM-2 PM, Weekdays 7-9 PM"
    
    def _match_niche(self, content_type: str) -> str:
        """Match content type to niche"""
        niche_map = {
            "true_crime": "true_crime",
            "history": "what_if",
            "what_if": "what_if",
            "science": "science_explained",
            "technology": "ai_workflows",
            "engineering": "engineering_fails",
            "paradox": "paradoxes",
            "story": "story",
        }
        return niche_map.get(content_type, "general")
    
    def rank_trends(self, trends: List[Trend], top_n: int = 10) -> List[Trend]:
        """Rank trends by viral potential"""
        analyses = self.analyze_trends(trends)
        
        # Score each trend
        scored = []
        for analysis in analyses:
            score = (
                analysis.estimated_engagement * 0.4 +
                analysis.trend.viral_score * 100 * 0.3 +
                analysis.hook_confidence * 100 * 0.2 +
                (100 if analysis.competition_level == "low" else 50 if analysis.competition_level == "medium" else 25) * 0.1
            )
            scored.append((analysis.trend, score))
        
        # Sort by score
        scored.sort(key=lambda x: x[1], reverse=True)
        
        return [t[0] for t in scored[:top_n]]
    
    def get_hook_insights(self) -> Dict:
        """Get insights about hook patterns"""
        trends = self.db.get_trends(limit=500, days_back=30)
        
        hook_stats = {}
        for trend in trends:
            hook_type = trend.hook_type or "general"
            if hook_type not in hook_stats:
                hook_stats[hook_type] = {"count": 0, "total_viral": 0, "total_engagement": 0}
            
            hook_stats[hook_type]["count"] += 1
            hook_stats[hook_type]["total_viral"] += trend.viral_score
            hook_stats[hook_type]["total_engagement"] += trend.engagement_rate
        
        # Calculate averages
        insights = {}
        for hook_type, stats in hook_stats.items():
            count = stats["count"]
            insights[hook_type] = {
                "count": count,
                "avg_viral_score": round(stats["total_viral"] / count, 3),
                "avg_engagement_rate": round(stats["total_engagement"] / count, 4),
                "recommendation": "Use this hook" if stats["total_viral"] / count > 0.5 else "Consider alternatives"
            }
        
        return insights


if __name__ == "__main__":
    analyzer = HookAnalyzer()
    insights = analyzer.get_hook_insights()
    print(json.dumps(insights, indent=2))
