#!/usr/bin/env python3
# test_reports.py - Test report generation

from database.db_manager import DatabaseManager
from data_collection.stock_data import StockDataCollector
from analysis.technical_analysis import TechnicalAnalyzer
from analysis.recommendation_engine import RecommendationEngine
from reports.report_generator import ReportGenerator

print("="*60)
print("📊 TESTING REPORT GENERATION")
print("="*60)
print()

# Initialize
db = DatabaseManager()
collector = StockDataCollector(db)
analyzer = TechnicalAnalyzer(db)
recommender = RecommendationEngine(db, analyzer)
reporter = ReportGenerator(db, analyzer, recommender)

# First, analyze some stocks
print("Step 1: Analyzing stocks to generate recommendations...")
test_stocks = ['AAPL', 'TSLA', 'NVDA']

for stock in test_stocks:
    collector.fetch_and_save(stock, period='3mo')
    recommender.analyze_and_recommend(stock)

print()
print("="*60)

# Generate daily report
print("\nStep 2: Generating Daily Report...")
daily = reporter.generate_daily_report()

print()
print("="*60)

# Generate weekly report
print("\nStep 3: Generating Weekly Report...")
weekly = reporter.generate_weekly_report()

print()
print("="*60)
print("✅ REPORT GENERATION TEST COMPLETE!")
print("="*60)