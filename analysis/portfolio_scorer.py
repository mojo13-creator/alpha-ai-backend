# analysis/portfolio_scorer.py
"""
Portfolio Scoring Engine
Scores every active position using the composite scorer.
Generates health status and actionable alerts based on tier rules.
"""

import math
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def safe_float(val, default=0.0):
    try:
        v = float(val)
        return default if math.isnan(v) or math.isinf(v) else v
    except Exception:
        return default


class PortfolioScorer:
    """Scores all active portfolio positions and generates tier-aware alerts."""

    def __init__(self, db_manager, technical_analyzer, news_scraper):
        self.db = db_manager
        self.analyzer = technical_analyzer
        self.news_scraper = news_scraper

    def score_all_positions(self) -> list:
        """Score every active position in the portfolio."""
        positions = self.db.get_active_positions()
        results = []
        for position in positions:
            try:
                result = self.score_position(position)
                results.append(result)
            except Exception as e:
                print(f"  Error scoring {position.get('symbol', '?')}: {e}")
                results.append({
                    "ticker": position.get("symbol", "?"),
                    "tier": position.get("tier", "unknown"),
                    "error": str(e),
                })
        return results

    def score_position(self, position: dict) -> dict:
        """Score a single position and generate alerts."""
        import yfinance as yf
        from analysis.composite_scorer import run_composite_analysis
        from data_collection.reddit_scraper import RedditScraper

        ticker = position["symbol"]
        tier = position.get("tier", "midcap_active")
        entry_price = safe_float(position.get("purchase_price", 0))
        shares = safe_float(position.get("shares", 0))
        stop_loss = safe_float(position.get("stop_loss", 0))
        target_price = safe_float(position.get("target_price", 0))

        print(f"\n  Scoring {ticker} (tier: {tier})...")

        # Get current price
        try:
            ticker_obj = yf.Ticker(ticker)
            fast = ticker_obj.fast_info
            current_price = float(fast.last_price) if fast.last_price else 0
        except Exception:
            current_price = safe_float(position.get("current_price", entry_price))

        if current_price <= 0:
            current_price = entry_price

        # Run composite scorer (skip_ai=True for speed on bulk scoring)
        reddit_scraper = None
        try:
            reddit_scraper = RedditScraper(self.db)
            if reddit_scraper.reddit is None:
                reddit_scraper = None
        except Exception:
            pass

        result = run_composite_analysis(
            symbol=ticker,
            db_manager=self.db,
            technical_analyzer=self.analyzer,
            news_scraper=self.news_scraper,
            reddit_scraper=reddit_scraper,
            skip_ai=True,  # Skip AI call for bulk scoring (cost control)
            use_berkeley=False,  # Skip Berkeley for speed
        )

        if "error" in result:
            composite_score = 50
            signal = "HOLD"
        else:
            composite_score = result.get("composite_score", 50)
            signal = result.get("signal", "HOLD")

        # Calculate P&L
        pnl = (current_price - entry_price) * shares if entry_price > 0 else 0
        pnl_pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0

        # Generate health status and alerts based on tier
        health, alert = self._evaluate_health(
            position, composite_score, signal, current_price,
            entry_price, stop_loss, target_price, tier
        )

        # Update the database
        self.db.update_position_score(
            position_id=position["id"],
            current_price=round(current_price, 2),
            composite_score=composite_score,
            unrealized_pnl=round(pnl, 2),
            unrealized_pnl_pct=round(pnl_pct, 2),
            health=health,
            alert=alert,
        )

        print(f"    {ticker}: score={composite_score}, health={health}, P&L={pnl_pct:+.1f}%")
        if alert:
            print(f"    ALERT: {alert}")

        return {
            "ticker": ticker,
            "tier": tier,
            "current_price": round(current_price, 2),
            "composite_score": composite_score,
            "signal": signal,
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "health": health,
            "alert": alert,
        }

    def _evaluate_health(self, position, score, signal, current_price,
                          entry_price, stop_loss, target_price, tier):
        """
        Evaluate health status and generate alert based on tier rules.
        Returns (health, alert_message_or_None).
        """
        ticker = position["symbol"]

        if tier == "long_term":
            return self._evaluate_tier1(ticker, score, signal, current_price)
        else:
            return self._evaluate_tier2(
                ticker, score, signal, current_price,
                entry_price, stop_loss, target_price
            )

    def _evaluate_tier1(self, ticker, score, signal, current_price):
        """
        Tier 1 (Long-Term Hold): ETFs and blue chips.
        Only flag at danger level — this should be RARE.
        """
        if score < 25 or signal == "STRONG_SELL":
            health = "danger"
            alert = f"{ticker} score at {score} — unusual, check for macro event"
            return health, alert

        if 25 <= score < 40 or signal in ("SELL",):
            health = "watch"
            alert = None  # Only alert at danger for Tier 1
            return health, alert

        health = "healthy"
        return health, None

    def _evaluate_tier2(self, ticker, score, signal, current_price,
                         entry_price, stop_loss, target_price):
        """
        Tier 2 (Midcap Active): Assessed daily with multiple alert levels.
        """
        # Check stop loss first (highest priority)
        if stop_loss > 0 and current_price <= stop_loss:
            health = "stop_loss"
            alert = f"{ticker} hit stop loss at ${stop_loss:.2f} — consider exiting"
            return health, alert

        # Check take profit
        if target_price > 0 and current_price >= target_price:
            health = "take_profit"
            alert = f"{ticker} reached target price ${target_price:.2f} — take profits or raise stop"
            return health, alert

        # Check score-based danger
        if score < 30 or signal in ("SELL", "STRONG_SELL"):
            health = "danger"
            alert = f"{ticker} score dropped to {score} — deteriorating setup, review position"
            return health, alert

        # Check watch conditions
        if 40 <= score < 60:
            health = "watch"
            alert = f"{ticker} score at {score} — momentum weakening, monitor closely"
            return health, alert

        # Check proximity to stop loss (within 5%)
        if stop_loss > 0 and entry_price > 0:
            distance_to_stop = (current_price - stop_loss) / current_price * 100
            if distance_to_stop <= 5:
                health = "watch"
                alert = f"{ticker} within 5% of stop loss (${stop_loss:.2f}) — tighten risk management"
                return health, alert

        # Score between 30-40 is also watch
        if 30 <= score < 40:
            health = "watch"
            alert = f"{ticker} score at {score} — below average, review thesis"
            return health, alert

        # Healthy
        health = "healthy"
        return health, None
