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
    period = request.period
    
    try:
        print(f"\n📊 Fetching data for {symbol}...")
        collector.fetch_stock_data(symbol, period=period)
        
        latest_price = db.get_latest_price(symbol)
        if not latest_price:
            raise HTTPException(status_code=404, detail=f"No data found for {symbol}")
        
        print(f"📈 Calculating indicators...")
        df = analyzer.calculate_all_indicators(symbol)
        
        if df is None or len(df) == 0:
            raise HTTPException(status_code=500, detail="Technical analysis failed")
        
        latest = df.iloc[-1]
        price = float(latest['close'])
        
        print(f"🤖 Getting recommendation...")
        result = recommender.analyze_and_recommend(symbol)
        
        if not result:
            raise HTTPException(status_code=500, detail="AI analysis failed")
        
        news_list = []
        reddit_data = {}
        try:
            print(f"🔴 Fetching Reddit sentiment...")
            reddit_data = fetch_reddit_sentiment(symbol)
            print(f"✅ Reddit: {reddit_data['sentiment_label']} ({reddit_data['sentiment_score']}/100)")
            print(f"📰 Fetching news...")
            news_articles = news_scraper.fetch_stock_news(symbol, days=7)
            if news_articles and len(news_articles) > 0:
                news_list = [
                    {
                        "title": article.get('title', 'No title'),
                        "source": article.get('source', 'Unknown'),
                        "url": article.get('url', ''),
                        "published": article.get('published', '')
                    }
                    for article in news_articles[:5]
                ]
        except Exception as e:
            print(f"⚠️  News/Reddit fetch error: {e}")
        
        technical_data = {
            "rsi": safe_float(latest.get('RSI', 50), 50),
            "macd": safe_float(latest.get('MACD', 0)),
            "macd_signal": safe_float(latest.get('MACD_Signal', 0)),
            "sma_20": safe_float(latest.get('SMA_20', price), price),
            "sma_50": safe_float(latest.get('SMA_50', price), price),
            "sma_200": safe_float(latest.get('SMA_200', price), price),
            "volume": int(latest.get('volume', 0)),
            "bb_upper": safe_float(latest.get('BB_Upper', price), price),
            "bb_lower": safe_float(latest.get('BB_Lower', price), price),
        }
        
        response = {
            "symbol": symbol,
            "price": float(result.get('price', price)),
            "recommendation": result.get('recommendation', 'HOLD'),
            "score": int(result.get('score', 50)),
            "reasoning": str(result.get('reasoning', 'Analysis complete')),
            "timestamp": str(result.get('timestamp', '')),
            "technical_data": technical_data,
            "news": news_list,
        }
        
        # Get price history
        price_rows = db.get_stock_prices(symbol, limit=365)
        price_history = []
        if price_rows is not None and not price_rows.empty:
            for _, row in price_rows.iterrows():
                price_history.append({
                    "date": str(row["date"]),
                    "close": float(row["close"]),
                    "open": float(row["open"]) if row["open"] else float(row["close"]),
                    "high": float(row["high"]) if row["high"] else float(row["close"]),
                    "low": float(row["low"]) if row["low"] else float(row["close"]),
                    "volume": int(row["volume"]) if row["volume"] else 0,
                })
        response["price_history"] = price_history
        response["reddit"] = reddit_data
        print(f"✅ Analysis complete for {symbol}")
        return response
    
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

@app.get("/api/portfolio")
async def get_portfolio():
    try:
        import yfinance as yf
        import sqlite3
        conn = sqlite3.connect("stock_data.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM portfolio ORDER BY symbol")
        rows = cursor.fetchall()
        conn.close()

        positions = []
        total_value = 0
        total_cost = 0

        for row in rows:
            symbol = row["symbol"]
            shares = float(row["shares"] or 0)
            purchase_price = float(row["purchase_price"] or 0)
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.fast_info
                current_price = float(info.last_price)
            except:
                current_price = purchase_price

            market_value = shares * current_price
            cost_basis = shares * purchase_price
            pnl = market_value - cost_basis
            pnl_pct = ((current_price - purchase_price) / purchase_price * 100) if purchase_price > 0 else 0

            total_value += market_value
            total_cost += cost_basis

            positions.append({
                "id": row["id"],
                "symbol": symbol,
                "shares": shares,
                "purchase_price": round(purchase_price, 2),
                "current_price": round(current_price, 2),
                "market_value": round(market_value, 2),
                "cost_basis": round(cost_basis, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
                "purchase_date": row["purchase_date"] or "",
                "notes": row["notes"] or "",
            })

        total_pnl = total_value - total_cost
        total_pnl_pct = ((total_value - total_cost) / total_cost * 100) if total_cost > 0 else 0

        return {
            "positions": positions,
            "summary": {
                "total_value": round(total_value, 2),
                "total_cost": round(total_cost, 2),
                "total_pnl": round(total_pnl, 2),
                "total_pnl_pct": round(total_pnl_pct, 2),
                "position_count": len(positions),
            }
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/portfolio")
async def add_position(request: PortfolioRequest):
    try:
        import sqlite3
        conn = sqlite3.connect("stock_data.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO portfolio (symbol, shares, purchase_price, purchase_date, notes, last_updated)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        """, (request.symbol.upper(), request.shares, request.purchase_price,
              request.purchase_date, request.notes))
        conn.commit()
        conn.close()
        return {"message": f"Added {request.symbol.upper()} to portfolio"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/portfolio/{position_id}")
async def delete_position(position_id: int):
    try:
        import sqlite3
        conn = sqlite3.connect("stock_data.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM portfolio WHERE id = ?", (position_id,))
        conn.commit()
        conn.close()
        return {"message": "Position removed"}
    except Exception as e:
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

report_generator = ReportGenerator(db, analyzer, recommender, news_scraper)

@app.get("/api/reports/daily")
async def get_daily_report():
    try:
        report = report_generator.generate_daily_report()
        return {"type": "daily", "report": report, "generated_at": __import__('datetime').datetime.now().isoformat()}
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
