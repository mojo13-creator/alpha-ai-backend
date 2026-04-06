# analysis/technical_scorer.py
"""
Programmatic Technical Score Calculator (0-100)
No AI involved — pure math from indicator data.
Sub-categories: Trend (30%), Momentum (30%), Volume (20%), Volatility (20%)
"""

import math
import numpy as np
import pandas as pd


def safe_float(val, default=0.0):
    try:
        v = float(val)
        return default if math.isnan(v) or math.isinf(v) else v
    except Exception:
        return default


def score_trend(df, latest, prev):
    """Score trend signals (0-100). Price vs SMAs, EMA crossover, ADX.
    Uses accumulation from 0 — fully bearish = ~0, fully bullish = ~100."""
    bullish_pts = 0.0
    bearish_pts = 0.0
    signals = []
    price = safe_float(latest['close'])
    if price <= 0:
        return 50, ["No price data"]

    # --- Price vs SMAs (20/50/100/200) — 15 pts each = 60 pts max ---
    sma_checks = [
        ('SMA_20', 12, 'short-term'),
        ('SMA_50', 14, 'medium-term'),
        ('SMA_100', 16, 'intermediate'),
        ('SMA_200', 18, 'long-term'),
    ]
    for col, weight, label in sma_checks:
        sma = safe_float(latest.get(col, 0))
        if sma <= 0:
            continue
        pct_from_sma = ((price - sma) / sma) * 100

        if pct_from_sma > 10:
            bullish_pts += weight
            signals.append(f"Price {pct_from_sma:.1f}% above {label} SMA — strong uptrend")
        elif pct_from_sma > 2:
            bullish_pts += weight * 0.6
            signals.append(f"Price above {label} SMA")
        elif pct_from_sma > -2:
            # Near the SMA — check for recent cross
            if len(df) >= 5:
                prev_price_5 = safe_float(df.iloc[-5]['close'])
                prev_sma_5 = safe_float(df.iloc[-5].get(col, 0))
                if prev_sma_5 > 0 and prev_price_5 < prev_sma_5 and price > sma:
                    bullish_pts += weight * 0.8
                    signals.append(f"Recently crossed above {label} SMA — bullish cross")
                elif prev_sma_5 > 0 and prev_price_5 > prev_sma_5 and price < sma:
                    bearish_pts += weight * 0.8
                    signals.append(f"Recently crossed below {label} SMA — bearish cross")
                else:
                    # Truly at SMA — slight bearish bias (resistance)
                    bearish_pts += weight * 0.2
        elif pct_from_sma > -10:
            bearish_pts += weight * 0.6
            signals.append(f"Price below {label} SMA")
        else:
            bearish_pts += weight
            signals.append(f"Price {abs(pct_from_sma):.1f}% below {label} SMA — strong downtrend")

    # --- EMA 9/21 crossover — 12 pts ---
    ema9 = safe_float(latest.get('EMA_9', 0))
    ema21 = safe_float(latest.get('EMA_21', 0))
    if ema9 > 0 and ema21 > 0:
        prev_ema9 = safe_float(prev.get('EMA_9', 0))
        prev_ema21 = safe_float(prev.get('EMA_21', 0))
        if ema9 > ema21:
            if prev_ema9 > 0 and prev_ema21 > 0 and prev_ema9 <= prev_ema21:
                bullish_pts += 12
                signals.append("EMA 9/21 bullish crossover — fresh buy signal")
            else:
                bullish_pts += 7
                signals.append("EMA 9 above EMA 21 — short-term bullish")
        else:
            if prev_ema9 > 0 and prev_ema21 > 0 and prev_ema9 >= prev_ema21:
                bearish_pts += 12
                signals.append("EMA 9/21 bearish crossover — fresh sell signal")
            else:
                bearish_pts += 7
                signals.append("EMA 9 below EMA 21 — short-term bearish")

    # --- Golden/Death Cross (50/200) — 14 pts ---
    sma50 = safe_float(latest.get('SMA_50', 0))
    sma200 = safe_float(latest.get('SMA_200', 0))
    if sma50 > 0 and sma200 > 0:
        if sma50 > sma200:
            sep = ((sma50 - sma200) / sma200) * 100
            if sep > 5:
                bullish_pts += 14
                signals.append(f"Golden Cross with {sep:.1f}% separation")
            else:
                bullish_pts += 8
                signals.append("Golden Cross (50 > 200 SMA)")
        else:
            sep = ((sma200 - sma50) / sma200) * 100
            if sep > 5:
                bearish_pts += 14
                signals.append(f"Death Cross with {sep:.1f}% separation")
            else:
                bearish_pts += 8
                signals.append("Death Cross (50 < 200 SMA)")

    # --- ADX (trend strength) — amplifier, does NOT compress ---
    adx = safe_float(latest.get('ADX', 0))
    if adx > 0:
        if adx >= 40:
            signals.append(f"ADX {adx:.0f} — very strong trend")
        elif adx >= 25:
            signals.append(f"ADX {adx:.0f} — trending")
        else:
            signals.append(f"ADX {adx:.0f} — weak/choppy")

    # Convert to 0-100 score
    total = bullish_pts + bearish_pts
    if total == 0:
        score = 50
    else:
        score = (bullish_pts / total) * 100

    # ADX amplification: strong trends push score further from 50
    if adx >= 35:
        deviation = score - 50
        score = 50 + deviation * 1.3
    elif adx < 15:
        deviation = score - 50
        score = 50 + deviation * 0.85

    return max(0, min(100, round(score))), signals


def score_momentum(df, latest, prev):
    """Score momentum signals (0-100). RSI, MACD, Stochastic.
    Uses accumulation approach like trend scorer."""
    bullish_pts = 0.0
    bearish_pts = 0.0
    signals = []

    # --- RSI (up to 30 pts) ---
    rsi = safe_float(latest.get('RSI', 0))
    prev_rsi = safe_float(prev.get('RSI', 0))
    if rsi > 0:
        if rsi < 25:
            if prev_rsi > 0 and rsi > prev_rsi:
                bullish_pts += 30
                signals.append(f"RSI {rsi:.0f} deeply oversold WITH uptick — strong buy signal")
            else:
                bullish_pts += 20
                signals.append(f"RSI {rsi:.0f} deeply oversold — potential reversal")
        elif rsi < 35:
            if prev_rsi > 0 and rsi > prev_rsi:
                bullish_pts += 22
                signals.append(f"RSI {rsi:.0f} oversold and recovering — buy signal")
            else:
                bullish_pts += 12
                signals.append(f"RSI {rsi:.0f} oversold")
        elif rsi < 45:
            bullish_pts += 6
            signals.append(f"RSI {rsi:.0f} — mild bearish zone")
        elif rsi <= 55:
            # True neutral — balanced contribution
            bullish_pts += 5
            bearish_pts += 5
        elif rsi < 65:
            bearish_pts += 6
            signals.append(f"RSI {rsi:.0f} — bullish momentum (mildly overbought)")
        elif rsi < 75:
            if prev_rsi > 0 and rsi < prev_rsi:
                bearish_pts += 22
                signals.append(f"RSI {rsi:.0f} overbought and declining — sell signal")
            else:
                bearish_pts += 12
                signals.append(f"RSI {rsi:.0f} — approaching overbought")
        else:
            if prev_rsi > 0 and rsi < prev_rsi:
                bearish_pts += 30
                signals.append(f"RSI {rsi:.0f} extremely overbought WITH downtick — strong sell")
            else:
                bearish_pts += 20
                signals.append(f"RSI {rsi:.0f} extremely overbought")

    # --- MACD (up to 25 pts) ---
    macd = safe_float(latest.get('MACD', 0))
    macd_sig = safe_float(latest.get('MACD_Signal', 0))
    macd_hist = safe_float(latest.get('MACD_Histogram', 0))
    prev_hist = safe_float(prev.get('MACD_Histogram', 0))

    if macd != 0 or macd_sig != 0:
        if macd_hist > 0 and prev_hist <= 0:
            bullish_pts += 20
            signals.append("MACD histogram turned positive — bullish momentum shift")
        elif macd_hist < 0 and prev_hist >= 0:
            bearish_pts += 20
            signals.append("MACD histogram turned negative — bearish momentum shift")
        elif macd_hist > 0 and macd_hist > prev_hist:
            bullish_pts += 14
            signals.append("MACD histogram expanding bullish")
        elif macd_hist > 0 and macd_hist < prev_hist:
            bullish_pts += 6
            signals.append("MACD bullish but momentum fading")
        elif macd_hist < 0 and macd_hist < prev_hist:
            bearish_pts += 14
            signals.append("MACD histogram expanding bearish")
        elif macd_hist < 0 and macd_hist > prev_hist:
            bearish_pts += 6
            signals.append("MACD bearish but selling pressure easing")

        # Price-MACD divergence (check last 10 bars)
        if len(df) >= 10:
            recent_prices = df['close'].iloc[-10:]
            recent_macd = df['MACD'].iloc[-10:] if 'MACD' in df.columns else None
            if recent_macd is not None and not recent_macd.isna().all():
                price_trend = recent_prices.iloc[-1] - recent_prices.iloc[0]
                macd_trend = safe_float(recent_macd.iloc[-1]) - safe_float(recent_macd.iloc[0])
                if price_trend < 0 and macd_trend > 0:
                    bullish_pts += 15
                    signals.append("Bullish divergence: price falling but MACD rising")
                elif price_trend > 0 and macd_trend < 0:
                    bearish_pts += 15
                    signals.append("Bearish divergence: price rising but MACD falling")

    # --- Stochastic %K/%D (up to 20 pts) ---
    stoch_k = safe_float(latest.get('STOCH', 0))
    stoch_d = safe_float(latest.get('STOCH_Signal', 0))
    prev_stoch_k = safe_float(prev.get('STOCH', 0))
    prev_stoch_d = safe_float(prev.get('STOCH_Signal', 0))

    if stoch_k > 0:
        if stoch_k < 20:
            if stoch_k > stoch_d and prev_stoch_k <= prev_stoch_d:
                bullish_pts += 20
                signals.append(f"Stochastic bullish crossover in oversold zone ({stoch_k:.0f})")
            else:
                bullish_pts += 12
                signals.append(f"Stochastic oversold ({stoch_k:.0f})")
        elif stoch_k < 40:
            bullish_pts += 5
        elif stoch_k > 80:
            if stoch_k < stoch_d and prev_stoch_k >= prev_stoch_d:
                bearish_pts += 20
                signals.append(f"Stochastic bearish crossover in overbought zone ({stoch_k:.0f})")
            else:
                bearish_pts += 12
                signals.append(f"Stochastic overbought ({stoch_k:.0f})")
        elif stoch_k > 60:
            bearish_pts += 5

    # Convert to 0-100
    total = bullish_pts + bearish_pts
    if total == 0:
        score = 50
    else:
        score = (bullish_pts / total) * 100

    return max(0, min(100, round(score))), signals


def score_volume(df, latest):
    """Score volume signals (0-100). Volume vs avg, OBV trend, volume-price alignment.
    Uses accumulation approach."""
    bullish_pts = 0.0
    bearish_pts = 0.0
    signals = []

    volume = safe_float(latest.get('volume', 0))
    price = safe_float(latest['close'])
    prev_close = safe_float(df.iloc[-2]['close']) if len(df) >= 2 else price

    # --- Volume vs 20-day average (up to 25 pts) ---
    if len(df) >= 20:
        avg_vol = safe_float(df['volume'].tail(20).mean())
        if avg_vol > 0 and volume > 0:
            ratio = volume / avg_vol
            price_up = price > prev_close

            if ratio >= 2.0:
                if price_up:
                    bullish_pts += 25
                    signals.append(f"Volume spike {ratio:.1f}x average on UP day — strong accumulation")
                else:
                    bearish_pts += 25
                    signals.append(f"Volume spike {ratio:.1f}x average on DOWN day — strong distribution")
            elif ratio >= 1.5:
                if price_up:
                    bullish_pts += 16
                    signals.append(f"Above-average volume ({ratio:.1f}x) on up day — accumulation")
                else:
                    bearish_pts += 16
                    signals.append(f"Above-average volume ({ratio:.1f}x) on down day — distribution")
            elif ratio >= 1.0:
                if price_up:
                    bullish_pts += 8
                else:
                    bearish_pts += 8
            else:
                # Below-average volume — mildly bearish (lack of conviction)
                bearish_pts += 5
                if ratio < 0.5:
                    signals.append("Very low volume — weak conviction")

    # --- OBV trend (up to 20 pts) ---
    obv = safe_float(latest.get('OBV', 0))
    obv_sma = safe_float(latest.get('OBV_SMA_20', 0))
    if obv != 0 and obv_sma != 0:
        if obv > obv_sma:
            bullish_pts += 12
            signals.append("OBV above 20-day average — positive volume trend")

            # OBV divergence from price
            if len(df) >= 10:
                price_chg = price - safe_float(df.iloc[-10]['close'])
                obv_10 = safe_float(df.iloc[-10].get('OBV', 0))
                obv_chg = obv - obv_10
                if price_chg < 0 and obv_chg > 0:
                    bullish_pts += 15
                    signals.append("Bullish OBV divergence: price down but volume accumulating")
                elif price_chg > 0 and obv_chg < 0:
                    bearish_pts += 15
                    signals.append("Bearish OBV divergence: price up but volume distributing")
        else:
            bearish_pts += 12
            signals.append("OBV below 20-day average — negative volume trend")

    # --- Volume trend 5-day vs 20-day (up to 8 pts) ---
    if len(df) >= 20:
        vol_5 = safe_float(df['volume'].tail(5).mean())
        vol_20 = safe_float(df['volume'].tail(20).mean())
        if vol_20 > 0 and vol_5 > 0:
            vol_trend = vol_5 / vol_20
            if vol_trend > 1.3:
                bullish_pts += 8
                signals.append("Volume trending higher — increasing interest")
            elif vol_trend < 0.7:
                bearish_pts += 8
                signals.append("Volume trending lower — fading interest")

    # Convert to 0-100
    total = bullish_pts + bearish_pts
    if total == 0:
        score = 50
    else:
        score = (bullish_pts / total) * 100

    return max(0, min(100, round(score))), signals


def score_volatility(df, latest):
    """Score volatility signals (0-100). Bollinger position, ATR context, squeeze.
    Uses accumulation approach."""
    bullish_pts = 0.0
    bearish_pts = 0.0
    signals = []
    price = safe_float(latest['close'])
    if price <= 0:
        return 50, ["No price data"]

    # --- Bollinger Band position (up to 20 pts) ---
    bb_upper = safe_float(latest.get('BB_Upper', 0))
    bb_lower = safe_float(latest.get('BB_Lower', 0))
    bb_mid = safe_float(latest.get('BB_Middle', 0))

    if bb_upper > 0 and bb_lower > 0 and bb_upper != bb_lower:
        bb_pos = (price - bb_lower) / (bb_upper - bb_lower)

        if bb_pos < 0.05:
            bullish_pts += 20
            signals.append("Price at lower Bollinger Band — oversold, potential bounce")
        elif bb_pos < 0.2:
            bullish_pts += 12
            signals.append("Price near lower Bollinger Band")
        elif bb_pos < 0.4:
            bullish_pts += 5
        elif bb_pos > 0.95:
            bearish_pts += 20
            signals.append("Price at upper Bollinger Band — overbought, potential pullback")
        elif bb_pos > 0.8:
            bearish_pts += 12
            signals.append("Price near upper Bollinger Band")
        elif bb_pos > 0.6:
            bearish_pts += 5
        else:
            # Near middle — balanced
            bullish_pts += 3
            bearish_pts += 3
            signals.append("Price near middle Bollinger Band — neutral")

        # Bollinger Band width (volatility expansion/contraction)
        bb_width = (bb_upper - bb_lower) / bb_mid if bb_mid > 0 else 0
        if len(df) >= 20 and bb_mid > 0:
            widths = []
            for i in range(-20, 0):
                u = safe_float(df.iloc[i].get('BB_Upper', 0))
                l = safe_float(df.iloc[i].get('BB_Lower', 0))
                m = safe_float(df.iloc[i].get('BB_Middle', 0))
                if m > 0:
                    widths.append((u - l) / m)
            if widths:
                avg_width = sum(widths) / len(widths)
                if bb_width < avg_width * 0.6:
                    signals.append("Bollinger Bands contracting — volatility squeeze building")

    # --- Squeeze detection (Bollinger inside Keltner) (up to 8 pts) ---
    kc_upper = safe_float(latest.get('KC_Upper', 0))
    kc_lower = safe_float(latest.get('KC_Lower', 0))
    if kc_upper > 0 and kc_lower > 0 and bb_upper > 0 and bb_lower > 0:
        in_squeeze = bb_lower > kc_lower and bb_upper < kc_upper
        if in_squeeze:
            bullish_pts += 8
            signals.append("Bollinger-Keltner squeeze detected — breakout imminent")

    # --- ATR relative to price (up to 12 pts) ---
    atr = safe_float(latest.get('ATR', 0))
    if atr > 0 and price > 0:
        atr_pct = (atr / price) * 100
        if atr_pct > 5:
            bearish_pts += 12
            signals.append(f"High volatility (ATR {atr_pct:.1f}% of price) — elevated risk")
        elif atr_pct > 3:
            bearish_pts += 6
            signals.append(f"Moderate volatility (ATR {atr_pct:.1f}% of price)")
        elif atr_pct < 1:
            bullish_pts += 8
            signals.append(f"Low volatility (ATR {atr_pct:.1f}% of price) — stable")
        else:
            # Normal volatility — balanced
            bullish_pts += 3
            bearish_pts += 3

    # Convert to 0-100
    total = bullish_pts + bearish_pts
    if total == 0:
        score = 50
    else:
        score = (bullish_pts / total) * 100

    return max(0, min(100, round(score))), signals


def calculate_technical_score(df):
    """
    Master function: calculates the composite technical score.
    Returns dict with score, sub-scores, and key_signals.
    """
    if df is None or df.empty or len(df) < 2:
        return {
            'score': 50,
            'trend': 50, 'momentum': 50, 'volume': 50, 'volatility': 50,
            'key_signals': ['Insufficient data for technical analysis'],
        }

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    trend_score, trend_signals = score_trend(df, latest, prev)
    momentum_score, momentum_signals = score_momentum(df, latest, prev)
    volume_score, volume_signals = score_volume(df, latest)
    volatility_score, volatility_signals = score_volatility(df, latest)

    # Weighted composite: Trend 30%, Momentum 30%, Volume 20%, Volatility 20%
    composite = (
        trend_score * 0.30
        + momentum_score * 0.30
        + volume_score * 0.20
        + volatility_score * 0.20
    )
    composite = max(0, min(100, round(composite)))

    # Collect top signals (most impactful)
    all_signals = trend_signals + momentum_signals + volume_signals + volatility_signals

    return {
        'score': composite,
        'trend': trend_score,
        'momentum': momentum_score,
        'volume': volume_score,
        'volatility': volatility_score,
        'key_signals': all_signals[:8],  # Top 8 signals
    }
