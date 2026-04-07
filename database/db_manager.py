# database/db_manager.py
"""
Database Manager - Auto-detects SQLite (local) or PostgreSQL (Railway)
"""

import os
import pandas as pd
from datetime import datetime

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    import psycopg2
    import psycopg2.extras
    DB_TYPE = "postgres"
    print(f"🐘 Using PostgreSQL (Railway)")
else:
    import sqlite3
    DB_TYPE = "sqlite"
    print(f"📁 Using SQLite (local)")

PH = "%s" if DB_TYPE == "postgres" else "?"

class DatabaseManager:

    def __init__(self, db_path="stock_data.db"):
        self.db_path = db_path
        if DB_TYPE == "sqlite":
            print(f"📁 Initializing database at: {db_path}")
        else:
            print(f"📁 Initializing database: PostgreSQL")
        self.init_database()

    def get_connection(self):
        if DB_TYPE == "postgres":
            return psycopg2.connect(DATABASE_URL)
        else:
            return sqlite3.connect(self.db_path)

    def init_database(self):
        print("🔨 Creating database tables...")
        conn = self.get_connection()
        cursor = conn.cursor()

        if DB_TYPE == "postgres":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stock_prices (
                    id SERIAL PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    date DATE NOT NULL,
                    open REAL, high REAL, low REAL, close REAL,
                    volume BIGINT, adj_close REAL,
                    UNIQUE(symbol, date)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS technical_indicators (
                    id SERIAL PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    date DATE NOT NULL,
                    indicator_name TEXT NOT NULL,
                    value REAL,
                    UNIQUE(symbol, date, indicator_name)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS news (
                    id SERIAL PRIMARY KEY,
                    symbol TEXT, title TEXT, description TEXT,
                    url TEXT UNIQUE, source TEXT,
                    published_at TIMESTAMP, sentiment_score REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reddit_posts (
                    id SERIAL PRIMARY KEY,
                    post_id TEXT UNIQUE, symbol TEXT, subreddit TEXT,
                    title TEXT, selftext TEXT, score INTEGER,
                    num_comments INTEGER, created_utc TIMESTAMP,
                    sentiment_score REAL, url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recommendations (
                    id SERIAL PRIMARY KEY,
                    symbol TEXT NOT NULL, date DATE NOT NULL,
                    recommendation TEXT, score REAL, reasoning TEXT,
                    price_at_recommendation REAL, target_price REAL, stop_loss REAL,
                    UNIQUE(symbol, date)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS portfolio (
                    id SERIAL PRIMARY KEY,
                    symbol TEXT NOT NULL, shares REAL,
                    purchase_price REAL, purchase_date DATE,
                    current_price REAL, last_updated TIMESTAMP, notes TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS watchlist (
                    id SERIAL PRIMARY KEY,
                    symbol TEXT UNIQUE, added_date DATE,
                    notes TEXT, priority INTEGER DEFAULT 0
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reports (
                    id SERIAL PRIMARY KEY,
                    report_type TEXT, date DATE, content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stock_info (
                    id SERIAL PRIMARY KEY,
                    symbol TEXT UNIQUE, name TEXT, sector TEXT,
                    industry TEXT, market_cap REAL, pe_ratio REAL,
                    dividend_yield REAL, beta REAL, last_updated TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pending_imports (
                    id SERIAL PRIMARY KEY,
                    action TEXT, symbol TEXT, company_name TEXT,
                    price REAL, trade_date DATE, shares REAL,
                    source TEXT DEFAULT 'gmail',
                    email_id TEXT UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS analysis_history (
                    id SERIAL PRIMARY KEY,
                    ticker TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    composite_score INTEGER,
                    technical_score INTEGER,
                    fundamental_score INTEGER,
                    sentiment_score INTEGER,
                    ai_insight_score INTEGER,
                    signal TEXT,
                    confidence TEXT,
                    risk_level TEXT,
                    entry_price REAL,
                    stop_loss REAL,
                    target_price REAL,
                    weight_profile TEXT,
                    market_cap_category TEXT,
                    raw_response TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS news_intelligence (
                    id TEXT PRIMARY KEY,
                    headline TEXT,
                    source TEXT,
                    url TEXT,
                    published_at TIMESTAMP,
                    importance_score INTEGER,
                    affected_tickers TEXT,
                    signals TEXT,
                    magnitude TEXT,
                    reasoning TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stock_prices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL, date DATE NOT NULL,
                    open REAL, high REAL, low REAL, close REAL,
                    volume INTEGER, adj_close REAL,
                    UNIQUE(symbol, date)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS technical_indicators (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL, date DATE NOT NULL,
                    indicator_name TEXT NOT NULL, value REAL,
                    UNIQUE(symbol, date, indicator_name)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS news (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT, title TEXT, description TEXT,
                    url TEXT UNIQUE, source TEXT,
                    published_at DATETIME, sentiment_score REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reddit_posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_id TEXT UNIQUE, symbol TEXT, subreddit TEXT,
                    title TEXT, selftext TEXT, score INTEGER,
                    num_comments INTEGER, created_utc DATETIME,
                    sentiment_score REAL, url TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL, date DATE NOT NULL,
                    recommendation TEXT, score REAL, reasoning TEXT,
                    price_at_recommendation REAL, target_price REAL, stop_loss REAL,
                    UNIQUE(symbol, date)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS portfolio (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL, shares REAL,
                    purchase_price REAL, purchase_date DATE,
                    current_price REAL, last_updated DATETIME, notes TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS watchlist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT UNIQUE, added_date DATE,
                    notes TEXT, priority INTEGER DEFAULT 0
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_type TEXT, date DATE, content TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stock_info (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT UNIQUE, name TEXT, sector TEXT,
                    industry TEXT, market_cap REAL, pe_ratio REAL,
                    dividend_yield REAL, beta REAL, last_updated DATETIME
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pending_imports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT, symbol TEXT, company_name TEXT,
                    price REAL, trade_date DATE, shares REAL,
                    source TEXT DEFAULT 'gmail',
                    email_id TEXT UNIQUE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS analysis_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    composite_score INTEGER,
                    technical_score INTEGER,
                    fundamental_score INTEGER,
                    sentiment_score INTEGER,
                    ai_insight_score INTEGER,
                    signal TEXT,
                    confidence TEXT,
                    risk_level TEXT,
                    entry_price REAL,
                    stop_loss REAL,
                    target_price REAL,
                    weight_profile TEXT,
                    market_cap_category TEXT,
                    raw_response TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS news_intelligence (
                    id TEXT PRIMARY KEY,
                    headline TEXT,
                    source TEXT,
                    url TEXT,
                    published_at DATETIME,
                    importance_score INTEGER,
                    affected_tickers TEXT,
                    signals TEXT,
                    magnitude TEXT,
                    reasoning TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

        conn.commit()
        conn.close()
        print("✅ Database initialized successfully!")

    # ========== STOCK PRICE OPERATIONS ==========

    def save_stock_prices(self, symbol, df):
        conn = self.get_connection()
        cursor = conn.cursor()
        count = 0
        for date, row in df.iterrows():
            try:
                if DB_TYPE == "postgres":
                    cursor.execute("""
                        INSERT INTO stock_prices (symbol, date, open, high, low, close, volume, adj_close)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (symbol, date) DO UPDATE SET
                            open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
                            close=EXCLUDED.close, volume=EXCLUDED.volume, adj_close=EXCLUDED.adj_close
                    """, (symbol.upper(), date.strftime("%Y-%m-%d"),
                          float(row["Open"]), float(row["High"]), float(row["Low"]),
                          float(row["Close"]), int(row["Volume"]), float(row["Close"])))
                else:
                    cursor.execute("""
                        INSERT OR REPLACE INTO stock_prices
                        (symbol, date, open, high, low, close, volume, adj_close)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (symbol.upper(), date.strftime("%Y-%m-%d"),
                          float(row["Open"]), float(row["High"]), float(row["Low"]),
                          float(row["Close"]), int(row["Volume"]), float(row["Close"])))
                count += 1
            except Exception as e:
                print(f"⚠️  Error saving {symbol} for {date}: {e}")
        conn.commit()
        conn.close()
        print(f"✅ Saved {count} price records for {symbol}")
        return count

    def get_stock_prices(self, symbol, start_date=None, end_date=None, limit=None):
        conn = self.get_connection()
        ph = PH
        query = f"SELECT * FROM stock_prices WHERE symbol = {ph}"
        params = [symbol.upper()]
        if start_date:
            query += f" AND date >= {ph}"; params.append(start_date)
        if end_date:
            query += f" AND date <= {ph}"; params.append(end_date)
        query += " ORDER BY date DESC"
        if limit:
            query += f" LIMIT {limit}"
        df = pd.read_sql_query(query, conn, params=params, parse_dates=["date"])
        conn.close()
        return df

    def get_latest_price(self, symbol):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT close, date FROM stock_prices WHERE symbol = {PH} ORDER BY date DESC LIMIT 1", (symbol.upper(),))
        result = cursor.fetchone()
        conn.close()
        if result:
            return {"price": result[0], "date": result[1]}
        return None

    # ========== WATCHLIST OPERATIONS ==========

    def add_to_watchlist(self, symbol, notes="", priority=0):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if DB_TYPE == "postgres":
                cursor.execute("""
                    INSERT INTO watchlist (symbol, added_date, notes, priority)
                    VALUES (%s, %s, %s, %s) ON CONFLICT (symbol) DO NOTHING
                """, (symbol.upper(), datetime.now().date(), notes, priority))
            else:
                cursor.execute("""
                    INSERT INTO watchlist (symbol, added_date, notes, priority)
                    VALUES (?, ?, ?, ?)
                """, (symbol.upper(), datetime.now().date(), notes, priority))
            conn.commit()
            print(f"✅ Added {symbol.upper()} to watchlist")
            return True
        except Exception as e:
            print(f"⚠️  Error adding to watchlist: {e}")
            return False
        finally:
            conn.close()

    def remove_from_watchlist(self, symbol):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM watchlist WHERE symbol = {PH}", (symbol.upper(),))
        conn.commit()
        deleted = cursor.rowcount
        conn.close()
        return deleted > 0

    def get_watchlist(self):
        conn = self.get_connection()
        df = pd.read_sql_query("SELECT * FROM watchlist ORDER BY priority DESC, added_date DESC", conn)
        conn.close()
        return df

    # ========== PORTFOLIO OPERATIONS ==========

    def add_portfolio_position(self, symbol, shares, purchase_price, purchase_date=None, notes=""):
        conn = self.get_connection()
        cursor = conn.cursor()
        if purchase_date is None:
            purchase_date = datetime.now().date()
        cursor.execute(f"""
            INSERT INTO portfolio (symbol, shares, purchase_price, purchase_date, last_updated, notes)
            VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH})
        """, (symbol.upper(), shares, purchase_price, purchase_date, datetime.now(), notes))
        conn.commit()
        row_id = cursor.lastrowid if DB_TYPE == "sqlite" else None
        if DB_TYPE == "postgres":
            cursor.execute("SELECT lastval()")
            row_id = cursor.fetchone()[0]
        conn.close()
        return row_id

    def get_portfolio(self):
        conn = self.get_connection()
        df = pd.read_sql_query("SELECT * FROM portfolio ORDER BY symbol", conn)
        conn.close()
        return df

    def delete_portfolio_position(self, position_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM portfolio WHERE id = {PH}", (position_id,))
        conn.commit()
        deleted = cursor.rowcount
        conn.close()
        return deleted > 0

    # ========== RECOMMENDATION OPERATIONS ==========

    def save_recommendation(self, symbol, recommendation, score, reasoning, price, target_price=None, stop_loss=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        if DB_TYPE == "postgres":
            cursor.execute("""
                INSERT INTO recommendations
                (symbol, date, recommendation, score, reasoning, price_at_recommendation, target_price, stop_loss)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (symbol, date) DO UPDATE SET
                    recommendation=EXCLUDED.recommendation, score=EXCLUDED.score,
                    reasoning=EXCLUDED.reasoning, price_at_recommendation=EXCLUDED.price_at_recommendation,
                    target_price=EXCLUDED.target_price, stop_loss=EXCLUDED.stop_loss
            """, (symbol.upper(), datetime.now().date(), recommendation, score, reasoning, price, target_price, stop_loss))
        else:
            cursor.execute("""
                INSERT OR REPLACE INTO recommendations
                (symbol, date, recommendation, score, reasoning, price_at_recommendation, target_price, stop_loss)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (symbol.upper(), datetime.now().date(), recommendation, score, reasoning, price, target_price, stop_loss))
        conn.commit()
        conn.close()

    def get_latest_recommendations(self, days=7, limit=None):
        conn = self.get_connection()
        if DB_TYPE == "postgres":
            query = f"SELECT * FROM recommendations WHERE date >= NOW() - INTERVAL '{days} days' ORDER BY date DESC, score DESC"
        else:
            query = f"SELECT * FROM recommendations WHERE date >= date('now', '-{days} days') ORDER BY date DESC, score DESC"
        if limit:
            query += f" LIMIT {limit}"
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df

    # ========== NEWS OPERATIONS ==========

    def save_news(self, symbol, title, description, url, source, published_at, sentiment_score=0):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if DB_TYPE == "postgres":
                cursor.execute("""
                    INSERT INTO news (symbol, title, description, url, source, published_at, sentiment_score)
                    VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (url) DO NOTHING
                """, (symbol, title, description, url, source, published_at, sentiment_score))
            else:
                cursor.execute("""
                    INSERT INTO news (symbol, title, description, url, source, published_at, sentiment_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (symbol, title, description, url, source, published_at, sentiment_score))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    def get_recent_news(self, symbol=None, days=7, limit=20):
        conn = self.get_connection()
        if DB_TYPE == "postgres":
            interval = f"NOW() - INTERVAL '{days} days'"
        else:
            interval = f"datetime('now', '-{days} days')"
        if symbol:
            query = f"SELECT * FROM news WHERE symbol = '{symbol.upper()}' AND published_at >= {interval} ORDER BY published_at DESC LIMIT {limit}"
        else:
            query = f"SELECT * FROM news WHERE published_at >= {interval} ORDER BY published_at DESC LIMIT {limit}"
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df

    # ========== REPORTS OPERATIONS ==========

    def save_report(self, report_type, content):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(f"""
                INSERT INTO reports (report_type, date, content)
                VALUES ({PH}, {PH}, {PH})
            """, (report_type, datetime.now().date(), content))
            conn.commit()
            print(f"✅ {report_type} report saved")
            return True
        except Exception as e:
            print(f"❌ Error saving report: {e}")
            return False
        finally:
            conn.close()

    def get_latest_report(self, report_type):
        conn = self.get_connection()
        query = f"SELECT * FROM reports WHERE report_type = {PH} ORDER BY created_at DESC LIMIT 1"
        df = pd.read_sql_query(query, conn, params=(report_type,))
        conn.close()
        return df

    # ========== UTILITY ==========

    def get_all_symbols(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT symbol FROM stock_prices ORDER BY symbol")
        symbols = [row[0] for row in cursor.fetchall()]
        conn.close()
        return symbols

    def get_database_stats(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        stats = {}
        for table in ["stock_prices", "watchlist", "recommendations", "news", "reddit_posts", "portfolio"]:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            stats[table] = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(DISTINCT symbol) FROM stock_prices")
        stats["unique_symbols"] = cursor.fetchone()[0]
        conn.close()
        return stats

    def clear_old_data(self, days=365):
        conn = self.get_connection()
        cursor = conn.cursor()
        if DB_TYPE == "postgres":
            cursor.execute(f"DELETE FROM stock_prices WHERE date < NOW() - INTERVAL '{days} days'")
            p = cursor.rowcount
            cursor.execute(f"DELETE FROM news WHERE published_at < NOW() - INTERVAL '{days} days'")
            n = cursor.rowcount
            cursor.execute(f"DELETE FROM reddit_posts WHERE created_utc < NOW() - INTERVAL '{days} days'")
            r = cursor.rowcount
        else:
            cursor.execute(f"DELETE FROM stock_prices WHERE date < date('now', '-{days} days')")
            p = cursor.rowcount
            cursor.execute(f"DELETE FROM news WHERE published_at < datetime('now', '-{days} days')")
            n = cursor.rowcount
            cursor.execute(f"DELETE FROM reddit_posts WHERE created_utc < datetime('now', '-{days} days')")
            r = cursor.rowcount
        conn.commit()
        conn.close()
        print(f"🗑️  Cleared {p} prices, {n} news, {r} reddit posts")

    def add_pending_import(self, action, symbol, company_name, price, trade_date, email_id, shares=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(f"""
                INSERT INTO pending_imports (action, symbol, company_name, price, trade_date, shares, email_id)
                VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH})
            """, (action, symbol, company_name, price, trade_date, shares, email_id))
            conn.commit()
            return True
        except Exception:
            return False  # duplicate email_id
        finally:
            conn.close()

    def get_pending_imports(self):
        conn = self.get_connection()
        df = pd.read_sql_query("SELECT * FROM pending_imports ORDER BY trade_date DESC", conn)
        conn.close()
        return df

    def update_pending_shares(self, import_id, shares):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(f"UPDATE pending_imports SET shares = {PH} WHERE id = {PH}", (shares, import_id))
        conn.commit()
        conn.close()

    def delete_pending_import(self, import_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM pending_imports WHERE id = {PH}", (import_id,))
        conn.commit()
        conn.close()

    def clear_pending_imports(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM pending_imports")
        conn.commit()
        conn.close()

    # ========== ANALYSIS HISTORY OPERATIONS ==========

    def save_analysis_history(self, ticker, composite_score, technical_score,
                               fundamental_score, sentiment_score, ai_insight_score,
                               signal, confidence, risk_level, entry_price,
                               stop_loss, target_price, weight_profile,
                               market_cap_category, raw_response=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(f"""
                INSERT INTO analysis_history
                (ticker, composite_score, technical_score, fundamental_score,
                 sentiment_score, ai_insight_score, signal, confidence, risk_level,
                 entry_price, stop_loss, target_price, weight_profile,
                 market_cap_category, raw_response)
                VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})
            """, (ticker.upper(), composite_score, technical_score, fundamental_score,
                  sentiment_score, ai_insight_score, signal, confidence, risk_level,
                  entry_price, stop_loss, target_price, weight_profile,
                  market_cap_category, raw_response))
            conn.commit()
            return True
        except Exception as e:
            print(f"⚠️  Error saving analysis history: {e}")
            return False
        finally:
            conn.close()

    def get_analysis_history(self, ticker, limit=30):
        conn = self.get_connection()
        query = f"""
            SELECT * FROM analysis_history
            WHERE ticker = {PH}
            ORDER BY timestamp DESC
            LIMIT {limit}
        """
        df = pd.read_sql_query(query, conn, params=(ticker.upper(),))
        conn.close()
        return df

    # ========== NEWS INTELLIGENCE OPERATIONS ==========

    def save_news_intelligence(self, article):
        """Save a single news intelligence article (dict with id, headline, etc.)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if DB_TYPE == "postgres":
                cursor.execute("""
                    INSERT INTO news_intelligence
                    (id, headline, source, url, published_at, importance_score,
                     affected_tickers, signals, magnitude, reasoning)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (id) DO UPDATE SET
                        importance_score=EXCLUDED.importance_score,
                        affected_tickers=EXCLUDED.affected_tickers,
                        signals=EXCLUDED.signals,
                        reasoning=EXCLUDED.reasoning
                """, (article["id"], article["headline"], article["source"],
                      article["url"], article["published_at"],
                      article["importance_score"], article["affected_tickers"],
                      article["signals"], article["magnitude"], article["reasoning"]))
            else:
                cursor.execute("""
                    INSERT OR REPLACE INTO news_intelligence
                    (id, headline, source, url, published_at, importance_score,
                     affected_tickers, signals, magnitude, reasoning)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                """, (article["id"], article["headline"], article["source"],
                      article["url"], article["published_at"],
                      article["importance_score"], article["affected_tickers"],
                      article["signals"], article["magnitude"], article["reasoning"]))
            conn.commit()
            return True
        except Exception as e:
            print(f"⚠️  Error saving news intelligence: {e}")
            return False
        finally:
            conn.close()

    def get_cached_news_intelligence(self, max_age_minutes=15):
        """Return cached news if fresh enough, else empty DataFrame."""
        conn = self.get_connection()
        if DB_TYPE == "postgres":
            age_check = f"created_at >= NOW() - INTERVAL '{max_age_minutes} minutes'"
        else:
            age_check = f"created_at >= datetime('now', '-{max_age_minutes} minutes')"
        query = f"SELECT * FROM news_intelligence WHERE {age_check} ORDER BY importance_score DESC"
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df

    def clear_old_news_intelligence(self, hours=24):
        """Remove news intelligence older than N hours."""
        conn = self.get_connection()
        cursor = conn.cursor()
        if DB_TYPE == "postgres":
            cursor.execute(f"DELETE FROM news_intelligence WHERE created_at < NOW() - INTERVAL '{hours} hours'")
        else:
            cursor.execute(f"DELETE FROM news_intelligence WHERE created_at < datetime('now', '-{hours} hours')")
        conn.commit()
        conn.close()
