# reports/daily_screener.py
"""
Daily Stock Screener Pipeline
Casts a wide net across multiple sources, applies quick filters,
then runs deep composite analysis on survivors.
"""

import os
import sys
import math
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_collection.finviz_scraper import FinvizScraper
from data_collection.reddit_scraper import RedditScraper
from data_collection.stock_data import StockDataCollector
from analysis.technical_analysis import TechnicalAnalyzer
from analysis.composite_scorer import run_composite_analysis


def safe_float(val, default=0.0):
    try:
        v = float(val)
        return default if math.isnan(v) or math.isinf(v) else v
    except Exception:
        return default


class DailyScreener:
    """
    Three-stage pipeline:
      1. Wide net — gather candidates from Finviz, news intelligence, Reddit
      2. First pass — quick technical filter (SMA, RSI, volume)
      3. Deep analysis — full composite scorer on survivors
    """

    def __init__(self, db_manager, technical_analyzer, news_scraper):
        self.db = db_manager
        self.analyzer = technical_analyzer
        self.news_scraper = news_scraper
        self.collector = StockDataCollector(db_manager)

    # ------------------------------------------------------------------
    # Stage 1: Wide net — pull candidate tickers from multiple sources
    # ------------------------------------------------------------------
    def _gather_finviz_candidates(self):
        """Midcap/smallcap from Finviz with positive signals."""
        tickers = set()
        try:
            finviz = FinvizScraper()
            # Pull from the most actionable signal categories
            for method in [finviz.get_upgrades, finviz.get_unusual_volume,
                           finviz.get_oversold, finviz.get_top_gainers,
                           finviz.get_insider_buying]:
                try:
                    results = method()
                    for stock in results:
                        sym = stock.get("symbol", "").strip().upper()
                        if sym:
                            tickers.add(sym)
                except Exception:
                    continue
        except Exception as e:
            print(f"  ⚠️  Finviz gathering failed: {e}")
        print(f"  Finviz candidates: {len(tickers)}")
        return tickers

    def _gather_news_candidates(self):
        """Tickers with BUY or STRONG_BUY from today's news intelligence."""
        tickers = set()
        try:
            cached = self.db.get_cached_news_intelligence(max_age_minutes=120)
            if cached is not None and not cached.empty:
                import json
                for _, row in cached.iterrows():
                    signals_raw = row.get("signals", "")
                    tickers_raw = row.get("affected_tickers", "")
                    try:
                        signals = json.loads(signals_raw) if isinstance(signals_raw, str) else signals_raw
                        affected = json.loads(tickers_raw) if isinstance(tickers_raw, str) else tickers_raw
                    except (json.JSONDecodeError, TypeError):
                        continue

                    if not isinstance(affected, list):
                        continue

                    for entry in affected:
                        if isinstance(entry, dict):
                            sig = str(entry.get("signal", "")).upper()
                            if sig in ("BUY", "STRONG_BUY"):
                                tick = str(entry.get("ticker", "")).strip().upper()
                                if tick:
                                    tickers.add(tick)
                        elif isinstance(entry, str):
                            # If signals list has BUY/STRONG_BUY somewhere
                            tick = entry.strip().upper()
                            if tick and isinstance(signals, list):
                                for s in signals:
                                    if isinstance(s, dict) and str(s.get("signal", "")).upper() in ("BUY", "STRONG_BUY"):
                                        tickers.add(tick)
        except Exception as e:
            print(f"  ⚠️  News intelligence gathering failed: {e}")
        print(f"  News intelligence candidates: {len(tickers)}")
        return tickers

    def _gather_reddit_candidates(self):
        """Tickers trending on Reddit with rising mention volume."""
        tickers = set()
        try:
            reddit = RedditScraper(self.db)
            posts = reddit.scrape_all_subreddits(limit=25)
            trending = reddit.get_trending_tickers(posts, min_mentions=2)
            for tick in trending:
                sym = tick.strip().upper()
                if sym and len(sym) <= 5:
                    tickers.add(sym)
        except Exception as e:
            print(f"  ⚠️  Reddit gathering failed: {e}")
        print(f"  Reddit candidates: {len(tickers)}")
        return tickers

    def gather_candidates(self):
        """Combine all sources into a deduplicated set of candidate tickers."""
        print("\n📡 Stage 1: Gathering candidates...")
        finviz_tickers = self._gather_finviz_candidates()
        news_tickers = self._gather_news_candidates()
        reddit_tickers = self._gather_reddit_candidates()

        all_candidates = finviz_tickers | news_tickers | reddit_tickers
        print(f"  Total unique candidates: {len(all_candidates)}")
        return all_candidates

    # ------------------------------------------------------------------
    # Stage 2: Quick technical filter
    # ------------------------------------------------------------------
    def quick_filter(self, tickers):
        """
        Quick check on each candidate. Must pass at least 1 of 3 criteria:
          - Price above 50 SMA
          - RSI between 30-70
          - Average volume above 500K
        Returns list of tickers that pass.
        """
        print(f"\n🔍 Stage 2: Quick filtering {len(tickers)} candidates...")
        passed = []

        for ticker in tickers:
            try:
                # Ensure price data is fetched before calculating indicators
                self.collector.fetch_and_save(ticker, period="6mo")
                df = self.analyzer.calculate_all_indicators(ticker)
                if df is None or df.empty:
                    continue

                latest = df.iloc[-1]
                checks_passed = 0

                # Check 1: Price above 50 SMA
                price = safe_float(latest.get("close", 0))
                sma_50 = safe_float(latest.get("SMA_50", 0))
                if price > 0 and sma_50 > 0 and price > sma_50:
                    checks_passed += 1

                # Check 2: RSI between 30-70 (not overbought, not oversold)
                rsi = safe_float(latest.get("RSI", 50))
                if 30 <= rsi <= 70:
                    checks_passed += 1

                # Check 3: Average volume above 500K
                avg_vol = safe_float(df["volume"].tail(20).mean(), 0)
                if avg_vol > 500_000:
                    checks_passed += 1

                if checks_passed >= 1:
                    passed.append(ticker)
                    print(f"  ✅ {ticker}: {checks_passed}/3 checks passed")
                else:
                    print(f"  ❌ {ticker}: failed all 3 checks")

            except Exception as e:
                print(f"  ⚠️  {ticker}: filter error — {e}")
                continue

        print(f"  Passed filter: {len(passed)} / {len(tickers)}")
        return passed

    # ------------------------------------------------------------------
    # Stage 3: Deep composite analysis
    # ------------------------------------------------------------------
    def deep_analyze(self, tickers, max_picks=8):
        """
        Run full composite scorer on filtered candidates.
        Returns top picks ranked by composite score.
        """
        print(f"\n🧠 Stage 3: Deep analysis on {len(tickers)} candidates...")
        results = []

        reddit_scraper = None
        try:
            reddit_scraper = RedditScraper(self.db)
        except Exception:
            pass

        for ticker in tickers:
            try:
                result = run_composite_analysis(
                    symbol=ticker,
                    db_manager=self.db,
                    technical_analyzer=self.analyzer,
                    news_scraper=self.news_scraper,
                    reddit_scraper=reddit_scraper,
                    skip_ai=False,
                    use_berkeley=True,
                )
                if result and "error" not in result:
                    results.append(result)
                    print(f"  ✅ {ticker}: score={result.get('composite_score', 0)} signal={result.get('signal', 'N/A')}")
            except Exception as e:
                print(f"  ⚠️  {ticker}: analysis failed — {e}")
                continue

        # Rank by composite score, take top N
        results.sort(key=lambda r: r.get("composite_score", 0), reverse=True)
        picks = results[:max_picks]
        watchlist = results[max_picks:max_picks + 5]  # Next 5 for watchlist

        print(f"\n  Top picks: {len(picks)} | Watchlist: {len(watchlist)}")
        return picks, watchlist

    # ------------------------------------------------------------------
    # Full pipeline
    # ------------------------------------------------------------------
    def run_pipeline(self, max_picks=8):
        """
        Run the full 3-stage screening pipeline.
        Returns (picks, watchlist, stats).
        """
        start = datetime.now()
        print(f"\n{'='*60}")
        print(f"  DAILY SCREENER — {start.strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*60}")

        # Stage 1
        candidates = self.gather_candidates()
        total_candidates = len(candidates)

        if not candidates:
            print("  No candidates found — aborting pipeline")
            return [], [], {"total_candidates": 0, "passed_filter": 0, "picks": 0}

        # Stage 2
        filtered = self.quick_filter(candidates)
        passed_filter = len(filtered)

        if not filtered:
            print("  No candidates passed filter — aborting pipeline")
            return [], [], {"total_candidates": total_candidates, "passed_filter": 0, "picks": 0}

        # Cap deep analysis at 15 to manage API costs
        if len(filtered) > 15:
            print(f"  Capping deep analysis to 15 (from {len(filtered)})")
            filtered = filtered[:15]

        # Stage 3
        picks, watchlist = self.deep_analyze(filtered, max_picks=max_picks)

        elapsed = (datetime.now() - start).total_seconds()
        stats = {
            "total_candidates": total_candidates,
            "passed_filter": passed_filter,
            "picks": len(picks),
            "watchlist": len(watchlist),
            "elapsed_seconds": round(elapsed, 1),
        }

        print(f"\n{'='*60}")
        print(f"  PIPELINE COMPLETE: {total_candidates} → {passed_filter} → {len(picks)} picks")
        print(f"  Elapsed: {elapsed:.1f}s")
        print(f"{'='*60}\n")

        return picks, watchlist, stats
