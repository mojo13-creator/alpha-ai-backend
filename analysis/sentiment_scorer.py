# analysis/sentiment_scorer.py
"""
Programmatic Sentiment Score Calculator (0-100)
Sources: NewsAPI headlines, Reddit mentions, Finviz analyst consensus.
"""

import math
from datetime import datetime


def safe_float(val, default=0.0):
    try:
        v = float(val)
        return default if math.isnan(v) or math.isinf(v) else v
    except Exception:
        return default


# Word lists for simple headline sentiment
BULLISH_WORDS = [
    'surge', 'soar', 'rally', 'beat', 'exceed', 'upgrade', 'buy',
    'bullish', 'gain', 'profit', 'record', 'high', 'growth', 'strong',
    'outperform', 'breakout', 'accelerat', 'positive', 'optimis',
    'raise', 'upside', 'boom', 'momentum', 'win',
]

BEARISH_WORDS = [
    'crash', 'plunge', 'drop', 'miss', 'downgrade', 'sell', 'bearish',
    'loss', 'decline', 'weak', 'fail', 'underperform', 'cut', 'risk',
    'warning', 'fear', 'negative', 'pessimis', 'deficit', 'debt',
    'layoff', 'restructur', 'bankrupt', 'fraud', 'lawsuit', 'probe',
    'investig', 'recall', 'default',
]


def _score_headline(text):
    """Score a single headline. Returns -1 to +1."""
    if not text:
        return 0
    text_lower = text.lower()
    bull = sum(1 for w in BULLISH_WORDS if w in text_lower)
    bear = sum(1 for w in BEARISH_WORDS if w in text_lower)
    total = bull + bear
    if total == 0:
        return 0
    return (bull - bear) / total


def score_news_sentiment(news_articles):
    """
    Score sentiment from news headlines (0-100).
    news_articles: list of dicts with 'title', 'description', 'published_at' keys.
    """
    if not news_articles:
        return 50, [], 'neutral'

    scores = []
    for article in news_articles[:20]:  # Cap at 20
        title = article.get('title', '')
        desc = article.get('description', '')
        text = f"{title} {desc}"
        s = _score_headline(text)
        scores.append(s)

    if not scores:
        return 50, [], 'neutral'

    avg_sentiment = sum(scores) / len(scores)

    # Convert -1..+1 to 0..100
    news_score = 50 + (avg_sentiment * 40)  # +-40 range from headlines
    news_score = max(0, min(100, round(news_score)))

    bullish_count = sum(1 for s in scores if s > 0.1)
    bearish_count = sum(1 for s in scores if s < -0.1)
    neutral_count = len(scores) - bullish_count - bearish_count

    signals = []
    if bullish_count > bearish_count * 2:
        label = 'bullish'
        signals.append(f'{bullish_count} bullish vs {bearish_count} bearish headlines')
    elif bearish_count > bullish_count * 2:
        label = 'bearish'
        signals.append(f'{bearish_count} bearish vs {bullish_count} bullish headlines')
    elif bullish_count > bearish_count:
        label = 'slightly bullish'
        signals.append(f'News slightly bullish ({bullish_count}B/{bearish_count}S/{neutral_count}N)')
    elif bearish_count > bullish_count:
        label = 'slightly bearish'
        signals.append(f'News slightly bearish ({bearish_count}S/{bullish_count}B/{neutral_count}N)')
    else:
        label = 'neutral'
        signals.append('News sentiment neutral')

    # News velocity — many articles = something is happening
    if len(news_articles) >= 15:
        signals.append(f'High news volume ({len(news_articles)} articles) — elevated attention')
    elif len(news_articles) >= 8:
        signals.append(f'Moderate news volume ({len(news_articles)} articles)')
    elif len(news_articles) <= 2:
        signals.append('Low news coverage')

    return news_score, signals, label


def score_reddit_sentiment(reddit_scraper, symbol):
    """
    Score sentiment from Reddit data (0-100).
    Uses the RedditScraper class instance.
    Returns (score, signals, buzz_label).
    """
    signals = []
    score = 50

    try:
        # Try to scrape relevant subreddits
        posts = []
        for sub in ['wallstreetbets', 'stocks', 'investing']:
            try:
                sub_posts = reddit_scraper.scrape_subreddit(sub, limit=25, time_filter='week')
                posts.extend(sub_posts)
            except Exception:
                continue

        # Filter posts mentioning this symbol
        symbol_upper = symbol.upper()
        relevant = [p for p in posts if symbol_upper in p.get('tickers', [])]

        if not relevant:
            return 50, ['No Reddit mentions found'], 'none'

        # Score based on mention volume
        mention_count = len(relevant)
        if mention_count >= 10:
            score += 10
            buzz_label = 'very high'
            signals.append(f'Reddit buzz very high ({mention_count} mentions)')
        elif mention_count >= 5:
            score += 5
            buzz_label = 'high'
            signals.append(f'Reddit buzz high ({mention_count} mentions)')
        elif mention_count >= 2:
            buzz_label = 'moderate'
            signals.append(f'Reddit mentions: {mention_count}')
        else:
            buzz_label = 'low'
            signals.append(f'Low Reddit mentions: {mention_count}')

        # Sentiment from post titles
        post_sentiments = []
        for post in relevant:
            text = f"{post.get('title', '')} {post.get('selftext', '')}"
            s = _score_headline(text)
            post_sentiments.append(s)

        if post_sentiments:
            avg = sum(post_sentiments) / len(post_sentiments)
            score += avg * 20  # +-20 from Reddit sentiment

            # Engagement-weighted (high score posts matter more)
            total_engagement = sum(p.get('score', 0) + p.get('num_comments', 0) for p in relevant)
            if total_engagement > 500:
                signals.append(f'High Reddit engagement ({total_engagement} interactions)')
            if avg > 0.3:
                signals.append('Reddit sentiment strongly positive')
            elif avg > 0.1:
                signals.append('Reddit sentiment positive')
            elif avg < -0.3:
                signals.append('Reddit sentiment strongly negative')
            elif avg < -0.1:
                signals.append('Reddit sentiment negative')

        score = max(0, min(100, round(score)))
        return score, signals, buzz_label

    except Exception as e:
        return 50, [f'Reddit data unavailable: {str(e)[:50]}'], 'unavailable'


def score_finviz_signals(finviz_data, symbol):
    """
    Score based on Finviz screener signals.
    finviz_data: list of dicts from FinvizScraper.get_all_signals()
    Returns (score_adjustment, signals).
    """
    if not finviz_data:
        return 0, []

    symbol_upper = symbol.upper()
    matching = [s for s in finviz_data if s.get('symbol', '').upper() == symbol_upper]

    if not matching:
        return 0, []

    adjustment = 0
    signals = []

    for match in matching:
        category = match.get('category', '').lower()
        if 'upgrade' in category:
            adjustment += 8
            signals.append(f'Finviz: Analyst Upgrade')
        elif 'insider buying' in category:
            adjustment += 10
            signals.append(f'Finviz: Recent Insider Buying')
        elif 'oversold' in category:
            adjustment += 6
            signals.append(f'Finviz: Oversold Bounce signal')
        elif 'unusual volume' in category:
            adjustment += 3
            signals.append(f'Finviz: Unusual Volume detected')
        elif 'new' in category and 'high' in category:
            adjustment += 5
            signals.append(f'Finviz: New 52-Week High')
        elif 'top gainer' in category:
            adjustment += 4
            signals.append(f'Finviz: Top Gainer today')

    return adjustment, signals


def calculate_sentiment_score(news_articles, reddit_scraper=None, symbol='', finviz_data=None):
    """
    Master function: calculates composite sentiment score (0-100).
    Returns dict with score, sub-components, and key_signals.
    """
    # News: 50% weight
    news_score, news_signals, news_label = score_news_sentiment(news_articles)

    # Reddit: 25% weight
    if reddit_scraper:
        reddit_score, reddit_signals, buzz_label = score_reddit_sentiment(reddit_scraper, symbol)
    else:
        reddit_score, reddit_signals, buzz_label = 50, ['Reddit API not configured'], 'unavailable'

    # Finviz: 25% weight (applied as adjustment)
    finviz_adj, finviz_signals = score_finviz_signals(finviz_data, symbol)

    # Composite: news 50%, reddit 25%, finviz adjusts the base
    base_score = news_score * 0.50 + reddit_score * 0.25 + 50 * 0.25
    composite = base_score + finviz_adj
    composite = max(0, min(100, round(composite)))

    all_signals = news_signals + reddit_signals + finviz_signals
    analyst_label = 'N/A'
    for sig in finviz_signals:
        if 'upgrade' in sig.lower():
            analyst_label = 'Upgraded'
        elif 'insider' in sig.lower():
            analyst_label = 'Insider buying'

    return {
        'score': composite,
        'news_sentiment': news_label,
        'reddit_buzz': f'{buzz_label} and {"positive" if reddit_score > 55 else "negative" if reddit_score < 45 else "neutral"}',
        'analyst_consensus': analyst_label,
        'key_signals': all_signals[:8],
    }
