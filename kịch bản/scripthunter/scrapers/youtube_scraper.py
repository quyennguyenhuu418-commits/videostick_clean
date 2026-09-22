"""
YouTube Scraper - ScriptHunter
Cào trend từ YouTube trending pages và search
"""

import re
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from pathlib import Path
import sys

import requests
from bs4 import BeautifulSoup
from colorama import Fore, Style

sys.path.append(str(Path(__file__).parent.parent))
from database import Database, Trend
from config import SOURCES


class YouTubeScraper:
    """Scraper cho YouTube - lấy trending videos và search results"""
    
    BASE_URL = "https://www.youtube.com"
    TRENDING_URL = "https://www.youtube.com/feed/trending"
    API_URL = "https://www.googleapis.com/youtube/v3"
    
    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database()
        self.config = SOURCES.get("youtube", {})
        self.api_key = self.config.get("api_key", "")
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """Tạo session với headers realistic"""
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        })
        return session
    
    def get_trending(self, region: str = "US", category: str = "") -> List[Dict]:
        """Lấy trending videos"""
        if self.api_key:
            return self._get_trending_api(region, category)
        else:
            return self._get_trending_scrape(region)
    
    def _get_trending_api(self, region: str = "US", category: str = "") -> List[Dict]:
        """Lấy trending qua YouTube Data API"""
        if not self.api_key:
            return []
        
        videos = []
        
        # Get trending video IDs
        params = {
            "part": "snippet",
            "chart": "mostPopular",
            "regionCode": region,
            "maxResults": 50,
            "key": self.api_key
        }
        
        if category:
            params["videoCategoryId"] = category
        
        try:
            response = requests.get(f"{self.API_URL}/videos", params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            for item in data.get("items", []):
                video = self._parse_api_video(item)
                if self._is_valid_video(video):
                    videos.append(video)
                    
        except Exception as e:
            print(f"{Fore.RED}[YouTube API] Error: {e}{Style.RESET_ALL}")
        
        return videos
    
    def _get_trending_scrape(self, region: str = "US") -> List[Dict]:
        """Lấy trending bằng scraping (fallback)"""
        videos = []
        
        # Map region to URL param
        region_map = {
            "US": "US", "GB": "GB", "VN": "VN", "DE": "DE",
            "JP": "JP", "KR": "KR", "IN": "IN", "AU": "AU"
        }
        hl = region_map.get(region, "US")
        
        url = f"{self.BASE_URL.com}/feed/trending?gl={region}&hl=en"
        
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            # Extract video data from page
            # YouTube uses ytInitialData JSON in the page
            pattern = r'ytInitialData\s*=\s*({.*?});'
            match = re.search(pattern, response.text, re.DOTALL)
            
            if match:
                data = json.loads(match.group(1))
                contents = data.get("contents", {}).get("twoColumnBrowseResultsRenderer", {})
                
                for tab in contents.get("tabs", []):
                    tab_content = tab.get("tabRenderer", {}).get("content", {})
                    section_list = tab_content.get("sectionListRenderer", {}).get("contents", [])
                    
                    for section in section_list:
                        items = section.get("itemSectionRenderer", {}).get("contents", [])
                        
                        for item in items:
                            video_renderer = item.get("videoRenderer", {})
                            if video_renderer:
                                video = self._parse_renderer_video(video_renderer)
                                if self._is_valid_video(video):
                                    videos.append(video)
            
        except Exception as e:
            print(f"{Fore.RED}[YouTube Scrape] Error: {e}{Style.RESET_ALL}")
        
        return videos
    
    def search_videos(self, query: str, limit: int = 20) -> List[Dict]:
        """Tìm kiếm videos"""
        videos = []
        
        if self.api_key:
            # Use API
            params = {
                "part": "snippet",
                "q": query,
                "type": "video",
                "order": "relevance",
                "maxResults": limit,
                "key": self.api_key
            }
            
            try:
                response = requests.get(f"{self.API_URL}/search", params=params, timeout=15)
                response.raise_for_status()
                data = response.json()
                
                # Get video IDs
                video_ids = [item["id"]["videoId"] for item in data.get("items", []) 
                           if item["id"].get("videoId")]
                
                # Get video details
                if video_ids:
                    details = self._get_video_details(video_ids)
                    for item in data.get("items", []):
                        video_id = item.get("id", {}).get("videoId")
                        if video_id in details:
                            video = self._merge_search_and_details(item, details[video_id])
                            if self._is_valid_video(video):
                                videos.append(video)
                                
            except Exception as e:
                print(f"{Fore.RED}[YouTube Search] API Error: {e}{Style.RESET_ALL}")
        else:
            # Fallback to scraping
            videos = self._search_scrape(query, limit)
        
        return videos
    
    def _search_scrape(self, query: str, limit: int = 20) -> List[Dict]:
        """Search bằng scraping"""
        videos = []
        url = f"{self.BASE_URL}/results"
        params = {"search_query": query, "sp": "CAI%253D"}
        
        try:
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            
            # Extract ytInitialData
            pattern = r'ytInitialData\s*=\s*({.*?});'
            match = re.search(pattern, response.text, re.DOTALL)
            
            if match:
                data = json.loads(match.group(1))
                results = data.get("contents", {}).get("twoColumnSearchResultsRenderer", {})
                
                for section in results.get("primaryContents", {}).get("sectionListRenderer", {}).get("contents", []):
                    items = section.get("itemSectionRenderer", {}).get("contents", [])
                    
                    for item in items:
                        video_renderer = item.get("videoRenderer", {})
                        if video_renderer and len(videos) < limit:
                            video = self._parse_renderer_video(video_renderer)
                            if self._is_valid_video(video):
                                videos.append(video)
                                
        except Exception as e:
            print(f"{Fore.RED}[YouTube Search] Scrape Error: {e}{Style.RESET_ALL}")
        
        return videos
    
    def _get_video_details(self, video_ids: List[str]) -> Dict[str, Dict]:
        """Lấy video details từ IDs"""
        if not self.api_key or not video_ids:
            return {}
        
        details = {}
        # YouTube API allows max 50 IDs per request
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i:i+50]
            params = {
                "part": "statistics,contentDetails",
                "id": ",".join(batch),
                "key": self.api_key
            }
            
            try:
                response = requests.get(f"{self.API_URL}/videos", params=params, timeout=15)
                data = response.json()
                
                for item in data.get("items", []):
                    video_id = item["id"]
                    details[video_id] = {
                        "view_count": int(item.get("statistics", {}).get("viewCount", 0)),
                        "like_count": int(item.get("statistics", {}).get("likeCount", 0)),
                        "comment_count": int(item.get("statistics", {}).get("commentCount", 0)),
                        "duration": item.get("contentDetails", {}).get("duration", ""),
                    }
            except Exception as e:
                print(f"{Fore.RED}[YouTube Details] Error: {e}{Style.RESET_ALL}")
        
        return details
    
    def _parse_api_video(self, item: Dict) -> Dict:
        """Parse video từ API response"""
        snippet = item.get("snippet", {})
        video_id = item.get("id", "")
        
        return {
            "video_id": video_id,
            "title": snippet.get("title", ""),
            "description": snippet.get("description", ""),
            "channel_title": snippet.get("channelTitle", ""),
            "channel_id": snippet.get("channelId", ""),
            "published_at": snippet.get("publishedAt", ""),
            "tags": snippet.get("tags", []),
            "category_id": snippet.get("categoryId", ""),
            "thumbnail": snippet.get("thumbnails", {}).get("medium", {}).get("url", ""),
            "view_count": 0,
            "like_count": 0,
            "comment_count": 0,
            "duration": "",
            "url": f"https://youtube.com/watch?v={video_id}",
        }
    
    def _parse_renderer_video(self, renderer: Dict) -> Dict:
        """Parse video từ YouTube renderer"""
        video_id = renderer.get("videoId", "")
        
        # Get view count
        view_text = ""
        view_runs = renderer.get("viewCountText", {}).get("runs", [])
        if view_runs:
            view_text = view_runs[0].get("text", "")
        
        # Parse view count
        view_count = self._parse_view_count(view_text)
        
        # Get published time
        published_text = ""
        published_runs = renderer.get("publishedTimeText", {}).get("runs", [])
        if published_runs:
            published_text = published_runs[0].get("text", "")
        
        # Get description snippet
        description = ""
        desc_runs = renderer.get("descriptionSnippet", {}).get("runs", [])
        for run in desc_runs:
            description += run.get("text", "")
        
        # Get channel
        channel = renderer.get("longBylineText", {}).get("runs", [])
        channel_title = channel[0].get("text", "") if channel else ""
        channel_id = channel[0].get("navigationEndpoint", {}).get("browseEndpoint", {}).get("browseId", "")
        
        # Get thumbnail
        thumbnails = renderer.get("thumbnail", {}).get("thumbnails", [])
        thumbnail = thumbnails[-1].get("url", "") if thumbnails else ""
        
        return {
            "video_id": video_id,
            "title": renderer.get("title", {}).get("runs", [{}])[0].get("text", ""),
            "description": description,
            "channel_title": channel_title,
            "channel_id": channel_id,
            "published_at": "",
            "published_text": published_text,
            "tags": [],
            "category_id": renderer.get("categoryLabel", ""),
            "thumbnail": thumbnail,
            "view_count": view_count,
            "like_count": 0,
            "comment_count": 0,
            "duration": "",
            "url": f"https://youtube.com/watch?v={video_id}",
            "short_view_count_text": view_text,
        }
    
    def _merge_search_and_details(self, search_item: Dict, details: Dict) -> Dict:
        """Merge search result với details"""
        video = self._parse_api_video(search_item.get("snippet", {}))
        video["video_id"] = search_item.get("id", {}).get("videoId", "")
        video["url"] = f"https://youtube.com/watch?v={video['video_id']}"
        video.update(details)
        return video
    
    def _parse_view_count(self, text: str) -> int:
        """Parse view count từ text"""
        if not text:
            return 0
        
        # Remove "No views" or similar
        text = text.lower().replace(" views", "").replace("view", "").strip()
        
        multipliers = {"k": 1000, "m": 1000000, "b": 1000000000}
        
        try:
            if any(m in text for m in multipliers):
                num = float(re.sub(r'[^\d.]', '', text))
                for m, mult in multipliers.items():
                    if m in text:
                        return int(num * mult)
            return int(float(re.sub(r'[^\d.]', '', text)))
        except:
            return 0
    
    def _is_valid_video(self, video: Dict) -> bool:
        """Kiểm tra video có đủ điều kiện"""
        min_views = self.config.get("min_views", 10000)
        
        if video.get("view_count", 0) < min_views:
            return False
        
        if not video.get("title"):
            return False
        
        # Skip shorts for now (we want longer content)
        if "shorts" in video.get("url", ""):
            return False
        
        return True
    
    def calculate_viral_score(self, video: Dict) -> float:
        """Tính viral score cho video"""
        views = video.get("view_count", 0)
        likes = video.get("like_count", 0)
        comments = video.get("comment_count", 0)
        
        import math
        
        # Normalize views (log scale)
        norm_views = math.log10(max(views, 1)) / 9  # Rough 0-1 scale
        
        # Engagement rates
        if views > 0:
            like_rate = likes / views
            comment_rate = comments / views
        else:
            like_rate = comment_rate = 0
        
        # Engagement bonus (higher engagement = better)
        engagement = (like_rate * 100 + comment_rate * 1000) / 10
        
        # Calculate score
        viral = (norm_views * 0.6 + min(engagement, 1) * 0.4)
        
        return round(viral, 3)
    
    def detect_hook_type(self, video: Dict) -> str:
        """Detect hook type từ title"""
        title = video.get("title", "").lower()
        
        hooks = {
            "contrarian": ["stop", "wrong", "don't", "mistake", "actually", "truth",
                          "everyone is wrong", "you're doing it wrong"],
            "curiosity_gap": ["secret", "they don't want you", "hidden", "buried",
                            "what they don't show", "the truth about"],
            "shocking_stat": ["percent", "out of", "chance in", "1 in", " statistic",
                            "study reveals", "research shows"],
            "story_open": ["story", "happened", "when i", "i was", "this is what",
                          "what i learned", "my experience"],
            "question": ["why", "how to", "what if", "can you", "should you",
                        "does this", "what happens"],
            "timeline": ["what happened", "timeline", "chronological", "step by step",
                        "the story of", "history of", "origin"],
            "mystery": ["mystery", "unsolved", "explained", "discovered", "why did",
                       "how did", "revealed", "finally"],
            "comparison": ["vs", "versus", "compared", "difference", "better than",
                          "worst", "best", "top"],
            "list": ["top", "best", "worst", "10", "5 ", " reasons", "ways to",
                    "things you", "things about"],
            "reaction": ["react", "reaction", "response", "watching", "trying",
                        "testing", "review"],
        }
        
        for hook_type, keywords in hooks.items():
            if any(kw in title for kw in keywords):
                return hook_type
        
        return "general"
    
    def match_niche(self, video: Dict) -> str:
        """Match video với niche"""
        title = video.get("title", "").lower()
        description = video.get("description", "").lower()
        category = video.get("category_id", "").lower()
        combined = f"{title} {description} {category}"
        
        # True Crime
        crime_keywords = ["murder", "crime", "mystery", "investigation", "killing",
                         "disappeared", "cold case", "unsolved", "detective"]
        if any(kw in combined for kw in crime_keywords):
            return "true_crime"
        
        # History / What-If
        history_keywords = ["history", "ancient", "war", "empire", "story of",
                          "what if", "history of", "origin", "timeline"]
        if any(kw in combined for kw in history_keywords):
            return "what_if"
        
        # Science
        science_keywords = ["science", "physics", "biology", "space", "universe",
                          "experiment", "discovery", "nasa", "earth"]
        if any(kw in combined for kw in science_keywords):
            return "science_explained"
        
        # AI / Tech
        tech_keywords = ["ai", "chatgpt", "technology", "robot", "software",
                        "computer", "tech", "app", "automation"]
        if any(kw in combined for kw in tech_keywords):
            return "ai_workflows"
        
        # Engineering
        eng_keywords = ["engineering", "engineer", "built", "construction",
                       "design", "architecture", "structure", "failure"]
        if any(kw in combined for kw in eng_keywords):
            return "engineering_fails"
        
        # Cooking
        cook_keywords = ["recipe", "cooking", "food", "cook", "kitchen", "make"]
        if any(kw in combined for kw in cook_keywords):
            return "village_cooking"
        
        return "general"
    
    def scrape_trending_all_regions(self) -> List[Trend]:
        """Scrape trending từ tất cả regions"""
        all_trends = []
        regions = self.config.get("regions", ["US", "VN", "GB"])
        
        print(f"\n{Fore.CYAN}[YouTube] Scraping trending from {len(regions)} regions...{Style.RESET_ALL}")
        
        for region in regions:
            print(f"{Fore.YELLOW}  Scraping region: {region}{Style.RESET_ALL}")
            
            videos = self.get_trending(region=region)
            
            for video in videos:
                viral_score = self.calculate_viral_score(video)
                hook_type = self.detect_hook_type(video)
                niche = self.match_niche(video)
                
                trend = Trend(
                    platform="youtube",
                    source_id=video["video_id"],
                    title=video["title"],
                    content=video.get("description", ""),
                    url=video["url"],
                    author=video.get("channel_title", ""),
                    score=video.get("view_count", 0),
                    comments=video.get("comment_count", 0),
                    views=video.get("view_count", 0),
                    viral_score=viral_score,
                    hook_type=hook_type,
                    niche=niche,
                    tags=json.dumps({
                        "region": region,
                        "category": video.get("category_id", ""),
                        "duration": video.get("duration", "")
                    }),
                    created_at=video.get("published_at", ""),
                )
                
                self.db.save_trend(trend)
                all_trends.append(trend)
            
            time.sleep(1)
        
        print(f"{Fore.GREEN}[YouTube] Found {len(all_trends)} trending videos!{Style.RESET_ALL}")
        return all_trends
    
    def scrape_niche_keywords(self, keywords: List[str]) -> List[Trend]:
        """Scrape videos theo keywords cho niche"""
        all_trends = []
        
        print(f"\n{Fore.CYAN}[YouTube] Searching keywords: {keywords}{Style.RESET_ALL}")
        
        for keyword in keywords:
            videos = self.search_videos(keyword, limit=20)
            
            for video in videos:
                viral_score = self.calculate_viral_score(video)
                hook_type = self.detect_hook_type(video)
                niche = self.match_niche(video)
                
                trend = Trend(
                    platform="youtube",
                    source_id=video["video_id"],
                    title=video["title"],
                    content=video.get("description", ""),
                    url=video["url"],
                    author=video.get("channel_title", ""),
                    score=video.get("view_count", 0),
                    comments=video.get("comment_count", 0),
                    views=video.get("view_count", 0),
                    viral_score=viral_score,
                    hook_type=hook_type,
                    niche=niche,
                    tags=json.dumps({"keyword": keyword}),
                    created_at=video.get("published_at", ""),
                )
                
                self.db.save_trend(trend)
                all_trends.append(trend)
            
            time.sleep(1)
        
        return all_trends


if __name__ == "__main__":
    scraper = YouTubeScraper()
    trends = scraper.scrape_trending_all_regions()
    print(f"\nTotal trends: {len(trends)}")
