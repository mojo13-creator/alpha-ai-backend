"""
Fidelity brokerage client — READ-ONLY portfolio data via fidelity-api.

Uses Playwright (Firefox) browser automation to scrape Fidelity's website.
All methods are synchronous (the library uses sync_playwright internally).
"""

import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Session files stored here (added to .gitignore)
SESSION_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fidelity_state")


class FidelityClient:
    def __init__(self):
        self.username = os.environ.get("FIDELITY_USERNAME")
        self.password = os.environ.get("FIDELITY_PASSWORD")
        self.totp_secret = os.environ.get("FIDELITY_TOTP_SECRET")
        self.browser = None
        self._logged_in = False

        if not self.username or not self.password:
            logger.warning("Fidelity credentials not set in .env")

    @property
    def credentials_available(self) -> bool:
        return bool(self.username and self.password)

    def connect(self, headless: bool = True) -> dict:
        """
        Login to Fidelity. Returns status dict:
          {"status": "connected"} — success
          {"status": "2fa_required", "message": "..."} — SMS code needed
          {"status": "failed", "message": "..."} — login failed
          {"status": "no_credentials"} — env vars not set
        """
        if not self.credentials_available:
            return {"status": "no_credentials", "message": "FIDELITY_USERNAME/PASSWORD not set in .env"}

        if self._logged_in and self.browser:
            return {"status": "connected"}

        try:
            from fidelity.fidelity import FidelityAutomation

            # Ensure session directory exists
            os.makedirs(SESSION_DIR, exist_ok=True)

            self.browser = FidelityAutomation(
                headless=headless,
                title="alpha_ai",
                save_state=True,
                profile_path=SESSION_DIR,
            )

            step_1, step_2 = self.browser.login(
                username=self.username,
                password=self.password,
                totp_secret=self.totp_secret,
                save_device=True,
            )

            if step_1 and step_2:
                logger.info("Fidelity login successful")
                self._logged_in = True
                return {"status": "connected"}
            elif step_1 and not step_2:
                logger.warning("Fidelity 2FA required — cannot proceed in headless mode")
                return {
                    "status": "2fa_required",
                    "message": "SMS 2FA code needed. Run sync locally with headless=False, "
                               "or add FIDELITY_TOTP_SECRET to .env for automatic TOTP.",
                }
            else:
                logger.error("Fidelity login failed")
                self.close()
                return {"status": "failed", "message": "Login failed — check credentials"}

        except Exception as e:
            logger.error(f"Fidelity connection error: {e}")
            self.close()
            return {"status": "failed", "message": str(e)}

    def get_positions(self) -> list:
        """
        Pull all positions from Fidelity account.
        Returns list of dicts with: ticker, shares, current_price, market_value, account_id.
        """
        if not self._logged_in:
            conn = self.connect()
            if conn["status"] != "connected":
                return []

        try:
            account_dict = self.browser.getAccountInfo()
            if not account_dict:
                logger.error("getAccountInfo returned empty")
                return []

            positions = []
            for account_id, account_data in account_dict.items():
                stocks = account_data.get("stocks", [])
                for stock in stocks:
                    ticker = stock.get("ticker", "")
                    # Skip cash positions (SPAXX, FDRXX, etc.)
                    if not ticker or ticker in ("SPAXX", "FDRXX", "FCASH", "Pending Activity"):
                        continue

                    quantity = float(stock.get("quantity", 0))
                    last_price = float(stock.get("last_price", 0))
                    value = float(stock.get("value", 0))

                    if quantity <= 0:
                        continue

                    positions.append({
                        "ticker": ticker,
                        "shares": quantity,
                        "current_price": last_price,
                        "market_value": value,
                        "account_id": account_id,
                        "source": "fidelity",
                    })

            logger.info(f"Fetched {len(positions)} positions from Fidelity")
            return positions

        except Exception as e:
            logger.error(f"Failed to get Fidelity positions: {e}")
            return []

    def get_account_summary(self) -> dict:
        """Pull account balance summary."""
        if not self._logged_in:
            conn = self.connect()
            if conn["status"] != "connected":
                return {}

        try:
            self.browser.get_list_of_accounts(set_flag=True, get_withdrawal_bal=True)
            account_dict = self.browser.account_dict

            summary = {
                "accounts": [],
                "total_value": 0,
            }

            for account_id, account_data in account_dict.items():
                balance = float(account_data.get("balance", 0))
                account = {
                    "id": account_id,
                    "nickname": account_data.get("nickname", ""),
                    "balance": balance,
                    "withdrawal_balance": float(account_data.get("withdrawal_balance", 0)),
                }
                summary["accounts"].append(account)
                summary["total_value"] += balance

            return summary

        except Exception as e:
            logger.error(f"Failed to get Fidelity summary: {e}")
            return {}

    def close(self):
        """Close browser and save session state."""
        if self.browser:
            try:
                self.browser.close_browser()
            except Exception:
                pass
            self.browser = None
        self._logged_in = False
