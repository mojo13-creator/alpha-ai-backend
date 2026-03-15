# utils/scheduler.py
"""
Automated Scheduler - Run tasks on schedule
"""

from datetime import datetime

class TaskScheduler:
    """Schedule and run automated tasks"""
    
    def __init__(self, db_manager, collector, recommender, reporter):
        self.db = db_manager
        self.collector = collector
        self.recommender = recommender
        self.reporter = reporter
        self.running = False
        print("⏰ Task Scheduler initialized")
    
    def update_all_watchlist_data(self):
        """Update data for all watchlist stocks"""
        print(f"\n⏰ [{datetime.now().strftime('%H:%M:%S')}] Running scheduled data update...")
        try:
            self.collector.update_all_watchlist_stocks(period="1mo")
            print(f"✅ [{datetime.now().strftime('%H:%M:%S')}] Data update complete")
        except Exception as e:
            print(f"❌ [{datetime.now().strftime('%H:%M:%S')}] Data update failed: {e}")
    
    def analyze_all_stocks(self):
        """Analyze all watchlist stocks"""
        print(f"\n⏰ [{datetime.now().strftime('%H:%M:%S')}] Running scheduled analysis...")
        try:
            self.recommender.analyze_watchlist()
            print(f"✅ [{datetime.now().strftime('%H:%M:%S')}] Analysis complete")
        except Exception as e:
            print(f"❌ [{datetime.now().strftime('%H:%M:%S')}] Analysis failed: {e}")
    
    def generate_daily_report(self):
        """Generate daily report"""
        print(f"\n⏰ [{datetime.now().strftime('%H:%M:%S')}] Generating daily report...")
        try:
            self.reporter.generate_daily_report()
            print(f"✅ [{datetime.now().strftime('%H:%M:%S')}] Daily report generated")
        except Exception as e:
            print(f"❌ [{datetime.now().strftime('%H:%M:%S')}] Report generation failed: {e}")
    
    def generate_weekly_report(self):
        """Generate weekly report"""
        print(f"\n⏰ [{datetime.now().strftime('%H:%M:%S')}] Generating weekly report...")
        try:
            self.reporter.generate_weekly_report()
            print(f"✅ [{datetime.now().strftime('%H:%M:%S')}] Weekly report generated")
        except Exception as e:
            print(f"❌ [{datetime.now().strftime('%H:%M:%S')}] Weekly report failed: {e}")
    
    def cleanup_old_data(self):
        """Clean up old data"""
        print(f"\n⏰ [{datetime.now().strftime('%H:%M:%S')}] Cleaning up old data...")
        try:
            self.db.clear_old_data(days=365)
            print(f"✅ [{datetime.now().strftime('%H:%M:%S')}] Cleanup complete")
        except Exception as e:
            print(f"❌ [{datetime.now().strftime('%H:%M:%S')}] Cleanup failed: {e}")
    
    def start(self):
        """Start the scheduler (placeholder)"""
        self.running = True
        print("⏰ Scheduler marked as running (manual execution mode)")
        print("💡 Use the 'Run Tasks Manually' buttons in the Scheduler page")
    
    def stop(self):
        """Stop the scheduler"""
        self.running = False
        print("⏰ Scheduler stopped")
    
    def run_now(self, task_name):
        """Run a specific task immediately"""
        tasks = {
            'update_data': self.update_all_watchlist_data,
            'analyze': self.analyze_all_stocks,
            'daily_report': self.generate_daily_report,
            'weekly_report': self.generate_weekly_report,
            'cleanup': self.cleanup_old_data
        }
        
        if task_name in tasks:
            print(f"⏰ Running task: {task_name}")
            tasks[task_name]()
        else:
            print(f"❌ Unknown task: {task_name}")
            