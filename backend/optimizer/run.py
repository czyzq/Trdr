"""Nightly optimization run.

Usage:
    python -m optimizer.run --symbol BTC            # one symbol
    python -m optimizer.run --nightly               # all enabled strategies
    python -m optimizer.run --nightly --dry-run     # search + guards, no promotion
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import database  # noqa: E402
from optimizer import promote as promo  # noqa: E402
from optimizer.search import optimize_strategy  # noqa: E402


def _fetch_candles(symbol: str, config: dict) -> dict:
    from historical_data import fetch_yahoo_historical
    from strategy.engine import SignalEngine

    engine = SignalEngine(config)
    out = {}
    for tf in engine.required_timeframes():
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
