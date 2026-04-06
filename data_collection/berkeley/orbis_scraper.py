"""
Orbis (Bureau van Dijk) scraper via Berkeley library proxy.
Extracts deep company financials, subsidiary structure, and comparable companies.
"""

import logging
import sqlite3
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from data_collection.berkeley.browser_base import BerkeleyBrowserBase

logger = logging.getLogger(__name__)

ORBIS_BASE = "https://orbis-bvdinfo-com.libproxy.berkeley.edu"
DB_PATH = Path(__file__).resolve().parent.parent.parent / "stock_data.db"
CACHE_TTL_HOURS = 24


class OrbisScraper:
    """Scrapes company data from Orbis via Berkeley library proxy."""

    def __init__(self):
        self._ensure_cache_table()

    def _ensure_cache_table(self):
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orbis_cache (
                ticker TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                fetched_at TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    def _get_cached(self, ticker: str) -> dict | None:
        conn = sqlite3.connect(str(DB_PATH))
        row = conn.execute(
            "SELECT data, fetched_at FROM orbis_cache WHERE ticker = ?", (ticker,)
        ).fetchone()
        conn.close()
        if not row:
            return None
        fetched_at = datetime.fromisoformat(row[1])
        if datetime.now(timezone.utc) - fetched_at > timedelta(hours=CACHE_TTL_HOURS):
            return None
        return json.loads(row[0])

    def _save_cache(self, ticker: str, data: dict):
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute(
            "INSERT OR REPLACE INTO orbis_cache (ticker, data, fetched_at) VALUES (?, ?, ?)",
            (ticker, json.dumps(data), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        conn.close()

    async def get_company_data(self, ticker: str) -> dict | None:
        """Fetch detailed company data from Orbis."""
        ticker = ticker.upper()
        cached = self._get_cached(ticker)
        if cached:
            logger.info(f"Orbis cache hit for {ticker}")
            return cached

        logger.info(f"Scraping Orbis for {ticker}...")

        try:
            async with BerkeleyBrowserBase() as browser:
                result = await self._scrape_company(browser, ticker)
            if result:
                self._save_cache(ticker, result)
            return result
        except Exception as e:
            logger.error(f"Orbis scrape failed for {ticker}: {e}")
            return None

    async def _scrape_company(self, browser: BerkeleyBrowserBase, ticker: str) -> dict | None:
        page = browser.page

        # Navigate to Orbis and search for the company
        search_url = f"{ORBIS_BASE}/version-20241014/orbis/1/Companies/Search"
        if not await browser.navigate(search_url):
            # Fallback: try the main page
            if not await browser.navigate(ORBIS_BASE):
                logger.error("Failed to load Orbis")
                return None

        await page.wait_for_load_state("networkidle", timeout=20000)

        # Enter search query
        try:
            search_input = page.locator(
                'input[name="search"], input[placeholder*="company"], '
                'input[type="text"], #search-input'
            ).first
            if await search_input.count() > 0:
                await search_input.fill(ticker)
                # Submit search
                submit = page.locator(
                    'button[type="submit"], button:has-text("Search"), '
                    'input[type="submit"], .search-button'
                ).first
                if await submit.count() > 0:
                    await submit.click()
                else:
                    await search_input.press("Enter")
                await page.wait_for_load_state("networkidle", timeout=20000)
        except Exception as e:
            logger.warning(f"Orbis search input failed: {e}")

        # Click first result
        try:
            result_link = page.locator(
                '.company-name a, .search-results a, '
                'table.results a, td a'
            ).first
            if await result_link.count() > 0:
                await result_link.click()
                await page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            pass

        result = {
            "ticker": ticker,
            "source": "orbis",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "financials": {},
            "subsidiaries": [],
            "beneficial_ownership": [],
            "comparables": [],
        }

        # Extract financials
        try:
            fin_link = page.locator(
                'a:has-text("Financial"), a[href*="financials"], '
                '.nav-item:has-text("Financial")'
            ).first
            if await fin_link.count() > 0:
                await fin_link.click()
                await page.wait_for_load_state("networkidle", timeout=15000)

            # Parse financial table rows
            fin_rows = page.locator(
                'table.financial tr, table[class*="financial"] tr, '
                '.financial-data tr'
            )
            count = await fin_rows.count()
            for i in range(count):
                row = fin_rows.nth(i)
                cells = await row.locator("td, th").all_text_contents()
                if len(cells) >= 2:
                    label = cells[0].strip().lower()
                    values = [c.strip() for c in cells[1:]]
                    if any(kw in label for kw in ["revenue", "turnover", "sales"]):
                        result["financials"]["revenue"] = values
                    elif "net income" in label or "profit" in label:
                        result["financials"]["net_income"] = values
                    elif "total assets" in label:
                        result["financials"]["total_assets"] = values
                    elif "total liab" in label:
                        result["financials"]["total_liabilities"] = values
                    elif "equity" in label and "debt" not in label:
                        result["financials"]["equity"] = values
                    elif "employees" in label:
                        result["financials"]["employees"] = values
        except Exception as e:
            logger.warning(f"Orbis financials extraction failed: {e}")

        # Extract subsidiaries
        try:
            sub_link = page.locator(
                'a:has-text("Subsidiar"), a:has-text("Corporate structure"), '
                'a[href*="subsidiaries"]'
            ).first
            if await sub_link.count() > 0:
                await sub_link.click()
                await page.wait_for_load_state("networkidle", timeout=15000)

                sub_rows = page.locator(
                    'table tr:has(td), .subsidiary-list li, '
                    '.corporate-tree .node'
                )
                count = await sub_rows.count()
                for i in range(min(count, 20)):
                    cells = await sub_rows.nth(i).locator("td").all_text_contents()
                    if cells:
                        result["subsidiaries"].append({
                            "name": cells[0].strip() if len(cells) > 0 else "",
                            "country": cells[1].strip() if len(cells) > 1 else "",
                            "ownership_pct": cells[2].strip() if len(cells) > 2 else "",
                        })
        except Exception:
            pass

        # Extract beneficial ownership
        try:
            own_link = page.locator(
                'a:has-text("Ownership"), a:has-text("Shareholders"), '
                'a[href*="ownership"]'
            ).first
            if await own_link.count() > 0:
                await own_link.click()
                await page.wait_for_load_state("networkidle", timeout=15000)

                own_rows = page.locator('table tr:has(td)')
                count = await own_rows.count()
                for i in range(min(count, 15)):
                    cells = await own_rows.nth(i).locator("td").all_text_contents()
                    if len(cells) >= 2:
                        result["beneficial_ownership"].append({
                            "name": cells[0].strip(),
                            "stake": cells[1].strip() if len(cells) > 1 else "",
                            "country": cells[2].strip() if len(cells) > 2 else "",
                        })
        except Exception:
            pass

        # Extract comparable companies
        try:
            comp_link = page.locator(
                'a:has-text("Compar"), a:has-text("Peer"), '
                'a[href*="comparable"]'
            ).first
            if await comp_link.count() > 0:
                await comp_link.click()
                await page.wait_for_load_state("networkidle", timeout=15000)

                comp_rows = page.locator('table tr:has(td)')
                count = await comp_rows.count()
                for i in range(min(count, 10)):
                    cells = await comp_rows.nth(i).locator("td").all_text_contents()
                    if cells:
                        result["comparables"].append({
                            "name": cells[0].strip() if len(cells) > 0 else "",
                            "revenue": cells[1].strip() if len(cells) > 1 else "",
                            "country": cells[2].strip() if len(cells) > 2 else "",
                        })
        except Exception:
            pass

        return result
