# analysis/options_signals.py
"""
Options-derived positioning signals.

Three signals from the options chain — one structural (IV vs RV), one flow
(put/call volume), one open positioning (OI skew). Aggregated over 7-45 day
expirations to avoid 0DTE noise and skew-blowout from quarterly events.

Used by sentiment_scorer to adjust the positioning component. Returns a
score adjustment in [-12, +12], a signals list, and a diagnostics dict.
"""

import math
from datetime import datetime, timedelta

import numpy as np


def safe_float(val, default=0.0):
    try:
        v = float(val)
        return default if math.isnan(v) or math.isinf(v) else v
    except Exception:
        return default


def _realized_vol_20d(df):
    """Annualized realized volatility from 20-day daily close returns."""
    if df is None or len(df) < 21:
        return None
    closes = df['close'].tail(21).values
    returns = np.diff(np.log(closes))
    if len(returns) < 5:
        return None
    daily_std = float(np.std(returns, ddof=1))
    return daily_std * math.sqrt(252)


def _aggregate_chain(ticker, current_price, min_dte=7, max_dte=45):
    """
    Aggregate calls/puts across expirations in [min_dte, max_dte] days.
    Returns dict with ATM IV (call+put avg), put/call volume ratio, OI skew.
    """
    try:
        exps = ticker.options
    except Exception:
        return None
    if not exps:
        return None

    today = datetime.now().date()
    selected_exps = []
    for e in exps:
        try:
            d = datetime.strptime(e, '%Y-%m-%d').date()
        except Exception:
            continue
        dte = (d - today).days
        if min_dte <= dte <= max_dte:
            selected_exps.append((e, dte))
    if not selected_exps:
        return None

    atm_ivs = []
    total_call_vol = 0
    total_put_vol = 0
    total_call_oi = 0
    total_put_oi = 0

    for exp, dte in selected_exps[:4]:  # cap at 4 expirations to keep latency bounded
        try:
            chain = ticker.option_chain(exp)
        except Exception:
            continue
        calls = chain.calls
        puts = chain.puts
        if calls is None or calls.empty or puts is None or puts.empty:
            continue

        # ATM strike = closest to current price
        try:
            atm_call = calls.iloc[(calls['strike'] - current_price).abs().argsort()[:1]]
            atm_put = puts.iloc[(puts['strike'] - current_price).abs().argsort()[:1]]
            iv_c = safe_float(atm_call['impliedVolatility'].iloc[0])
            iv_p = safe_float(atm_put['impliedVolatility'].iloc[0])
            # yfinance occasionally returns absurd IVs (>5.0 = 500%) for thin contracts
            if 0.05 < iv_c < 3.0:
                atm_ivs.append(iv_c)
            if 0.05 < iv_p < 3.0:
                atm_ivs.append(iv_p)
        except Exception:
            pass

        total_call_vol += int(calls['volume'].fillna(0).sum())
        total_put_vol += int(puts['volume'].fillna(0).sum())
        total_call_oi += int(calls['openInterest'].fillna(0).sum())
        total_put_oi += int(puts['openInterest'].fillna(0).sum())

    if not atm_ivs:
        return None

    atm_iv = float(np.mean(atm_ivs))
    pc_vol_ratio = total_put_vol / total_call_vol if total_call_vol > 0 else None
    pc_oi_ratio = total_put_oi / total_call_oi if total_call_oi > 0 else None

    return {
        'atm_iv': atm_iv,
        'put_call_volume_ratio': pc_vol_ratio,
        'put_call_oi_ratio': pc_oi_ratio,
        'total_call_volume': total_call_vol,
        'total_put_volume': total_put_vol,
        'expirations_used': len(selected_exps[:4]),
    }


def score_options_positioning(symbol, current_price, df=None, ticker_obj=None):
    """
    Score options-derived positioning. Returns (adjustment_pts, signals, info).
    Adjustment in [-12, +12]. info=None if options data unavailable.
    """
    import yfinance as yf
    if ticker_obj is None:
        ticker_obj = yf.Ticker(symbol)

    if not current_price or current_price <= 0:
        return 0, [], None

    chain_data = _aggregate_chain(ticker_obj, current_price)
    if chain_data is None:
        return 0, [], None

    signals = []
    adj = 0.0
    rv = _realized_vol_20d(df) if df is not None else None
    chain_data['realized_vol_20d'] = round(rv, 4) if rv else None

    # --- IV vs RV (option richness) ---
    # If implied vol is much higher than realized, the market is pricing in
    # stress that hasn't materialized. Either bearish setup priced in, or
    # an event coming. If much lower, options are cheap (complacency).
    iv = chain_data['atm_iv']
    if rv and rv > 0:
        iv_rv_ratio = iv / rv
        chain_data['iv_rv_ratio'] = round(iv_rv_ratio, 2)
        if iv_rv_ratio > 2.0:
            adj -= 6
            signals.append(f'ATM IV {iv*100:.0f}% vs 20d RV {rv*100:.0f}% — options pricing in stress (ratio {iv_rv_ratio:.1f}x)')
        elif iv_rv_ratio > 1.5:
            adj -= 3
            signals.append(f'IV {iv_rv_ratio:.1f}x realized — options elevated, caution priced in')
        elif iv_rv_ratio < 0.7:
            adj += 4
            signals.append(f'IV {iv_rv_ratio:.1f}x realized — options cheap, complacency or coiled spring')
        elif iv_rv_ratio < 0.9:
            adj += 2

    # --- Put/Call volume ratio (today's flow) ---
    # >1.2 typically bearish positioning, <0.6 bullish, ~0.7-1.0 normal
    pc_vol = chain_data.get('put_call_volume_ratio')
    if pc_vol is not None:
        if pc_vol > 1.5:
            # Extreme — often a contrarian bullish indicator (too many puts = capitulation)
            adj += 4
            signals.append(f'P/C volume {pc_vol:.2f} — extreme put buying, contrarian bullish')
        elif pc_vol > 1.2:
            adj -= 4
            signals.append(f'P/C volume {pc_vol:.2f} — bearish flow')
        elif pc_vol < 0.5:
            adj += 4
            signals.append(f'P/C volume {pc_vol:.2f} — heavy call buying, bullish flow')
        elif pc_vol < 0.7:
            adj += 2
            signals.append(f'P/C volume {pc_vol:.2f} — call-heavy flow')

    # --- Put/Call OI ratio (positioning, slower-moving) ---
    pc_oi = chain_data.get('put_call_oi_ratio')
    if pc_oi is not None:
        if pc_oi > 1.5:
            adj -= 2
            signals.append(f'P/C OI {pc_oi:.2f} — sustained bearish positioning')
        elif pc_oi < 0.5:
            adj += 2
            signals.append(f'P/C OI {pc_oi:.2f} — sustained bullish positioning')

    # Clamp
    adj = max(-12, min(12, round(adj)))
    return adj, signals, chain_data


if __name__ == '__main__':
    import sys
    import yfinance as yf
    sym = sys.argv[1] if len(sys.argv) > 1 else 'AAPL'
    t = yf.Ticker(sym)
    px = float(t.fast_info.last_price)
    adj, sigs, info = score_options_positioning(sym, px, ticker_obj=t)
    print(f'\n{sym} @ ${px:.2f}:  adjustment {adj:+d}')
    for s in sigs:
        print(f'  • {s}')
    print(f'\nDiagnostics: {info}')
