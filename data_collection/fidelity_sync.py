"""
Fidelity Sync Service — pulls Fidelity positions into Alpha AI portfolio.

Syncs real brokerage holdings into the portfolio table with automatic
tier classification. READ-ONLY — no trades are ever placed.
"""

import logging
from database.db_manager import DatabaseManager
from data_collection.fidelity_client import FidelityClient

logger = logging.getLogger(__name__)

# ETFs and blue chips → long_term tier
# NOTE: Expand this list as needed — everything else defaults to midcap_active
LONG_TERM_TICKERS = {
    # Major index ETFs
    "VOO", "VTI", "QQQ", "SPY", "IWM", "VGT", "SCHD", "DIA", "VEA", "VWO",
    "VXUS", "BND", "AGG", "VNQ", "ARKK",
    # Blue chip mega-caps
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "BRK.B", "JNJ", "JPM",
    "V", "MA", "UNH", "PG", "HD", "KO", "PEP", "COST", "WMT",
    "NVDA", "META", "TSLA", "AVGO", "LLY",
}


class FidelitySyncService:
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.fidelity_client = FidelityClient()

    def sync_positions(self, headless: bool = True) -> dict:
        """
        Pull Fidelity positions and sync to Alpha AI portfolio.
        Set headless=False for first run to handle 2FA in the browser window.
        Returns status dict with sync results.
        """
        if not self.fidelity_client.credentials_available:
            return {
                "status": "no_credentials",
                "message": "Fidelity credentials not configured in .env",
            }

        # Connect to Fidelity
        conn_result = self.fidelity_client.connect(headless=headless)
        if conn_result["status"] != "connected":
            return conn_result

        # Pull positions
        fidelity_positions = self.fidelity_client.get_positions()

        if not fidelity_positions:
            self.fidelity_client.close()
            return {
                "status": "success",
                "message": "Connected but no positions found",
                "positions_synced": 0,
                "details": [],
            }

        synced = []
        for pos in fidelity_positions:
            ticker = pos["ticker"].upper()
            shares = pos["shares"]
            current_price = pos["current_price"]
            market_value = pos["market_value"]

            # Determine tier automatically
            tier = self.classify_tier(ticker)

            # Check if already in portfolio
            existing = self._find_existing_position(ticker)

            if existing:
                # Update current price and shares from Fidelity
                self.db.update_position(
                    existing["id"],
                    shares=shares,
                    current_price=current_price,
                    last_updated=__import__("datetime").datetime.now(),
                )
                synced.append({"ticker": ticker, "action": "updated", "shares": shares})
            else:
                # Add new position — use current price as entry since
                # Fidelity API doesn't provide cost basis
                self.db.add_portfolio_position(
                    symbol=ticker,
                    shares=shares,
                    purchase_price=current_price,
                    notes="Synced from Fidelity brokerage",
                    tier=tier,
                    source="fidelity",
                )
                synced.append({"ticker": ticker, "action": "added", "shares": shares, "tier": tier})

        # Close browser session (saves cookies for next time)
        self.fidelity_client.close()

        return {
            "status": "success",
            "positions_synced": len(synced),
            "details": synced,
        }

    def get_raw_positions(self) -> dict:
        """Return raw Fidelity positions without syncing to portfolio."""
        if not self.fidelity_client.credentials_available:
            return {"status": "no_credentials", "positions": []}

        conn_result = self.fidelity_client.connect()
        if conn_result["status"] != "connected":
            return {**conn_result, "positions": []}

        positions = self.fidelity_client.get_positions()
        self.fidelity_client.close()

        return {
            "status": "success",
            "positions": positions,
            "count": len(positions),
        }

    def check_connection(self) -> dict:
        """Check if Fidelity connection is possible without full sync."""
        if not self.fidelity_client.credentials_available:
            return {"status": "no_credentials", "connected": False}

        result = self.fidelity_client.connect()
        connected = result["status"] == "connected"
        self.fidelity_client.close()

        return {
            "status": result["status"],
            "connected": connected,
            "message": result.get("message", ""),
        }

    @staticmethod
    def classify_tier(ticker: str) -> str:
        """Auto-classify into tier based on ticker type."""
        if ticker.upper() in LONG_TERM_TICKERS:
            return "long_term"
        return "midcap_active"

    def _find_existing_position(self, ticker: str) -> dict | None:
        """Find an active portfolio position by ticker."""
        positions = self.db.get_active_positions()
        for pos in positions:
            if pos.get("symbol", "").upper() == ticker.upper():
                return pos
        return None
