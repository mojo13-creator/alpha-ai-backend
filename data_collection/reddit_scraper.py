"""
Reddit Sentiment Scraper - No API key required
Uses Reddit's public JSON API
"""
import requests
import time
from datetime import datetime

HEADERS = {'User-Agent': 'AlphaAI/1.0 StockAnalyzer'}

SUBREDDITS = ['wallstreetbets', 'stocks', 'investing', 'stockmarket']

def fetch_reddit_sentiment(symbol: str, limit: int = 25) -> dict:
    """
    Fetch Reddit posts mentioning a stock symbol.
    Returns sentiment summary for use in AI analysis.
    """
    posts = []
    
    for subreddit in SUBREDDITS:
        try:
            url = f"https://www.reddit.com/r/{subreddit}/search.json"
            params = {
                'q': symbol,
                'sort': 'new',
                'limit': limit,
                't': 'week',
                'restrict_sr': 1
            }
            response = requests.get(url, headers=HEADERS, params=params, timeout=10)
            
            if response.status_code != 200:
                continue
                
            data = response.json()
            children = data.get('data', {}).get('children', [])
            
            for post in children:
                p = post.get('data', {})
                posts.append({
                    'title': p.get('title', ''),
                    'score': p.get('score', 0),
                    'upvote_ratio': p.get('upvote_ratio', 0.5),
                    'num_comments': p.get('num_comments', 0),
                    'subreddit': subreddit,
                    'created': datetime.fromtimestamp(p.get('created_utc', 0)).isoformat(),
                    'url': f"https://reddit.com{p.get('permalink', '')}",
                })
            
            time.sleep(0.5)  # be polite
            
        except Exception as e:
            print(f"⚠️  Reddit error for r/{subreddit}: {e}")
            continue
    
    if not posts:
        return {
            'post_count': 0,
            'sentiment_score': 50,
            'sentiment_label': 'NEUTRAL',
            'top_posts': [],
            'summary': f'No recent Reddit discussion found for {symbol}.'
        }
    
    # Score sentiment based on upvote ratios and scores
    total_weight = 0
    weighted_sentiment = 0
    
    for post in posts:
        weight = max(post['score'], 1) + post['num_comments']
        sentiment = post['upvote_ratio']  # 0-1, higher = more bullish
        weighted_sentiment += sentiment * weight
        total_weight += weight
    
    avg_sentiment = (weighted_sentiment / total_weight) if total_weight > 0 else 0.5
    sentiment_score = int(avg_sentiment * 100)
    
    if sentiment_score >= 70:
        label = 'BULLISH'
    elif sentiment_score <= 40:
        label = 'BEARISH'
    else:
        label = 'NEUTRAL'
    
    # Top posts by engagement
    top_posts = sorted(posts, key=lambda x: x['score'] + x['num_comments'], reverse=True)[:5]
    
    return {
        'post_count': len(posts),
        'sentiment_score': sentiment_score,
        'sentiment_label': label,
        'top_posts': top_posts,
        'summary': f"{len(posts)} Reddit posts found. Community sentiment: {label} ({sentiment_score}/100)."
    }


if __name__ == '__main__':
    result = fetch_reddit_sentiment('AAPL')
    print(f"Posts found: {result['post_count']}")
    print(f"Sentiment: {result['sentiment_label']} ({result['sentiment_score']}/100)")
    for post in result['top_posts'][:3]:
        print(f"  [{post['subreddit']}] {post['title'][:80]}")
