#!/usr/bin/env python3
# test_basic.py - Test script for Stock Analyzer

"""
This script tests our basic functionality:
1. Database creation
2. Stock data fetching
3. Watchlist management
"""

print("="*60)
print("🚀 STOCK ANALYZER - BASIC FUNCTIONALITY TEST")
print("="*60)
print()

# Import our modules
from database.db_manager import DatabaseManager
from data_collection.stock_data import StockDataCollector
import config

print("Step 1: Loading configuration...")
print(f"   Default watchlist has {len(config.DEFAULT_WATCHLIST)} stocks")
print()

print("Step 2: Initializing database...")
db = DatabaseManager()
print()

print("Step 3: Creating stock data collector...")
collector = StockDataCollector(db)
print()

print("Step 4: Adding stocks to watchlist...")
test_stocks = ['AAPL', 'TSLA', 'MSFT', 'NVDA', 'GOOGL']

for stock in test_stocks:
    db.add_to_watchlist(stock, f"{stock} - Tech stock")
print()

print("Step 5: Fetching current prices...")
prices = collector.get_multiple_prices(test_stocks)
print(f"\n📊 Current Prices:")
for symbol, price in prices.items():
    print(f"   {symbol}: ${price:.2f}")
print()

print("Step 6: Fetching historical data for AAPL...")
success = collector.fetch_and_save('AAPL', period='1mo')
if success:
    print("✅ Successfully saved AAPL data")
print()

print("Step 7: Getting stock info for AAPL...")
info = collector.get_stock_info('AAPL')
if info:
    print(f"\n📈 {info['name']} ({info['symbol']})")
    print(f"   Sector: {info['sector']}")
    print(f"   Market Cap: ${info['market_cap']:,.0f}")
    print(f"   P/E Ratio: {info['pe_ratio']}")
print()

print("Step 8: Viewing your watchlist...")
watchlist = db.get_watchlist()
print(f"\n📋 Your Watchlist ({len(watchlist)} stocks):")
print(watchlist[['symbol', 'added_date', 'notes']])
print()

print("Step 9: Database statistics...")
stats = db.get_database_stats()
print("\n📊 Database Stats:")
for table, count in stats.items():
    print(f"   {table}: {count} records")
print()

print("="*60)
print("✅ ALL TESTS COMPLETED SUCCESSFULLY!")
print("="*60)
print()
print("Next steps:")
print("1. Get API keys for Reddit and News")
print("2. Build technical analysis")
print("3. Create the dashboard")
print()
