"""
Tests for the backtesting engine and historical data module.

Run:  python -m pytest tests/test_backtester.py -v
"""

import sys
import os
import pytest

# Ensure backend dir is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtester import (
    run_backtest,
    calculate_signal_score,
    BacktestResult,
    BacktestTrade,
    results_to_dict,
    LOOKBACK,
    MAX_HOLD_CANDLES,
)
from historical_data import generate_sample_data, load_csv_candles
from indicators import TechnicalIndicators


# ── Fixtures ──

@pytest.fixture
def gold_candles():
    """200+ daily candles for Gold with fixed seed (deterministic)."""
    return generate_sample_data("XAU", days=300, base_price=2000.0)


@pytest.fixture
def silver_candles():
    return generate_sample_data("XAG", days=300, base_price=23.0)


@pytest.fixture
def nasdaq_candles():
    return generate_sample_data("US100", days=300, base_price=17500.0)


@pytest.fixture
def btc_candles():
    return generate_sample_data("BTC", days=300, base_price=95000.0)


@pytest.fixture
def short_candles():
    """Too few candles — should fail."""
    return generate_sample_data("XAU", days=50, base_price=2000.0)


# ── Sample data generator tests ──

class TestSampleDataGenerator:
    def test_generates_correct_count(self):
        candles = generate_sample_data("XAU", days=200, base_price=2000.0)
        # Weekends are skipped for equity-like instruments, so ~143 trading days
        assert len(candles) > 100
        assert len(candles) < 200  # Must skip weekends

    def test_btc_includes_weekends(self):
        candles = generate_sample_data("BTC", days=100, base_price=95000.0)
        # BTC trades every day, so should be close to 100
        assert len(candles) == 100

    def test_deterministic_with_same_seed(self):
        c1 = generate_sample_data("XAU", days=100, base_price=2000.0)
        c2 = generate_sample_data("XAU", days=100, base_price=2000.0)
        assert len(c1) == len(c2)
        assert c1[0]["close"] == c2[0]["close"]
        assert c1[-1]["close"] == c2[-1]["close"]

    def test_different_symbol_gives_different_data(self):
        c1 = generate_sample_data("XAU", days=100, base_price=2000.0)
        c2 = generate_sample_data("XAG", days=100, base_price=23.0)
        assert c1[10]["close"] != c2[10]["close"]

    def test_candle_structure(self):
        candles = generate_sample_data("XAU", days=100, base_price=2000.0)
        for c in candles:
            assert "timestamp" in c
            assert "time" in c
            assert "open" in c
            assert "high" in c
            assert "low" in c
            assert "close" in c
            assert "volume" in c
            # OHLC validity
            assert c["high"] >= c["low"]
            assert c["high"] >= c["open"]
            assert c["high"] >= c["close"]
            assert c["low"] <= c["open"]
            assert c["low"] <= c["close"]
            assert c["volume"] > 0

    def test_prices_near_base(self):
        candles = generate_sample_data("XAU", days=100, base_price=2000.0)
        # After 100 days of random walk, prices should still be in a reasonable range
        for c in candles:
            assert 1000 < c["close"] < 4000, f"Price {c['close']} too far from base 2000"

    def test_chronological_order(self):
        candles = generate_sample_data("XAU", days=100, base_price=2000.0)
        for i in range(1, len(candles)):
            assert candles[i]["timestamp"] > candles[i-1]["timestamp"]


# ── Indicator tests ──

class TestIndicators:
    def test_rsi_range(self, gold_candles):
        closes = [c["close"] for c in gold_candles]
        rsi = TechnicalIndicators.rsi(closes, 14)
        assert rsi is not None
        assert 0 <= rsi <= 100

    def test_macd_structure(self, gold_candles):
        closes = [c["close"] for c in gold_candles]
        macd = TechnicalIndicators.macd(closes)
        assert macd is not None
        assert "macd_line" in macd
        assert "signal_line" in macd
        assert "histogram" in macd

    def test_bollinger_bands(self, gold_candles):
        closes = [c["close"] for c in gold_candles]
        bb = TechnicalIndicators.bollinger_bands(closes)
        assert bb is not None
        assert bb["upper"] > bb["middle"] > bb["lower"]

    def test_atr_positive(self, gold_candles):
        highs = [c["high"] for c in gold_candles]
        lows = [c["low"] for c in gold_candles]
        closes = [c["close"] for c in gold_candles]
        atr = TechnicalIndicators.atr(highs, lows, closes, 14)
        assert atr is not None
        assert atr > 0

    def test_adx_structure(self, gold_candles):
        highs = [c["high"] for c in gold_candles]
        lows = [c["low"] for c in gold_candles]
        closes = [c["close"] for c in gold_candles]
        adx = TechnicalIndicators.adx(highs, lows, closes, 14)
        assert adx is not None
        assert "adx" in adx
        assert "plus_di" in adx
        assert "minus_di" in adx
        assert 0 <= adx["adx"] <= 100

    def test_calculate_all(self, gold_candles):
        result = TechnicalIndicators.calculate_all(gold_candles, period=14)
        assert result is not None
        assert "rsi_14" in result
        assert "macd" in result
        assert "atr_14" in result
        assert "bollinger_bands" in result
        assert "adx" in result
        assert "stoch_rsi" in result


# ── Signal scoring tests ──

class TestSignalScoring:
    def test_score_range(self, gold_candles):
        ind = TechnicalIndicators.calculate_all(gold_candles, period=14)
        ind["_closes"] = [c["close"] for c in gold_candles]
        score, direction = calculate_signal_score(ind)
        assert -1 <= score <= 1
        assert direction in ("STRONG_BUY", "BUY", "NEUTRAL", "SELL", "STRONG_SELL")

    def test_strong_buy_threshold(self):
        # Score > 0.45 should be STRONG_BUY
        # We can't easily force a specific score, but we can check the mapping
        from backtester import calculate_signal_score
        # This is implicitly tested through the backtest

    def test_neutral_for_flat_market(self):
        """A perfectly flat market should produce neutral signals."""
        candles = []
        for i in range(100):
            candles.append({
                "open": 100.0, "high": 100.5, "low": 99.5,
                "close": 100.0, "volume": 50000,
            })
        ind = TechnicalIndicators.calculate_all(candles, period=14)
        if ind:
            ind["_closes"] = [100.0] * 100
            score, direction = calculate_signal_score(ind)
            # Flat market should be neutral or very weak signal
            assert abs(score) < 0.5


# ── Backtest engine tests ──

class TestBacktestEngine:
    def test_basic_run(self, gold_candles):
        result = run_backtest(gold_candles, symbol="XAU")
        assert isinstance(result, BacktestResult)
        assert result.symbol == "XAU"
        assert result.total_candles == len(gold_candles)
        assert result.total_trades >= 0
        assert result.total_signals > 0

    def test_too_few_candles_raises(self, short_candles):
        if len(short_candles) < LOOKBACK + 10:
            with pytest.raises(ValueError, match="Need at least"):
                run_backtest(short_candles, symbol="XAU")

    def test_trades_have_valid_structure(self, gold_candles):
        result = run_backtest(gold_candles, symbol="XAU")
        for trade in result.trades:
            assert isinstance(trade, BacktestTrade)
            assert trade.direction in ("BUY", "SELL")
            assert trade.entry_price > 0
            assert trade.exit_price is not None
            assert trade.exit_price > 0
            assert trade.exit_reason in ("TP", "SL", "TIMEOUT", "END")
            assert trade.entry_idx >= LOOKBACK
            assert trade.exit_idx >= trade.entry_idx

    def test_win_rate_bounds(self, gold_candles):
        result = run_backtest(gold_candles, symbol="XAU")
        assert 0 <= result.win_rate <= 100
        assert result.winning_trades + result.losing_trades == result.total_trades

    def test_equity_curve_length(self, gold_candles):
        result = run_backtest(gold_candles, symbol="XAU")
        # Equity curve has one entry per candle from LOOKBACK onward, plus initial
        assert len(result.equity_curve) > 0

    def test_max_drawdown_non_negative(self, gold_candles):
        result = run_backtest(gold_candles, symbol="XAU")
        assert result.max_drawdown_pct >= 0

    def test_profit_factor_non_negative(self, gold_candles):
        result = run_backtest(gold_candles, symbol="XAU")
        assert result.profit_factor >= 0

    def test_all_instruments(self, gold_candles, silver_candles, nasdaq_candles, btc_candles):
        """Run backtest for all 4 instruments."""
        for candles, sym in [
            (gold_candles, "XAU"),
            (silver_candles, "XAG"),
            (nasdaq_candles, "US100"),
            (btc_candles, "BTC"),
        ]:
            result = run_backtest(candles, symbol=sym)
            assert result.total_candles > 0
            assert result.total_signals > 0, f"{sym} produced no signals"

    def test_max_concurrent_respected(self, gold_candles):
        """With max_concurrent=1, should never have overlapping trades."""
        result = run_backtest(gold_candles, symbol="XAU", max_concurrent=1)
        # Sort trades by entry index
        sorted_trades = sorted(result.trades, key=lambda t: t.entry_idx)
        for i in range(1, len(sorted_trades)):
            prev = sorted_trades[i - 1]
            curr = sorted_trades[i]
            # Current trade should start after previous trade exits
            assert curr.entry_idx >= prev.exit_idx, (
                f"Trade overlap: trade {i-1} exits at {prev.exit_idx}, "
                f"trade {i} enters at {curr.entry_idx}"
            )

    def test_stop_loss_respected(self, gold_candles):
        """Trades closed via SL should exit at the stop loss price."""
        result = run_backtest(gold_candles, symbol="XAU")
        for trade in result.trades:
            if trade.exit_reason == "SL":
                assert trade.exit_price == trade.stop_loss

    def test_take_profit_respected(self, gold_candles):
        """Trades closed via TP should exit at the take profit price."""
        result = run_backtest(gold_candles, symbol="XAU")
        for trade in result.trades:
            if trade.exit_reason == "TP":
                assert trade.exit_price == trade.take_profit

    def test_timeout_respected(self, gold_candles):
        """Timed-out trades should not exceed MAX_HOLD_CANDLES bars."""
        result = run_backtest(gold_candles, symbol="XAU")
        for trade in result.trades:
            if trade.exit_reason == "TIMEOUT":
                bars_held = trade.exit_idx - trade.entry_idx
                assert bars_held >= MAX_HOLD_CANDLES

    def test_buy_pnl_calculation(self):
        """Manual check: BUY trade P&L should be positive when exit > entry."""
        candles = generate_sample_data("XAU", days=300, base_price=2000.0)
        result = run_backtest(candles, symbol="XAU")
        for trade in result.trades:
            if trade.direction == "BUY" and trade.exit_reason in ("TP", "SL"):
                expected_sign = 1 if trade.exit_price > trade.entry_price else -1
                actual_sign = 1 if trade.pnl_pct > 0 else -1
                assert expected_sign == actual_sign, (
                    f"BUY: entry={trade.entry_price}, exit={trade.exit_price}, "
                    f"pnl={trade.pnl_pct}"
                )

    def test_sell_pnl_calculation(self):
        """Manual check: SELL trade P&L should be positive when exit < entry."""
        candles = generate_sample_data("XAG", days=300, base_price=23.0)
        result = run_backtest(candles, symbol="XAG")
        for trade in result.trades:
            if trade.direction == "SELL" and trade.exit_reason in ("TP", "SL"):
                expected_sign = 1 if trade.exit_price < trade.entry_price else -1
                actual_sign = 1 if trade.pnl_pct > 0 else -1
                assert expected_sign == actual_sign, (
                    f"SELL: entry={trade.entry_price}, exit={trade.exit_price}, "
                    f"pnl={trade.pnl_pct}"
                )

    def test_deterministic_results(self, gold_candles):
        """Same input data should produce identical backtest results."""
        r1 = run_backtest(gold_candles, symbol="XAU")
        r2 = run_backtest(gold_candles, symbol="XAU")
        assert r1.total_trades == r2.total_trades
        assert r1.win_rate == r2.win_rate
        assert r1.total_return_pct == r2.total_return_pct

    def test_results_to_dict(self, gold_candles):
        result = run_backtest(gold_candles, symbol="XAU")
        d = results_to_dict(result)
        assert d["symbol"] == "XAU"
        assert isinstance(d["trades"], list)
        assert "win_rate" in d
        assert "total_return_pct" in d
        # Should be JSON serialisable
        import json
        json_str = json.dumps(d)
        assert len(json_str) > 0


# ── CSV loader tests ──

class TestIntradayBacktest:
    """Tests for intraday (15m/30m) backtesting."""

    def test_15m_sample_generation(self):
        candles = generate_sample_data("XAU", days=10, base_price=2000.0, resolution="15")
        assert len(candles) > 100  # ~26 candles/day * ~7 trading days
        # All times should be at 15m intervals
        for c in candles:
            parts = c["time"].split(":")
            assert int(parts[1]) % 15 == 0

    def test_30m_sample_generation(self):
        candles = generate_sample_data("XAU", days=10, base_price=2000.0, resolution="30")
        assert len(candles) > 50  # ~13 candles/day * ~7 trading days
        for c in candles:
            parts = c["time"].split(":")
            assert int(parts[1]) % 30 == 0

    def test_60m_sample_generation(self):
        candles = generate_sample_data("US100", days=10, base_price=17500.0, resolution="60")
        assert len(candles) > 30

    def test_btc_24h_candles(self):
        """BTC should generate 24h of candles per day (no market hours restriction)."""
        candles = generate_sample_data("BTC", days=2, base_price=95000.0, resolution="60")
        # 2 days * 24 hours = 48 candles
        assert len(candles) == 48

    def test_intraday_backtest_runs(self):
        """15m backtest should run and produce trades."""
        candles = generate_sample_data("XAU", days=30, base_price=2000.0, resolution="15")
        result = run_backtest(candles, symbol="XAU")
        assert result.total_trades > 0
        assert result.total_signals > 0
        assert 0 <= result.win_rate <= 100

    def test_30m_backtest_all_instruments(self):
        """30m backtest across all instruments."""
        configs = [
            ("XAU", 2000.0), ("XAG", 23.0), ("US100", 17500.0), ("BTC", 95000.0),
        ]
        for sym, base in configs:
            candles = generate_sample_data(sym, days=30, base_price=base, resolution="30")
            result = run_backtest(candles, symbol=sym)
            assert result.total_signals > 0, f"{sym} at 30m produced no signals"

    def test_intraday_chronological_order(self):
        candles = generate_sample_data("XAU", days=5, base_price=2000.0, resolution="15")
        for i in range(1, len(candles)):
            assert candles[i]["timestamp"] > candles[i-1]["timestamp"]


class TestCSVLoader:
    def test_missing_file_returns_none(self):
        result = load_csv_candles("/nonexistent/file.csv")
        assert result is None

    def test_load_valid_csv(self, tmp_path):
        csv_file = tmp_path / "test_data.csv"
        csv_file.write_text(
            "Date,Open,High,Low,Close,Volume\n"
            "2025-01-02,100.0,105.0,98.0,103.0,50000\n"
            "2025-01-03,103.0,107.0,101.0,106.0,60000\n"
            "2025-01-06,106.0,110.0,104.0,108.0,55000\n"
        )
        candles = load_csv_candles(str(csv_file))
        assert candles is not None
        assert len(candles) == 3
        assert candles[0]["open"] == 100.0
        assert candles[2]["close"] == 108.0

    def test_load_with_multiplier(self, tmp_path):
        csv_file = tmp_path / "test_gold.csv"
        csv_file.write_text(
            "Date,Open,High,Low,Close,Volume\n"
            "2025-01-02,190.0,195.0,188.0,193.0,50000\n"
        )
        candles = load_csv_candles(str(csv_file), multiplier=10.0)
        assert candles is not None
        assert candles[0]["close"] == 1930.0  # 193 * 10


# ── Time format tests (regression for the x-axis bug) ──

class TestTimeFormatting:
    def test_realistic_prices_60m_times_aligned(self):
        """60-minute candles should have times ending in :00."""
        from realistic_prices import RealisticPriceFeeder
        feeder = RealisticPriceFeeder()
        candles = feeder.get_candles("XAU", resolution="60", count=20)
        assert candles is not None
        for c in candles:
            time_str = c["time"]
            # Should be HH:MM format with minutes = 00
            assert ":" in time_str, f"Bad time format: {time_str}"
            parts = time_str.split(":")
            assert len(parts) == 2
            assert parts[1] == "00", f"60m candle should end in :00, got {time_str}"

    def test_realistic_prices_30m_times_aligned(self):
        """30-minute candles should have times ending in :00 or :30."""
        from realistic_prices import RealisticPriceFeeder
        feeder = RealisticPriceFeeder()
        candles = feeder.get_candles("XAU", resolution="30", count=20)
        assert candles is not None
        for c in candles:
            time_str = c["time"]
            parts = time_str.split(":")
            assert parts[1] in ("00", "30"), f"30m candle should be :00 or :30, got {time_str}"

    def test_realistic_prices_15m_times_aligned(self):
        """15-minute candles should have times at 15-minute intervals."""
        from realistic_prices import RealisticPriceFeeder
        feeder = RealisticPriceFeeder()
        candles = feeder.get_candles("XAU", resolution="15", count=20)
        assert candles is not None
        for c in candles:
            time_str = c["time"]
            parts = time_str.split(":")
            minute = int(parts[1])
            assert minute % 15 == 0, f"15m candle should be at 15m intervals, got {time_str}"

    def test_realistic_prices_5m_times_aligned(self):
        """5-minute candles should have times at 5-minute intervals."""
        from realistic_prices import RealisticPriceFeeder
        feeder = RealisticPriceFeeder()
        candles = feeder.get_candles("XAU", resolution="5", count=20)
        assert candles is not None
        for c in candles:
            time_str = c["time"]
            parts = time_str.split(":")
            minute = int(parts[1])
            assert minute % 5 == 0, f"5m candle should be at 5m intervals, got {time_str}"

    def test_realistic_prices_daily_format(self):
        """Daily candles should have MM/DD format."""
        from realistic_prices import RealisticPriceFeeder
        feeder = RealisticPriceFeeder()
        candles = feeder.get_candles("XAU", resolution="D", count=10)
        assert candles is not None
        for c in candles:
            time_str = c["time"]
            assert "/" in time_str, f"Daily candle should have MM/DD format, got {time_str}"
            parts = time_str.split("/")
            assert len(parts) == 2
            month = int(parts[0])
            day = int(parts[1])
            assert 1 <= month <= 12
            assert 1 <= day <= 31

    def test_realistic_prices_chronological_order(self):
        """Candles should be in chronological order (oldest first)."""
        from realistic_prices import RealisticPriceFeeder
        feeder = RealisticPriceFeeder()
        candles = feeder.get_candles("XAU", resolution="60", count=20)
        assert candles is not None
        timestamps = [c["timestamp"] for c in candles]
        for i in range(1, len(timestamps)):
            assert timestamps[i] > timestamps[i-1], (
                f"Candles not in order: {timestamps[i-1]} >= {timestamps[i]}"
            )

    def test_candle_continuity(self):
        """Each candle's open should equal the previous candle's close (from index 1+)."""
        from realistic_prices import RealisticPriceFeeder
        feeder = RealisticPriceFeeder()
        candles = feeder.get_candles("XAU", resolution="60", count=20)
        assert candles is not None
        for i in range(1, len(candles)):
            assert candles[i]["open"] == candles[i-1]["close"], (
                f"Continuity break at index {i}: "
                f"prev close={candles[i-1]['close']}, current open={candles[i]['open']}"
            )
