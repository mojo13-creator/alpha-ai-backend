# analysis/calibration.py
"""
Calibration metrics for Alpha AI signals.

Backtest tells us hit rate; calibration tells us whether *stated* confidence
matches *realized* hit rate. A model that says "85% confident" should be right
~85% of the time. If it's right 60%, the model is over-confident and any
position-sizing rule built on confidence is leaking edge.

Metrics:
  - Brier score: mean squared error between P(correct) and actual outcome.
    Range [0, 1]; lower is better. 0.25 = always-50% baseline.
  - Reliability table: bins of stated probability vs realized hit rate.
    The diagonal (stated == realized) is perfect calibration.
  - ECE (Expected Calibration Error): weighted mean gap between stated and
    realized across bins. Single-number summary of the reliability table.

Probability model:
  composite_score is treated as the model's stated probability that the
  *direction* is correct. For bullish signals (BUY/STRONG_BUY): P = score/100.
  For bearish (SELL/STRONG_SELL/SHORT): P = (100 - score)/100. HOLD is excluded.

Usage:
    from analysis.calibration import calibration_report
    report = calibration_report(db_manager, horizon=10)
"""

from collections import defaultdict
from datetime import datetime, timedelta

import numpy as np
import pandas as pd


BULLISH_SIGNALS = {'BUY', 'STRONG_BUY'}
BEARISH_SIGNALS = {'SELL', 'STRONG_SELL', 'SHORT'}
DIRECTIONAL_SIGNALS = BULLISH_SIGNALS | BEARISH_SIGNALS

HIT_THRESHOLD_PCT = 1.0  # match backtest_validator
HORIZON_COL = {5: 'realized_return_5d', 10: 'realized_return_10d', 30: 'realized_return_30d'}


def _stated_probability(signal, composite_score):
    """Map (signal, composite_score) -> stated P(direction correct), or None."""
    if composite_score is None or pd.isna(composite_score):
        return None
    s = float(composite_score) / 100.0
    s = max(0.0, min(1.0, s))
    if signal in BULLISH_SIGNALS:
        return s
    if signal in BEARISH_SIGNALS:
        return 1.0 - s
    return None


def _outcome(signal, realized_pct):
    """Return 1 if direction was correct, 0 if wrong, None if flat (no decision)."""
    if realized_pct is None or pd.isna(realized_pct):
        return None
    if abs(realized_pct) < HIT_THRESHOLD_PCT:
        return None
    if signal in BULLISH_SIGNALS:
        return 1 if realized_pct > 0 else 0
    if signal in BEARISH_SIGNALS:
        return 1 if realized_pct < 0 else 0
    return None


def _brier(probs, outcomes):
    if not probs:
        return None
    p = np.asarray(probs, dtype=float)
    y = np.asarray(outcomes, dtype=float)
    return float(np.mean((p - y) ** 2))


def _reliability_table(probs, outcomes, n_bins=10):
    """
    Bin predicted probabilities into n_bins equal-width buckets [0, 1].
    For each bin, return mean stated P, mean realized hit rate, and count.
    """
    if not probs:
        return []
    p = np.asarray(probs, dtype=float)
    y = np.asarray(outcomes, dtype=float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    table = []
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        # Last bin is inclusive on the right
        if i == n_bins - 1:
            mask = (p >= lo) & (p <= hi)
        else:
            mask = (p >= lo) & (p < hi)
        n = int(mask.sum())
        if n == 0:
            continue
        table.append({
            'bin_low': round(float(lo), 2),
            'bin_high': round(float(hi), 2),
            'count': n,
            'mean_predicted': round(float(p[mask].mean()), 4),
            'mean_realized': round(float(y[mask].mean()), 4),
            'gap': round(float(p[mask].mean() - y[mask].mean()), 4),
        })
    return table


def _ece(reliability):
    """Expected Calibration Error: weighted mean |gap| across bins."""
    if not reliability:
        return None
    total = sum(b['count'] for b in reliability)
    if total == 0:
        return None
    return round(sum(b['count'] * abs(b['gap']) for b in reliability) / total, 4)


def calibration_report(db_manager, horizon=10, lookback_days=180, n_bins=10):
    """
    Compute calibration metrics from analysis_history.

    Args:
        db_manager: DatabaseManager instance
        horizon: 5, 10, or 30 (trading-day horizon for realized returns)
        lookback_days: max age of analyses to include
        n_bins: number of reliability bins

    Returns:
        dict with brier, ece, reliability table, per-signal breakdown,
        and per-model-confidence breakdown.
    """
    if horizon not in HORIZON_COL:
        return {'error': f'horizon must be one of {list(HORIZON_COL)}'}

    col = HORIZON_COL[horizon]
    cutoff = datetime.now() - timedelta(days=lookback_days)

    conn = db_manager.get_connection()
    from database.db_manager import DB_TYPE
    placeholder = '%s' if DB_TYPE == 'postgres' else '?'
    query = f"""
        SELECT signal, confidence, composite_score, {col} AS realized_pct
        FROM analysis_history
        WHERE timestamp >= {placeholder}
          AND signal IS NOT NULL
          AND {col} IS NOT NULL
    """
    df = pd.read_sql_query(query, conn, params=(cutoff,))
    conn.close()

    if df.empty:
        return {
            'error': 'No filled realized returns yet. Run backtest_validator to populate, then retry.',
            'horizon_days': horizon,
            'lookback_start': cutoff.isoformat(),
        }

    # Filter to directional rows with valid outcomes
    df = df[df['signal'].isin(DIRECTIONAL_SIGNALS)].copy()
    df['outcome'] = df.apply(lambda r: _outcome(r['signal'], r['realized_pct']), axis=1)
    df['p_stated'] = df.apply(lambda r: _stated_probability(r['signal'], r['composite_score']), axis=1)
    df = df.dropna(subset=['outcome', 'p_stated'])

    if df.empty:
        return {
            'error': 'No directional decisions in window (all flat or missing scores).',
            'horizon_days': horizon,
        }

    probs = df['p_stated'].tolist()
    outs = df['outcome'].tolist()

    reliability = _reliability_table(probs, outs, n_bins=n_bins)

    report = {
        'horizon_days': horizon,
        'lookback_days': lookback_days,
        'sample_size': int(len(df)),
        'brier_score': round(_brier(probs, outs), 4),
        'brier_baseline_50_50': 0.25,
        'ece': _ece(reliability),
        'overall_hit_rate': round(float(np.mean(outs)), 4),
        'mean_stated_probability': round(float(np.mean(probs)), 4),
        'reliability_bins': reliability,
        'by_signal': {},
        'by_confidence': {},
    }

    for sig in sorted(df['signal'].unique()):
        s = df[df['signal'] == sig]
        report['by_signal'][sig] = {
            'count': int(len(s)),
            'hit_rate': round(float(s['outcome'].mean()), 4),
            'mean_stated_p': round(float(s['p_stated'].mean()), 4),
            'brier': round(_brier(s['p_stated'].tolist(), s['outcome'].tolist()), 4),
        }

    for conf in sorted(df['confidence'].dropna().unique()):
        s = df[df['confidence'] == conf]
        if len(s) < 5:
            continue
        report['by_confidence'][str(conf)] = {
            'count': int(len(s)),
            'hit_rate': round(float(s['outcome'].mean()), 4),
            'mean_stated_p': round(float(s['p_stated'].mean()), 4),
            'brier': round(_brier(s['p_stated'].tolist(), s['outcome'].tolist()), 4),
        }

    return report


def print_calibration(report):
    if 'error' in report:
        print(f"\n❌ {report['error']}")
        return
    print(f"\n{'='*60}")
    print(f"  CALIBRATION REPORT — {report['horizon_days']}d horizon")
    print(f"{'='*60}")
    print(f"Sample size:       {report['sample_size']}")
    print(f"Brier score:       {report['brier_score']}  (lower is better; 0.25 = coin flip)")
    print(f"ECE:               {report['ece']}  (lower is better; 0 = perfectly calibrated)")
    print(f"Overall hit rate:  {report['overall_hit_rate']:.1%}")
    print(f"Mean stated P:     {report['mean_stated_probability']:.1%}")
    gap = report['mean_stated_probability'] - report['overall_hit_rate']
    if abs(gap) > 0.05:
        direction = 'OVER' if gap > 0 else 'UNDER'
        print(f"  ⚠️  Model is {direction}-confident by {abs(gap):.1%}")

    print(f"\nReliability table:")
    print(f"  {'bin':<14} {'count':>6} {'predicted':>10} {'realized':>10} {'gap':>8}")
    for b in report['reliability_bins']:
        marker = '  ⚠️' if abs(b['gap']) > 0.10 else ''
        print(f"  [{b['bin_low']:.2f}-{b['bin_high']:.2f}]   {b['count']:>6} {b['mean_predicted']:>10.3f} {b['mean_realized']:>10.3f} {b['gap']:>+8.3f}{marker}")

    if report['by_confidence']:
        print(f"\nBy stated confidence tier:")
        for conf, s in report['by_confidence'].items():
            print(f"  {conf:<12} n={s['count']:>4}  hit_rate={s['hit_rate']:.1%}  stated={s['mean_stated_p']:.1%}  brier={s['brier']}")

    print()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Calibration report for Alpha AI signals')
    parser.add_argument('--horizon', type=int, default=10, choices=[5, 10, 30])
    parser.add_argument('--lookback', type=int, default=180)
    parser.add_argument('--bins', type=int, default=10)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()

    from database.db_manager import DatabaseManager
    db = DatabaseManager()
    rep = calibration_report(db, horizon=args.horizon, lookback_days=args.lookback, n_bins=args.bins)
    if args.json:
        import json
        print(json.dumps(rep, indent=2, default=str))
    else:
        print_calibration(rep)
