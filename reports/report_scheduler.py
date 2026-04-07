# reports/report_scheduler.py
"""
Daily Report Scheduler
Orchestrates the full pipeline: screening → market summary → packaging.
"""

import os
import sys
import json
import math
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from reports.daily_screener import DailyScreener

# Detect DB type for SQL syntax
DATABASE_URL = os.environ.get("DATABASE_URL")
_DB_TYPE = "postgres" if DATABASE_URL else "sqlite"


def safe_float(val, default=0.0):
    try:
        v = float(val)
        return default if math.isnan(v) or math.isinf(v) else v
    except Exception:
        return default


class ReportScheduler:
    """Generates and caches the structured daily report."""

    def __init__(self, db_manager, technical_analyzer, news_scraper):
        self.db = db_manager
        self.analyzer = technical_analyzer
        self.news_scraper = news_scraper
        self.screener = DailyScreener(db_manager, technical_analyzer, news_scraper)

    # ------------------------------------------------------------------
    # Market Summary — Claude-generated from index data + news signals
    # ------------------------------------------------------------------
    def _generate_market_summary(self):
        """
        Pull major index performance and top news signals,
        then ask Claude for a 3-4 sentence market summary.
        """
        import yfinance as yf

        # Fetch index data
        indices = {"SPY": "S&P 500", "QQQ": "Nasdaq 100", "IWM": "Russell 2000"}
        index_lines = []
        for symbol, name in indices.items():
            try:
                ticker = yf.Ticker(symbol)
                fast = ticker.fast_info
                price = safe_float(fast.last_price)
                prev = safe_float(fast.previous_close)
                if price > 0 and prev > 0:
                    change = price - prev
                    change_pct = (change / prev) * 100
                    index_lines.append(
                        f"{name} ({symbol}): ${price:.2f} ({change_pct:+.2f}%)"
                    )
            except Exception:
                continue

        # Fetch top news signals
        news_lines = []
        try:
            cached = self.db.get_cached_news_intelligence(max_age_minutes=120)
            if cached is not None and not cached.empty:
                top_news = cached.nlargest(5, "importance_score") if "importance_score" in cached.columns else cached.head(5)
                for _, row in top_news.iterrows():
                    headline = row.get("headline", "")
                    if headline:
                        news_lines.append(f"- {headline}")
        except Exception:
            pass

        # Build prompt
        index_block = "\n".join(index_lines) if index_lines else "Index data unavailable"
        news_block = "\n".join(news_lines) if news_lines else "No major news signals"

        prompt = f"""Today's market data:

{index_block}

Top news signals:
{news_block}

Write a 3-4 sentence market summary for today. Be direct and specific. No fluff.
Focus on: overall market direction, sector themes, and what traders should watch.
Return ONLY the summary text, no labels or headers."""

        # Call Claude
        try:
            import anthropic
            if not getattr(config, "CLAUDE_API_KEY", None):
                return "Market summary unavailable — no API key configured."

            client = anthropic.Anthropic(api_key=config.CLAUDE_API_KEY)
            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            summary = message.content[0].text.strip()
            return summary
        except Exception as e:
            return f"Market summary generation failed: {e}"

    # ------------------------------------------------------------------
    # Package a single pick for the response
    # ------------------------------------------------------------------
    def _package_pick(self, result, rank):
        """Convert a composite analysis result into the report pick format."""
        sub_scores = result.get("sub_scores", {})
        action = result.get("action", {})
        ai_insight = sub_scores.get("ai_insight", {})

        # Extract catalysts from news + AI reasoning
        catalysts = []
        for article in result.get("news", [])[:3]:
            title = article.get("title", "")
            if title:
                catalysts.append(title)
        if not catalysts:
            catalysts = ai_insight.get("agreements", [])[:3]

        # Extract risks
        risks = ai_insight.get("risks", [])
        if not risks:
            disagreements = ai_insight.get("disagreements", [])
            risks = disagreements[:3] if disagreements else ["No specific risks identified"]

        # Berkeley highlights
        berkeley_highlights = {}
        data_quality = result.get("data_quality", {})
        if data_quality.get("berkeley_enhanced"):
            berkeley_highlights = {
                "sources_used": data_quality.get("sources_available", []),
                "source_count": data_quality.get("berkeley_source_count", 0),
            }

        return {
            "rank": rank,
            "ticker": result.get("ticker", ""),
            "company_name": result.get("company_name", result.get("ticker", "")),
            "composite_score": result.get("composite_score", 0),
            "signal": result.get("signal", "HOLD"),
            "sub_scores": {
                "technical": sub_scores.get("technical", {}).get("score", 0),
                "fundamental": sub_scores.get("fundamental", {}).get("score", 0),
                "sentiment": sub_scores.get("sentiment", {}).get("score", 0),
                "ai_insight": sub_scores.get("ai_insight", {}).get("score", 0),
            },
            "action": {
                "entry_price": safe_float(action.get("entry_price", 0)),
                "stop_loss": safe_float(action.get("stop_loss", 0)),
                "target_price": safe_float(action.get("target_price", 0)),
                "time_horizon": action.get("time_horizon", "2-4 weeks"),
                "risk_reward_ratio": action.get("risk_reward_ratio", "N/A"),
            },
            "catalysts": catalysts,
            "risks": risks,
            "berkeley_highlights": berkeley_highlights,
        }

    # ------------------------------------------------------------------
    # Package a watchlist entry
    # ------------------------------------------------------------------
    def _package_watchlist_item(self, result):
        """Convert a near-miss result into a watchlist entry."""
        signal = result.get("signal", "HOLD")
        score = result.get("composite_score", 0)

        # Generate a reason based on what's close
        if score >= 65:
            reason = "Approaching buy zone — strong fundamentals"
        elif signal == "HOLD":
            reason = "Holding pattern — waiting for catalyst"
        else:
            reason = "Interesting setup — needs confirmation"

        return {
            "ticker": result.get("ticker", ""),
            "company_name": result.get("company_name", ""),
            "reason": reason,
            "composite_score": score,
            "signal": signal,
        }

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def generate_daily_report(self):
        """
        Run the full pipeline and return a structured report dict.
        """
        print("\n📋 Generating daily report...")
        report_date = date.today().isoformat()

        # 1. Market summary
        print("\n📊 Generating market summary...")
        market_summary = self._generate_market_summary()

        # 2. Run screening pipeline
        picks_raw, watchlist_raw, stats = self.screener.run_pipeline(max_picks=8)

        # 3. Package picks
        picks = []
        for i, result in enumerate(picks_raw, start=1):
            picks.append(self._package_pick(result, rank=i))

        # 4. Package watchlist
        watchlist = []
        for result in watchlist_raw:
            watchlist.append(self._package_watchlist_item(result))

        report = {
            "report_date": report_date,
            "generated_at": datetime.now().isoformat(),
            "market_summary": market_summary,
            "picks": picks,
            "watchlist": watchlist,
            "stats": stats,
        }

        # 5. Cache in database
        try:
            self._save_report(report)
        except Exception as e:
            print(f"  ⚠️  Could not cache report: {e}")

        return report

    # ------------------------------------------------------------------
    # Database operations
    # ------------------------------------------------------------------
    def _save_report(self, report):
        """Save report to daily_reports table."""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        report_date = report["report_date"]
        generated_at = report["generated_at"]
        market_summary = report["market_summary"]
        picks_json = json.dumps(report["picks"])
        watchlist_json = json.dumps(report["watchlist"])

        if _DB_TYPE == "postgres":
            cursor.execute("""
                INSERT INTO daily_reports (report_date, generated_at, market_summary, picks_json, watchlist_json)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (report_date) DO UPDATE SET
                    generated_at = EXCLUDED.generated_at,
                    market_summary = EXCLUDED.market_summary,
                    picks_json = EXCLUDED.picks_json,
                    watchlist_json = EXCLUDED.watchlist_json
            """, (report_date, generated_at, market_summary, picks_json, watchlist_json))
        else:
            cursor.execute("""
                INSERT OR REPLACE INTO daily_reports
                    (report_date, generated_at, market_summary, picks_json, watchlist_json)
                VALUES (?, ?, ?, ?, ?)
            """, (report_date, generated_at, market_summary, picks_json, watchlist_json))

        conn.commit()
        conn.close()
        print(f"  ✅ Report cached for {report_date}")

    def get_cached_report(self, report_date=None):
        """Retrieve a cached report by date. Defaults to today."""
        if report_date is None:
            report_date = date.today().isoformat()

        conn = self.db.get_connection()
        cursor = conn.cursor()

        if _DB_TYPE == "postgres":
            cursor.execute(
                "SELECT report_date, generated_at, market_summary, picks_json, watchlist_json "
                "FROM daily_reports WHERE report_date = %s",
                (report_date,),
            )
        else:
            cursor.execute(
                "SELECT report_date, generated_at, market_summary, picks_json, watchlist_json "
                "FROM daily_reports WHERE report_date = ?",
                (report_date,),
            )

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            "report_date": row[0] if isinstance(row[0], str) else str(row[0]),
            "generated_at": row[1] if isinstance(row[1], str) else str(row[1]),
            "market_summary": row[2],
            "picks": json.loads(row[3]) if row[3] else [],
            "watchlist": json.loads(row[4]) if row[4] else [],
        }
