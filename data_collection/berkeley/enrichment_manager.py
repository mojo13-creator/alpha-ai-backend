"""
Single entry point for all Berkeley institutional data enrichment.
Other modules call this, not individual scrapers directly.
"""

import logging

from data_collection.berkeley.capiq_scraper import CapIQScraper
from data_collection.berkeley.wrds_client import WRDSClient
from data_collection.berkeley.ibisworld_scraper import IBISWorldScraper
from data_collection.berkeley.fitch_scraper import FitchScraper
from data_collection.berkeley.orbis_scraper import OrbisScraper
from data_collection.berkeley.finaeon_scraper import FinaeonScraper
from data_collection.berkeley.statista_scraper import StatistaScraper

logger = logging.getLogger(__name__)


class BerkeleyEnrichmentManager:
    """Aggregates data from all available Berkeley database sources."""

    def __init__(self):
        self.capiq = CapIQScraper()
        self.wrds = WRDSClient()
        self.ibisworld = IBISWorldScraper()
        self.fitch = FitchScraper()
        self.orbis = OrbisScraper()
        self.finaeon = FinaeonScraper()
        self.statista = StatistaScraper()

    async def enrich(self, ticker: str) -> dict:
        """
        Pull enrichment data from all available Berkeley sources.
        Returns combined dict. Gracefully handles any source being unavailable.
        """
        ticker = ticker.upper()
        result = {}

        # Each source wrapped in try/except — one failure doesn't kill the others
        # Async scrapers (Playwright-based)
        async_scrapers = [
            ("capital_iq", self.capiq.get_company_data),
            ("ibisworld", self.ibisworld.get_industry_data),
            ("fitch", self.fitch.get_macro_context),
            ("orbis", self.orbis.get_company_data),
            ("finaeon", self.finaeon.get_historical_data),
            ("statista", self.statista.get_market_data),
        ]

        for name, scraper_method in async_scrapers:
            try:
                data = await scraper_method(ticker)
                if data:
                    result[name] = data
            except Exception as e:
                logger.warning(f"{name} scraper failed for {ticker}: {e}")

        # Sync scrapers (WRDS uses a direct DB connection, not Playwright)
        sync_scrapers = [
            ("wrds", self.wrds.get_stock_data),
        ]

        for name, scraper_method in sync_scrapers:
            try:
                data = scraper_method(ticker)
                if data:
                    result[name] = data
            except Exception as e:
                logger.warning(f"{name} scraper failed for {ticker}: {e}")

        if result:
            logger.info(f"Berkeley enrichment for {ticker}: sources={list(result.keys())}")
        else:
            logger.info(f"No Berkeley enrichment data available for {ticker}")

        return result

    def close(self):
        """Clean up resources."""
        self.wrds.close()
