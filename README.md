# Trdr — CFD Trading Bot

Personal CFD trading bot with real-time signals, interactive candlestick charts, news sentiment analysis, and a plug-and-play broker architecture ready for live trading.

Built to run from any device (iPhone, iPad, laptop) via a hosted web UI with a mobile-first dark trading interface.

## Features

- **Signal Engine**: Regime-adaptive scoring (trending vs ranging markets) using RSI, MACD, Bollinger Bands, ADX, StochRSI, SMA crossover, volume profile, and momentum
- **Risk Management**: 2% max risk per trade, ATR-based position sizing, circuit breaker at 20% drawdown, max 3 concurrent positions
- **Candlestick Charts**: Custom SVG OHLCV charts with Bollinger Bands, SMA 20/50, MACD, RSI, and volume panels. Multiple timeframes (1m, 5m, 15m, 30m, 1H, 1D). Horizontally scrollable on mobile for full readability
- **News Sentiment**: Multi-source news with keyword-based sentiment scoring (Brave Search, Alpha Vantage NEWS_SENTIMENT, web scraping fallback)
- **MongoDB Persistence**: Account balance, trade history, and open positions survive restarts
- **Broker Abstraction**: Switch between paper trading and Interactive Brokers with one env var
- **Mobile-first UI**: Responsive dark trading interface with bottom tab navigation, safe-area support, and touch-friendly controls

## Supported Instruments

| Symbol | Instrument | Alpha Vantage Mapping |
|--------|-----------|----------------------|
| XAU | Gold (spot) | GOLD |
| XAG | Silver (spot) | SILVER |
| US100 | Nasdaq-100 | QQQ (ETF proxy) |
| BTC | Bitcoin | BTC / CRYPTO:BTC |

## Data Sources

Ticker and market data flows through multiple providers with automatic fallback:

| Source | What it provides | Rate limit |
|--------|-----------------|------------|
| **Alpha Vantage** (primary) | Real-time quotes (`GLOBAL_QUOTE`), intraday/daily candles (`TIME_SERIES_INTRADAY`, `TIME_SERIES_DAILY`), news sentiment (`NEWS_SENTIMENT`) | 5 calls/min (free tier) |
| **Finnhub** (optional) | Quotes, candles, company news | Token-based |
| **Brave Search** (optional) | Financial news headlines for sentiment analysis | 20 req/min (free tier) |
| **Synthetic fallback** | Realistic price generator with perfect candle continuity when APIs are unavailable | Unlimited |

Data fetching priority: Alpha Vantage → Finnhub → Synthetic price generator.

All price data is cached (60s for quotes, 2min for news) and rate-limited to stay within free tier limits.

## Tech Stack

| Layer | Tech |
|-------|------|
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS |
| Charts | Custom SVG candlestick renderer (client-side indicator calculations) |
| Backend | FastAPI (Python) + uvicorn |
| Database | MongoDB Atlas (free M0 tier) |
| Data | Alpha Vantage + Finnhub + Brave Search (with synthetic fallback) |
| Broker | Simulated paper trading (default) or Interactive Brokers |
| Deployment | Render (free tier) |

## Quick Start (Local)

```bash
# 1. Clone
git clone <repo-url> && cd Trdr

# 2. Backend
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 3. Create .env (copy from example)
cp .env.example .env
# Edit .env and add your ALPHA_VANTAGE_API_KEY

# 4. Start backend
python main.py --port 8001

# 5. Frontend (new terminal)
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — the frontend proxies `/api` to the backend automatically.

## Environment Variables

Create `backend/.env` based on `backend/.env.example`:

```bash
# REQUIRED - get free key at alphavantage.co/support/#api-key
# Covers: price quotes, candlestick data, news sentiment
ALPHA_VANTAGE_API_KEY=your_key_here

# RECOMMENDED - free at mongodb.com/atlas (512MB free)
# Without this, all data lives in memory and is lost on restart
MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/
MONGO_DB=cfd_trading_bot

# OPTIONAL - news from Brave Search
BRAVE_API_KEY=your_brave_key

# OPTIONAL - additional data from Finnhub
FINNHUB_API_KEY=your_finnhub_key

# OPTIONAL - broker selection
BROKER_TYPE=sim              # "sim" (default) or "ibkr"

# OPTIONAL - Interactive Brokers (only if BROKER_TYPE=ibkr)
# IBKR_HOST=127.0.0.1
# IBKR_PORT=7497             # 7497=paper, 7496=live
# IBKR_CLIENT_ID=1
```

## Deploy to Render (Free)

The easiest free hosting for this stack. One service runs both backend + frontend.

### Step-by-step:

1. **Create accounts** (all free):
   - [Render](https://render.com) - hosting
   - [MongoDB Atlas](https://mongodb.com/atlas) - database (free M0 cluster)
   - [Alpha Vantage](https://alphavantage.co/support/#api-key) - market data API key

2. **Set up MongoDB Atlas**:
   - Create free M0 cluster
   - Create database user
   - Add `0.0.0.0/0` to Network Access (allows Render to connect)
   - Copy connection string: `mongodb+srv://user:pass@cluster.mongodb.net/`

3. **Deploy on Render**:
   - Push this repo to GitHub
   - Go to [Render Dashboard](https://dashboard.render.com) > New > Blueprint
   - Connect your GitHub repo - Render auto-detects `render.yaml`
   - Set environment variables when prompted:
     - `ALPHA_VANTAGE_API_KEY` = your key
     - `MONGO_URI` = your Atlas connection string
   - Click Deploy

   Or manually: New > Web Service > connect repo, set:
   - Build: `cd frontend && npm install && npm run build && cd ../backend && pip install -r requirements.txt`
   - Start: `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
   - Add env vars above

4. **Access**: Your bot will be at `https://your-app-name.onrender.com`

### Render free tier notes:
- Spins down after 15 min of inactivity (cold start ~30s)
- 750 hours/month (enough for 1 service 24/7)

### Keep it alive with UptimeRobot (free)

Render free tier sleeps your service after 15 min of no traffic. UptimeRobot pings it every 5 min to prevent that.

1. Create a free account at [uptimerobot.com](https://uptimerobot.com)
2. Click **Add New Monitor**
3. Configure:
   - **Monitor Type**: HTTP(s)
   - **Friendly Name**: Trdr
   - **URL**: `https://your-app-name.onrender.com/health`
   - **Monitoring Interval**: 5 minutes
4. Save

## Architecture

```
Browser (any device)
    |
    v
[FastAPI Backend]
    |-- /api/signals       -> Signal engine (regime-adaptive scoring)
    |-- /api/chart/:sym    -> Candlestick OHLCV data
    |-- /api/quote/:sym    -> Current price quote
    |-- /api/trade/open    -> Open position via broker
    |-- /api/trade/close   -> Close position via broker
    |-- /api/account       -> Account balance & stats
    |-- /api/news/:sym     -> News sentiment per symbol
    |-- /api/alerts        -> Alert configuration & history
    |-- /*                 -> Serves React frontend (SPA)
    |
    +-- DataProvider (quotes + candles)
    |     Alpha Vantage -> Finnhub -> synthetic fallback
    |
    +-- NewsProvider (sentiment)
    |     Brave Search -> Alpha Vantage NEWS_SENTIMENT -> web scraping -> mock
    |
    +-- Broker (execution)
    |     sim:  Paper trading (in-memory + MongoDB)
    |     ibkr: Real orders via IB Gateway/TWS
    |
    +-- MongoDB Atlas
          account, trades, signal_cache
```

## Adding a New Broker

1. Create `backend/broker_xxx.py` implementing `Broker` + `DataProvider` from `broker.py`
2. Add an `elif` in `broker_factory.py`
3. Set `BROKER_TYPE=xxx` in `.env`

No changes to `main.py` needed.

## Project Structure

```
Trdr/
  backend/
    main.py                # FastAPI app + signal engine
    broker.py              # Abstract Broker + DataProvider interfaces
    broker_sim.py          # Simulated paper trading
    broker_ibkr.py         # Interactive Brokers implementation
    broker_factory.py      # Creates broker based on BROKER_TYPE
    database.py            # MongoDB persistence layer
    indicators.py          # RSI, MACD, ATR, ADX, StochRSI, BB, volume
    alpha_vantage.py       # Price & candle data client
    alpha_vantage_news.py  # News sentiment client
    news_client.py         # Brave Search news client
    finnhub.py             # Finnhub API integration
    realistic_prices.py    # Synthetic price fallback generator
    models.py              # Pydantic models
    .env.example           # Environment variable template
  frontend/
    src/
      components/
        Dashboard.tsx      # Main layout + tab navigation
        MainTab.tsx        # Charts + signals view
        ChartsTab.tsx      # Multi-chart view (4 instruments)
        TradesTab.tsx      # Open positions + trade history
        CandlestickChart.tsx  # SVG OHLCV + BB + SMA + MACD + RSI + volume
        SignalsGrid.tsx    # Trading signals display
        NewsTab.tsx        # News sentiment view
        Sidebar.tsx        # Account stats + mode toggle
  render.yaml              # One-click Render deployment
```

## License

MIT
