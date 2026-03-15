#!/usr/bin/env python3
# test_analysis.py - Test technical analysis

from database.db_manager import DatabaseManager
from data_collection.stock_data import StockDataCollector
from analysis.technical_analysis import TechnicalAnalyzer
from analysis.recommendation_engine import RecommendationEngine

print("="*60)
print("📈 TESTING TECHNICAL ANALYSIS")
print("="*60)
print()

# Initialize
db = DatabaseManager()
collector = StockDataCollector(db)
analyzer = TechnicalAnalyzer(db)
recommender = RecommendationEngine(db, analyzer)

# Test stock
test_symbol = 'AAPL'

print(f"Step 1: Fetching data for {test_symbol}...")
collector.fetch_and_save(test_symbol, period='6mo')
print()

print(f"Step 2: Running technical analysis on {test_symbol}...")
result = analyzer.analyze_stock(test_symbol)
print()

if result:
    analysis = result['analysis']
    
    print(f"📊 Analysis Results for {test_symbol}:")
    print(f"   Recommendation: {analysis['recommendation']}")
    print(f"   Score: {analysis['score']}/100")
    print(f"   Current Price: ${analysis['latest_price']:.2f}")
    if analysis['rsi']:
        print(f"   RSI: {analysis['rsi']:.1f}")
    if analysis['sma_20']:
        print(f"   20-day SMA: ${analysis['sma_20']:.2f}")
    if analysis['sma_50']:
        print(f"   50-day SMA: ${analysis['sma_50']:.2f}")
    
    print(f"\n   Signals detected:")
    for signal in analysis['signals']:
        print(f"      • {signal}")

print()
print("="*60)
print("✅ TECHNICAL ANALYSIS TEST COMPLETE!")
print("="*60)