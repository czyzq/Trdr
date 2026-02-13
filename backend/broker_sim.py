"""
Simulated broker for paper trading.
Implements Broker + DataProvider interfaces using Alpha Vantage + Yahoo Finance
with DB-cached fallback (never synthetic/fake data).
All positions and account state are managed in-memory + MongoDB.
All fetched candles are accumulated in DB for backtesting.
"""
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

import database as db
from broker import Broker, DataProvider
from alpha_vantage import get_client as get_alpha_client
from historical_data import fetch_yahoo_historical

PLN_USD_RATE = 4.05
INITIAL_BALANCE_PLN = 10000.0

INSTRUMENTS = {
    "XAU": {"name": "Gold", "multiplier": 1, "pip_size": 0.01, "lot_size": 1, "leverage": 20},
    "XAG": {"name": "Silver", "multiplier": 1, "pip_size": 0.001, "lot_size": 100, "leverage": 20},
    "US100": {"name": "Nasdaq-100", "multiplier": 1, "pip_size": 0.01, "lot_size": 1, "leverage": 20},
    "BTC": {"name": "Bitcoin", "multiplier": 1, "pip_size": 1.0, "lot_size": 0.01, "leverage": 5},
}


class SimulatedDataProvider(DataProvider):
    """
    Data provider with multiple sources and persistent candle history.
    Priority: Alpha Vantage → Yahoo Finance → DB history → DB cache.
    Never returns synthetic/generated prices.
    All fetched candles are accumulated in DB for backtesting.
    """

    # Map resolution values to Yahoo Finance intervals
    _YAHOO_INTERVAL = {
        "1": "1m", "5": "5m", "15": "15m", "30": "30m",
        "60": "1h", "D": "1d",
    }

    def __init__(self):
        self._alpha = get_alpha_client()

    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        # 1. Alpha Vantage (live)
        try:
            q = self._alpha.get_quote(symbol)
            if q and q.get("price"):
                db.save_quote(symbol, q)
                return q
        except Exception:
            pass
        # 2. Yahoo Finance — latest candle close as quote
        try:
            yahoo_interval = self._YAHOO_INTERVAL.get("60", "1h")
            candles = fetch_yahoo_historical(symbol, period_days=2, interval=yahoo_interval)
            if candles and len(candles) > 0:
                last = candles[-1]
                q = {
                    "symbol": symbol,
                    "price": last["close"],
                    "high": last["high"],
                    "low": last["low"],
                    "open": last["open"],
                    "volume": last.get("volume", 0),
                    "timestamp": last.get("timestamp", datetime.utcnow().isoformat()),
                    "source": "yahoo",
                }
                db.save_quote(symbol, q)
                return q
        except Exception:
            pass
        # 3. DB cache
        cached = db.load_quote(symbol)
        if cached and cached.get("quote"):
            return cached["quote"]
        return None

    def get_candles(
        self, symbol: str, resolution: str = "60", count: int = 100
    ) -> Optional[List[Dict[str, Any]]]:
        candles = None
        source = ""

        # 1. Alpha Vantage (live, rate-limited)
        try:
            candles = self._alpha.get_candles(symbol, resolution, count)
            if candles and len(candles) > 0:
                source = "alpha_vantage"
        except Exception:
            candles = None

        # 2. Yahoo Finance (free, delayed)
        if not candles:
            try:
                yahoo_interval = self._YAHOO_INTERVAL.get(resolution, "1h")
                period = 7 if resolution in ("1", "5", "15", "30", "60") else 365
                candles = fetch_yahoo_historical(symbol, period_days=period, interval=yahoo_interval)
                if candles and len(candles) > 0:
                    source = "yahoo"
                    # Trim to requested count
                    candles = candles[-count:]
            except Exception:
                candles = None

        # 3. DB candle history — exact resolution
        if not candles:
            history = db.load_candle_history(symbol, resolution, limit=count)
            if history:
                candles = history
                source = "db_history"

        # 4. Aggregation pipeline — build from smaller stored candles
        if not candles:
            candles = self._try_aggregate(symbol, resolution, count)
            if candles:
                source = "aggregated"

        # 5. Old candle_cache fallback (latest batch)
        if not candles:
            cached = db.load_candles(symbol, resolution)
            if cached and cached.get("candles"):
                candles = cached["candles"]
                source = "cache"

        # Accumulate to persistent history (always, regardless of source)
        if candles and source not in ("db_history", "aggregated", "cache"):
            db.store_candles(symbol, resolution, candles, source)
            # Also keep old cache updated for backward compat
            db.save_candles(symbol, resolution, candles, source)

        return candles if candles else None

    def _try_aggregate(
        self, symbol: str, target_resolution: str, count: int
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Try to build target_resolution candles by aggregating smaller stored candles.
        E.g. build 1H from 15m, daily from 1H, etc.
        """
        # Map target to possible source resolutions (smallest first = best)
        source_candidates = {
            "5": ["1"],
            "15": ["5", "1"],
            "30": ["15", "5", "1"],
            "60": ["30", "15", "5", "1"],
            "240": ["60", "30", "15"],
            "D": ["60", "30", "15", "5", "1"],
        }
        candidates = source_candidates.get(target_resolution, [])
        for src_res in candidates:
            stored = db.load_candle_history(symbol, src_res)
            if stored and len(stored) >= 2:
                aggregated = db.aggregate_candles(stored, target_resolution)
                if aggregated and len(aggregated) >= min(10, count):
                    return aggregated[-count:]
        return None


class SimulatedBroker(Broker):
    """
    Paper-trading broker. Tracks positions in memory + MongoDB.
    Drop-in replacement for a real broker.
    """

    def __init__(self):
        self.account: Dict[str, Any] = db.load_account()
        self.open_positions: List[Dict[str, Any]] = db.load_open_positions()
        self.closed_positions: List[Dict[str, Any]] = db.load_closed_positions()

    # ── Account ──────────────────────────────────────────────────────

    def get_account(self) -> Dict[str, Any]:
        return self.account

    # ── Open position ────────────────────────────────────────────────

    def open_position(
        self,
        symbol: str,
        direction: str,
        size: float,
        take_profit: Optional[float] = None,
        stop_loss: Optional[float] = None,
        entry_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        if symbol not in INSTRUMENTS:
            return {"error": f"Unknown instrument: {symbol}"}
        if direction not in ("buy", "sell"):
            return {"error": "Direction must be 'buy' or 'sell'"}
        if entry_price is None:
            return {"error": "entry_price is required"}

        # Margin calculation: margin = notional / leverage
        leverage = INSTRUMENTS[symbol].get("leverage", 20)
        margin_usd = entry_price * size / leverage
        margin_pln = margin_usd * PLN_USD_RATE

        if margin_pln > self.account.get("available_pln", 0):
            return {
                "error": "Insufficient margin",
                "required_pln": margin_pln,
                "available_pln": self.account["available_pln"],
            }

        # Default TP/SL if not provided
        atr = entry_price * 0.01
        if take_profit is None:
            take_profit = (
                entry_price + atr * 3 if direction == "buy" else entry_price - atr * 3
            )
        if stop_loss is None:
            stop_loss = (
                entry_price - atr * 2 if direction == "buy" else entry_price + atr * 2
            )

        position = {
            "id": str(uuid.uuid4())[:8],
            "symbol": symbol,
            "name": INSTRUMENTS[symbol]["name"],
            "direction": direction,
            "size": size,
            "leverage": leverage,
            "entry_price": entry_price,
            "current_price": entry_price,
            "take_profit": round(take_profit, 2),
            "stop_loss": round(stop_loss, 2),
            "margin_pln": round(margin_pln, 2),
            "unrealized_pnl_usd": 0.0,
            "unrealized_pnl_pln": 0.0,
            "opened_at": datetime.utcnow().isoformat(),
            "status": "open",
        }

        self.open_positions.append(position)
        self.account["used_margin"] = self.account.get("used_margin", 0) + margin_pln
        self.account["available_pln"] = (
            self.account["balance_pln"] - self.account["used_margin"]
        )
        self.account["open_trades"] = len(self.open_positions)
        self.account["positions"] = len(self.open_positions)

        db.save_trade(position)
        db.save_account(self.account)

        return {"status": "opened", "position": position}

    # ── Close position ───────────────────────────────────────────────

    def close_position(
        self, position_id: str, exit_price: Optional[float] = None
    ) -> Dict[str, Any]:
        position = None
        pos_index = None
        for i, pos in enumerate(self.open_positions):
            if pos["id"] == position_id:
                position = pos
                pos_index = i
                break

        if not position:
            return {"error": f"Position {position_id} not found"}

        if exit_price is None:
            exit_price = position.get("current_price", position["entry_price"])

        # P&L calculation: price_move * size * leverage
        pos_leverage = position.get("leverage", 1)
        if position["direction"] == "buy":
            pnl_usd = (exit_price - position["entry_price"]) * position["size"] * pos_leverage
        else:
            pnl_usd = (position["entry_price"] - exit_price) * position["size"] * pos_leverage

        pnl_pln = pnl_usd * PLN_USD_RATE

        # Update account
        self.account["balance_pln"] = round(self.account["balance_pln"] + pnl_pln, 2)
        self.account["balance_usd"] = round(
            self.account["balance_pln"] / PLN_USD_RATE, 2
        )
        self.account["used_margin"] = max(
            0, self.account["used_margin"] - position["margin_pln"]
        )
        self.account["available_pln"] = (
            self.account["balance_pln"] - self.account["used_margin"]
        )
        self.account["total_pnl_pln"] = round(
            self.account.get("total_pnl_pln", 0) + pnl_pln, 2
        )
        self.account["total_pnl_usd"] = round(
            self.account.get("total_pnl_usd", 0) + pnl_usd, 2
        )
        self.account["closed_trades"] = self.account.get("closed_trades", 0) + 1

        if pnl_usd >= 0:
            self.account["win_count"] = self.account.get("win_count", 0) + 1
        else:
            self.account["loss_count"] = self.account.get("loss_count", 0) + 1

        total = self.account["win_count"] + self.account["loss_count"]
        self.account["win_rate"] = (
            round(self.account["win_count"] / total * 100, 1) if total > 0 else 0
        )

        # Move to closed
        closed_pos = {
            **position,
            "exit_price": exit_price,
            "pnl_usd": round(pnl_usd, 2),
            "pnl_pln": round(pnl_pln, 2),
            "closed_at": datetime.utcnow().isoformat(),
            "status": "closed",
            "result": "win" if pnl_usd >= 0 else "loss",
        }
        self.closed_positions.insert(0, closed_pos)
        self.open_positions.pop(pos_index)

        self.account["open_trades"] = len(self.open_positions)
        self.account["positions"] = len(self.open_positions)

        db.save_trade(closed_pos)
        db.save_account(self.account)

        return {"status": "closed", "position": closed_pos}

    # ── Queries ──────────────────────────────────────────────────────

    def get_open_positions(self) -> List[Dict[str, Any]]:
        return self.open_positions

    def get_closed_positions(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.closed_positions[:limit]

    # ── Price update ─────────────────────────────────────────────────

    def update_prices(self, data_provider: DataProvider) -> List[Dict[str, Any]]:
        """
        Update open positions with latest quotes.
        Auto-closes positions that hit TP or SL.
        Returns list of auto-closed positions (for logging).
        """
        unrealized_usd = 0.0
        auto_closed = []
        to_close = []

        for pos in self.open_positions:
            quote = data_provider.get_quote(pos["symbol"])
            if not quote:
                continue

            price = quote["price"]
            pos_leverage = pos.get("leverage", 1)
            if pos["direction"] == "buy":
                pnl = (price - pos["entry_price"]) * pos["size"] * pos_leverage
            else:
                pnl = (pos["entry_price"] - price) * pos["size"] * pos_leverage
            pos["current_price"] = price
            pos["unrealized_pnl_usd"] = round(pnl, 2)
            pos["unrealized_pnl_pln"] = round(pnl * PLN_USD_RATE, 2)
            unrealized_usd += pnl

            # Check TP/SL
            tp = pos.get("take_profit")
            sl = pos.get("stop_loss")
            if pos["direction"] == "buy":
                if tp and price >= tp:
                    to_close.append((pos["id"], tp, "TP"))
                elif sl and price <= sl:
                    to_close.append((pos["id"], sl, "SL"))
            else:  # sell
                if tp and price <= tp:
                    to_close.append((pos["id"], tp, "TP"))
                elif sl and price >= sl:
                    to_close.append((pos["id"], sl, "SL"))

        # Auto-close hit positions
        for pos_id, exit_price, reason in to_close:
            result = self.close_position(pos_id, exit_price=exit_price)
            if "error" not in result:
                result["exit_reason"] = reason
                auto_closed.append(result)

        # Recalculate unrealized after closes
        unrealized_usd = 0.0
        for pos in self.open_positions:
            unrealized_usd += pos.get("unrealized_pnl_usd", 0)

        unrealized_pln = unrealized_usd * PLN_USD_RATE
        self.account["equity_pln"] = round(
            self.account["balance_pln"] + unrealized_pln, 2
        )
        self.account["equity_usd"] = round(
            self.account["equity_pln"] / PLN_USD_RATE, 2
        )
        self.account["open_trades"] = len(self.open_positions)
        self.account["positions"] = len(self.open_positions)

        # Persist updated open positions (live prices, P&L) to DB
        for pos in self.open_positions:
            db.save_trade(pos)
        db.save_account(self.account)

        return auto_closed

    # ── Reset ────────────────────────────────────────────────────────

    def reset(self) -> Dict[str, Any]:
        """Reset account to initial state."""
        self.open_positions.clear()
        self.closed_positions.clear()
        self.account.update(
            {
                "balance_pln": INITIAL_BALANCE_PLN,
                "equity_pln": INITIAL_BALANCE_PLN,
                "balance_usd": round(INITIAL_BALANCE_PLN / PLN_USD_RATE, 2),
                "equity_usd": round(INITIAL_BALANCE_PLN / PLN_USD_RATE, 2),
                "positions": 0,
                "open_trades": 0,
                "closed_trades": 0,
                "total_pnl_pln": 0.0,
                "total_pnl_usd": 0.0,
                "win_count": 0,
                "loss_count": 0,
                "win_rate": 0.0,
                "used_margin": 0.0,
                "available_pln": INITIAL_BALANCE_PLN,
            }
        )
        db.delete_all_trades()
        db.save_account(self.account)
        return {"status": "reset", "account": self.account}
