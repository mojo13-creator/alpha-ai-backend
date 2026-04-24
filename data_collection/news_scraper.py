# data_collection/news_scraper.py
"""
News Scraper - Fetches latest financial news via newsapi.ai (Event Registry).

Public interface is preserved for drop-in compatibility with the prior
newsapi.org-based implementation: NewsScraper(db_manager),
fetch_stock_news(symbol, days=7), fetch_general_market_news(days=1),
save_news(news_list). Returned article dicts keep the same keys
(symbol, title, description, url, source, published_at, content).
"""

from datetime import datetime, timedelta
import requests
import config

EVENT_REGISTRY_URL = "https://eventregistry.org/api/v1/article/getArticles"


class NewsScraper:
    """Fetches financial news from newsapi.ai (Event Registry)."""

    def __init__(self, db_manager):
        self.db = db_manager
        print("📰 News Scraper initializing...")

        import importlib
        importlib.reload(config)

        key = config.NEWS_API_KEY or ""
        print(f"   API Key: {key[:10]}..." if len(key) > 10 else "   API Key: NOT SET")

        if not key or key == "your_newsapi_key_here":
            print("⚠️  News API not configured. Get a key from https://newsapi.ai")
            self.api_key = None
        else:
            self.api_key = key
            print("✅ News API (newsapi.ai / Event Registry) configured")

    def _post(self, payload):
        payload = dict(payload)
        payload["apiKey"] = self.api_key
        r = requests.post(EVENT_REGISTRY_URL, json=payload, timeout=20)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and data.get("error"):
            raise RuntimeError(f"newsapi.ai error: {data['error']}")
        return data

    @staticmethod
    def _normalize(article, symbol=None):
        body = article.get("body", "") or ""
        description = body[:300].strip()
        source = article.get("source") or {}
        dt_pub = article.get("dateTimePub") or article.get("dateTime") or ""
        return {
            "symbol": symbol,
            "title": article.get("title", "") or "",
            "description": description,
            "url": article.get("url", "") or "",
            "source": source.get("title") or source.get("uri") or "Unknown",
            "published_at": dt_pub,
            "content": body,
        }

    def fetch_stock_news(self, symbol, days=7):
        """Fetch news for a specific stock."""
        if not self.api_key:
            print("⚠️  News API not available")
            return [{
                "symbol": symbol,
                "title": f"Mock news for {symbol}",
                "description": "News API not configured. Add NEWS_API_KEY to .env",
                "url": "https://newsapi.ai",
                "source": "Mock",
                "published_at": datetime.now().isoformat(),
                "content": "",
            }]

        to_date = datetime.now()
        from_date = to_date - timedelta(days=days)

        print(f"📰 Fetching news for {symbol}...")
        try:
            data = self._post({
                "action": "getArticles",
                "keyword": [f"{symbol} stock", f"{symbol} shares"],
                "keywordOper": "or",
                "lang": "eng",
                "dateStart": from_date.strftime("%Y-%m-%d"),
                "dateEnd": to_date.strftime("%Y-%m-%d"),
                "articlesSortBy": "rel",
                "articlesCount": 20,
                "resultType": "articles",
            })
            results = (data.get("articles") or {}).get("results", [])
            news_list = [self._normalize(a, symbol=symbol) for a in results]
            print(f"✅ Found {len(news_list)} news articles for {symbol}")
            return news_list
        except Exception as e:
            print(f"❌ Error fetching news for {symbol}: {e}")
            return []

    def fetch_general_market_news(self, days=1):
        """Fetch general market news across several catalyst buckets."""
        if not self.api_key:
            print("⚠️  News API not available")
            return [{
                "symbol": None,
                "title": "Mock market news",
                "description": "News API not configured. Get a key from newsapi.ai",
                "url": "https://newsapi.ai",
                "source": "Mock",
                "published_at": datetime.now().isoformat(),
            }]

        to_date = datetime.now()
        from_date = to_date - timedelta(days=days)

        print("📰 Fetching general market news...")

        # Each bucket is a list of OR'd keywords; buckets cover catalyst types.
        keyword_buckets = [
            ["stock market", "wall street", "nasdaq", "S&P 500"],
            ["FDA approval", "breakthrough", "clinical trial results"],
            ["earnings beat", "revenue surprise", "guidance raised"],
            ["tariff", "sanctions", "geopolitical", "trade war"],
            ["acquisition", "merger", "IPO", "buyback"],
            ["upgrade", "price target raised", "analyst bullish"],
        ]

        news_list = []
        seen_urls = set()

        for keywords in keyword_buckets:
            try:
                data = self._post({
                    "action": "getArticles",
                    "keyword": keywords,
                    "keywordOper": "or",
                    "lang": "eng",
                    "dateStart": from_date.strftime("%Y-%m-%d"),
                    "dateEnd": to_date.strftime("%Y-%m-%d"),
                    "articlesSortBy": "date",
                    "articlesCount": 30,
                    "resultType": "articles",
                })
                results = (data.get("articles") or {}).get("results", [])
                for a in results:
                    url = a.get("url", "")
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    item = self._normalize(a, symbol=None)
                    item.pop("content", None)
                    news_list.append(item)
            except Exception as eq:
                label = ", ".join(keywords)[:40]
                print(f"   ⚠️  Bucket '{label}...' failed: {eq}")
                continue

        print(f"✅ Found {len(news_list)} general market news articles (multi-query)")
        return news_list

    def save_news(self, news_list):
        """Save news articles to database."""
        saved_count = 0
        for article in news_list:
            success = self.db.save_news(
                symbol=article.get("symbol"),
                title=article["title"],
                description=article.get("description", ""),
                url=article["url"],
                source=article["source"],
                published_at=article["published_at"],
                sentiment_score=0,
            )
            if success:
                saved_count += 1
        print(f"✅ Saved {saved_count} news articles to database")
        return saved_count
