# analysis/sentiment_scorer.py
"""
Programmatic Sentiment Score Calculator (0-100)
Sources: NewsAPI headlines, Reddit mentions, Finviz analyst consensus.

Headline classification uses Claude Haiku in a single batched call per analysis
(~$0.0007/call). Falls back to keyword bag if the API is unavailable. The
keyword approach scored "Apple beats antitrust probe" as bullish — we replaced
it because that's a structural error, not a tuning issue.
"""

import json
import math
import os
import re
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
    """Keyword-bag fallback. Returns -1 to +1. Use _classify_headlines_ai when possible."""
    if not text:
        return 0
    text_lower = text.lower()
    bull = sum(1 for w in BULLISH_WORDS if w in text_lower)
    bear = sum(1 for w in BEARISH_WORDS if w in text_lower)
    total = bull + bear
    if total == 0:
        return 0
    return (bull - bear) / total


def _classify_headlines_ai(headlines, symbol):
    """
    Batch-classify headlines via Claude Haiku. Returns list of floats in [-1, 1]
    aligned to the input order, or None on any failure (caller falls back to
    keyword bag). One API call per analysis.

    Each headline is scored for sentiment AS IT RELATES TO THE TICKER. So
    "AMZN beats antitrust probe" is bullish for AMZN, "AMZN sued by FTC" is
    bearish. The keyword bag couldn't tell those apart.
    """
    if not headlines:
        return []

    try:
        import config
        import anthropic
    except Exception:
        return None

    api_key = getattr(config, 'CLAUDE_API_KEY', None) or os.environ.get('CLAUDE_API_KEY')
    if not api_key:
        return None

    # Build a numbered list — Haiku returns a parallel array
    numbered = "\n".join(f"{i+1}. {h}" for i, h in enumerate(headlines))
    prompt = (
        f"For each headline below, score its sentiment FOR THE TICKER {symbol} "
        f"on a scale from -1.0 (very bearish for {symbol}) to +1.0 (very bullish "
        f"for {symbol}). 0.0 = neutral or unrelated.\n\n"
        f"Critical: judge by impact on {symbol}, not by tone. "
        f"\"{symbol} beats lawsuit\" is BULLISH (legal overhang removed). "
        f"\"{symbol} cuts forecast\" is BEARISH even without negative words. "
        f"Headlines about competitors, the broader market, or macro should be "
        f"scored small (|score| <= 0.3) unless the impact on {symbol} is direct.\n\n"
        f"Headlines:\n{numbered}\n\n"
        f"Respond with ONLY a JSON array of {len(headlines)} numbers in the same "
        f"order, no prose, no markdown. Example: [0.8, -0.4, 0.0, 0.2]"
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        text = message.content[0].text.strip()
        # Strip optional markdown fences
        text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text, flags=re.MULTILINE).strip()
        scores = json.loads(text)
        if not isinstance(scores, list) or len(scores) != len(headlines):
            return None
        # Clamp to [-1, 1] and coerce to float
        return [max(-1.0, min(1.0, float(s))) for s in scores]
    except Exception as e:
        print(f"  ⚠️  Haiku headline classification failed: {e} — falling back to keyword bag")
        return None


def score_news_sentiment(news_articles, symbol=None):
    """
    Score sentiment from news headlines (0-100).
    news_articles: list of dicts with 'title', 'description', 'published_at' keys.
    symbol: ticker — required for AI classification (without it, falls back to keyword bag).
    """
    if not news_articles:
        return 50, [], 'neutral'

    capped = news_articles[:20]
    texts = [f"{a.get('title', '')} {a.get('description', '')}".strip() for a in capped]

    scores = None
    classifier = 'keyword'
    if symbol:
        ai_scores = _classify_headlines_ai(texts, symbol)
        if ai_scores is not None:
            scores = ai_scores
            classifier = 'ai'

    if scores is None:
        scores = [_score_headline(t) for t in texts]

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
    if classifier == 'ai':
        signals.append(f'AI-classified {len(scores)} headlines (avg {avg_sentiment:+.2f})')
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


def _berkeley_sentiment_adjustment(berkeley_data):
    """
    Extract sentiment-relevant signals from Berkeley data.
    Returns (adjustment_points, signals_list). Max +-10 points.
    """
    if not berkeley_data:
        return 0, []

    adj = 0.0
    signals = []

    # Capital IQ analyst consensus shifts as sentiment signals
    capiq = berkeley_data.get("capital_iq", {})
    if capiq:
        consensus = (capiq.get("analyst", {}).get("consensus") or "").lower()
        if "strong buy" in consensus or "overweight" in consensus:
            adj += 4
            signals.append(f"CapIQ institutional consensus: bullish")
        elif "sell" in consensus or "underweight" in consensus:
            adj -= 4
            signals.append(f"CapIQ institutional consensus: bearish")

    # Statista consumer trends
    statista = berkeley_data.get("statista", {})
    if statista:
        trends = statista.get("consumer_trends", [])
        if trends:
            adj += 2
            signals.append(f"Statista: {len(trends)} relevant consumer trend(s)")

    # IBISWorld industry outlook as macro sentiment
    ibisworld = berkeley_data.get("ibisworld", {})
    if ibisworld:
        outlook = (ibisworld.get("outlook") or "").lower()
        if any(w in outlook for w in ["growing", "positive", "strong"]):
            adj += 3
            signals.append("IBISWorld: positive industry outlook")
        elif any(w in outlook for w in ["declining", "negative", "weak"]):
            adj -= 3
            signals.append("IBISWorld: negative industry outlook")

    # Fitch macro risk context
    fitch = berkeley_data.get("fitch", {})
    if fitch:
        risks = fitch.get("macro_risk_factors", [])
        if len(risks) >= 3:
            adj -= 2
            signals.append(f"Fitch: {len(risks)} macro risk factors flagged")

    return max(-10, min(10, round(adj))), signals


def calculate_sentiment_score(news_articles, reddit_scraper=None, symbol='',
                               finviz_data=None, berkeley_data=None):
    """
    Master function: calculates composite sentiment score (0-100).
    Returns dict with score, sub-components, and key_signals.
    """
    # News: 50% weight
    news_score, news_signals, news_label = score_news_sentiment(news_articles, symbol=symbol)

    # Reddit: 25% weight
    if reddit_scraper:
        reddit_score, reddit_signals, buzz_label = score_reddit_sentiment(reddit_scraper, symbol)
    else:
        reddit_score, reddit_signals, buzz_label = 50, ['Reddit API not configured'], 'unavailable'

    # Finviz: 25% weight (applied as adjustment)
    finviz_adj, finviz_signals = score_finviz_signals(finviz_data, symbol)

    # Berkeley institutional sentiment (supplementary adjustment)
    berkeley_adj, berkeley_signals = _berkeley_sentiment_adjustment(berkeley_data)

    # Composite: news 50%, reddit 25%, finviz + berkeley adjust the base
    base_score = news_score * 0.50 + reddit_score * 0.25 + 50 * 0.25
    composite = base_score + finviz_adj + berkeley_adj
    composite = max(0, min(100, round(composite)))

    all_signals = news_signals + reddit_signals + finviz_signals + berkeley_signals
    analyst_label = 'N/A'
    for sig in finviz_signals:
        if 'upgrade' in sig.lower():
            analyst_label = 'Upgraded'
        elif 'insider' in sig.lower():
            analyst_label = 'Insider buying'
    # Berkeley can also provide analyst label
    if analyst_label == 'N/A' and berkeley_signals:
        for sig in berkeley_signals:
            if 'bullish' in sig.lower():
                analyst_label = 'Institutional bullish'
            elif 'bearish' in sig.lower():
                analyst_label = 'Institutional bearish'

    return {
        'score': composite,
        'news_sentiment': news_label,
        'reddit_buzz': f'{buzz_label} and {"positive" if reddit_score > 55 else "negative" if reddit_score < 45 else "neutral"}',
        'analyst_consensus': analyst_label,
        'key_signals': all_signals[:10],
    }
