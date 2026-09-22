"""
Scheduler - ScriptHunter
Cấu hình cron job tự động chạy hàng ngày
"""

import time
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Callable
import sys

from colorama import Fore, Style, init as colorama_init
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

sys.path.append(str(Path(__file__).parent.parent))
from config import CRON_CONFIG, LOG_FILE, LOG_LEVEL, LOG_FORMAT


# Initialize colorama
colorama_init(autoreset=True)


class ScriptHunterScheduler:
    """Scheduler cho ScriptHunter - chạy tự động theo lịch"""
    
    def __init__(self, run_callback: Optional[Callable] = None):
        self.scheduler = BackgroundScheduler(timezone="Asia/Ho_Chi_Minh")
        self.run_callback = run_callback
        self.logger = self._setup_logger()
        self.is_running = False
        self._setup_logging()
    
    def _setup_logger(self) -> logging.Logger:
        """Setup logger"""
        logger = logging.getLogger("ScriptHunter.Scheduler")
        logger.setLevel(getattr(logging, LOG_LEVEL))
        
        # File handler
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(LOG_FILE)
        fh.setLevel(logging.DEBUG)
        
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(LOG_FORMAT)
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        logger.addHandler(fh)
        logger.addHandler(ch)
        
        return logger
    
    def _setup_logging(self):
        """Setup basic logging"""
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            level=getattr(logging, LOG_LEVEL),
            format=LOG_FORMAT,
            handlers=[
                logging.FileHandler(LOG_FILE),
                logging.StreamHandler()
            ]
        )
    
    def add_daily_job(
        self,
        job_id: str,
        hour: int = 8,
        minute: int = 0,
        platforms: Optional[List[str]] = None
    ):
        """Thêm job chạy hàng ngày vào giờ cố định"""
        trigger = CronTrigger(hour=hour, minute=minute)
        
        self.scheduler.add_job(
            func=self._run_with_params,
            trigger=trigger,
            id=job_id,
            name=f"Daily ScriptHunter ({hour:02d}:{minute:02d})",
            args=[platforms or ["reddit", "google_trends"]],
            replace_existing=True
        )
        
        self.logger.info(f"Added daily job: {job_id} at {hour:02d}:{minute:02d}")
    
    def add_interval_job(
        self,
        job_id: str,
        hours: int = 6,
        platforms: Optional[List[str]] = None
    ):
        """Thêm job chạy theo interval"""
        trigger = IntervalTrigger(hours=hours)
        
        self.scheduler.add_job(
            func=self._run_with_params,
            trigger=trigger,
            id=job_id,
            name=f"Interval ScriptHunter (every {hours}h)",
            args=[platforms or ["reddit"]],
            replace_existing=True
        )
        
        self.logger.info(f"Added interval job: {job_id} every {hours} hours")
    
    def _run_with_params(self, platforms: List[str]):
        """Wrapper để chạy với params"""
        self.logger.info(f"Starting scheduled run for platforms: {platforms}")
        
        try:
            if self.run_callback:
                result = self.run_callback(platforms=platforms)
                self.logger.info(f"Scheduled run completed: {result}")
            else:
                self.logger.warning("No run callback configured")
        except Exception as e:
            self.logger.error(f"Scheduled run failed: {e}")
    
    def start(self, immediate: bool = False):
        """Bắt đầu scheduler"""
        if self.is_running:
            self.logger.warning("Scheduler already running")
            return
        
        self.scheduler.start()
        self.is_running = True
        
        print(f"{Fore.GREEN}[Scheduler] ScriptHunter Scheduler started!{Style.RESET_ALL}")
        print(f"{Fore.CYAN}[Scheduler] Jobs scheduled:{Style.RESET_ALL}")
        
        for job in self.scheduler.get_jobs():
            print(f"  • {job.name} (ID: {job.id})")
            next_run = job.next_run_time
            if next_run:
                print(f"    Next run: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if immediate:
            print(f"\n{Fore.YELLOW}[Scheduler] Running initial scrape...{Style.RESET_ALL}")
            self._run_with_params(["reddit", "google_trends"])
    
    def stop(self):
        """Dừng scheduler"""
        if not self.is_running:
            return
        
        self.scheduler.shutdown(wait=True)
        self.is_running = False
        print(f"{Fore.RED}[Scheduler] Scheduler stopped{Style.RESET_ALL}")
    
    def run_now(self, platforms: Optional[List[str]] = None):
        """Chạy ngay lập tức"""
        print(f"{Fore.YELLOW}[Scheduler] Running immediate scrape...{Style.RESET_ALL}")
        self._run_with_params(platforms or ["reddit"])
    
    def get_status(self) -> dict:
        """Lấy trạng thái scheduler"""
        jobs = self.scheduler.get_jobs()
        return {
            "running": self.is_running,
            "jobs_count": len(jobs),
            "jobs": [
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run": job.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if job.next_run_time else "N/A"
                }
                for job in jobs
            ]
        }
    
    def remove_job(self, job_id: str):
        """Xóa một job"""
        try:
            self.scheduler.remove_job(job_id)
            print(f"{Fore.GREEN}[Scheduler] Removed job: {job_id}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}[Scheduler] Failed to remove job: {e}{Style.RESET_ALL}")


class WindowsTaskScheduler:
    """Windows Task Scheduler integration"""
    
    @staticmethod
    def create_task(
        task_name: str = "ScriptHunter Daily",
        script_path: str = None,
        hour: int = 8,
        minute: int = 0
    ):
        """Tạo Windows Scheduled Task"""
        import subprocess
        
        if script_path is None:
            script_path = Path(__file__).parent / "main.py"
        
        command = f'schtasks /create /tn "{task_name}" /tr "python {script_path} --scrape" /sc daily /st {hour:02d}:{minute:02d} /f'
        
        try:
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"{Fore.GREEN}[Task Scheduler] Created task: {task_name}{Style.RESET_ALL}")
                return True
            else:
                print(f"{Fore.RED}[Task Scheduler] Error: {result.stderr}{Style.RESET_ALL}")
                return False
        except Exception as e:
            print(f"{Fore.RED}[Task Scheduler] Error: {e}{Style.RESET_ALL}")
            return False
    
    @staticmethod
    def delete_task(task_name: str = "ScriptHunter Daily"):
        """Xóa Windows Scheduled Task"""
        import subprocess
        
        command = f'schtasks /delete /tn "{task_name}" /f'
        
        try:
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"{Fore.GREEN}[Task Scheduler] Deleted task: {task_name}{Style.RESET_ALL}")
                return True
            else:
                print(f"{Fore.RED}[Task Scheduler] Error: {result.stderr}{Style.RESET_ALL}")
                return False
        except Exception as e:
            print(f"{Fore.RED}[Task Scheduler] Error: {e}{Style.RESET_ALL}")
            return False
    
    @staticmethod
    def list_tasks(pattern: str = "ScriptHunter"):
        """Liệt kê các task liên quan"""
        import subprocess
        
        command = f'schtasks /query /fo csv /nh | findstr "{pattern}"'
        
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            if result.stdout:
                print(f"{Fore.CYAN}[Task Scheduler] Tasks found:{Style.RESET_ALL}")
                for line in result.stdout.strip().split('\n'):
                    if line:
                        print(f"  {line}")
                return True
            else:
                print(f"{Fore.YELLOW}[Task Scheduler] No tasks found matching: {pattern}{Style.RESET_ALL}")
                return False
        except Exception as e:
            print(f"{Fore.RED}[Task Scheduler] Error: {e}{Style.RESET_ALL}")
            return False


def setup_cron_windows(schedule_times: List[str] = None):
    """Setup cron cho Windows"""
    if schedule_times is None:
        schedule_times = ["08:00", "14:00", "20:00"]
    
    for i, time_str in enumerate(schedule_times):
        hour, minute = map(int, time_str.split(":"))
        task_name = f"ScriptHunter Daily {i+1}" if len(schedule_times) > 1 else "ScriptHunter Daily"
        
        WindowsTaskScheduler.create_task(
            task_name=task_name,
            hour=hour,
            minute=minute
        )
    
    print(f"\n{Fore.GREEN}[Setup] Created {len(schedule_times)} scheduled tasks{Style.RESET_ALL}")


if __name__ == "__main__":
    # Test scheduler
    scheduler = ScriptHunterScheduler()
    
    # Add jobs
    scheduler.add_daily_job("morning_scrape", hour=8, minute=0)
    scheduler.add_daily_job("afternoon_scrape", hour=14, minute=0)
    scheduler.add_daily_job("evening_scrape", hour=20, minute=0)
    
    # Start
    scheduler.start()
    
    print("\nScheduler running. Press Ctrl+C to stop.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scheduler.stop()
