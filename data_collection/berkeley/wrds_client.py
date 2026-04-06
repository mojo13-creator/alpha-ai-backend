# WRDS account pending approval — this module will activate once credentials are set in .env
# To test: python -m data_collection.berkeley.wrds_client

"""
WRDS (Wharton Research Data Services) Python client.
Pulls CRSP and Compustat data for individual tickers via Berkeley institutional access.
"""

import os
import logging
import sqlite3
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent.parent / "stock_data.db"
CACHE_TTL_HOURS = 24


class WRDSClient:
    """Client for querying WRDS databases (CRSP, Compustat)."""

    def __init__(self):
        self.username = os.environ.get("WRDS_USERNAME")
        self._conn = None
        self._ensure_cache_table()

        if not self.username:
            logger.warning(
                "WRDS_USERNAME not set in .env — WRDS queries will be unavailable. "
                "Set WRDS_USERNAME once your account is approved."
            )

    def _ensure_cache_table(self):
        """Create the wrds_cache table if it doesn't exist."""
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS wrds_cache (
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
            "SELECT data, fetched_at FROM wrds_cache WHERE cache_key = ?", (key,)
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
            "INSERT OR REPLACE INTO wrds_cache (cache_key, data, fetched_at) VALUES (?, ?, ?)",
            (key, json.dumps(data), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        conn.close()

    def _connect(self):
        """Establish WRDS connection. Returns True on success."""
        if not self.username:
            return False

        if self._conn is not None:
            return True

        try:
            import wrds
            self._conn = wrds.Connection(wrds_username=self.username)
            logger.info("Connected to WRDS successfully.")
            return True
        except Exception as e:
            logger.error(f"WRDS connection failed: {e}")
            self._conn = None
            return False

    def get_stock_data(self, ticker: str) -> dict | None:
        """
        Pull all available WRDS data for a ticker.
        Returns combined dict of CRSP + Compustat data, or None.
        """
        ticker = ticker.upper()
        cache_key = f"wrds_all_{ticker}"
        cached = self._get_cached(cache_key)
        if cached:
            logger.info(f"WRDS cache hit for {ticker}")
            return cached

        if not self._connect():
            return None

        result = {
            "ticker": ticker,
            "source": "wrds",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        crsp = self.get_crsp_daily_returns(ticker)
        if crsp:
            result["crsp_daily_returns"] = crsp

        compustat_q = self.get_compustat_quarterly(ticker)
        if compustat_q:
            result["compustat_quarterly"] = compustat_q

        compustat_a = self.get_compustat_annual(ticker)
        if compustat_a:
            result["compustat_annual"] = compustat_a

        # Only cache if we got at least some data
        if len(result) > 3:
            self._save_cache(cache_key, result)
            return result

        return None

    def get_crsp_daily_returns(self, ticker: str) -> list | None:
        """Pull CRSP daily stock returns for the last year."""
        ticker = ticker.upper()
        cache_key = f"crsp_daily_{ticker}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        if not self._connect():
            return None

        try:
            one_year_ago = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

            query = f"""
                SELECT date, ret, prc, vol, shrout
                FROM crsp.dsf
                WHERE ticker = '{ticker}'
                AND date >= '{one_year_ago}'
                ORDER BY date
            """
            df = self._conn.raw_sql(query)

            if df is None or df.empty:
                logger.info(f"No CRSP data found for {ticker}")
                return None

            records = df.to_dict(orient="records")
            # Convert dates to strings for JSON serialization
            for r in records:
                for k, v in r.items():
                    if hasattr(v, "isoformat"):
                        r[k] = v.isoformat()

            self._save_cache(cache_key, records)
            return records

        except Exception as e:
            logger.error(f"CRSP query failed for {ticker}: {e}")
            return None

    def get_compustat_quarterly(self, ticker: str) -> list | None:
        """Pull Compustat quarterly financials."""
        ticker = ticker.upper()
        cache_key = f"compustat_q_{ticker}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        if not self._connect():
            return None

        try:
            query = f"""
                SELECT datadate, fyearq, fqtr, revtq, niq, epspxq, atq, ltq
                FROM comp.fundq
                WHERE tic = '{ticker}'
                ORDER BY datadate DESC
                LIMIT 12
            """
            df = self._conn.raw_sql(query)

            if df is None or df.empty:
                logger.info(f"No Compustat quarterly data for {ticker}")
                return None

            records = df.to_dict(orient="records")
            for r in records:
                for k, v in r.items():
                    if hasattr(v, "isoformat"):
                        r[k] = v.isoformat()

            self._save_cache(cache_key, records)
            return records

        except Exception as e:
            logger.error(f"Compustat quarterly query failed for {ticker}: {e}")
            return None

    def get_compustat_annual(self, ticker: str) -> list | None:
        """Pull Compustat annual financials."""
        ticker = ticker.upper()
        cache_key = f"compustat_a_{ticker}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        if not self._connect():
            return None

        try:
            query = f"""
                SELECT datadate, fyear, revt, ni, epspx, at, lt, ceq
                FROM comp.funda
                WHERE tic = '{ticker}'
                AND indfmt = 'INDL'
                AND datafmt = 'STD'
                AND popsrc = 'D'
                AND consol = 'C'
                ORDER BY datadate DESC
                LIMIT 5
            """
            df = self._conn.raw_sql(query)

            if df is None or df.empty:
                logger.info(f"No Compustat annual data for {ticker}")
                return None

            records = df.to_dict(orient="records")
            for r in records:
                for k, v in r.items():
                    if hasattr(v, "isoformat"):
                        r[k] = v.isoformat()

            self._save_cache(cache_key, records)
            return records

        except Exception as e:
            logger.error(f"Compustat annual query failed for {ticker}: {e}")
            return None

    def close(self):
        """Close WRDS connection."""
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def test_connection(self) -> bool:
        """Test WRDS connection and report status."""
        if not self.username:
            print("WRDS_USERNAME not set in .env — cannot connect.")
            return False

        try:
            import wrds
        except ImportError:
            print("wrds package not installed. Run: pip install wrds")
            return False

        if self._connect():
            print(f"WRDS connection successful for user: {self.username}")
            self.close()
            return True
        else:
            print("WRDS connection failed — check credentials and network.")
            return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    client = WRDSClient()
    client.test_connection()
