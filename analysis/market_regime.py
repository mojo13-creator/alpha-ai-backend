# analysis/market_regime.py
"""
Market regime detection — SPY trend + VIX level → risk_on / neutral / risk_off.

Used by the composite scorer to dampen counter-regime signals. The validator
showed SELL signals had ~15% hit rate with +9-11% avg realized return — the
system was calling SELL right before stocks ripped. Most of those calls
happened in a clear risk-on regime where bearish technical setups simply
don't pay. This module gates that.

Cached for 1 hour per process — regime doesn't flip intraday.
"""

import time
from datetime import datetime
from typing import Optional

import yfinance as yf


_CACHE = {}
_CACHE_TTL_SECONDS = 3600  # 1 hour


def _cached(key: str):
    entry = _CACHE.get(key)
    if entry and time.time() - entry['ts'] < _CACHE_TTL_SECONDS:
        return entry['value']
    return None


def _set_cache(key: str, value):
    _CACHE[key] = {'ts': time.time(), 'value': value}


def _spy_trend() -> dict:
    """Return SPY trend snapshot: price, 50 SMA, 200 SMA, slope."""
    cached = _cached('spy_trend')
    if cached is not None:
        return cached

    try:
        df = yf.Ticker('SPY').history(period='1y', auto_adjust=True)
        if df is None or df.empty or len(df) < 200:
            return {'available': False}
        close = df['Close']
        price = float(close.iloc[-1])
        sma_50 = float(close.tail(50).mean())
        sma_200 = float(close.tail(200).mean())
        # 20-day slope as % change — momentum check
        change_20d = float((close.iloc[-1] / close.iloc[-21] - 1) * 100) if len(close) > 21 else 0.0
        result = {
            'available': True,
            'price': round(price, 2),
            'sma_50': round(sma_50, 2),
            'sma_200': round(sma_200, 2),
            'above_50': price > sma_50,
            'above_200': price > sma_200,
            'change_20d_pct': round(change_20d, 2),
        }
        _set_cache('spy_trend', result)
        return result
    except Exception as e:
        return {'available': False, 'error': str(e)}


def _vix_level() -> dict:
    """Return VIX level + classification."""
    cached = _cached('vix_level')
    if cached is not None:
        return cached

    try:
        df = yf.Ticker('^VIX').history(period='5d', auto_adjust=False)
        if df is None or df.empty:
            return {'available': False}
        vix = float(df['Close'].iloc[-1])

        if vix < 15:
            zone = 'calm'
        elif vix < 20:
            zone = 'normal'
        elif vix < 30:
            zone = 'elevated'
        else:
            zone = 'panic'

        result = {'available': True, 'vix': round(vix, 2), 'zone': zone}
        _set_cache('vix_level', result)
        return result
    except Exception as e:
        return {'available': False, 'error': str(e)}


def get_market_regime() -> dict:
    """
    Compute current market regime. Returns:
      {
        'regime': 'risk_on' | 'neutral' | 'risk_off',
        'spy_trend': {...},
        'vix': {...},
        'reasoning': str,
        'as_of': ISO timestamp
      }
    """
    cached = _cached('regime')
    if cached is not None:
        return cached

    spy = _spy_trend()
    vix = _vix_level()

    # If we can't fetch either, default to neutral so we don't dampen signals on bad data
    if not spy.get('available') or not vix.get('available'):
        return {
            'regime': 'neutral',
            'spy_trend': spy,
            'vix': vix,
            'reasoning': 'regime data unavailable — defaulting to neutral',
            'as_of': datetime.now().isoformat(),
        }

    above_200 = spy['above_200']
    above_50 = spy['above_50']
    momentum_up = spy['change_20d_pct'] > 0
    vix_zone = vix['zone']

    # Risk-on: clear SPY uptrend AND benign VIX
    if above_200 and above_50 and vix_zone in ('calm', 'normal'):
        regime = 'risk_on'
        reasoning = (f"SPY above both 50/200 SMAs (+{spy['change_20d_pct']:.1f}% 20d), "
                     f"VIX {vix['vix']:.1f} ({vix_zone}) — bearish signals downgraded")
    # Risk-off: SPY below 200 SMA OR VIX in panic, OR both 50/200 broken with VIX elevated
    elif (not above_200) or vix_zone == 'panic' or (not above_50 and vix_zone == 'elevated'):
        regime = 'risk_off'
        if not above_200:
            reasoning = (f"SPY below 200 SMA, VIX {vix['vix']:.1f} ({vix_zone}) — "
                         f"bullish signals downgraded")
        else:
            reasoning = (f"VIX {vix['vix']:.1f} ({vix_zone}) signaling stress — "
                         f"bullish signals downgraded")
    else:
        regime = 'neutral'
        reasoning = (f"Mixed: above_200={above_200}, above_50={above_50}, "
                     f"VIX {vix['vix']:.1f} ({vix_zone}) — no regime adjustment")

    result = {
        'regime': regime,
        'spy_trend': spy,
        'vix': vix,
        'reasoning': reasoning,
        'as_of': datetime.now().isoformat(),
    }
    _set_cache('regime', result)
    return result


def apply_regime_to_signal(signal: str, composite_score: int,
                            regime: Optional[dict] = None) -> tuple:
    """
    Adjust a signal based on market regime. Returns (new_signal, regime_note).

    Rules:
      - risk_on: bearish signals get downgraded one level UNLESS conviction is
        overwhelming (composite < 15 for SHORT/STRONG_SELL, < 25 for SELL).
        STRONG_SELL → SELL, SELL → HOLD, SHORT → HOLD.
      - risk_off: bullish signals get downgraded one level UNLESS composite > 85.
        STRONG_BUY → BUY, BUY → HOLD.
      - neutral: no adjustment.
    """
    if regime is None:
        regime = get_market_regime()

    r = regime.get('regime', 'neutral')
    if r == 'neutral':
        return signal, ''

    if r == 'risk_on':
        # Downgrade bearish signals
        if signal == 'STRONG_SELL':
            if composite_score < 15:
                return signal, 'risk_on regime but conviction overwhelming (composite < 15)'
            return 'SELL', 'risk_on regime — STRONG_SELL downgraded to SELL'
        if signal == 'SELL':
            if composite_score < 25:
                return signal, 'risk_on regime but composite < 25 — SELL retained'
            return 'HOLD', 'risk_on regime — SELL downgraded to HOLD'
        if signal == 'SHORT':
            if composite_score < 15:
                return signal, 'risk_on regime but conviction overwhelming (composite < 15)'
            return 'HOLD', 'risk_on regime — SHORT downgraded to HOLD'

    if r == 'risk_off':
        # Downgrade bullish signals
        if signal == 'STRONG_BUY':
            if composite_score > 85:
                return signal, 'risk_off regime but conviction overwhelming (composite > 85)'
            return 'BUY', 'risk_off regime — STRONG_BUY downgraded to BUY'
        if signal == 'BUY':
            if composite_score > 75:
                return signal, 'risk_off regime but composite > 75 — BUY retained'
            return 'HOLD', 'risk_off regime — BUY downgraded to HOLD'

    return signal, ''


if __name__ == '__main__':
    import json
    regime = get_market_regime()
    print(json.dumps(regime, indent=2))
