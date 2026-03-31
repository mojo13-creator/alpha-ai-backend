# data_collection/finviz_scraper.py
"""
Finviz Screener Integration
Uses Finviz signals to find actionable stock opportunities
"""

from finvizfinance.screener.overview import Overview
import pandas as pd
from datetime import datetime

class FinvizScraper:

    def __init__(self):
        print("📡 Finviz Scraper initialized")

    def _run_signal(self, signal, label, limit=20):
        """Run a signal-based screen and return clean results"""
        try:
            f = Overview()
            f.set_filter(signal=signal, filters_dict={"Country": "USA", "Price": "Over $5", "Average Volume": "Over 300K"})
            df = f.screener_view()
            if df is None or df.empty:
                return []

            results = []
            for _, row in df.head(limit).iterrows():
                try:
                    price_raw = str(row.get("Price", "0")).replace(",", "")
                    change_raw = str(row.get("Change", "0")).replace("%", "").replace(",", "")
                    volume_raw = str(row.get("Volume", "0")).replace(",", "")

                    price = float(price_raw) if price_raw and price_raw != "-" else 0.0
                    change = float(change_raw) if change_raw and change_raw != "-" else 0.0
                    volume = int(float(volume_raw)) if volume_raw and volume_raw != "-" else 0

                    if price <= 0:
                        continue

                    results.append({
                        "symbol": str(row.get("Ticker", "")).strip(),
                        "company": str(row.get("Company", "")).strip(),
                        "sector": str(row.get("Sector", "")).strip(),
                        "industry": str(row.get("Industry", "")).strip(),
                        "price": price,
                        "change_pct": round(change * 100, 2) if abs(change) < 1 else round(change, 2),
                        "volume": volume,
                        "market_cap": str(row.get("Market Cap", "-")).strip(),
                        "category": label,
                        "signal": label,
                        "source": "Finviz"
                    })
                except Exception:
                    continue

            print(f"✅ Finviz [{label}]: {len(results)} stocks")
            return results

        except Exception as e:
            print(f"❌ Finviz [{label}] error: {e}")
            return []

    def get_upgrades(self):
        return self._run_signal("Upgrades", "Analyst Upgrade")

    def get_oversold(self):
        return self._run_signal("Oversold", "Oversold Bounce")

    def get_top_gainers(self):
        return self._run_signal("Top Gainers", "Top Gainer")

    def get_unusual_volume(self):
        return self._run_signal("Unusual Volume", "Unusual Volume")

    def get_insider_buying(self):
        return self._run_signal("Recent Insider Buying", "Insider Buying")

    def get_new_highs(self):
        return self._run_signal("New High", "New 52W High")

    def get_all_signals(self):
        """Run all screens and combine, deduplicating by symbol"""
        print("\n🔍 Running Finviz screener...")

        all_stocks = (
            self.get_upgrades() +
            self.get_oversold() +
            self.get_top_gainers() +
            self.get_unusual_volume() +
            self.get_insider_buying() +
            self.get_new_highs()
        )

        # Deduplicate — keep first occurrence (priority order above)
        seen = {}
        for stock in all_stocks:
            sym = stock.get("symbol", "")
            if sym and sym not in seen:
                seen[sym] = stock

        results = list(seen.values())
        print(f"✅ Finviz total: {len(results)} unique opportunities")
        return results
