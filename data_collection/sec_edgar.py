# data_collection/sec_edgar.py
"""
SEC EDGAR Data Scraper
Pulls insider trading (Form 4), recent filings (10-K/10-Q/8-K),
and company facts from SEC's free EDGAR API.

No API key required — just a User-Agent header with contact info.
Rate limit: 10 requests/second (SEC policy).
"""

import re
import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta


# SEC requires a descriptive User-Agent with contact email
SEC_HEADERS = {
    "User-Agent": "AlphaAI StockAnalyzer contact@alpha-ai.app",
    "Accept": "application/json",
}

# Rate limiting: SEC allows 10 req/sec, we'll be conservative
_last_request_time = 0.0
_MIN_REQUEST_INTERVAL = 0.15  # ~6.6 req/sec max


def _rate_limit():
    """Ensure we don't exceed SEC rate limits."""
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < _MIN_REQUEST_INTERVAL:
        time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
    _last_request_time = time.time()


def _fetch_json(url):
    """Fetch JSON from SEC EDGAR with rate limiting."""
    try:
        _rate_limit()
        resp = requests.get(url, headers=SEC_HEADERS, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception:
        return None


def _fetch_text(url):
    """Fetch raw text from SEC EDGAR with rate limiting."""
    try:
        _rate_limit()
        resp = requests.get(url, headers=SEC_HEADERS, timeout=15)
        if resp.status_code == 200:
            return resp.text
        return None
    except Exception:
        return None


def _get_cik(ticker):
    """
    Look up the SEC CIK number for a ticker symbol.
    Returns zero-padded 10-digit CIK string, or None.
    """
    try:
        resp = _fetch_json("https://www.sec.gov/files/company_tickers.json")
        if not resp:
            return None

        ticker_upper = ticker.upper()
        for entry in resp.values():
            if entry.get("ticker", "").upper() == ticker_upper:
                return str(entry["cik_str"]).zfill(10)
        return None
    except Exception as e:
        print(f"  SEC EDGAR: CIK lookup failed for {ticker}: {e}")
        return None


def get_latest_earnings_release(submissions_data, cik_raw, max_age_days=120, max_chars=12000):
    """
    Find the most recent 8-K with Item 2.02 (earnings results) and return its
    text content, stripped of HTML tags.

    Returns dict with {date, items, text, url} or None if not found.
    Item 2.02 is the SEC code for "Results of Operations" — earnings releases
    are required to file under this item, making it a precise filter.
    """
    recent = submissions_data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    items_list = recent.get("items", [""] * len(forms))
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])

    cutoff = (datetime.now() - timedelta(days=max_age_days)).strftime("%Y-%m-%d")

    for i, form in enumerate(forms):
        if form != "8-K":
            continue
        items_str = items_list[i] if i < len(items_list) else ""
        if "2.02" not in items_str:
            continue
        date = dates[i] if i < len(dates) else ""
        if date < cutoff:
            return None  # filings are in date-desc order; older ones won't be relevant

        acc = accessions[i] if i < len(accessions) else ""
        doc = primary_docs[i] if i < len(primary_docs) else ""
        if not acc or not doc:
            continue
        acc_clean = acc.replace("-", "")
        doc_filename = doc.split("/")[-1]
        base = f"https://www.sec.gov/Archives/edgar/data/{cik_raw}/{acc_clean}"

        # The primary 8-K cover doc is usually a thin reference page. The actual
        # earnings press release lives in larger exhibit files (EX-99, e.g.
        # "q4fy26pr.htm"). Fetch the accession index and pull the largest .htm
        # exhibits, concatenating their stripped text.
        idx_data = _fetch_json(f"{base}/index.json")
        html = ""
        url = f"{base}/{doc_filename}"
        if idx_data:
            items = idx_data.get("directory", {}).get("item", [])
            candidates = []
            for it in items:
                name = it.get("name", "")
                if not name.lower().endswith(".htm"):
                    continue
                if name == doc_filename:
                    continue
                size_str = it.get("size", "")
                try:
                    size = int(size_str) if size_str else 0
                except ValueError:
                    size = 0
                if size < 30_000:  # cover/index pages are small; press releases are big
                    continue
                candidates.append((size, name))
            # Largest first; concatenate up to 3 to keep input bounded
            candidates.sort(reverse=True)
            for _, name in candidates[:3]:
                exhibit_html = _fetch_text(f"{base}/{name}")
                if exhibit_html:
                    html += "\n\n" + exhibit_html
            if candidates:
                url = f"{base}/{candidates[0][1]}"

        # Fall back to the primary doc if we couldn't find any exhibit
        if not html:
            html = _fetch_text(f"{base}/{doc_filename}") or ""
        if not html:
            return None

        # Strip HTML tags and normalize whitespace. Good-enough for LLM consumption.
        text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"&nbsp;|&#160;", " ", text)
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"&[a-z]+;|&#\d+;", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

        return {
            "date": date,
            "items": items_str,
            "text": text[:max_chars],
            "url": url,
            "truncated": len(text) > max_chars,
        }

    return None


def _parse_submissions(submissions_data, days_insider=90, days_filings=180, max_filings=15):
    """
    Parse the submissions JSON (fetched once) into insider summary + recent filings.
    Returns (insider_summary_dict, filings_list, form4_filings_list).
    form4_filings_list: list of {date, url} dicts within the insider window,
    used to fetch Form 4 XMLs for cluster detection.
    """
    insider_summary = None
    filings = []
    form4_filings = []

    recent = submissions_data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    descriptions = recent.get("primaryDocDescription", [])
    primary_docs = recent.get("primaryDocument", [])
    cik_raw = str(submissions_data.get("cik", "")).lstrip("0")

    # --- Insider summary (Form 4 count) + collect Form 4 URLs ---
    insider_cutoff = (datetime.now() - timedelta(days=days_insider)).strftime("%Y-%m-%d")
    form4_dates = []
    for i, form in enumerate(forms):
        if form != "4":
            continue
        filing_date = dates[i] if i < len(dates) else ""
        if filing_date < insider_cutoff:
            continue
        form4_dates.append(filing_date)

        acc = accessions[i] if i < len(accessions) else ""
        doc = primary_docs[i] if i < len(primary_docs) else ""
        if acc and doc and doc.endswith(".xml"):
            acc_clean = acc.replace("-", "")
            # primaryDocument often points to an XSLT-rendered HTML view
            # (e.g. xslF345X06/form4.xml). Strip that prefix to get raw XML.
            doc_filename = doc.split("/")[-1]
            form4_filings.append({
                "date": filing_date,
                "url": f"https://www.sec.gov/Archives/edgar/data/{cik_raw}/{acc_clean}/{doc_filename}",
            })

    if form4_dates:
        insider_summary = {
            "total_form4_filings": len(form4_dates),
            "period_days": days_insider,
            "most_recent": form4_dates[0],
            "oldest_in_range": form4_dates[-1],
        }
    else:
        insider_summary = {"total_form4_filings": 0, "period_days": days_insider}

    # --- Recent filings ---
    filings_cutoff = (datetime.now() - timedelta(days=days_filings)).strftime("%Y-%m-%d")
    important_forms = {"10-K", "10-Q", "8-K", "S-1", "DEF 14A", "SC 13D",
                       "SC 13G", "13F-HR", "4", "3", "5", "6-K", "20-F"}

    for i, form in enumerate(forms):
        if form not in important_forms:
            continue
        filing_date = dates[i] if i < len(dates) else ""
        if filing_date < filings_cutoff:
            continue

        acc = accessions[i] if i < len(accessions) else ""
        doc = primary_docs[i] if i < len(primary_docs) else ""
        desc = descriptions[i] if i < len(descriptions) else form

        filing_url = ""
        if acc and doc:
            acc_clean = acc.replace("-", "")
            filing_url = f"https://www.sec.gov/Archives/edgar/data/{cik_raw}/{acc_clean}/{doc}"

        filings.append({
            "form": form,
            "date": filing_date,
            "description": desc or form,
            "url": filing_url,
        })

        if len(filings) >= max_filings:
            break

    return insider_summary, filings, form4_filings


def get_company_facts(cik):
    """
    Fetch XBRL company facts (structured financial data) from EDGAR.
    Returns key financial metrics from recent filings.
    """
    try:
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        data = _fetch_json(url)
        if not data:
            return None

        facts = {}
        us_gaap = data.get("facts", {}).get("us-gaap", {})

        # Extract key metrics — try multiple XBRL tags per metric,
        # pick the tag with the MOST RECENT 10-K data (not just the first match)
        metrics_map = {
            "Revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                        "SalesRevenueNet", "RevenueFromContractWithCustomerIncludingAssessedTax"],
            "NetIncome": ["NetIncomeLoss", "ProfitLoss"],
            "EPS": ["EarningsPerShareDiluted", "EarningsPerShareBasic"],
            "TotalAssets": ["Assets"],
            "TotalDebt": ["LongTermDebt", "LongTermDebtNoncurrent"],
            "CashAndEquivalents": ["CashAndCashEquivalentsAtCarryingValue",
                                    "CashCashEquivalentsAndShortTermInvestments"],
            "OperatingIncome": ["OperatingIncomeLoss"],
            "FreeCashFlow": ["NetCashProvidedByUsedInOperatingActivities"],
            "SharesOutstanding": ["CommonStockSharesOutstanding",
                                   "WeightedAverageNumberOfDilutedSharesOutstanding"],
        }

        for label, xbrl_tags in metrics_map.items():
            best_annual = None  # (end_date, latest_entry, prior_entry)
            best_quarterly = None  # (end_date, entry)

            for tag in xbrl_tags:
                if tag not in us_gaap:
                    continue

                units = us_gaap[tag].get("units", {})
                values = units.get("USD", units.get("shares", units.get("USD/shares", [])))
                if not values:
                    continue

                # Check 10-K entries for this tag
                annual = [v for v in values if v.get("form") == "10-K"]
                if annual:
                    sorted_annual = sorted(annual, key=lambda x: x.get("end", ""), reverse=True)
                    latest_end = sorted_annual[0].get("end", "")
                    # Only use this tag if it has more recent data than what we already found
                    if best_annual is None or latest_end > best_annual[0]:
                        prior = sorted_annual[1] if len(sorted_annual) >= 2 else None
                        best_annual = (latest_end, sorted_annual[0], prior)

                # Check 10-Q entries for this tag
                quarterly = [v for v in values if v.get("form") == "10-Q"]
                if quarterly:
                    sorted_q = sorted(quarterly, key=lambda x: x.get("end", ""), reverse=True)
                    latest_end = sorted_q[0].get("end", "")
                    if best_quarterly is None or latest_end > best_quarterly[0]:
                        best_quarterly = (latest_end, sorted_q[0])

            # Store the best results
            if best_annual:
                _, latest_entry, prior_entry = best_annual
                facts[f"{label}_annual"] = {
                    "value": latest_entry.get("val"),
                    "period_end": latest_entry.get("end"),
                    "filed": latest_entry.get("filed"),
                }
                if prior_entry:
                    facts[f"{label}_annual_prior"] = {
                        "value": prior_entry.get("val"),
                        "period_end": prior_entry.get("end"),
                    }

            if best_quarterly:
                _, q_entry = best_quarterly
                facts[f"{label}_quarterly"] = {
                    "value": q_entry.get("val"),
                    "period_end": q_entry.get("end"),
                    "filed": q_entry.get("filed"),
                }

        return facts if facts else None

    except Exception as e:
        print(f"  SEC EDGAR: company facts error: {e}")
        return None


# --- Form 4 detail parsing ---
# Open-market purchase/sale codes carry the strongest insider-signal value.
# A=grant/award, M=option exercise, F=tax withholding etc. are excluded as noise.
_BUY_CODES = {"P"}        # Open market purchase
_SELL_CODES = {"S"}       # Open market sale
_NOISE_CODES = {"A", "M", "F", "G", "I", "X", "C"}  # awards, exercises, tax, gifts, splits, conversions

# Insider trades made under pre-arranged 10b5-1 plans don't reflect new
# information — they're scheduled in advance. Exclude from sell-side signal.
_RULE_10B5_RE = re.compile(r"10b5[-\s]?1", re.IGNORECASE)


def _strip_ns(tag):
    """Strip XML namespace from a tag name."""
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _findtext(elem, *path):
    """Find first child text matching path (namespace-agnostic). Returns None if missing."""
    if elem is None:
        return None
    cur = elem
    for tag in path:
        nxt = None
        for child in cur:
            if _strip_ns(child.tag) == tag:
                nxt = child
                break
        if nxt is None:
            return None
        cur = nxt
    text = cur.text
    return text.strip() if text else None


def _parse_form4_xml(xml_text):
    """
    Parse a Form 4 XML document into a list of insider transaction dicts.
    Returns [] on any parse failure (defensive).

    Each dict: {insider_name, insider_role, code, shares, price, value,
                acquired_disposed, is_10b5_1, transaction_date}
    """
    if not xml_text:
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    # Reporting owner
    owner_name = None
    is_director = is_officer = is_ten_pct = False
    officer_title = None
    for child in root:
        if _strip_ns(child.tag) != "reportingOwner":
            continue
        owner_name = _findtext(child, "reportingOwnerId", "rptOwnerName")
        is_director = (_findtext(child, "reportingOwnerRelationship", "isDirector") in ("1", "true"))
        is_officer = (_findtext(child, "reportingOwnerRelationship", "isOfficer") in ("1", "true"))
        is_ten_pct = (_findtext(child, "reportingOwnerRelationship", "isTenPercentOwner") in ("1", "true"))
        officer_title = _findtext(child, "reportingOwnerRelationship", "officerTitle")
        break

    role_parts = []
    if is_officer:
        role_parts.append(officer_title or "Officer")
    if is_director:
        role_parts.append("Director")
    if is_ten_pct:
        role_parts.append("10%Owner")
    role = "/".join(role_parts) or "Insider"

    # Footnote text (used to detect 10b5-1 plans)
    footnotes_text = ""
    for child in root:
        if _strip_ns(child.tag) == "footnotes":
            for fn in child:
                if _strip_ns(fn.tag) == "footnote" and fn.text:
                    footnotes_text += " " + fn.text
    plan_in_filing = bool(_RULE_10B5_RE.search(footnotes_text))

    # Non-derivative transactions
    txns = []
    for child in root:
        if _strip_ns(child.tag) != "nonDerivativeTable":
            continue
        for ndt in child:
            if _strip_ns(ndt.tag) != "nonDerivativeTransaction":
                continue
            code = _findtext(ndt, "transactionCoding", "transactionCode")
            ad = _findtext(ndt, "transactionAmounts", "transactionAcquiredDisposedCode", "value")
            shares_s = _findtext(ndt, "transactionAmounts", "transactionShares", "value")
            price_s = _findtext(ndt, "transactionAmounts", "transactionPricePerShare", "value")
            tdate = _findtext(ndt, "transactionDate", "value")

            try:
                shares = float(shares_s) if shares_s else 0.0
            except ValueError:
                shares = 0.0
            try:
                price = float(price_s) if price_s else 0.0
            except ValueError:
                price = 0.0

            txns.append({
                "insider_name": owner_name or "Unknown",
                "insider_role": role,
                "code": code,
                "shares": shares,
                "price": price,
                "value": shares * price,
                "acquired_disposed": ad,  # "A"=acquired, "D"=disposed
                "is_10b5_1": plan_in_filing,
                "transaction_date": tdate,
            })
    return txns


def get_insider_transactions(cik_raw, form4_filings, max_filings=20):
    """
    Fetch and parse the Form 4 XMLs for a list of filings.
    `form4_filings` is a list of dicts with at least 'url' (the primary-doc URL).

    Returns aggregated insider signal dict:
      {
        distinct_buyers, total_buy_value, total_buy_shares,
        distinct_sellers, total_sell_value, total_sell_shares,
        sell_value_excluding_10b5_1, sell_value_10b5_1,
        cluster_score: -2 to +3,  # see _cluster_score
        recent_transactions: [...],  # capped at 20 most recent
      }
    """
    all_txns = []
    for f in form4_filings[:max_filings]:
        url = f.get("url", "")
        if not url.endswith(".xml"):
            continue
        xml_text = _fetch_text(url)
        if not xml_text:
            continue
        all_txns.extend(_parse_form4_xml(xml_text))

    if not all_txns:
        return None

    buyers = set()
    sellers = set()
    total_buy_value = 0.0
    total_buy_shares = 0.0
    total_sell_value = 0.0
    total_sell_shares = 0.0
    sell_10b5_value = 0.0
    sell_open_value = 0.0  # excludes 10b5-1

    for t in all_txns:
        code = t["code"]
        if code in _NOISE_CODES:
            continue
        if code in _BUY_CODES and t["acquired_disposed"] == "A":
            buyers.add(t["insider_name"])
            total_buy_value += t["value"]
            total_buy_shares += t["shares"]
        elif code in _SELL_CODES and t["acquired_disposed"] == "D":
            sellers.add(t["insider_name"])
            total_sell_value += t["value"]
            total_sell_shares += t["shares"]
            if t["is_10b5_1"]:
                sell_10b5_value += t["value"]
            else:
                sell_open_value += t["value"]

    return {
        "distinct_buyers": len(buyers),
        "total_buy_value": round(total_buy_value, 2),
        "total_buy_shares": int(total_buy_shares),
        "distinct_sellers": len(sellers),
        "total_sell_value": round(total_sell_value, 2),
        "total_sell_shares": int(total_sell_shares),
        "sell_value_10b5_1": round(sell_10b5_value, 2),
        "sell_value_open_market": round(sell_open_value, 2),
        "cluster_score": _cluster_score(len(buyers), total_buy_value,
                                         len(sellers), sell_open_value),
        "buyer_names": sorted(buyers),
        "seller_names": sorted(sellers),
    }


def _cluster_score(n_buyers, buy_value, n_sellers, sell_value_open):
    """
    Map insider activity to a -2..+3 score. Calibrated for the rule of thumb that
    cluster buying (multiple insiders, six figures+) is one of the strongest free
    signals; lone executive purchases under $50K are noise; and sales under
    10b5-1 plans are not informative.

      +3: ≥3 distinct buyers AND >$1M open-market buying, no major selling
      +2: ≥2 distinct buyers AND >$250K open-market buying
      +1: 1 buyer AND >$100K open-market buying
       0: no meaningful activity
      -1: ≥2 distinct open-market sellers AND >$1M open-market selling
      -2: ≥3 distinct open-market sellers AND >$5M open-market selling
    """
    sells_dominant = sell_value_open > buy_value * 2

    if n_buyers >= 3 and buy_value > 1_000_000 and not sells_dominant:
        return 3
    if n_buyers >= 2 and buy_value > 250_000 and not sells_dominant:
        return 2
    if n_buyers >= 1 and buy_value > 100_000 and not sells_dominant:
        return 1
    if n_sellers >= 3 and sell_value_open > 5_000_000:
        return -2
    if n_sellers >= 2 and sell_value_open > 1_000_000:
        return -1
    return 0


class SECEdgarScraper:
    """
    SEC EDGAR data scraper for stock analysis.
    Pulls insider trades, filings, and financial facts.
    No API key required.
    """

    def __init__(self):
        self._cik_cache = {}
        print("📋 SEC EDGAR scraper initialized")

    def _get_cik(self, ticker):
        """Get CIK with caching."""
        if ticker not in self._cik_cache:
            self._cik_cache[ticker] = _get_cik(ticker)
        return self._cik_cache[ticker]

    def get_edgar_data(self, ticker):
        """
        Fetch all SEC EDGAR data for a ticker.
        Returns dict with insider_summary, recent_filings, company_facts.
        """
        cik = self._get_cik(ticker)
        if not cik:
            print(f"  SEC EDGAR: could not find CIK for {ticker}")
            return {}

        print(f"  SEC EDGAR: fetching data for {ticker} (CIK: {cik})...")

        result = {}

        # Fetch submissions once — used for both insider summary and filings
        submissions = _fetch_json(f"https://data.sec.gov/submissions/CIK{cik}.json")
        if submissions:
            insider_summary, filings, form4_filings = _parse_submissions(submissions)

            if insider_summary:
                result["insider_summary"] = insider_summary

            # Parse Form 4 XMLs to get directional insider signal (buying vs selling)
            cik_raw = str(submissions.get("cik", "")).lstrip("0")
            if form4_filings:
                insider_detail = get_insider_transactions(cik_raw, form4_filings)
                if insider_detail:
                    result["insider_signal"] = insider_detail

            # Pull most recent earnings press release (8-K Item 2.02) for sentiment scoring
            earnings_release = get_latest_earnings_release(submissions, cik_raw)
            if earnings_release:
                result["earnings_release"] = earnings_release

            if filings:
                result["recent_filings"] = filings

                # Categorize filings for quick analysis
                form_counts = {}
                for f in filings:
                    form = f["form"]
                    form_counts[form] = form_counts.get(form, 0) + 1
                result["filing_counts"] = form_counts

                # Flag 8-K filings (material events)
                eight_ks = [f for f in filings if f["form"] == "8-K"]
                if eight_ks:
                    result["material_events"] = len(eight_ks)
                    result["latest_8k_date"] = eight_ks[0]["date"]
                    result["latest_8k_description"] = eight_ks[0].get("description", "")

        # Company financial facts from XBRL (separate endpoint)
        facts = get_company_facts(cik)
        if facts:
            result["company_facts"] = facts

            # Calculate YoY revenue growth if available
            rev_current = facts.get("Revenue_annual", {}).get("value")
            rev_prior = facts.get("Revenue_annual_prior", {}).get("value")
            # Sanity check: both periods should be from the same tag (close in time)
            rev_end = facts.get("Revenue_annual", {}).get("period_end", "")
            rev_prior_end = facts.get("Revenue_annual_prior", {}).get("period_end", "")
            if (rev_current and rev_prior and rev_prior > 0
                    and rev_end and rev_prior_end
                    and rev_end[:4].isdigit() and rev_prior_end[:4].isdigit()
                    and abs(int(rev_end[:4]) - int(rev_prior_end[:4])) <= 2):
                yoy_growth = ((rev_current - rev_prior) / rev_prior) * 100
                result["revenue_yoy_growth"] = round(yoy_growth, 1)

            # Net income trend
            ni_current = facts.get("NetIncome_annual", {}).get("value")
            ni_prior = facts.get("NetIncome_annual_prior", {}).get("value")
            if ni_current is not None and ni_prior is not None:
                if ni_current > 0 and ni_prior > 0:
                    ni_growth = ((ni_current - ni_prior) / abs(ni_prior)) * 100
                    result["net_income_yoy_growth"] = round(ni_growth, 1)
                elif ni_current > 0 and ni_prior <= 0:
                    result["net_income_yoy_growth"] = "turnaround"
                elif ni_current <= 0:
                    result["net_income_yoy_growth"] = "negative"

        if result:
            print(f"  SEC EDGAR: got {len(result)} data sections for {ticker}")
        else:
            print(f"  SEC EDGAR: no data found for {ticker}")

        return result
