"""Settings API routes - extracted from main.py
Endpoints: /api/settings, /api/trading-mode, /api/settings/dynamic-positions, /api/settings/indicators/{symbol}
"""

from fastapi import APIRouter, Body
import database as db
from settings import get_all_settings

router = APIRouter(tags=["settings"])

# All available indicators (moved from main.py)
ALL_INDICATORS = ["RSI", "MACD", "BB", "SMA", "ADX", "STOCH", "MOMENTUM", "WILLIAMS_R", "DIVERGENCE", "HTF_CANDLE"]


# These endpoints need access to globals from main.py
# Factory pattern to create routes with proper references
def create_settings_endpoints(log_event_ref, INSTRUMENTS_ref, list_strategies_ref):
    """Create settings endpoints with log_event, INSTRUMENTS, and list_strategies references"""
    
    @router.get("/api/settings")
    async def get_settings():
        """Get all settings including broker-specific refresh rates."""
        db_settings = db.list_settings()
        broker_settings = get_all_settings()
        return {
            "db": db_settings,
            "broker": broker_settings,
        }

    @router.post("/api/settings")
    async def set_setting(key: str, value: str):
        """Set a setting in the database."""
        db.set_setting(key, value, "api")
        log_event_ref(f"[SETTINGS] Updated {key} = {value}", "event")
        return {"status": "ok", "key": key, "value": value}

    @router.get("/api/trading-mode")
    async def get_trading_mode():
        """Get current trading mode from DB settings."""
        broker = db.get_setting("PREFERRED_BROKER", "sim")
        auto_trade = db.get_setting("AUTO_TRADE_ENABLED", False)
        # Map internal "sim" to frontend "simulation"
        broker_display = "simulation" if broker == "sim" else "ibkr"
        return {
            "broker": broker_display,
            "autoTrade": bool(auto_trade),
        }

    @router.post("/api/trading-mode")
    async def set_trading_mode(broker: str = "simulation", autoTrade: bool = False):
        """Set trading mode in DB settings."""
        # Map frontend "simulation" to internal "sim"
        broker_type = "sim" if broker == "simulation" else broker
        db.set_setting("PREFERRED_BROKER", broker_type, "system")
        db.set_setting("AUTO_TRADE_ENABLED", 1 if autoTrade else 0, "system")
        log_event_ref(f"[TRADING-MODE] Broker: {broker}, Auto-trade: {'ON' if autoTrade else 'OFF'}", "event")
        return {"status": "ok", "broker": broker_type, "auto_trade": autoTrade}

    @router.post("/api/settings/dynamic-positions")
    async def set_dynamic_positions(enabled: bool = True):
        """Enable/disable dynamic position sizing."""
        db.set_setting("DYNAMIC_POSITIONS_ENABLED", 1 if enabled else 0, "system")
        log_event_ref(f"[DYNAMIC-POSITIONS] {'Enabled' if enabled else 'Disabled'}", "event")
        return {"status": "ok", "enabled": enabled}

    @router.get("/api/settings/indicators/{symbol}")
    async def get_indicators_for_symbol(symbol: str):
        """Get enabled indicators for a symbol."""
        symbol = symbol.upper()
        if symbol not in INSTRUMENTS_ref:
            return {"error": f"Unknown symbol: {symbol}"}

        # Get from DB or use defaults
        key = f"INDICATORS_{symbol}"
        indicators = db.get_setting(key)
        if not indicators:
            indicators = ALL_INDICATORS

        # Also get strategy for this symbol
        strategy_key = f"STRATEGY_{symbol}"
        strategy = db.get_setting(strategy_key, "mms")

        return {
            "symbol": symbol,
            "indicators": indicators,
            "strategy": strategy,
            "available_indicators": ALL_INDICATORS,
        }

    @router.post("/api/settings/indicators/{symbol}")
    async def set_indicators_for_symbol(
        symbol: str,
        body: dict = Body(...),
    ):
        """Set enabled indicators for a symbol."""
        symbol = symbol.upper()
        if symbol not in INSTRUMENTS_ref:
            return {"error": f"Unknown symbol: {symbol}"}

        indicators = body.get("indicators", ALL_INDICATORS)
        strategy = body.get("strategy", "mms")

        # Validate indicators
        invalid = [i for i in indicators if i not in ALL_INDICATORS]
        if invalid:
            return {"error": f"Invalid indicators: {invalid}. Available: {ALL_INDICATORS}"}

        # Validate strategy
        valid_strategies = [s["id"] for s in list_strategies_ref()]
        if strategy not in valid_strategies:
            return {"error": f"Invalid strategy: {strategy}. Available: {valid_strategies}"}

        # Save to DB
        key = f"INDICATORS_{symbol}"
        db.set_setting(key, indicators, "user")

        strategy_key = f"STRATEGY_{symbol}"
        db.set_setting(strategy_key, strategy, "user")

        log_event_ref(f"[INDICATORS] {symbol}: indicators={indicators}, strategy={strategy}", "event")
        return {
            "symbol": symbol,
            "indicators": indicators,
            "strategy": strategy,
        }

    @router.delete("/api/settings/{key}")
    async def delete_setting(key: str):
        """Delete a setting by key."""
        db.settings_current.delete_one({"key": key})
        return {"status": "deleted", "settings": db.list_settings()}

    return router
