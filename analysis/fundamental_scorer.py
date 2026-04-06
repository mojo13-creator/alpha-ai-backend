# analysis/fundamental_scorer.py
"""
Programmatic Fundamental Score Calculator (0-100)
Uses yfinance data for P/E, revenue growth, earnings, debt, FCF, insider activity.
Adjusts weights based on market cap category.
"""

import math
import yfinance as yf


def safe_float(val, default=0.0):
    try:
        v = float(val)
        return default if math.isnan(v) or math.isinf(v) else v
    except Exception:
        return default


def classify_market_cap(market_cap):
    """Return market cap category and human-readable label."""
    if market_cap is None or market_cap <= 0:
        return 'unknown', 'Unknown'
    if market_cap < 300_000_000:
        return 'micro', 'Micro Cap'
    if market_cap < 2_000_000_000:
        return 'small', 'Small Cap'
    if market_cap < 10_000_000_000:
        return 'midcap', 'Mid Cap'
    if market_cap < 200_000_000_000:
        return 'large', 'Large Cap'
    return 'mega', 'Mega Cap'


def calculate_fundamental_score(symbol):
    """
    Calculate fundamental score (0-100) from yfinance data.
    Returns dict with score, key metrics, key_signals, and market_cap info.
    """
    signals = []
    score = 50.0

    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
    except Exception as e:
        return {
            'score': 50,
            'pe_vs_sector': 'N/A',
            'revenue_growth': 'N/A',
            'earnings_surprise': 'N/A',
            'key_signals': [f'Could not fetch fundamental data: {e}'],
            'market_cap': 0,
            'market_cap_category': 'unknown',
            'market_cap_label': 'Unknown',
        }

    if not info or info.get('quoteType') == 'ETF':
        # ETFs: score based on available metrics
        return _score_etf(info, signals)

    market_cap = safe_float(info.get('marketCap', 0))
    cap_cat, cap_label = classify_market_cap(market_cap)

    # ===== P/E Ratio =====
    forward_pe = safe_float(info.get('forwardPE', 0))
    trailing_pe = safe_float(info.get('trailingPE', 0))
    sector_pe = safe_float(info.get('sectorPe', 0))  # may not exist
    pe_used = forward_pe if forward_pe > 0 else trailing_pe
    pe_label = 'N/A'

    if pe_used > 0:
        if pe_used < 10:
            score += 12
            pe_label = f'{pe_used:.1f} (very low — value territory)'
            signals.append(f'P/E {pe_used:.1f} — deep value')
        elif pe_used < 18:
            score += 8
            pe_label = f'{pe_used:.1f} (reasonable)'
            signals.append(f'P/E {pe_used:.1f} — fair value')
        elif pe_used < 30:
            score += 2
            pe_label = f'{pe_used:.1f} (moderate)'
        elif pe_used < 50:
            score -= 5
            pe_label = f'{pe_used:.1f} (elevated)'
            signals.append(f'P/E {pe_used:.1f} — premium valuation')
        elif pe_used < 80:
            score -= 10
            pe_label = f'{pe_used:.1f} (high)'
            signals.append(f'P/E {pe_used:.1f} — expensive')
        else:
            score -= 15
            pe_label = f'{pe_used:.1f} (extreme)'
            signals.append(f'P/E {pe_used:.1f} — extremely overvalued')
    elif trailing_pe < 0:
        score -= 10
        pe_label = 'Negative (unprofitable)'
        signals.append('Negative earnings — company is unprofitable')

    # ===== Revenue Growth =====
    rev_growth = safe_float(info.get('revenueGrowth', 0))
    rev_label = 'N/A'
    if rev_growth != 0:
        rev_pct = rev_growth * 100
        rev_label = f'{rev_pct:+.1f}% YoY'
        if rev_pct > 30:
            score += 15
            signals.append(f'Revenue growth {rev_pct:.0f}% — hyper growth')
        elif rev_pct > 15:
            score += 10
            signals.append(f'Revenue growth {rev_pct:.0f}% — strong growth')
        elif rev_pct > 5:
            score += 5
            signals.append(f'Revenue growth {rev_pct:.0f}%')
        elif rev_pct > 0:
            score += 2
        elif rev_pct > -5:
            score -= 3
        elif rev_pct > -15:
            score -= 8
            signals.append(f'Revenue declining {rev_pct:.0f}%')
        else:
            score -= 15
            signals.append(f'Revenue collapsing {rev_pct:.0f}%')

    # Weight growth higher for small/midcap
    if cap_cat in ('micro', 'small', 'midcap') and rev_growth > 0.15:
        score += 5
        signals.append('High growth company in growth-favored cap range')

    # ===== Earnings Surprise =====
    earnings_label = 'N/A'
    try:
        earnings_dates = ticker.earnings_dates
        if earnings_dates is not None and not earnings_dates.empty:
            # Find most recent past earnings
            past = earnings_dates.dropna(subset=['Reported EPS'])
            if not past.empty:
                latest_row = past.iloc[0]
                reported = safe_float(latest_row.get('Reported EPS', 0))
                estimated = safe_float(latest_row.get('EPS Estimate', 0))
                if estimated != 0:
                    surprise_pct = ((reported - estimated) / abs(estimated)) * 100
                    earnings_label = f'{surprise_pct:+.1f}% last quarter'
                    if surprise_pct > 15:
                        score += 12
                        signals.append(f'Earnings beat by {surprise_pct:.0f}% — strong surprise')
                    elif surprise_pct > 5:
                        score += 7
                        signals.append(f'Earnings beat by {surprise_pct:.0f}%')
                    elif surprise_pct > 0:
                        score += 3
                    elif surprise_pct > -5:
                        score -= 3
                    elif surprise_pct > -15:
                        score -= 7
                        signals.append(f'Earnings miss by {abs(surprise_pct):.0f}%')
                    else:
                        score -= 12
                        signals.append(f'Earnings miss by {abs(surprise_pct):.0f}% — big miss')
    except Exception:
        pass

    # ===== Debt-to-Equity =====
    de_ratio = safe_float(info.get('debtToEquity', 0))
    if de_ratio > 0:
        de_ratio_pct = de_ratio  # yfinance returns as percentage already
        if de_ratio_pct < 30:
            score += 8
            signals.append(f'Low debt (D/E {de_ratio_pct:.0f}%) — strong balance sheet')
        elif de_ratio_pct < 80:
            score += 4
        elif de_ratio_pct < 150:
            score -= 3
        elif de_ratio_pct < 300:
            score -= 8
            signals.append(f'High debt (D/E {de_ratio_pct:.0f}%)')
        else:
            score -= 15
            signals.append(f'Extreme debt (D/E {de_ratio_pct:.0f}%) — financial risk')

    # ===== Free Cash Flow =====
    fcf = safe_float(info.get('freeCashflow', 0))
    if fcf != 0:
        if market_cap > 0:
            fcf_yield = (fcf / market_cap) * 100
            if fcf_yield > 8:
                score += 10
                signals.append(f'Strong FCF yield {fcf_yield:.1f}%')
            elif fcf_yield > 4:
                score += 6
                signals.append(f'Healthy FCF yield {fcf_yield:.1f}%')
            elif fcf_yield > 0:
                score += 2
            elif fcf_yield < -3:
                score -= 8
                signals.append(f'Negative FCF yield {fcf_yield:.1f}% — cash burn')
        elif fcf > 0:
            score += 3
        else:
            score -= 5
            signals.append('Negative free cash flow')

    # ===== Profit Margins =====
    margin = safe_float(info.get('profitMargins', 0))
    if margin != 0:
        margin_pct = margin * 100
        if margin_pct > 25:
            score += 8
            signals.append(f'Excellent profit margin {margin_pct:.0f}%')
        elif margin_pct > 15:
            score += 5
        elif margin_pct > 5:
            score += 2
        elif margin_pct > 0:
            pass
        else:
            score -= 8
            signals.append(f'Negative profit margin {margin_pct:.0f}%')

    # ===== Insider Activity =====
    insider_pct = safe_float(info.get('heldPercentInsiders', 0))
    if insider_pct > 0:
        if insider_pct > 0.15:
            score += 5
            signals.append(f'High insider ownership {insider_pct*100:.1f}%')
        elif insider_pct > 0.05:
            score += 2

    # ===== Dividend (for large cap / stability) =====
    if cap_cat in ('large', 'mega'):
        div_yield = safe_float(info.get('dividendYield', 0))
        if div_yield > 0:
            div_pct = div_yield * 100
            if div_pct > 4:
                score += 6
                signals.append(f'Strong dividend yield {div_pct:.1f}%')
            elif div_pct > 2:
                score += 3
                signals.append(f'Dividend yield {div_pct:.1f}%')

    # ===== Analyst Recommendation =====
    rec_mean = safe_float(info.get('recommendationMean', 0))
    if rec_mean > 0:
        # 1 = strong buy, 5 = strong sell
        if rec_mean <= 1.5:
            score += 8
            signals.append(f'Analyst consensus: Strong Buy ({rec_mean:.1f})')
        elif rec_mean <= 2.2:
            score += 4
            signals.append(f'Analyst consensus: Buy ({rec_mean:.1f})')
        elif rec_mean <= 3.0:
            pass  # Hold — neutral
        elif rec_mean <= 3.8:
            score -= 4
            signals.append(f'Analyst consensus: Underperform ({rec_mean:.1f})')
        else:
            score -= 8
            signals.append(f'Analyst consensus: Sell ({rec_mean:.1f})')

    score = max(0, min(100, round(score)))

    return {
        'score': score,
        'pe_vs_sector': pe_label,
        'revenue_growth': rev_label,
        'earnings_surprise': earnings_label,
        'key_signals': signals[:8],
        'market_cap': market_cap,
        'market_cap_category': cap_cat,
        'market_cap_label': cap_label,
    }


def _score_etf(info, signals):
    """Simplified scoring for ETFs — focus on yield, expense ratio, AUM."""
    score = 55  # ETFs start slightly above neutral (they're diversified)

    if not info:
        return {
            'score': score, 'pe_vs_sector': 'N/A (ETF)', 'revenue_growth': 'N/A (ETF)',
            'earnings_surprise': 'N/A (ETF)', 'key_signals': ['ETF — limited fundamental data'],
            'market_cap': 0, 'market_cap_category': 'etf', 'market_cap_label': 'ETF',
        }

    # Expense ratio
    expense = safe_float(info.get('annualReportExpenseRatio', 0))
    if expense > 0:
        if expense < 0.001:
            score += 5
            signals.append(f'Very low expense ratio {expense*100:.2f}%')
        elif expense < 0.005:
            score += 3
        elif expense > 0.01:
            score -= 5
            signals.append(f'High expense ratio {expense*100:.2f}%')

    # Dividend yield
    div_yield = safe_float(info.get('yield', 0))
    if div_yield > 0:
        div_pct = div_yield * 100
        if div_pct > 3:
            score += 5
            signals.append(f'ETF yield {div_pct:.1f}%')
        elif div_pct > 1:
            score += 2

    # AUM / total assets
    total_assets = safe_float(info.get('totalAssets', 0))
    if total_assets > 10_000_000_000:
        score += 3
        signals.append('Large ETF with high liquidity')

    # 3-year return
    three_yr = safe_float(info.get('threeYearAverageReturn', 0))
    if three_yr > 0:
        ret_pct = three_yr * 100
        if ret_pct > 15:
            score += 8
        elif ret_pct > 8:
            score += 4
        elif ret_pct < 0:
            score -= 5

    score = max(0, min(100, round(score)))

    return {
        'score': score,
        'pe_vs_sector': 'N/A (ETF)',
        'revenue_growth': 'N/A (ETF)',
        'earnings_surprise': 'N/A (ETF)',
        'key_signals': signals[:6] if signals else ['ETF — diversified, stable'],
        'market_cap': safe_float(info.get('totalAssets', 0)),
        'market_cap_category': 'etf',
        'market_cap_label': 'ETF',
    }
