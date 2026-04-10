"""
Standalone Fidelity login test — run this directly to handle 2FA.

Usage:
    cd ~/Desktop/stock-analyzer
    source venv/bin/activate
    python test_fidelity.py

A Firefox window will open. If 2FA is needed, enter the code in the browser.
The session will be saved for future headless use.
"""

import os
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
print("Opening Firefox browser for Fidelity login...")
print()

from fidelity.fidelity import FidelityAutomation

SESSION_DIR = os.path.join(os.path.dirname(__file__), "fidelity_state")
os.makedirs(SESSION_DIR, exist_ok=True)

browser = FidelityAutomation(
    headless=False,
    title="alpha_ai",
    save_state=True,
    profile_path=SESSION_DIR,
)

step_1, step_2 = browser.login(
    username=username,
    password=password,
    totp_secret=totp_secret,
    save_device=True,
)

print(f"Step 1 (initial login): {step_1}")
print(f"Step 2 (fully logged in): {step_2}")

if step_1 and not step_2:
    print()
    print("2FA required — enter the code in the browser window.")
    code = input("Once you've entered the code, press Enter here to continue... ")
    # After manual 2FA in the browser, try to proceed
    print("Attempting to continue after 2FA...")

if step_1 and step_2:
    print()
    print("Login successful! Fetching positions...")
    account_info = browser.getAccountInfo()

    if account_info:
        for acct_id, acct_data in account_info.items():
            masked_id = f"***{acct_id[-4:]}" if len(acct_id) > 4 else "****"
            print(f"\nAccount: {acct_data.get('nickname', 'Unknown')} ({masked_id})")
            print(f"  Balance: ${acct_data.get('balance', 0):,.2f}")
            stocks = acct_data.get("stocks", [])
            for stock in stocks:
                ticker = stock.get("ticker", "")
                qty = stock.get("quantity", 0)
                price = stock.get("last_price", 0)
                value = stock.get("value", 0)
                print(f"  {ticker}: {qty} shares @ ${price:,.2f} = ${value:,.2f}")
    else:
        print("No account info returned.")

    print()
    print("Saving session and closing browser...")
    browser.close_browser()
    print("Done! Session saved — future syncs may work headless.")
elif not step_1:
    print()
    print("Login FAILED. Check your FIDELITY_USERNAME and FIDELITY_PASSWORD in .env")
    browser.close_browser()
else:
    print("Saving session state...")
    browser.close_browser()
    print("Session saved. Try running again — the saved cookies may allow headless login.")
