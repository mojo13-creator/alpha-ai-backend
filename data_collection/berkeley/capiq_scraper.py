"""
Capital IQ Pro scraper via Berkeley institutional access.
Extracts financial data, analyst estimates, ownership, and peer comparables.

Capital IQ page structures change frequently — selectors may need updating.
"""

import logging
import sqlite3
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from data_collection.berkeley.browser_base import BerkeleyBrowserBase

logger = logging.getLogger(__name__)

CAPIQ_BASE = "https://www-capitaliq-com.libproxy.berkeley.edu"
DB_PATH = Path(__file__).resolve().parent.parent.parent / "stock_data.db"
CACHE_TTL_HOURS = 24


class CapIQScraper:
    """Scrapes financial data from Capital IQ Pro via CalNet-authenticated access."""

    def __init__(self):
        self._ensure_cache_table()

    def _ensure_cache_table(self):
        """Create the capiq_cache table if it doesn't exist."""
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS capiq_cache (
                ticker TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                fetched_at TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    def _get_cached(self, ticker: str) -> dict | None:
        """Return cached data if fresh enough, else None."""
        conn = sqlite3.connect(str(DB_PATH))
        row = conn.execute(
            "SELECT data, fetched_at FROM capiq_cache WHERE ticker = ?", (ticker,)
        ).fetchone()
        conn.close()

        if not row:
            return None

        fetched_at = datetime.fromisoformat(row[1])
        if datetime.now(timezone.utc) - fetched_at > timedelta(hours=CACHE_TTL_HOURS):
            return None

        return json.loads(row[0])

    def _save_cache(self, ticker: str, data: dict):
        """Persist scraped data to cache."""
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute(
            "INSERT OR REPLACE INTO capiq_cache (ticker, data, fetched_at) VALUES (?, ?, ?)",
            (ticker, json.dumps(data), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        conn.close()

    async def get_company_data(self, ticker: str) -> dict | None:
        """
        Fetch comprehensive financial data for a ticker from Capital IQ.
        Returns structured dict or None on failure.
        """
        ticker = ticker.upper()

        # Check cache first
        cached = self._get_cached(ticker)
        if cached:
            logger.info(f"CapIQ cache hit for {ticker}")
            return cached

        logger.info(f"Scraping Capital IQ for {ticker}...")

        try:
            async with BerkeleyBrowserBase() as browser:
                result = await self._scrape_company(browser, ticker)

            if result:
                self._save_cache(ticker, result)
                logger.info(f"CapIQ scrape complete for {ticker}")
            return result

        except Exception as e:
            logger.error(f"CapIQ scrape failed for {ticker}: {e}")
            return None

    async def _scrape_company(self, browser: BerkeleyBrowserBase, ticker: str) -> dict | None:
        """Navigate Capital IQ and extract all data for a ticker."""

        # Step 1: Search for the company
        search_url = f"{CAPIQ_BASE}/CIQDotNet/Search.aspx?searchQuery={ticker}"
        if not await browser.navigate(search_url):
            logger.error(f"Failed to load Capital IQ search for {ticker}")
            return None

        # Wait for search results or company page to load
        page = browser.page
        await page.wait_for_load_state("networkidle", timeout=20000)

        # If we landed on a search results page, click the first matching result
        try:
            # Capital IQ typically auto-redirects to the company page for exact ticker matches
            # If not, look for the company link in results
            company_link = page.locator(f'a:has-text("{ticker}")').first
            if await company_link.count() > 0 and "companyId" not in page.url:
                await company_link.click()
                await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        # Build the result dict
        result = {
            "ticker": ticker,
            "source": "capital_iq",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "financials": await self._extract_financials(browser, ticker),
            "earnings": await self._extract_earnings(browser, ticker),
            "analyst": await self._extract_analyst_data(browser, ticker),
            "ownership": await self._extract_ownership(browser, ticker),
            "debt": await self._extract_debt(browser, ticker),
            "peers": await self._extract_peers(browser, ticker),
        }

        return result

    async def _extract_financials(self, browser: BerkeleyBrowserBase, ticker: str) -> dict:
        """Extract revenue and net income data."""
        financials = {
            "revenue_quarterly": [],
            "revenue_annual": [],
            "net_income_quarterly": [],
            "net_income_annual": [],
        }

        try:
            # Navigate to financials section
            page = browser.page

            # Try the financials tab/link on the company page
            fin_link = page.locator('a:has-text("Financials"), a[href*="Financials"]').first
            if await fin_link.count() > 0:
                await fin_link.click()
                await page.wait_for_load_state("networkidle", timeout=15000)

            # Extract data from financial tables
            # Capital IQ uses dynamic tables — selectors will need tuning against live site
            rows = page.locator("table.financialTable tr, table[class*='financial'] tr")
            row_count = await rows.count()

            for i in range(row_count):
                row = rows.nth(i)
                label = await row.locator("td:first-child").text_content() or ""
                label = label.strip().lower()

                cells = row.locator("td:not(:first-child)")
                values = []
                for j in range(await cells.count()):
                    text = (await cells.nth(j).text_content() or "").strip()
                    values.append(self._parse_financial_value(text))

                if "revenue" in label or "total revenue" in label:
                    financials["revenue_annual"] = values[:3] if len(values) >= 3 else values
                elif "net income" in label:
                    financials["net_income_annual"] = values[:3] if len(values) >= 3 else values

        except Exception as e:
            logger.warning(f"Could not extract financials for {ticker}: {e}")

        return financials

    async def _extract_earnings(self, browser: BerkeleyBrowserBase, ticker: str) -> dict:
        """Extract EPS estimates vs actuals and next earnings date."""
        earnings = {
            "eps_estimates_vs_actuals": [],
            "next_earnings_date": None,
        }

        try:
            page = browser.page

            # Navigate to earnings/estimates section
            est_link = page.locator('a:has-text("Estimates"), a:has-text("Earnings")').first
            if await est_link.count() > 0:
                await est_link.click()
                await page.wait_for_load_state("networkidle", timeout=15000)

            # Look for EPS table rows
            eps_rows = page.locator("table tr:has-text('EPS')")
            for i in range(min(await eps_rows.count(), 4)):
                row = eps_rows.nth(i)
                cells = await row.locator("td").all_text_contents()
                if len(cells) >= 3:
                    earnings["eps_estimates_vs_actuals"].append({
                        "period": cells[0].strip(),
                        "estimate": self._parse_financial_value(cells[1]),
                        "actual": self._parse_financial_value(cells[2]),
                    })

            # Next earnings date
            date_el = page.locator('*:has-text("Next Earnings")').first
            if await date_el.count() > 0:
                text = (await date_el.text_content() or "").strip()
                # Try to extract a date from nearby text
                earnings["next_earnings_date"] = self._extract_date_from_text(text)

        except Exception as e:
            logger.warning(f"Could not extract earnings for {ticker}: {e}")

        return earnings

    async def _extract_analyst_data(self, browser: BerkeleyBrowserBase, ticker: str) -> dict:
        """Extract analyst consensus and price targets."""
        analyst = {
            "consensus": None,
            "price_target_mean": None,
            "price_target_high": None,
            "price_target_low": None,
        }

        try:
            page = browser.page

            # Look for analyst/consensus data on the page
            consensus_el = page.locator(
                '*:has-text("Consensus"), *:has-text("Mean Rating")'
            ).first
            if await consensus_el.count() > 0:
                analyst["consensus"] = (await consensus_el.text_content() or "").strip()

            # Price targets
            for label, key in [
                ("Mean Target", "price_target_mean"),
                ("High Target", "price_target_high"),
                ("Low Target", "price_target_low"),
            ]:
                el = page.locator(f'*:has-text("{label}")').first
                if await el.count() > 0:
                    text = (await el.text_content() or "").strip()
                    analyst[key] = self._parse_financial_value(text)

        except Exception as e:
            logger.warning(f"Could not extract analyst data for {ticker}: {e}")

        return analyst

    async def _extract_ownership(self, browser: BerkeleyBrowserBase, ticker: str) -> dict:
        """Extract institutional ownership and insider transactions."""
        ownership = {
            "institutional_pct": None,
            "insider_transactions": [],
        }

        try:
            page = browser.page

            # Navigate to ownership section
            own_link = page.locator('a:has-text("Ownership"), a[href*="ownership"]').first
            if await own_link.count() > 0:
                await own_link.click()
                await page.wait_for_load_state("networkidle", timeout=15000)

            # Institutional ownership percentage
            inst_el = page.locator('*:has-text("Institutional")').first
            if await inst_el.count() > 0:
                text = (await inst_el.text_content() or "").strip()
                ownership["institutional_pct"] = self._parse_percentage(text)

            # Insider transactions table
            insider_rows = page.locator("table tr:has-text('Insider')")
            for i in range(min(await insider_rows.count(), 10)):
                cells = await insider_rows.nth(i).locator("td").all_text_contents()
                if len(cells) >= 3:
                    ownership["insider_transactions"].append({
                        "name": cells[0].strip(),
                        "type": cells[1].strip(),
                        "value": cells[2].strip(),
                    })

        except Exception as e:
            logger.warning(f"Could not extract ownership for {ticker}: {e}")

        return ownership

    async def _extract_debt(self, browser: BerkeleyBrowserBase, ticker: str) -> dict:
        """Extract debt and capital structure data."""
        debt = {
            "total_debt": None,
            "debt_to_equity": None,
        }

        try:
            page = browser.page

            # Look for debt metrics on financials/balance sheet
            for label, key in [
                ("Total Debt", "total_debt"),
                ("Debt/Equity", "debt_to_equity"),
                ("Debt to Equity", "debt_to_equity"),
            ]:
                el = page.locator(f'*:has-text("{label}")').first
                if await el.count() > 0:
                    text = (await el.text_content() or "").strip()
                    debt[key] = self._parse_financial_value(text)

        except Exception as e:
            logger.warning(f"Could not extract debt data for {ticker}: {e}")

        return debt

    async def _extract_peers(self, browser: BerkeleyBrowserBase, ticker: str) -> dict:
        """Extract industry comparable metrics."""
        peers = {
            "sector_avg_pe": None,
            "sector_avg_revenue_growth": None,
        }

        try:
            page = browser.page

            # Navigate to comparables/peers section
            peer_link = page.locator(
                'a:has-text("Compar"), a:has-text("Peers"), a[href*="peer"]'
            ).first
            if await peer_link.count() > 0:
                await peer_link.click()
                await page.wait_for_load_state("networkidle", timeout=15000)

            # Look for sector/industry averages
            pe_el = page.locator('*:has-text("Sector P/E"), *:has-text("Industry P/E")').first
            if await pe_el.count() > 0:
                text = (await pe_el.text_content() or "").strip()
                peers["sector_avg_pe"] = self._parse_financial_value(text)

            growth_el = page.locator('*:has-text("Revenue Growth")').first
            if await growth_el.count() > 0:
                text = (await growth_el.text_content() or "").strip()
                peers["sector_avg_revenue_growth"] = self._parse_percentage(text)

        except Exception as e:
            logger.warning(f"Could not extract peer data for {ticker}: {e}")

        return peers

    # ---- Parsing helpers ----

    @staticmethod
    def _parse_financial_value(text: str) -> float | None:
        """Parse a financial value string like '$1,234.56M' into a number."""
        if not text:
            return None
        text = text.replace(",", "").replace("$", "").strip()

        multiplier = 1
        if text.endswith("B"):
            multiplier = 1_000_000_000
            text = text[:-1]
        elif text.endswith("M"):
            multiplier = 1_000_000
            text = text[:-1]
        elif text.endswith("K"):
            multiplier = 1_000
            text = text[:-1]

        try:
            return float(text) * multiplier
        except ValueError:
            return None

    @staticmethod
    def _parse_percentage(text: str) -> float | None:
        """Parse a percentage string like '62.5%' into 0.625."""
        if not text:
            return None
        text = text.replace("%", "").strip()
        try:
            return float(text) / 100
        except ValueError:
            return None

    @staticmethod
    def _extract_date_from_text(text: str) -> str | None:
        """Try to find a date in text. Returns ISO date string or None."""
        import re
        # Match patterns like 2026-05-05, May 5 2026, 05/05/2026
        patterns = [
            r"\d{4}-\d{2}-\d{2}",
            r"\d{2}/\d{2}/\d{4}",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        return None
