"""Central state management for CFD Trading Bot
Replaces global variables in main.py - provides clean API for all services
"""
from typing import Dict, Any

from broker_factory import create_broker, create_data_provider

data_provider = create_data_provider()
broker = create_broker(data_provider)

# Core state
account: Dict[str, Any] = {}
open_positions: list = []
closed_positions: list = []
signals_cache: Dict[str, Any] = {}
signal_history_cache: Dict[str, Any] = {}

# Strategy selection (per-symbol)
_strategy_selection: Dict[str, str] = {}

# Signals cache
signals_cache: Dict[str, Any] = {}

# Timing stats
_timing_stats: Dict[str, Dict] = {}


def get_timing_stats() -> Dict[str, Dict]:
    """Get timing stats"""
    return _timing_stats


def reset_timing_stats() -> None:
    """Reset timing stats"""
    global _timing_stats
    _timing_stats = {}


# Signals cache
_signals_cache: Dict[str, Any] = {}


def get_signals_cache() -> Dict[str, Any]:
    """Get signals cache"""
    return _signals_cache


def set_signals_cache(cache: Dict[str, Any]) -> None:
    """Set signals cache"""
    global _signals_cache
    _signals_cache = cache

# Price cache
_live_price_cache: Dict[str, Dict[str, Any]] = {}
_live_price_cache_last_update: float = 0

# Settings
INSTRUMENTS: Dict[str, Dict[str, Any]] = {}

INITIAL_BALANCE_USD: float = 3000.0

# Trading state
AUTO_TRADE_ENABLED: bool = False
AUTO_TRADE_INTERVAL_SEC: int = 300


def get_account() -> Dict[str, Any]:
    """Get current account state"""
    return account


def set_account(new_account: Dict[str, Any]) -> None:
    """Update account state"""
    global account
    account = new_account


def get_open_positions() -> list:
    """Get open positions"""
    return open_positions


def set_open_positions(positions: list) -> None:
    """Update open positions"""
    global open_positions
    open_positions = positions


def get_closed_positions() -> list:
    """Get closed positions"""
    return closed_positions


def set_closed_positions(positions: list) -> None:
    """Update closed positions"""
    global closed_positions
    closed_positions = positions


def get_signals_cache() -> Dict[str, Any]:
    """Get signals cache"""
    return signals_cache


def set_signals_cache(cache: Dict[str, Any]) -> None:
    """Update signals cache"""
    global signals_cache
    signals_cache = cache


def get_signal_history_cache() -> Dict[str, Any]:
    """Get signal history cache"""
    return signal_history_cache


def set_signal_history_cache(cache: Dict[str, Any]) -> None:
    """Update signal history cache"""
    global signal_history_cache
    signal_history_cache = cache


def get_live_price_cache() -> Dict[str, Dict[str, Any]]:
    """Get live price cache"""
    return _live_price_cache


def update_live_price_cache(symbol: str, price_data: Dict[str, Any]) -> None:
    """Update price for a symbol"""
    global _live_price_cache, _live_price_cache_last_update
    import time
    _live_price_cache[symbol] = price_data
    _live_price_cache_last_update = time.time()


def get_price_cache_last_update() -> float:
    """Get last price cache update time"""
    return _live_price_cache_last_update


def get_auto_trade_enabled() -> bool:
    """Get auto trade enabled state"""
    return AUTO_TRADE_ENABLED


def set_auto_trade_enabled(enabled: bool) -> None:
    """Set auto trade enabled state"""
    global AUTO_TRADE_ENABLED
    AUTO_TRADE_ENABLED = enabled


def get_auto_trade_interval() -> int:
    """Get auto trade interval in seconds"""
    return AUTO_TRADE_INTERVAL_SEC


def set_auto_trade_interval(seconds: int) -> None:
    """Set auto trade interval"""
    global AUTO_TRADE_INTERVAL_SEC
    AUTO_TRADE_INTERVAL_SEC = seconds


def get_instruments() -> Dict[str, Dict[str, Any]]:
    """Get instruments config"""
    return INSTRUMENTS


def set_instruments(instruments: Dict[str, Dict[str, Any]]) -> None:
    """Set instruments config"""
    global INSTRUMENTS
    INSTRUMENTS = instruments


def get_initial_balance() -> float:
    """Get initial balance"""
    return INITIAL_BALANCE_USD


def set_initial_balance(balance: float) -> None:
    """Set initial balance"""
    global INITIAL_BALANCE_USD
    INITIAL_BALANCE_USD = balance


# Strategy selection
def get_symbol_strategy(symbol: str) -> str:
    """Get strategy for symbol"""
    return _strategy_selection.get(symbol, "adaptive_regime")


def set_symbol_strategy(symbol: str, strategy_id: str) -> None:
    """Set strategy for symbol"""
    global _strategy_selection
    _strategy_selection[symbol] = strategy_id


def get_all_strategy_selections() -> Dict[str, str]:
    """Get all symbol strategy selections"""
    return _strategy_selection.copy()
