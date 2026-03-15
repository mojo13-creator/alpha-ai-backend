# database/db_manager.py
"""
Database Manager for Stock Analyzer
Handles all database operations including creating tables,
saving data, and retrieving information.
"""

import sqlite3
import pandas as pd
from datetime import datetime
import json

class DatabaseManager:
    """Manages all database operations"""
    
    def __init__(self, db_path="stock_data.db"):
        """Initialize database connection"""
        self.db_path = db_path
        print(f"📁 Initializing database at: {db_path}")
        self.init_database()
    
    def get_connection(self):
        """Create and return a database connection"""
        return sqlite3.connect(self.db_path)
    
    def init_database(self):
        """Create all necessary database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        print("🔨 Creating database tables...")
        
        # ===== STOCK PRICES TABLE =====
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                date DATE NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                adj_close REAL,
                UNIQUE(symbol, date)
            )
        ''')
        
        # ===== TECHNICAL INDICATORS TABLE =====
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS technical_indicators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                date DATE NOT NULL,
                indicator_name TEXT NOT NULL,
                value REAL,
                UNIQUE(symbol, date, indicator_name)
            )
        ''')
        
        # ===== NEWS TABLE =====
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                title TEXT,
                description TEXT,
                url TEXT UNIQUE,
                source TEXT,
                published_at DATETIME,
                sentiment_score REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # ===== REDDIT POSTS TABLE =====
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reddit_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id TEXT UNIQUE,
                symbol TEXT,
                subreddit TEXT,
                title TEXT,
                selftext TEXT,
                score INTEGER,
                num_comments INTEGER,
                created_utc DATETIME,
                sentiment_score REAL,
                url TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # ===== RECOMMENDATIONS TABLE =====
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                date DATE NOT NULL,
                recommendation TEXT,
                score REAL,
                reasoning TEXT,
                price_at_recommendation REAL,
                target_price REAL,
                stop_loss REAL,
                UNIQUE(symbol, date)
            )
        ''')
        
        # ===== PORTFOLIO TABLE =====
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS portfolio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                shares REAL,
                purchase_price REAL,
                purchase_date DATE,
                current_price REAL,
                last_updated DATETIME,
                notes TEXT
            )
        ''')
        
        # ===== WATCHLIST TABLE =====
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT UNIQUE,
                added_date DATE,
                notes TEXT,
                priority INTEGER DEFAULT 0
            )
        ''')
        
        # ===== REPORTS ARCHIVE TABLE =====
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_type TEXT,
                date DATE,
                content TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # ===== STOCK INFO TABLE =====
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT UNIQUE,
                name TEXT,
                sector TEXT,
                industry TEXT,
                market_cap REAL,
                pe_ratio REAL,
                dividend_yield REAL,
                beta REAL,
                last_updated DATETIME
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ Database initialized successfully!")
    
    # ========== STOCK PRICE OPERATIONS ==========
    
    def save_stock_prices(self, symbol, df):
        """Save stock price data to database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        count = 0
        for date, row in df.iterrows():
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO stock_prices 
                    (symbol, date, open, high, low, close, volume, adj_close)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    symbol.upper(),
                    date.strftime('%Y-%m-%d'),
                    float(row['Open']),
                    float(row['High']),
                    float(row['Low']),
                    float(row['Close']),
                    int(row['Volume']),
                    float(row['Close'])  # adj_close
                ))
                count += 1
            except Exception as e:
                print(f"⚠️  Error saving {symbol} for {date}: {e}")
        
        conn.commit()
        conn.close()
        print(f"✅ Saved {count} price records for {symbol}")
        return count
    
    def get_stock_prices(self, symbol, start_date=None, end_date=None, limit=None):
        """Retrieve stock prices from database"""
        conn = self.get_connection()
        
        query = f"SELECT * FROM stock_prices WHERE symbol = '{symbol.upper()}'"
        
        if start_date:
            query += f" AND date >= '{start_date}'"
        if end_date:
            query += f" AND date <= '{end_date}'"
        
        query += " ORDER BY date DESC"
        
        if limit:
            query += f" LIMIT {limit}"
        
        df = pd.read_sql_query(query, conn, parse_dates=['date'])
        conn.close()
        
        return df
    
    def get_latest_price(self, symbol):
        """Get the most recent price for a symbol"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT close, date FROM stock_prices 
            WHERE symbol = ? 
            ORDER BY date DESC 
            LIMIT 1
        ''', (symbol.upper(),))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {'price': result[0], 'date': result[1]}
        return None
    
    # ========== WATCHLIST OPERATIONS ==========
    
    def add_to_watchlist(self, symbol, notes="", priority=0):
        """Add a stock to watchlist"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO watchlist (symbol, added_date, notes, priority)
                VALUES (?, ?, ?, ?)
            ''', (symbol.upper(), datetime.now().date(), notes, priority))
            conn.commit()
            print(f"✅ Added {symbol.upper()} to watchlist")
            return True
        except sqlite3.IntegrityError:
            print(f"⚠️  {symbol.upper()} is already in watchlist")
            return False
        finally:
            conn.close()
    
    def remove_from_watchlist(self, symbol):
        """Remove a stock from watchlist"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM watchlist WHERE symbol = ?', (symbol.upper(),))
        conn.commit()
        deleted = cursor.rowcount
        conn.close()
        
        if deleted:
            print(f"✅ Removed {symbol.upper()} from watchlist")
            return True
        else:
            print(f"⚠️  {symbol.upper()} not found in watchlist")
            return False
    
    def get_watchlist(self):
        """Get all stocks in watchlist"""
        conn = self.get_connection()
        df = pd.read_sql_query(
            "SELECT * FROM watchlist ORDER BY priority DESC, added_date DESC", 
            conn
        )
        conn.close()
        return df
    
    # ========== RECOMMENDATION OPERATIONS ==========
    
    def save_recommendation(self, symbol, recommendation, score, reasoning, price, target_price=None, stop_loss=None):
        """Save a stock recommendation"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO recommendations 
            (symbol, date, recommendation, score, reasoning, price_at_recommendation, target_price, stop_loss)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            symbol.upper(),
            datetime.now().date(),
            recommendation,
            score,
            reasoning,
            price,
            target_price,
            stop_loss
        ))
        
        conn.commit()
        conn.close()
        print(f"✅ Saved {recommendation} recommendation for {symbol.upper()}")
    
    def get_latest_recommendations(self, days=7, limit=None):
        """Get recent recommendations"""
        conn = self.get_connection()
        
        query = f'''
            SELECT * FROM recommendations 
            WHERE date >= date('now', '-{days} days')
            ORDER BY date DESC, score DESC
        '''
        
        if limit:
            query += f" LIMIT {limit}"
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    
    def get_recommendation_performance(self, symbol, days=30):
        """Check how past recommendations performed"""
        conn = self.get_connection()
        
        # Get recommendations
        recs = pd.read_sql_query(f'''
            SELECT * FROM recommendations 
            WHERE symbol = '{symbol.upper()}'
            AND date >= date('now', '-{days} days')
            ORDER BY date DESC
        ''', conn)
        
        # Get current price
        latest = self.get_latest_price(symbol)
        
        conn.close()
        
        if recs.empty or not latest:
            return None
        
        # Calculate performance
        recs['current_price'] = latest['price']
        recs['gain_loss_pct'] = ((recs['current_price'] - recs['price_at_recommendation']) / 
                                  recs['price_at_recommendation'] * 100)
        
        return recs
    
    # ========== NEWS OPERATIONS ==========
    
    def save_news(self, symbol, title, description, url, source, published_at, sentiment_score=0):
        """Save news article"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO news 
                (symbol, title, description, url, source, published_at, sentiment_score)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (symbol, title, description, url, source, published_at, sentiment_score))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Article already exists
            return False
        finally:
            conn.close()
    
    def get_recent_news(self, symbol=None, days=7, limit=20):
        """Get recent news articles"""
        conn = self.get_connection()
        
        if symbol:
            query = f'''
                SELECT * FROM news 
                WHERE symbol = '{symbol.upper()}'
                AND published_at >= datetime('now', '-{days} days')
                ORDER BY published_at DESC
                LIMIT {limit}
            '''
        else:
            query = f'''
                SELECT * FROM news 
                WHERE published_at >= datetime('now', '-{days} days')
                ORDER BY published_at DESC
                LIMIT {limit}
            '''
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    
    # ========== UTILITY FUNCTIONS ==========
    
    def get_all_symbols(self):
        """Get list of all symbols in database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT DISTINCT symbol FROM stock_prices ORDER BY symbol')
        symbols = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        return symbols
    
    def get_database_stats(self):
        """Get statistics about the database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        stats = {}
        
        # Count records in each table
        tables = ['stock_prices', 'watchlist', 'recommendations', 'news', 'reddit_posts', 'portfolio']
        
        for table in tables:
            cursor.execute(f'SELECT COUNT(*) FROM {table}')
            stats[table] = cursor.fetchone()[0]
        
        # Get unique symbols
        cursor.execute('SELECT COUNT(DISTINCT symbol) FROM stock_prices')
        stats['unique_symbols'] = cursor.fetchone()[0]
        
        conn.close()
        return stats
    
    def clear_old_data(self, days=365):
        """Remove data older than specified days (except watchlist)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Clear old stock prices
        cursor.execute(f"DELETE FROM stock_prices WHERE date < date('now', '-{days} days')")
        prices_deleted = cursor.rowcount
        
        # Clear old news
        cursor.execute(f"DELETE FROM news WHERE published_at < datetime('now', '-{days} days')")
        news_deleted = cursor.rowcount
        
        # Clear old reddit posts
        cursor.execute(f"DELETE FROM reddit_posts WHERE created_utc < datetime('now', '-{days} days')")
        reddit_deleted = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        print(f"🗑️  Cleared old data:")
        print(f"   - {prices_deleted} price records")
        print(f"   - {news_deleted} news articles")
        print(f"   - {reddit_deleted} reddit posts")
def save_report(self, report_type, content):
        """Save generated report to database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO reports (report_type, date, content)
            VALUES (?, ?, ?)
        ''', (report_type, datetime.now().date(), content))
        
        conn.commit()
        conn.close()
        print(f"✅ {report_type} report saved to database")    

def save_report(self, report_type, content):
        """Save generated report to database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO reports (report_type, date, content)
                VALUES (?, ?, ?)
            ''', (report_type, datetime.now().date(), content))
            
            conn.commit()
            print(f"✅ {report_type} report saved to database")
            return True
        except Exception as e:
            print(f"❌ Error saving report: {e}")
            return False
        finally:
            conn.close()
    
def get_latest_report(self, report_type):
        """Get the most recent report of a specific type"""
        conn = self.get_connection()
        
        query = '''
            SELECT * FROM reports 
            WHERE report_type = ? 
            ORDER BY created_at DESC 
            LIMIT 1
        '''
        
        report = pd.read_sql_query(query, conn, params=(report_type,))
        conn.close()
        
        return report       