"""
MongoDB persistence layer for CFD Trading Bot.
Collections: account, trades, signal_cache, candle_cache, quote_cache
Falls back to in-memory if MONGO_URI is not set.
"""
import os
from datetime import datetime
from typing import Optional

_db = None
_connected = False


def get_db():
    """Get MongoDB database instance. Returns None if not configured."""
    global _db, _connected
    if _db is not None:
        return _db
    if _connected:
        return _db

    mongo_uri = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")
    if not mongo_uri:
        _connected = True
        return None

    try:
        from pymongo import MongoClient
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        db_name = os.getenv("MONGO_DB", "cfd_trading_bot")
        _db = client[db_name]
        _connected = True
        return _db
    except Exception as e:
        print(f"[WARNING] MongoDB connection failed: {e}. Using in-memory storage.")
        _connected = True
        return None


# ── Account ──────────────────────────────────────────────────────────

DEFAULT_ACCOUNT = {
    "balance_pln": 10000.0,
    "equity_pln": 10000.0,
    "balance_usd": 2469.14,
    "equity_usd": 2469.14,
    "positions": 0,
    "open_trades": 0,
    "closed_trades": 0,
    "total_pnl_pln": 0.0,
    "total_pnl_usd": 0.0,
    "win_count": 0,
    "loss_count": 0,
    "win_rate": 0.0,
    "used_margin": 0.0,
    "available_pln": 10000.0,
    "dry_run": True,
    "mode": "simulate",
    "currency": "PLN",
}


def load_account() -> dict:
    """Load account state from DB, or return defaults."""
    db = get_db()
    if db is None:
        return {**DEFAULT_ACCOUNT, "last_scan": datetime.utcnow().isoformat()}
    doc = db.account.find_one({"_id": "main"})
    if doc:
        doc.pop("_id", None)
        return doc
    return {**DEFAULT_ACCOUNT, "last_scan": datetime.utcnow().isoformat()}


def save_account(account: dict):
    """Persist current account state."""
    db = get_db()
    if db is None:
        return
    db.account.replace_one({"_id": "main"}, {**account, "_id": "main"}, upsert=True)


# ── Trades ───────────────────────────────────────────────────────────

def load_open_positions() -> list:
    """Load open positions from DB."""
    db = get_db()
    if db is None:
        return []
    docs = list(db.trades.find({"status": "open"}).sort("opened_at", 1))
    for doc in docs:
        doc.pop("_id", None)
    return docs


def load_closed_positions(limit: int = 200) -> list:
    """Load closed positions from DB, most recent first."""
    db = get_db()
    if db is None:
        return []
    docs = list(db.trades.find({"status": "closed"}).sort("closed_at", -1).limit(limit))
    for doc in docs:
        doc.pop("_id", None)
    return docs


def save_trade(trade: dict):
    """Insert or update a trade document (keyed by trade id)."""
    db = get_db()
    if db is None:
        return
    db.trades.replace_one({"id": trade["id"]}, trade, upsert=True)


def delete_all_trades():
    """Remove all trades (used by account reset)."""
    db = get_db()
    if db is None:
        return
    db.trades.delete_many({})


# ── Signal Cache ─────────────────────────────────────────────────────

def load_signal_cache_db() -> dict:
    """Load signal history cache from DB."""
    db = get_db()
    if db is None:
        return {}
    doc = db.signal_cache.find_one({"_id": "cache"})
    if doc:
        doc.pop("_id", None)
        return doc
    return {}


def save_signal_cache_db(cache: dict):
    """Persist signal history cache."""
    db = get_db()
    if db is None:
        return
    db.signal_cache.replace_one({"_id": "cache"}, {**cache, "_id": "cache"}, upsert=True)


def is_connected() -> bool:
    """Check if MongoDB is available."""
    return get_db() is not None


# ── Candle / Quote Cache ────────────────────────────────────────────
# Persists real market data so the app can show the last-known prices
# even when the API is temporarily unavailable.

_candle_mem_cache: dict = {}
_quote_mem_cache: dict = {}


def save_candles(symbol: str, resolution: str, candles: list, source: str):
    """Cache fetched candle data (DB or in-memory)."""
    doc = {
        "symbol": symbol,
        "resolution": resolution,
        "candles": candles,
        "source": source,
        "fetched_at": datetime.utcnow().isoformat(),
    }
    db = get_db()
    if db is not None:
        db.candle_cache.replace_one(
            {"symbol": symbol, "resolution": resolution},
            {**doc, "_id": f"{symbol}_{resolution}"},
            upsert=True,
        )
    _candle_mem_cache[f"{symbol}_{resolution}"] = doc


def load_candles(symbol: str, resolution: str) -> Optional[dict]:
    """Load cached candle data. Returns dict with candles, source, fetched_at or None."""
    db = get_db()
    if db is not None:
        doc = db.candle_cache.find_one({"symbol": symbol, "resolution": resolution})
        if doc:
            doc.pop("_id", None)
            return doc
    cached = _candle_mem_cache.get(f"{symbol}_{resolution}")
    return cached


def save_quote(symbol: str, quote: dict):
    """Cache a price quote (DB or in-memory)."""
    doc = {
        "symbol": symbol,
        "quote": quote,
        "fetched_at": datetime.utcnow().isoformat(),
    }
    db = get_db()
    if db is not None:
        db.quote_cache.replace_one(
            {"symbol": symbol},
            {**doc, "_id": f"quote_{symbol}"},
            upsert=True,
        )
    _quote_mem_cache[symbol] = doc


def load_quote(symbol: str) -> Optional[dict]:
    """Load cached quote. Returns dict with quote, fetched_at or None."""
    db = get_db()
    if db is not None:
        doc = db.quote_cache.find_one({"symbol": symbol})
        if doc:
            doc.pop("_id", None)
            return doc
    return _quote_mem_cache.get(symbol)
