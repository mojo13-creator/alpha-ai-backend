# trading/paper_trader.py
"""
Paper Trading Simulator
Runs a daily algorithm that auto-buys and sells based on composite scores,
technical signals, news sentiment, and stop loss/target logic.
"""

import os
import sys
import math
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yfinance as yf
from reports.daily_screener import DailyScreener
from analysis.composite_scorer import run_composite_analysis
from data_collection.reddit_scraper import RedditScraper


def safe_float(val, default=0.0):
    try:
        v = float(val)
        return default if math.isnan(v) or math.isinf(v) else v
    except Exception:
        return default


def get_current_price(ticker):
    """Fetch latest price via yfinance."""
    try:
        t = yf.Ticker(ticker)
        price = float(t.fast_info.last_price)
        return price if price > 0 else None
    except Exception:
        return None


class PaperTrader:
    MAX_POSITION_SIZE = 0.15   # Hard cap: no position larger than 15% of portfolio
    MAX_POSITIONS = 8          # Max 8 simultaneous positions
    MIN_SCORE_TO_BUY = 65      # Only buy composite score 65+
    SELL_SCORE_THRESHOLD = 35  # Sell if score drops below 35

    # Volatility-targeted position sizing: each position risks at most this fraction
    # of total portfolio value if the stop loss is hit. Replaces fixed 15% rule.
    # 1% per trade = max ~8% portfolio drawdown if all 8 positions stop out
    # simultaneously, which is a tail event but bounded.
    RISK_PER_POSITION_PCT = 0.01

    # Time stop: exit if a position has been open this long with no meaningful
    # move (|pnl_pct| < 3%). Caps opportunity cost on trades that just sit.
    MAX_DAYS_FLAT = 21
    FLAT_PNL_THRESHOLD_PCT = 3.0

    def __init__(self, db_manager, technical_analyzer, news_scraper, on_progress=None):
        self.db = db_manager
        self.analyzer = technical_analyzer
        self.news_scraper = news_scraper
        self.screener = DailyScreener(db_manager, technical_analyzer, news_scraper, on_progress=on_progress)
        self.account = self.db.get_paper_account()
        self.actions_taken = []
        self.skipped_candidates = []  # why each candidate was rejected
        self.screener_stats = {}      # pipeline stats (candidates → filtered → picks)
        self.on_progress = on_progress  # callback(step, detail)

    def _emit(self, step, detail=""):
        """Send progress update if callback is set."""
        if self.on_progress:
            self.on_progress(step, detail)

    def _refresh_account(self):
        self.account = self.db.get_paper_account()

    def open_position_count(self):
        return len(self.db.get_open_paper_positions())

    def has_position(self, ticker):
        positions = self.db.get_open_paper_positions()
        return any(p["ticker"] == ticker.upper() for p in positions)

    def unrealized_pnl_pct(self, position, current_price):
        entry = safe_float(position.get("entry_price", 0))
        if entry <= 0:
            return 0
        return ((current_price - entry) / entry) * 100

    # ------------------------------------------------------------------
    # Exit Logic
    # ------------------------------------------------------------------
    def check_exits(self):
        """Check all open positions for exit signals."""
        positions = self.db.get_open_paper_positions()
        print(f"\n  Checking {len(positions)} open positions for exits...")

        reddit_scraper = None
        try:
            reddit_scraper = RedditScraper(self.db)
            if reddit_scraper.reddit is None:
                reddit_scraper = None
        except Exception:
            pass

        for pos in positions:
            ticker = pos["ticker"]
            current_price = get_current_price(ticker)
            if current_price is None:
                print(f"    {ticker}: could not fetch price, skipping")
                continue

            # Update stored current price
            self.db.update_paper_position_price(pos["id"], current_price)

            exit_reason = None
            stop_loss = safe_float(pos.get("stop_loss", 0))
            target_price = safe_float(pos.get("target_price", 0))
            entry_price = safe_float(pos.get("entry_price", 0))

            # Hard stop loss
            if stop_loss > 0 and current_price <= stop_loss:
                exit_reason = f"Stop loss hit at ${current_price:.2f}"

            # Target reached
            elif target_price > 0 and current_price >= target_price:
                exit_reason = f"Target price reached at ${current_price:.2f}"

            else:
                # Re-score for signal/score checks
                try:
                    result = run_composite_analysis(
                        symbol=ticker,
                        db_manager=self.db,
                        technical_analyzer=self.analyzer,
                        news_scraper=self.news_scraper,
                        reddit_scraper=reddit_scraper,
                        skip_ai=True,  # Faster — skip AI for exit checks
                        use_berkeley=False,
                    )

                    if result and "error" not in result:
                        score = result.get("composite_score", 50)
                        signal = result.get("signal", "HOLD")

                        # Score deterioration
                        if score < self.SELL_SCORE_THRESHOLD:
                            exit_reason = f"Score dropped to {score} — conviction lost"

                        # Signal flipped bearish
                        elif signal in ("SELL", "STRONG_SELL", "SHORT"):
                            exit_reason = f"Signal changed to {signal}"

                except Exception as e:
                    print(f"    {ticker}: re-score failed — {e}")

            # Trailing stop: if up 10%+, tighten to breakeven + 2%
            if exit_reason is None and entry_price > 0:
                pnl_pct = self.unrealized_pnl_pct(pos, current_price)
                if pnl_pct > 10:
                    trailing_stop = entry_price * 1.02
                    if current_price <= trailing_stop:
                        exit_reason = f"Trailing stop triggered at ${current_price:.2f} (was up {pnl_pct:.1f}%)"

            # Time stop: dead money — opened > MAX_DAYS_FLAT ago and barely moved.
            # Frees capital for higher-conviction setups instead of letting it sit.
            if exit_reason is None and entry_price > 0:
                opened_at = pos.get("opened_at")
                days_held = None
                if opened_at:
                    try:
                        if isinstance(opened_at, str):
                            opened_dt = datetime.fromisoformat(opened_at.replace("Z", "+00:00").split(".")[0])
                        else:
                            opened_dt = opened_at
                        days_held = (datetime.now() - opened_dt.replace(tzinfo=None)).days
                    except Exception:
                        days_held = None
                if days_held is not None and days_held >= self.MAX_DAYS_FLAT:
                    pnl_pct = self.unrealized_pnl_pct(pos, current_price)
                    if abs(pnl_pct) < self.FLAT_PNL_THRESHOLD_PCT:
                        exit_reason = f"Time stop: held {days_held}d with PnL {pnl_pct:+.1f}% (flat) — freeing capital"

            if exit_reason:
                self.execute_sell(pos, current_price, exit_reason)
            else:
                print(f"    {ticker}: holding (${current_price:.2f})")

    # ------------------------------------------------------------------
    # Entry Logic
    # ------------------------------------------------------------------
    def find_entries(self):
        """Find new buy candidates from the daily screener."""
        if self.open_position_count() >= self.MAX_POSITIONS:
            print(f"\n  Max positions ({self.MAX_POSITIONS}) reached — skipping entries")
            self.skipped_candidates.append({
                "ticker": "N/A",
                "reason": f"Max positions ({self.MAX_POSITIONS}) reached — entry scan skipped entirely",
            })
            return

        print(f"\n  Running screener for entry candidates...")
        picks, _watchlist, stats = self.screener.run_pipeline(
            max_picks=10, skip_ai=False, use_berkeley=False,
        )
        self.screener_stats = stats
        print(f"  Screener returned {len(picks)} picks")

        if not picks:
            self.skipped_candidates.append({
                "ticker": "N/A",
                "reason": "Screener returned 0 picks — no candidates passed the 3-stage pipeline",
            })

        self._refresh_account()

        for candidate in picks:
            if self.open_position_count() >= self.MAX_POSITIONS:
                break

            ticker = candidate.get("ticker", "")
            if not ticker:
                continue

            composite_score = candidate.get("composite_score", 0)
            signal = candidate.get("signal", "HOLD")

            if self.has_position(ticker):
                skip_reason = "Already holding position"
                print(f"    {ticker}: {skip_reason}")
                self.skipped_candidates.append({"ticker": ticker, "score": composite_score, "signal": signal, "reason": skip_reason})
                continue

            if composite_score < self.MIN_SCORE_TO_BUY:
                skip_reason = f"Score {composite_score} below minimum {self.MIN_SCORE_TO_BUY}"
                print(f"    {ticker}: {skip_reason}")
                self.skipped_candidates.append({"ticker": ticker, "score": composite_score, "signal": signal, "reason": skip_reason})
                continue

            if signal not in ("BUY", "STRONG_BUY"):
                skip_reason = f"Signal is {signal}, need BUY or STRONG_BUY"
                print(f"    {ticker}: {skip_reason}")
                self.skipped_candidates.append({"ticker": ticker, "score": composite_score, "signal": signal, "reason": skip_reason})
                continue

            action = candidate.get("action", {})
            price = safe_float(action.get("entry_price", 0))
            if price <= 0:
                price = safe_float(candidate.get("price", 0))
            if price <= 0:
                skip_reason = "No valid price available"
                print(f"    {ticker}: {skip_reason}")
                self.skipped_candidates.append({"ticker": ticker, "score": composite_score, "signal": signal, "reason": skip_reason})
                continue

            stop_loss = safe_float(action.get("stop_loss", 0))
            target = safe_float(action.get("target_price", 0))

            # Volatility-targeted position sizing: risk a fixed % of portfolio
            # per trade based on the stop-loss distance. Tight stops = larger
            # position; wide stops = smaller position. Same dollar risk per trade.
            # Falls back to the hard 15% cap if no valid stop is available.
            self._refresh_account()
            total_value = safe_float(self.account.get("total_value", 10000))
            cash = safe_float(self.account.get("cash_balance", 0))
            hard_cap = total_value * self.MAX_POSITION_SIZE
            sizing_method = "hard_cap"

            if stop_loss > 0 and stop_loss < price:
                risk_per_share = price - stop_loss
                target_dollar_risk = total_value * self.RISK_PER_POSITION_PCT
                vol_target_value = (target_dollar_risk / risk_per_share) * price
                position_value = min(vol_target_value, hard_cap, cash)
                sizing_method = f"vol-targeted (risk ${target_dollar_risk:.0f}, stop {((price-stop_loss)/price)*100:.1f}% away)"
            else:
                position_value = min(hard_cap, cash)

            if position_value < 100:
                skip_reason = f"Insufficient cash (${cash:.2f})"
                print(f"    {skip_reason} — stopping entries")
                self.skipped_candidates.append({"ticker": ticker, "score": composite_score, "signal": signal, "reason": skip_reason})
                break

            shares = position_value / price
            reason = f"Score {composite_score}, signal {signal} | sizing: {sizing_method}"

            self.execute_buy(
                ticker=ticker,
                shares=shares,
                price=price,
                stop_loss=stop_loss,
                target=target,
                score=composite_score,
                signal=signal,
                reason=reason,
            )

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    def execute_buy(self, ticker, shares, price, stop_loss, target, score, signal, reason):
        self._refresh_account()
        cash_before = safe_float(self.account.get("cash_balance", 0))
        cost = shares * price
        cash_after = cash_before - cost

        self.db.create_paper_position(ticker, shares, price, stop_loss, target, signal, score, reason)
        self.db.update_paper_cash(cash_after)
        self.db.log_paper_trade("BUY", ticker, shares, price, reason, score, signal, cash_before, cash_after)

        action_record = {
            "action": "BUY",
            "ticker": ticker,
            "shares": round(shares, 4),
            "price": round(price, 2),
            "cost": round(cost, 2),
            "stop_loss": round(stop_loss, 2),
            "target": round(target, 2),
            "score": score,
            "signal": signal,
            "reason": reason,
        }
        self.actions_taken.append(action_record)
        print(f"    BUY {ticker}: {shares:.4f} shares @ ${price:.2f} = ${cost:.2f} | Score {score} {signal}")

    def execute_sell(self, position, current_price, reason):
        self._refresh_account()
        cash_before = safe_float(self.account.get("cash_balance", 0))
        shares = safe_float(position.get("shares", 0))
        entry_price = safe_float(position.get("entry_price", 0))
        proceeds = shares * current_price
        pnl = (current_price - entry_price) * shares
        pnl_pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
        cash_after = cash_before + proceeds

        self.db.close_paper_position(position["id"], current_price, reason, pnl, pnl_pct)
        self.db.update_paper_cash(cash_after)
        self.db.update_paper_stats(pnl > 0)
        self.db.log_paper_trade("SELL", position["ticker"], shares, current_price,
                                reason, None, None, cash_before, cash_after)

        action_record = {
            "action": "SELL",
            "ticker": position["ticker"],
            "shares": round(shares, 4),
            "price": round(current_price, 2),
            "proceeds": round(proceeds, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "reason": reason,
        }
        self.actions_taken.append(action_record)
        win_loss = "WIN" if pnl > 0 else "LOSS"
        print(f"    SELL {position['ticker']}: {shares:.4f} shares @ ${current_price:.2f} = ${proceeds:.2f} | P&L: ${pnl:.2f} ({pnl_pct:+.1f}%) {win_loss} | {reason}")

    # ------------------------------------------------------------------
    # Account Update
    # ------------------------------------------------------------------
    def update_account(self):
        """Recalculate total value = cash + open positions market value."""
        self._refresh_account()
        cash = safe_float(self.account.get("cash_balance", 0))

        positions = self.db.get_open_paper_positions()
        positions_value = 0
        for pos in positions:
            current_price = get_current_price(pos["ticker"])
            if current_price is None:
                current_price = safe_float(pos.get("current_price", pos.get("entry_price", 0)))
            else:
                self.db.update_paper_position_price(pos["id"], current_price)
            positions_value += safe_float(pos.get("shares", 0)) * current_price

        total_value = cash + positions_value
        total_pnl = total_value - 10000.0
        total_pnl_pct = (total_pnl / 10000.0) * 100

        self.db.update_paper_account(
            total_value=round(total_value, 2),
            total_pnl=round(total_pnl, 2),
            total_pnl_pct=round(total_pnl_pct, 2),
            last_algo_run=datetime.now(),
        )

    # ------------------------------------------------------------------
    # Main Algorithm
    # ------------------------------------------------------------------
    def run_daily_algo(self):
        """Main daily algorithm entry point."""
        start = datetime.now()
        print(f"\n{'='*60}")
        print(f"  PAPER TRADING ALGO — {start.strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*60}")

        self._refresh_account()
        print(f"  Starting cash: ${safe_float(self.account.get('cash_balance', 0)):,.2f}")
        print(f"  Open positions: {self.open_position_count()}")

        # Step 1: Check exits
        print(f"\n--- STEP 1: EXIT CHECK ---")
        self._emit("checking_exits", f"Reviewing {self.open_position_count()} open positions")
        self.check_exits()

        # Step 2: Find entries
        print(f"\n--- STEP 2: ENTRY SCAN ---")
        self._emit("scanning_entries", "Gathering candidates from Finviz, news, Reddit")
        self.find_entries()

        # Step 3: Update account
        print(f"\n--- STEP 3: ACCOUNT UPDATE ---")
        self._emit("updating_account", "Calculating portfolio value")
        self.update_account()

        elapsed = (datetime.now() - start).total_seconds()
        summary = self.get_summary()
        summary["elapsed_seconds"] = round(elapsed, 1)
        summary["actions"] = self.actions_taken
        summary["skipped_candidates"] = self.skipped_candidates
        summary["screener_stats"] = self.screener_stats

        print(f"\n{'='*60}")
        print(f"  ALGO COMPLETE — {len(self.actions_taken)} actions taken in {elapsed:.1f}s")
        print(f"  Cash: ${summary['account']['cash_balance']:,.2f} | Value: ${summary['account']['total_value']:,.2f}")
        print(f"{'='*60}\n")

        return summary

    def get_summary(self):
        """Return current state summary."""
        self._refresh_account()
        positions = self.db.get_open_paper_positions()

        position_list = []
        for pos in positions:
            entry = safe_float(pos.get("entry_price", 0))
            current = safe_float(pos.get("current_price", entry))
            shares = safe_float(pos.get("shares", 0))
            pnl = (current - entry) * shares
            pnl_pct = ((current - entry) / entry * 100) if entry > 0 else 0
            position_list.append({
                "id": pos["id"],
                "ticker": pos["ticker"],
                "shares": round(shares, 4),
                "entry_price": round(entry, 2),
                "current_price": round(current, 2),
                "stop_loss": round(safe_float(pos.get("stop_loss", 0)), 2),
                "target_price": round(safe_float(pos.get("target_price", 0)), 2),
                "unrealized_pnl": round(pnl, 2),
                "unrealized_pnl_pct": round(pnl_pct, 2),
                "signal": pos.get("entry_signal", ""),
                "score": pos.get("entry_score"),
                "reason": pos.get("entry_reason", ""),
                "opened_at": str(pos.get("opened_at", "")),
            })

        return {
            "account": {
                "cash_balance": round(safe_float(self.account.get("cash_balance", 0)), 2),
                "total_value": round(safe_float(self.account.get("total_value", 0)), 2),
                "total_pnl": round(safe_float(self.account.get("total_pnl", 0)), 2),
                "total_pnl_pct": round(safe_float(self.account.get("total_pnl_pct", 0)), 2),
                "total_trades": self.account.get("total_trades", 0),
                "winning_trades": self.account.get("winning_trades", 0),
                "losing_trades": self.account.get("losing_trades", 0),
                "win_rate": safe_float(self.account.get("win_rate", 0)),
                "last_algo_run": str(self.account.get("last_algo_run", "")),
            },
            "open_positions": position_list,
            "position_count": len(position_list),
        }
