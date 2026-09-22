#!/usr/bin/env python3
"""
ScriptHunter - Main Entry Point
Automated daily viral script scraping tool
"""

import os
import sys
import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import List, Optional

# Force UTF-8 output for Windows console
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

# Setup path
sys.path.insert(0, str(Path(__file__).parent))

from colorama import Fore, Style, init as colorama_init
colorama_init(autoreset=True)

# Import modules
from database import Database, Trend, Script
from scrapers.reddit_scraper import RedditScraper
from scrapers.youtube_scraper import YouTubeScraper
from analyzer import HookAnalyzer
from script_generator import ScriptGenerator
from demo_data import DemoDataGenerator
from scheduler import ScriptHunterScheduler, WindowsTaskScheduler, setup_cron_windows
from config import SCRIPTS_DIR, LOGS_DIR


class ScriptHunter:
    """Main ScriptHunter orchestrator"""
    
    def __init__(self):
        self.db = Database()
        self.reddit = RedditScraper(self.db)
        self.youtube = YouTubeScraper(self.db)
        self.analyzer = HookAnalyzer(self.db)
        self.generator = ScriptGenerator(self.db)
        self.scheduler = ScriptHunterScheduler(run_callback=self.run_scrape)
    
    def scrape_trends(
        self,
        platforms: List[str] = None,
        niches: List[str] = None,
        min_viral: float = 0.3,
        use_demo: bool = False
    ) -> List[Trend]:
        """Scrape trends from platforms (or use demo data)"""
        if platforms is None:
            platforms = ["reddit"]
        
        # Use demo data if requested
        if use_demo or "demo" in platforms:
            print(f"\n{Fore.YELLOW}[ScriptHunter] Using demo data mode{Style.RESET_ALL}")
            demo_gen = DemoDataGenerator(self.db)
            all_trends = demo_gen.generate_all_demo_data(
                reddit_count=15,
                youtube_count=10
            )
        else:
            all_trends = []
            
            for platform in platforms:
                if platform == "reddit":
                    print(f"\n{Fore.CYAN}[ScriptHunter] Scraping Reddit...{Style.RESET_ALL}")
                    trends = self.reddit.scrape_all_subreddits()
                    all_trends.extend(trends)
                
                elif platform == "youtube":
                    print(f"\n{Fore.CYAN}[ScriptHunter] Scraping YouTube...{Style.RESET_ALL}")
                    trends = self.youtube.scrape_trending_all_regions()
                    all_trends.extend(trends)
        
        # Filter by niches if specified
        if niches:
            all_trends = [t for t in all_trends if t.niche in niches]
        
        # Filter by viral score
        all_trends = [t for t in all_trends if t.viral_score >= min_viral]
        
        print(f"\n{Fore.GREEN}[ScriptHunter] Found {len(all_trends)} trends (min_viral={min_viral}){Style.RESET_ALL}")
        
        return all_trends
    
    def analyze_trends(self, trends: List[Trend]) -> List:
        """Analyze trends for hook patterns"""
        print(f"\n{Fore.CYAN}[ScriptHunter] Analyzing {len(trends)} trends...{Style.RESET_ALL}")
        
        analyses = self.analyzer.analyze_trends(trends)
        
        # Rank by potential
        ranked = self.analyzer.rank_trends(trends, top_n=20)
        
        print(f"{Fore.GREEN}[ScriptHunter] Analysis complete!{Style.RESET_ALL}")
        
        return ranked
    
    def generate_scripts(
        self,
        trends: List[Trend],
        target_duration: Optional[int] = None,
        max_scripts: int = 5
    ) -> List[Script]:
        """Generate scripts từ trends"""
        print(f"\n{Fore.CYAN}[ScriptHunter] Generating scripts...{Style.RESET_ALL}")
        
        # Take top trends
        top_trends = trends[:max_scripts]
        
        scripts = self.generator.generate_batch(top_trends, target_duration)
        
        return scripts
    
    def run_scrape(
        self,
        platforms: List[str] = None,
        generate: bool = True,
        target_duration: int = 10,
        use_demo: bool = False,
        max_scripts: int = 5
    ) -> dict:
        """Run complete scrape pipeline"""
        start_time = datetime.now()
        platforms = platforms or ["reddit"]
        
        print(f"\n{'='*60}")
        print(f"{Fore.CYAN}ScriptHunter - Daily Scrape Started at {start_time.strftime('%Y-%m-%d %H:%M:%S')}{Style.RESET_ALL}")
        print(f"{'='*60}")
        
        result = {
            "started_at": start_time.isoformat(),
            "platforms": platforms,
            "trends_found": 0,
            "scripts_generated": 0,
            "status": "running",
        }
        
        try:
            # Step 1: Scrape
            trends = self.scrape_trends(platforms=platforms, use_demo=use_demo)
            result["trends_found"] = len(trends)
            
            if not trends:
                print(f"\n{Fore.YELLOW}[ScriptHunter] No trends found. Try --demo or different platforms.{Style.RESET_ALL}")
                result["status"] = "no_trends"
                return result
            
            # Step 2: Analyze and rank
            ranked = self.analyze_trends(trends)
            
            # Step 3: Generate scripts
            scripts = []
            if generate:
                scripts = self.generate_scripts(ranked, target_duration=target_duration, max_scripts=max_scripts)
                result["scripts_generated"] = len(scripts)
            
            # Log execution
            self.db.log_execution(
                run_type="scrape",
                platforms=platforms,
                trends_found=len(trends),
                scripts_generated=len(scripts) if generate else 0,
                status="success",
            )
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            print(f"\n{'='*60}")
            print(f"{Fore.GREEN}[ScriptHunter] Scrape Complete!{Style.RESET_ALL}")
            print(f"  Duration: {duration:.1f}s")
            print(f"  Trends found: {len(trends)}")
            print(f"  Scripts generated: {len(scripts) if generate else 0}")
            print(f"{'='*60}")
            
            result["status"] = "success"
            result["completed_at"] = end_time.isoformat()
            result["duration_seconds"] = duration
            
        except Exception as e:
            print(f"\n{Fore.RED}[ScriptHunter] Error: {e}{Style.RESET_ALL}")
            result["status"] = "error"
            result["error"] = str(e)
            
            self.db.log_execution(
                run_type="scrape",
                platforms=platforms,
                trends_found=0,
                scripts_generated=0,
                status="error",
                error=str(e),
            )
        
        return result
    
    def review_scripts(self, status: str = "draft", limit: int = 10) -> List[Script]:
        """Review available scripts"""
        return self.db.get_scripts(status=status, limit=limit)
    
    def export_script(self, script_id: int, format: str = "txt") -> str:
        """Export script to file"""
        script = self.db.get_script_by_id(script_id)
        
        if not script:
            print(f"{Fore.RED}[ScriptHunter] Script not found: {script_id}{Style.RESET_ALL}")
            return None
        
        # Ensure export directory exists
        export_dir = SCRIPTS_DIR / "exported"
        export_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"script_{script_id}_{timestamp}.{format}"
        filepath = export_dir / filename
        
        if format == "txt":
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"Title: {script.title}\n")
                f.write(f"Duration: {script.duration_minutes} minutes\n")
                f.write(f"Hook: {script.hook}\n")
                f.write(f"Viral Score: {script.viral_score}\n")
                f.write(f"Status: {script.status}\n")
                f.write(f"\n{'='*60}\n\n")
                f.write(script.content)
        elif format == "json":
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(script.to_dict(), f, indent=2, ensure_ascii=False)
        
        print(f"{Fore.GREEN}[ScriptHunter] Exported to: {filepath}{Style.RESET_ALL}")
        
        # Update status
        self.db.update_script_status(script_id, "reviewed")
        
        return str(filepath)
    
    def show_stats(self):
        """Show database statistics"""
        stats = self.db.get_stats()
        
        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"ScriptHunter Statistics")
        print(f"{'='*60}{Style.RESET_ALL}\n")
        
        print(f"{Fore.YELLOW}Trends by Platform:{Style.RESET_ALL}")
        for platform, count in stats.get("trends_by_platform", {}).items():
            print(f"  {platform}: {count}")
        
        print(f"\n{Fore.YELLOW}Scripts by Status:{Style.RESET_ALL}")
        for status, count in stats.get("scripts_by_status", {}).items():
            print(f"  {status}: {count}")
        
        print(f"\n{Fore.YELLOW}Top Trends:{Style.RESET_ALL}")
        for i, trend in enumerate(stats.get("top_trends", [])[:5], 1):
            print(f"  {i}. {trend['title'][:50]}... (score: {trend['viral_score']:.2f})")
        
        print(f"\n{Fore.YELLOW}Top Scripts:{Style.RESET_ALL}")
        for i, script in enumerate(stats.get("top_scripts", [])[:5], 1):
            print(f"  {i}. {script['title'][:50]}... ({script['duration_minutes']} min)")
        
        print(f"\n{Fore.YELLOW}Total:{Style.RESET_ALL}")
        print(f"  Trends: {stats.get('total_trends', 0)}")
        print(f"  Scripts: {stats.get('total_scripts', 0)}")
        
        # Show execution history
        history = self.db.get_execution_history(limit=5)
        if history:
            print(f"\n{Fore.YELLOW}Recent Runs:{Style.RESET_ALL}")
            for run in history:
                status_color = Fore.GREEN if run['status'] == 'success' else Fore.RED
                print(f"  {run['started_at'][:19]} - {status_color}{run['status']}{Style.RESET_ALL} "
                      f"(trends: {run['trends_found']}, scripts: {run['scripts_generated']})")
        
        print()
    
    def list_niches(self):
        """List available niches"""
        niches = self.db.get_niches()
        
        print(f"\n{Fore.CYAN}Available Niches:{Style.RESET_ALL}\n")
        
        for niche in niches:
            print(f"{Fore.YELLOW}{niche['name']}{Style.RESET_ALL}")
            print(f"  Description: {niche['description']}")
            print(f"  Viral Potential: {niche['viral_potential']*100:.0f}%")
            print(f"  Competition: {niche['min_competition']*100:.0f}%")
            print()
    
    def setup_scheduler(
        self,
        times: List[str] = None,
        use_windows_scheduler: bool = False
    ):
        """Setup automatic scheduling"""
        if use_windows_scheduler:
            setup_cron_windows(times)
        else:
            if times is None:
                times = ["08:00", "14:00", "20:00"]
            
            for time_str in times:
                hour, minute = map(int, time_str.split(":"))
                job_id = f"daily_{time_str.replace(':', '')}"
                self.scheduler.add_daily_job(job_id, hour, minute)
            
            self.scheduler.start(immediate=True)


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="ScriptHunter - Tool tự động cào kịch bản viral hàng ngày",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --scrape                          # Scrape với settings mặc định
  python main.py --scrape --platforms reddit youtube  # Scrape từ nhiều platforms
  python main.py --scrape --niche true_crime        # Scrape cho niche cụ thể
  python main.py --review                           # Xem các scripts đã tạo
  python main.py --export 1                         # Export script ID 1
  python main.py --stats                           # Xem thống kê
  python main.py --cron --time 08:00 14:00         # Setup scheduler
  python main.py --setup                           # Setup Windows Task Scheduler
        """
    )
    
    parser.add_argument("--scrape", action="store_true", help="Chạy scrape")
    parser.add_argument("--platforms", nargs="+", default=["reddit"],
                       help="Platforms để scrape (reddit, youtube, google_trends)")
    parser.add_argument("--niche", help="Niche cụ thể để scrape")
    parser.add_argument("--niches", nargs="+",
                       help="Nhiều niches (true_crime, what_if, science, etc.)")
    parser.add_argument("--duration", type=int, default=10,
                       help="Độ dài script target (phút, default: 10)")
    parser.add_argument("--min-viral", type=float, default=0.3,
                       help="Minimum viral score (0-1, default: 0.3)")
    parser.add_argument("--no-generate", action="store_true",
                       help="Khong generate scripts, chi scrape trends")
    parser.add_argument("--demo", action="store_true",
                       help="Su dung demo data (khong can internet)")
    parser.add_argument("--max-scripts", type=int, default=5,
                       help="So luong scripts toi da generate (default: 5)")
    
    parser.add_argument("--review", action="store_true", help="Review scripts")
    parser.add_argument("--export", type=int, help="Export script by ID")
    parser.add_argument("--format", default="txt", choices=["txt", "json"],
                       help="Export format")
    
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--niches-list", action="store_true", help="List available niches")
    
    parser.add_argument("--cron", action="store_true", help="Setup scheduler")
    parser.add_argument("--time", nargs="+", help="Thời gian chạy (VD: 08:00 14:00)")
    parser.add_argument("--setup", action="store_true", help="Setup Windows Task Scheduler")
    
    parser.add_argument("--watch", action="store_true", help="Watch mode - chạy liên tục")
    
    args = parser.parse_args()
    
    # Create ScriptHunter instance
    hunter = ScriptHunter()
    
    # Handle commands
    if args.scrape:
        niches = args.niches or ([args.niche] if args.niche else None)
        hunter.run_scrape(
            platforms=args.platforms,
            generate=not args.no_generate,
            target_duration=args.duration,
            use_demo=args.demo,
            max_scripts=args.max_scripts,
        )
    
    elif args.review:
        scripts = hunter.review_scripts(limit=20)
        
        print(f"\n{Fore.CYAN}Available Scripts (Draft):{Style.RESET_ALL}\n")
        
        if not scripts:
            print(f"{Fore.YELLOW}No draft scripts found. Run --scrape first.{Style.RESET_ALL}")
        else:
            for script in scripts:
                print(f"{Fore.YELLOW}[{script.id}] {script.title}{Style.RESET_ALL}")
                print(f"  Duration: {script.duration_minutes} min")
                print(f"  Viral Score: {script.viral_score:.2f}")
                print(f"  Hook: {script.hook[:60]}...")
                print(f"  Created: {script.created_at[:19]}")
                print()
    
    elif args.export:
        hunter.export_script(args.export, format=args.format)
    
    elif args.stats:
        hunter.show_stats()
    
    elif args.niches_list:
        hunter.list_niches()
    
    elif args.cron:
        hunter.setup_scheduler(times=args.time)
    
    elif args.setup:
        print(f"\n{Fore.CYAN}[Setup] Setting up Windows Task Scheduler...{Style.RESET_ALL}")
        setup_cron_windows(args.time or ["08:00"])
    
    elif args.watch:
        print(f"\n{Fore.CYAN}[Watch Mode] Starting continuous monitoring...{Style.RESET_ALL}")
        hunter.setup_scheduler(times=args.time or ["08:00", "14:00", "20:00"])
        
        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"\n{Fore.RED}[Watch Mode] Stopped{Style.RESET_ALL}")
            hunter.scheduler.stop()
    
    else:
        # Default: show help or stats
        parser.print_help()
        print("\n")
        hunter.show_stats()


if __name__ == "__main__":
    main()
