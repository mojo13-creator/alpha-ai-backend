"""
FitchConnect scraper via Berkeley library proxy.
Extracts macro/country risk context and credit outlooks.
"""

import logging
import sqlite3
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yfinance as yf

from data_collection.berkeley.browser_base import BerkeleyBrowserBase

logger = logging.getLogger(__name__)

FITCH_BASE = "https://app-fitchconnect-com.libproxy.berkeley.edu"
DB_PATH = Path(__file__).resolve().parent.parent.parent / "stock_data.db"
CACHE_TTL_HOURS = 168  # 7 days


class FitchScraper:
    """Scrapes macro context and credit data from FitchConnect via Berkeley proxy."""

    def __init__(self):
        self._ensure_cache_table()

    def _ensure_cache_table(self):
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fitch_cache (
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
            "SELECT data, fetched_at FROM fitch_cache WHERE cache_key = ?", (key,)
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
            "INSERT OR REPLACE INTO fitch_cache (cache_key, data, fetched_at) VALUES (?, ?, ?)",
            (key, json.dumps(data), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        conn.close()

    def _get_company_context(self, ticker: str) -> tuple[str | None, str | None]:
        """Look up company's country and sector via yfinance."""
        try:
            info = yf.Ticker(ticker).info
            return info.get("country", "United States"), info.get("sector")
        except Exception:
            return "United States", None

    async def get_macro_context(self, ticker: str) -> dict | None:
        """Fetch FitchConnect macro/credit context for a ticker's market."""
        ticker = ticker.upper()
        cache_key = f"fitch_{ticker}"
        cached = self._get_cached(cache_key)
        if cached:
            logger.info(f"FitchConnect cache hit for {ticker}")
            return cached

        country, sector = self._get_company_context(ticker)
        logger.info(f"Scraping FitchConnect for {ticker} (country={country}, sector={sector})...")

        try:
            async with BerkeleyBrowserBase() as browser:
                result = await self._scrape_fitch(browser, ticker, country, sector)
            if result:
                self._save_cache(cache_key, result)
            return result
        except Exception as e:
            logger.error(f"FitchConnect scrape failed for {ticker}: {e}")
            return None

    async def _scrape_fitch(
        self, browser: BerkeleyBrowserBase, ticker: str, country: str | None, sector: str | None
    ) -> dict | None:
        page = browser.page

        result = {
            "ticker": ticker,
            "source": "fitch_connect",
            "country": country,
            "sector": sector,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "country_outlook": None,
            "sector_credit_outlook": None,
            "company_rating": None,
            "macro_risk_factors": [],
        }

        # Search for company-specific rating first
        search_url = f"{FITCH_BASE}/search?query={ticker}"
        if not await browser.navigate(search_url):
            logger.error("Failed to load FitchConnect search")
            return None

        await page.wait_for_load_state("networkidle", timeout=20000)

        # Try to find a company-specific rating
        try:
            rating_link = page.locator(
                f'a:has-text("{ticker}"), .search-result a, .entity-link'
            ).first
            if await rating_link.count() > 0:
                await rating_link.click()
                await page.wait_for_load_state("networkidle", timeout=15000)

                # Extract company rating
                rating_el = page.locator(
                    '.rating-value, .issuer-rating, '
                    '*:has-text("Long-Term IDR"), *:has-text("Rating")'
                ).first
                if await rating_el.count() > 0:
                    result["company_rating"] = (await rating_el.text_content() or "").strip()
        except Exception:
            pass

        # Search for country economic outlook
        if country:
            country_url = f"{FITCH_BASE}/search?query={country.replace(' ', '+')}+economic+outlook"
            if await browser.navigate(country_url):
                await page.wait_for_load_state("networkidle", timeout=15000)

                try:
                    outlook_link = page.locator(
                        'a:has-text("Economic Outlook"), a:has-text("Country Report"), '
                        '.search-result a'
                    ).first
                    if await outlook_link.count() > 0:
                        await outlook_link.click()
                        await page.wait_for_load_state("networkidle", timeout=15000)

                        # Extract outlook summary
                        summary_el = page.locator(
                            '.report-summary, .executive-summary, '
                            'section:has-text("Summary") p, article p'
                        ).first
                        if await summary_el.count() > 0:
                            text = (await summary_el.text_content() or "").strip()
                            result["country_outlook"] = text[:1000]
                except Exception:
                    pass

        # Search for sector credit outlook
        if sector:
            sector_url = f"{FITCH_BASE}/search?query={sector.replace(' ', '+')}+credit+outlook"
            if await browser.navigate(sector_url):
                await page.wait_for_load_state("networkidle", timeout=15000)

                try:
                    sector_link = page.locator(
                        'a:has-text("Credit Outlook"), a:has-text("Sector"), '
                        '.search-result a'
                    ).first
                    if await sector_link.count() > 0:
                        await sector_link.click()
                        await page.wait_for_load_state("networkidle", timeout=15000)

                        summary_el = page.locator(
                            '.report-summary, .executive-summary, article p'
                        ).first
                        if await summary_el.count() > 0:
                            text = (await summary_el.text_content() or "").strip()
                            result["sector_credit_outlook"] = text[:1000]
                except Exception:
                    pass

        # Extract macro risk factors from any loaded report
        try:
            risk_items = page.locator(
                'section:has-text("Risk") li, '
                'div:has-text("Key Risk") li, '
                '.risk-factors li'
            )
            count = await risk_items.count()
            for i in range(min(count, 10)):
                text = (await risk_items.nth(i).text_content() or "").strip()
                if text:
                    result["macro_risk_factors"].append(text)
        except Exception:
            pass

        return result
