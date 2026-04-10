"""
Standalone Fidelity login test — run directly in your terminal.

Usage:
    cd ~/Desktop/stock-analyzer
    source venv/bin/activate
    python test_fidelity.py

A Firefox window opens. If automated TOTP fails, the browser stays open
so you can complete 2FA manually, then press Enter to continue.
"""

import os
import pyotp
from dotenv import load_dotenv
load_dotenv()

username = os.environ.get("FIDELITY_USERNAME")
password = os.environ.get("FIDELITY_PASSWORD")
totp_secret = os.environ.get("FIDELITY_TOTP_SECRET")

if not username or not password:
    print("FIDELITY_USERNAME and FIDELITY_PASSWORD must be set in .env")
    exit(1)

print(f"Username: {'*' * (len(username) - 2)}{username[-2:]}")
print(f"TOTP secret: {'set' if totp_secret else 'not set'}")
print()

SESSION_DIR = os.path.join(os.path.dirname(__file__), "fidelity_state")
os.makedirs(SESSION_DIR, exist_ok=True)
STATE_FILE = os.path.join(SESSION_DIR, "Fidelity_alpha_ai.json")

# ── Use raw Playwright so the browser never auto-closes ──
import json
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import StealthConfig, stealth_sync

print("Launching Firefox...")
pw = sync_playwright().start()
browser = pw.firefox.launch(headless=False)

# Load saved state if it exists
storage_state = STATE_FILE if os.path.exists(STATE_FILE) and os.path.getsize(STATE_FILE) > 2 else None
context = browser.new_context(storage_state=storage_state)

stealth_config = StealthConfig(
    navigator_languages=False,
    navigator_user_agent=False,
    navigator_vendor=False,
)
stealth_sync(context, stealth_config)
page = context.new_page()

# ── Step 1: Navigate to login ──
print("Navigating to Fidelity login page...")
page.goto("https://digital.fidelity.com/prgw/digital/login/full-page", timeout=60000)

# Check if saved cookies already got us logged in
if "summary" in page.url:
    print("Already logged in from saved session!")
else:
    # Fill credentials
    print("Filling credentials...")
    page.get_by_label("Username", exact=True).click()
    page.get_by_label("Username", exact=True).fill(username)
    page.get_by_label("Password", exact=True).click()
    page.get_by_label("Password", exact=True).fill(password)
    page.get_by_role("button", name="Log in").click()

    # Wait for page to load
    page.wait_for_timeout(3000)

    # Check if we're on the summary page (no 2FA needed)
    if "summary" in page.url:
        print("Logged in — no 2FA needed!")
    else:
        # Try TOTP if available
        totp_handled = False
        if totp_secret:
            try:
                if page.get_by_role("heading", name="Enter the code from your").is_visible(timeout=3000):
                    print("Entering TOTP code...")
                    code = pyotp.TOTP(totp_secret).now()
                    page.get_by_placeholder("XXXXXX").click()
                    page.get_by_placeholder("XXXXXX").fill(code)

                    # Check "Don't ask me again"
                    try:
                        page.locator("label").filter(has_text="Don't ask me again on this").check()
                    except Exception:
                        pass

                    page.get_by_role("button", name="Continue").click()
                    page.wait_for_timeout(5000)

                    if "summary" in page.url:
                        print("TOTP login successful!")
                        totp_handled = True
            except PlaywrightTimeoutError:
                pass

        if not totp_handled and "summary" not in page.url:
            print()
            print("=" * 60)
            print("  2FA page detected that needs manual action.")
            print("  Complete login in the browser window, then")
            print("  come back here and press Enter.")
            print("=" * 60)
            input("\nPress Enter after you've logged in... ")

            # Give it a moment to redirect
            page.wait_for_timeout(2000)

# ── Step 2: Verify login ──
if "summary" not in page.url:
    print(f"Not on summary page yet (URL: {page.url})")
    print("Waiting up to 60s for you to finish login...")
    try:
        page.wait_for_url("**/portfolio/summary**", timeout=60000)
    except PlaywrightTimeoutError:
        print("Timed out waiting for summary page. Saving state and exiting.")
        if storage_state:
            context.storage_state(path=STATE_FILE)
        browser.close()
        pw.stop()
        exit(1)

print()
print("Logged in! Fetching positions...")

# ── Step 3: Use the library's getAccountInfo via its internal methods ──
# Create the FidelityAutomation object and attach our existing page/context
from fidelity.fidelity import FidelityAutomation

fid = FidelityAutomation.__new__(FidelityAutomation)
fid.page = page
fid.context = context
fid.browser = browser
fid.playwright = pw
fid.account_dict = {}
fid.save_state = True
fid.profile_path = STATE_FILE
fid.headless = False
fid.title = "alpha_ai"
fid.debug = False

account_info = fid.getAccountInfo()

if account_info:
    total = 0
    for acct_id, acct_data in account_info.items():
        masked_id = f"***{acct_id[-4:]}" if len(acct_id) > 4 else "****"
        balance = acct_data.get("balance", 0)
        total += balance
        print(f"\nAccount: {acct_data.get('nickname', 'Unknown')} ({masked_id})")
        print(f"  Balance: ${balance:,.2f}")
        stocks = acct_data.get("stocks", [])
        for stock in stocks:
            ticker = stock.get("ticker", "")
            qty = stock.get("quantity", 0)
            price = stock.get("last_price", 0)
            value = stock.get("value", 0)
            print(f"  {ticker}: {qty} shares @ ${price:,.2f} = ${value:,.2f}")
    print(f"\nTotal across all accounts: ${total:,.2f}")
else:
    print("No account info returned.")

# ── Save state and close ──
print()
print("Saving session state...")
context.storage_state(path=STATE_FILE)
browser.close()
pw.stop()
print("Done! Session saved to fidelity_state/")
print("Future headless syncs should reuse this session.")
