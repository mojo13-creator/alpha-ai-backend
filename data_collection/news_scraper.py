# data_collection/news_scraper.py
"""
News Scraper - Fetches latest financial news
"""

from datetime import datetime, timedelta
import config

class NewsScraper:
    """Fetches financial news from various sources"""
    
    def __init__(self, db_manager):
        self.db = db_manager
        print("📰 News Scraper initializing...")
        
        # Reload config to get latest values
        import importlib
        importlib.reload(config)
        
        print(f"   API Key: {config.NEWS_API_KEY[:10]}..." if len(config.NEWS_API_KEY) > 10 else "   API Key: NOT SET")
        
        # Check if News API is configured
        if config.NEWS_API_KEY == "your_newsapi_key_here" or not config.NEWS_API_KEY:

            print("⚠️  News API not configured. Get a key from https://newsapi.org")
            self.newsapi = None
        else:
            try:
                from newsapi import NewsApiClient
                self.newsapi = NewsApiClient(api_key=config.NEWS_API_KEY)
                print("✅ News API connected")
            except ImportError:
                print("⚠️  newsapi-python not installed. Run: pip install newsapi-python")
                self.newsapi = None
            except Exception as e:
                print(f"❌ News API connection failed: {e}")
                self.newsapi = None
    
    def fetch_stock_news(self, symbol, days=7):
        """Fetch news for a specific stock"""
        if not self.newsapi:
            print("⚠️  News API not available")
            # Return mock data for testing
            return [{
                'symbol': symbol,
                'title': f'Mock news for {symbol}',
                'description': 'News API not configured. Add your API key to config.py',
                'url': 'https://newsapi.org',
                'source': 'Mock',
                'published_at': datetime.now().isoformat()
            }]
        
        try:
            to_date = datetime.now()
            from_date = to_date - timedelta(days=days)
            
            query = f"{symbol} stock OR {symbol} shares"
            
            print(f"📰 Fetching news for {symbol}...")
            
            articles = self.newsapi.get_everything(
                q=query,
                from_param=from_date.strftime('%Y-%m-%d'),
                to=to_date.strftime('%Y-%m-%d'),
                language='en',
                sort_by='relevancy',
                page_size=20
            )
            
            news_list = []
            for article in articles.get('articles', []):
                news_list.append({
                    'symbol': symbol,
                    'title': article['title'],
                    'description': article.get('description', ''),
                    'url': article['url'],
                    'source': article['source']['name'],
                    'published_at': article['publishedAt'],
                    'content': article.get('content', '')
                })
            
            print(f"✅ Found {len(news_list)} news articles for {symbol}")
            return news_list
            
        except Exception as e:
            print(f"❌ Error fetching news for {symbol}: {e}")
            return []
    
    def fetch_general_market_news(self, days=1):
        """Fetch general market news"""
        if not self.newsapi:
            print("⚠️  News API not available")
            return [{
                'symbol': None,
                'title': 'Mock market news',
                'description': 'News API not configured. Get a free key from newsapi.org',
                'url': 'https://newsapi.org',
                'source': 'Mock',
                'published_at': datetime.now().isoformat()
            }]
        
        try:
            to_date = datetime.now()
            from_date = to_date - timedelta(days=days)
            
            print("📰 Fetching general market news...")
            
            articles = self.newsapi.get_everything(
                q='stock market OR wall street OR nasdaq OR dow jones OR S&P 500',
                from_param=from_date.strftime('%Y-%m-%d'),
                to=to_date.strftime('%Y-%m-%d'),
                language='en',
                sort_by='publishedAt',
                page_size=50
            )
            
            news_list = []
            for article in articles.get('articles', []):
                news_list.append({
                    'symbol': None,
                    'title': article['title'],
                    'description': article.get('description', ''),
                    'url': article['url'],
                    'source': article['source']['name'],
                    'published_at': article['publishedAt']
                })
            
            print(f"✅ Found {len(news_list)} general market news articles")
            return news_list
            
        except Exception as e:
            print(f"❌ Error fetching market news: {e}")
            return []
    
    def save_news(self, news_list):
        """Save news articles to database"""
        saved_count = 0
        
        for article in news_list:
            success = self.db.save_news(
                symbol=article.get('symbol'),
                title=article['title'],
                description=article.get('description', ''),
                url=article['url'],
                source=article['source'],
                published_at=article['published_at'],
                sentiment_score=0
            )
            if success:
                saved_count += 1
        
        print(f"✅ Saved {saved_count} news articles to database")
        return saved_count