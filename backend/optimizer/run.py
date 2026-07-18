"""Nightly optimization run.

Usage:
    python -m optimizer.run --symbol BTC            # one symbol
    python -m optimizer.run --nightly               # all enabled strategies
    python -m optimizer.run --nightly --dry-run     # search + guards, no promotion
"""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import database  # noqa: E402
from optimizer import promote as promo  # noqa: E402
from optimizer.search import optimize_strategy  # noqa: E402


# Timeframes fetched from Binance for BTC (tf.value == Binance kline interval)
_BINANCE_TIMEFRAMES = {"5m", "15m", "1h", "4h", "1d"}
_BINANCE_HISTORY_DAYS = 730
_BINANCE_CACHE_MAX_AGE_HOURS = 24
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _cache_newest_ms(cached: list) -> int | None:
    """Epoch ms of the newest cached candle, or None."""
    if not cached:
        return None
    try:
        ts = cached[-1]["timestamp"].replace("Z", "").split("+")[0].split(".")[0]
        dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except (KeyError, ValueError, AttributeError, IndexError, TypeError):
        return None


def _binance_history_cached(interval: str, days: int = _BINANCE_HISTORY_DAYS) -> list:
    """730d of BTCUSDT history with a local JSON cache.

    Full pagination (~210 requests for 5m) runs only when the cache is missing
    or stale (newest candle >= 24h old). A fresh cache only fetches the tail
    from its newest candle and merges.
    """
    from binance_data import fetch_binance_history

    cache_file = _DATA_DIR / f"binance_hist_{interval}.json"
    cached = []
    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text())
        except (ValueError, OSError):
            cached = []

    newest_ms = _cache_newest_ms(cached)
    now_ms = int(time.time() * 1000)
    if newest_ms is not None and now_ms - newest_ms < _BINANCE_CACHE_MAX_AGE_HOURS * 3600 * 1000:
        tail = fetch_binance_history("BTCUSDT", interval=interval, days=days, start_ms=newest_ms)
        merged = {c["timestamp"]: c for c in cached}
        merged.update({c["timestamp"]: c for c in tail})
        candles = [merged[k] for k in sorted(merged)]
    else:
        candles = fetch_binance_history("BTCUSDT", interval=interval, days=days)

    if candles:
        try:
            _DATA_DIR.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(candles))
        except OSError as e:
            print(f"[OPTIMIZE] could not write binance cache {cache_file}: {e}")
    return candles


def _fetch_candles(symbol: str, config: dict) -> dict:
    from historical_data import fetch_yahoo_historical
    from strategy.engine import SignalEngine

    engine = SignalEngine(config)
    out = {}
    for tf in engine.required_timeframes():
        if symbol.upper() == "BTC" and tf.value in _BINANCE_TIMEFRAMES:
            candles = _binance_history_cached(tf.value)
        else:
            days = {"5m": 55, "15m": 55, "30m": 55, "1h": 320, "4h": 320, "1d": 700}.get(tf.value, 55)
            candles = fetch_yahoo_historical(symbol, period_days=days, interval=tf.yahoo_interval)
        if candles:
            out[tf.value] = candles
    return out


def run_for_strategy(strategy: dict, n_trials: int, dry_run: bool) -> dict:
    sid, symbol = strategy["id"], strategy["symbol"]
    print(f"[OPTIMIZE] {sid} ({symbol}): fetching history...")
    candles = _fetch_candles(symbol, strategy)
    base_tf = strategy.get("base_timeframe", strategy.get("timeframe", "5m"))
    if base_tf not in candles or len(candles[base_tf]) < 500:
        return {"strategy_id": sid, "error": f"not enough {base_tf} history"}

    result = optimize_strategy(strategy, candles, n_trials=n_trials, champion_config=strategy)
    result["strategy_id"] = sid
    mongo = None
    try:
        mongo = database.get_db()
    except Exception:
        pass
    if mongo is not None:
        mongo.optimization_studies.insert_one({
            "strategy_id": sid, "symbol": symbol, "at": datetime.utcnow().isoformat(),
            "passed": result.get("passed"), "best_value": result.get("best_value"),
            "guard_report": result.get("guard_report"), "config_hash": result.get("config_hash"),
        })

    if result.get("passed") and not dry_run:
        promo.promote(sid, result["best_config"], result["guard_report"])
        result["promoted"] = True
    else:
        result["promoted"] = False
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", help="optimize strategies for one symbol")
    parser.add_argument("--nightly", action="store_true", help="all enabled strategies")
    parser.add_argument("--trials", type=int, default=75)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not promo.optimizer_enabled():
        print("[OPTIMIZE] OPTIMIZER_ENABLED=0 - exiting")
        return

    strategies = json.loads((Path(__file__).resolve().parent.parent / "strategies.json").read_text())
    targets = [s for s in strategies["strategies"] if s.get("enabled", True)]
    if args.symbol:
        targets = [s for s in targets if s["symbol"].upper() == args.symbol.upper()]
    if not targets:
        print("[OPTIMIZE] no matching strategies")
        return

    for strategy in targets:
        try:
            result = run_for_strategy(strategy, args.trials, args.dry_run)
        except Exception as e:
            result = {"strategy_id": strategy["id"], "error": str(e)}
        status = "PROMOTED" if result.get("promoted") else ("passed" if result.get("passed") else "rejected")
        print(f"[OPTIMIZE] {result.get('strategy_id')}: {status} "
              f"(best={result.get('best_value')}, err={result.get('error')})")


if __name__ == "__main__":
    main()
