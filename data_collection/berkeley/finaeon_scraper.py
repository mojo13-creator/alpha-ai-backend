"""
Finaeon (Global Financial Database) scraper via Berkeley library proxy.
Extracts deep historical price data, sector correlations, commodity/forex data.
"""

import logging
import sqlite3
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yfinance as yf

from data_collection.berkeley.browser_base import BerkeleyBrowserBase

logger = logging.getLogger(__name__)

FINAEON_BASE = "https://www-finaeon-com.libproxy.berkeley.edu"
DB_PATH = Path(__file__).resolve().parent.parent.parent / "stock_data.db"
CACHE_TTL_HOURS = 24


class FinaeonScraper:
    """Scrapes historical financial data from Finaeon via Berkeley library proxy."""

    def __init__(self):
        self._ensure_cache_table()

    def _ensure_cache_table(self):
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS finaeon_cache (
                cache_key TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                fetched_at TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    def _get_cached(self, key: str) -> dict | None:
        conn = sqlite3.connect(str(DB_PATH))
        row = conn.execute(
            "SELECT data, fetched_at FROM finaeon_cache WHERE cache_key = ?", (key,)
        ).fetchone()
        conn.close()
        if not row:
            return None
        fetched_at = datetime.fromisoformat(row[1])
        if datetime.now(timezone.utc) - fetched_at > timedelta(hours=CACHE_TTL_HOURS):
            return None
        return json.loads(row[0])

    def _save_cache(self, key: str, data: dict):
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute(
            "INSERT OR REPLACE INTO finaeon_cache (cache_key, data, fetched_at) VALUES (?, ?, ?)",
            (key, json.dumps(data), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        conn.close()

    def _get_company_context(self, ticker: str) -> dict:
        """Look up sector and international exposure via yfinance."""
        try:
            info = yf.Ticker(ticker).info
            return {
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "country": info.get("country", "United States"),
                "currency": info.get("currency", "USD"),
            }
        except Exception:
            return {"sector": None, "industry": None, "country": "United States", "currency": "USD"}

    async def get_historical_data(self, ticker: str) -> dict | None:
        """Fetch deep historical and correlation data from Finaeon."""
        ticker = ticker.upper()
        cache_key = f"finaeon_{ticker}"
        cached = self._get_cached(cache_key)
        if cached:
            logger.info(f"Finaeon cache hit for {ticker}")
            return cached

        context = self._get_company_context(ticker)
        logger.info(f"Scraping Finaeon for {ticker}...")

        try:
            async with BerkeleyBrowserBase() as browser:
                result = await self._scrape_data(browser, ticker, context)
            if result:
                self._save_cache(cache_key, result)
            return result
        except Exception as e:
            logger.error(f"Finaeon scrape failed for {ticker}: {e}")
            return None

    async def _scrape_data(
        self, browser: BerkeleyBrowserBase, ticker: str, context: dict
    ) -> dict | None:
        page = browser.page

        result = {
            "ticker": ticker,
            "source": "finaeon",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "historical_prices": [],
            "sector_index": {},
            "commodity_prices": [],
            "currency_data": [],
        }

        # Search for the ticker's historical prices
        search_url = f"{FINAEON_BASE}/search?q={ticker}"
        if not await browser.navigate(search_url):
            # Try alternate URL patterns
            if not await browser.navigate(f"{FINAEON_BASE}/data/search?query={ticker}"):
                logger.error("Failed to load Finaeon")
                return None

        await page.wait_for_load_state("networkidle", timeout=20000)

        # Click first matching result
        try:
            result_link = page.locator(
                'a:has-text("' + ticker + '"), .search-result a, '
                'table a, .result-item a'
            ).first
            if await result_link.count() > 0:
                await result_link.click()
                await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        # Extract historical price data from tables
        try:
            price_rows = page.locator(
                'table tr:has(td), .data-table tr, '
                '.price-history tr'
            )
            count = await price_rows.count()
            for i in range(min(count, 100)):
                cells = await price_rows.nth(i).locator("td").all_text_contents()
                if len(cells) >= 2:
                    result["historical_prices"].append({
                        "date": cells[0].strip(),
                        "close": cells[1].strip(),
                        "volume": cells[2].strip() if len(cells) > 2 else None,
                    })
        except Exception as e:
            logger.warning(f"Finaeon price extraction failed: {e}")

        # Search for sector index data
        sector = context.get("sector")
        if sector:
            sector_url = f"{FINAEON_BASE}/search?q={sector.replace(' ', '+')}+index"
            if await browser.navigate(sector_url):
                await page.wait_for_load_state("networkidle", timeout=15000)

                try:
                    # Extract sector index performance
                    index_link = page.locator('.search-result a, table a').first
                    if await index_link.count() > 0:
                        await index_link.click()
                        await page.wait_for_load_state("networkidle", timeout=15000)

                        perf_el = page.locator(
                            '*:has-text("Return"), *:has-text("Performance"), '
                            '.summary-stats'
                        ).first
                        if await perf_el.count() > 0:
                            result["sector_index"]["performance"] = (
                                await perf_el.text_content() or ""
                            ).strip()[:500]
                except Exception:
                    pass

        # Search for relevant commodity data based on sector
        commodity_sectors = {
            "Energy": "crude oil",
            "Basic Materials": "commodities index",
            "Technology": "semiconductor index",
            "Financial Services": "treasury yield",
            "Healthcare": "healthcare index",
            "Consumer Cyclical": "consumer confidence",
            "Consumer Defensive": "consumer staples index",
            "Industrials": "industrial production",
            "Real Estate": "housing index",
            "Utilities": "natural gas",
            "Communication Services": "communications index",
        }

        commodity_query = commodity_sectors.get(sector, "")
        if commodity_query:
            commodity_url = f"{FINAEON_BASE}/search?q={commodity_query.replace(' ', '+')}"
            if await browser.navigate(commodity_url):
                await page.wait_for_load_state("networkidle", timeout=15000)

                try:
                    comm_rows = page.locator('table tr:has(td)').first
                    if await comm_rows.count() > 0:
                        cells = await comm_rows.locator("td").all_text_contents()
                        if cells:
                            result["commodity_prices"].append({
                                "name": commodity_query,
                                "latest": cells[1].strip() if len(cells) > 1 else "",
                            })
                except Exception:
                    pass

        # Currency data for international companies
        currency = context.get("currency", "USD")
        if currency != "USD":
            fx_url = f"{FINAEON_BASE}/search?q=USD+{currency}+exchange+rate"
            if await browser.navigate(fx_url):
                await page.wait_for_load_state("networkidle", timeout=15000)

                try:
                    fx_el = page.locator('table tr:has(td)').first
                    if await fx_el.count() > 0:
                        cells = await fx_el.locator("td").all_text_contents()
                        if cells:
                            result["currency_data"].append({
                                "pair": f"USD/{currency}",
                                "rate": cells[1].strip() if len(cells) > 1 else "",
                            })
                except Exception:
                    pass

        return result
