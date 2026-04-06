"""
Statista scraper via Berkeley library proxy.
Extracts market sizing, consumer trends, and industry statistics.
"""

import logging
import sqlite3
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yfinance as yf

from data_collection.berkeley.browser_base import BerkeleyBrowserBase

logger = logging.getLogger(__name__)

STATISTA_BASE = "https://www-statista-com.libproxy.berkeley.edu"
DB_PATH = Path(__file__).resolve().parent.parent.parent / "stock_data.db"
CACHE_TTL_HOURS = 168  # 7 days


class StatistaScraper:
    """Scrapes market and industry statistics from Statista via Berkeley proxy."""

    def __init__(self):
        self._ensure_cache_table()

    def _ensure_cache_table(self):
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS statista_cache (
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
            "SELECT data, fetched_at FROM statista_cache WHERE cache_key = ?", (key,)
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
            "INSERT OR REPLACE INTO statista_cache (cache_key, data, fetched_at) VALUES (?, ?, ?)",
            (key, json.dumps(data), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        conn.close()

    def _get_sector(self, ticker: str) -> tuple[str | None, str | None]:
        """Look up sector and industry via yfinance."""
        try:
            info = yf.Ticker(ticker).info
            return info.get("sector"), info.get("industry")
        except Exception:
            return None, None

    async def get_market_data(self, ticker: str) -> dict | None:
        """Fetch market sizing and industry statistics from Statista."""
        ticker = ticker.upper()
        cache_key = f"statista_{ticker}"
        cached = self._get_cached(cache_key)
        if cached:
            logger.info(f"Statista cache hit for {ticker}")
            return cached

        sector, industry = self._get_sector(ticker)
        if not industry and not sector:
            logger.warning(f"No sector/industry found for {ticker}, skipping Statista")
            return None

        logger.info(f"Scraping Statista for {ticker} (industry={industry})...")

        try:
            async with BerkeleyBrowserBase() as browser:
                result = await self._scrape_market(browser, ticker, sector, industry)
            if result:
                self._save_cache(cache_key, result)
            return result
        except Exception as e:
            logger.error(f"Statista scrape failed for {ticker}: {e}")
            return None

    async def _scrape_market(
        self, browser: BerkeleyBrowserBase, ticker: str, sector: str | None, industry: str | None
    ) -> dict | None:
        page = browser.page

        result = {
            "ticker": ticker,
            "source": "statista",
            "sector": sector,
            "industry": industry,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "market_size": None,
            "market_forecast": None,
            "consumer_trends": [],
            "competitive_landscape": [],
            "revenue_benchmarks": [],
        }

        search_term = industry or sector or ""

        # Search for market size
        search_url = f"{STATISTA_BASE}/search/?q={search_term.replace(' ', '+')}+market+size"
        if not await browser.navigate(search_url):
            logger.error("Failed to load Statista search")
            return None

        await page.wait_for_load_state("networkidle", timeout=20000)

        # Click first relevant result for market size
        try:
            stat_link = page.locator(
                '.statisticLink, .searchResultLink, '
                'a[href*="/statistics/"], a[href*="/outlook/"], '
                '.search-results a'
            ).first
            if await stat_link.count() > 0:
                await stat_link.click()
                await page.wait_for_load_state("networkidle", timeout=15000)

                # Extract main statistic value
                stat_value = page.locator(
                    '.statisticValue, .statistic__value, '
                    '.mainStat, #mainStatistic, '
                    'h2 + .value, .statistic-header + .value'
                ).first
                if await stat_value.count() > 0:
                    result["market_size"] = (await stat_value.text_content() or "").strip()

                # Extract description/context
                desc_el = page.locator(
                    '.statisticDescription, .statistic__description, '
                    '.statistic-description, article p'
                ).first
                if await desc_el.count() > 0:
                    text = (await desc_el.text_content() or "").strip()
                    result["market_forecast"] = text[:500]
        except Exception as e:
            logger.warning(f"Statista market size extraction failed: {e}")

        # Search for consumer/industry trends
        trends_url = f"{STATISTA_BASE}/search/?q={search_term.replace(' ', '+')}+trends"
        if await browser.navigate(trends_url):
            await page.wait_for_load_state("networkidle", timeout=15000)

            try:
                trend_results = page.locator(
                    '.statisticLink, .searchResultLink, '
                    'a[href*="/statistics/"], .search-results a'
                )
                count = await trend_results.count()
                for i in range(min(count, 5)):
                    title_text = (await trend_results.nth(i).text_content() or "").strip()
                    href = await trend_results.nth(i).get_attribute("href") or ""
                    if title_text:
                        result["consumer_trends"].append({
                            "title": title_text[:200],
                            "url": href,
                        })
            except Exception:
                pass

        # Search for competitive landscape / revenue benchmarks
        comp_url = f"{STATISTA_BASE}/search/?q={search_term.replace(' ', '+')}+revenue+companies"
        if await browser.navigate(comp_url):
            await page.wait_for_load_state("networkidle", timeout=15000)

            try:
                # Click first result about company revenues
                comp_link = page.locator(
                    'a[href*="/statistics/"]:has-text("revenue"), '
                    'a[href*="/statistics/"]:has-text("companies"), '
                    '.search-results a'
                ).first
                if await comp_link.count() > 0:
                    await comp_link.click()
                    await page.wait_for_load_state("networkidle", timeout=15000)

                    # Extract data from the chart/table
                    data_rows = page.locator(
                        '.chartTable tr, .statistic__table tr, '
                        'table tr:has(td), .data-table tr'
                    )
                    count = await data_rows.count()
                    for i in range(min(count, 10)):
                        cells = await data_rows.nth(i).locator("td, th").all_text_contents()
                        if len(cells) >= 2:
                            result["competitive_landscape"].append({
                                "company": cells[0].strip(),
                                "value": cells[1].strip(),
                            })
            except Exception:
                pass

        # Search for growth/revenue benchmarks
        bench_url = f"{STATISTA_BASE}/search/?q={search_term.replace(' ', '+')}+growth+forecast"
        if await browser.navigate(bench_url):
            await page.wait_for_load_state("networkidle", timeout=15000)

            try:
                bench_results = page.locator(
                    '.statisticLink, .searchResultLink, '
                    'a[href*="/statistics/"], a[href*="/outlook/"]'
                )
                count = await bench_results.count()
                for i in range(min(count, 3)):
                    title_text = (await bench_results.nth(i).text_content() or "").strip()
                    if title_text:
                        result["revenue_benchmarks"].append(title_text[:200])
            except Exception:
                pass

        return result
