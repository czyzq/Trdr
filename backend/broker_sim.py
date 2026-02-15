"""
Simulated broker for paper trading - ASYNC version.
Implements Broker + DataProvider interfaces using async Alpha Vantage + Yahoo Finance.
"""
import uuid
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any

import database as db
from database import async_save_trade, async_save_account, async_save_quote
from broker import Broker, DataProvider
from alpha_vantage import get_async_client
from historical_data import fetch_yahoo_historical

PLN_USD_RATE = 4.05
INITIAL_BALANCE_PLN = 10000.0

INSTRUMENTS = {
    "XAU": {"name": "Gold", "multiplier": 1, "pip_size": 0.01, "lot_size": 1, "leverage": 20},
    "XAG": {"name": "Silver", "multiplier": 1, "pip_size": 0.001, "lot_size": 100, "leverage": 20},
    "US100": {"name": "Nasdaq-100", "multiplier": 1, "pip_size": 0.01, "lot_size": 1, "leverage": 20},
    "BTC": {"name": "Bitcoin", "multiplier": 1, "pip_size": 1.0, "lot_size": 0.01, "leverage": 5},
}


class AsyncSimulatedDataProvider:
    """Async data provider with multiple sources."""
    
    _YAHOO_INTERVAL = {
        "1": "1m", "5": "5m", "15": "15m", "30": "30m",
        "60": "1h", "D": "1d",
    }

    def __init__(self):
        self._alpha = get_async_client()

    async def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get quote - tries Alpha Vantage async, then Yahoo, then DB."""
        # 1. Alpha Vantage (async)
        try:
            q = await asyncio.wait_for(self._alpha.get_quote(symbol), timeout=5.0)
            if q and q.get("price"):
                await async_save_quote(symbol, q)
                return q
        except Exception:
            pass
        
        # 2. Yahoo Finance (sync - runs in thread)
        try:
            yahoo_interval = self._YAHOO_INTERVAL.get("60", "1h")
            candles = await asyncio.to_thread(
                fetch_yahoo_historical, symbol, period_days=2, interval=yahoo_interval
            )
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
                await async_save_quote(symbol, q)
                return q
        except Exception:
            pass
        
        # 3. DB cache
        cached = db.load_quote(symbol)
        if cached and cached.get("quote"):
            return cached["quote"]
        return None

    async def get_candles(
        self, symbol: str, resolution: str = "60", count: int = 100
    ) -> Optional[List[Dict[str, Any]]]:
        """Get candles - async with fallbacks."""
        candles = None
        source = ""

        # 1. Alpha Vantage (async)
        try:
            candles = await asyncio.wait_for(
                self._alpha.get_candles(symbol, resolution, count), 
                timeout=10.0
            )
            if candles and len(candles) > 0:
                source = "alpha_vantage"
        except Exception:
            candles = None

        # 2. Yahoo Finance (in thread)
        if not candles:
            try:
                yahoo_interval = self._YAHOO_INTERVAL.get(resolution, "1h")
                period = 30 if resolution in ("1", "5", "15", "30", "60") else 365
                candles = await asyncio.to_thread(
                    fetch_yahoo_historical, symbol, period_days=period, interval=yahoo_interval
                )
                if candles and len(candles) > 0:
                    candles = candles[-count:]
                    source = "yahoo"
            except Exception:
                candles = None

        # 3. DB history
        if not candles:
            history = await asyncio.to_thread(db.load_candle_history, symbol, resolution, limit=count)
            if history:
                candles = history
                source = "db_history"

        # 4. Aggregation
        if not candles:
            candles = await self._try_aggregate(symbol, resolution, count)
            if candles:
                source = "aggregated"

        # 5. Cache fallback
        if not candles:
            cached = await asyncio.to_thread(db.load_candles, symbol, resolution)
            if cached and cached.get("candles"):
                candles = cached["candles"]
                source = "cache"

        # Save to DB
        if candles and source not in ("db_history", "aggregated", "cache"):
            await asyncio.to_thread(db.store_candles, symbol, resolution, candles, source)
            await asyncio.to_thread(db.save_candles, symbol, resolution, candles, source)

        return candles

    async def _try_aggregate(
        self, symbol: str, target_resolution: str, count: int
    ) -> Optional[List[Dict[str, Any]]]:
        """Try to build candles from smaller intervals."""
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
            stored = await asyncio.to_thread(db.load_candle_history, symbol, src_res)
            if stored and len(stored) >= 2:
                aggregated = db.aggregate_candles(stored, target_resolution)
                if aggregated and len(aggregated) >= min(10, count):
                    return aggregated[-count:]
        return None


class AsyncSimulatedBroker(Broker):
    """Async paper-trading broker."""

    def __init__(self):
        self.account: Dict[str, Any] = db.load_account()
        self.open_positions: List[Dict[str, Any]] = db.load_open_positions()
        self.closed_positions: List[Dict[str, Any]] = db.load_closed_positions()
        self._data_provider = AsyncSimulatedDataProvider()

    def get_account(self) -> Dict[str, Any]:
        return self.account

    def get_open_positions(self) -> List[Dict[str, Any]]:
        return self.open_positions

    def get_closed_positions(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.closed_positions[:limit]

    def open_position(
        self, symbol: str, direction: str, size: float,
        take_profit: Optional[float] = None,
        stop_loss: Optional[float] = None,
        entry_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Sync wrapper for async open."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                future = asyncio.run_coroutine_threadsafe(
                    self._async_open_position(symbol, direction, size, take_profit, stop_loss, entry_price),
                    loop
                )
                return future.result(timeout=10)
            else:
                return loop.run_until_complete(
                    self._async_open_position(symbol, direction, size, take_profit, stop_loss, entry_price)
                )
        except Exception as e:
            return {"error": str(e)}

    async def _async_open_position(
        self, symbol: str, direction: str, size: float,
        take_profit: Optional[float] = None,
        stop_loss: Optional[float] = None,
        entry_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Async position opening."""
        if symbol not in INSTRUMENTS:
            return {"error": f"Unknown instrument: {symbol}"}
        if direction not in ("buy", "sell"):
            return {"error": "Direction must be 'buy' or 'sell'"}
        if entry_price is None:
            return {"error": "entry_price is required"}

        leverage = INSTRUMENTS[symbol].get("leverage", 20)
        margin_usd = entry_price * size / leverage
        margin_pln = margin_usd * PLN_USD_RATE

        if margin_pln > self.account.get("available_pln", 0):
            return {
                "error": "Insufficient margin",
                "required_pln": margin_pln,
                "available_pln": self.account["available_pln"],
            }

        # Default TP/SL
        atr = entry_price * 0.01
        if take_profit is None:
            take_profit = entry_price + atr * 3 if direction == "buy" else entry_price - atr * 3
        if stop_loss is None:
            stop_loss = entry_price - atr * 2 if direction == "buy" else entry_price + atr * 2

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
        self.account["available_pln"] = self.account["balance_pln"] - self.account["used_margin"]
        self.account["open_trades"] = len(self.open_positions)
        self.account["positions"] = len(self.open_positions)

        await async_save_trade(position)
        await async_save_account(self.account)

        return {"status": "opened", "position": position}

    def close_position(self, position_id: str, exit_price: Optional[float] = None) -> Dict[str, Any]:
        """Sync wrapper for async close."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                future = asyncio.run_coroutine_threadsafe(
                    self._async_close_position(position_id, exit_price), loop
                )
                return future.result(timeout=10)
            else:
                return loop.run_until_complete(self._async_close_position(position_id, exit_price))
        except Exception as e:
            return {"error": str(e)}

    async def _async_close_position(self, position_id: str, exit_price: Optional[float] = None) -> Dict[str, Any]:
        """Async position closing."""
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

        pos_leverage = position.get("leverage", 1)
        if position["direction"] == "buy":
            pnl_usd = (exit_price - position["entry_price"]) * position["size"] * pos_leverage
        else:
            pnl_usd = (position["entry_price"] - exit_price) * position["size"] * pos_leverage

        pnl_pln = pnl_usd * PLN_USD_RATE

        self.account["balance_pln"] = round(self.account["balance_pln"] + pnl_pln, 2)
        self.account["balance_usd"] = round(self.account["balance_pln"] / PLN_USD_RATE, 2)
        self.account["used_margin"] = max(0, self.account["used_margin"] - position["margin_pln"])
        self.account["available_pln"] = self.account["balance_pln"] - self.account["used_margin"]
        self.account["total_pnl_pln"] = round(self.account.get("total_pnl_pln", 0) + pnl_pln, 2)
        self.account["total_pnl_usd"] = round(self.account.get("total_pnl_usd", 0) + pnl_usd, 2)
        self.account["closed_trades"] = self.account.get("closed_trades", 0) + 1

        if pnl_usd >= 0:
            self.account["win_count"] = self.account.get("win_count", 0) + 1
        else:
            self.account["loss_count"] = self.account.get("loss_count", 0) + 1

        total = self.account["win_count"] + self.account["loss_count"]
        self.account["win_rate"] = round(self.account["win_count"] / total * 100, 1) if total > 0 else 0

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

        await async_save_trade(closed_pos)
        await async_save_account(self.account)

        return {"status": "closed", "position": closed_pos}

    def update_prices(self, data_provider) -> List[Dict[str, Any]]:
        """Sync wrapper for price update."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                future = asyncio.run_coroutine_threadsafe(
                    self._async_update_prices(), loop
                )
                return future.result(timeout=30)
            else:
                return loop.run_until_complete(self._async_update_prices())
        except Exception as e:
            print(f"Error updating prices: {e}")
            return []

    async def _async_update_prices(self) -> List[Dict[str, Any]]:
        """Async price update with auto-close."""
        auto_closed = []
        to_close = []

        for pos in self.open_positions:
            quote = await self._data_provider.get_quote(pos["symbol"])
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

            tp = pos.get("take_profit")
            sl = pos.get("stop_loss")
            if pos["direction"] == "buy":
                if tp and price >= tp:
                    to_close.append((pos["id"], tp, "TP"))
                elif sl and price <= sl:
                    to_close.append((pos["id"], sl, "SL"))
            else:
                if tp and price <= tp:
                    to_close.append((pos["id"], tp, "TP"))
                elif sl and price >= sl:
                    to_close.append((pos["id"], sl, "SL"))

        for pos_id, trigger_price, reason in to_close:
            # Get current market price for closing (not the trigger price)
            position = next((p for p in self.open_positions if p["id"] == pos_id), None)
            if position:
                market_price = position.get("current_price", trigger_price)
                result = await self._async_close_position(pos_id, exit_price=market_price)
                if "error" not in result:
                    result["exit_reason"] = reason
                    auto_closed.append(result)

        # Recalculate unrealized
        for pos in self.open_positions:
            quote = await self._data_provider.get_quote(pos["symbol"])
            if quote:
                price = quote["price"]
                pos_leverage = pos.get("leverage", 1)
                if pos["direction"] == "buy":
                    pnl = (price - pos["entry_price"]) * pos["size"] * pos_leverage
                else:
                    pnl = (pos["entry_price"] - price) * pos["size"] * pos_leverage
                pos["current_price"] = price
                pos["unrealized_pnl_usd"] = round(pnl, 2)
                pos["unrealized_pnl_pln"] = round(pnl * PLN_USD_RATE, 2)

        unrealized_usd = sum(p.get("unrealized_pnl_usd", 0) for p in self.open_positions)
        unrealized_pln = unrealized_usd * PLN_USD_RATE
        self.account["equity_pln"] = round(self.account["balance_pln"] + unrealized_pln, 2)
        self.account["equity_usd"] = round(self.account["equity_pln"] / PLN_USD_RATE, 2)
        self.account["open_trades"] = len(self.open_positions)
        self.account["positions"] = len(self.open_positions)

        for pos in self.open_positions:
            await async_save_trade(pos)
        await async_save_account(self.account)

        return auto_closed

    def reset(self) -> Dict[str, Any]:
        """Reset account."""
        self.open_positions.clear()
        self.closed_positions.clear()
        self.account.update({
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
        })
        db.delete_all_trades()
        db.save_account(self.account)
        return {"status": "reset", "account": self.account}


# Legacy SimulatedDataProvider for compatibility
class SimulatedDataProvider(AsyncSimulatedDataProvider):
    """Legacy sync wrapper."""
    pass


# Legacy SimulatedBroker for compatibility  
class SimulatedBroker(AsyncSimulatedBroker):
    """Legacy sync wrapper."""
    pass
