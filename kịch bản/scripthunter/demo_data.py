"""
Demo Data Generator - ScriptHunter
Tạo dữ liệu mẫu để test pipeline khi không thể scrape từ internet
"""

import random
import json
import math
from datetime import datetime, timedelta
from typing import List, Optional
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))
from database import Database, Trend


class DemoDataGenerator:
    """Generate realistic demo data for testing"""
    
    DEMO_TRENDS = [
        # TRUE CRIME
        {
            "title": "The mysterious disappearance of the Sodder family children still baffles investigators 75 years later",
            "content": "On Christmas Eve 1945, five of the Sodder children disappeared from their family home in Fayetteville, West Virginia. The parents believed the house was set on fire. Despite decades of investigation, no trace of the children has ever been found. The case remains one of America's most haunting unsolved mysteries, with multiple suspects but no definitive answers. Investigators have explored connections to organized crime, insurance fraud, and even theories involving secret tunnels and witness tampering.",
            "niche": "true_crime",
            "hook_type": "mystery",
            "score": 18500,
            "comments": 2340,
        },
        {
            "title": "What really happened to the Beaumont children on Adelaide beach in 1966?",
            "content": "Three siblings - Jane, Arnna, and Grant Beaumont - vanished from Glenelg Beach on Australia Day 1966. Despite one of the largest manhunts in Australian history, they were never found. The case has produced numerous suspects, including a known paedophile who confessed before his death. Recent DNA analysis of items found in his home has reopened the investigation, but conclusive answers remain elusive.",
            "niche": "true_crime",
            "hook_type": "curiosity_gap",
            "score": 12300,
            "comments": 1875,
        },
        {
            "title": "The Black Dahlia case: What the LAPD didn't tell you for 75 years",
            "content": "The gruesome murder of Elizabeth Short in 1947 has been investigated countless times, but new evidence suggests the LAPD knew more than they let on. Recently declassified files reveal connections to organized crime figures and potential witnesses who were never interviewed. The case remains officially unsolved, but the new documents paint a different picture of what really happened on that cold January morning.",
            "niche": "true_crime",
            "hook_type": "contrarian",
            "score": 22100,
            "comments": 3420,
        },
        # WHAT IF / HISTORY
        {
            "title": "What if the Roman Empire never fell? A 1500-year alternate history",
            "content": "Imagine if the Visigoths never sacked Rome in 410 AD. How would world history have unfolded differently? In this exploration, we consider the technological, cultural, and political implications of a continuous Roman civilization spanning two millennia. From the potential discovery of the Americas 1000 years before Columbus to a very different Industrial Revolution, the possibilities are fascinating.",
            "niche": "what_if",
            "hook_type": "pov",
            "score": 9800,
            "comments": 1450,
        },
        {
            "title": "The day the sun turned green: What actually happened during the 1815 solar event",
            "content": "For an entire year after the eruption of Mount Tambora, the sun appeared green, blue, or purple across the world. Temperatures dropped by an average of 1.5°C globally. 1816 became known as the 'Year Without a Summer.' Crops failed, famines spread, and thousands died. Yet most people have never heard of this catastrophic event that shaped the 19th century in ways we're still discovering.",
            "niche": "what_if",
            "hook_type": "shocking_stat",
            "score": 15600,
            "comments": 2100,
        },
        {
            "title": "How a single typo in a 1923 treaty changed the map of the Middle East forever",
            "content": "A seemingly innocent translation error in the Treaty of Lausanne has had consequences lasting a century. The mistranslation of a single Arabic word led to disputes over territories spanning Iraq, Kuwait, and Saudi Arabia. The error wasn't discovered for decades, by which time entire nations had been shaped by it. This is the story of how one diplomat's oversight changed history.",
            "niche": "what_if",
            "hook_type": "contrarian",
            "score": 11200,
            "comments": 1680,
        },
        # SCIENCE
        {
            "title": "Scientists discovered something impossible about this 800-year-old star",
            "content": "A star that's been burning for 800 million years longer than physics says it should have. Recent observations from the James Webb Space Telescope have revealed what appears to be a star that contradicts our understanding of stellar evolution. The discovery has forced astrophysicists to reconsider fundamental theories about how stars form and age.",
            "niche": "science_explained",
            "hook_type": "shocking_stat",
            "score": 19400,
            "comments": 2890,
        },
        {
            "title": "The bizarre reason your phone battery dies faster in cold weather (it's not what you think)",
            "content": "Most people assume cold weather kills batteries because of the temperature. The truth is far more interesting. The actual chemical reaction that powers your phone slows dramatically in cold conditions, but there's a specific threshold at which this happens. More importantly, there are ways to extend your battery life in winter that nobody talks about.",
            "niche": "science_explained",
            "hook_type": "contrarian",
            "score": 8700,
            "comments": 1230,
        },
        {
            "title": "A team of physicists just proved Einstein wrong in a way nobody expected",
            "content": "After 100 years of experimental verification, Einstein's theory of general relativity has finally shown a crack - but not in the way scientists predicted. New measurements from quantum entanglement experiments suggest spacetime might not be continuous but made of discrete units. This discovery could revolutionize our understanding of reality itself.",
            "niche": "science_explained",
            "hook_type": "shocking_stat",
            "score": 24500,
            "comments": 4100,
        },
        # ENGINEERING
        {
            "title": "Why the Hyatt Regency walkway collapse killed 114 people - and it wasn't the design",
            "content": "In 1981, two suspended walkways collapsed at the Hyatt Regency Kansas City, killing 114 people and injuring 200+ more. The disaster wasn't caused by a flawed design - it was caused by a change during construction that doubled the load on a critical connection. The original engineers' warning was ignored. This is the story of how a 'minor' modification became one of America's deadliest structural failures.",
            "niche": "engineering_fails",
            "hook_type": "mystery",
            "score": 16800,
            "comments": 2240,
        },
        {
            "title": "The bridge that was built upside down - and stayed standing for 30 years",
            "content": "In 2000, a Romanian engineer accidentally built a bridge with the deck below the suspension cables - the complete opposite of how it should be. By the time anyone noticed, the bridge had been standing for three decades and was carrying traffic daily. The story of how it stayed up, and what it teaches us about structural engineering assumptions.",
            "niche": "engineering_fails",
            "hook_type": "shocking_stat",
            "score": 13200,
            "comments": 1980,
        },
        # AI / TECH
        {
            "title": "I built a $500/month side hustle using only AI tools - here's the exact workflow",
            "content": "Six months ago, I started a side project using ChatGPT, Midjourney, and a few other AI tools. Today, it generates $500/month with less than 10 hours of work weekly. I'll show you the exact tools, prompts, and workflows I use. This isn't theory - this is a step-by-step breakdown of how regular people are using AI to build real income.",
            "niche": "ai_workflows",
            "hook_type": "how_to",
            "score": 21500,
            "comments": 3650,
        },
        {
            "title": "The AI prompt technique that 99% of people don't know about (it's called 'Tree of Thoughts')",
            "content": "Most people use AI like a search engine - asking one question, getting one answer. But there's a prompting technique called Tree of Thoughts that has been shown to improve AI reasoning by 70% on complex problems. Here's how it works, and why it's about to change how everyone uses AI.",
            "niche": "ai_workflows",
            "hook_type": "how_to",
            "score": 14200,
            "comments": 1890,
        },
        # PARADOXES
        {
            "title": "The bootstrap paradox: How can you be your own grandfather?",
            "content": "The bootstrap paradox is one of the most mind-bending puzzles in physics and philosophy. If you travel back in time and give your past self the plans for a time machine, who invented the time machine? This paradox doesn't just break causality - it suggests something profound about the nature of information itself. Scientists are still arguing about what this means.",
            "niche": "paradoxes",
            "hook_type": "question",
            "score": 10800,
            "comments": 1540,
        },
        {
            "title": "Why does Schrödinger still matter 100 years later?",
            "content": "Erwin Schrödinger's famous cat thought experiment wasn't just about cats. It was about the fundamental nature of reality. A century later, physicists are still debating what his equation means. The answer might change everything we know about the universe.",
            "niche": "paradoxes",
            "hook_type": "question",
            "score": 9300,
            "comments": 1320,
        },
        # STORIES
        {
            "title": "TIFU by accidentally becoming a hero during a robbery",
            "content": "I was at a gas station at 2 AM when a robbery started. I tried to hide but knocked over a shelf. The robber thought I was reaching for a weapon and dropped his gun. Long story short, I ended up being called 'the hero of the night' by local news, but I still feel guilty because I was just scared and clumsy. AMA about my 15 minutes of accidental fame.",
            "niche": "story",
            "hook_type": "story_open",
            "score": 25600,
            "comments": 4500,
        },
        {
            "title": "I worked at a haunted hotel for 5 years - here's what I really saw",
            "content": "The Stanley Hotel inspired Stephen King's 'The Shining.' I worked there for five years as a night auditor. Most 'hauntings' are explainable, but some things I witnessed cannot be explained by science. From objects moving on their own to voices in empty rooms, these are the incidents that changed my mind about what's possible.",
            "niche": "story",
            "hook_type": "contrarian",
            "score": 17800,
            "comments": 2870,
        },
        # MICRO DOCUMENTARY
        {
            "title": "The tiny Pacific island that changed world history in one day",
            "content": "In 1942, the Battle of Midway lasted just 3 days but changed the entire course of World War II. It happened on an island so small you could walk across it in 30 minutes. Yet this tiny atoll decided the fate of empires. Most people have never heard of this battle, but without it, the world today would look completely different.",
            "niche": "micro_documentary",
            "hook_type": "timeline",
            "score": 11500,
            "comments": 1680,
        },
        {
            "title": "How a forgotten chemist accidentally invented the plastic that built the modern world",
            "content": "In 1907, Leo Baekeland was trying to create a substitute for shellac. He accidentally invented Bakelite - the world's first fully synthetic plastic. Within 20 years, this 'lab accident' had replaced ivory in billiard balls, transformed jewelry, and laid the foundation for the entire plastics industry. The invention that built the modern world was a complete mistake.",
            "niche": "micro_documentary",
            "hook_type": "contrarian",
            "score": 13400,
            "comments": 1890,
        },
    ]
    
    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database()
    
    def generate_demo_trends(self, count: int = 20) -> List[Trend]:
        """Generate demo trends"""
        trends = []
        selected = random.sample(self.DEMO_TRENDS, min(count, len(self.DEMO_TRENDS)))
        
        for i, item in enumerate(selected):
            # Add realistic metadata
            score = item.get("score", random.randint(5000, 30000))
            comments = item.get("comments", random.randint(500, 5000))
            engagement_rate = (score + comments * 2) / max(score, 1)
            
            # Calculate viral score
            import math
            norm_score = math.log10(max(score, 1)) / 6
            norm_comments = math.log10(max(comments, 1)) / 5
            engagement_bonus = min(engagement_rate / 3, 1.5)
            viral_score = round((norm_score * 0.4 + norm_comments * 0.3 + engagement_bonus * 0.3), 3)
            viral_score = min(viral_score, 1.0)
            
            days_ago = random.randint(0, 5)
            created_at = datetime.now() - timedelta(days=days_ago)
            
            trend = Trend(
                platform="reddit",
                source_id=f"demo_{i:03d}",
                title=item["title"],
                content=item["content"],
                url=f"https://reddit.com/r/{item['niche']}/comments/demo_{i}",
                author=f"user_{random.randint(1000, 9999)}",
                score=score,
                comments=comments,
                engagement_rate=engagement_rate,
                viral_score=viral_score,
                hook_type=item["hook_type"],
                niche=item["niche"],
                tags=json.dumps({
                    "subreddit": f"r/{item['niche']}",
                    "content_type": item["niche"],
                    "demo": True
                }),
                created_at=created_at.isoformat(),
                fetched_at=datetime.now().isoformat()
            )
            
            trends.append(trend)
            self.db.save_trend(trend)
        
        return trends
    
    def generate_youtube_demo(self, count: int = 10) -> List[Trend]:
        """Generate demo YouTube trends"""
        youtube_titles = [
            {
                "title": "Why Most People Will Never Be Rich (The Math Is Brutal)",
                "views": 1250000, "likes": 45000, "comments": 8900,
                "niche": "science_explained", "hook_type": "contrarian",
                "content": "A detailed breakdown of the wealth distribution mathematics and why the system favors the wealthy."
            },
            {
                "title": "The Disappearance of Flight MH370: What We Actually Know",
                "views": 3400000, "likes": 89000, "comments": 15400,
                "niche": "true_crime", "hook_type": "mystery",
                "content": "An in-depth analysis of the evidence and what investigators have concluded 10 years later."
            },
            {
                "title": "I Built an AI Agent That Replaced My 9-5 (Full Tutorial)",
                "views": 890000, "likes": 34000, "comments": 5200,
                "niche": "ai_workflows", "hook_type": "how_to",
                "content": "A complete walkthrough of building automation AI agents using Python and OpenAI APIs."
            },
            {
                "title": "The 1918 Flu Was Worse Than You Think - Here's Why It Happened",
                "views": 2100000, "likes": 67000, "comments": 12300,
                "niche": "micro_documentary", "hook_type": "timeline",
                "content": "Historical analysis of the Spanish Flu pandemic and its parallels to modern outbreaks."
            },
            {
                "title": "What If We Nuked the Moon? (Scientific Analysis)",
                "views": 4500000, "likes": 156000, "comments": 28900,
                "niche": "what_if", "hook_type": "pov",
                "content": "A scientific exploration of what would actually happen if we detonated a nuclear device on the lunar surface."
            },
            {
                "title": "The $100 Million Mistake That Bankrupted This Company",
                "views": 1800000, "likes": 54000, "comments": 9800,
                "niche": "engineering_fails", "hook_type": "shocking_stat",
                "content": "Case study of Theranos and how Elizabeth Holmes' deception unraveled."
            },
            {
                "title": "Japan's Strange Solution to Their Loneliness Crisis",
                "views": 980000, "likes": 32000, "comments": 6700,
                "niche": "ai_workflows", "hook_type": "contrarian",
                "content": "How Japan is using robots and AI to combat their aging population and loneliness epidemic."
            },
            {
                "title": "The Loop That Breaks Physics (Time Travel Paradox Explained)",
                "views": 2700000, "likes": 78000, "comments": 14200,
                "niche": "paradoxes", "hook_type": "question",
                "content": "An exploration of the Novikov self-consistency principle and bootstrap paradox in time travel."
            },
            {
                "title": "This 1990s Tech Stock Was Worth More Than Apple - What Happened?",
                "views": 1500000, "likes": 43000, "comments": 7800,
                "niche": "story", "hook_type": "story_open",
                "content": "The rise and fall of Nokia, Blackberry, and how they missed the smartphone revolution."
            },
            {
                "title": "I Spent 30 Days Living Like a Caveman - Here's What I Learned",
                "views": 3200000, "likes": 89000, "comments": 19800,
                "niche": "story", "hook_type": "story_open",
                "content": "An experiment in primitive living that revealed surprising lessons about modern life."
            },
        ]
        
        trends = []
        selected = random.sample(youtube_titles, min(count, len(youtube_titles)))
        
        for i, item in enumerate(selected):
            views = item["views"]
            likes = item["likes"]
            comments = item["comments"]
            
            engagement_rate = (likes + comments * 5) / views
            
            import math
            norm_views = math.log10(max(views, 1)) / 9
            engagement = engagement_rate * 100
            viral_score = round((norm_views * 0.6 + min(engagement, 1) * 0.4), 3)
            viral_score = min(viral_score, 1.0)
            
            days_ago = random.randint(0, 30)
            created_at = datetime.now() - timedelta(days=days_ago)
            
            trend = Trend(
                platform="youtube",
                source_id=f"yt_demo_{i:03d}",
                title=item["title"],
                content=item["content"],
                url=f"https://youtube.com/watch?v=demo_{i}",
                author=f"Channel_{random.randint(1000, 9999)}",
                score=views,
                comments=comments,
                views=views,
                engagement_rate=engagement_rate,
                viral_score=viral_score,
                hook_type=item["hook_type"],
                niche=item["niche"],
                tags=json.dumps({
                    "region": random.choice(["US", "VN", "GB"]),
                    "demo": True
                }),
                created_at=created_at.isoformat(),
                fetched_at=datetime.now().isoformat()
            )
            
            trends.append(trend)
            self.db.save_trend(trend)
        
        return trends
    
    def generate_all_demo_data(self, reddit_count: int = 15, youtube_count: int = 8) -> List[Trend]:
        """Generate both Reddit and YouTube demo data"""
        print(f"\n{Fore.CYAN}[Demo] Generating demo data...{Style.RESET_ALL}")
        
        reddit_trends = self.generate_demo_trends(reddit_count)
        youtube_trends = self.generate_youtube_demo(youtube_count)
        
        all_trends = reddit_trends + youtube_trends
        
        print(f"{Fore.GREEN}[Demo] Generated {len(all_trends)} demo trends!{Style.RESET_ALL}")
        return all_trends


# Add colorama import for this module
try:
    from colorama import Fore, Style
except:
    class Fore:
        CYAN = GREEN = YELLOW = RED = ""
    class Style:
        RESET_ALL = ""


if __name__ == "__main__":
    from database import Database
    db = Database()
    generator = DemoDataGenerator(db)
    trends = generator.generate_all_demo_data()
    print(f"\nTotal demo trends: {len(trends)}")
