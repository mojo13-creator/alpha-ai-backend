# analysis/backtest_validator.py
"""
Backtest Validator — measures whether past signals actually predicted price moves.

For every row in analysis_history older than min_days_old, looks up the realized
price at T+5 / T+10 / T+30 trading days and scores the prediction. Reports:

  - Hit rate by signal (BUY, STRONG_BUY, SELL, etc.) and by confidence tier
  - Information Coefficient (Spearman rank correlation) for each sub-score
    vs realized return — tells you which sub-score actually has predictive value
  - Average realized return by signal — calibration check
  - Best/worst calls

Run:
    python -m analysis.backtest_validator
    python -m analysis.backtest_validator --horizon 10 --min-days 10

Or import:
    from analysis.backtest_validator import validate_signals
    report = validate_signals(db_manager)
"""

import argparse
import math
import sys
from collections import defaultdict
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import yfinance as yf


# Signals that make a directional claim. HOLD is excluded — no claim, no score.
BULLISH_SIGNALS = {'BUY', 'STRONG_BUY'}
BEARISH_SIGNALS = {'SELL', 'STRONG_SELL', 'SHORT'}
DIRECTIONAL_SIGNALS = BULLISH_SIGNALS | BEARISH_SIGNALS

# Minimum return magnitude to count as a "hit" — anything inside the band
# is treated as flat (no win, no loss) to avoid noise dominating the signal.
HIT_THRESHOLD_PCT = 1.0

# Sub-score columns whose predictive value we want to measure.
SUBSCORE_COLS = ['composite_score', 'technical_score', 'fundamental_score',
                 'sentiment_score', 'ai_insight_score']


def _fetch_price_window(ticker, start, end):
    """Fetch daily closes from yfinance for a single ticker. Returns DataFrame indexed by date."""
    try:
        df = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=True)
        if df is None or df.empty:
            return None
        df.index = df.index.tz_localize(None) if df.index.tz else df.index
        return df
    except Exception as e:
        print(f"  ⚠️  yfinance fetch failed for {ticker}: {e}", file=sys.stderr)
        return None


def _realized_return(price_df, signal_date, horizon_days):
    """
    Return the close-to-close % return from signal_date to signal_date + horizon (trading days).
    Returns None if we can't find both points.
    """
    if price_df is None or price_df.empty:
        return None

    # Find the first trading day on or after signal_date (entry)
    entries = price_df.index[price_df.index >= signal_date]
    if len(entries) == 0:
        return None
    entry_date = entries[0]
    entry_price = float(price_df.loc[entry_date, 'Close'])
    if entry_price <= 0:
        return None

    # Find the close `horizon_days` trading days later
    entry_pos = price_df.index.get_loc(entry_date)
    exit_pos = entry_pos + horizon_days
    if exit_pos >= len(price_df):
        return None  # not enough future data yet
    exit_price = float(price_df.iloc[exit_pos]['Close'])
    if exit_price <= 0:
        return None

    return (exit_price - entry_price) / entry_price * 100


def _score_prediction(signal, realized_pct):
    """
    Returns 'hit', 'miss', or 'flat' based on whether the signal's direction
    matched the realized return beyond the noise threshold.
    """
    if abs(realized_pct) < HIT_THRESHOLD_PCT:
        return 'flat'
    if signal in BULLISH_SIGNALS:
        return 'hit' if realized_pct > 0 else 'miss'
    if signal in BEARISH_SIGNALS:
        return 'hit' if realized_pct < 0 else 'miss'
    return 'flat'


def _spearman_ic(scores, returns):
    """
    Spearman rank correlation between sub-scores and realized returns.
    This is the Information Coefficient — the standard quant metric for
    sub-score predictive value. Range -1 to +1; >0.05 is meaningful, >0.10 is strong.
    """
    if len(scores) < 10:
        return None
    s = pd.Series(scores).rank()
    r = pd.Series(returns).rank()
    if s.std() == 0 or r.std() == 0:
        return None
    return float(s.corr(r))


def validate_signals(db_manager, horizons=(5, 10, 30), min_days_old=5,
                      lookback_days=180, verbose=True):
    """
    Run validation across all analysis_history rows.
    Returns a dict report.
    """
    conn = db_manager.get_connection()
    cutoff = datetime.now() - timedelta(days=min_days_old)
    lookback_start = datetime.now() - timedelta(days=lookback_days)

    query = """
        SELECT id, ticker, timestamp, composite_score, technical_score,
               fundamental_score, sentiment_score, ai_insight_score,
               signal, confidence, risk_level, entry_price,
               market_cap_category,
               realized_return_5d, realized_return_10d, realized_return_30d
        FROM analysis_history
        WHERE timestamp <= %s AND timestamp >= %s
        ORDER BY timestamp ASC
    """
    # Adapt placeholder for sqlite vs postgres
    from database.db_manager import DB_TYPE
    if DB_TYPE != 'postgres':
        query = query.replace('%s', '?')

    history = pd.read_sql_query(query, conn, params=(cutoff, lookback_start),
                                 parse_dates=['timestamp'])
    conn.close()

    if history.empty:
        return {'error': 'No analysis_history rows in the validation window',
                'cutoff': cutoff.isoformat(), 'lookback_start': lookback_start.isoformat()}

    if verbose:
        print(f"\n{'='*60}")
        print(f"  BACKTEST VALIDATION")
        print(f"{'='*60}")
        print(f"Window: {lookback_start.date()} → {cutoff.date()}")
        print(f"Total analyses: {len(history)}")
        print(f"Tickers: {history['ticker'].nunique()}")

    # Fetch price history for each unique ticker once
    tickers = history['ticker'].unique()
    earliest = history['timestamp'].min()
    fetch_start = (earliest - timedelta(days=10)).date()
    fetch_end = (datetime.now() + timedelta(days=1)).date()

    if verbose:
        print(f"\nFetching price data for {len(tickers)} tickers...")

    price_cache = {}
    for i, t in enumerate(tickers):
        if verbose and i % 10 == 0:
            print(f"  {i}/{len(tickers)} fetched...")
        price_cache[t] = _fetch_price_window(t, fetch_start, fetch_end)

    # Build outcome rows: one per (analysis, horizon).
    # Use cached realized returns when present; compute + persist when missing.
    HORIZON_COL = {5: 'realized_return_5d', 10: 'realized_return_10d', 30: 'realized_return_30d'}
    outcomes = []
    persisted = 0
    for _, row in history.iterrows():
        ticker = row['ticker']
        signal = row['signal']
        ts = row['timestamp']
        analysis_id = row.get('id')
        price_df = price_cache.get(ticker)

        # Compute (or reuse cached) returns at each horizon
        per_horizon = {}
        for h in horizons:
            cached = row.get(HORIZON_COL.get(h)) if h in HORIZON_COL else None
            if cached is not None and not (isinstance(cached, float) and math.isnan(cached)):
                per_horizon[h] = float(cached)
            elif price_df is not None and not price_df.empty:
                ret = _realized_return(price_df, pd.Timestamp(ts).normalize(), h)
                if ret is not None:
                    per_horizon[h] = ret

        # Persist any newly-computed returns (only for horizons in HORIZON_COL)
        if analysis_id is not None:
            new_5 = per_horizon.get(5) if pd.isna(row.get('realized_return_5d')) else None
            new_10 = per_horizon.get(10) if pd.isna(row.get('realized_return_10d')) else None
            new_30 = per_horizon.get(30) if pd.isna(row.get('realized_return_30d')) else None
            if any(v is not None for v in (new_5, new_10, new_30)):
                # Preserve existing values for horizons we didn't refresh
                final_5 = new_5 if new_5 is not None else (None if pd.isna(row.get('realized_return_5d')) else float(row.get('realized_return_5d')))
                final_10 = new_10 if new_10 is not None else (None if pd.isna(row.get('realized_return_10d')) else float(row.get('realized_return_10d')))
                final_30 = new_30 if new_30 is not None else (None if pd.isna(row.get('realized_return_30d')) else float(row.get('realized_return_30d')))
                if db_manager.update_analysis_realized_returns(int(analysis_id), final_5, final_10, final_30):
                    persisted += 1

        for h, ret in per_horizon.items():
            result = _score_prediction(signal, ret)
            outcomes.append({
                'ticker': ticker,
                'timestamp': ts,
                'horizon': h,
                'signal': signal,
                'confidence': row.get('confidence', ''),
                'market_cap_category': row.get('market_cap_category', ''),
                'realized_pct': ret,
                'result': result,
                'composite_score': row.get('composite_score'),
                'technical_score': row.get('technical_score'),
                'fundamental_score': row.get('fundamental_score'),
                'sentiment_score': row.get('sentiment_score'),
                'ai_insight_score': row.get('ai_insight_score'),
            })

    if verbose and persisted:
        print(f"  Persisted realized returns for {persisted} rows")

    if not outcomes:
        return {'error': 'No outcomes could be computed (price data missing or insufficient horizon)'}

    out_df = pd.DataFrame(outcomes)
    report = {
        'window': {'start': lookback_start.isoformat(), 'end': cutoff.isoformat()},
        'total_analyses': int(len(history)),
        'total_outcomes': int(len(out_df)),
        'horizons_days': list(horizons),
        'hit_threshold_pct': HIT_THRESHOLD_PCT,
        'by_horizon': {},
    }

    for h in horizons:
        sub = out_df[out_df['horizon'] == h]
        if sub.empty:
            continue

        directional = sub[sub['signal'].isin(DIRECTIONAL_SIGNALS)]
        h_report = {
            'total': int(len(sub)),
            'directional_calls': int(len(directional)),
            'mean_realized_pct': round(float(sub['realized_pct'].mean()), 3),
            'by_signal': {},
            'by_confidence': {},
            'by_market_cap': {},
            'information_coefficient': {},
        }

        # Hit rate by signal
        for sig in sorted(sub['signal'].unique()):
            s = sub[sub['signal'] == sig]
            hits = int((s['result'] == 'hit').sum())
            misses = int((s['result'] == 'miss').sum())
            flats = int((s['result'] == 'flat').sum())
            decided = hits + misses
            h_report['by_signal'][sig] = {
                'count': int(len(s)),
                'hits': hits, 'misses': misses, 'flats': flats,
                'hit_rate': round(hits / decided * 100, 1) if decided else None,
                'mean_return_pct': round(float(s['realized_pct'].mean()), 3),
            }

        # Hit rate by confidence (only directional calls)
        for conf in sorted(directional['confidence'].dropna().unique()):
            s = directional[directional['confidence'] == conf]
            hits = int((s['result'] == 'hit').sum())
            misses = int((s['result'] == 'miss').sum())
            decided = hits + misses
            h_report['by_confidence'][conf] = {
                'count': int(len(s)),
                'hits': hits, 'misses': misses,
                'hit_rate': round(hits / decided * 100, 1) if decided else None,
                'mean_return_pct': round(float(s['realized_pct'].mean()), 3),
            }

        # Hit rate by market cap
        for cap in sorted(directional['market_cap_category'].dropna().unique()):
            s = directional[directional['market_cap_category'] == cap]
            hits = int((s['result'] == 'hit').sum())
            misses = int((s['result'] == 'miss').sum())
            decided = hits + misses
            h_report['by_market_cap'][str(cap)] = {
                'count': int(len(s)),
                'hits': hits, 'misses': misses,
                'hit_rate': round(hits / decided * 100, 1) if decided else None,
            }

        # Information Coefficient — Spearman rank correlation per sub-score.
        # Sign convention: bullish signals expect positive return, so we measure
        # IC across ALL outcomes (not just directional) — the score itself encodes
        # direction. A higher score should correlate with higher return.
        for col in SUBSCORE_COLS:
            valid = sub[[col, 'realized_pct']].dropna()
            if len(valid) >= 10:
                ic = _spearman_ic(valid[col].values, valid['realized_pct'].values)
                if ic is not None:
                    h_report['information_coefficient'][col] = round(ic, 4)

        report['by_horizon'][h] = h_report

    # Best / worst calls (only directional, only if we have data)
    directional_all = out_df[out_df['signal'].isin(DIRECTIONAL_SIGNALS)].copy()
    if not directional_all.empty:
        # "edge" = realized return aligned with signal direction
        directional_all['edge'] = directional_all.apply(
            lambda r: r['realized_pct'] if r['signal'] in BULLISH_SIGNALS else -r['realized_pct'],
            axis=1
        )
        best = directional_all.nlargest(5, 'edge')[
            ['ticker', 'timestamp', 'signal', 'horizon', 'realized_pct', 'edge']
        ]
        worst = directional_all.nsmallest(5, 'edge')[
            ['ticker', 'timestamp', 'signal', 'horizon', 'realized_pct', 'edge']
        ]
        report['best_calls'] = best.to_dict(orient='records')
        report['worst_calls'] = worst.to_dict(orient='records')

    return report


def print_report(report):
    """Pretty-print a validation report to stdout."""
    if 'error' in report:
        print(f"\n❌ {report['error']}")
        return

    print(f"\n{'='*60}")
    print(f"  VALIDATION REPORT")
    print(f"{'='*60}")
    print(f"Analyses scored:  {report['total_analyses']}")
    print(f"Outcomes computed: {report['total_outcomes']}")
    print(f"Hit threshold:    ±{report['hit_threshold_pct']}%")

    for h, hr in report['by_horizon'].items():
        print(f"\n--- Horizon: {h} trading days ---")
        print(f"  Mean realized return across all signals: {hr['mean_realized_pct']:+.2f}%")
        print(f"  Directional calls: {hr['directional_calls']}")

        if hr['by_signal']:
            print(f"\n  By signal:")
            print(f"    {'Signal':<14} {'Count':>6} {'Hit%':>7} {'Hits':>5} {'Miss':>5} {'Flat':>5} {'AvgRet%':>9}")
            for sig, s in hr['by_signal'].items():
                hr_str = f"{s['hit_rate']}" if s['hit_rate'] is not None else 'n/a'
                print(f"    {sig:<14} {s['count']:>6} {hr_str:>7} {s['hits']:>5} {s['misses']:>5} {s['flats']:>5} {s['mean_return_pct']:>+9.2f}")

        if hr['by_confidence']:
            print(f"\n  By confidence (directional only):")
            for conf, s in hr['by_confidence'].items():
                hr_str = f"{s['hit_rate']}%" if s['hit_rate'] is not None else 'n/a'
                print(f"    {conf:<10} {s['count']:>4} calls  hit_rate={hr_str:<6}  avg_ret={s['mean_return_pct']:+.2f}%")

        if hr['information_coefficient']:
            print(f"\n  Information Coefficient (Spearman rank corr — predictive power):")
            print(f"    >0.05 meaningful   >0.10 strong   <0 inverse (broken)")
            for col, ic in sorted(hr['information_coefficient'].items(), key=lambda x: -abs(x[1])):
                marker = ''
                if ic > 0.10:
                    marker = '  ✅ strong'
                elif ic > 0.05:
                    marker = '  ✅'
                elif ic < -0.05:
                    marker = '  ⚠️  inverse'
                print(f"    {col:<22} {ic:+.4f}{marker}")

    if report.get('best_calls'):
        print(f"\n--- Best 5 calls ---")
        for c in report['best_calls']:
            print(f"  {c['ticker']:<6} {c['signal']:<12} h={c['horizon']:>2}d  realized={c['realized_pct']:+.2f}%  edge={c['edge']:+.2f}%")

    if report.get('worst_calls'):
        print(f"\n--- Worst 5 calls ---")
        for c in report['worst_calls']:
            print(f"  {c['ticker']:<6} {c['signal']:<12} h={c['horizon']:>2}d  realized={c['realized_pct']:+.2f}%  edge={c['edge']:+.2f}%")

    print()


def main():
    parser = argparse.ArgumentParser(description='Backtest validator for Alpha AI signals')
    parser.add_argument('--horizons', type=int, nargs='+', default=[5, 10, 30],
                        help='Trading-day horizons to score (default: 5 10 30)')
    parser.add_argument('--min-days', type=int, default=5,
                        help='Only score signals at least this many days old (default: 5)')
    parser.add_argument('--lookback', type=int, default=180,
                        help='How far back to pull signals (default: 180 days)')
    parser.add_argument('--json', action='store_true', help='Print full JSON report')
    args = parser.parse_args()

    from database.db_manager import DatabaseManager
    db = DatabaseManager()
    report = validate_signals(db, horizons=tuple(args.horizons),
                               min_days_old=args.min_days,
                               lookback_days=args.lookback)

    if args.json:
        import json
        # Pandas timestamps aren't JSON-serializable directly
        def _default(o):
            if hasattr(o, 'isoformat'):
                return o.isoformat()
            if isinstance(o, np.integer):
                return int(o)
            if isinstance(o, np.floating):
                return float(o)
            return str(o)
        print(json.dumps(report, indent=2, default=_default))
    else:
        print_report(report)


if __name__ == '__main__':
    main()
