# data_collection/reddit_scraper.py
"""
Reddit Scraper - Collects stock mentions and sentiment from Reddit
"""

import praw
from datetime import datetime
import re
import config

class RedditScraper:
    """Scrapes Reddit for stock mentions and sentiment"""
    
    def __init__(self, db_manager):
        self.db = db_manager
        print("🤖 Reddit Scraper initialized")
        
        # Check if Reddit credentials are configured
        if config.REDDIT_CLIENT_ID == "your_reddit_client_id_here":
            print("⚠️  Reddit API not configured. Set credentials in config.py")
            self.reddit = None
        else:
            try:
                self.reddit = praw.Reddit(
                    client_id=config.REDDIT_CLIENT_ID,
                    client_secret=config.REDDIT_CLIENT_SECRET,
                    user_agent=config.REDDIT_USER_AGENT
                )
                print("✅ Reddit API connected")
            except Exception as e:
                print(f"❌ Reddit API connection failed: {e}")
                self.reddit = None
    
    def extract_tickers(self, text):
        """Extract stock tickers from text (must be $XXX or XXX format)"""
        # Match $AAPL or standalone AAPL (2-5 uppercase letters)
        pattern = r'\$([A-Z]{2,5})\b|\b([A-Z]{2,5})\b'
        matches = re.findall(pattern, text.upper())
        
        # Flatten and remove common words
        tickers = [m[0] or m[1] for m in matches]
        
        # Filter out common non-ticker words
        exclude = ['THE', 'AND', 'FOR', 'ARE', 'BUT', 'NOT', 'YOU', 'ALL', 'CAN', 'HER', 'WAS', 'ONE', 'OUR', 'OUT', 'DAY', 'GET', 'HAS', 'HIM', 'HIS', 'HOW', 'ITS', 'MAY', 'NEW', 'NOW', 'OLD', 'SEE', 'TWO', 'WHO', 'BOY', 'DID', 'ITS', 'LET', 'PUT', 'SAY', 'SHE', 'TOO', 'USE']
        
        tickers = [t for t in tickers if t not in exclude and len(t) <= 5]
        
        return list(set(tickers))  # Remove duplicates
    
    def scrape_subreddit(self, subreddit_name, limit=25, time_filter='day'):
        """
        Scrape a subreddit for stock mentions
        
        time_filter: 'hour', 'day', 'week', 'month', 'year', 'all'
        """
        if not self.reddit:
            print("⚠️  Reddit API not configured")
            return []
        
        try:
            print(f"📡 Scraping r/{subreddit_name}...")
            subreddit = self.reddit.subreddit(subreddit_name)
            posts = []
            
            for post in subreddit.hot(limit=limit):
                # Extract tickers from title and body
                text = f"{post.title} {post.selftext}"
                tickers = self.extract_tickers(text)
                
                if tickers:  # Only save posts that mention stock tickers
                    post_data = {
                        'post_id': post.id,
                        'subreddit': subreddit_name,
                        'title': post.title,
                        'selftext': post.selftext[:500],  # Limit text length
                        'score': post.score,
                        'num_comments': post.num_comments,
                        'created_utc': datetime.fromtimestamp(post.created_utc),
                        'url': post.url,
                        'tickers': tickers
                    }
                    posts.append(post_data)
            
            print(f"✅ Found {len(posts)} relevant posts in r/{subreddit_name}")
            return posts
            
        except Exception as e:
            print(f"❌ Error scraping r/{subreddit_name}: {e}")
            return []
    
    def scrape_all_subreddits(self, limit=25):
        """Scrape all configured subreddits"""
        all_posts = []
        
        for subreddit in config.SUBREDDITS:
            posts = self.scrape_subreddit(subreddit, limit=limit)
            all_posts.extend(posts)
        
        return all_posts
    
    def save_posts(self, posts):
        """Save Reddit posts to database"""
        saved_count = 0
        
        for post in posts:
            for ticker in post['tickers']:
                try:
                    # Save to database (we'll add this method to db_manager)
                    # For now, just count
                    saved_count += 1
                except Exception as e:
                    print(f"Error saving post: {e}")
        
        print(f"✅ Processed {saved_count} ticker mentions from Reddit")
        return saved_count
    
    def get_trending_tickers(self, posts, min_mentions=3):
        """Get most mentioned tickers from posts"""
        ticker_counts = {}
        
        for post in posts:
            for ticker in post['tickers']:
                ticker_counts[ticker] = ticker_counts.get(ticker, 0) + 1
        
        # Filter by minimum mentions and sort
        trending = {k: v for k, v in ticker_counts.items() if v >= min_mentions}
        trending = dict(sorted(trending.items(), key=lambda x: x[1], reverse=True))
        
        return trending
    
    def analyze_sentiment_simple(self, text):
        """
        Simple sentiment analysis (positive/negative words)
        Returns score from -1 (negative) to +1 (positive)
        """
        positive_words = ['bullish', 'moon', 'buy', 'calls', 'long', 'up', 'gain', 'profit', 'winner', 'rocket', 'green', 'bull']
        negative_words = ['bearish', 'sell', 'puts', 'short', 'down', 'loss', 'dump', 'crash', 'red', 'bear', 'rip']
        
        text_lower = text.lower()
        
        pos_count = sum(1 for word in positive_words if word in text_lower)
        neg_count = sum(1 for word in negative_words if word in text_lower)
        
        total = pos_count + neg_count
        if total == 0:
            return 0
        
        return (pos_count - neg_count) / total