"""
Interactive Brokers (IBKR) broker implementation.
Uses the IBKR Client Portal API or TWS API via ib_insync.

SETUP:
  1. pip install ib_insync
  2. Run IB Gateway or TWS with API enabled
  3. Set env vars:
       BROKER_TYPE=ibkr
       IBKR_HOST=127.0.0.1
       IBKR_PORT=7497          (7497=paper, 7496=live)
       IBKR_CLIENT_ID=1

SYMBOL MAPPING (our symbols → IBKR contracts):
  XAU   → XAUUSD (CMDTY)  or GC futures
  XAG   → XAGUSD (CMDTY)  or SI futures
  US100 → NQ futures       or QQQ stock
  BTC   → BTC (CRYPTO)     on Paxos

STATUS: STUB – replace TODOs with real ib_insync calls.
"""

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from broker import Broker, DataProvider

IBKR_HOST = os.getenv("IBKR_HOST", "127.0.0.1")
IBKR_PORT = int(os.getenv("IBKR_PORT", "7497"))  # 7497=paper, 7496=live
IBKR_CLIENT_ID = int(os.getenv("IBKR_CLIENT_ID", "1"))

# Map our internal symbols to IBKR contract definitions
IBKR_CONTRACTS = {
    "XAU": {"symbol": "XAUUSD", "secType": "CMDTY", "exchange": "SMART", "currency": "USD"},
    "XAG": {"symbol": "XAGUSD", "secType": "CMDTY", "exchange": "SMART", "currency": "USD"},
    "US100": {"symbol": "NQ", "secType": "FUT", "exchange": "CME", "currency": "USD"},
    "BTC": {"symbol": "BTC", "secType": "CRYPTO", "exchange": "PAXOS", "currency": "USD"},
}


class IBKRDataProvider(DataProvider):
    """
    Market data via Interactive Brokers.
    Requires active IB Gateway / TWS connection.
    """

    def __init__(self):
        self.ib = None
        self._connect()

    def _connect(self):
        try:
            from ib_insync import IB

            self.ib = IB()
            self.ib.connect(IBKR_HOST, IBKR_PORT, clientId=IBKR_CLIENT_ID)
            print(f"[IBKR] Connected to {IBKR_HOST}:{IBKR_PORT}")
        except Exception as e:
            print(f"[IBKR] Connection failed: {e}")
            print("[IBKR] Make sure IB Gateway/TWS is running with API enabled")
            self.ib = None

    def _get_contract(self, symbol: str):
        """Build an IBKR contract object for our symbol."""
        from ib_insync import Contract, Crypto, Forex, Future, Stock

        spec = IBKR_CONTRACTS.get(symbol)
        if not spec:
            return None

        if spec["secType"] == "CMDTY":
            contract = Contract(
                symbol=spec["symbol"],
                secType=spec["secType"],
                exchange=spec["exchange"],
                currency=spec["currency"],
            )
        elif spec["secType"] == "FUT":
            # For futures, you need to specify the contract month
            # TODO: auto-detect front month
            contract = Future(
                symbol=spec["symbol"],
                exchange=spec["exchange"],
                currency=spec["currency"],
            )
        elif spec["secType"] == "CRYPTO":
            contract = Crypto(
                symbol=spec["symbol"],
                exchange=spec["exchange"],
                currency=spec["currency"],
            )
        else:
            contract = Stock(
                symbol=spec["symbol"],
                exchange=spec["exchange"],
                currency=spec["currency"],
            )

        self.ib.qualifyContracts(contract)
        return contract

    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        if not self.ib or not self.ib.isConnected():
            return None
        try:
            contract = self._get_contract(symbol)
            if not contract:
                return None
            ticker = self.ib.reqMktData(contract, snapshot=True)
            self.ib.sleep(2)  # Wait for data
            price = ticker.marketPrice()
            if price != price:  # NaN check
                return None
            return {
                "symbol": symbol,
                "price": float(price),
                "high": float(ticker.high) if ticker.high == ticker.high else float(price),
                "low": float(ticker.low) if ticker.low == ticker.low else float(price),
                "open": float(ticker.open) if ticker.open == ticker.open else float(price),
                "volume": int(ticker.volume) if ticker.volume == ticker.volume else 0,
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            print(f"[IBKR] Quote error for {symbol}: {e}")
            return None

    def get_candles(self, symbol: str, resolution: str = "60", count: int = 100) -> Optional[List[Dict[str, Any]]]:
        if not self.ib or not self.ib.isConnected():
            return None
        try:
            contract = self._get_contract(symbol)
            if not contract:
                return None

            # Map resolution to IBKR bar size
            bar_map = {
                "1": "1 min",
                "5": "5 mins",
                "15": "15 mins",
                "30": "30 mins",
                "60": "1 hour",
                "D": "1 day",
            }
            bar_size = bar_map.get(resolution, "1 hour")

            # Duration string (how far back)
            dur_map = {
                "1": f"{count * 60} S",
                "5": f"{count * 5 * 60} S",
                "15": f"{count * 15 * 60} S",
                "30": f"{count * 30 * 60} S",
                "60": f"{count} D",
                "D": f"{count} D",
            }
            duration = dur_map.get(resolution, f"{count} D")

            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime="",
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow="MIDPOINT",
                useRTH=False,
            )

            candles = []
            for bar in bars:
                candles.append(
                    {
                        "timestamp": bar.date.isoformat() if hasattr(bar.date, "isoformat") else str(bar.date),
                        "open": float(bar.open),
                        "high": float(bar.high),
                        "low": float(bar.low),
                        "close": float(bar.close),
                        "volume": int(bar.volume),
                    }
                )
            return candles if candles else None

        except Exception as e:
            print(f"[IBKR] Candles error for {symbol}: {e}")
            return None


class IBKRBroker(Broker):
    """
    Live broker via Interactive Brokers.
    Executes real orders through IB Gateway/TWS.
    """

    def __init__(self, data_provider: IBKRDataProvider):
        self.data = data_provider
        self.ib = data_provider.ib

    def get_account(self) -> Dict[str, Any]:
        if not self.ib or not self.ib.isConnected():
            return {"error": "Not connected to IBKR"}
        try:
            summary = self.ib.accountSummary()
            result = {}
            for item in summary:
                if item.tag == "TotalCashValue":
                    result["balance_usd"] = float(item.value)
                elif item.tag == "NetLiquidation":
                    result["equity_usd"] = float(item.value)
                elif item.tag == "MaintMarginReq":
                    result["used_margin"] = float(item.value)
            result["balance_pln"] = result.get("balance_usd", 0) * 4.05
            result["equity_pln"] = result.get("equity_usd", 0) * 4.05
            result["available_pln"] = result["balance_pln"] - result.get("used_margin", 0) * 4.05
            result["mode"] = "live"
            result["dry_run"] = False
            result["currency"] = "PLN"
            return result
        except Exception as e:
            return {"error": f"Failed to get account: {e}"}

    def open_position(
        self,
        symbol: str,
        direction: str,
        size: float,
        take_profit: Optional[float] = None,
        stop_loss: Optional[float] = None,
        entry_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        if not self.ib or not self.ib.isConnected():
            return {"error": "Not connected to IBKR"}
        try:
            from ib_insync import BracketOrder, LimitOrder, MarketOrder, StopOrder

            contract = self.data._get_contract(symbol)
            if not contract:
                return {"error": f"Unknown IBKR contract for {symbol}"}

            action = "BUY" if direction == "buy" else "SELL"

            if take_profit and stop_loss:
                # Bracket order: entry + TP + SL
                bracket = self.ib.bracketOrder(
                    action=action,
                    quantity=size,
                    limitPrice=entry_price or 0,
                    takeProfitPrice=take_profit,
                    stopLossPrice=stop_loss,
                )
                trades = []
                for order in bracket:
                    trade = self.ib.placeOrder(contract, order)
                    trades.append(trade)
                return {
                    "status": "opened",
                    "position": {
                        "id": str(trades[0].order.orderId),
                        "symbol": symbol,
                        "direction": direction,
                        "size": size,
                        "take_profit": take_profit,
                        "stop_loss": stop_loss,
                        "status": "open",
                    },
                }
            else:
                # Simple market order
                order = MarketOrder(action, size)
                trade = self.ib.placeOrder(contract, order)
                return {
                    "status": "opened",
                    "position": {
                        "id": str(trade.order.orderId),
                        "symbol": symbol,
                        "direction": direction,
                        "size": size,
                        "status": "open",
                    },
                }
        except Exception as e:
            return {"error": f"Order failed: {e}"}

    def close_position(self, position_id: str) -> Dict[str, Any]:
        if not self.ib or not self.ib.isConnected():
            return {"error": "Not connected to IBKR"}
        try:
            # Find the position in IBKR portfolio
            positions = self.ib.positions()
            for pos in positions:
                # Match by order ID or contract
                if str(pos.contract.conId) == position_id:
                    from ib_insync import MarketOrder

                    action = "SELL" if pos.position > 0 else "BUY"
                    order = MarketOrder(action, abs(pos.position))
                    trade = self.ib.placeOrder(pos.contract, order)
                    return {"status": "closed", "order_id": str(trade.order.orderId)}
            return {"error": f"Position {position_id} not found in IBKR"}
        except Exception as e:
            return {"error": f"Close failed: {e}"}

    def get_open_positions(self) -> List[Dict[str, Any]]:
        if not self.ib or not self.ib.isConnected():
            return []
        try:
            positions = self.ib.positions()
            result = []
            for pos in positions:
                if pos.position != 0:
                    result.append(
                        {
                            "id": str(pos.contract.conId),
                            "symbol": pos.contract.symbol,
                            "direction": "buy" if pos.position > 0 else "sell",
                            "size": abs(pos.position),
                            "entry_price": pos.avgCost,
                            "current_price": pos.avgCost,  # Updated by update_prices
                            "unrealized_pnl_usd": 0,
                            "status": "open",
                        }
                    )
            return result
        except Exception:
            return []

    def get_closed_positions(self, limit: int = 50) -> List[Dict[str, Any]]:
        # IBKR doesn't have a simple "closed trades" query via ib_insync
        # You'd need to use executions or flex queries
        # TODO: implement via self.ib.executions() or Flex Web Service
        return []

    def update_prices(self, data_provider: DataProvider) -> None:
        # IBKR positions are updated in real-time by the gateway
        pass
