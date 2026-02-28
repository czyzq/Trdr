"""
Candle Data Quality Validator

Checks:
1. Coverage - do all symbols have the same date range?
2. Price sanity - are there unrealistic price jumps?
3. Data completeness - are there gaps in the timeline?

Usage:
    python validate_candles.py --symbol XAU --resolution 60
    python validate_candles.py --all
    python validate_candles.py --fix  # Delete bad data
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from database import get_db


# Thresholds for validation
MAX_INTRADAY_GAP_PCT = 50  # 50% intraday move is unrealistic
MAX_DAILY_GAP_PCT = 30     # 30% daily move is suspicious
MIN_PRICES = {
    "XAU": 1000,   # Gold can't be below $1000
    "XAG": 10,     # Silver can't be below $10
    "BTC": 10000,  # BTC can't be below $10k in 2025+
    "US100": 10000,# Nasdaq can't be below 10k
}
MAX_PRICES = {
    "XAU": 10000,  # Gold can't be above $10000
    "XAG": 200,    # Silver can't be above $200
    "BTC": 200000, # BTC can't be above $200k
    "US100": 100000,
}


def validate_symbol(symbol: str, resolution: str = "60", fix: bool = False) -> dict:
    """Validate candle data for a symbol."""
    db = get_db()
    if db is None:
        print("  [DB] Not connected")
        return {}
    
    candles = list(db.candles.find(
        {"symbol": symbol, "resolution": resolution}
    ).sort("timestamp", 1))
    
    if not candles:
        print(f"  ❌ No data for {symbol} {resolution}m")
        return {}
    
    first_ts = candles[0]["timestamp"]
    last_ts = candles[-1]["timestamp"]
    
    issues = {
        "total": len(candles),
        "first": first_ts,
        "last": last_ts,
        "price_issues": [],
        "gap_issues": [],
    }
    
    # Check for unrealistic prices
    min_price = MIN_PRICES.get(symbol, 1)
    max_price = MAX_PRICES.get(symbol, 999999)
    
    for c in candles:
        close = c.get("close", 0)
        open_p = c.get("open", 0)
        
        if close < min_price or close > max_price:
            issues["price_issues"].append({
                "timestamp": c["timestamp"],
                "open": open_p,
                "close": close,
                "reason": f"price {close} outside {min_price}-{max_price}"
            })
        
        if open_p < min_price or open_p > max_price:
            issues["price_issues"].append({
                "timestamp": c["timestamp"],
                "open": open_p,
                "close": close,
                "reason": f"open {open_p} outside {min_price}-{max_price}"
            })
    
    # Check for unrealistic gaps
    for i in range(1, len(candles)):
        prev = candles[i-1]
        curr = candles[i]
        
        prev_close = prev.get("close", 0)
        curr_close = curr.get("close", 0)
        
        if prev_close <= 0 or curr_close <= 0:
            continue
        
        # Calculate gap percentage
        gap_pct = abs(curr_close - prev_close) / prev_close * 100
        
        # Calculate time difference
        prev_ts = prev.get("timestamp", "")
        curr_ts = curr.get("timestamp", "")
        
        try:
            prev_dt = datetime.fromisoformat(prev_ts.replace("Z", "+00:00"))
            curr_dt = datetime.fromisoformat(curr_ts.replace("Z", "+00:00"))
            hours_diff = (curr_dt - prev_dt).total_seconds() / 3600
        except:
            hours_diff = 1
        
        # Determine threshold based on timeframe
        if resolution == "60":
            threshold = MAX_INTRADAY_GAP_PCT if hours_diff < 36 else MAX_DAILY_GAP_PCT
        else:
            threshold = MAX_DAILY_GAP_PCT
        
        if gap_pct > threshold:
            issues["gap_issues"].append({
                "timestamp": curr_ts,
                "prev_close": prev_close,
                "close": curr_close,
                "gap_pct": round(gap_pct, 1),
                "hours": round(hours_diff, 1),
                "reason": f"{gap_pct:.1f}% in {hours_diff:.0f}h"
            })
    
    # Fix if requested
    if fix and (issues["price_issues"] or issues["gap_issues"]):
        print(f"  🔧 Fixing {symbol}...")
        
        # Delete price issues
        if issues["price_issues"]:
            for issue in issues["price_issues"]:
                db.candles.delete_one({
                    "symbol": symbol,
                    "resolution": resolution,
                    "timestamp": issue["timestamp"]
                })
            print(f"     Deleted {len(issues['price_issues'])} price issues")
        
        # Delete extreme gaps
        if issues["gap_issues"]:
            # Delete candles with gaps > 100% (clearly bad data)
            for issue in issues["gap_issues"]:
                if issue["gap_pct"] > 100:
                    db.candles.delete_one({
                        "symbol": symbol,
                        "resolution": resolution,
                        "timestamp": issue["timestamp"]
                    })
            print(f"     Deleted {len([g for g in issues['gap_issues'] if g['gap_pct'] > 100])} extreme gap issues")
    
    return issues


def check_coverage(resolution: str = "60"):
    """Check coverage across all symbols."""
    db = get_db()
    if db is None:
        print("[DB] Not connected")
        return
    
    print(f"\n{'='*60}")
    print(f"  COVERAGE CHECK - {resolution}m resolution")
    print(f"{'='*60}")
    
    symbols = ["XAU", "XAG", "BTC", "US100"]
    all_data = {}
    
    for symbol in symbols:
        count = db.candles.count_documents({"symbol": symbol, "resolution": resolution})
        
        first = db.candles.find_one(
            {"symbol": symbol, "resolution": resolution},
            sort=[("timestamp", 1)]
        )
        last = db.candles.find_one(
            {"symbol": symbol, "resolution": resolution},
            sort=[("timestamp", -1)]
        )
        
        first_ts = first["timestamp"][:10] if first else "N/A"
        last_ts = last["timestamp"][:10] if last else "N/A"
        
        all_data[symbol] = {
            "count": count,
            "first": first_ts,
            "last": last_ts
        }
        
        print(f"{symbol:8} {count:>6} candles | {first_ts} → {last_ts}")
    
    # Check if ranges match
    first_dates = set(d["first"] for d in all_data.values())
    last_dates = set(d["last"] for d in all_data.values())
    
    if len(first_dates) == 1 and len(last_dates) == 1:
        print(f"\n✅ All symbols cover the same period: {list(first_dates)[0]} → {list(last_dates)[0]}")
    else:
        print(f"\n⚠️  Date ranges DON'T match!")
        for s, d in all_data.items():
            print(f"   {s}: {d['first']} → {d['last']}")


def validate_all(fix: bool = False):
    """Validate all symbols and resolutions."""
    db = get_db()
    if db is None:
        print("[DB] Not connected")
        return
    
    print(f"\n{'='*60}")
    print(f"  CANDLE DATA QUALITY CHECK")
    print(f"{'='*60}")
    
    for resolution in ["60", "15", "5", "D"]:
        print(f"\n--- {resolution}m ---")
        
        for symbol in ["XAU", "XAG", "BTC", "US100"]:
            issues = validate_symbol(symbol, resolution, fix=fix)
            
            if not issues:
                print(f"  {symbol}: No data")
                continue
            
            status = "✅"
            if issues["price_issues"]:
                status = "❌"
            elif issues["gap_issues"]:
                status = "⚠️"
            
            print(f"  {status} {symbol}: {issues['total']} candles", end="")
            if issues["price_issues"]:
                print(f" | {len(issues['price_issues'])} price issues", end="")
            if issues["gap_issues"]:
                print(f" | {len(issues['gap_issues'])} gap issues", end="")
            print()
            
            # Show first few issues
            for issue in issues["price_issues"][:3]:
                print(f"      ❌ {issue['timestamp']}: O={issue['open']} C={issue['close']} ({issue['reason']})")
            for issue in issues["gap_issues"][:3]:
                print(f"      ⚠️  {issue['timestamp']}: {issue['prev_close']}→{issue['close']} ({issue['reason']})")


def main():
    parser = argparse.ArgumentParser(description="Validate candle data quality")
    parser.add_argument("--symbol", default="XAU", help="Symbol to validate")
    parser.add_argument("--resolution", default="60", help="Resolution (60, 15, 5, D)")
    parser.add_argument("--all", action="store_true", help="Check all symbols")
    parser.add_argument("--coverage", action="store_true", help="Check coverage across symbols")
    parser.add_argument("--fix", action="store_true", help="Delete bad data")
    
    args = parser.parse_args()
    
    if args.all:
        validate_all(fix=args.fix)
    elif args.coverage:
        check_coverage(args.resolution)
    else:
        validate_symbol(args.symbol, args.resolution, fix=args.fix)


if __name__ == "__main__":
    main()
