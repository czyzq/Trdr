"""Canonical backtest result types and correct metrics.

Replaces the three competing TradeRecord/Result definitions. Rules:
- equity is mark-to-market per bar (open positions count), not realized-only
- Sharpe/Sortino annualize from BAR returns with bars_per_year derived from
  the timeframe and the instrument's trading calendar - never sqrt(252) on
  trade returns for intraday data
- ranking metric is net dollar P&L after costs, never leverage-compounded
  average percent
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# Trading hours per instrument calendar (hours/day, days/week)
_CALENDARS = {
    "BTC": (24, 7),
    "XAU": (23, 5),
    "XAG": (23, 5),
    "US100": (17, 5),
}


def bars_per_year(timeframe_minutes: int, symbol: str) -> float:
    hours, days = _CALENDARS.get(symbol, (24, 5))
    return (hours * 60 / timeframe_minutes) * days * 52


@dataclass
class TradeRecord:
    symbol: str
    direction: str              # buy | sell
    entry_ts: str
    exit_ts: str
    entry_price: float          # actual fill (spread included)
    exit_price: float           # actual fill
    size: float
    gross_pnl_usd: float
    costs_usd: float            # spread+slippage impact + swap, as positive cost
    net_pnl_usd: float
    exit_reason: str            # tp | sl | timeout | trend | end_of_data
    bars_held: int
    signal_score: float = 0.0
    confidence: float = 0.0


@dataclass
class BacktestReport:
    symbol: str
    strategy_id: str
    timeframe: str
    window_from: str
    window_to: str
    initial_balance: float
    final_balance: float
    trades: List[TradeRecord] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)   # mark-to-market per bar
    metrics: Dict[str, float] = field(default_factory=dict)

    def compute_metrics(self, timeframe_minutes: int) -> Dict[str, float]:
        n = len(self.trades)
        wins = [t for t in self.trades if t.net_pnl_usd > 0]
        losses = [t for t in self.trades if t.net_pnl_usd <= 0]
        net = sum(t.net_pnl_usd for t in self.trades)
        costs = sum(t.costs_usd for t in self.trades)
        gross_win = sum(t.net_pnl_usd for t in wins)
        gross_loss = abs(sum(t.net_pnl_usd for t in losses))

        # bar returns from the mark-to-market equity curve
        rets = []
        for i in range(1, len(self.equity_curve)):
            prev = self.equity_curve[i - 1]
            if prev > 0:
                rets.append(self.equity_curve[i] / prev - 1)
        bpy = bars_per_year(timeframe_minutes, self.symbol)
        sharpe = sortino = 0.0
        if len(rets) > 1:
            mean = sum(rets) / len(rets)
            var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
            std = math.sqrt(var)
            if std > 0:
                sharpe = mean / std * math.sqrt(bpy)
            downside = [r for r in rets if r < 0]
            if downside:
                dvar = sum(r ** 2 for r in downside) / len(downside)
                dstd = math.sqrt(dvar)
                if dstd > 0:
                    sortino = mean / dstd * math.sqrt(bpy)

        # max drawdown on mark-to-market equity
        peak = -float("inf")
        max_dd_pct = 0.0
        max_dd_usd = 0.0
        for e in self.equity_curve:
            peak = max(peak, e)
            if peak > 0:
                max_dd_pct = max(max_dd_pct, (peak - e) / peak * 100)
                max_dd_usd = max(max_dd_usd, peak - e)

        total_return_pct = (
            (self.final_balance - self.initial_balance) / self.initial_balance * 100
            if self.initial_balance else 0.0
        )

        self.metrics = {
            "trades": n,
            "win_rate": len(wins) / n * 100 if n else 0.0,
            "net_pnl_usd": round(net, 2),
            "costs_usd": round(costs, 2),
            "profit_factor": round(gross_win / gross_loss, 3) if gross_loss > 0 else (float("inf") if gross_win > 0 else 0.0),
            "sharpe": round(sharpe, 3),
            "sortino": round(sortino, 3),
            "max_dd_pct": round(max_dd_pct, 2),
            "max_dd_usd": round(max_dd_usd, 2),
            "total_return_pct": round(total_return_pct, 2),
            "avg_hold_bars": round(sum(t.bars_held for t in self.trades) / n, 1) if n else 0.0,
        }
        return self.metrics

    def objective(self, min_trades: int = 10, dd_penalty: float = 2.0) -> float:
        """Ranking objective: net dollars, drawdown-penalized, gated on sample size."""
        m = self.metrics or {}
        if m.get("trades", 0) < min_trades:
            return -float("inf")
        return m.get("net_pnl_usd", 0.0) - dd_penalty * m.get("max_dd_usd", 0.0)

    def to_doc(self) -> dict:
        """Mongo document (trades capped, equity downsampled)."""
        eq = self.equity_curve
        if len(eq) > 500:
            step = len(eq) / 500
            eq = [eq[int(i * step)] for i in range(500)]
        return {
            "symbol": self.symbol,
            "strategy_id": self.strategy_id,
            "timeframe": self.timeframe,
            "window": {"from": self.window_from, "to": self.window_to},
            "initial_balance": self.initial_balance,
            "final_balance": self.final_balance,
            "metrics": self.metrics,
            "trades": [t.__dict__ for t in self.trades[:500]],
            "equity_curve": eq,
        }
