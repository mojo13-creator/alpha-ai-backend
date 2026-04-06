#!/usr/bin/env python3
"""
Test the new composite scoring engine on 6 tickers.
Runs technical + fundamental scores without the Claude API call.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db_manager import DatabaseManager
from data_collection.stock_data import StockDataCollector
from analysis.technical_analysis import TechnicalAnalyzer
from analysis.technical_scorer import calculate_technical_score
from analysis.fundamental_scorer import calculate_fundamental_score

db = DatabaseManager()
collector = StockDataCollector(db)
analyzer = TechnicalAnalyzer(db)

TICKERS = ['AAPL', 'PLTR', 'SMCI', 'VOO', 'RIVN', 'GME']

print("\n" + "=" * 80)
print("  COMPOSITE SCORING TEST — 6 TICKERS")
print("=" * 80)

results = []

for symbol in TICKERS:
    print(f"\n{'─' * 60}")
    print(f"  Analyzing {symbol}...")
    print(f"{'─' * 60}")

    # Fetch data
    collector.fetch_and_save(symbol, period='1y')

    # Technical indicators
    df = analyzer.calculate_all_indicators(symbol)
    if df is None or df.empty:
        print(f"  ❌ No data for {symbol}")
        continue

    # Technical score
    tech = calculate_technical_score(df)

    # Fundamental score
    fund = calculate_fundamental_score(symbol)

    price = float(df.iloc[-1]['close'])

    results.append({
        'symbol': symbol,
        'price': price,
        'tech_score': tech['score'],
        'tech_trend': tech.get('trend', 0),
        'tech_momentum': tech.get('momentum', 0),
        'tech_volume': tech.get('volume', 0),
        'tech_volatility': tech.get('volatility', 0),
        'fund_score': fund['score'],
        'cap_category': fund.get('market_cap_label', 'Unknown'),
        'tech_signals': tech.get('key_signals', [])[:3],
        'fund_signals': fund.get('key_signals', [])[:3],
    })

# Print summary
print("\n\n" + "=" * 80)
print("  RESULTS SUMMARY")
print("=" * 80)
print(f"\n{'Symbol':<8} {'Price':>10} {'Tech':>6} {'Fund':>6} {'Trend':>6} {'Mom':>6} {'Vol':>6} {'Volat':>6} {'Cap':<12}")
print("─" * 80)

for r in results:
    print(f"{r['symbol']:<8} ${r['price']:>9.2f} {r['tech_score']:>5} {r['fund_score']:>5} "
          f"{r['tech_trend']:>5} {r['tech_momentum']:>5} {r['tech_volume']:>5} "
          f"{r['tech_volatility']:>5} {r['cap_category']:<12}")

print("\n─── Key Signals ───")
for r in results:
    print(f"\n{r['symbol']}:")
    print(f"  Tech: {'; '.join(r['tech_signals'][:3])}")
    print(f"  Fund: {'; '.join(r['fund_signals'][:3])}")

# Check for clustering
tech_scores = [r['tech_score'] for r in results]
fund_scores = [r['fund_score'] for r in results]
print(f"\n─── Score Distribution Check ───")
print(f"Tech scores range: {min(tech_scores)} - {max(tech_scores)} (spread: {max(tech_scores) - min(tech_scores)})")
print(f"Fund scores range: {min(fund_scores)} - {max(fund_scores)} (spread: {max(fund_scores) - min(fund_scores)})")

if max(tech_scores) - min(tech_scores) < 20:
    print("⚠️  WARNING: Tech scores are clustering — needs adjustment")
else:
    print("✅ Tech scores show good differentiation")

if max(fund_scores) - min(fund_scores) < 20:
    print("⚠️  WARNING: Fund scores are clustering — needs adjustment")
else:
    print("✅ Fund scores show good differentiation")
