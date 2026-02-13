"""
Broker abstraction layer for CFD Trading Bot.

Defines the interfaces for:
  - DataProvider: price quotes, candles, news
  - Broker: order execution, position management, account info

Switch between simulated and live brokers via BROKER_TYPE env var.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime


class DataProvider(ABC):
    """Interface for market data (quotes, candles)."""

    @abstractmethod
    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get current quote for a symbol.
        Returns: {"symbol", "price", "high", "low", "open", "volume", "timestamp"}
        """
        ...

    @abstractmethod
    def get_candles(
        self, symbol: str, resolution: str = "60", count: int = 100
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get historical OHLCV candles.
        resolution: "1", "5", "15", "30", "60", "D"
        Returns list of: {"timestamp", "open", "high", "low", "close", "volume"}
        """
        ...


class Broker(ABC):
    """Interface for trade execution and account management."""

    @abstractmethod
    def get_account(self) -> Dict[str, Any]:
        """
        Get account summary.
        Returns: {"balance", "equity", "used_margin", "available", "currency", ...}
        """
        ...

    @abstractmethod
    def open_position(
        self,
        symbol: str,
        direction: str,
        size: float,
        take_profit: Optional[float] = None,
        stop_loss: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Open a new position.
        direction: "buy" or "sell"
        Returns: {"status": "opened", "position": {...}} or {"error": "..."}
        """
        ...

    @abstractmethod
    def close_position(self, position_id: str) -> Dict[str, Any]:
        """
        Close an existing position by ID.
        Returns: {"status": "closed", "position": {...}} or {"error": "..."}
        """
        ...

    @abstractmethod
    def get_open_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions with live P&L."""
        ...

    @abstractmethod
    def get_closed_positions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get closed trade history."""
        ...

    @abstractmethod
    def update_prices(self, data_provider: DataProvider):
        """Update open positions with latest prices from data provider.
        May return a list of auto-closed positions (TP/SL hits)."""
        ...
