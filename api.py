# api.py
"""
FastAPI Backend for Alpha AI
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db_manager import DatabaseManager
from data_collection.stock_data import StockDataCollector
from analysis.technical_analysis import TechnicalAnalyzer
from data_collection.news_scraper import NewsScraper
import math

def safe_float(val, default=0.0):
    try:
        v = float(val)
        return default if math.isnan(v) or math.isinf(v) else v
    except:
        return default
from data_collection.reddit_scraper import RedditScraper
from analysis.hybrid_recommender import HybridRecommender

app = FastAPI(title="Alpha AI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db = DatabaseManager()
collector = StockDataCollector(db)
analyzer = TechnicalAnalyzer(db)
news_scraper = NewsScraper(db)
recommender = HybridRecommender(db, analyzer, news_scraper)

class AnalysisRequest(BaseModel):
    symbol: str
    period: str = "6mo"

@app.get("/")
def root():
    return {"message": "Alpha AI API is running!", "version": "1.0.0"}

@app.post("/api/analyze")
async def analyze_stock(request: AnalysisRequest):
    symbol = request.symbol.upper()

    try:
        from analysis.composite_scorer import run_composite_analysis

        # Initialize reddit scraper if available
        reddit_scraper_instance = None
        try:
            reddit_scraper_instance = RedditScraper(db)
            if reddit_scraper_instance.reddit is None:
                reddit_scraper_instance = None
        except Exception:
            pass

        # Get finviz data (non-blocking, best-effort)
        finviz_data = None
        try:
            finviz_data = finviz.get_all_signals()
        except Exception:
            pass

        result = run_composite_analysis(
            symbol=symbol,
            db_manager=db,
            technical_analyzer=analyzer,
            news_scraper=news_scraper,
            reddit_scraper=reddit_scraper_instance,
            finviz_data=finviz_data,
        )

        if 'error' in result:
            raise HTTPException(status_code=404, detail=result['error'])

        # Save recommendation to DB
        db.save_recommendation(
            symbol=symbol,
            recommendation=result.get('recommendation', 'HOLD'),
            score=result.get('composite_score', 50),
            reasoning=result.get('reasoning', ''),
            price=result.get('price', 0),
            target_price=result.get('action', {}).get('target_price'),
            stop_loss=result.get('action', {}).get('stop_loss'),
        )

        print(f"✅ Composite analysis complete for {symbol}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dashboard")
async def get_dashboard():
    try:
        import yfinance as yf
        from datetime import datetime, timedelta

        # 1. Recent Analyses from real DB
        recent_recs = db.get_latest_recommendations(days=30, limit=10)
        recent_analyses = []
        if recent_recs is not None and not recent_recs.empty:
            for _, row in recent_recs.iterrows():
                recent_analyses.append({
                    "symbol": str(row.get("symbol", "")),
                    "recommendation": str(row.get("recommendation", "HOLD")),
                    "score": int(row.get("score", 50)),
                    "price": float(row.get("price_at_recommendation", 0)),
                    "timestamp": str(row.get("date", "")),
                })

        # 2. Watchlist with real prices
        watchlist_df = db.get_watchlist()
        watchlist = []
        if watchlist_df is not None and not watchlist_df.empty:
            for _, row in watchlist_df.iterrows():
                symbol = str(row.get("symbol", ""))
                try:
                    ticker = yf.Ticker(symbol)
                    info = ticker.fast_info
                    price = float(info.last_price) if hasattr(info, "last_price") else 0
                    prev = float(info.previous_close) if hasattr(info, "previous_close") else price
                    change = ((price - prev) / prev * 100) if prev > 0 else 0
                except:
                    price = 0
                    change = 0
                # Get latest AI score if available
                rec = db.get_latest_recommendations(days=30, limit=1)
                score = 50
                recommendation = "HOLD"
                if rec is not None and not rec.empty:
                    sym_rec = rec[rec["symbol"] == symbol]
                    if not sym_rec.empty:
                        score = int(sym_rec.iloc[0].get("score", 50))
                        recommendation = str(sym_rec.iloc[0].get("recommendation", "HOLD"))
                watchlist.append({
                    "symbol": symbol,
                    "price": round(price, 2),
                    "change": round(change, 2),
                    "score": score,
                    "recommendation": recommendation,
                })

        # 3. Market Overview with real prices
        market_symbols = {"S&P 500": "^GSPC", "NASDAQ": "^IXIC", "DOW": "^DJI", "VIX": "^VIX"}
        market_data = []
        for name, sym in market_symbols.items():
            try:
                ticker = yf.Ticker(sym)
                info = ticker.fast_info
                price = float(info.last_price)
                prev = float(info.previous_close)
                change = ((price - prev) / prev * 100) if prev > 0 else 0
                market_data.append({
                    "name": name,
                    "value": f"{price:,.2f}",
                    "change": f"{change:+.2f}%",
                    "up": change >= 0,
                })
            except Exception as e:
                market_data.append({"name": name, "value": "N/A", "change": "0.00%", "up": True})

        # 4. AI Alerts from real technical signals
        alerts = []
        all_symbols = db.get_all_symbols()
        if all_symbols:
            for symbol in all_symbols[:10]:
                try:
                    df = analyzer.calculate_all_indicators(symbol)
                    if df is None or df.empty:
                        continue
                    latest = df.iloc[-1]
                    price = float(latest["close"])
                    rsi = float(latest.get("RSI", 50))
                    macd = float(latest.get("MACD", 0))
                    macd_sig = float(latest.get("MACD_Signal", 0))
                    sma200 = float(latest.get("SMA_200", price))

                    if rsi > 75:
                        alerts.append({"symbol": symbol, "severity": "HIGH", "message": f"RSI overbought at {rsi:.0f} — consider taking profits"})
                    elif rsi < 28:
                        alerts.append({"symbol": symbol, "severity": "HIGH", "message": f"RSI oversold at {rsi:.0f} — potential buying opportunity"})
                    if price < sma200 * 0.97 and sma200 > 0:
                        alerts.append({"symbol": symbol, "severity": "MEDIUM", "message": f"Breaking below 200-day MA — watch for further downside"})
                    if macd > macd_sig and abs(macd - macd_sig) > 0.1:
                        alerts.append({"symbol": symbol, "severity": "LOW", "message": f"Bullish MACD crossover detected"})
                except:
                    continue
        alerts = alerts[:5]

        # 5. Portfolio stats (from DB if available, else empty)
        portfolio_value = 0
        positions = 0
        try:
            import sqlite3
            conn = sqlite3.connect("stock_data.db")
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM portfolio")
            positions = cursor.fetchone()[0]
            conn.close()
        except:
            pass

        return {
            "recent_analyses": recent_analyses,
            "watchlist": watchlist,
            "market_data": market_data,
            "alerts": alerts,
            "portfolio": {
                "value": portfolio_value,
                "positions": positions,
            }
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


class PortfolioRequest(BaseModel):
    symbol: str
    shares: float
    purchase_price: float
    purchase_date: str = ""
    notes: str = ""
    tier: str = "midcap_active"
    stop_loss: float = 0
    target_price: float = 0
    signal: str = ""
    source: str = "manual"

class PortfolioUpdateRequest(BaseModel):
    tier: str = ""
    stop_loss: float = 0
    target_price: float = 0
    shares: float = 0
    notes: str = ""

@app.get("/api/portfolio")
async def get_portfolio():
    """Returns all positions separated by tier with current scores and P&L."""
    try:
        import yfinance as yf

        positions = db.get_active_positions()
        tier_1_positions = []
        tier_2_positions = []
        tier_1_value = 0
        tier_1_cost = 0
        tier_2_value = 0
        tier_2_cost = 0
        all_alerts = []
        last_scored = None

        for pos in positions:
            symbol = pos["symbol"]
            shares = safe_float(pos.get("shares", 0))
            entry_price = safe_float(pos.get("purchase_price", 0))

            # Use cached current_price if scored recently, otherwise fetch live
            current_price = safe_float(pos.get("current_price", 0))
            if current_price <= 0:
                try:
                    ticker_obj = yf.Ticker(symbol)
                    current_price = float(ticker_obj.fast_info.last_price)
                except Exception:
                    current_price = entry_price

            market_value = shares * current_price
            cost_basis = shares * entry_price
            pnl = market_value - cost_basis
            pnl_pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0

            scored_at = pos.get("last_scored_at")
            if scored_at and (last_scored is None or str(scored_at) > str(last_scored)):
                last_scored = scored_at

            position_data = {
                "id": pos["id"],
                "ticker": symbol,
                "shares": shares,
                "entry_price": round(entry_price, 2),
                "current_price": round(current_price, 2),
                "total_invested": round(cost_basis, 2),
                "unrealized_pnl": round(pnl, 2),
                "unrealized_pnl_pct": round(pnl_pct, 2),
                "composite_score": pos.get("current_score"),
                "health": pos.get("health", "healthy"),
                "alert": pos.get("alert"),
                "stop_loss": safe_float(pos.get("stop_loss", 0)) or None,
                "target_price": safe_float(pos.get("target_price", 0)) or None,
                "signal": pos.get("signal", ""),
                "source": pos.get("source", "manual"),
                "notes": pos.get("notes", ""),
                "purchase_date": str(pos.get("purchase_date", "")),
            }

            tier = pos.get("tier", "midcap_active")
            if tier == "long_term":
                tier_1_positions.append(position_data)
                tier_1_value += market_value
                tier_1_cost += cost_basis
            else:
                tier_2_positions.append(position_data)
                tier_2_value += market_value
                tier_2_cost += cost_basis

            # Collect alerts
            if pos.get("alert"):
                severity = "high" if pos.get("health") in ("danger", "stop_loss") else \
                           "medium" if pos.get("health") == "take_profit" else "low"
                all_alerts.append({
                    "ticker": symbol,
                    "type": pos.get("health", "watch"),
                    "message": pos["alert"],
                    "severity": severity,
                })

        total_value = tier_1_value + tier_2_value
        total_cost = tier_1_cost + tier_2_cost
        total_pnl = total_value - total_cost
        total_pnl_pct = ((total_value - total_cost) / total_cost * 100) if total_cost > 0 else 0

        return {
            "portfolio_value": round(total_value, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl_pct, 2),
            "last_scored_at": str(last_scored) if last_scored else None,
            "tier_1": {
                "label": "Long-Term Holdings",
                "positions": tier_1_positions,
                "subtotal": round(tier_1_value, 2),
                "subtotal_pnl": round(tier_1_value - tier_1_cost, 2),
            },
            "tier_2": {
                "label": "Active Midcap",
                "positions": tier_2_positions,
                "subtotal": round(tier_2_value, 2),
                "subtotal_pnl": round(tier_2_value - tier_2_cost, 2),
            },
            "alerts": all_alerts,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/portfolio/alerts")
async def get_portfolio_alerts():
    """Returns only positions with active alerts."""
    try:
        rows = db.get_positions_with_alerts()
        alerts = []
        for pos in rows:
            severity = "high" if pos.get("health") in ("danger", "stop_loss") else \
                       "medium" if pos.get("health") == "take_profit" else "low"
            alerts.append({
                "id": pos["id"],
                "ticker": pos["symbol"],
                "tier": pos.get("tier", "midcap_active"),
                "type": pos.get("health", "watch"),
                "message": pos.get("alert", ""),
                "severity": severity,
                "composite_score": pos.get("current_score"),
                "current_price": safe_float(pos.get("current_price", 0)),
            })
        return {"alerts": alerts, "count": len(alerts)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/portfolio/score-all")
async def score_all_positions():
    """Trigger scoring of all active positions on demand."""
    try:
        from analysis.portfolio_scorer import PortfolioScorer

        scorer = PortfolioScorer(db, analyzer, news_scraper)
        print("\n" + "=" * 60)
        print("  PORTFOLIO SCORING — ALL POSITIONS")
        print("=" * 60)
        results = scorer.score_all_positions()
        print("=" * 60)
        print(f"  Scored {len(results)} positions")
        print("=" * 60 + "\n")

        return {
            "scored": len(results),
            "results": results,
            "scored_at": datetime.now().isoformat(),
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/portfolio")
async def add_position(request: PortfolioRequest):
    try:
        symbol = request.symbol.upper().strip()
        if not symbol.isalpha() or len(symbol) > 10:
            raise HTTPException(status_code=400, detail="Invalid ticker symbol")

        row_id = db.add_portfolio_position(
            symbol=symbol,
            shares=request.shares,
            purchase_price=request.purchase_price,
            purchase_date=request.purchase_date if request.purchase_date else None,
            notes=request.notes,
            tier=request.tier,
            stop_loss=request.stop_loss if request.stop_loss > 0 else None,
            target_price=request.target_price if request.target_price > 0 else None,
            signal=request.signal if request.signal else None,
            source=request.source,
        )
        return {"message": f"Added {symbol} to portfolio", "id": row_id, "ticker": symbol}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/portfolio/{position_id}")
async def update_position(position_id: int, request: PortfolioUpdateRequest):
    """Update a position (change tier, stop loss, target, shares, notes)."""
    try:
        updates = {}
        if request.tier:
            updates["tier"] = request.tier
        if request.stop_loss > 0:
            updates["stop_loss"] = request.stop_loss
        if request.target_price > 0:
            updates["target_price"] = request.target_price
        if request.shares > 0:
            updates["shares"] = request.shares
        if request.notes:
            updates["notes"] = request.notes
        if updates:
            updates["last_updated"] = datetime.now()
            db.update_position(position_id, **updates)
        return {"message": f"Updated position {position_id}", "updated_fields": list(updates.keys())}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/portfolio/{position_id}")
async def delete_position(position_id: int):
    """Mark position as closed (soft delete)."""
    try:
        closed = db.close_position(position_id)
        if not closed:
            raise HTTPException(status_code=404, detail="Position not found")
        return {"message": f"Position {position_id} closed"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ReportPickPortfolioRequest(BaseModel):
    ticker: str
    entry_price: float
    stop_loss: float
    target_price: float
    signal: str
    source: str = "daily_report"
    tier: str = "midcap_active"
    shares: float = 0

@app.post("/api/portfolio/from-report")
async def add_report_pick_to_portfolio(request: ReportPickPortfolioRequest):
    """Add a daily report pick to the portfolio tracking table."""
    try:
        symbol = request.ticker.upper().strip()
        if not symbol.isalpha() or len(symbol) > 10:
            raise HTTPException(status_code=400, detail="Invalid ticker symbol")

        row_id = db.add_portfolio_position(
            symbol=symbol,
            shares=request.shares,
            purchase_price=request.entry_price,
            notes=f"From daily report | Signal: {request.signal}",
            tier=request.tier,
            stop_loss=request.stop_loss,
            target_price=request.target_price,
            signal=request.signal,
            source=request.source,
        )
        return {"message": f"Added {symbol} from daily report", "id": row_id, "ticker": symbol, "signal": request.signal}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/portfolio/history")
async def get_portfolio_history():
    try:
        import yfinance as yf
        import sqlite3
        from datetime import datetime, timedelta
        import pandas as pd

        conn = sqlite3.connect("stock_data.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM portfolio")
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return {"history": []}

        # Get 1 year of history for each position
        end = datetime.now()
        start = end - timedelta(days=365)
        
        portfolio_df = None

        for row in rows:
            symbol = row["symbol"]
            shares = float(row["shares"] or 0)
            purchase_date = row["purchase_date"] or "2020-01-01"

            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(start=start, end=end)
                if hist.empty:
                    continue
                position_value = hist["Close"] * shares
                position_value.name = symbol

                if portfolio_df is None:
                    portfolio_df = position_value.to_frame()
                else:
                    portfolio_df = portfolio_df.join(position_value.to_frame(), how="outer")
            except:
                continue

        if portfolio_df is None:
            return {"history": []}

        portfolio_df = portfolio_df.fillna(method="ffill").fillna(0)
        portfolio_df["total"] = portfolio_df.sum(axis=1)

        # Resample to weekly for cleaner chart
        portfolio_df = portfolio_df.resample("W").last()

        history = []
        for date, row in portfolio_df.iterrows():
            history.append({
                "date": date.strftime("%b %d"),
                "value": round(float(row["total"]), 2),
            })

        return {"history": history}

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


class WatchlistRequest(BaseModel):
    symbol: str
    notes: str = ""

@app.get("/api/watchlist")
async def get_watchlist():
    try:
        import yfinance as yf
        watchlist_df = db.get_watchlist()
        items = []
        if watchlist_df is not None and not watchlist_df.empty:
            for _, row in watchlist_df.iterrows():
                symbol = str(row.get("symbol", ""))
                try:
                    ticker = yf.Ticker(symbol)
                    info = ticker.fast_info
                    price = float(info.last_price)
                    prev = float(info.previous_close)
                    change = ((price - prev) / prev * 100) if prev > 0 else 0
                    market_cap = float(info.market_cap) if hasattr(info, "market_cap") else 0
                except:
                    price = 0
                    change = 0
                    market_cap = 0

                # Get latest AI recommendation from DB
                try:
                    import sqlite3
                    conn = sqlite3.connect("stock_data.db")
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute("SELECT recommendation, score FROM recommendations WHERE symbol=? ORDER BY date DESC LIMIT 1", (symbol,))
                    rec_row = cursor.fetchone()
                    conn.close()
                    score = int(rec_row["score"]) if rec_row else 50
                    recommendation = str(rec_row["recommendation"]) if rec_row else "HOLD"
                except:
                    score = 50
                    recommendation = "HOLD"

                items.append({
                    "symbol": symbol,
                    "notes": str(row.get("notes", "")),
                    "added_date": str(row.get("added_date", "")),
                    "price": round(price, 2),
                    "change": round(change, 2),
                    "score": score,
                    "recommendation": recommendation,
                    "market_cap": market_cap,
                })
        return {"items": items}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/watchlist")
async def add_to_watchlist(request: WatchlistRequest):
    try:
        db.add_to_watchlist(request.symbol.upper(), notes=request.notes)
        return {"message": f"Added {request.symbol.upper()} to watchlist"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/watchlist/{symbol}")
async def remove_from_watchlist(symbol: str):
    try:
        db.remove_from_watchlist(symbol.upper())
        return {"message": f"Removed {symbol.upper()} from watchlist"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/alerts")
async def get_alerts():
    try:
        all_symbols = db.get_all_symbols()
        alerts = []

        if all_symbols:
            for symbol in all_symbols[:15]:
                try:
                    df = analyzer.calculate_all_indicators(symbol)
                    if df is None or df.empty:
                        continue
                    latest = df.iloc[-1]
                    price = float(latest["close"])
                    rsi = float(latest.get("RSI", 50))
                    macd = float(latest.get("MACD", 0))
                    macd_sig = float(latest.get("MACD_Signal", 0))
                    sma20 = float(latest.get("SMA_20", price))
                    sma50 = float(latest.get("SMA_50", price))
                    sma200 = float(latest.get("SMA_200", price))
                    bb_upper = float(latest.get("BB_Upper", price))
                    bb_lower = float(latest.get("BB_Lower", price))
                    import math
                    def sf(v): return 0 if math.isnan(v) or math.isinf(v) else v
                    rsi = sf(rsi); macd = sf(macd); macd_sig = sf(macd_sig)
                    sma20 = sf(sma20); sma50 = sf(sma50); sma200 = sf(sma200)
                    bb_upper = sf(bb_upper); bb_lower = sf(bb_lower)

                    if rsi > 75:
                        alerts.append({"symbol": symbol, "severity": "HIGH", "type": "RSI Overbought",
                            "message": f"RSI at {rsi:.0f} — significantly overbought, consider taking profits", "price": price})
                    if rsi < 28:
                        alerts.append({"symbol": symbol, "severity": "HIGH", "type": "RSI Oversold",
                            "message": f"RSI at {rsi:.0f} — oversold territory, potential buying opportunity", "price": price})
                    if sma200 > 0 and price < sma200 * 0.97:
                        alerts.append({"symbol": symbol, "severity": "HIGH", "type": "Below 200 MA",
                            "message": f"Price ${price:.2f} broke below 200-day MA (${sma200:.2f}) — bearish signal", "price": price})
                    if sma50 > 0 and sma200 > 0 and sma50 < sma200 and price < sma50:
                        alerts.append({"symbol": symbol, "severity": "HIGH", "type": "Death Cross",
                            "message": f"50-day MA crossed below 200-day MA — strong bearish signal", "price": price})
                    if macd > macd_sig and abs(macd - macd_sig) > 0.05:
                        alerts.append({"symbol": symbol, "severity": "LOW", "type": "MACD Bullish",
                            "message": f"Bullish MACD crossover — momentum turning positive", "price": price})
                    if macd < macd_sig and abs(macd - macd_sig) > 0.05:
                        alerts.append({"symbol": symbol, "severity": "MEDIUM", "type": "MACD Bearish",
                            "message": f"Bearish MACD crossover — momentum turning negative", "price": price})
                    if bb_upper > 0 and price > bb_upper:
                        alerts.append({"symbol": symbol, "severity": "MEDIUM", "type": "BB Upper Break",
                            "message": f"Price broke above upper Bollinger Band (${bb_upper:.2f}) — potential reversal", "price": price})
                    if bb_lower > 0 and price < bb_lower:
                        alerts.append({"symbol": symbol, "severity": "MEDIUM", "type": "BB Lower Break",
                            "message": f"Price broke below lower Bollinger Band (${bb_lower:.2f}) — oversold signal", "price": price})
                    if sma20 > 0 and sma50 > 0 and sma20 > sma50 and price > sma20:
                        alerts.append({"symbol": symbol, "severity": "LOW", "type": "Golden Cross",
                            "message": f"50-day MA above 200-day MA with price above 20-day MA — bullish trend", "price": price})
                except:
                    continue

        # Sort: HIGH first, then MEDIUM, then LOW
        severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        alerts.sort(key=lambda x: severity_order.get(x["severity"], 3))

        return {"alerts": alerts, "count": len(alerts),
                "high": len([a for a in alerts if a["severity"] == "HIGH"]),
                "medium": len([a for a in alerts if a["severity"] == "MEDIUM"]),
                "low": len([a for a in alerts if a["severity"] == "LOW"])}

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ========== REPORTS ENDPOINTS ==========
from reports.report_generator import ReportGenerator
from reports.report_scheduler import ReportScheduler

report_generator = ReportGenerator(db, analyzer, recommender, news_scraper)
daily_report_scheduler = ReportScheduler(db, analyzer, news_scraper)

@app.get("/api/reports/daily")
async def get_daily_report(force: bool = False, date: str = ""):
    """
    Structured daily report with AI-scored picks.
    Returns cached report if available, generates fresh if not.
    ?force=true to regenerate. ?date=YYYY-MM-DD for historical.
    """
    try:
        target_date = date if date else None

        if not force:
            cached = daily_report_scheduler.get_cached_report(report_date=target_date)
            if cached:
                return cached

        if target_date:
            raise HTTPException(status_code=404, detail=f"No report found for {target_date}")

        report = daily_report_scheduler.generate_daily_report()
        return report
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/reports/weekly")
async def get_weekly_report():
    try:
        report = report_generator.generate_weekly_report()
        return {"type": "weekly", "report": report, "generated_at": __import__('datetime').datetime.now().isoformat()}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/reports/monthly")
async def get_monthly_report():
    try:
        report = report_generator.generate_monthly_report()
        return {"type": "monthly", "report": report, "generated_at": __import__('datetime').datetime.now().isoformat()}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ========== FINVIZ SCREENER ==========
from data_collection.finviz_scraper import FinvizScraper
finviz = FinvizScraper()

@app.get("/api/finviz/screener")
async def get_finviz_signals():
    try:
        results = finviz.get_all_signals()
        return {
            "stocks": results,
            "count": len(results),
            "generated_at": __import__("datetime").datetime.now().isoformat()
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/finviz/strong-buys")
async def get_strong_buys():
    try:
        results = finviz.get_strong_buys()
        return {"stocks": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== ANALYSIS HISTORY ENDPOINT ==========

@app.get("/api/analysis/{ticker}/history")
async def get_analysis_history(ticker: str):
    """Return last 30 analyses for a ticker for score trend charting."""
    try:
        symbol = ticker.upper()
        df = db.get_analysis_history(symbol, limit=30)

        history = []
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                history.append({
                    "date": str(row.get("timestamp", "")),
                    "composite_score": int(row.get("composite_score", 50)),
                    "technical_score": int(row.get("technical_score", 50)),
                    "fundamental_score": int(row.get("fundamental_score", 50)),
                    "sentiment_score": int(row.get("sentiment_score", 50)),
                    "ai_insight_score": int(row.get("ai_insight_score", 50)),
                    "signal": str(row.get("signal", "HOLD")),
                    "confidence": str(row.get("confidence", "")),
                    "entry_price": float(row.get("entry_price", 0)) if row.get("entry_price") else None,
                    "target_price": float(row.get("target_price", 0)) if row.get("target_price") else None,
                    "stop_loss": float(row.get("stop_loss", 0)) if row.get("stop_loss") else None,
                })

        return {"ticker": symbol, "history": history, "count": len(history)}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ========== PORTFOLIO IMPORT ENDPOINTS ==========
from pydantic import BaseModel as BM
from typing import Optional, List

class PendingImport(BM):
    action: str
    symbol: str
    company_name: str
    price: float
    trade_date: str
    email_id: str
    shares: Optional[float] = None

class ConfirmImport(BM):
    import_id: int
    shares: float

@app.post("/api/portfolio/pending")
async def add_pending_imports(trades: List[PendingImport]):
    """Receive parsed trades from Gmail and save as pending"""
    added = 0
    for trade in trades:
        success = db.add_pending_import(
            action=trade.action,
            symbol=trade.symbol,
            company_name=trade.company_name,
            price=trade.price,
            trade_date=trade.trade_date,
            email_id=trade.email_id,
            shares=trade.shares
        )
        if success:
            added += 1
    return {"added": added, "total": len(trades)}

@app.get("/api/portfolio/pending")
async def get_pending_imports():
    """Get all pending imports waiting for confirmation"""
    try:
        df = db.get_pending_imports()
        if df.empty:
            return {"pending": [], "count": 0}
        records = df.to_dict(orient="records")
        for r in records:
            for k, v in r.items():
                if hasattr(v, "item"):
                    r[k] = v.item()
        return {"pending": records, "count": len(records)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/portfolio/pending/confirm")
async def confirm_import(data: ConfirmImport):
    """Confirm a pending import and add to portfolio"""
    try:
        df = db.get_pending_imports()
        row = df[df["id"] == data.import_id]
        if row.empty:
            raise HTTPException(status_code=404, detail="Pending import not found")
        r = row.iloc[0]
        if r["action"] == "BOUGHT":
            db.add_portfolio_position(
                symbol=r["symbol"],
                shares=data.shares,
                purchase_price=float(r["price"]),
                purchase_date=str(r["trade_date"]),
                notes=f"Imported from Fidelity email"
            )
        db.delete_pending_import(data.import_id)
        return {"message": f"Successfully imported {r['action']} {r['symbol']}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/portfolio/pending/{import_id}")
async def dismiss_pending_import(import_id: int):
    """Dismiss a pending import without adding to portfolio"""
    db.delete_pending_import(import_id)
    return {"message": "Dismissed"}


# ========== NEWS INTELLIGENCE ENDPOINT ==========
import uuid
import json
from datetime import datetime, timedelta
from difflib import SequenceMatcher

# Cache timestamp for news intelligence
_news_cache_time = None
_news_cache_data = None

def _similarity(a: str, b: str) -> float:
    """Quick headline similarity check for deduplication."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def _source_credibility(source: str, source_type: str) -> int:
    """Score source credibility 0-100."""
    major = {"reuters", "bloomberg", "financial times", "wall street journal",
             "wsj", "cnbc", "associated press", "ap", "new york times", "nyt",
             "barron's", "marketwatch", "the economist"}
    mid = {"business insider", "yahoo finance", "investopedia", "seeking alpha",
           "motley fool", "benzinga", "thestreet"}
    src_lower = source.lower()
    if any(m in src_lower for m in major):
        return 90
    if any(m in src_lower for m in mid):
        return 65
    if source_type == "reddit":
        return 35
    if source_type == "finviz":
        return 55
    return 45

def _compute_importance(article: dict) -> int:
    """Compute importance score 0-100 for a raw article before AI analysis."""
    score = 50
    # Source credibility
    cred = _source_credibility(article.get("source", ""), article.get("source_type", ""))
    score = int(cred * 0.5)  # base from credibility

    # Recency bonus
    published = article.get("published_at", "")
    if published:
        try:
            if isinstance(published, str):
                pub_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
            else:
                pub_dt = published
            age_hours = (datetime.now(pub_dt.tzinfo) if pub_dt.tzinfo else datetime.now() - pub_dt).total_seconds() / 3600
        except Exception:
            age_hours = 24
        if hasattr(age_hours, '__float__'):
            pass
        else:
            try:
                age_td = datetime.now() - pub_dt.replace(tzinfo=None)
                age_hours = age_td.total_seconds() / 3600
            except Exception:
                age_hours = 24
        if age_hours < 1:
            score += 25
        elif age_hours < 6:
            score += 15
        elif age_hours < 24:
            score += 5

    return min(score, 100)

def _deduplicate_articles(articles: list) -> list:
    """Remove near-duplicate headlines, keeping the one from the best source."""
    if not articles:
        return []
    seen = []
    for article in articles:
        headline = article.get("headline", "")
        is_dup = False
        for i, existing in enumerate(seen):
            if _similarity(headline, existing["headline"]) > 0.7:
                # Merge source tags
                existing_tags = set(existing.get("source_tags", []))
                new_tags = set(article.get("source_tags", []))
                existing["source_tags"] = list(existing_tags | new_tags)
                # Keep higher credibility version
                if _source_credibility(article.get("source", ""), article.get("source_type", "")) > \
                   _source_credibility(existing.get("source", ""), existing.get("source_type", "")):
                    article["source_tags"] = existing["source_tags"]
                    seen[i] = article
                is_dup = True
                break
        if not is_dup:
            seen.append(article)
    return seen

def _collect_all_news() -> list:
    """Aggregate news from all sources into a unified list."""
    raw_articles = []

    # 1. NewsAPI — general market news
    try:
        news_items = news_scraper.fetch_general_market_news(days=1)
        for item in news_items:
            if item.get("source") == "Mock":
                continue
            raw_articles.append({
                "id": str(uuid.uuid4()),
                "headline": item.get("title", ""),
                "source": item.get("source", "Unknown"),
                "source_type": "major_outlet",
                "url": item.get("url", ""),
                "published_at": item.get("published_at", ""),
                "description": item.get("description", ""),
                "source_tags": ["newsapi"],
            })
    except Exception as e:
        print(f"⚠️  NewsAPI collection error: {e}")

    # 2. Reddit — scrape stock subreddits
    try:
        reddit_scraper_instance = RedditScraper(db)
        if reddit_scraper_instance.reddit is not None:
            for sub in ["wallstreetbets", "stocks", "investing", "stockmarket"]:
                try:
                    posts = reddit_scraper_instance.scrape_subreddit(sub, limit=15)
                    for post in posts:
                        raw_articles.append({
                            "id": str(uuid.uuid4()),
                            "headline": post.get("title", ""),
                            "source": f"r/{post.get('subreddit', sub)}",
                            "source_type": "reddit",
                            "url": post.get("url", ""),
                            "published_at": post.get("created_utc", datetime.now()).isoformat() if isinstance(post.get("created_utc"), datetime) else str(post.get("created_utc", "")),
                            "description": (post.get("selftext", "") or "")[:300],
                            "source_tags": ["reddit"],
                        })
                except Exception:
                    continue
    except Exception as e:
        print(f"⚠️  Reddit collection error: {e}")

    # 3. Finviz — top signals as news-like items
    try:
        finviz_results = finviz.get_all_signals()
        for stock in finviz_results[:30]:
            raw_articles.append({
                "id": str(uuid.uuid4()),
                "headline": f"{stock.get('symbol', '')} ({stock.get('company', '')}) — {stock.get('signal', 'Signal')} | {stock.get('sector', '')}",
                "source": "Finviz Screener",
                "source_type": "finviz",
                "url": f"https://finviz.com/quote.ashx?t={stock.get('symbol', '')}",
                "published_at": datetime.now().isoformat(),
                "description": f"Price: ${stock.get('price', 0)}, Change: {stock.get('change_pct', 0)}%, Volume: {stock.get('volume', 0)}, Market Cap: {stock.get('market_cap', '-')}",
                "source_tags": ["finviz"],
            })
    except Exception as e:
        print(f"⚠️  Finviz collection error: {e}")

    return raw_articles

def _ai_analyze_batch(articles: list) -> list:
    """Send a batch of articles to Claude for financial analysis."""
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ.get("CLAUDE_API_KEY", ""))

    # Build article summaries for the prompt
    article_texts = []
    for i, a in enumerate(articles):
        article_texts.append(f"{i+1}. [{a.get('source', '')}] {a.get('headline', '')}\n   {a.get('description', '')[:200]}")

    articles_block = "\n".join(article_texts)

    prompt = f"""You are a financial news analyst. For each article below, determine:

1. AFFECTED TICKER(S) — which specific stock(s) will be impacted. Be specific, not vague. If it's a macro story (Fed rates, tariffs), list the ETFs and sectors affected.
2. DIRECTION — bullish or bearish for each ticker
3. MAGNITUDE — low / medium / high impact
4. SIGNAL — one of: STRONG_BUY, BUY, WATCH, IGNORE, SELL, SHORT
5. TIME SENSITIVITY — is this actionable now, this week, or long-term?
6. REASONING — 2-3 sentences max explaining the trade logic

Be decisive. "WATCH" is acceptable for genuinely unclear situations, but don't default to it. If a story clearly helps or hurts a stock, say so.

Articles:
{articles_block}

Respond in JSON array format only. Each element should have:
- "article_index": (1-based index matching the article number above)
- "affected_tickers": [{{"ticker": "XXX", "direction": "bullish|bearish", "signal": "STRONG_BUY|BUY|WATCH|IGNORE|SELL|SHORT"}}]
- "magnitude": "low|medium|high"
- "time_sensitivity": "actionable_now|this_week|long_term"
- "reasoning": "string"

No preamble. JSON array only."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip()
        # Parse JSON — handle potential markdown wrapping
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        analyses = json.loads(text)
        return analyses
    except Exception as e:
        print(f"⚠️  AI analysis batch error: {e}")
        return []

def _build_intelligence_response(articles: list, ai_results: list) -> dict:
    """Merge raw articles with AI analysis results into the final response."""
    # Index AI results by article_index
    ai_map = {}
    for r in ai_results:
        idx = r.get("article_index")
        if idx is not None:
            ai_map[idx] = r

    enriched = []
    all_tickers = set()
    all_signals = set()
    all_sources = set()
    all_magnitudes = set()

    for i, article in enumerate(articles):
        ai = ai_map.get(i + 1, {})
        affected = ai.get("affected_tickers", [])
        magnitude = ai.get("magnitude", "low")
        reasoning = ai.get("reasoning", "")
        time_sensitivity = ai.get("time_sensitivity", "this_week")

        # Compute final importance score
        base_score = _compute_importance(article)
        # Boost based on AI analysis
        mag_boost = {"high": 25, "medium": 10, "low": 0}.get(magnitude, 0)
        ticker_boost = min(len(affected) * 3, 15)
        signal_boost = 0
        for t in affected:
            sig = t.get("signal", "WATCH")
            if sig in ("STRONG_BUY", "SHORT"):
                signal_boost = max(signal_boost, 15)
            elif sig in ("BUY", "SELL"):
                signal_boost = max(signal_boost, 8)
        importance = min(base_score + mag_boost + ticker_boost + signal_boost, 100)

        for t in affected:
            all_tickers.add(t.get("ticker", ""))
            all_signals.add(t.get("signal", ""))
        all_sources.add(article.get("source", "").lower())
        all_magnitudes.add(magnitude)

        enriched_article = {
            "id": article.get("id", str(uuid.uuid4())),
            "headline": article.get("headline", ""),
            "source": article.get("source", ""),
            "source_type": article.get("source_type", ""),
            "url": article.get("url", ""),
            "published_at": article.get("published_at", ""),
            "importance_score": importance,
            "ai_analysis": {
                "affected_tickers": affected,
                "magnitude": magnitude,
                "time_sensitivity": time_sensitivity,
                "reasoning": reasoning,
            },
            "source_tags": article.get("source_tags", []),
        }
        enriched.append(enriched_article)

        # Save to DB
        try:
            db.save_news_intelligence({
                "id": enriched_article["id"],
                "headline": enriched_article["headline"],
                "source": enriched_article["source"],
                "url": enriched_article["url"],
                "published_at": enriched_article["published_at"],
                "importance_score": importance,
                "affected_tickers": json.dumps(affected),
                "signals": json.dumps([t.get("signal") for t in affected]),
                "magnitude": magnitude,
                "reasoning": reasoning,
            })
        except Exception:
            pass

    # Sort by importance descending
    enriched.sort(key=lambda x: x["importance_score"], reverse=True)

    all_tickers.discard("")
    all_signals.discard("")

    return {
        "generated_at": datetime.now().isoformat(),
        "article_count": len(enriched),
        "articles": enriched,
        "filters_available": {
            "tickers": sorted(list(all_tickers)),
            "signals": sorted(list(all_signals)),
            "sources": sorted(list(all_sources)),
            "magnitude": sorted(list(all_magnitudes)),
        }
    }

@app.get("/api/news/intelligence")
async def get_news_intelligence(ticker: str = "", signal: str = "", source: str = "", magnitude: str = "", refresh: bool = False):
    """Multi-source news intelligence with AI analysis, cached for 15 minutes."""
    global _news_cache_time, _news_cache_data

    try:
        # Check cache (15 minutes)
        now = datetime.now()
        if not refresh and _news_cache_data and _news_cache_time and (now - _news_cache_time).total_seconds() < 900:
            data = _news_cache_data
        else:
            # Check DB cache first
            cached_df = db.get_cached_news_intelligence(max_age_minutes=15)
            if not refresh and cached_df is not None and not cached_df.empty and len(cached_df) >= 5:
                # Rebuild response from DB cache
                articles = []
                all_tickers = set()
                all_signals_set = set()
                all_sources_set = set()
                all_magnitudes_set = set()

                for _, row in cached_df.iterrows():
                    affected = []
                    try:
                        affected = json.loads(row.get("affected_tickers", "[]"))
                    except Exception:
                        pass
                    sigs = []
                    try:
                        sigs = json.loads(row.get("signals", "[]"))
                    except Exception:
                        pass

                    for t in affected:
                        all_tickers.add(t.get("ticker", ""))
                        all_signals_set.add(t.get("signal", ""))
                    all_sources_set.add(str(row.get("source", "")).lower())
                    all_magnitudes_set.add(str(row.get("magnitude", "")))

                    articles.append({
                        "id": str(row.get("id", "")),
                        "headline": str(row.get("headline", "")),
                        "source": str(row.get("source", "")),
                        "source_type": "",
                        "url": str(row.get("url", "")),
                        "published_at": str(row.get("published_at", "")),
                        "importance_score": int(row.get("importance_score", 0)),
                        "ai_analysis": {
                            "affected_tickers": affected,
                            "magnitude": str(row.get("magnitude", "")),
                            "time_sensitivity": "this_week",
                            "reasoning": str(row.get("reasoning", "")),
                        },
                        "source_tags": [],
                    })

                all_tickers.discard("")
                all_signals_set.discard("")
                articles.sort(key=lambda x: x["importance_score"], reverse=True)

                data = {
                    "generated_at": datetime.now().isoformat(),
                    "article_count": len(articles),
                    "articles": articles,
                    "filters_available": {
                        "tickers": sorted(list(all_tickers)),
                        "signals": sorted(list(all_signals_set)),
                        "sources": sorted(list(all_sources_set)),
                        "magnitude": sorted(list(all_magnitudes_set)),
                    }
                }
            else:
                # Fresh fetch: collect, deduplicate, AI analyze
                print("📰 Collecting news from all sources...")
                raw = _collect_all_news()
                print(f"   Raw articles: {len(raw)}")

                # Deduplicate
                deduped = _deduplicate_articles(raw)
                print(f"   After dedup: {len(deduped)}")

                # Limit to top ~40 for AI analysis (cost control)
                deduped = deduped[:40]

                # AI analyze in batches of 8
                all_ai_results = []
                batch_size = 8
                for batch_start in range(0, len(deduped), batch_size):
                    batch = deduped[batch_start:batch_start + batch_size]
                    # Adjust article indices for this batch
                    results = _ai_analyze_batch(batch)
                    # Re-index to global position
                    for r in results:
                        r["article_index"] = r.get("article_index", 0) + batch_start
                    all_ai_results.extend(results)

                # Build final response
                data = _build_intelligence_response(deduped, all_ai_results)

                # Clean old entries
                try:
                    db.clear_old_news_intelligence(hours=48)
                except Exception:
                    pass

            # Update in-memory cache
            _news_cache_time = now
            _news_cache_data = data

        # Apply filters
        articles = data["articles"]
        if ticker:
            ticker_upper = ticker.upper()
            articles = [a for a in articles if any(
                t.get("ticker", "").upper() == ticker_upper
                for t in a.get("ai_analysis", {}).get("affected_tickers", [])
            )]
        if signal:
            signal_upper = signal.upper()
            articles = [a for a in articles if any(
                t.get("signal", "").upper() == signal_upper
                for t in a.get("ai_analysis", {}).get("affected_tickers", [])
            )]
        if source:
            source_lower = source.lower()
            articles = [a for a in articles if source_lower in a.get("source", "").lower()]
        if magnitude:
            mag_lower = magnitude.lower()
            articles = [a for a in articles if a.get("ai_analysis", {}).get("magnitude", "").lower() == mag_lower]

        return {
            "generated_at": data["generated_at"],
            "article_count": len(articles),
            "articles": articles,
            "filters_available": data["filters_available"],
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ========== BERKELEY ENRICHMENT ENDPOINT ==========
from data_collection.berkeley.enrichment_manager import BerkeleyEnrichmentManager

berkeley_enrichment = BerkeleyEnrichmentManager()

@app.get("/api/enrichment/{ticker}")
async def get_enrichment_data(ticker: str):
    """Return Berkeley institutional enrichment data for a ticker (testing/debug)."""
    try:
        symbol = ticker.upper().strip()
        if not symbol.isalpha() or len(symbol) > 10:
            raise HTTPException(status_code=400, detail="Invalid ticker symbol")

        data = await berkeley_enrichment.enrich(symbol)
        return {
            "ticker": symbol,
            "sources": list(data.keys()),
            "data": data,
            "generated_at": __import__("datetime").datetime.now().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
