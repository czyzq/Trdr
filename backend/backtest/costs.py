"""Per-instrument transaction cost model for backtests and paper trading.

Every fill in the unified backtester goes through this model. Without it,
exact-level fills at 10-20x leverage overstate returns badly (the old sweep
harness reported +2830% "average return" on strategies that lost dollars).

Values are conservative retail-CFD defaults; override per instrument via the
Mongo `settings` collection key COST_MODEL_<SYMBOL>.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional


@dataclass(frozen=True)
class InstrumentCosts:
    spread_abs: float          # full spread in price units (half is paid on entry, half on exit)
    slippage_bps: float        # extra adverse slippage on stop fills, in basis points
    swap_long_bps: float       # overnight financing for longs, bps of notional per night (negative = cost)
    swap_short_bps: float      # overnight financing for shorts
    weekend_swap: bool = False # True = swap accrues 7 nights/week (crypto)


DEFAULT_COSTS = {
    "XAU": InstrumentCosts(spread_abs=0.35, slippage_bps=0.5, swap_long_bps=-6.0, swap_short_bps=-1.0),
    "XAG": InstrumentCosts(spread_abs=0.03, slippage_bps=1.0, swap_long_bps=-8.0, swap_short_bps=-3.0),
    "US100": InstrumentCosts(spread_abs=1.5, slippage_bps=0.5, swap_long_bps=-6.0, swap_short_bps=0.5),
    "BTC": InstrumentCosts(spread_abs=None, slippage_bps=3.0, swap_long_bps=-12.0, swap_short_bps=-12.0,
                           weekend_swap=True),  # spread_abs None -> 8 bps of price
}
_BTC_SPREAD_BPS = 8.0
_FALLBACK = InstrumentCosts(spread_abs=None, slippage_bps=1.0, swap_long_bps=-6.0, swap_short_bps=-6.0)
_FALLBACK_SPREAD_BPS = 5.0


class CostModel:
    def __init__(self, symbol: str, costs: Optional[InstrumentCosts] = None):
        self.symbol = symbol
        self.costs = costs or self._load(symbol)

    @staticmethod
    def _load(symbol: str) -> InstrumentCosts:
        try:
            import database

            override = database.get_setting(f"COST_MODEL_{symbol}")
            if override:
                return InstrumentCosts(**override)
        except Exception:
            pass
        return DEFAULT_COSTS.get(symbol, _FALLBACK)

    # ── spreads ──

    def half_spread(self, price: float) -> float:
        c = self.costs
        if c.spread_abs is not None:
            return c.spread_abs / 2
        bps = _BTC_SPREAD_BPS if self.symbol == "BTC" else _FALLBACK_SPREAD_BPS
        return price * bps / 10_000 / 2

    def entry_fill(self, price: float, direction: str) -> float:
        """Market entry: buyer pays the ask, seller receives the bid."""
        hs = self.half_spread(price)
        return price + hs if direction == "buy" else price - hs

    def exit_fill(self, price: float, direction: str) -> float:
        """Market/TP exit crosses the spread the other way."""
        hs = self.half_spread(price)
        return price - hs if direction == "buy" else price + hs

    # ── stops with gap awareness ──

    def stop_fill(self, stop_price: float, bar_open: float, direction: str) -> float:
        """A stop triggered inside a bar fills at the stop unless the bar OPENED
        through it (gap) - then you get the open. Adverse slippage on top."""
        if direction == "buy":  # long being stopped out (selling)
            base = min(stop_price, bar_open)
            return base * (1 - self.costs.slippage_bps / 10_000)
        base = max(stop_price, bar_open)
        return base * (1 + self.costs.slippage_bps / 10_000)

    def tp_fill(self, tp_price: float, bar_open: float, direction: str) -> float:
        """TP fills at the level, or better if the bar gapped past it."""
        if direction == "buy":  # long taking profit (selling)
            base = max(tp_price, bar_open) if bar_open >= tp_price else tp_price
            return self.exit_fill(base, direction)
        base = min(tp_price, bar_open) if bar_open <= tp_price else tp_price
        return self.exit_fill(base, direction)

    # ── financing ──

    def swap_nights(self, opened: datetime, closed: datetime) -> int:
        """Number of financing accruals between open and close (21:00 UTC rollovers).
        Wednesday counts triple for non-crypto (weekend carry)."""
        nights = 0
        cursor = opened.replace(hour=21, minute=0, second=0, microsecond=0)
        if cursor <= opened:
            cursor += timedelta(days=1)
        while cursor <= closed:
            if self.costs.weekend_swap:
                nights += 1
            else:
                if cursor.weekday() < 5:  # rollovers only on weekdays
                    nights += 3 if cursor.weekday() == 2 else 1  # triple-swap Wednesday
            cursor += timedelta(days=1)
        return nights

    def swap_cost(self, notional: float, direction: str, opened: datetime, closed: datetime) -> float:
        """Financing cost in account currency. Negative = cost, positive = credit."""
        nights = self.swap_nights(opened, closed)
        if nights == 0:
            return 0.0
        bps = self.costs.swap_long_bps if direction == "buy" else self.costs.swap_short_bps
        return notional * bps / 10_000 * nights
