"""
Script Generator - ScriptHunter
Generate kịch bản 9-15 phút từ trends đã phân tích
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
from database import Database, Trend, Script
from config import SCRIPT_DURATION_MIN, SCRIPT_DURATION_MAX, WORDS_PER_MINUTE, SCRIPT_STRUCTURE


@dataclass
class ScriptSection:
    """A section of the script"""
    name: str
    duration_seconds: int
    word_count: int
    content: str
    cue_points: List[str]  # When to transition/pause
    visual_notes: List[str]  # What visuals to show


@dataclass
class GeneratedScript:
    """Complete generated script"""
    title: str
    hook: str
    sections: List[ScriptSection]
    total_duration_minutes: int
    total_words: int
    structure: Dict
    metadata: Dict
    raw_prompt_output: str = ""


class ScriptGenerator:
    """Generate professional scripts from trends"""
    
    # Script templates for different content types
    SCRIPT_TEMPLATES = {
        "true_crime": {
            "name": "True Crime Documentary",
            "structure": {
                "intro": {
                    "hook_position": "first_30_seconds",
                    "elements": ["dramatic_question", "setup_teaser", "promise"],
                },
                "context": {
                    "elements": ["victim_profile", "timeline_setup", "stakes_establishment"],
                },
                "development": {
                    "elements": ["investigation_steps", "evidence_presentation", "twists"],
                },
                "climax": {
                    "elements": ["major_revelation", "emotional_peak"],
                },
                "outro": {
                    "elements": ["summary", "open_questions", "discussion_prompt"],
                },
            },
            "tone": "suspenseful, investigative, respectful",
            "pacing": "measured, building tension",
        },
        "what_if": {
            "name": "What If Scenario",
            "structure": {
                "intro": {
                    "hook_position": "immediate",
                    "elements": ["scenario_setup", "stakes_introduction"],
                },
                "context": {
                    "elements": ["current_reality", "divergence_point", "rules"],
                },
                "development": {
                    "elements": ["consequence_chain", "expert_angles", "possibilities"],
                },
                "climax": {
                    "elements": ["ultimate_conclusion", "most_likely_outcome"],
                },
                "outro": {
                    "elements": ["reflection", "your_thoughts", "share_prompt"],
                },
            },
            "tone": "speculative, engaging, thought-provoking",
            "pacing": "steady_build, curiosity_drive",
        },
        "science_explained": {
            "name": "Science Explainer",
            "structure": {
                "intro": {
                    "hook_position": "curiosity_hook",
                    "elements": ["mind_blowing_fact", "question_setup"],
                },
                "context": {
                    "elements": ["basic_concepts", "why_it_matters", "context"],
                },
                "development": {
                    "elements": ["deep_dive", "examples", "analogies", "evidence"],
                },
                "climax": {
                    "elements": ["key_insight", "aha_moment"],
                },
                "outro": {
                    "elements": ["summary", "applications", "further_curiosity"],
                },
            },
            "tone": "clear, enthusiastic, accessible",
            "pacing": "balanced, clear_progression",
        },
        "micro_documentary": {
            "name": "Micro Documentary",
            "structure": {
                "intro": {
                    "hook_position": "immediate",
                    "elements": ["intriguing_opening", "time_period", "promise"],
                },
                "context": {
                    "elements": ["setting", "key_figures", "situation"],
                },
                "development": {
                    "elements": ["events_sequence", "key_moments", "impact"],
                },
                "climax": {
                    "elements": ["climax_event", "significance"],
                },
                "outro": {
                    "elements": ["legacy", "lessons", "reflection"],
                },
            },
            "tone": "narrative, cinematic, immersive",
            "pacing": "flowing, story_driven",
        },
        "engineering_fails": {
            "name": "Engineering Failure Analysis",
            "structure": {
                "intro": {
                    "hook_position": "dramatic_hook",
                    "elements": ["failure_preview", "scope_setup"],
                },
                "context": {
                    "elements": ["project_overview", "design_goals", "stakes"],
                },
                "development": {
                    "elements": ["failure_sequence", "cause_analysis", "consequences"],
                },
                "climax": {
                    "elements": ["root_cause_reveal", "human_impact"],
                },
                "outro": {
                    "elements": ["lessons_learned", "modern_relevance", "prevention"],
                },
            },
            "tone": "analytical, dramatic, educational",
            "pacing": "building_to_revelation",
        },
        "general": {
            "name": "General Topic Script",
            "structure": {
                "intro": {
                    "hook_position": "immediate",
                    "elements": ["hook", "topic_intro", "value_preview"],
                },
                "context": {
                    "elements": ["background", "key_points_setup"],
                },
                "development": {
                    "elements": ["main_content", "examples", "supporting_evidence"],
                },
                "climax": {
                    "elements": ["key_insight", "memorable_point"],
                },
                "outro": {
                    "elements": ["summary", "call_to_action", "next_video_hint"],
                },
            },
            "tone": "engaging, informative, relatable",
            "pacing": "steady, engaging",
        },
    }
    
    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database()
        self.duration_min = SCRIPT_DURATION_MIN
        self.duration_max = SCRIPT_DURATION_MAX
        self.words_per_minute = WORDS_PER_MINUTE
    
    def generate_script(
        self,
        trend: Trend,
        target_duration: Optional[int] = None,
        content_type: Optional[str] = None,
        use_ai: bool = False,
        ai_api_key: Optional[str] = None
    ) -> Script:
        """Generate a complete script from a trend"""
        
        # Determine target duration
        duration = target_duration or self._calculate_optimal_duration(trend)
        
        # Get content type
        content_type = content_type or trend.niche or "general"
        
        # Get template
        template = self.SCRIPT_TEMPLATES.get(content_type, self.SCRIPT_TEMPLATES["general"])
        
        # Calculate word budget
        total_words = duration * self.words_per_minute
        
        # Generate sections
        sections = self._generate_sections(trend, duration, template)
        
        # Calculate actual duration
        actual_words = sum(s.word_count for s in sections)
        actual_duration = actual_words / self.words_per_minute
        
        # Build full content
        full_content = self._build_full_content(sections)
        
        # Create script object
        script = Script(
            trend_id=trend.id,
            title=self._generate_title(trend, content_type),
            duration_minutes=round(actual_duration, 1),
            hook=self._extract_hook(sections),
            content=full_content,
            structure=json.dumps({
                "template": template["name"],
                "content_type": content_type,
                "sections": [
                    {
                        "name": s.name,
                        "duration": s.duration_seconds,
                        "words": s.word_count,
                    }
                    for s in sections
                ]
            }),
            tags=json.dumps({
                "content_type": content_type,
                "source": trend.platform,
                "source_title": trend.title[:100],
            }),
            status="draft",
            viral_score=self._estimate_viral_potential(trend, sections),
            quality_score=0.0,  # Will be updated after review
            created_at=datetime.now().isoformat(),
        )
        
        # Save to database
        script_id = self.db.save_script(script)
        script.id = script_id
        
        return script
    
    def _calculate_optimal_duration(self, trend: Trend) -> int:
        """Calculate optimal script duration based on trend"""
        # Base on viral score
        if trend.viral_score > 0.8:
            return 12  # High potential, go longer
        elif trend.viral_score > 0.5:
            return 10  # Medium, standard length
        else:
            return 9   # Lower, keep concise
        
        # Could also adjust based on content complexity
        # if "deep" in trend.title.lower() or "history" in trend.niche:
        #     return min(duration + 3, self.duration_max)
    
    def _generate_sections(
        self,
        trend: Trend,
        duration: int,
        template: Dict
    ) -> List[ScriptSection]:
        """Generate all sections for the script"""
        sections = []
        total_seconds = duration * 60
        
        # Use base structure as the source of duration_pct
        structure = SCRIPT_STRUCTURE.copy()
        
        section_defs = [
            ("INTRO", "intro"),
            ("CONTEXT", "context"),
            ("DEVELOPMENT", "development"),
            ("CLIMAX", "climax"),
            ("OUTRO", "outro"),
        ]
        
        # Get section-specific elements from template
        template_structure = template.get("structure", {})
        
        for section_name, section_key in section_defs:
            if section_key not in structure:
                continue
            
            # Use base structure for duration, but override with template if provided
            section_config = structure[section_key].copy()
            if section_key in template_structure:
                template_cfg = template_structure[section_key]
                # Preserve template elements but use base duration_pct
                if "elements" in template_cfg:
                    section_config["elements"] = template_cfg["elements"]
                # Template can override duration_pct if it specifies one
                if "duration_pct" in template_cfg:
                    section_config["duration_pct"] = template_cfg["duration_pct"]
            
            duration_pct = section_config.get("duration_pct", 0.1)
            duration_seconds = int(total_seconds * duration_pct)
            word_count = int(duration_seconds / 60 * self.words_per_minute)
            
            # Generate section content
            content = self._generate_section_content(
                trend, section_key, section_config, word_count
            )
            
            # Generate cue points
            cue_points = self._generate_cue_points(section_key, duration_seconds)
            
            # Generate visual notes
            visual_notes = self._generate_visual_notes(section_key, trend)
            
            sections.append(ScriptSection(
                name=section_name,
                duration_seconds=duration_seconds,
                word_count=len(content.split()),
                content=content,
                cue_points=cue_points,
                visual_notes=visual_notes,
            ))
        
        return sections
    
    def _generate_section_content(
        self,
        trend: Trend,
        section_type: str,
        config: Dict,
        word_count: int
    ) -> str:
        """Generate content for a specific section"""
        
        title = trend.title
        content = trend.content[:500] if trend.content else ""
        hook_type = trend.hook_type or "general"
        
        # Intro section
        if section_type == "intro":
            return self._expand_to_word_count(
                self._generate_intro(trend, hook_type, word_count),
                word_count, section_type, trend
            )
        
        # Context section
        elif section_type == "context":
            return self._expand_to_word_count(
                self._generate_context(trend, word_count),
                word_count, section_type, trend
            )
        
        # Development section
        elif section_type == "development":
            return self._expand_to_word_count(
                self._generate_development(trend, config, word_count),
                word_count, section_type, trend
            )
        
        # Climax section
        elif section_type == "climax":
            return self._expand_to_word_count(
                self._generate_climax(trend, word_count),
                word_count, section_type, trend
            )
        
        # Outro section
        elif section_type == "outro":
            return self._expand_to_word_count(
                self._generate_outro(trend, word_count),
                word_count, section_type, trend
            )
        
        return ""
    
    def _expand_to_word_count(
        self,
        base_content: str,
        target_words: int,
        section_type: str,
        trend: Trend
    ) -> str:
        """Expand content to meet target word count by adding detail variations"""
        current_words = len(base_content.split())
        
        if current_words >= target_words * 0.9:
            return base_content
        
        topic = self._extract_topic(trend)
        
        # Detail blocks to expand based on section type
        expansion_blocks = {
            "intro": [
                f"\n\nHere's why {topic} matters more than you think.",
                f"\n\nMost people overlook the significance of {topic}, but the data tells a different story.",
                f"\n\nStay with me because what I'm about to share changes everything.",
                f"\n\nThis isn't speculation - it's based on real evidence.",
                f"\n\nLet me paint a picture for you.",
                f"\n\nBy the end of this, you'll see {topic} in a completely new light.",
                f"\n\nThe facts are often stranger than fiction, and {topic} is no exception.",
            ],
            "context": [
                f"\n\nTo understand {topic}, we need to go back to the beginning.",
                f"\n\nThe story of {topic} starts with a series of events that most people have forgotten.",
                f"\n\nConsider the time period when {topic} first emerged.",
                f"\n\nThe world looked very different then.",
                f"\n\nKey players were making decisions that would shape everything that followed.",
                f"\n\nThe context matters because it explains the 'why' behind the 'what.'",
                f"\n\nWithout this background, the rest doesn't make sense.",
                f"\n\nLet me give you the essential details you need to know.",
                f"\n\nThis foundation is crucial for what comes next.",
            ],
            "development": [
                f"\n\nLet's break this down further.",
                f"\n\nHere's where things get interesting.",
                f"\n\nPoint by point, the picture becomes clearer.",
                f"\n\nConsider this angle for a moment.",
                f"\n\nThe implications are profound.",
                f"\n\nThis leads us to another important aspect of {topic}.",
                f"\n\nMany experts have weighed in on this, and their consensus is striking.",
                f"\n\nWhat the mainstream sources don't tell you is this:",
                f"\n\nThere's a pattern here that reveals something important.",
                f"\n\nLet me walk you through the evidence.",
                f"\n\nThe data supports this conclusion.",
                f"\n\nWhen you connect all the dots, a clear narrative emerges.",
                f"\n\nResearchers have found additional evidence that strengthens this view.",
                f"\n\nHere's another piece of the puzzle.",
                f"\n\nThis is where the analysis gets really interesting.",
                f"\n\nExperts in the field have noted these patterns for years.",
                f"\n\nThe deeper you dig, the more fascinating it becomes.",
                f"\n\nConsider the second-order effects of {topic}.",
                f"\n\nThere are multiple layers to this story.",
                f"\n\nLet me illustrate with a specific example.",
            ],
            "climax": [
                f"\n\nThis is where everything comes together.",
                f"\n\nThe answer, when you finally see it, feels inevitable.",
                f"\n\nThink about what this means for {topic}.",
                f"\n\nThe full picture is finally clear.",
                f"\n\nNow you understand why this matters.",
                f"\n\nThis insight changes everything.",
                f"\n\nWith this understanding, {topic} takes on new meaning.",
                f"\n\nThe implications extend far beyond what most people realize.",
                f"\n\nThis is the crux of the matter.",
            ],
            "outro": [
                f"\n\nThat's the complete picture.",
                f"\n\nThank you for staying with me until the end.",
                f"\n\nIf this resonated with you, share it with someone who needs to hear it.",
                f"\n\nLet me know your thoughts in the comments.",
                f"\n\nUntil next time, keep questioning everything.",
            ],
        }
        
        blocks = expansion_blocks.get(section_type, expansion_blocks["development"])
        
        # Add blocks until we hit target
        expanded = base_content
        block_index = 0
        max_blocks = len(blocks) * 6  # Allow more iterations
        
        while len(expanded.split()) < target_words and block_index < max_blocks:
            block = blocks[block_index % len(blocks)]
            expanded += block
            block_index += 1
            
            # Safety: don't exceed too much
            if len(expanded.split()) > target_words * 1.15:
                break
        
        # If still under target, add generic detail paragraphs
        topic = self._extract_topic(trend)
        theme_paragraphs = [
            f"Let me elaborate on another aspect of {topic}.",
            f"This connects to a broader pattern we see in {topic}.",
            f"Consider the long-term implications of {topic}.",
            f"This is why {topic} continues to fascinate researchers.",
            f"There's more to {topic} than meets the eye.",
            f"The story of {topic} has many layers.",
            f"This brings us to another critical point.",
            f"Experts in {topic} often highlight this connection.",
            f"The relationship between these elements is significant.",
            f"This phenomenon appears repeatedly in {topic}.",
            f"Researchers have documented similar cases related to {topic}.",
            f"The data consistently supports this view of {topic}.",
        ]
        
        para_index = 0
        while len(expanded.split()) < target_words and para_index < len(theme_paragraphs) * 2:
            para = theme_paragraphs[para_index % len(theme_paragraphs)]
            expanded += "\n\n" + para
            para_index += 1
            
            if len(expanded.split()) > target_words * 1.1:
                break
        
        return expanded
    
    def _generate_intro(self, trend: Trend, hook_type: str, word_count: int) -> str:
        """Generate intro section with strong hook"""
        
        # Strong opening based on hook type
        openings = {
            "contrarian": [
                f"Everyone thinks {self._extract_topic(trend)}, but what if I told you the opposite is actually true?",
                f"What if everything you've heard about {self._extract_topic(trend)} is completely wrong?",
            ],
            "curiosity_gap": [
                f"There's something about {self._extract_topic(trend)} that nobody talks about.",
                f"What they don't want you to know about {self._extract_topic(trend)} will change everything.",
            ],
            "mystery": [
                f"Here's the mystery: {self._extract_topic(trend)}. And nobody knows the answer.",
                f"It happened in {self._extract_topic(trend)}. And experts are still baffled.",
            ],
            "shocking_stat": [
                f"Ninety percent of people don't know this about {self._extract_topic(trend)}.",
                f"Here's a statistic that will blow your mind about {self._extract_topic(trend)}.",
            ],
            "story_open": [
                f"Let me tell you a story about {self._extract_topic(trend)}.",
                f"What happened next will shock you. It's about {self._extract_topic(trend)}.",
            ],
            "timeline": [
                f"What happened in {self._extract_topic(trend)} changed everything.",
                f"The story of {self._extract_topic(trend)} starts like this...",
            ],
            "general": [
                f"Today, we're diving deep into {self._extract_topic(trend)}.",
                f"If you've ever wondered about {self._extract_topic(trend)}, this video is for you.",
            ],
        }
        
        hook = openings.get(hook_type, openings["general"])[0]
        
        intro = f"""{hook}

In this video, you're going to discover something fascinating about {self._extract_topic(trend)}.

By the end, you'll understand not just the what, but the why behind it all — and why it matters to you.

Let's get into it."""

        return intro
    
    def _generate_context(self, trend: Trend, word_count: int) -> str:
        """Generate context/background section"""
        
        topic = self._extract_topic(trend)
        
        context = f"""Before we dive deeper, let's set the stage for {topic}.

{topic} has been a topic of intense interest for a long time. But most people only know the surface-level details.

What we're going to explore today goes beyond the basics. We're talking about the real story — the details that most videos skip over.

This context is crucial because it helps us understand not just what happened, but why it matters in the bigger picture."""

        return context
    
    def _generate_development(
        self,
        trend: Trend,
        config: Dict,
        word_count: int
    ) -> str:
        """Generate main development section with key points"""
        
        topic = self._extract_topic(trend)
        elements = config.get("elements", ["main_points", "evidence", "examples"])
        
        # Build development content based on content type
        if "investigation_steps" in elements or "evidence_presentation" in elements:
            development = self._generate_investigative_development(trend, topic)
        elif "consequence_chain" in elements or "possibilities" in elements:
            development = self._generate_speculative_development(trend, topic)
        elif "examples" in elements or "analogies" in elements:
            development = self._generate_educational_development(trend, topic)
        elif "events_sequence" in elements or "key_moments" in elements:
            development = self._generate_narrative_development(trend, topic)
        else:
            development = self._generate_generic_development(trend, topic)
        
        return development
    
    def _generate_investigative_development(self, trend: Trend, topic: str) -> str:
        """Development for true crime / investigative content"""
        return f"""Let's break down what we know about {topic}.

**First**, there's the initial circumstances. This sets the foundation for everything that followed.

**Second**, we have the key developments. These are the moments that changed the trajectory.

**Third**, there's the evidence. And this is where things get interesting.

See, most coverage of {topic} stops here. But we're just getting started.

What the official reports don't tell you is the context behind each piece of evidence. When you look at the timeline more carefully, patterns start to emerge.

Some experts believe that the commonly accepted narrative misses crucial details. They point to inconsistencies that most people overlook.

And then there's the aspect that nobody discusses in mainstream coverage — the human element.

The people involved in {topic} weren't just names in a report. They were real people with real stories. Understanding this changes everything about how we view the situation.

**Here's something fascinating:** When we dig deeper into the secondary sources, we find information that contradicts the mainstream narrative."""

    def _generate_speculative_development(self, trend: Trend, topic: str) -> str:
        """Development for what-if / speculative content"""
        return f"""Now let's explore the fascinating implications of {topic}.

**The first layer** — what most people consider when they think about {topic}.

But here's where it gets interesting. When experts dig deeper, they find connections that most people miss.

**The second layer** — the ripple effects. {topic} doesn't exist in isolation. It connects to bigger systems, bigger ideas.

Think about it this way: if {topic} were different, how would that change everything else?

**The third layer** — the long-term implications. This is where things get really thought-provoking.

Some researchers have spent years studying these connections. Their findings suggest that {topic} is more significant than we initially thought.

**Consider this scenario:** What if we approached {topic} from a completely different angle?

The possibilities are endless, and that's what makes this topic so compelling.

Each perspective reveals something new. Each angle opens up questions we haven't considered before."""

    def _generate_educational_development(self, trend: Trend, topic: str) -> str:
        """Development for educational content"""
        return f"""Let's break down {topic} into digestible pieces.

**First, the fundamentals.** To understand the complex stuff, we need to grasp these basics.

Think of it like building a house. You need a solid foundation before you can add the walls. {topic} works the same way.

**Second, the mechanism.** Here's how it actually works...

This is where most explanations get too technical. Let me use an analogy instead.

Imagine {topic} as a complex machine. Each part has a specific role, but they all work together.

**Third, the evidence.** What proof do we have?

Multiple studies have confirmed these principles. The data is compelling.

**Fourth, real-world applications.** How does this show up in everyday life?

You encounter {topic} more often than you realize. Once you know what to look for, you'll start noticing it everywhere.

**Finally, the deeper implications.** What does this mean for the bigger picture?

Understanding {topic} isn't just about knowledge. It's about seeing the world differently."""

    def _generate_narrative_development(self, trend: Trend, topic: str) -> str:
        """Development for storytelling content"""
        return f"""The story of {topic} begins in a way that most people don't expect.

It started with a seemingly small event — so small that most people overlooked it.

But this tiny spark would ignite something much larger.

**The early days** were marked by uncertainty. No one knew how this would unfold.

Then came the turning point. This is where everything changed.

The key figures emerged. Each one played a crucial role in what would become {topic}.

**The progression** was not linear. There were setbacks, challenges, moments of doubt.

But through it all, the momentum built. Each event connected to the next.

By the middle of the story, patterns were emerging. The shape of {topic} was becoming clear.

**The pivotal moment** came when everything aligned.

This is where the story reaches its critical juncture.

What happened next would define everything that followed.

The aftermath revealed consequences that no one had anticipated.

**The legacy** of {topic} extends far beyond what anyone expected at the beginning."""

    def _generate_generic_development(self, trend: Trend, topic: str) -> str:
        """Generic development section"""
        return f"""Let's explore the key aspects of {topic}.

**Point one:** The fundamentals everyone should know.

This forms the foundation of understanding {topic}. Without this context, the rest doesn't make sense.

**Point two:** The deeper insights.

Here's where most sources fall short. They give you surface-level information, but we're going deeper.

What the experts understand about {topic} is fascinating. Their perspective changes how we view the entire topic.

**Point three:** Real-world connections.

{topic} doesn't exist in isolation. It connects to many other areas in surprising ways.

Understanding these connections helps us grasp the bigger picture.

**Point four:** Common misconceptions.

There's a lot of misinformation about {topic}. Let's clear that up right now.

The truth is often different from what most people believe.

**Point five:** What this means for you.

How does {topic} affect your daily life? More than you might think.

Once you understand this, you'll never see {topic} the same way again."""
    
    def _generate_climax(self, trend: Trend, word_count: int) -> str:
        """Generate climax/reveal section"""
        topic = self._extract_topic(trend)
        
        return f"""And now, here's the moment you've been waiting for.

This is the insight that ties everything together about {topic}.

**The key revelation:**

Everything we've discussed points to this one critical understanding. 

The implications are profound. This isn't just trivia or interesting information — this changes how we think about {topic}.

When you truly grasp this concept, you realize that most conventional wisdom about {topic} is incomplete.

**Why does this matter?**

Because understanding {topic} at this level gives you an advantage. You see what others miss. You understand what others overlook.

This is the difference between knowing something and truly understanding it.

**The bottom line:**

{topic} is more complex, more fascinating, and more significant than most people realize.

And now that you know, you'll never look at {topic} the same way again."""
    
    def _generate_outro(self, trend: Trend, word_count: int) -> str:
        """Generate outro with CTA"""
        topic = self._extract_topic(trend)
        
        return f"""That brings us to the end of our deep dive into {topic}.

**Quick recap** of what we covered:
- The hook that reveals the true nature of {topic}
- The context that sets the stage for understanding
- The development that shows the complexity and depth
- The climax that ties everything together

**What to do next:**
If you found this valuable, hit that subscribe button and leave a comment.

What aspect of {topic} surprised you the most? I'd love to hear your thoughts.

And if you want to go deeper, check out my other videos where we explore similar topics.

**A final thought:**

The more we learn about {topic}, the more we realize how much there is still to discover.

That's what makes this journey of knowledge so exciting.

Thanks for watching. I'll see you in the next one."""
    
    def _generate_cue_points(self, section_type: str, duration_seconds: int) -> List[str]:
        """Generate cue points for editing"""
        cues = []
        
        if section_type == "intro":
            cues = [
                f"0:00 - Opening hook",
                f"0:15 - Topic introduction",
                f"{duration_seconds//60}:{(duration_seconds%60):02d} - Transition to main content"
            ]
        elif section_type == "context":
            cues = [
                f"Set background mood/music",
                f"{duration_seconds//4}:00 - First key point",
                f"{duration_seconds//2}:00 - Second key point",
            ]
        elif section_type == "development":
            cues = [
                f"{duration_seconds//5}:00 - Section 1 transition",
                f"{2*duration_seconds//5}:00 - Section 2 transition",
                f"{3*duration_seconds//5}:00 - Section 3 transition",
                f"{4*duration_seconds//5}:00 - Building to climax",
            ]
        elif section_type == "climax":
            cues = [
                f"0:00 - Peak moment",
                f"Music swell",
                f"{duration_seconds//2}:00 - Key insight",
            ]
        elif section_type == "outro":
            cues = [
                f"0:00 - Recap",
                f"{duration_seconds//3}:00 - CTA",
                f"End card",
            ]
        
        return cues
    
    def _generate_visual_notes(self, section_type: str, trend: Trend) -> List[str]:
        """Generate visual direction notes"""
        notes = []
        
        visual_styles = {
            "intro": ["B-roll of relevant imagery", "Text overlay with hook", "Creator face cam (optional)"],
            "context": ["Historical footage if applicable", "Diagrams/charts", "Location establishing shots"],
            "development": ["Supporting B-roll", "On-screen text highlights", "Archival images", "Reenactments if appropriate"],
            "climax": [" dramatic imagery", "Key moment highlight", "Emotional visual", "Slow motion if applicable"],
            "outro": ["Creator face cam", "Subscribe button", "Related videos", "End screen template"],
        }
        
        notes.extend(visual_styles.get(section_type, []))
        
        # Add content-specific notes
        if "crime" in trend.niche or "true_crime" in trend.niche:
            notes.append("Crime scene photos (handle sensitively)")
            notes.append("Forensic diagrams")
        elif "history" in trend.niche or "what_if" in trend.niche:
            notes.append("Historical recreations")
            notes.append("Timeline graphics")
        elif "science" in trend.niche:
            notes.append("Scientific animations")
            notes.append("Data visualizations")
            notes.append("Lab footage")
        
        return notes
    
    def _generate_title(self, trend: Trend, content_type: str) -> str:
        """Generate engaging title based on trend"""
        topic = self._extract_topic(trend)
        
        # Title templates by content type
        templates = {
            "true_crime": [
                f"The Disturbing Truth About {topic} Nobody Talks About",
                f"What Really Happened With {topic} (Deep Dive)",
            ],
            "what_if": [
                f"What If {topic}? (Mind-Bending Scenario)",
                f"The Reality of {topic} That Will Shock You",
            ],
            "science_explained": [
                f"{topic} Explained in 10 Minutes",
                f"The Science Behind {topic} (Simple Explanation)",
            ],
            "micro_documentary": [
                f"The Untold Story of {topic}",
                f"{topic}: The Complete Story (Documentary)",
            ],
            "engineering_fails": [
                f"How {topic} Went Wrong (Engineering Analysis)",
                f"The Brutal Truth About {topic}",
            ],
            "general": [
                f"Everything About {topic} You Need to Know",
                f"The Complete Guide to {topic}",
            ],
        }
        
        import random
        titles = templates.get(content_type, templates["general"])
        return random.choice(titles)
    
    def _extract_topic(self, trend: Trend) -> str:
        """Extract clean topic from trend title"""
        # Clean up the title
        title = trend.title
        
        # Remove common prefixes
        prefixes_to_remove = [
            r"^Update:", r"^RE:", r"^\[.*?\]\s*",
            r"^What if ", r"^Why ",
        ]
        
        for prefix in prefixes_to_remove:
            title = re.sub(prefix, "", title, flags=re.IGNORECASE)
        
        # Limit length
        if len(title) > 50:
            title = title[:47] + "..."
        
        return title
    
    def _extract_hook(self, sections: List[ScriptSection]) -> str:
        """Extract hook line from intro"""
        for section in sections:
            if section.name == "INTRO":
                # Get first 100 chars as hook
                return section.content[:100].strip() + "..."
        return ""
    
    def _build_full_content(self, sections: List[ScriptSection]) -> str:
        """Build full script content from sections"""
        full = ""
        
        for section in sections:
            full += f"\n{'='*60}\n"
            full += f"[{section.name}] (Duration: {section.duration_seconds//60}:{section.duration_seconds%60:02d})\n"
            full += f"{'='*60}\n\n"
            full += section.content
            full += "\n\n"
            
            # Add cue points
            if section.cue_points:
                full += "CUE POINTS:\n"
                for cue in section.cue_points:
                    full += f"  • {cue}\n"
                full += "\n"
            
            # Add visual notes
            if section.visual_notes:
                full += "VISUAL NOTES:\n"
                for note in section.visual_notes:
                    full += f"  • {note}\n"
                full += "\n"
        
        return full.strip()
    
    def _estimate_viral_potential(self, trend: Trend, sections: List[ScriptSection]) -> float:
        """Estimate viral potential of generated script"""
        score = trend.viral_score
        
        # Boost for strong hook
        intro = next((s for s in sections if s.name == "INTRO"), None)
        if intro and len(intro.content) > 50:
            score += 0.1
        
        # Boost for good structure
        if len(sections) >= 4:
            score += 0.05
        
        return min(score, 1.0)
    
    def generate_batch(
        self,
        trends: List[Trend],
        target_duration: Optional[int] = None
    ) -> List[Script]:
        """Generate scripts for multiple trends"""
        scripts = []
        
        print(f"\n{Fore.CYAN}[Generator] Generating scripts for {len(trends)} trends...{Style.RESET_ALL}")
        
        for i, trend in enumerate(trends):
            print(f"{Fore.YELLOW}  [{i+1}/{len(trends)}] {trend.title[:50]}...{Style.RESET_ALL}")
            
            try:
                script = self.generate_script(
                    trend=trend,
                    target_duration=target_duration
                )
                scripts.append(script)
                print(f"{Fore.GREEN}    ✓ Generated: {script.title[:40]}... ({script.duration_minutes} min){Style.RESET_ALL}")
                
            except Exception as e:
                print(f"{Fore.RED}    ✗ Error: {e}{Style.RESET_ALL}")
        
        print(f"\n{Fore.GREEN}[Generator] Generated {len(scripts)} scripts!{Style.RESET_ALL}")
        return scripts


if __name__ == "__main__":
    generator = ScriptGenerator()
    # Test with a mock trend
    from database import Trend
    test_trend = Trend(
        platform="reddit",
        source_id="test123",
        title="What happened to this mysterious disappearance will shock you",
        content="A detailed story about a mysterious case that has baffled investigators for decades.",
        viral_score=0.75,
        hook_type="mystery",
        niche="true_crime"
    )
    
    script = generator.generate_script(test_trend, target_duration=10)
    print(f"\nGenerated script: {script.title}")
    print(f"Duration: {script.duration_minutes} minutes")
    print(f"Word count: {len(script.content.split())}")
