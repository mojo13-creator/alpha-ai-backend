"""
IBISWorld scraper via Berkeley library proxy.
Extracts industry-level context for the sector a stock operates in.
"""

import logging
import sqlite3
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yfinance as yf

from data_collection.berkeley.browser_base import BerkeleyBrowserBase

logger = logging.getLogger(__name__)

IBISWORLD_BASE = "https://www-ibisworld-com.libproxy.berkeley.edu"
DB_PATH = Path(__file__).resolve().parent.parent.parent / "stock_data.db"
CACHE_TTL_HOURS = 168  # 7 days


class IBISWorldScraper:
    """Scrapes industry reports from IBISWorld via Berkeley library proxy."""

    def __init__(self):
        self._ensure_cache_table()

    def _ensure_cache_table(self):
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ibisworld_cache (
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
            "SELECT data, fetched_at FROM ibisworld_cache WHERE cache_key = ?", (key,)
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
            "INSERT OR REPLACE INTO ibisworld_cache (cache_key, data, fetched_at) VALUES (?, ?, ?)",
            (key, json.dumps(data), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        conn.close()

    def _get_industry(self, ticker: str) -> tuple[str | None, str | None]:
        """Use yfinance to look up a ticker's industry and sector."""
        try:
            info = yf.Ticker(ticker).info
            return info.get("industry"), info.get("sector")
        except Exception as e:
            logger.warning(f"Could not look up industry for {ticker}: {e}")
            return None, None

    async def get_industry_data(self, ticker: str) -> dict | None:
        """Fetch IBISWorld industry data for the sector a ticker operates in."""
        ticker = ticker.upper()
        cache_key = f"ibisworld_{ticker}"
        cached = self._get_cached(cache_key)
        if cached:
            logger.info(f"IBISWorld cache hit for {ticker}")
            return cached

        industry, sector = self._get_industry(ticker)
        if not industry:
            logger.warning(f"No industry found for {ticker}, skipping IBISWorld")
            return None

        logger.info(f"Scraping IBISWorld for {ticker} industry: {industry}...")

        try:
            async with BerkeleyBrowserBase() as browser:
                result = await self._scrape_industry(browser, ticker, industry, sector)
            if result:
                self._save_cache(cache_key, result)
            return result
        except Exception as e:
            logger.error(f"IBISWorld scrape failed for {ticker}: {e}")
            return None

    async def _scrape_industry(
        self, browser: BerkeleyBrowserBase, ticker: str, industry: str, sector: str | None
    ) -> dict | None:
        page = browser.page

        # Search for the industry
        search_url = f"{IBISWORLD_BASE}/united-states/search?query={industry.replace(' ', '+')}"
        if not await browser.navigate(search_url):
            logger.error("Failed to load IBISWorld search")
            return None

        await page.wait_for_load_state("networkidle", timeout=20000)

        # Click first matching industry report link
        try:
            report_link = page.locator(
                'a[href*="/united-states/market-research-reports/"], '
                'a[href*="/industry/"], '
                'a.report-link, '
                '.search-results a'
            ).first
            if await report_link.count() > 0:
                await report_link.click()
                await page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            pass

        result = {
            "ticker": ticker,
            "source": "ibisworld",
            "industry": industry,
            "sector": sector,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "revenue": None,
            "growth_rate": None,
            "outlook": None,
            "key_success_factors": [],
            "major_players": [],
            "threats": [],
            "opportunities": [],
        }

        # Extract industry revenue
        try:
            rev_el = page.locator(
                '*:has-text("Industry Revenue"), *:has-text("Revenue"), '
                '.industry-revenue, .key-stat'
            ).first
            if await rev_el.count() > 0:
                text = (await rev_el.text_content() or "").strip()
                result["revenue"] = text
        except Exception:
            pass

        # Extract growth rate
        try:
            growth_el = page.locator(
                '*:has-text("Annual Growth"), *:has-text("Growth Rate"), '
                '*:has-text("CAGR"), .growth-rate'
            ).first
            if await growth_el.count() > 0:
                text = (await growth_el.text_content() or "").strip()
                result["growth_rate"] = text
        except Exception:
            pass

        # Extract industry outlook
        try:
            outlook_el = page.locator(
                '*:has-text("Industry Outlook"), *:has-text("Outlook"), '
                '.industry-outlook, .outlook-section'
            ).first
            if await outlook_el.count() > 0:
                text = (await outlook_el.text_content() or "").strip()
                result["outlook"] = text[:500]
        except Exception:
            pass

        # Key success factors
        try:
            ksf_items = page.locator(
                '.key-success-factors li, '
                'section:has-text("Key Success Factors") li, '
                'div:has-text("Key Success Factors") ul li'
            )
            count = await ksf_items.count()
            for i in range(min(count, 10)):
                text = (await ksf_items.nth(i).text_content() or "").strip()
                if text:
                    result["key_success_factors"].append(text)
        except Exception:
            pass

        # Major players / market share
        try:
            player_rows = page.locator(
                '.major-players tr, '
                'section:has-text("Major Companies") tr, '
                'table:has-text("Market Share") tr'
            )
            count = await player_rows.count()
            for i in range(min(count, 10)):
                cells = await player_rows.nth(i).locator("td").all_text_contents()
                if cells:
                    result["major_players"].append({
                        "name": cells[0].strip() if len(cells) > 0 else "",
                        "market_share": cells[1].strip() if len(cells) > 1 else "",
                    })
        except Exception:
            pass

        # Threats and opportunities
        for label, key in [("Threat", "threats"), ("Opportunit", "opportunities")]:
            try:
                items = page.locator(f'section:has-text("{label}") li, div:has-text("{label}") ul li')
                count = await items.count()
                for i in range(min(count, 5)):
                    text = (await items.nth(i).text_content() or "").strip()
                    if text:
                        result[key].append(text)
            except Exception:
                pass

        return result
