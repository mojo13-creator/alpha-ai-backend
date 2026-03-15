# data_collection/stock_data.py
"""
Stock Data Collector
Fetches stock data from Yahoo Finance and saves to database
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time

class StockDataCollector:
    """Fetches and manages stock data"""
    
    def __init__(self, db_manager):
        self.db = db_manager
        print("📊 Stock Data Collector initialized")
    
    def fetch_stock_data(self, symbol, period="1y", interval="1d"):
        """
        Fetch historical stock data from Yahoo Finance
        
        Parameters:
        - symbol: Stock ticker (e.g., 'AAPL')
        - period: Time period ('1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max')
        - interval: Data interval ('1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h', '1d', '5d', '1wk', '1mo', '3mo')
        """
        try:
            print(f"📥 Fetching {period} of data for {symbol.upper()}...")
            
            stock = yf.Ticker(symbol)
            df = stock.history(period=period, interval=interval)
            
            if df.empty:
                print(f"❌ No data found for {symbol.upper()}")
                return None
            
            print(f"✅ Retrieved {len(df)} records for {symbol.upper()}")
            return df
            
        except Exception as e:
            print(f"❌ Error fetching {symbol.upper()}: {str(e)}")
            return None
    
    def fetch_and_save(self, symbol, period="1y", interval="1d"):
        """Fetch data and save to database"""
        df = self.fetch_stock_data(symbol, period, interval)
        
        if df is not None and not df.empty:
            count = self.db.save_stock_prices(symbol, df)
            return count > 0
        
        return False
    
    def fetch_multiple_stocks(self, symbols, period="1y", delay=0.5):
        """
        Fetch data for multiple stocks
        
        Parameters:
        - symbols: List of stock tickers
        - period: Time period to fetch
        - delay: Delay between requests (seconds) to avoid rate limiting
        """
        results = {}
        total = len(symbols)
        
        print(f"\n🔄 Fetching data for {total} stocks...")
        print("=" * 50)
        
        for i, symbol in enumerate(symbols, 1):
            print(f"\n[{i}/{total}] Processing {symbol.upper()}...")
            
            success = self.fetch_and_save(symbol, period)
            results[symbol.upper()] = success
            
            if i < total:
                time.sleep(delay)  # Polite delay between requests
        
        print("\n" + "=" * 50)
        successful = sum(1 for v in results.values() if v)
        print(f"✅ Successfully fetched {successful}/{total} stocks")
        
        return results
    
    def get_current_price(self, symbol):
        """Get the current/latest price of a stock"""
        try:
            stock = yf.Ticker(symbol)
            data = stock.history(period="1d")
            
            if not data.empty:
                price = data['Close'].iloc[-1]
                print(f"💰 {symbol.upper()}: ${price:.2f}")
                return price
            
            return None
            
        except Exception as e:
            print(f"❌ Error getting price for {symbol.upper()}: {str(e)}")
            return None
    
    def get_multiple_prices(self, symbols):
        """Get current prices for multiple stocks"""
        prices = {}
        
        for symbol in symbols:
            price = self.get_current_price(symbol)
            if price:
                prices[symbol.upper()] = price
            time.sleep(0.3)
        
        return prices
    
    def get_stock_info(self, symbol):
        """Get detailed information about a stock"""
        try:
            print(f"ℹ️  Fetching info for {symbol.upper()}...")
            
            stock = yf.Ticker(symbol)
            info = stock.info
            
            stock_info = {
                'symbol': symbol.upper(),
                'name': info.get('longName', 'N/A'),
                'sector': info.get('sector', 'N/A'),
                'industry': info.get('industry', 'N/A'),
                'market_cap': info.get('marketCap', 0),
                'pe_ratio': info.get('forwardPE', None),
                'trailing_pe': info.get('trailingPE', None),
                'dividend_yield': info.get('dividendYield', 0),
                'beta': info.get('beta', None),
                '52_week_high': info.get('fiftyTwoWeekHigh', 0),
                '52_week_low': info.get('fiftyTwoWeekLow', 0),
                'avg_volume': info.get('averageVolume', 0),
                'description': info.get('longBusinessSummary', 'N/A'),
                'website': info.get('website', 'N/A'),
                'employees': info.get('fullTimeEmployees', 'N/A'),
                'previous_close': info.get('previousClose', 0),
                'current_price': info.get('currentPrice', 0)
            }
            
            print(f"✅ Got info for {stock_info['name']}")
            return stock_info
            
        except Exception as e:
            print(f"❌ Error getting info for {symbol.upper()}: {str(e)}")
            return None
    
    def get_price_change(self, symbol, days=1):
        """Calculate price change over specified days"""
        df = self.db.get_stock_prices(symbol, limit=days+1)
        
        if df.empty or len(df) < 2:
            return None
        
        current_price = df.iloc[0]['close']
        old_price = df.iloc[-1]['close']
        
        change = current_price - old_price
        change_pct = (change / old_price) * 100
        
        return {
            'current': current_price,
            'previous': old_price,
            'change': change,
            'change_pct': change_pct
        }
    
    def update_all_watchlist_stocks(self, period="1mo"):
        """Update data for all stocks in watchlist"""
        watchlist = self.db.get_watchlist()
        
        if watchlist.empty:
            print("⚠️  Watchlist is empty!")
            return {}
        
        symbols = watchlist['symbol'].tolist()
        print(f"\n🔄 Updating {len(symbols)} stocks from watchlist...")
        
        return self.fetch_multiple_stocks(symbols, period=period)
    
    def search_stock(self, query):
        """Search for a stock by name or symbol"""
        try:
            # Try as ticker first
            ticker = yf.Ticker(query)
            info = ticker.info
            
            if 'symbol' in info:
                return {
                    'symbol': info.get('symbol', query.upper()),
                    'name': info.get('longName', 'N/A'),
                    'type': info.get('quoteType', 'N/A')
                }
            
            return None
            
        except Exception as e:
            print(f"❌ Could not find stock: {query}")
            return None