"""
Reddit Scraper v2 - ScriptHunter
Supports PRAW (official API) + old.reddit.com scraping + demo mode
"""

import re
import json
import time
import os
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
import sys

import requests
from bs4 import BeautifulSoup
from colorama import Fore, Style

sys.path.append(str(Path(__file__).parent.parent))
from database import Database, Trend
from config import SOURCES


class RedditScraper:
    """Scraper for Reddit with multiple fallback strategies"""
    
    def __init__(self, db: Optional[Database] = None, use_praw: bool = False):
        self.db = db or Database()
        self.config = SOURCES.get("reddit", {})
        self.use_praw = use_praw
        self.reddit = None
        self.session = self._create_session()
        
        # Try to initialize PRAW
        if use_praw:
            self._init_praw()
    
    def _init_praw(self):
        """Initialize PRAW with credentials from environment"""
        try:
            import praw
            client_id = os.getenv("REDDIT_CLIENT_ID")
            client_secret = os.getenv("REDDIT_CLIENT_SECRET")
            user_agent = os.getenv("REDDIT_USER_AGENT", "ScriptHunter/1.0")
            
            if client_id and client_secret:
                self.reddit = praw.Reddit(
                    client_id=client_id,
                    client_secret=client_secret,
                    user_agent=user_agent
                )
                print(f"{Fore.GREEN}[Reddit] PRAW initialized successfully{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}[Reddit] PRAW credentials not found. Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET{Style.RESET_ALL}")
        except ImportError:
            print(f"{Fore.YELLOW}[Reddit] PRAW not installed. Run: pip install praw{Style.RESET_ALL}")
    
    def _create_session(self) -> requests.Session:
        """Create session with realistic headers"""
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; ScriptHunter/1.0; +https://github.com/scripthunter)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        })
        return session
    
    def get_hot_posts(self, subreddit: str, limit: int = 25) -> List[Dict]:
        """Get hot posts with multiple fallback strategies"""
        # Strategy 1: Try PRAW
        if self.reddit:
            posts = self._get_praw_posts(subreddit, limit, "hot")
            if posts:
                return posts
        
        # Strategy 2: Try old.reddit.com HTML
        posts = self._get_old_reddit_posts(subreddit, limit, sort="hot")
        if posts:
            return posts
        
        # Strategy 3: Try JSON endpoint with different approach
        posts = self._get_json_endpoint(subreddit, limit, sort="hot")
        return posts
    
    def get_rising_posts(self, subreddit: str, limit: int = 25) -> List[Dict]:
        """Get rising posts"""
        if self.reddit:
            posts = self._get_praw_posts(subreddit, limit, "rising")
            if posts:
                return posts
        
        posts = self._get_old_reddit_posts(subreddit, limit, sort="rising")
        if posts:
            return posts
        
        posts = self._get_json_endpoint(subreddit, limit, sort="rising")
        return posts
    
    def get_top_posts(self, subreddit: str, limit: int = 25, timeframe: str = "week") -> List[Dict]:
        """Get top posts"""
        if self.reddit:
            posts = self._get_praw_posts(subreddit, limit, "top", time_filter=timeframe)
            if posts:
                return posts
        
        posts = self._get_old_reddit_posts(subreddit, limit, sort="top", t=timeframe)
        return posts
    
    def _get_praw_posts(
        self, 
        subreddit: str, 
        limit: int, 
        sort: str, 
        time_filter: str = "week"
    ) -> List[Dict]:
        """Fetch posts using PRAW (official API)"""
        try:
            sub = self.reddit.subreddit(subreddit)
            
            if sort == "hot":
                submissions = sub.hot(limit=limit)
            elif sort == "rising":
                submissions = sub.rising(limit=limit)
            elif sort == "top":
                submissions = sub.top(limit=limit, time_filter=time_filter)
            elif sort == "new":
                submissions = sub.new(limit=limit)
            else:
                submissions = sub.hot(limit=limit)
            
            posts = []
            for submission in submissions:
                post = self._parse_praw_post(submission, subreddit)
                if self._is_valid_post(post):
                    posts.append(post)
            
            return posts
        except Exception as e:
            print(f"{Fore.RED}[Reddit PRAW] Error: {e}{Style.RESET_ALL}")
            return []
    
    def _parse_praw_post(self, submission, subreddit: str) -> Dict:
        """Parse PRAW submission"""
        score = submission.score
        num_comments = submission.num_comments
        engagement_rate = (score + num_comments * 2) / max(score, 1)
        
        return {
            "source_id": submission.id,
            "platform": "reddit",
            "title": submission.title,
            "content": submission.selftext if submission.is_self else "",
            "url": f"https://reddit.com{submission.permalink}",
            "author": str(submission.author) if submission.author else "[deleted]",
            "subreddit": f"r/{subreddit}",
            "score": score,
            "comments": num_comments,
            "engagement_rate": engagement_rate,
            "created_utc": submission.created_utc,
            "content_type": "general",
            "is_video": submission.is_video,
            "over_18": submission.over_18,
            "link_flair_text": submission.link_flair_text or "",
            "award_count": submission.total_awards_received,
        }
    
    def _get_old_reddit_posts(
        self, 
        subreddit: str, 
        limit: int, 
        sort: str = "hot",
        t: str = "week"
    ) -> List[Dict]:
        """Scrape old.reddit.com (more permissive)"""
        url = f"https://old.reddit.com/r/{subreddit}/{sort}/"
        params = {"limit": min(limit, 25)}
        if sort == "top":
            params["t"] = t
        
        try:
            response = self.session.get(url, params=params, timeout=20)
            
            if response.status_code != 200:
                return []
            
            soup = BeautifulSoup(response.text, "lxml")
            posts = []
            
            # Find all post divs
            post_divs = soup.find_all("div", class_="thing", limit=limit)
            
            for post_div in post_divs:
                try:
                    post = self._parse_old_reddit_post(post_div, subreddit)
                    if self._is_valid_post(post):
                        posts.append(post)
                except Exception as e:
                    continue
            
            return posts
            
        except Exception as e:
            return []
    
    def _parse_old_reddit_post(self, post_div, subreddit: str) -> Dict:
        """Parse post from old.reddit.com HTML"""
        # Get post ID
        post_id = post_div.get("data-fullname", "").split("_")[-1]
        
        # Get title
        title_elem = post_div.find("a", class_="title")
        title = title_elem.get_text(strip=True) if title_elem else ""
        url = title_elem.get("href", "") if title_elem else ""
        
        if url and not url.startswith("http"):
            url = f"https://old.reddit.com{url}"
        
        # Get score
        score = 0
        score_elem = post_div.find("div", class_="score")
        if score_elem:
            score_text = score_elem.get("title", "0").replace(",", "")
            try:
                score = int(score_text)
            except:
                score = 0
        
        # Get comments count
        comments = 0
        comments_elem = post_div.find("a", class_="comments")
        if comments_elem:
            comments_text = comments_elem.get_text(strip=True)
            num_match = re.search(r'(\d+)', comments_text)
            if num_match:
                comments = int(num_match.group(1))
        
        # Get author
        author = "[deleted]"
        author_elem = post_div.find("a", class_="author")
        if author_elem:
            author = author_elem.get_text(strip=True)
        
        # Get content (self posts)
        content = ""
        content_elem = post_div.find("div", class_="usertext-body")
        if content_elem:
            content = content_elem.get_text(strip=True)[:500]
        
        # Get timestamp
        timestamp = post_div.find("time")
        created_utc = 0
        if timestamp and timestamp.get("datetime"):
            try:
                from datetime import datetime as dt
                dt_obj = dt.fromisoformat(timestamp["datetime"].replace("Z", "+00:00"))
                created_utc = dt_obj.timestamp()
            except:
                pass
        
        # Get flair
        flair = ""
        flair_elem = post_div.find("span", class_="linkflairlabel")
        if flair_elem:
            flair = flair_elem.get_text(strip=True)
        
        # Get subreddit from post
        sub_elem = post_div.find("a", class_="subreddit")
        sub = subreddit
        if sub_elem:
            sub_text = sub_elem.get_text(strip=True)
            if sub_text:
                sub = sub_text.replace("r/", "")
        
        # Engagement rate
        engagement_rate = (score + comments * 2) / max(score, 1) if score > 0 else 0
        
        return {
            "source_id": post_id,
            "platform": "reddit",
            "title": title,
            "content": content,
            "url": url or f"https://old.reddit.com/r/{subreddit}/comments/{post_id}",
            "author": author,
            "subreddit": f"r/{sub}",
            "score": score,
            "comments": comments,
            "engagement_rate": engagement_rate,
            "created_utc": created_utc,
            "content_type": self._detect_content_type_from_text(title + " " + content),
            "is_video": False,
            "over_18": "nsfw" in post_div.get("class", []),
            "link_flair_text": flair,
            "award_count": 0,
        }
    
    def _get_json_endpoint(
        self, 
        subreddit: str, 
        limit: int, 
        sort: str = "hot"
    ) -> List[Dict]:
        """Try JSON endpoint with custom headers"""
        url = f"https://www.reddit.com/r/{subreddit}/{sort}.json"
        params = {"limit": limit}
        
        # Add additional headers to bypass 403
        headers = self.session.headers.copy()
        headers.update({
            "Accept": "application/json",
            "Referer": f"https://www.reddit.com/r/{subreddit}/",
            "Origin": "https://www.reddit.com",
        })
        
        try:
            response = self.session.get(url, params=params, headers=headers, timeout=15)
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            posts = []
            
            for child in data.get("data", {}).get("children", []):
                post = child.get("data", {})
                if self._is_valid_post(post):
                    parsed = self._parse_json_post(post, subreddit)
                    posts.append(parsed)
            
            return posts
            
        except Exception as e:
            return []
    
    def _parse_json_post(self, post: Dict, subreddit: str) -> Dict:
        """Parse JSON endpoint post"""
        score = post.get("score", 0)
        num_comments = post.get("num_comments", 0)
        engagement_rate = (score + num_comments * 2) / max(score, 1)
        
        return {
            "source_id": post.get("id", ""),
            "platform": "reddit",
            "title": post.get("title", ""),
            "content": post.get("selftext", ""),
            "url": f"https://reddit.com{post.get('permalink', '')}",
            "author": post.get("author", ""),
            "subreddit": f"r/{subreddit}",
            "score": score,
            "comments": num_comments,
            "engagement_rate": engagement_rate,
            "created_utc": post.get("created_utc", 0),
            "content_type": "general",
            "is_video": post.get("is_video", False),
            "over_18": post.get("over_18", False),
            "link_flair_text": post.get("link_flair_text", ""),
            "award_count": post.get("total_awards_received", 0),
        }
    
    def _is_valid_post(self, post: Dict) -> bool:
        """Check if post meets criteria"""
        min_score = self.config.get("min_score", 1000)
        
        # Accept if from PRAW (no min_score filtering for low-engagement niches)
        if isinstance(post, dict) and post.get("source_id") and not post.get("score"):
            return True
        
        if post.get("score", 0) < min_score:
            return False
        
        # Check age
        max_age = self.config.get("max_age_days", 7)
        created_utc = post.get("created_utc", 0)
        if created_utc > 0:
            post_age = datetime.now().timestamp() - created_utc
            if post_age > (max_age * 24 * 3600):
                return False
        
        return True
    
    def _detect_content_type_from_text(self, text: str) -> str:
        """Detect content type from text"""
        text_lower = text.lower()
        
        if any(kw in text_lower for kw in ["murder", "killing", "death", "mystery", "unsolved", "crime", "victim"]):
            return "true_crime"
        elif any(kw in text_lower for kw in ["history", "ancient", "war", "century", "what if"]):
            return "history_whatif"
        elif any(kw in text_lower for kw in ["science", "research", "study", "discovery"]):
            return "science"
        elif any(kw in text_lower for kw in ["ai", "technology", "tech", "robot"]):
            return "technology"
        elif any(kw in text_lower for kw in ["engineering", "engineer", "bridge", "construction"]):
            return "engineering"
        elif any(kw in text_lower for kw in ["story", "happened", "experience", "tifu"]):
            return "story"
        
        return "general"
    
    def calculate_viral_score(self, post: Dict) -> float:
        """Calculate viral score"""
        score = post.get("score", 0)
        comments = post.get("comments", 0)
        engagement_rate = post.get("engagement_rate", 1.0)
        award_count = post.get("award_count", 0)
        
        import math
        norm_score = math.log10(max(score, 1)) / 6
        norm_comments = math.log10(max(comments, 1)) / 5
        
        engagement_bonus = min(engagement_rate / 3, 1.5) if engagement_rate > 1 else 0.5
        award_bonus = 1 + (award_count * 0.1)
        
        viral = (norm_score * 0.4 + norm_comments * 0.3 + engagement_bonus * 0.3) * award_bonus
        
        return round(min(viral, 1.0), 3)
    
    def detect_hook_type(self, post: Dict) -> str:
        """Detect hook type from title"""
        title = post.get("title", "").lower()
        
        hooks = {
            "contrarian": ["everyone says", "they don't want", "stop", "wrong", "lie", "myth", "actually"],
            "curiosity_gap": ["secret", "hidden", "buried", "they don't want", "real reason"],
            "shocking_stat": ["%", "percent", "statistic", "study", "research"],
            "story_open": ["story", "happened to me", "when i", "tifu", "confession"],
            "question": ["why", "how to", "what if", "should i", "?"],
            "pattern_interrupt": ["nsfw", "sfw", "oc", "mildly"],
            "pov": ["pov:", "when you", "as a"],
            "mystery": ["mystery", "unsolved", "disappeared", "nobody knows"],
            "timeline": ["what happened", "then", "after"],
            "comparison": [" vs ", "versus", "compared to"],
        }
        
        for hook_type, keywords in hooks.items():
            if any(kw in title for kw in keywords):
                return hook_type
        
        return "general"
    
    def match_niche(self, post: Dict) -> str:
        """Match post to niche"""
        content_type = post.get("content_type", "general")
        
        niche_map = {
            "true_crime": "true_crime",
            "history_whatif": "what_if",
            "science": "science_explained",
            "technology": "ai_workflows",
            "engineering": "engineering_fails",
            "story": "story",
        }
        
        return niche_map.get(content_type, "general")
    
    def scrape_all_subreddits(self) -> List[Trend]:
        """Scrape all configured subreddits"""
        all_trends = []
        subreddits = self.config.get("subreddits", [])
        
        # Deduplicate
        subreddits = list(dict.fromkeys(subreddits))
        
        print(f"\n{Fore.CYAN}[Reddit] Scraping {len(subreddits)} subreddits...{Style.RESET_ALL}")
        
        for i, subreddit in enumerate(subreddits):
            sub = subreddit.replace("r/", "")
            print(f"{Fore.YELLOW}  [{i+1}/{len(subreddits)}] r/{sub}{Style.RESET_ALL}")
            
            posts = self.get_hot_posts(sub, limit=15)
            rising = self.get_rising_posts(sub, limit=10)
            posts.extend(rising)
            
            for post in posts:
                post["content_type"] = self._detect_content_type_from_text(
                    post.get("title", "") + " " + post.get("content", "")
                )
                post["viral_score"] = self.calculate_viral_score(post)
                post["hook_type"] = self.detect_hook_type(post)
                post["niche"] = self.match_niche(post)
                
                trend = Trend(
                    platform="reddit",
                    source_id=post["source_id"],
                    title=post["title"],
                    content=post.get("content", ""),
                    url=post["url"],
                    author=post.get("author", ""),
                    score=post.get("score", 0),
                    comments=post.get("comments", 0),
                    engagement_rate=post.get("engagement_rate", 0),
                    viral_score=post["viral_score"],
                    hook_type=post["hook_type"],
                    niche=post["niche"],
                    tags=json.dumps({
                        "subreddit": post.get("subreddit", "r/" + sub),
                        "content_type": post["content_type"]
                    }),
                    created_at=datetime.fromtimestamp(post.get("created_utc", 0)).isoformat() 
                        if post.get("created_utc") else "",
                )
                
                self.db.save_trend(trend)
                all_trends.append(trend)
            
            time.sleep(0.5)
        
        print(f"{Fore.GREEN}[Reddit] Found {len(all_trends)} trending posts!{Style.RESET_ALL}")
        return all_trends
    
    def scrape_keywords(self, keywords: List[str]) -> List[Trend]:
        """Scrape by keywords"""
        all_trends = []
        
        for keyword in keywords:
            # Search Reddit
            url = "https://old.reddit.com/search/"
            params = {"q": keyword, "sort": "relevance", "t": "week", "restrict_sr": ""}
            
            try:
                response = self.session.get(url, params=params, timeout=15)
                if response.status_code != 200:
                    continue
                
                soup = BeautifulSoup(response.text, "lxml")
                posts = soup.find_all("div", class_="thing", limit=20)
                
                for post_div in posts:
                    try:
                        # Determine subreddit
                        sub_elem = post_div.find("a", class_="subreddit")
                        sub = "all"
                        if sub_elem:
                            sub = sub_elem.get_text(strip=True).replace("r/", "")
                        
                        post = self._parse_old_reddit_post(post_div, sub)
                        post["content_type"] = self._detect_content_type_from_text(
                            post.get("title", "") + " " + post.get("content", "")
                        )
                        post["viral_score"] = self.calculate_viral_score(post)
                        post["hook_type"] = self.detect_hook_type(post)
                        post["niche"] = self.match_niche(post)
                        
                        trend = Trend(
                            platform="reddit",
                            source_id=post["source_id"],
                            title=post["title"],
                            content=post.get("content", ""),
                            url=post["url"],
                            author=post.get("author", ""),
                            score=post.get("score", 0),
                            comments=post.get("comments", 0),
                            engagement_rate=post.get("engagement_rate", 0),
                            viral_score=post["viral_score"],
                            hook_type=post["hook_type"],
                            niche=post["niche"],
                            tags=json.dumps({"keyword": keyword}),
                            created_at=datetime.fromtimestamp(post.get("created_utc", 0)).isoformat() 
                                if post.get("created_utc") else "",
                        )
                        
                        self.db.save_trend(trend)
                        all_trends.append(trend)
                    except Exception as e:
                        continue
                
                time.sleep(1)
            except Exception as e:
                continue
        
        return all_trends


if __name__ == "__main__":
    scraper = RedditScraper()
    trends = scraper.scrape_all_subreddits()
    print(f"\nTotal trends: {len(trends)}")
