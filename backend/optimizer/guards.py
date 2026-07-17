"""Overfit guards: every one must pass before a candidate may be promoted."""

from typing import List, Tuple

MIN_TRAIN_TRADES = 30
MIN_VAL_TRADES = 10
MAX_DD_PCT = 25.0
MIN_POSITIVE_FOLDS_RATIO = 2 / 3
SHARPE_RETENTION = 0.5          # validation sharpe >= 0.5x train sharpe
CHAMPION_EDGE = 1.10            # beat champion OOS net PnL by >= 10%


def check(train_metrics: List[dict], val_metrics: List[dict],
          champion_val_pnl: float = None) -> Tuple[bool, dict]:
    report = {"checks": {}, "passed": False}
    ch = report["checks"]

    ch["train_trades"] = all(m.get("trades", 0) >= MIN_TRAIN_TRADES for m in train_metrics)
    ch["val_trades"] = all(m.get("trades", 0) >= MIN_VAL_TRADES for m in val_metrics)

    positive = sum(1 for m in val_metrics if m.get("net_pnl_usd", 0) > 0)
    ch["positive_folds"] = len(val_metrics) > 0 and positive / len(val_metrics) >= MIN_POSITIVE_FOLDS_RATIO

    ch["max_dd"] = all(m.get("max_dd_pct", 100) <= MAX_DD_PCT for m in val_metrics)

    train_sharpe = sum(m.get("sharpe", 0) for m in train_metrics) / max(len(train_metrics), 1)
    val_sharpe = sum(m.get("sharpe", 0) for m in val_metrics) / max(len(val_metrics), 1)
    ch["sharpe_retention"] = train_sharpe <= 0 or val_sharpe >= SHARPE_RETENTION * train_sharpe

    if champion_val_pnl is not None and champion_val_pnl > 0:
        cand_pnl = sum(m.get("net_pnl_usd", 0) for m in val_metrics)
        ch["beats_champion"] = cand_pnl >= CHAMPION_EDGE * champion_val_pnl
    else:
        ch["beats_champion"] = True

    report["train_sharpe"] = round(train_sharpe, 3)
    report["val_sharpe"] = round(val_sharpe, 3)
    report["val_net_pnl"] = round(sum(m.get("net_pnl_usd", 0) for m in val_metrics), 2)
    report["passed"] = all(ch.values())
    return report["passed"], report
