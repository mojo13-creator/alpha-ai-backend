# analysis/horizon_screener.py
"""
Horizon-Based Stock Screener
Three time horizons (short/mid/long) using purely quantitative signals.
No AI API calls — all scoring is mathematical/technical/fundamental.
"""

import os
import sys
import math
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yfinance as yf
from data_collection.finviz_scraper import FinvizScraper
from data_collection.stock_data import StockDataCollector
from analysis.technical_scorer import calculate_technical_score
from analysis.fundamental_scorer import calculate_fundamental_score, classify_market_cap
from analysis.sentiment_scorer import calculate_sentiment_score


def safe_float(val, default=0.0):
    try:
        v = float(val)
        return default if math.isnan(v) or math.isinf(v) else v
    except Exception:
        return default


# Blue-chip universe for long-term screening
LONG_TERM_UNIVERSE = [
    # Major ETFs
    'VOO', 'SPY', 'QQQ', 'IWM', 'DIA', 'VTI',
    # Mega-cap tech
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'AVGO', 'ORCL', 'CRM',
    # Financials
    'JPM', 'V', 'MA', 'BRK-B', 'BAC', 'GS',
    # Healthcare
    'UNH', 'LLY', 'JNJ', 'PFE', 'ABBV', 'MRK',
    # Consumer
    'HD', 'PG', 'COST', 'WMT', 'KO', 'PEP', 'MCD',
    # Industrial / Energy
    'CAT', 'DE', 'XOM', 'CVX', 'LMT',
]


class HorizonScreener:
    """
    Screens stocks across 3 time horizons using only quantitative signals.
    No AI API calls — keeps token costs zero for daily screening.
    """

    def __init__(self, db_manager, technical_analyzer, news_scraper):
        self.db = db_manager
        self.analyzer = technical_analyzer
        self.news_scraper = news_scraper
        self.collector = StockDataCollector(db_manager)
        self.finviz = FinvizScraper()

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------
    def _fetch_indicators(self, symbol, period='6mo'):
        """Fetch price data and calculate all indicators for a symbol."""
        try:
            self.collector.fetch_and_save(symbol, period=period)
            df = self.analyzer.calculate_all_indicators(symbol)
            if df is None or df.empty or len(df) < 20:
                return None
            return df
        except Exception as e:
            print(f"  [horizon] {symbol}: indicator fetch failed — {e}")
            return None

    def _get_market_cap(self, symbol):
        """Return market cap in dollars (float) or 0."""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info or {}
            return safe_float(info.get('marketCap', 0))
        except Exception:
            return 0

    def _get_finviz_signals_for(self, symbol, all_signals):
        """Count how many Finviz signal categories mention this symbol."""
        count = 0
        labels = []
        for stock in all_signals:
            if stock.get('symbol', '').upper() == symbol.upper():
                count += 1
                label = stock.get('category', '')
                if label and label not in labels:
                    labels.append(label)
        return count, labels

    def _build_pick(self, symbol, df, horizon, scores, action, reasoning, catalysts, market_cap_category):
        """Build the standard pick dict returned by all horizons."""
        latest = df.iloc[-1]
        price = safe_float(latest.get('close', 0))

        # Company name + sector (used for portfolio diversification at output time)
        company_name = symbol.upper()
        sector = None
        try:
            info = self.collector.get_stock_info(symbol)
            if info:
                company_name = info.get('name', symbol.upper())
                sector = info.get('sector')
        except Exception:
            pass

        composite = round(
            scores.get('technical', 50) * scores.get('tech_weight', 0.33)
            + scores.get('fundamental', 50) * scores.get('fund_weight', 0.33)
            + scores.get('sentiment', 50) * scores.get('sent_weight', 0.34)
        )
        composite = max(0, min(100, composite))

        # Determine signal from composite
        if composite >= 80:
            signal = 'STRONG_BUY'
        elif composite >= 65:
            signal = 'BUY'
        elif composite >= 45:
            signal = 'HOLD'
        elif composite >= 30:
            signal = 'SELL'
        else:
            signal = 'STRONG_SELL'

        return {
            'ticker': symbol.upper(),
            'company_name': company_name,
            'price': price,
            'composite_score': composite,
            'signal': signal,
            'horizon': horizon,
            'sub_scores': {
                'technical': scores.get('technical', 0),
                'fundamental': scores.get('fundamental', 0),
                'sentiment': scores.get('sentiment', 0),
            },
            'action': action,
            'reasoning': reasoning,
            'catalysts': catalysts,
            'market_cap_category': market_cap_category,
            'sector': sector,
        }

    def _diversify(self, scored, max_picks, max_per_sector=2):
        """
        Greedy diversification: walk the score-sorted list and accept picks
        unless adding one would exceed max_per_sector for that sector. Picks
        without a known sector are accepted up to one slot to avoid blocking
        ETFs / unclassified names.

        Without this, a single hot sector (semis, oil, biotech) can fill all
        picks and a "screener" portfolio becomes one concentrated bet.
        """
        scored.sort(key=lambda x: x.get('_rank_score', x.get('composite_score', 0)), reverse=True)
        picks = []
        sector_counts = {}
        unknown_used = 0
        for cand in scored:
            if len(picks) >= max_picks:
                break
            sec = cand.get('sector')
            if not sec:
                if unknown_used >= 1:
                    continue
                unknown_used += 1
                picks.append(cand)
                continue
            if sector_counts.get(sec, 0) >= max_per_sector:
                continue
            sector_counts[sec] = sector_counts.get(sec, 0) + 1
            picks.append(cand)

        # If sector caps left us short, top up from highest-scored leftovers
        # so we still hit max_picks. Concentration warning still surfaces below.
        if len(picks) < max_picks:
            remaining = [c for c in scored if c not in picks]
            picks.extend(remaining[:max_picks - len(picks)])

        for p in picks:
            p.pop('_rank_score', None)
        return picks

    def _compute_action(self, price, atr, horizon, signal_direction='long'):
        """Compute entry/stop/target tailored to each horizon."""
        if price <= 0:
            return {'entry_price': 0, 'stop_loss': 0, 'target_price': 0,
                    'time_horizon': 'N/A', 'risk_reward_ratio': 'N/A'}

        atr = safe_float(atr, price * 0.02)
        if atr <= 0:
            atr = price * 0.02

        entry = round(price, 2)

        if horizon == 'short_term':
            stop = round(price - 1.5 * atr, 2)
            target = round(price + 2.0 * atr, 2)
            time_horizon = '1-2 days'
        elif horizon == 'mid_term':
            stop = round(price - 2.0 * atr, 2)
            target = round(price + 3.0 * atr, 2)
            time_horizon = '2-8 weeks'
        else:  # long_term
            stop = round(price - 3.0 * atr, 2)
            target = round(price * 1.20, 2)  # 20% upside target
            time_horizon = '3-6 months'

        risk = entry - stop
        reward = target - entry
        rr = round(reward / risk, 1) if risk > 0 else 0

        return {
            'entry_price': entry,
            'stop_loss': stop,
            'target_price': target,
            'time_horizon': time_horizon,
            'risk_reward_ratio': f'{rr}:1',
        }

    # ------------------------------------------------------------------
    # SHORT-TERM: Momentum Plays (1-2 days)
    # ------------------------------------------------------------------
    def screen_short_term(self, max_picks=5, _finviz_data=None):
        """
        Momentum plays for 1-2 day holds.
        Targets midcap/small cap with volume spikes, RSI recovery, MACD turns.
        """
        print("\n" + "=" * 60)
        print("  SCREENER: Short-Term Momentum Plays")
        print("=" * 60)

        # Gather candidates from Finviz momentum signals
        all_finviz = _finviz_data if _finviz_data is not None else self.finviz.get_all_signals()
        candidates = set()
        for stock in all_finviz:
            sym = stock.get('symbol', '').strip().upper()
            if sym:
                candidates.add(sym)
        print(f"  Finviz candidates: {len(candidates)}")

        # Also pull from news intelligence
        try:
            cached = self.db.get_cached_news_intelligence(max_age_minutes=120)
            if cached is not None and not cached.empty:
                for _, row in cached.iterrows():
                    tickers_raw = row.get('affected_tickers', '')
                    try:
                        affected = json.loads(tickers_raw) if isinstance(tickers_raw, str) else tickers_raw
                    except (json.JSONDecodeError, TypeError):
                        continue
                    if isinstance(affected, list):
                        for entry in affected:
                            if isinstance(entry, dict):
                                sig = str(entry.get('signal', '')).upper()
                                if sig in ('BUY', 'STRONG_BUY'):
                                    tick = str(entry.get('ticker', '')).strip().upper()
                                    if tick:
                                        candidates.add(tick)
        except Exception:
            pass

        print(f"  Total candidates: {len(candidates)}")
        scored = []

        for symbol in candidates:
            try:
                df = self._fetch_indicators(symbol, period='6mo')
                if df is None:
                    continue

                latest = df.iloc[-1]
                price = safe_float(latest.get('close', 0))
                if price <= 0:
                    continue

                # Market cap filter: $300M - $10B
                market_cap = self._get_market_cap(symbol)
                cap_cat, cap_label = classify_market_cap(market_cap)
                if cap_cat not in ('small', 'midcap'):
                    continue

                rsi = safe_float(latest.get('RSI', 50))
                ema_9 = safe_float(latest.get('EMA_9', 0))
                macd_hist = safe_float(latest.get('MACD_Histogram', 0))
                atr = safe_float(latest.get('ATR', 0))
                volume = safe_float(latest.get('volume', 0))
                avg_volume = safe_float(df['volume'].tail(20).mean(), 1)
                volume_ratio = volume / avg_volume if avg_volume > 0 else 1

                # Previous day MACD histogram for slope detection
                prev_macd_hist = safe_float(df.iloc[-2].get('MACD_Histogram', 0)) if len(df) >= 2 else 0

                # Filter criteria (must pass at least 3 of 5)
                checks = 0
                reasons = []

                # Check 1: RSI oversold bounce or crossing above 50
                if rsi < 35:
                    checks += 1
                    reasons.append(f"RSI oversold at {rsi:.0f} — bounce setup")
                elif 48 <= rsi <= 58 and len(df) >= 3:
                    prev_rsi = safe_float(df.iloc[-3].get('RSI', 50))
                    if prev_rsi < 48:
                        checks += 1
                        reasons.append(f"RSI crossing above 50 ({prev_rsi:.0f} -> {rsi:.0f})")

                # Check 2: Volume spike
                if volume_ratio >= 2.0:
                    checks += 1
                    reasons.append(f"Volume {volume_ratio:.1f}x above 20-day average")

                # Check 3: Price above EMA_9
                if ema_9 > 0 and price > ema_9:
                    checks += 1
                    reasons.append(f"Price above EMA-9 (${price:.2f} > ${ema_9:.2f})")

                # Check 4: MACD histogram turning positive
                if macd_hist > 0 and prev_macd_hist <= 0:
                    checks += 1
                    reasons.append("MACD histogram turned positive")
                elif macd_hist > prev_macd_hist and macd_hist > 0:
                    checks += 1
                    reasons.append(f"MACD histogram accelerating ({prev_macd_hist:.3f} -> {macd_hist:.3f})")

                # Check 5: Enough volatility (ATR > 2% of price)
                atr_pct = (atr / price * 100) if price > 0 else 0
                if atr_pct >= 2.0:
                    checks += 1
                    reasons.append(f"ATR {atr_pct:.1f}% of price — sufficient volatility")

                if checks < 3:
                    continue

                # Scoring
                # Momentum score (0-100): RSI recovery + MACD slope + EMA distance
                rsi_component = max(0, min(100, (50 - abs(rsi - 45)) * 2.5))  # peak at RSI 45
                macd_slope = (macd_hist - prev_macd_hist) if prev_macd_hist != 0 else macd_hist
                macd_component = max(0, min(100, 50 + macd_slope * 500))
                ema_dist = ((price - ema_9) / ema_9 * 100) if ema_9 > 0 else 0
                ema_component = max(0, min(100, 50 + ema_dist * 10))
                momentum_score = (rsi_component + macd_component + ema_component) / 3

                # Volume score (0-100)
                vol_score = min(100, volume_ratio * 20)  # 5x ratio = 100

                # Catalyst score from Finviz signal count
                finviz_count, finviz_labels = self._get_finviz_signals_for(symbol, all_finviz)
                catalyst_score = min(100, finviz_count * 25)
                for label in finviz_labels:
                    prefixed = f"Finviz: {label}"
                    if prefixed not in reasons:
                        reasons.append(prefixed)

                # Combined rank score
                rank_score = 0.40 * momentum_score + 0.30 * vol_score + 0.30 * catalyst_score

                action = self._compute_action(price, atr, 'short_term')

                pick = self._build_pick(
                    symbol=symbol, df=df, horizon='short_term',
                    scores={'technical': round(momentum_score), 'fundamental': 50,
                            'sentiment': round(catalyst_score),
                            'tech_weight': 0.50, 'fund_weight': 0.15, 'sent_weight': 0.35},
                    action=action, reasoning=reasons[:5],
                    catalysts=finviz_labels[:3], market_cap_category=cap_label,
                )
                pick['_rank_score'] = rank_score
                scored.append(pick)
                print(f"  + {symbol}: rank={rank_score:.0f} checks={checks}/5")

            except Exception as e:
                print(f"  [short] {symbol}: error — {e}")
                continue

        # Sector-diversified top N — caps any single sector at 2 picks
        picks = self._diversify(scored, max_picks)

        print(f"  Short-term picks: {len(picks)}")
        return picks

    # ------------------------------------------------------------------
    # MID-TERM: Swing Trades (2-8 weeks)
    # ------------------------------------------------------------------
    def screen_mid_term(self, max_picks=6, _finviz_data=None):
        """
        Swing trades for 2-8 week holds.
        Targets mid + large cap with strong trend setups.
        """
        print("\n" + "=" * 60)
        print("  SCREENER: Mid-Term Swing Trades")
        print("=" * 60)

        # Gather candidates: Finviz upgrades + insider buying + new highs
        all_finviz = _finviz_data if _finviz_data is not None else self.finviz.get_all_signals()
        candidates = set()
        for stock in all_finviz:
            sym = stock.get('symbol', '').strip().upper()
            cat = stock.get('category', '')
            if sym and cat in ('Analyst Upgrade', 'Insider Buying', 'New 52W High', 'Unusual Volume'):
                candidates.add(sym)
        print(f"  Finviz candidates: {len(candidates)}")

        # Also pull news BUY signals
        try:
            cached = self.db.get_cached_news_intelligence(max_age_minutes=120)
            if cached is not None and not cached.empty:
                for _, row in cached.iterrows():
                    tickers_raw = row.get('affected_tickers', '')
                    try:
                        affected = json.loads(tickers_raw) if isinstance(tickers_raw, str) else tickers_raw
                    except (json.JSONDecodeError, TypeError):
                        continue
                    if isinstance(affected, list):
                        for entry in affected:
                            if isinstance(entry, dict):
                                sig = str(entry.get('signal', '')).upper()
                                if sig in ('BUY', 'STRONG_BUY'):
                                    tick = str(entry.get('ticker', '')).strip().upper()
                                    if tick:
                                        candidates.add(tick)
        except Exception:
            pass

        print(f"  Total candidates: {len(candidates)}")
        scored = []

        for symbol in candidates:
            try:
                df = self._fetch_indicators(symbol, period='1y')
                if df is None:
                    continue

                latest = df.iloc[-1]
                price = safe_float(latest.get('close', 0))
                if price <= 0:
                    continue

                # Market cap filter: $2B+ (mid, large, mega)
                market_cap = self._get_market_cap(symbol)
                cap_cat, cap_label = classify_market_cap(market_cap)
                if cap_cat in ('micro', 'small', 'unknown'):
                    continue

                sma_20 = safe_float(latest.get('SMA_20', 0))
                sma_50 = safe_float(latest.get('SMA_50', 0))
                rsi = safe_float(latest.get('RSI', 50))
                macd = safe_float(latest.get('MACD', 0))
                macd_signal = safe_float(latest.get('MACD_Signal', 0))
                adx = safe_float(latest.get('ADX', 0))
                atr = safe_float(latest.get('ATR', 0))

                # 20-day price momentum
                if len(df) >= 20:
                    price_20d_ago = safe_float(df.iloc[-20].get('close', price))
                    momentum_20d = ((price - price_20d_ago) / price_20d_ago * 100) if price_20d_ago > 0 else 0
                else:
                    momentum_20d = 0

                # Filter criteria (must pass at least 4 of 6)
                checks = 0
                reasons = []

                if sma_50 > 0 and price > sma_50:
                    checks += 1
                    reasons.append(f"Price above SMA-50 (${price:.2f} > ${sma_50:.2f})")

                if sma_20 > 0 and sma_50 > 0 and sma_20 > sma_50:
                    checks += 1
                    reasons.append(f"SMA-20 above SMA-50 — short-term trend leading")

                if 45 <= rsi <= 70:
                    checks += 1
                    reasons.append(f"RSI {rsi:.0f} — strong momentum without being overbought")

                if macd > macd_signal:
                    checks += 1
                    reasons.append(f"MACD above signal line — bullish momentum")

                if adx > 20:
                    checks += 1
                    reasons.append(f"ADX {adx:.0f} — trend has strength")

                if momentum_20d > 3:
                    checks += 1
                    reasons.append(f"20-day momentum +{momentum_20d:.1f}%")

                if checks < 4:
                    continue

                # Sub-scores from existing scorers
                tech_result = calculate_technical_score(df)
                tech_score = tech_result.get('score', 50)

                fund_result = calculate_fundamental_score(symbol)
                fund_score = fund_result.get('score', 50)

                news_articles = []
                try:
                    news_articles = self.news_scraper.fetch_stock_news(symbol, days=7) or []
                except Exception:
                    pass
                sent_result = calculate_sentiment_score(
                    news_articles=news_articles, symbol=symbol,
                )
                sent_score = sent_result.get('score', 50)

                # Trend score: SMA alignment + ADX + distance above SMA_50
                sma_dist = ((price - sma_50) / sma_50 * 100) if sma_50 > 0 else 0
                trend_score = min(100, (adx * 1.5) + (sma_dist * 3) + (30 if sma_20 > sma_50 else 0))
                trend_score = max(0, trend_score)

                # Combined rank
                rank_score = (
                    0.35 * trend_score
                    + 0.25 * fund_score
                    + 0.25 * tech_score
                    + 0.15 * sent_score
                )

                # Catalysts
                finviz_count, finviz_labels = self._get_finviz_signals_for(symbol, all_finviz)
                for label in finviz_labels:
                    reasons.append(f"Finviz: {label}")

                action = self._compute_action(price, atr, 'mid_term')

                pick = self._build_pick(
                    symbol=symbol, df=df, horizon='mid_term',
                    scores={'technical': tech_score, 'fundamental': fund_score,
                            'sentiment': sent_score,
                            'tech_weight': 0.35, 'fund_weight': 0.35, 'sent_weight': 0.30},
                    action=action, reasoning=reasons[:6],
                    catalysts=finviz_labels[:3], market_cap_category=cap_label,
                )
                pick['_rank_score'] = rank_score
                scored.append(pick)
                print(f"  + {symbol}: rank={rank_score:.0f} tech={tech_score} fund={fund_score} sent={sent_score}")

            except Exception as e:
                print(f"  [mid] {symbol}: error — {e}")
                continue

        picks = self._diversify(scored, max_picks)

        print(f"  Mid-term picks: {len(picks)}")
        return picks

    # ------------------------------------------------------------------
    # LONG-TERM: Core Holdings (3+ months)
    # ------------------------------------------------------------------
    def screen_long_term(self, max_picks=5, _finviz_data=None):
        """
        Core holdings for 3+ month holds.
        Targets large/mega cap + ETFs with strong fundamentals.
        """
        print("\n" + "=" * 60)
        print("  SCREENER: Long-Term Core Holdings")
        print("=" * 60)

        # Start with predefined blue-chip universe
        candidates = set(LONG_TERM_UNIVERSE)

        # Add Finviz new highs (from pre-fetched data or fresh call)
        all_finviz = _finviz_data if _finviz_data is not None else []
        new_highs = [s for s in all_finviz if s.get('category') == 'New 52W High']
        if not new_highs:
            try:
                new_highs = self.finviz.get_new_highs()
            except Exception:
                new_highs = []
        for stock in new_highs:
            sym = stock.get('symbol', '').strip().upper()
            if sym:
                candidates.add(sym)

        print(f"  Total candidates: {len(candidates)}")
        scored = []

        for symbol in candidates:
            try:
                df = self._fetch_indicators(symbol, period='1y')
                if df is None:
                    continue

                latest = df.iloc[-1]
                price = safe_float(latest.get('close', 0))
                if price <= 0:
                    continue

                # Market cap filter: $10B+ (large, mega, ETF)
                market_cap = self._get_market_cap(symbol)
                cap_cat, cap_label = classify_market_cap(market_cap)
                # Allow ETFs (which may have market_cap=0) if they're in the predefined universe
                is_predefined = symbol in LONG_TERM_UNIVERSE
                if not is_predefined and cap_cat not in ('large', 'mega'):
                    continue
                if is_predefined and cap_cat == 'unknown':
                    cap_label = 'ETF' if symbol in ('VOO', 'SPY', 'QQQ', 'IWM', 'DIA', 'VTI') else cap_label

                sma_50 = safe_float(latest.get('SMA_50', 0))
                sma_200 = safe_float(latest.get('SMA_200', 0))
                atr = safe_float(latest.get('ATR', 0))

                # Filter criteria (must pass at least 2 of 3)
                checks = 0
                reasons = []

                if sma_200 > 0 and price > sma_200:
                    checks += 1
                    reasons.append(f"Price above SMA-200 — long-term uptrend intact")

                if sma_50 > 0 and sma_200 > 0 and sma_50 > sma_200:
                    checks += 1
                    reasons.append(f"Golden cross — SMA-50 above SMA-200")

                # Fundamental score
                fund_result = calculate_fundamental_score(symbol)
                fund_score = fund_result.get('score', 50)
                if fund_score >= 55:
                    checks += 1
                    reasons.append(f"Fundamental score {fund_score}/100")

                if checks < 2:
                    continue

                # Full sub-scores
                tech_result = calculate_technical_score(df)
                tech_score = tech_result.get('score', 50)

                news_articles = []
                try:
                    news_articles = self.news_scraper.fetch_stock_news(symbol, days=7) or []
                except Exception:
                    pass
                sent_result = calculate_sentiment_score(
                    news_articles=news_articles, symbol=symbol,
                )
                sent_score = sent_result.get('score', 50)

                # Trend score for long-term: SMA alignment + distance above 200
                sma_dist_200 = ((price - sma_200) / sma_200 * 100) if sma_200 > 0 else 0
                golden_cross_bonus = 20 if (sma_50 > 0 and sma_200 > 0 and sma_50 > sma_200) else 0
                trend_score = min(100, max(0, sma_dist_200 * 2 + golden_cross_bonus + 30))

                # Add fundamental details to reasoning
                pe = fund_result.get('pe_vs_sector', 'N/A')
                rev_growth = fund_result.get('revenue_growth', 'N/A')
                if pe != 'N/A':
                    reasons.append(f"P/E vs sector: {pe}")
                if rev_growth != 'N/A':
                    reasons.append(f"Revenue growth: {rev_growth}")

                # Combined rank: heavily fundamental-weighted
                rank_score = (
                    0.45 * fund_score
                    + 0.30 * trend_score
                    + 0.15 * sent_score
                    + 0.10 * tech_score
                )

                action = self._compute_action(price, atr, 'long_term')

                pick = self._build_pick(
                    symbol=symbol, df=df, horizon='long_term',
                    scores={'technical': tech_score, 'fundamental': fund_score,
                            'sentiment': sent_score,
                            'tech_weight': 0.20, 'fund_weight': 0.50, 'sent_weight': 0.30},
                    action=action, reasoning=reasons[:6],
                    catalysts=[], market_cap_category=cap_label,
                )
                pick['_rank_score'] = rank_score
                scored.append(pick)
                print(f"  + {symbol}: rank={rank_score:.0f} fund={fund_score} tech={tech_score}")

            except Exception as e:
                print(f"  [long] {symbol}: error — {e}")
                continue

        picks = self._diversify(scored, max_picks)

        print(f"  Long-term picks: {len(picks)}")
        return picks

    # ------------------------------------------------------------------
    # Run all horizons
    # ------------------------------------------------------------------
    def run_all_horizons(self):
        """Run all 3 screens and return combined result."""
        start = datetime.now()

        # Pre-fetch Finviz once to avoid 3 separate scrapes
        all_finviz = self.finviz.get_all_signals()

        short = self.screen_short_term(_finviz_data=all_finviz)
        mid = self.screen_mid_term(_finviz_data=all_finviz)
        long = self.screen_long_term(_finviz_data=all_finviz)

        elapsed = (datetime.now() - start).total_seconds()

        return {
            'generated_at': datetime.now().isoformat(),
            'short_term': {
                'picks': short,
                'horizon': '1-2 days',
                'strategy': 'Momentum Plays',
                'description': 'Short-term momentum stocks with volume spikes, RSI recovery, and news catalysts.',
            },
            'mid_term': {
                'picks': mid,
                'horizon': '2-8 weeks',
                'strategy': 'Swing Trades',
                'description': 'Mid-cap and large-cap stocks with strong trend setups and fundamental backing.',
            },
            'long_term': {
                'picks': long,
                'horizon': '3+ months',
                'strategy': 'Core Holdings',
                'description': 'Blue-chip stocks and ETFs with strong fundamentals for long-term portfolio building.',
            },
            'stats': {
                'total_picks': len(short) + len(mid) + len(long),
                'elapsed_seconds': round(elapsed, 1),
            },
        }