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
                              df=None, berkeley_data=None, user_period=None,
                              sec_data=None):
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
                fundamental_result, sentiment_result, news_headlines, df,
                berkeley_data, user_period, sec_data
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
                      sentiment, news_headlines, df, berkeley_data=None,
                      user_period=None, sec_data=None):
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
  Volume: {int(safe_float(latest.get('volume', 0))):,}
  Z-Score (50d): {safe_float(latest.get('ZScore', 0)):.2f}
  LinReg Slope: {safe_float(latest.get('LinReg_Slope', 0)):.4f} (R²: {safe_float(latest.get('LinReg_R2', 0)):.2f})
  Hurst Exponent: {safe_float(latest.get('Hurst', 0)):.2f}
  VWAP (20d): ${safe_float(latest.get('VWAP_20', 0)):.2f}
  RS vs SPY (20d/50d): {safe_float(latest.get('RS_SPY_20', 0)):+.1f}pp / {safe_float(latest.get('RS_SPY_50', 0)):+.1f}pp
  Ichimoku: Tenkan ${safe_float(latest.get('Ichi_Tenkan', 0)):.2f}, Kijun ${safe_float(latest.get('Ichi_Kijun', 0)):.2f}, Cloud ${safe_float(latest.get('Ichi_SenkouA', 0)):.2f}-${safe_float(latest.get('Ichi_SenkouB', 0)):.2f}
  Chaikin Money Flow: {safe_float(latest.get('CMF', 0)):.3f}
  Fibonacci: 38.2%=${safe_float(latest.get('Fib_382', 0)):.2f}, 50%=${safe_float(latest.get('Fib_500', 0)):.2f}, 61.8%=${safe_float(latest.get('Fib_618', 0)):.2f}"""

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

        # Map period codes to readable investment horizons
        period_map = {
            '1mo': '1 month', '3mo': '3 months', '6mo': '6 months',
            '1y': '1 year', '2y': '2 years',
        }
        horizon_label = period_map.get(user_period, '6 months') if user_period else '6 months'

        prompt = f"""You are a decisive stock analyst. You DO NOT hedge. You DO NOT cluster scores in the safe middle range.

ROLE — BULL CASE ANALYST (1 of 3 models in consensus):
You are the bull-case lens. Your job: find the strongest credible reason this stock could outperform over the user's horizon. Force yourself to identify the bull thesis BEFORE looking at the score range. Then stress-test it: do the numbers actually support it? Is there a catalyst? What would have to be true?

If the bull case survives scrutiny → score high (75+).
If the bull case has a fatal flaw → score low even though you tried to find one (your honest score must dominate over your assigned lens). Better to say "I tried to make the bull case and couldn't" than to invent one.

You are NOT being asked to be a cheerleader. You are being asked to be the model that prosecutes the bull thesis aggressively. Two other models (bear, synth) are doing the same from other angles. The user gets the consensus.

ANALYZE: {symbol} at ${price:.2f}
INVESTMENT HORIZON: {horizon_label} — the user is evaluating this stock for a {horizon_label} hold. Your entry_price, stop_loss, target_price, and time_horizon MUST be calibrated to this timeframe. Do NOT suggest a 1-2 week target if the user is looking at 3 months.
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

{self._build_berkeley_block(berkeley_data)}

{self._build_sec_edgar_block(sec_data)}

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

STRATEGY RULES — read carefully:
- For STRONG BUY / BUY: entry_price = ideal buy price (at or slightly below current), target_price = profit target ABOVE entry, stop_loss = exit price BELOW entry to limit losses.
- For SELL / STRONG SELL: entry_price = price to sell/exit at (at or near current), target_price = lower price where re-entry becomes attractive, stop_loss = price ABOVE current that would invalidate the bearish thesis (i.e. "you were wrong if it hits this").
- For HOLD: entry_price = current price, target_price = upside level to watch, stop_loss = downside level that would trigger a sell.
- For SHORT: entry_price = price to short at, target_price = cover target BELOW entry, stop_loss = price ABOVE entry to cut losses.
- target_price must ALWAYS be in the profitable direction for the action. Never set a target that loses money on the trade.
- stop_loss must ALWAYS be in the losing direction for the action. It is the "I was wrong" exit.

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

    def _build_berkeley_block(self, berkeley_data):
        """Build the institutional data section for the prompt."""
        if not berkeley_data:
            return ""

        lines = ["INSTITUTIONAL DATA (Capital IQ, WRDS, IBISWorld, Fitch, Orbis, Finaeon, Statista — treat as high-quality signals):"]

        capiq = berkeley_data.get("capital_iq", {})
        if capiq:
            analyst = capiq.get("analyst", {})
            if analyst.get("consensus"):
                lines.append(f"  Analyst consensus: {analyst['consensus']}")
            pt_low = analyst.get("price_target_low")
            pt_mean = analyst.get("price_target_mean")
            pt_high = analyst.get("price_target_high")
            if pt_mean:
                lines.append(f"  Price target range: ${pt_low or '?'} - ${pt_mean} - ${pt_high or '?'}")

            own = capiq.get("ownership", {})
            if own.get("institutional_pct"):
                lines.append(f"  Institutional ownership: {own['institutional_pct']*100:.0f}%")
            insider = own.get("insider_transactions", [])
            if insider:
                buys = sum(1 for t in insider if "buy" in (t.get("type", "") or "").lower())
                sells = sum(1 for t in insider if "sell" in (t.get("type", "") or "").lower())
                lines.append(f"  Insider activity: {buys} buys, {sells} sells (last 6 months)")

            peers = capiq.get("peers", {})
            if peers.get("sector_avg_pe"):
                lines.append(f"  Sector avg P/E: {peers['sector_avg_pe']}")
            if peers.get("sector_avg_revenue_growth"):
                lines.append(f"  Sector avg revenue growth: {peers['sector_avg_revenue_growth']*100:.1f}%")

            earnings = capiq.get("earnings", {})
            if earnings.get("next_earnings_date"):
                lines.append(f"  Next earnings date: {earnings['next_earnings_date']}")

        orbis = berkeley_data.get("orbis", {})
        if orbis:
            subs = orbis.get("subsidiaries", [])
            if subs:
                lines.append(f"  Corporate structure: {len(subs)} subsidiaries")
            comps = orbis.get("comparables", [])
            if comps:
                comp_names = [c.get("name", "") for c in comps[:5] if c.get("name")]
                if comp_names:
                    lines.append(f"  Comparable companies: {', '.join(comp_names)}")

        statista = berkeley_data.get("statista", {})
        if statista:
            if statista.get("market_size"):
                lines.append(f"  Market size / TAM: {statista['market_size']}")
            if statista.get("market_forecast"):
                lines.append(f"  Market forecast: {statista['market_forecast'][:200]}")

        ibisworld = berkeley_data.get("ibisworld", {})
        if ibisworld:
            if ibisworld.get("outlook"):
                lines.append(f"  Industry outlook: {ibisworld['outlook'][:200]}")
            if ibisworld.get("growth_rate"):
                lines.append(f"  Industry growth rate: {ibisworld['growth_rate']}")

        fitch = berkeley_data.get("fitch", {})
        if fitch:
            if fitch.get("company_rating"):
                lines.append(f"  Fitch rating: {fitch['company_rating']}")
            if fitch.get("sector_credit_outlook"):
                lines.append(f"  Sector credit outlook: {fitch['sector_credit_outlook'][:200]}")

        wrds = berkeley_data.get("wrds", {})
        if wrds:
            compustat_q = wrds.get("compustat_quarterly", [])
            if compustat_q:
                latest_q = compustat_q[0] if compustat_q else {}
                rev = latest_q.get("revtq")
                ni = latest_q.get("niq")
                eps = latest_q.get("epspxq")
                if rev is not None:
                    lines.append(f"  WRDS Compustat quarterly revenue: ${rev:,.0f}M" if rev > 1000 else f"  WRDS Compustat quarterly revenue: ${rev:,.2f}M")
                if ni is not None:
                    lines.append(f"  WRDS Compustat quarterly net income: ${ni:,.2f}M")
                if eps is not None:
                    lines.append(f"  WRDS Compustat quarterly EPS: ${eps:.2f}")
            compustat_a = wrds.get("compustat_annual", [])
            if compustat_a and len(compustat_a) >= 2:
                curr_rev = compustat_a[0].get("revt")
                prev_rev = compustat_a[1].get("revt")
                if curr_rev and prev_rev and prev_rev > 0:
                    yoy_growth = ((curr_rev - prev_rev) / prev_rev) * 100
                    lines.append(f"  WRDS annual revenue growth: {yoy_growth:+.1f}% YoY")
            crsp = wrds.get("crsp_daily_returns", [])
            if crsp and len(crsp) >= 20:
                recent_rets = [r.get("ret", 0) for r in crsp[-20:] if r.get("ret") is not None]
                if recent_rets:
                    avg_ret = sum(recent_rets) / len(recent_rets) * 100
                    lines.append(f"  WRDS CRSP 20-day avg daily return: {avg_ret:+.3f}%")

        finaeon = berkeley_data.get("finaeon", {})
        if finaeon:
            hist_prices = finaeon.get("historical_prices", [])
            if hist_prices:
                lines.append(f"  Finaeon deep history: {len(hist_prices)} data points available")
            sector_idx = finaeon.get("sector_index", {})
            if sector_idx.get("performance"):
                lines.append(f"  Finaeon sector index: {sector_idx['performance'][:200]}")
            commodity = finaeon.get("commodity_prices", [])
            if commodity:
                for c in commodity[:2]:
                    lines.append(f"  Related commodity ({c.get('name', 'N/A')}): {c.get('latest', 'N/A')}")

        if len(lines) <= 1:
            return ""

        lines.append("\nUse this institutional data to validate or challenge your analysis. If your score disagrees with analyst consensus, explain why specifically.")
        return "\n".join(lines)

    def _build_sec_edgar_block(self, sec_data):
        """Build the SEC EDGAR data section for the prompt."""
        if not sec_data:
            return ""

        lines = ["SEC EDGAR DATA (public filings — high-reliability source):"]

        # Insider trading summary
        insider = sec_data.get("insider_summary", {})
        if insider:
            count = insider.get("total_form4_filings", 0)
            if count > 0:
                most_recent = insider.get("most_recent", "N/A")
                lines.append(f"  Insider transactions (Form 4): {count} filings in last {insider.get('period_days', 90)} days (latest: {most_recent})")

        # Revenue YoY from XBRL
        rev_yoy = sec_data.get("revenue_yoy_growth")
        if rev_yoy is not None:
            lines.append(f"  SEC filing revenue growth: {rev_yoy:+.1f}% YoY")

        # Net income trend
        ni_yoy = sec_data.get("net_income_yoy_growth")
        if ni_yoy == "turnaround":
            lines.append("  Net income: turned positive (turnaround from loss)")
        elif ni_yoy == "negative":
            lines.append("  Net income: currently negative")
        elif isinstance(ni_yoy, (int, float)):
            lines.append(f"  SEC filing net income growth: {ni_yoy:+.1f}% YoY")

        # Company facts from XBRL
        facts = sec_data.get("company_facts", {})
        if facts:
            rev = facts.get("Revenue_annual", {})
            if rev.get("value"):
                val = rev["value"]
                if val > 1_000_000_000:
                    lines.append(f"  Annual revenue (10-K): ${val/1e9:.1f}B (period ending {rev.get('period_end', 'N/A')})")
                elif val > 1_000_000:
                    lines.append(f"  Annual revenue (10-K): ${val/1e6:.0f}M (period ending {rev.get('period_end', 'N/A')})")

            cash = facts.get("CashAndEquivalents_annual", {})
            if cash.get("value"):
                val = cash["value"]
                if val > 1_000_000_000:
                    lines.append(f"  Cash & equivalents: ${val/1e9:.1f}B")
                elif val > 1_000_000:
                    lines.append(f"  Cash & equivalents: ${val/1e6:.0f}M")

            debt = facts.get("TotalDebt_annual", {})
            if debt.get("value"):
                val = debt["value"]
                if val > 1_000_000_000:
                    lines.append(f"  Long-term debt: ${val/1e9:.1f}B")
                elif val > 1_000_000:
                    lines.append(f"  Long-term debt: ${val/1e6:.0f}M")

            fcf = facts.get("FreeCashFlow_annual", {})
            if fcf.get("value"):
                val = fcf["value"]
                if val > 1_000_000_000:
                    lines.append(f"  Operating cash flow: ${val/1e9:.1f}B")
                elif val > 1_000_000:
                    lines.append(f"  Operating cash flow: ${val/1e6:.0f}M")
                elif val < 0:
                    lines.append(f"  Operating cash flow: -${abs(val)/1e6:.0f}M (cash burn)")

        # Recent material filings
        filings = sec_data.get("recent_filings", [])
        if filings:
            # Show important recent filings
            important = [f for f in filings if f["form"] in ("10-K", "10-Q", "8-K", "S-1")][:5]
            if important:
                lines.append("  Recent filings:")
                for f in important:
                    desc = f.get("description", f["form"])
                    lines.append(f"    {f['date']} — {f['form']}: {desc}")

        # Material events count
        if sec_data.get("material_events", 0) > 0:
            lines.append(f"  Material events (8-K): {sec_data['material_events']} in last 6 months")

        if len(lines) <= 1:
            return ""

        lines.append("\nSEC filings are the most reliable public data source. Use insider activity and filing patterns to validate your thesis.")
        return "\n".join(lines)

    def _parse_response(self, response_text):
        """Parse Claude's JSON response."""
        try:
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                data = json.loads(json_match.group())
                action = str(data.get('action', 'HOLD')).upper()
                entry = safe_float(data.get('entry_price', 0))
                stop = safe_float(data.get('stop_loss', 0))
                target = safe_float(data.get('target_price', 0))

                # Sanity-check: fix inverted target/stop for the action direction
                if action in ('STRONG BUY', 'BUY', 'HOLD'):
                    # Target should be above entry, stop below
                    if entry > 0 and target > 0 and target < entry:
                        target, stop = stop, target  # swap
                    if entry > 0 and stop > 0 and stop > entry:
                        target, stop = stop, target  # swap
                elif action in ('SELL', 'STRONG SELL', 'SHORT'):
                    # Target should be below entry, stop above
                    if entry > 0 and target > 0 and target > entry:
                        target, stop = stop, target  # swap
                    if entry > 0 and stop > 0 and stop < entry:
                        target, stop = stop, target  # swap

                raw_score = max(0, min(100, int(data.get('score', 50))))

                # Enforce the banned 45-55 dead zone — push to nearest decisive edge
                if 45 <= raw_score <= 55:
                    if action in ('STRONG BUY', 'BUY'):
                        raw_score = 65
                    elif action in ('SELL', 'STRONG SELL', 'SHORT'):
                        raw_score = 35
                    elif raw_score >= 50:
                        raw_score = 58  # lean bullish
                    else:
                        raw_score = 42  # lean bearish

                return {
                    'score': raw_score,
                    'reasoning': str(data.get('reasoning', '')),
                    'agreements': data.get('agreements', []),
                    'disagreements': data.get('disagreements', []),
                    'risks': data.get('risks', []),
                    'action': action,
                    'entry_price': entry,
                    'stop_loss': stop,
                    'target_price': target,
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
