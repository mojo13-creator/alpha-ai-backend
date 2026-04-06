# analysis/composite_scorer.py
"""
Composite Scoring Engine
Combines Technical, Fundamental, Sentiment, and AI Insight sub-scores
with market-cap-aware weighting. Generates actionable signals.
"""

import math
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.technical_scorer import calculate_technical_score
from analysis.fundamental_scorer import calculate_fundamental_score, classify_market_cap
from analysis.sentiment_scorer import calculate_sentiment_score
from analysis.ai_analyzer import AIStockAnalyzer


def safe_float(val, default=0.0):
    try:
        v = float(val)
        return default if math.isnan(v) or math.isinf(v) else v
    except Exception:
        return default


# Weight profiles by market cap category
WEIGHT_PROFILES = {
    'micro': {'technical': 0.35, 'fundamental': 0.15, 'sentiment': 0.25, 'ai_insight': 0.25, 'label': 'micro_active'},
    'small': {'technical': 0.35, 'fundamental': 0.20, 'sentiment': 0.20, 'ai_insight': 0.25, 'label': 'smallcap_active'},
    'midcap': {'technical': 0.35, 'fundamental': 0.20, 'sentiment': 0.20, 'ai_insight': 0.25, 'label': 'midcap_active'},
    'large': {'technical': 0.20, 'fundamental': 0.35, 'sentiment': 0.15, 'ai_insight': 0.30, 'label': 'largecap_hold'},
    'mega': {'technical': 0.20, 'fundamental': 0.35, 'sentiment': 0.15, 'ai_insight': 0.30, 'label': 'megacap_hold'},
    'etf': {'technical': 0.25, 'fundamental': 0.30, 'sentiment': 0.15, 'ai_insight': 0.30, 'label': 'etf_hold'},
    'unknown': {'technical': 0.30, 'fundamental': 0.25, 'sentiment': 0.20, 'ai_insight': 0.25, 'label': 'default'},
}


def determine_signal(composite_score, tech_score, fund_score, sent_score, ai_score):
    """
    Determine actionable signal based on composite + sub-score alignment.
    Returns (signal, confidence, risk_level).
    """
    sub_scores = [tech_score, fund_score, sent_score, ai_score]
    above_75 = sum(1 for s in sub_scores if s >= 75)
    above_60 = sum(1 for s in sub_scores if s >= 60)
    below_25 = sum(1 for s in sub_scores if s <= 25)
    below_40 = sum(1 for s in sub_scores if s <= 40)
    any_below_20 = any(s < 20 for s in sub_scores)

    # Score spread = alignment indicator
    spread = max(sub_scores) - min(sub_scores)

    if composite_score >= 85 and above_75 >= 3:
        signal = 'STRONG_BUY'
    elif composite_score >= 70 and not any(s < 40 for s in sub_scores):
        signal = 'BUY'
    elif composite_score <= 25 and tech_score < 35:
        # Confirm downtrend for SHORT
        signal = 'SHORT'
    elif composite_score < 30 or below_25 >= 2:
        signal = 'STRONG_SELL'
    elif composite_score < 50 or any_below_20:
        signal = 'SELL'
    else:
        signal = 'HOLD'

    # Confidence based on sub-score alignment
    if spread < 15:
        confidence = 'HIGH'
    elif spread < 30:
        confidence = 'MODERATE'
    else:
        confidence = 'LOW'

    # Risk level
    if spread > 40 or any_below_20:
        risk_level = 'HIGH'
    elif spread > 25 or below_40 >= 1:
        risk_level = 'MODERATE'
    else:
        risk_level = 'LOW'

    return signal, confidence, risk_level


def calculate_action(signal, price, atr, df=None):
    """
    Calculate entry price, stop loss, target price, time horizon, risk/reward.
    """
    if price <= 0:
        return {
            'recommendation': signal.replace('_', ' '),
            'entry_price': 0, 'stop_loss': 0, 'target_price': 0,
            'time_horizon': 'N/A', 'risk_reward_ratio': 'N/A',
        }

    atr = safe_float(atr, price * 0.02)  # Default to 2% of price
    if atr <= 0:
        atr = price * 0.02

    if signal in ('STRONG_BUY', 'BUY'):
        entry = round(price, 2)
        stop = round(price - (2.0 * atr), 2)
        # Target: minimum 2:1 risk/reward
        risk = entry - stop
        target = round(entry + (risk * 2.5), 2)

        # Look for resistance levels from recent highs
        if df is not None and not df.empty and len(df) >= 20:
            recent_high = safe_float(df['high'].tail(60).max())
            if recent_high > target and recent_high > price:
                target = round(recent_high, 2)

        risk_per_share = entry - stop
        reward_per_share = target - entry
        rr = round(reward_per_share / risk_per_share, 1) if risk_per_share > 0 else 0

        time_horizon = '2-4 weeks' if signal == 'BUY' else '1-3 months'

    elif signal in ('STRONG_SELL', 'SELL', 'SHORT'):
        entry = round(price, 2)
        stop = round(price + (2.0 * atr), 2)
        risk = stop - entry
        target = round(entry - (risk * 2.0), 2)

        # Look for support levels from recent lows
        if df is not None and not df.empty and len(df) >= 20:
            recent_low = safe_float(df['low'].tail(60).min())
            if recent_low < target and recent_low > 0:
                target = round(recent_low, 2)

        risk_per_share = stop - entry
        reward_per_share = entry - target
        rr = round(reward_per_share / risk_per_share, 1) if risk_per_share > 0 else 0

        time_horizon = '1-2 weeks' if signal == 'SELL' else '2-4 weeks'
    else:
        # HOLD
        entry = round(price, 2)
        stop = round(price - (2.0 * atr), 2)
        target = round(price + (2.0 * atr), 2)
        rr = 1.0
        time_horizon = 'Monitoring'

    return {
        'recommendation': signal.replace('_', ' '),
        'entry_price': entry,
        'stop_loss': stop,
        'target_price': target,
        'time_horizon': time_horizon,
        'risk_reward_ratio': f'{rr}:1',
    }


def run_composite_analysis(symbol, db_manager, technical_analyzer, news_scraper,
                            reddit_scraper=None, finviz_data=None, skip_ai=False,
                            use_berkeley=True):
    """
    Run the full composite analysis pipeline for a symbol.
    Returns the complete analysis result dict matching the API response schema.
    """
    import yfinance as yf
    import asyncio
    from data_collection.stock_data import StockDataCollector

    print(f"\n{'='*60}")
    print(f"  COMPOSITE ANALYSIS: {symbol.upper()}")
    print(f"{'='*60}")

    # 1. Fetch/update price data
    collector = StockDataCollector(db_manager)
    collector.fetch_and_save(symbol, period='1y')

    # 2. Calculate all technical indicators
    print(f"\n📊 Phase 1: Technical Analysis...")
    df = technical_analyzer.calculate_all_indicators(symbol)
    if df is None or df.empty:
        return {'error': f'No data available for {symbol}'}

    latest = df.iloc[-1]

    # Get real-time price
    try:
        ticker_obj = yf.Ticker(symbol)
        fast = ticker_obj.fast_info
        price = float(fast.last_price) if fast.last_price else float(latest['close'])
        prev_close = float(fast.previous_close) if hasattr(fast, 'previous_close') and fast.previous_close else None
    except Exception:
        price = float(latest['close'])
        prev_close = None

    # Get stock info
    try:
        stock_info = collector.get_stock_info(symbol) or {}
    except Exception:
        stock_info = {}

    # 2b. Berkeley enrichment (best-effort, non-blocking)
    berkeley_data = {}
    berkeley_sources_available = []
    berkeley_sources_failed = []
    if use_berkeley:
        print(f"\n🏛️  Phase 0: Berkeley Enrichment...")
        try:
            from data_collection.berkeley.enrichment_manager import BerkeleyEnrichmentManager
            enrichment = BerkeleyEnrichmentManager()

            # Run async enrichment from sync context
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        berkeley_data = pool.submit(
                            asyncio.run, enrichment.enrich(symbol)
                        ).result(timeout=120)
                else:
                    berkeley_data = loop.run_until_complete(enrichment.enrich(symbol))
            except RuntimeError:
                berkeley_data = asyncio.run(enrichment.enrich(symbol))

            berkeley_sources_available = list(berkeley_data.keys())
            all_berkeley = ["capital_iq", "wrds", "ibisworld", "fitch", "orbis", "finaeon", "statista"]
            berkeley_sources_failed = [s for s in all_berkeley if s not in berkeley_sources_available]
            print(f"  Berkeley sources: {berkeley_sources_available or 'none'}")
        except Exception as e:
            print(f"  ⚠️  Berkeley enrichment unavailable: {e}")

    # 3. Technical Score
    tech_result = calculate_technical_score(df)
    print(f"  Technical Score: {tech_result['score']}/100")

    # 4. Fundamental Score (enhanced with Berkeley data if available)
    print(f"\n📊 Phase 2: Fundamental Analysis...")
    fund_result = calculate_fundamental_score(symbol, berkeley_data=berkeley_data or None)
    print(f"  Fundamental Score: {fund_result['score']}/100")
    if fund_result.get('berkeley_enhanced'):
        print(f"  (Berkeley-enhanced from: {fund_result.get('berkeley_sources', [])})")

    # Market cap classification
    market_cap = fund_result.get('market_cap', 0)
    cap_cat = fund_result.get('market_cap_category', 'unknown')
    cap_label = fund_result.get('market_cap_label', 'Unknown')

    # 5. Sentiment Score
    print(f"\n📊 Phase 3: Sentiment Analysis...")
    news_articles = []
    try:
        news_articles = news_scraper.fetch_stock_news(symbol, days=7) or []
    except Exception:
        pass

    sent_result = calculate_sentiment_score(
        news_articles=news_articles,
        reddit_scraper=reddit_scraper,
        symbol=symbol,
        finviz_data=finviz_data,
        berkeley_data=berkeley_data or None,
    )
    print(f"  Sentiment Score: {sent_result['score']}/100")

    # 6. AI Insight Score
    print(f"\n🤖 Phase 4: AI Insight Analysis...")
    if skip_ai:
        ai_result = {
            'score': 50, 'reasoning': 'AI analysis skipped',
            'agreements': [], 'disagreements': [], 'risks': [],
            'action': 'HOLD', 'entry_price': 0, 'stop_loss': 0,
            'target_price': 0, 'time_horizon': '',
        }
        print(f"  AI Insight Score: SKIPPED")
    else:
        ai_analyzer = AIStockAnalyzer(db_manager, technical_analyzer, news_scraper)
        ai_result = ai_analyzer.get_ai_insight_score(
            symbol=symbol,
            price=price,
            stock_info=stock_info,
            technical_result=tech_result,
            fundamental_result=fund_result,
            sentiment_result=sent_result,
            news_headlines=news_articles[:8],
            df=df,
            berkeley_data=berkeley_data or None,
        )
        print(f"  AI Insight Score: {ai_result['score']}/100")

    # 7. Composite Score with market-cap weighting
    weights = WEIGHT_PROFILES.get(cap_cat, WEIGHT_PROFILES['unknown'])

    composite = (
        tech_result['score'] * weights['technical']
        + fund_result['score'] * weights['fundamental']
        + sent_result['score'] * weights['sentiment']
        + ai_result['score'] * weights['ai_insight']
    )
    composite = max(0, min(100, round(composite)))

    # 8. Signal determination
    signal, confidence, risk_level = determine_signal(
        composite, tech_result['score'], fund_result['score'],
        sent_result['score'], ai_result['score']
    )

    # Confidence boost from Berkeley data breadth
    confidence_tiers = ['LOW', 'MODERATE', 'HIGH']
    num_berkeley = len(berkeley_sources_available)
    if num_berkeley >= 5 and confidence in confidence_tiers:
        idx = confidence_tiers.index(confidence)
        confidence = confidence_tiers[min(idx + 2, 2)]
    elif num_berkeley >= 3 and confidence in confidence_tiers:
        idx = confidence_tiers.index(confidence)
        confidence = confidence_tiers[min(idx + 1, 2)]

    # 9. Action calculation (entry, stop, target)
    atr = safe_float(latest.get('ATR', 0))
    # Use AI's action if available and reasonable, otherwise calculate from signal
    if ai_result.get('entry_price', 0) > 0:
        action = {
            'recommendation': ai_result.get('action', signal.replace('_', ' ')),
            'entry_price': ai_result['entry_price'],
            'stop_loss': ai_result['stop_loss'],
            'target_price': ai_result['target_price'],
            'time_horizon': ai_result.get('time_horizon', '2-4 weeks'),
            'risk_reward_ratio': '',
        }
        # Calculate risk/reward
        if action['stop_loss'] > 0 and action['target_price'] > 0:
            if signal in ('SHORT', 'STRONG_SELL', 'SELL'):
                risk = action['stop_loss'] - action['entry_price']
                reward = action['entry_price'] - action['target_price']
            else:
                risk = action['entry_price'] - action['stop_loss']
                reward = action['target_price'] - action['entry_price']
            rr = round(reward / risk, 1) if risk > 0 else 0
            action['risk_reward_ratio'] = f'{rr}:1'
    else:
        action = calculate_action(signal, price, atr, df)

    # 10. Price change
    price_change = round(price - prev_close, 2) if prev_close else 0.0
    price_change_pct = round(((price - prev_close) / prev_close) * 100, 2) if prev_close and prev_close > 0 else 0.0

    # 11. Price history for charting
    price_rows = db_manager.get_stock_prices(symbol, limit=365)
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

    # 12. News for response
    news_list = []
    for article in (news_articles or [])[:5]:
        news_list.append({
            "title": article.get('title', 'No title'),
            "source": article.get('source', 'Unknown'),
            "url": article.get('url', ''),
            "published": article.get('published_at', ''),
        })

    print(f"\n{'='*60}")
    print(f"  RESULT: {symbol.upper()} — Score {composite}/100 — {signal}")
    print(f"{'='*60}\n")

    # 13. Save to analysis_history
    try:
        import json as _json
        db_manager.save_analysis_history(
            ticker=symbol,
            composite_score=composite,
            technical_score=tech_result['score'],
            fundamental_score=fund_result['score'],
            sentiment_score=sent_result['score'],
            ai_insight_score=ai_result['score'],
            signal=signal,
            confidence=confidence,
            risk_level=risk_level,
            entry_price=action.get('entry_price', 0),
            stop_loss=action.get('stop_loss', 0),
            target_price=action.get('target_price', 0),
            weight_profile=weights.get('label', 'default'),
            market_cap_category=cap_label,
            raw_response=_json.dumps({'sub_scores': {
                'technical': tech_result['score'],
                'fundamental': fund_result['score'],
                'sentiment': sent_result['score'],
                'ai_insight': ai_result['score'],
            }}),
        )
    except Exception as e:
        print(f"⚠️  Could not save analysis history: {e}")

    # Build final response
    return {
        'ticker': symbol.upper(),
        'symbol': symbol.upper(),  # backward compat
        'company_name': stock_info.get('name', symbol.upper()),
        'timestamp': datetime.now().isoformat(),
        'price': price,
        'prev_close': prev_close,
        'price_change': price_change,
        'price_change_pct': price_change_pct,
        'composite_score': composite,
        'score': composite,  # backward compat
        'signal': signal,
        'confidence': confidence,
        'risk_level': risk_level,
        'recommendation': action['recommendation'],
        'sub_scores': {
            'technical': {
                'score': tech_result['score'],
                'trend': tech_result.get('trend', 50),
                'momentum': tech_result.get('momentum', 50),
                'volume': tech_result.get('volume', 50),
                'volatility': tech_result.get('volatility', 50),
                'key_signals': tech_result.get('key_signals', []),
            },
            'fundamental': {
                'score': fund_result['score'],
                'pe_vs_sector': fund_result.get('pe_vs_sector', 'N/A'),
                'revenue_growth': fund_result.get('revenue_growth', 'N/A'),
                'earnings_surprise': fund_result.get('earnings_surprise', 'N/A'),
                'key_signals': fund_result.get('key_signals', []),
            },
            'sentiment': {
                'score': sent_result['score'],
                'news_sentiment': sent_result.get('news_sentiment', 'N/A'),
                'reddit_buzz': sent_result.get('reddit_buzz', 'N/A'),
                'analyst_consensus': sent_result.get('analyst_consensus', 'N/A'),
                'key_signals': sent_result.get('key_signals', []),
            },
            'ai_insight': {
                'score': ai_result['score'],
                'reasoning': ai_result.get('reasoning', ''),
                'agreements': ai_result.get('agreements', []),
                'disagreements': ai_result.get('disagreements', []),
                'risks': ai_result.get('risks', []),
            },
        },
        'action': action,
        'weight_profile': weights.get('label', 'default'),
        'market_cap_category': cap_label,
        'technical_data': {
            'rsi': safe_float(latest.get('RSI', 50), 50),
            'macd': safe_float(latest.get('MACD', 0)),
            'macd_signal': safe_float(latest.get('MACD_Signal', 0)),
            'sma_20': safe_float(latest.get('SMA_20', price), price),
            'sma_50': safe_float(latest.get('SMA_50', price), price),
            'sma_200': safe_float(latest.get('SMA_200', price), price),
            'volume': int(latest.get('volume', 0)),
            'bb_upper': safe_float(latest.get('BB_Upper', price), price),
            'bb_lower': safe_float(latest.get('BB_Lower', price), price),
            'atr': safe_float(latest.get('ATR', 0)),
        },
        'news': news_list,
        'price_history': price_history,
        'reasoning': ai_result.get('reasoning', f'Composite score: {composite}/100. Signal: {signal}.'),
        'data_quality': {
            'sources_available': (
                ['yfinance', 'newsapi']
                + (['reddit'] if reddit_scraper else [])
                + (['finviz'] if finviz_data else [])
                + berkeley_sources_available
            ),
            'sources_failed': berkeley_sources_failed,
            'berkeley_enhanced': bool(berkeley_sources_available),
            'berkeley_source_count': num_berkeley,
            'confidence_boost': num_berkeley >= 3,
        },
    }
