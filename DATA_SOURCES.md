# Historical Data Sources for Backtesting

## Recommended Free Sources

### 1. Yahoo Finance (Already Integrated)
- **Best for:** Daily and intraday data (1m, 5m, 15m, 30m, 1h)
- **Coverage:** XAU/USD, XAG/USD, BTC/USD, US100 (Nasdaq)
- **Limit:** ~2 years of intraday, 10+ years of daily
- **Usage:** Built into backtester - no setup needed
- **Command:** `python backtester.py --symbol XAU --days 365`

### 2. Dukascopy (Best Quality)
- **Best for:** Tick data, 1-minute OHLCV
- **Coverage:** All forex pairs, metals, indices, crypto
- **Limit:** 20+ years of data
- **Download:** https://www.dukascopy.com/swiss/english/marketwatch/historical/
- **Format:** CSV with OHLCV + volume

### 3. HistData.com
- **Best for:** Forex and metals historical data
- **Coverage:** XAU/USD, XAG/USD, major pairs
- **Limit:** From 2000 onwards
- **Download:** http://www.histdata.com/
- **Format:** CSV 1-minute data

### 4. Kaggle Datasets
- **Best for:** Pre-processed datasets
- **Search:** "XAU USD historical" or "gold price data"
- **Examples:**
  - Gold prices 2000-2024
  - Forex daily rates
  - Cryptocurrency OHLCV

### 5. Alpha Vantage (Already Integrated)
- **Best for:** Daily data
- **Limit:** 5 API calls/minute (free tier)
- **Usage:** Automatic fallback in backtester

## Data Format for Backtester

CSV should have columns:
```
Date,Open,High,Low,Close,Volume
2024-01-01,2045.50,2050.00,2040.25,2048.75,15000
```

Or with time:
```
Date,Time,Open,High,Low,Close,Volume
2024-01-01,14:30,2045.50,2050.00,2040.25,2048.75,15000
```

## Usage Examples

```bash
# Use Yahoo Finance (auto-download)
python backtester.py --symbol XAU --days 365

# Use your own CSV
python backtester.py --csv data/gold_2024.csv --symbol XAU

# Backtest all instruments
python backtester.py --all --days 180

# Different timeframes
python backtester.py --symbol XAU --resolution 60 --days 90
```

## Downloading from Dukascopy

1. Go to: https://www.dukascopy.com/swiss/english/marketwatch/historical/
2. Select instrument (e.g., XAU/USD)
3. Select timeframe (1 minute recommended)
4. Select date range
5. Download and extract
6. Convert to CSV format if needed
7. Place in `backend/data/` folder

## Notes

- XAU = Gold (XAU/USD pair)
- XAG = Silver (XAG/USD pair)
- US100 = Nasdaq-100 index
- BTC = Bitcoin (BTC/USD pair)

For CFD trading, make sure data reflects your broker's trading hours and spreads.
