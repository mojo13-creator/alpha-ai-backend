# analysis/ai_analyzer.py
"""
AI Insight Score Engine
Feeds Claude the full sub-score breakdown + raw data.
Claude identifies patterns the math misses, flags risks, and gives its own conviction score.
"""

import json
import math
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def safe_float(val, default=0.0):
    try:
        v = float(val)
        return default if math.isnan(v) or math.isinf(v) else v
    except Exception:
        return default


class AIStockAnalyzer:
    """AI-powered stock analyzer using Claude — provides the AI Insight sub-score."""

    def __init__(self, db_manager=None, technical_analyzer=None, news_scraper=None):
        self.db = db_manager
        self.technical = technical_analyzer
        self.news = news_scraper
        print("🤖 AI Stock Analyzer initialized")

    def get_ai_insight_score(self, symbol, price, stock_info, technical_result,
                              fundamental_result, sentiment_result, news_headlines,
                              df=None):
        """
        Call Claude API for the AI Insight sub-score.
        Receives all other sub-scores + raw data. Returns dict with score,
        reasoning, agreements, disagreements, risks.
        """
        try:
            import config
            import anthropic

            if not hasattr(config, 'CLAUDE_API_KEY') or not config.CLAUDE_API_KEY:
                print("⚠️  No Claude API key configured")
                return self._fallback_result("No Claude API key")

            client = anthropic.Anthropic(api_key=config.CLAUDE_API_KEY)

            # Build the data package for Claude
            prompt = self._build_prompt(
                symbol, price, stock_info, technical_result,
                fundamental_result, sentiment_result, news_headlines, df
            )

            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text
            return self._parse_response(response_text)

        except Exception as e:
            print(f"⚠️  AI Insight error: {e}")
            return self._fallback_result(str(e))

    def _build_prompt(self, symbol, price, stock_info, technical, fundamental,
                      sentiment, news_headlines, df):
        """Build the decisive analyst prompt with all data."""

        # Gather technical details from the dataframe
        tech_details = ""
        if df is not None and not df.empty and len(df) >= 2:
            latest = df.iloc[-1]
            tech_details = f"""
RAW TECHNICAL DATA:
  Price: ${price:.2f}
  RSI: {safe_float(latest.get('RSI', 0)):.1f}
  MACD: {safe_float(latest.get('MACD', 0)):.3f} (Signal: {safe_float(latest.get('MACD_Signal', 0)):.3f}, Histogram: {safe_float(latest.get('MACD_Histogram', 0)):.3f})
  SMA 20/50/100/200: ${safe_float(latest.get('SMA_20', 0)):.2f} / ${safe_float(latest.get('SMA_50', 0)):.2f} / ${safe_float(latest.get('SMA_100', 0)):.2f} / ${safe_float(latest.get('SMA_200', 0)):.2f}
  EMA 9/21: ${safe_float(latest.get('EMA_9', 0)):.2f} / ${safe_float(latest.get('EMA_21', 0)):.2f}
  Bollinger Bands: ${safe_float(latest.get('BB_Lower', 0)):.2f} / ${safe_float(latest.get('BB_Middle', 0)):.2f} / ${safe_float(latest.get('BB_Upper', 0)):.2f}
  ATR: ${safe_float(latest.get('ATR', 0)):.2f}
  Stochastic %K/%D: {safe_float(latest.get('STOCH', 0)):.1f} / {safe_float(latest.get('STOCH_Signal', 0)):.1f}
  ADX: {safe_float(latest.get('ADX', 0)):.1f}
  Volume: {int(safe_float(latest.get('volume', 0))):,}"""

            # Price change context
            if len(df) >= 5:
                chg_5d = ((price - safe_float(df.iloc[-5]['close'])) / safe_float(df.iloc[-5]['close'])) * 100
                tech_details += f"\n  5-day price change: {chg_5d:+.1f}%"
            if len(df) >= 20:
                chg_20d = ((price - safe_float(df.iloc[-20]['close'])) / safe_float(df.iloc[-20]['close'])) * 100
                tech_details += f"\n  20-day price change: {chg_20d:+.1f}%"

        # Stock info context
        info_block = ""
        if stock_info:
            info_block = f"""
COMPANY INFO:
  Name: {stock_info.get('name', symbol)}
  Sector: {stock_info.get('sector', 'N/A')}
  Industry: {stock_info.get('industry', 'N/A')}
  Market Cap: ${stock_info.get('market_cap', 0):,.0f}
  Beta: {safe_float(stock_info.get('beta', 0)):.2f}
  52W High/Low: ${safe_float(stock_info.get('52_week_high', 0)):.2f} / ${safe_float(stock_info.get('52_week_low', 0)):.2f}"""

        # News block
        news_block = "RECENT NEWS:\n"
        if news_headlines:
            for h in news_headlines[:8]:
                title = h.get('title', '') if isinstance(h, dict) else str(h)
                news_block += f"  - {title}\n"
        else:
            news_block += "  No recent news available\n"

        prompt = f"""You are a decisive stock analyst. You DO NOT hedge. You DO NOT cluster scores in the safe middle range.

ANALYZE: {symbol} at ${price:.2f}
{info_block}
{tech_details}

PRE-COMPUTED SUB-SCORES (from our quantitative models):
  Technical Score: {technical.get('score', 'N/A')}/100 (Trend: {technical.get('trend', 'N/A')}, Momentum: {technical.get('momentum', 'N/A')}, Volume: {technical.get('volume', 'N/A')}, Volatility: {technical.get('volatility', 'N/A')})
  Technical Signals: {', '.join(technical.get('key_signals', [])[:5])}

  Fundamental Score: {fundamental.get('score', 'N/A')}/100
  P/E: {fundamental.get('pe_vs_sector', 'N/A')} | Revenue Growth: {fundamental.get('revenue_growth', 'N/A')} | Earnings: {fundamental.get('earnings_surprise', 'N/A')}
  Fundamental Signals: {', '.join(fundamental.get('key_signals', [])[:5])}

  Sentiment Score: {sentiment.get('score', 'N/A')}/100
  News: {sentiment.get('news_sentiment', 'N/A')} | Reddit: {sentiment.get('reddit_buzz', 'N/A')}
  Sentiment Signals: {', '.join(sentiment.get('key_signals', [])[:5])}

{news_block}

YOUR TASK:
1. Review ALL the data above
2. Identify patterns the quantitative models might miss (sector rotation, macro correlation, earnings setup, competitive dynamics)
3. Identify risks the math might miss (regulatory, competitive, management red flags)
4. Give your OWN conviction score (0-100) with mandatory reasoning
5. Flag any disagreement with the sub-scores and explain why

SCORING RULES YOU MUST FOLLOW:
- Scores above 80: Stock has multiple strong bullish signals aligned across technicals, fundamentals, and sentiment. You are confident this is a good entry.
- Scores 60-79: Stock has more bullish than bearish signals but some concerns exist. Specify what would push it higher or lower.
- Scores 40-59: Stock is genuinely mixed or unclear. You should rarely land here — dig deeper and take a stance.
- Scores 20-39: Stock has significant red flags. Be specific about what's wrong.
- Scores below 20: Stock is in serious trouble or is a clear trap. Say so directly.

You MUST justify your score with specific data points, not vague statements.
If you are uncertain, your score should reflect that uncertainty by being LOWER, not by being in the middle.

Respond ONLY with valid JSON in this exact format:
{{
    "score": <integer 0-100>,
    "reasoning": "<2-4 sentences explaining your score with specific data points>",
    "agreements": ["<list of things you agree with from the sub-scores>"],
    "disagreements": ["<list of things you disagree with and why>"],
    "risks": ["<specific risks not captured by the quantitative models>"],
    "action": "<STRONG BUY|BUY|HOLD|SELL|STRONG SELL|SHORT>",
    "entry_price": <float>,
    "stop_loss": <float>,
    "target_price": <float>,
    "time_horizon": "<e.g. 1-2 weeks, 2-4 weeks, 1-3 months>"
}}"""

        return prompt

    def _parse_response(self, response_text):
        """Parse Claude's JSON response."""
        try:
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                data = json.loads(json_match.group())
                return {
                    'score': max(0, min(100, int(data.get('score', 50)))),
                    'reasoning': str(data.get('reasoning', '')),
                    'agreements': data.get('agreements', []),
                    'disagreements': data.get('disagreements', []),
                    'risks': data.get('risks', []),
                    'action': str(data.get('action', 'HOLD')),
                    'entry_price': safe_float(data.get('entry_price', 0)),
                    'stop_loss': safe_float(data.get('stop_loss', 0)),
                    'target_price': safe_float(data.get('target_price', 0)),
                    'time_horizon': str(data.get('time_horizon', '')),
                }
        except (json.JSONDecodeError, Exception) as e:
            print(f"⚠️  Failed to parse AI response: {e}")

        return self._fallback_result("Could not parse AI response")

    def _fallback_result(self, reason):
        """Return a neutral fallback when AI is unavailable."""
        return {
            'score': 50,
            'reasoning': f'AI analysis unavailable: {reason}',
            'agreements': [],
            'disagreements': [],
            'risks': ['AI analysis not available — rely on quantitative scores'],
            'action': 'HOLD',
            'entry_price': 0,
            'stop_loss': 0,
            'target_price': 0,
            'time_horizon': '',
        }

    # Legacy method — kept for backward compatibility with hybrid_recommender
    def analyze_stock_with_ai(self, symbol):
        """Legacy wrapper — returns basic result dict."""
        try:
            df = self.technical.calculate_all_indicators(symbol)
            if df is None or df.empty:
                return None

            latest = df.iloc[-1]
            price = float(latest['close'])

            result = self.get_ai_insight_score(
                symbol=symbol,
                price=price,
                stock_info={},
                technical_result={'score': 50, 'trend': 50, 'momentum': 50, 'volume': 50, 'volatility': 50, 'key_signals': []},
                fundamental_result={'score': 50, 'key_signals': [], 'pe_vs_sector': 'N/A', 'revenue_growth': 'N/A', 'earnings_surprise': 'N/A'},
                sentiment_result={'score': 50, 'key_signals': [], 'news_sentiment': 'N/A', 'reddit_buzz': 'N/A'},
                news_headlines=[],
                df=df,
            )

            return {
                'symbol': symbol,
                'recommendation': result['action'],
                'score': result['score'],
                'price': price,
                'reasoning': result['reasoning'],
                'timestamp': datetime.now(),
            }
        except Exception as e:
            print(f"⚠️  Legacy AI analysis error: {e}")
            return None
