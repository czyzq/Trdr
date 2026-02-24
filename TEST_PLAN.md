# TEST_PLAN.md - CFD Trading Bot Test Plan

## Overview
This document outlines the test strategy for the CFD Trading Bot project. The goal is to ensure reliability, catch bugs early, and document expected behavior.

---

## 1. Test Infrastructure

### Backend
- **Framework:** pytest
- **Location:** `backend/tests/`
- **Run:** `cd backend && source venv/bin/activate && python -m pytest tests/ -v`
- **Existing:** `test_backtester.py` (63 tests - ✅ passing)

### Frontend
- **Framework:** Vitest + React Testing Library (recommended)
- **Location:** `frontend/src/__tests__/`
- **Run:** `cd frontend && npm run test`

---

## 2. Critical Features to Test (P0)

### 2.1 Signal Generation
**Priority:** P0 - Core functionality

| Scenario | Description | Expected Result |
|---------|-------------|-----------------|
| Happy Path - Buy Signal | Generate signal for XAU with strong indicators | Signal with direction="buy", score > 0.5 |
| Happy Path - Sell Signal | Generate signal with strong bearish indicators | Signal with direction="sell", score < -0.5 |
| Happy Path - Neutral | Generate signal with mixed indicators | Signal with direction="neutral", -0.3 < score < 0.3 |
| Edge - Score Clamping | Technical score exceeds 1.0 | Score clamped to [-1, 1] |
| Edge - Empty Indicators | No indicator data available | Returns neutral signal with default values |
| Edge - Unknown Symbol | Request signal for invalid symbol | Returns error or neutral signal |

**Test File:** `tests/test_signals.py` (new)

---

### 2.2 Trade Execution (Broker Simulation)
**Priority:** P0 - Core functionality

| Scenario | Description | Expected Result |
|---------|-------------|-----------------|
| Happy Path - Open Buy | Open buy position on XAU | Position created, status="open", direction="buy" |
| Happy Path - Open Sell | Open sell position on XAG | Position created, status="open", direction="sell" |
| Happy Path - Close Position | Close existing position | Position status="closed", P&L calculated |
| Edge - Insufficient Margin | Try to open position exceeding balance | Error: "Insufficient margin" |
| Edge - Invalid Symbol | Try to trade non-existent symbol | Error: "Invalid symbol" |
| Edge - Duplicate Position | Try to open same direction on same symbol | Allowed (scalping) or rejected based on config |
| Edge - Negative Size | Try to open position with negative size | Error: "Invalid size" |
| Edge - Zero Leverage | Open position with 0 leverage | Error: "Leverage must be > 0" |

**Test File:** `tests/test_broker.py` (new)

---

### 2.3 Account Management
**Priority:** P0 - Core functionality

| Scenario | Description | Expected Result |
|---------|-------------|-----------------|
| Happy Path - Get Account | Fetch account info | Returns balance, equity, margin, positions |
| Happy Path - Update Mode | Switch between simulation/live | Mode updated successfully |
| Edge - Negative Balance | Account goes negative (large loss) | Should not happen (margin call logic) |
| Edge - Max Drawdown | Equity drops significantly | Account updates correctly |

**Test File:** `tests/test_account.py` (new)

---

### 2.4 API Endpoints
**Priority:** P0 - Core functionality

| Endpoint | Scenario | Expected |
|----------|----------|----------|
| GET /api/signals | Fetch all signals | Returns list of signals with valid structure |
| GET /api/trades/open | Fetch open positions | Returns list of open positions |
| GET /api/account | Fetch account | Returns account object |
| POST /api/trade/open | Open position | Position created |
| POST /api/trade/close/{id} | Close position | Position closed |
| GET /api/strategies | Fetch strategies | Returns list of available strategies |
| POST /api/settings | Save setting | Setting persisted |
| GET /api/backtest | Run backtest | Returns results with trades/metrics |

**Test File:** `tests/test_api.py` (new)

---

## 3. Important Features (P1)

### 3.1 Backtesting Engine
**Priority:** P1 - Already tested (63 tests)

| Scenario | Description | Expected |
|----------|-------------|----------|
| Basic Run | Run backtest on XAU | Returns results with trades |
| Invalid Candles | Too few candles | Raises error |
| Win Rate | Calculate win rate | 0 <= win_rate <= 1 |
| Drawdown | Calculate max drawdown | Non-negative value |
| Deterministic | Same inputs = same outputs | Results are reproducible |

**Status:** ✅ Covered by existing `test_backtester.py`

---

### 3.2 Indicators
**Priority:** P1 - Core calculation logic

| Indicator | Test Case | Expected |
|-----------|-----------|----------|
| RSI | Overbought (RSI > 70) | Value > 70, zone="OVERBOUGHT" |
| RSI | Oversold (RSI < 30) | Value < 30, zone="OVERSOLD" |
| RSI | Neutral | 30 <= value <= 70 |
| MACD | Bullish cross | MACD line above signal line |
| MACD | Bearish cross | MACD line below signal line |
| Bollinger Bands | Price above upper band | Zone="UPPER" |
| Bollinger Bands | Price below lower band | Zone="LOWER" |
| ADX | Strong trend | ADX > 25 |
| ADX | Weak trend (ranging) | ADX < 25 |

**Test File:** `tests/test_indicators.py` (new)

---

### 3.3 Position Management (TP/SL)
**Priority:** P1 - Risk management

| Scenario | Description | Expected |
|----------|-------------|----------|
| TP Hit - Buy | Price rises to TP | Position closed, profit realized |
| SL Hit - Buy | Price falls to SL | Position closed, loss realized |
| TP Hit - Sell | Price falls to TP | Position closed, profit realized |
| Trailing Stop | Price moves favorably, then reverses | Stop adjusts, position closes at new level |

**Test File:** `tests/test_risk.py` (new)

---

### 3.4 News & Sentiment
**Priority:** P1 - External data

| Scenario | Description | Expected |
|----------|-------------|----------|
| News Available | Fetch news for AAPL | Returns articles with sentiment |
| No News | Fetch news for obscure symbol | Returns empty list (no mock data) |
| API Failure | Alpha Vantage API down | Graceful fallback, empty news |

**Test File:** `tests/test_news.py` (new)

---

## 4. Nice to Have (P2)

### 4.1 Frontend Components
**Priority:** P2 - UI testing

| Component | Test Case |
|-----------|-----------|
| Dashboard | Renders without crash |
| SignalsGrid | Displays signals correctly |
| Charts | Chart renders with data |
| Forms | Validation works |

**Test File:** `frontend/src/__tests__/components.test.tsx` (new)

---

### 4.2 Data Providers
**Priority:** P2

| Provider | Test Case |
|----------|-----------|
| Binance | Price fetch works |
| Fallback | Graceful degradation |

---

## 5. Test Data Management

### Fixtures (pytest)
Create reusable fixtures in `tests/conftest.py`:

```python
@pytest.fixture
def sample_candles():
    """Generate 100 sample candles for testing."""
    return generate_sample_data("XAU", days=100, base_price=2000.0)

@pytest.fixture
def mock_account():
    """Mock account with known balance."""
    return {
        "balance_usd": 10000.0,
        "equity_usd": 10000.0,
        "available_usd": 10000.0,
        "positions": []
    }

@pytest.fixture
def sample_signal():
    """Sample signal for XAU."""
    return Signal(
        symbol="XAU",
        direction=SignalDirection.BUY,
        score=0.75,
        ...
    )
```

---

## 6. Running Tests

### Full Suite
```bash
# Backend
cd ~/dev/cfd-trading-bot/backend
source venv/bin/activate
python -m pytest tests/ -v

# Frontend
cd ~/dev/cfd-trading-bot/frontend
npm test
```

### By Priority
```bash
# P0 only (CI/CD)
python -m pytest tests/ -v -m "p0"

# P0 + P1
python -m pytest tests/ -v -m "p0 or p1"
```

### With Coverage
```bash
python -m pytest tests/ --cov=. --cov-report=html
```

---

## 7. CI/CD Integration

Create `.github/workflows/test.yml`:

```yaml
name: Tests
on: [push, pull_request]
jobs:
  backend-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Run pytest
        run: |
          cd backend
          pip install -r requirements.txt
          python -m pytest tests/ -v
```

---

## 8. Test Maintenance

- **Review:** Update test plan when adding new features
- **Coverage:** Aim for 80% coverage on P0 features
- **Flaky Tests:** Mark and fix tests that fail intermittently
- **Documentation:** Document edge cases discovered in production

---

## 9. Implementation Checklist

- [ ] Create `tests/conftest.py` with shared fixtures
- [ ] Create `tests/test_signals.py` - Signal generation tests
- [ ] Create `tests/test_broker.py` - Trade execution tests
- [ ] Create `tests/test_account.py` - Account tests
- [ ] Create `tests/test_api.py` - API endpoint tests
- [ ] Create `tests/test_indicators.py` - Indicator tests
- [ ] Create `tests/test_risk.py` - Risk management tests
- [ ] Create `tests/test_news.py` - News/fallback tests
- [ ] Add Vitest to frontend package.json
- [ ] Create frontend component tests
- [ ] Set up GitHub Actions workflow

---

## 10. Priority Order for Implementation

1. **First:** Copy existing fixtures from test_backtester.py to conftest.py
2. **Second:** Create test_signals.py (most critical)
3. **Third:** Create test_broker.py (trade logic)
4. **Fourth:** Create test_api.py (API coverage)
5. **Fifth:** Create test_indicators.py
6. **Sixth:** Remaining test files
