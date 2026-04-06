"""
Reusable base class for authenticated Berkeley database scraping.
Uses Playwright (headless Chromium) with CalNet authentication.
"""

import os
import time
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# State directory for browser session persistence
STATE_DIR = Path(__file__).resolve().parent.parent.parent / "browser_state"
STATE_DIR.mkdir(exist_ok=True)
STATE_FILE = STATE_DIR / "calnet_session.json"

# Rate limiting
MIN_DELAY_SECONDS = 5


class BerkeleyBrowserBase:
    """Base class for all Berkeley database scrapers using Playwright."""

    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self._last_request_time = 0

        self.calnet_username = os.environ.get("CALNET_USERNAME")
        self.calnet_password = os.environ.get("CALNET_PASSWORD")

        if not self.calnet_username or not self.calnet_password:
            logger.warning(
                "CALNET_USERNAME or CALNET_PASSWORD not set in .env — "
                "Berkeley scrapers will not be able to authenticate."
            )

    async def _launch_browser(self):
        """Launch Playwright Chromium with session persistence."""
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(headless=True)

        # Reuse saved session state if available
        if STATE_FILE.exists():
            try:
                self.context = await self.browser.new_context(
                    storage_state=str(STATE_FILE)
                )
                logger.info("Restored saved CalNet session state.")
            except Exception:
                logger.info("Saved session state invalid, starting fresh.")
                self.context = await self.browser.new_context()
        else:
            self.context = await self.browser.new_context()

        self.page = await self.context.new_page()

    async def _save_session(self):
        """Persist browser session state to disk."""
        if self.context:
            try:
                await self.context.storage_state(path=str(STATE_FILE))
                logger.info("Saved CalNet session state.")
            except Exception as e:
                logger.warning(f"Failed to save session state: {e}")

    def _is_auth_page(self, url: str) -> bool:
        """Check if current URL is a CalNet or libproxy authentication page."""
        return "auth.berkeley.edu" in url or "libproxy.berkeley.edu/login" in url

    async def _calnet_login(self):
        """
        Handle CalNet authentication flow through libproxy.berkeley.edu.

        Typical flow:
        1. Navigate to proxied URL (e.g. www-capitaliq-com.libproxy.berkeley.edu)
        2. libproxy redirects to auth.berkeley.edu/cas/login?service=...libproxy...
        3. Enter CalNet credentials
        4. Duo 2FA push (if required)
        5. CAS redirects back to libproxy, which sets session cookies
        6. libproxy proxies through to the target site
        """
        if not self.calnet_username or not self.calnet_password:
            logger.error("CalNet credentials not configured.")
            return False

        page = self.page
        try:
            current_url = page.url

            if not self._is_auth_page(current_url):
                logger.info("Not on CalNet/libproxy login page — may already be authenticated.")
                return True

            logger.info(f"Auth page detected ({current_url}), entering CalNet credentials...")

            # Wait for the login form to be ready
            await page.wait_for_selector(
                'input[name="username"], input[id="username"]', timeout=10000
            )

            # Fill username
            username_field = page.locator('input[name="username"], input[id="username"]')
            await username_field.fill(self.calnet_username)

            # Fill password
            password_field = page.locator('input[name="password"], input[id="password"]')
            await password_field.fill(self.calnet_password)

            # Submit
            submit_btn = page.locator(
                'button[type="submit"], input[type="submit"], button:has-text("Sign In"), button:has-text("Log In")'
            )
            await submit_btn.first.click()

            # Wait for navigation — may go to 2FA, back to libproxy, or directly through
            await page.wait_for_load_state("networkidle", timeout=15000)

            # Check for Duo 2FA prompt (can appear as iframe or redirect)
            duo_detected = (
                "duosecurity.com" in page.url
                or "duo.berkeley.edu" in page.url
                or await page.locator("iframe#duo_iframe, iframe[src*='duosecurity'], iframe[src*='duo']").count() > 0
            )

            if duo_detected:
                logger.info(
                    "Duo 2FA detected — waiting up to 120 seconds for manual approval "
                    "(check your phone for a push notification)."
                )
                try:
                    await page.wait_for_url(
                        lambda url: not self._is_auth_page(url)
                        and "duosecurity.com" not in url
                        and "duo.berkeley.edu" not in url,
                        timeout=120000,
                    )
                    logger.info("2FA approved, proceeding.")
                except Exception:
                    logger.error("2FA timed out after 120 seconds.")
                    return False

            # After CAS login, libproxy may show an interstitial or redirect.
            # Wait for the page to settle on a non-auth URL.
            try:
                if self._is_auth_page(page.url):
                    await page.wait_for_url(
                        lambda url: not self._is_auth_page(url),
                        timeout=30000,
                    )
            except Exception:
                logger.warning(f"Still on auth page after login: {page.url}")

            await page.wait_for_load_state("networkidle", timeout=15000)
            await self._save_session()
            logger.info(f"CalNet authentication successful. Now at: {page.url}")
            return True

        except Exception as e:
            logger.error(f"CalNet login failed: {e}")
            return False

    async def _rate_limit(self):
        """Enforce minimum delay between page loads."""
        elapsed = time.time() - self._last_request_time
        if elapsed < MIN_DELAY_SECONDS:
            wait = MIN_DELAY_SECONDS - elapsed
            logger.debug(f"Rate limiting: waiting {wait:.1f}s")
            await self.page.wait_for_timeout(int(wait * 1000))
        self._last_request_time = time.time()

    async def navigate(self, url: str, max_retries: int = 3):
        """
        Navigate to a URL with rate limiting and retry logic.
        Returns True on success, False on failure.
        """
        for attempt in range(1, max_retries + 1):
            try:
                await self._rate_limit()
                response = await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)

                # Handle CalNet / libproxy auth redirect
                if self._is_auth_page(self.page.url):
                    success = await self._calnet_login()
                    if not success:
                        return False
                    # After login, libproxy may have already redirected us to the target.
                    # If not, re-navigate to the original proxied URL.
                    if self.page.url != url and "libproxy.berkeley.edu" not in self.page.url:
                        await self._rate_limit()
                        response = await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)

                if response and response.ok:
                    return True

                logger.warning(f"Attempt {attempt}: HTTP {response.status if response else 'None'} for {url}")

            except Exception as e:
                backoff = 2 ** attempt
                logger.warning(f"Attempt {attempt} failed for {url}: {e}. Retrying in {backoff}s...")
                await self.page.wait_for_timeout(backoff * 1000)

        logger.error(f"All {max_retries} attempts failed for {url}")
        return False

    async def get_text(self, selector: str, default: str = "") -> str:
        """Safely extract text content from a selector."""
        try:
            el = self.page.locator(selector).first
            if await el.count() > 0:
                return (await el.text_content() or "").strip()
        except Exception:
            pass
        return default

    async def get_texts(self, selector: str) -> list:
        """Extract all text values matching a selector."""
        try:
            elements = self.page.locator(selector)
            count = await elements.count()
            return [(await elements.nth(i).text_content() or "").strip() for i in range(count)]
        except Exception:
            return []

    async def close(self):
        """Clean up browser resources."""
        try:
            if self.context:
                await self._save_session()
            if self.browser:
                await self.browser.close()
            if hasattr(self, "_playwright") and self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.warning(f"Error during browser cleanup: {e}")
        finally:
            self.browser = None
            self.context = None
            self.page = None

    async def __aenter__(self):
        await self._launch_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        return False
