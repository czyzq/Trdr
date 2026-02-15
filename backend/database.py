"""
MongoDB persistence layer for CFD Trading Bot.
Collections: account, trades, signal_cache, candle_cache, quote_cache, candles, event_log
Falls back to in-memory if MONGO_URI is not set.
"""
import os
from collections import OrderedDict
from datetime import datetime
from typing import List, Optional

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
    mongo_db = os.getenv("MONGO_DB", "cfd_trading_bot")
    
    print(f"[DB] Checking MongoDB config...")
    print(f"[DB] MONGO_URI set: {bool(mongo_uri)} (length: {len(mongo_uri) if mongo_uri else 0})")
    print(f"[DB] MONGO_DB: {mongo_db}")
    
    if not mongo_uri:
        print(f"[DB] MONGO_URI not set - using in-memory storage")
        _connected = True
        return None

    try:
        from pymongo import MongoClient
        print(f"[DB] Connecting to MongoDB...")
        
        # Simplified connection for Render - let MongoDB driver handle SSL
        client = MongoClient(
            mongo_uri,
            serverSelectionTimeoutMS=10000,
        )
        client.admin.command("ping")
        print(f"[DB] ✅ MongoDB connected successfully")
        
        _db = client[mongo_db]
        _connected = True
        print(f"[DB] ✅ MongoDB connected successfully to database: {mongo_db}")
        
        # Test write access
        try:
            _db.test_connection.insert_one({"test": True, "timestamp": datetime.utcnow()})
            _db.test_connection.delete_one({"test": True})
            print(f"[DB] ✅ Write access confirmed")
        except Exception as write_err:
            print(f"[DB] ⚠️ Connected but write test failed: {write_err}")
        
        return _db
    except Exception as e:
        print(f"[DB] ❌ MongoDB connection failed: {type(e).__name__}: {e}")
        print(f"[DB] Using in-memory storage - data will be lost on restart!")
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


def count_closed_positions() -> int:
    """Count total closed trades in DB."""
    db = get_db()
    if db is None:
        return 0
    return db.trades.count_documents({"status": "closed"})


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


# ── Candle History (accumulating time-series) ──────────────────────
# Stores individual candles as documents, never overwrites.
# Key: (symbol, resolution, timestamp) — upserts to avoid duplicates.
# This builds a growing historical dataset for backtesting.

_candle_history_mem: dict = {}  # In-memory fallback: {symbol_resolution: [candles]}


def store_candles(symbol: str, resolution: str, candles: list, source: str = ""):
    """
    Accumulate candles into persistent history.
    Each candle is stored as its own document keyed by (symbol, resolution, timestamp).
    Existing candles are updated (upsert), new ones are inserted — no data lost.
    """
    if not candles:
        return

    db = get_db()
    if db is not None:
        from pymongo import UpdateOne
        ops = []
        for c in candles:
            ts = c.get("timestamp", "")
            if not ts:
                continue
            doc = {
                "symbol": symbol,
                "resolution": resolution,
                "timestamp": ts,
                "open": c["open"],
                "high": c["high"],
                "low": c["low"],
                "close": c["close"],
                "volume": c.get("volume", 0),
                "source": source,
            }
            ops.append(UpdateOne(
                {"symbol": symbol, "resolution": resolution, "timestamp": ts},
                {"$set": doc},
                upsert=True,
            ))
        if ops:
            db.candles.bulk_write(ops, ordered=False)
    else:
        # In-memory fallback
        key = f"{symbol}_{resolution}"
        existing = {c.get("timestamp"): c for c in _candle_history_mem.get(key, [])}
        for c in candles:
            ts = c.get("timestamp", "")
            if ts:
                existing[ts] = c
        _candle_history_mem[key] = sorted(existing.values(), key=lambda x: x.get("timestamp", ""))


def load_candle_history(
    symbol: str,
    resolution: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    limit: int = 0,
) -> list:
    """
    Load accumulated candle history from DB.
    Optional time range filter (ISO timestamps).
    Returns candles sorted oldest-first (chronological).
    """
    db = get_db()
    if db is not None:
        query: dict = {"symbol": symbol, "resolution": resolution}
        if start or end:
            ts_filter: dict = {}
            if start:
                ts_filter["$gte"] = start
            if end:
                ts_filter["$lte"] = end
            query["timestamp"] = ts_filter

        cursor = db.candles.find(query).sort("timestamp", 1)
        if limit > 0:
            cursor = cursor.limit(limit)
        docs = list(cursor)
        for doc in docs:
            doc.pop("_id", None)
        return docs

    # In-memory fallback
    key = f"{symbol}_{resolution}"
    all_candles = _candle_history_mem.get(key, [])
    if start:
        all_candles = [c for c in all_candles if c.get("timestamp", "") >= start]
    if end:
        all_candles = [c for c in all_candles if c.get("timestamp", "") <= end]
    if limit > 0:
        all_candles = all_candles[-limit:]
    return all_candles


def count_candles(symbol: str, resolution: str) -> int:
    """Count stored candles for a symbol/resolution pair."""
    db = get_db()
    if db is not None:
        return db.candles.count_documents({"symbol": symbol, "resolution": resolution})
    key = f"{symbol}_{resolution}"
    return len(_candle_history_mem.get(key, []))


def get_candle_date_range(symbol: str, resolution: str) -> Optional[dict]:
    """Get the earliest and latest timestamp for stored candles."""
    db = get_db()
    if db is not None:
        query = {"symbol": symbol, "resolution": resolution}
        first = db.candles.find_one(query, sort=[("timestamp", 1)])
        last = db.candles.find_one(query, sort=[("timestamp", -1)])
        if first and last:
            return {"first": first["timestamp"], "last": last["timestamp"]}
        return None
    key = f"{symbol}_{resolution}"
    candles = _candle_history_mem.get(key, [])
    if candles:
        return {"first": candles[0].get("timestamp", ""), "last": candles[-1].get("timestamp", "")}
    return None


def ensure_candle_indexes():
    """Create indexes on the candles collection for fast queries."""
    db = get_db()
    if db is None:
        return
    db.candles.create_index(
        [("symbol", 1), ("resolution", 1), ("timestamp", 1)],
        unique=True,
        background=True,
    )
    db.candles.create_index(
        [("symbol", 1), ("resolution", 1)],
        background=True,
    )


# ── Candle Aggregation ────────────────────────────────────────────
# Build larger interval candles from smaller stored ones.

AGGREGATION_MAP = {
    "5": ("1", 5),
    "15": ("5", 3),    # or ("1", 15)
    "30": ("15", 2),   # or ("5", 6)
    "60": ("30", 2),   # or ("15", 4)
    "240": ("60", 4),  # 4H from 1H
    "D": ("60", None), # daily from hourly — group by date
}


def aggregate_candles(candles: list, target_resolution: str) -> list:
    """
    Aggregate smaller-interval candles into larger ones.
    For "D" (daily): groups by date.
    For numeric resolutions: groups every N candles.
    """
    if not candles:
        return []

    if target_resolution == "D":
        # Group by date
        days: OrderedDict = OrderedDict()
        for c in candles:
            ts = c.get("timestamp", "")
            date_key = ts.split("T")[0] if "T" in ts else ""
            if not date_key:
                continue
            if date_key not in days:
                days[date_key] = {
                    "timestamp": date_key + "T00:00:00",
                    "time": datetime.fromisoformat(date_key).strftime("%m/%d") if len(date_key) == 10 else date_key,
                    "open": c["open"],
                    "high": c["high"],
                    "low": c["low"],
                    "close": c["close"],
                    "volume": c.get("volume", 0),
                }
            else:
                day = days[date_key]
                day["high"] = max(day["high"], c["high"])
                day["low"] = min(day["low"], c["low"])
                day["close"] = c["close"]
                day["volume"] += c.get("volume", 0)
        return list(days.values())

    # Numeric grouping
    try:
        n = int(target_resolution)
    except ValueError:
        return candles

    # Determine source interval from first two timestamps
    if len(candles) >= 2:
        t0 = candles[0].get("timestamp", "")
        t1 = candles[1].get("timestamp", "")
        try:
            dt0 = datetime.fromisoformat(t0)
            dt1 = datetime.fromisoformat(t1)
            src_minutes = max(1, int((dt1 - dt0).total_seconds() / 60))
        except (ValueError, TypeError):
            src_minutes = 1
    else:
        src_minutes = 1

    group_size = max(1, n // src_minutes)
    result = []
    for i in range(0, len(candles), group_size):
        group = candles[i:i + group_size]
        if not group:
            continue
        result.append({
            "timestamp": group[0].get("timestamp", ""),
            "time": group[0].get("time", ""),
            "open": group[0]["open"],
            "high": max(c["high"] for c in group),
            "low": min(c["low"] for c in group),
            "close": group[-1]["close"],
            "volume": sum(c.get("volume", 0) for c in group),
        })
    return result


# ── Event Log ──────────────────────────────────────────────────────
# Persists the last N log entries so they survive restarts.

def save_event_log(events: list, max_entries: int = 200):
    """Persist recent event log entries to DB."""
    db = get_db()
    if db is None:
        return
    # Keep only the most recent entries
    trimmed = events[-max_entries:] if len(events) > max_entries else events
    db.event_log.replace_one(
        {"_id": "log"},
        {"_id": "log", "entries": trimmed, "updated_at": datetime.utcnow().isoformat()},
        upsert=True,
    )


def load_event_log() -> list:
    """Load persisted event log entries from DB."""
    db = get_db()
    if db is None:
        return []
    doc = db.event_log.find_one({"_id": "log"})
    if doc and "entries" in doc:
        return doc["entries"]
    return []


# =============================================================================
# ASYNC WRAPPERS - Non-blocking database operations
# =============================================================================
import asyncio

async def async_load_account() -> dict:
    """Async: Load account state from DB."""
    return await asyncio.to_thread(load_account)

async def async_save_account(account: dict):
    """Async: Persist account state."""
    return await asyncio.to_thread(save_account, account)

async def async_load_open_positions() -> list:
    """Async: Load open positions."""
    return await asyncio.to_thread(load_open_positions)

async def async_load_closed_positions(limit: int = 200) -> list:
    """Async: Load closed positions."""
    return await asyncio.to_thread(load_closed_positions, limit)

async def async_save_trade(trade: dict):
    """Async: Save trade to DB."""
    return await asyncio.to_thread(save_trade, trade)

async def async_load_candle_history(
    symbol: str,
    resolution: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    limit: int = 0,
) -> list:
    """Async: Load candle history."""
    return await asyncio.to_thread(load_candle_history, symbol, resolution, start, end, limit)

async def async_store_candles(symbol: str, resolution: str, candles: list, source: str = ""):
    """Async: Store candles to history."""
    return await asyncio.to_thread(store_candles, symbol, resolution, candles, source)

async def async_load_candles(symbol: str, resolution: str) -> Optional[dict]:
    """Async: Load cached candles."""
    return await asyncio.to_thread(load_candles, symbol, resolution)

async def async_save_candles(symbol: str, resolution: str, candles: list, source: str):
    """Async: Save candles to cache."""
    return await asyncio.to_thread(save_candles, symbol, resolution, candles, source)

async def async_load_signal_cache_db() -> dict:
    """Async: Load signal cache."""
    return await asyncio.to_thread(load_signal_cache_db)

async def async_save_signal_cache_db(cache: dict):
    """Async: Save signal cache."""
    return await asyncio.to_thread(save_signal_cache_db, cache)

async def async_save_event_log(events: list, max_entries: int = 200):
    """Async: Persist event log."""
    return await asyncio.to_thread(save_event_log, events, max_entries)

async def async_load_event_log() -> list:
    """Async: Load event log."""
    return await asyncio.to_thread(load_event_log)


async def async_count_closed_positions() -> int:
    """Async: Count closed positions."""
    return await asyncio.to_thread(count_closed_positions)


async def async_delete_all_trades():
    """Async: Delete all trades."""
    return await asyncio.to_thread(delete_all_trades)


async def async_count_candles(symbol: str, resolution: str) -> int:
    """Async: Count candles."""
    return await asyncio.to_thread(count_candles, symbol, resolution)


async def async_get_candle_date_range(symbol: str, resolution: str) -> Optional[dict]:
    """Async: Get candle date range."""
    return await asyncio.to_thread(get_candle_date_range, symbol, resolution)


async def async_save_quote(symbol: str, quote: dict):
    """Async: Save quote to cache."""
    return await asyncio.to_thread(save_quote, symbol, quote)


async def async_load_quote(symbol: str) -> Optional[dict]:
    """Async: Load cached quote."""
    return await asyncio.to_thread(load_quote, symbol)
