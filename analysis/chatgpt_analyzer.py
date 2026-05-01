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
                                   df=None, berkeley_data=None, user_period=None,
                                   sec_data=None):
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
                berkeley_data, sec_data
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
                      sentiment, news_headlines, df, berkeley_data=None,
                      sec_data=None):
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
  Volume: {int(safe_float(latest.get('volume', 0))):,}
  Z-Score (50d): {safe_float(latest.get('ZScore', 0)):.2f}
  LinReg Slope: {safe_float(latest.get('LinReg_Slope', 0)):.4f} (R²: {safe_float(latest.get('LinReg_R2', 0)):.2f})
  Hurst Exponent: {safe_float(latest.get('Hurst', 0)):.2f}
  VWAP (20d): ${safe_float(latest.get('VWAP_20', 0)):.2f}
  RS vs SPY (20d/50d): {safe_float(latest.get('RS_SPY_20', 0)):+.1f}pp / {safe_float(latest.get('RS_SPY_50', 0)):+.1f}pp
  Ichimoku: Tenkan ${safe_float(latest.get('Ichi_Tenkan', 0)):.2f}, Kijun ${safe_float(latest.get('Ichi_Kijun', 0)):.2f}, Cloud ${safe_float(latest.get('Ichi_SenkouA', 0)):.2f}-${safe_float(latest.get('Ichi_SenkouB', 0)):.2f}
  Chaikin Money Flow: {safe_float(latest.get('CMF', 0)):.3f}
  Fibonacci: 38.2%=${safe_float(latest.get('Fib_382', 0)):.2f}, 50%=${safe_float(latest.get('Fib_500', 0)):.2f}, 61.8%=${safe_float(latest.get('Fib_618', 0)):.2f}"""

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

        # SEC EDGAR data block
        sec_block = self._build_sec_edgar_block(sec_data)

        prompt = f"""You are a decisive stock analyst. You DO NOT hedge. You DO NOT cluster scores in the safe middle range.

ROLE — SYNTHESIZER (1 of 3 models in consensus):
You are the synthesizer lens. Two other models are running the bull case (aggressive bull-thesis search) and bear case (aggressive bear-thesis search) on this stock independently. You are the PM weighing both views.

Your job: independently identify the SINGLE strongest bullish factor and the SINGLE strongest bearish factor in the data. Don't list five of each — pick the most decisive one for each side. Then judge which side has more evidence weight in the data, given the user's investment horizon. Score based on which side wins.

You should NOT default to the average. If one side has overwhelming evidence and the other has thin theoretical concerns, score in the direction of the strong side. If both sides have real evidence, that genuinely is a moderate score — but say specifically what each side is.

The user is paying for actionable judgment, not a both-sides hedge.

ANALYZE: {symbol} at ${price:.2f}
{info_block}
{tech_details}

PRE-COMPUTED SUB-SCORES (from our quantitative models):
  Technical Score: {technical.get('score', 'N/A')}/100 (Trend: {technical.get('trend', 'N/A')}, Momentum: {technical.get('momentum', 'N/A')}, Volume: {technical.get('volume', 'N/A')}, Volatility: {technical.get('volatility', 'N/A')}, Statistical: {technical.get('statistical', 'N/A')}, Institutional: {technical.get('institutional', 'N/A')}, Win Rate: {technical.get('winrate', 'N/A')})
  Technical Signals: {', '.join(technical.get('key_signals', [])[:8])}

  Fundamental Score: {fundamental.get('score', 'N/A')}/100
  P/E: {fundamental.get('pe_vs_sector', 'N/A')} | Revenue Growth: {fundamental.get('revenue_growth', 'N/A')} | Earnings: {fundamental.get('earnings_surprise', 'N/A')}
  Fundamental Signals: {', '.join(fundamental.get('key_signals', [])[:5])}

  Sentiment Score: {sentiment.get('score', 'N/A')}/100
  News: {sentiment.get('news_sentiment', 'N/A')} | Reddit: {sentiment.get('reddit_buzz', 'N/A')}
  Sentiment Signals: {', '.join(sentiment.get('key_signals', [])[:5])}

{news_block}

{berkeley_block}

{sec_block}

YOUR TASK:
1. Review ALL the data above
2. Identify patterns the quantitative models might miss (sector rotation, macro correlation, earnings setup, competitive dynamics)
3. Identify risks the math might miss (regulatory, competitive, management red flags)
4. Give your OWN conviction score (0-100) with mandatory reasoning
5. Flag any disagreement with the sub-scores and explain why

SCORING RULES — MANDATORY, READ CAREFULLY:

BANNED ZONE: Scores 45-55 are FORBIDDEN. You must NEVER return a score between 45 and 55. That range is a cop-out — every stock has a lean. Find it. If you're tempted to score 50, ask yourself: "Would I put my own money in this stock right now?" If yes, score 65+. If no, score 35 or below.

Score distribution you MUST follow:
- 85-100 (STRONG BUY): Multiple strong bullish signals aligned. Technicals, fundamentals, AND sentiment all point up. You'd confidently enter this trade.
- 65-84 (BUY): More bullish than bearish. Good setup with manageable risk. Specify what concerns remain.
- 56-64 (LEAN BULLISH): Slightly favorable but not enough to commit. Say what's missing for a full buy.
- 36-44 (LEAN BEARISH): More red flags than green. Say what's wrong specifically.
- 15-35 (SELL): Significant problems — bad technicals, deteriorating fundamentals, or negative sentiment. Be specific.
- 0-14 (STRONG SELL): Broken stock, value trap, or serious trouble. Say so directly.

CALIBRATION EXAMPLES — use these as anchors:
- Score 85+: Stock has RSI recovering from oversold, MACD bullish crossover, price above all major SMAs, strong earnings beat, positive news flow, AND strong relative strength vs SPY. Almost everything aligns.
- Score 70: Solid uptrend, good fundamentals, but one concern (e.g., overbought stochastic or elevated P/E). Still a buy.
- Score 40: Stock has a mix but leans negative — maybe downtrend, earnings miss, or bearish sentiment. Not a hold — it's a cautious sell.
- Score 25: Clear downtrend, multiple bearish indicators, fundamental problems. Get out.

CRITICAL: Your score must be ACTIONABLE. A paid user is relying on this to make real trading decisions. "HOLD at 52" helps nobody. Take a position. Be wrong sometimes — that's fine. Being vague is worse than being wrong.

You MUST justify your score with specific data points from the indicators above, not vague statements like "mixed signals" or "some concerns."

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

    def _build_sec_edgar_block(self, sec_data):
        """Build the SEC EDGAR data section for the prompt."""
        if not sec_data:
            return ""

        lines = ["SEC EDGAR DATA (public filings — high-reliability source):"]

        insider = sec_data.get("insider_summary", {})
        if insider and insider.get("total_form4_filings", 0) > 0:
            lines.append(f"  Insider transactions (Form 4): {insider['total_form4_filings']} filings in last {insider.get('period_days', 90)} days")

        rev_yoy = sec_data.get("revenue_yoy_growth")
        if rev_yoy is not None:
            lines.append(f"  SEC filing revenue growth: {rev_yoy:+.1f}% YoY")

        ni_yoy = sec_data.get("net_income_yoy_growth")
        if ni_yoy == "turnaround":
            lines.append("  Net income: turned positive (turnaround)")
        elif ni_yoy == "negative":
            lines.append("  Net income: currently negative")
        elif isinstance(ni_yoy, (int, float)):
            lines.append(f"  Net income growth: {ni_yoy:+.1f}% YoY")

        facts = sec_data.get("company_facts", {})
        if facts:
            rev = facts.get("Revenue_annual", {})
            if rev.get("value"):
                val = rev["value"]
                label = f"${val/1e9:.1f}B" if val > 1e9 else f"${val/1e6:.0f}M"
                lines.append(f"  Annual revenue (10-K): {label}")
            cash = facts.get("CashAndEquivalents_annual", {})
            if cash.get("value"):
                val = cash["value"]
                label = f"${val/1e9:.1f}B" if val > 1e9 else f"${val/1e6:.0f}M"
                lines.append(f"  Cash & equivalents: {label}")

        filings = sec_data.get("recent_filings", [])
        important = [f for f in filings if f["form"] in ("10-K", "10-Q", "8-K")][:3]
        if important:
            lines.append("  Recent filings:")
            for f in important:
                lines.append(f"    {f['date']} — {f['form']}: {f.get('description', f['form'])}")

        if len(lines) <= 1:
            return ""

        return "\n".join(lines)

    def _parse_response(self, response_text):
        """Parse ChatGPT's JSON response."""
        try:
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                data = json.loads(json_match.group())
                raw_score = max(0, min(100, int(data.get('score', 50))))
                signal = str(data.get('signal', 'HOLD')).upper()

                # Enforce banned 45-55 dead zone
                if 45 <= raw_score <= 55:
                    if signal in ('STRONG BUY', 'BUY', 'STRONG_BUY'):
                        raw_score = 65
                    elif signal in ('SELL', 'STRONG SELL', 'SHORT', 'STRONG_SELL'):
                        raw_score = 35
                    elif raw_score >= 50:
                        raw_score = 58
                    else:
                        raw_score = 42

                return {
                    'score': raw_score,
                    'signal': signal,
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
