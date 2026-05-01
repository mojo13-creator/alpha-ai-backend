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


def calculate_berkeley_adjustment(berkeley_data):
    """
    Calculate score adjustment from Berkeley enrichment data.
    Returns (adjustment_points, signals_list). Max +-15 points.
    """
    adj = 0.0
    signals = []

    if not berkeley_data:
        return 0, []

    # --- Capital IQ ---
    capiq = berkeley_data.get("capital_iq", {})
    if capiq:
        # Analyst consensus
        consensus = (capiq.get("analyst", {}).get("consensus") or "").lower()
        if any(w in consensus for w in ["strong buy", "overweight"]):
            adj += 5
            signals.append(f"CapIQ analyst consensus: {consensus}")
        elif any(w in consensus for w in ["buy"]):
            adj += 3
        elif any(w in consensus for w in ["sell", "underweight"]):
            adj -= 5
            signals.append(f"CapIQ analyst consensus: {consensus}")
        elif any(w in consensus for w in ["strong sell"]):
            adj -= 7

        # Price targets — compare mean to current
        pt_mean = capiq.get("analyst", {}).get("price_target_mean")
        if pt_mean and isinstance(pt_mean, (int, float)) and pt_mean > 0:
            signals.append(f"CapIQ mean price target: ${pt_mean:.2f}")

        # Institutional ownership
        inst_pct = capiq.get("ownership", {}).get("institutional_pct")
        if inst_pct and isinstance(inst_pct, (int, float)):
            if inst_pct > 0.7:
                adj += 3
                signals.append(f"High institutional ownership: {inst_pct*100:.0f}%")
            elif inst_pct < 0.2:
                adj -= 2

        # Insider transactions — net buying vs selling
        insider_txns = capiq.get("ownership", {}).get("insider_transactions", [])
        if insider_txns:
            buys = sum(1 for t in insider_txns if "buy" in (t.get("type", "") or "").lower())
            sells = sum(1 for t in insider_txns if "sell" in (t.get("type", "") or "").lower())
            if buys > sells:
                adj += 3
                signals.append(f"CapIQ: net insider buying ({buys}B/{sells}S)")
            elif sells > buys * 2:
                adj -= 3
                signals.append(f"CapIQ: heavy insider selling ({sells}S/{buys}B)")

        # EPS surprises
        eps_data = capiq.get("earnings", {}).get("eps_estimates_vs_actuals", [])
        beats = 0
        for q in eps_data:
            est = q.get("estimate")
            act = q.get("actual")
            if est is not None and act is not None and isinstance(est, (int, float)) and isinstance(act, (int, float)):
                if act > est:
                    beats += 1
        if beats >= 3:
            adj += 3
            signals.append(f"CapIQ: beat EPS estimates {beats}/4 quarters")

        # Peer comparison — P/E below sector avg
        sector_pe = capiq.get("peers", {}).get("sector_avg_pe")
        sector_growth = capiq.get("peers", {}).get("sector_avg_revenue_growth")
        if sector_pe and isinstance(sector_pe, (int, float)) and sector_pe > 0:
            signals.append(f"CapIQ sector avg P/E: {sector_pe:.1f}")

    # --- Orbis ---
    orbis = berkeley_data.get("orbis", {})
    if orbis:
        # Subsidiary complexity as risk factor
        subs = orbis.get("subsidiaries", [])
        if len(subs) > 50:
            adj -= 2
            signals.append(f"Orbis: complex structure ({len(subs)} subsidiaries)")

        # Comparable companies for context
        comps = orbis.get("comparables", [])
        if comps:
            signals.append(f"Orbis: {len(comps)} peer comparables available")

    # --- Statista ---
    statista = berkeley_data.get("statista", {})
    if statista:
        market_size = statista.get("market_size")
        if market_size:
            signals.append(f"Statista TAM: {market_size}")

        forecast = statista.get("market_forecast")
        if forecast:
            forecast_lower = forecast.lower()
            if any(w in forecast_lower for w in ["grow", "increase", "expand", "rise"]):
                adj += 2
                signals.append("Statista: growing market forecast")
            elif any(w in forecast_lower for w in ["decline", "shrink", "contract"]):
                adj -= 2
                signals.append("Statista: declining market forecast")

    # Clamp to +-15
    adj = max(-15, min(15, round(adj)))
    return adj, signals


def calculate_sec_edgar_adjustment(sec_data):
    """
    Calculate score adjustment from SEC EDGAR data.
    Returns (adjustment_points, signals_list). Max +-10 points.
    """
    adj = 0.0
    signals = []

    if not sec_data:
        return 0, []

    # --- Insider trading activity (Form 4 filings) ---
    insider = sec_data.get("insider_summary", {})
    if insider:
        form4_count = insider.get("total_form4_filings", 0)
        if form4_count > 10:
            # Heavy insider activity — could be buying or selling
            signals.append(f"SEC: {form4_count} insider transactions (90d)")
        elif form4_count > 0:
            signals.append(f"SEC: {form4_count} insider transactions (90d)")

    # --- Material events (8-K filings) ---
    material_events = sec_data.get("material_events", 0)
    if material_events >= 5:
        adj -= 3
        signals.append(f"SEC: {material_events} material event filings (8-K) in 6 months — high activity")
    elif material_events >= 3:
        signals.append(f"SEC: {material_events} material events (8-K) recently")

    # --- Revenue YoY growth from XBRL ---
    rev_yoy = sec_data.get("revenue_yoy_growth")
    if rev_yoy is not None:
        if rev_yoy > 25:
            adj += 4
            signals.append(f"SEC filing revenue growth: {rev_yoy:+.1f}% YoY")
        elif rev_yoy > 10:
            adj += 2
            signals.append(f"SEC filing revenue growth: {rev_yoy:+.1f}% YoY")
        elif rev_yoy < -25:
            adj -= 5
            signals.append(f"SEC filing revenue decline: {rev_yoy:+.1f}% YoY")
        elif rev_yoy < -10:
            adj -= 3
            signals.append(f"SEC filing revenue decline: {rev_yoy:+.1f}% YoY")

    # --- Net income trend ---
    ni_yoy = sec_data.get("net_income_yoy_growth")
    if ni_yoy == "turnaround":
        adj += 3
        signals.append("SEC: net income turned positive (turnaround)")
    elif ni_yoy == "negative":
        adj -= 2
        signals.append("SEC: net income is negative")
    elif isinstance(ni_yoy, (int, float)):
        if ni_yoy > 30:
            adj += 3
            signals.append(f"SEC filing net income growth: {ni_yoy:+.1f}% YoY")
        elif ni_yoy < -30:
            adj -= 3
            signals.append(f"SEC filing net income decline: {ni_yoy:+.1f}% YoY")

    # --- Cash position from XBRL ---
    facts = sec_data.get("company_facts", {})
    cash_data = facts.get("CashAndEquivalents_annual", {})
    cash_val = cash_data.get("value")
    total_debt_data = facts.get("TotalDebt_annual", {})
    debt_val = total_debt_data.get("value")
    if cash_val is not None and debt_val is not None and debt_val > 0:
        cash_to_debt = cash_val / debt_val
        if cash_to_debt > 2.0:
            adj += 2
            signals.append(f"SEC: strong cash/debt ratio ({cash_to_debt:.1f}x)")
        elif cash_to_debt < 0.2:
            adj -= 2
            signals.append(f"SEC: weak cash/debt ratio ({cash_to_debt:.1f}x)")

    # Clamp to +-10
    adj = max(-10, min(10, round(adj)))
    return adj, signals


def calculate_fundamental_score(symbol, berkeley_data=None, sec_data=None):
    """
    Calculate fundamental score (0-100) from yfinance data.
    Optionally enhanced with Berkeley institutional data and SEC EDGAR data.
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

    # ===== Earnings Estimate Revisions =====
    # Net up vs down EPS estimate revisions over the last 30 days. Sell-side
    # revision direction is one of the most documented alpha factors —
    # analyst estimates trending up tends to precede price.
    try:
        revs = ticker.eps_revisions
        if revs is not None and not revs.empty:
            # Use the +1q (next quarter) row as the most actionable signal
            row = revs.loc['+1q'] if '+1q' in revs.index else revs.iloc[1]
            up = safe_float(row.get('upLast30days', 0))
            down = safe_float(row.get('downLast30days', 0))
            if up + down > 0:
                net = up - down
                if net >= 5:
                    score += 10
                    signals.append(f'EPS revisions strongly positive ({int(up)}↑/{int(down)}↓ 30d)')
                elif net >= 2:
                    score += 6
                    signals.append(f'EPS revisions trending up ({int(up)}↑/{int(down)}↓ 30d)')
                elif net <= -5:
                    score -= 10
                    signals.append(f'EPS revisions strongly negative ({int(up)}↑/{int(down)}↓ 30d)')
                elif net <= -2:
                    score -= 6
                    signals.append(f'EPS revisions trending down ({int(up)}↑/{int(down)}↓ 30d)')
    except Exception:
        pass

    # ===== Piotroski-lite Quality Score =====
    # Subset of Piotroski's 9-point F-Score using fields available without
    # multi-year financial parsing. 8 binary criteria — high score = quality.
    try:
        ni = safe_float(info.get('netIncomeToCommon', 0))
        ocf = safe_float(info.get('operatingCashflow', 0))
        roa = safe_float(info.get('returnOnAssets', 0))
        cur_ratio = safe_float(info.get('currentRatio', 0))
        gross_m = safe_float(info.get('grossMargins', 0))
        total_debt = safe_float(info.get('totalDebt', 0))
        fcf_pl = safe_float(info.get('freeCashflow', 0))

        f_score = 0
        f_score += 1 if ni > 0 else 0                       # profitable
        f_score += 1 if ocf > 0 else 0                       # cash-generating
        f_score += 1 if (ocf > ni and ni > 0) else 0         # earnings quality (CFO > NI)
        f_score += 1 if roa > 0.05 else 0                    # ROA > 5%
        f_score += 1 if cur_ratio > 1.0 else 0               # liquidity
        f_score += 1 if gross_m > 0.30 else 0                # gross margin > 30%
        f_score += 1 if (market_cap > 0 and total_debt / market_cap < 0.5) else 0  # leverage
        f_score += 1 if fcf_pl > 0 else 0                    # FCF positive

        if f_score >= 7:
            score += 8
            signals.append(f'Piotroski-lite quality score {f_score}/8 — high quality')
        elif f_score >= 5:
            score += 4
            signals.append(f'Piotroski-lite quality score {f_score}/8')
        elif f_score <= 2:
            score -= 8
            signals.append(f'Piotroski-lite quality score {f_score}/8 — weak fundamentals')
        elif f_score <= 3:
            score -= 4
            signals.append(f'Piotroski-lite quality score {f_score}/8 — below average')
    except Exception:
        pass

    # ===== Short Interest =====
    # High short interest = squeeze setup (bullish if other signals positive),
    # also a tell that smart money expects trouble. We treat it bidirectionally:
    # very high SI is a contrarian bullish setup, moderately elevated is bearish.
    short_pct = safe_float(info.get('shortPercentOfFloat', 0))
    if short_pct > 0:
        si_pct = short_pct * 100
        if si_pct > 25:
            score += 6
            signals.append(f'Short interest {si_pct:.1f}% of float — heavy squeeze potential')
        elif si_pct > 15:
            # Bearish bet but not yet squeeze territory
            score -= 3
            signals.append(f'Short interest {si_pct:.1f}% of float — elevated bearish positioning')
        elif si_pct > 8:
            score -= 1
            signals.append(f'Short interest {si_pct:.1f}% of float')

    # Short interest CHANGE (institutional positioning shift)
    shares_short = safe_float(info.get('sharesShort', 0))
    shares_short_prior = safe_float(info.get('sharesShortPriorMonth', 0))
    if shares_short > 0 and shares_short_prior > 0:
        si_change_pct = ((shares_short - shares_short_prior) / shares_short_prior) * 100
        if si_change_pct > 25:
            score -= 3
            signals.append(f'Shorts ramping up {si_change_pct:+.0f}% MoM — bearish positioning')
        elif si_change_pct < -25:
            score += 3
            signals.append(f'Shorts covering {si_change_pct:+.0f}% MoM — bears giving up')

    score = max(0, min(100, round(score)))

    # Berkeley enrichment adjustment (supplementary — score works fine without it)
    berkeley_enhanced = False
    berkeley_sources = []
    if berkeley_data:
        berkeley_adj, berkeley_signals = calculate_berkeley_adjustment(berkeley_data)
        if berkeley_adj != 0 or berkeley_signals:
            score = max(0, min(100, score + berkeley_adj))
            signals.extend(berkeley_signals)
            berkeley_enhanced = True
            berkeley_sources = list(berkeley_data.keys())

    # SEC EDGAR adjustment (free public data — insider trades, filings, XBRL financials)
    sec_enhanced = False
    if sec_data:
        sec_adj, sec_signals = calculate_sec_edgar_adjustment(sec_data)
        if sec_adj != 0 or sec_signals:
            score = max(0, min(100, score + sec_adj))
            signals.extend(sec_signals)
            sec_enhanced = True

    return {
        'score': score,
        'pe_vs_sector': pe_label,
        'revenue_growth': rev_label,
        'earnings_surprise': earnings_label,
        'key_signals': signals[:12],
        'market_cap': market_cap,
        'market_cap_category': cap_cat,
        'market_cap_label': cap_label,
        'berkeley_enhanced': berkeley_enhanced,
        'berkeley_sources': berkeley_sources,
        'sec_enhanced': sec_enhanced,
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
