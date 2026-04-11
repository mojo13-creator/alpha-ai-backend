# analysis/chatgpt_analyzer.py
"""
ChatGPT AI Insight Engine
Provides a third independent AI opinion for the composite scorer.
Uses the same data package and conviction-scoring prompt as Claude and Gemini.
"""

import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def safe_float(val, default=0.0):
    try:
        v = float(val)
        return default if math.isnan(v) or math.isinf(v) else v
    except Exception:
        return default


class ChatGPTAnalyzer:
    """ChatGPT-powered stock analyzer — provides an independent AI Insight score."""

    MODEL = "gpt-4o"

    def __init__(self):
        self.client = None
        self._init_client()

    def _init_client(self):
        """Initialize the OpenAI client. Fails silently if key not set."""
        try:
            api_key = os.environ.get("OPENAI_API_KEY", "")
            if not api_key:
                print("  No OpenAI API key configured — ChatGPT analysis disabled")
                return
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key)
            print("  ChatGPT Analyzer initialized")
        except Exception as e:
            print(f"  ChatGPT init failed: {e}")

    def get_chatgpt_insight_score(self, symbol, price, stock_info, technical_result,
                                   fundamental_result, sentiment_result, news_headlines,
                                   df=None, berkeley_data=None, user_period=None):
        """
        Call OpenAI API for an independent AI Insight score.
        Returns dict matching the same schema as Claude/Gemini AI Insight result.
        Returns None if ChatGPT is unavailable.
        """
        if self.client is None:
            return None

        try:
            prompt = self._build_prompt(
                symbol, price, stock_info, technical_result,
                fundamental_result, sentiment_result, news_headlines, df,
                berkeley_data
            )

            response = self.client.chat.completions.create(
                model=self.MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )

            return self._parse_response(response.choices[0].message.content)

        except Exception as e:
            print(f"  ChatGPT Insight error: {e}")
            return None

    def _build_prompt(self, symbol, price, stock_info, technical, fundamental,
                      sentiment, news_headlines, df, berkeley_data=None):
        """Build the decisive analyst prompt with all data — mirrors Claude/Gemini prompt."""

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

        # Berkeley data block
        berkeley_block = self._build_berkeley_block(berkeley_data)

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

{berkeley_block}

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
    "signal": "<STRONG_BUY|BUY|HOLD|SELL|STRONG_SELL|SHORT>",
    "reasoning": "<2-4 sentences explaining your score with specific data points>",
    "agreements": ["<list of things you agree with from the sub-scores>"],
    "disagreements": ["<list of things you disagree with and why>"],
    "risks": ["<specific risks not captured by the quantitative models>"],
    "entry_price": <float>,
    "stop_loss": <float>,
    "target_price": <float>,
    "time_horizon": "<e.g. 1-2 weeks, 2-4 weeks, 1-3 months>"
}}"""

        return prompt

    def _build_berkeley_block(self, berkeley_data):
        """Build the institutional data section for the prompt."""
        if not berkeley_data:
            return ""

        lines = ["INSTITUTIONAL DATA (from Capital IQ / Orbis / Statista — treat as high-quality signals):"]

        capiq = berkeley_data.get("capital_iq", {})
        if capiq:
            analyst = capiq.get("analyst", {})
            if analyst.get("consensus"):
                lines.append(f"  Analyst consensus: {analyst['consensus']}")
            pt_mean = analyst.get("price_target_mean")
            if pt_mean:
                lines.append(f"  Price target range: ${analyst.get('price_target_low', '?')} - ${pt_mean} - ${analyst.get('price_target_high', '?')}")
            own = capiq.get("ownership", {})
            if own.get("institutional_pct"):
                lines.append(f"  Institutional ownership: {own['institutional_pct']*100:.0f}%")

        orbis = berkeley_data.get("orbis", {})
        if orbis:
            comps = orbis.get("comparables", [])
            if comps:
                comp_names = [c.get("name", "") for c in comps[:5] if c.get("name")]
                if comp_names:
                    lines.append(f"  Comparable companies: {', '.join(comp_names)}")

        statista = berkeley_data.get("statista", {})
        if statista:
            if statista.get("market_size"):
                lines.append(f"  Market size / TAM: {statista['market_size']}")

        if len(lines) <= 1:
            return ""

        return "\n".join(lines)

    def _parse_response(self, response_text):
        """Parse ChatGPT's JSON response."""
        try:
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                data = json.loads(json_match.group())
                return {
                    'score': max(0, min(100, int(data.get('score', 50)))),
                    'signal': str(data.get('signal', 'HOLD')),
                    'reasoning': str(data.get('reasoning', '')),
                    'agreements': data.get('agreements', []),
                    'disagreements': data.get('disagreements', []),
                    'risks': data.get('risks', []),
                    'entry_price': safe_float(data.get('entry_price', 0)),
                    'stop_loss': safe_float(data.get('stop_loss', 0)),
                    'target_price': safe_float(data.get('target_price', 0)),
                    'time_horizon': str(data.get('time_horizon', '')),
                }
        except (json.JSONDecodeError, Exception) as e:
            print(f"  Failed to parse ChatGPT response: {e}")

        return None
