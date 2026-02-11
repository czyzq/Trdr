# CFD Trading Bot

Personal CFD trading bot with real-time signals, candlestick charts, news sentiment, and a plug-and-play broker architecture ready for live trading.

Built to run from any device (iPhone, iPad, laptop) via a hosted web UI.

## Features

- **Signal Engine**: Regime-adaptive scoring (trending vs ranging markets) using RSI, MACD, Bollinger Bands, ADX, StochRSI, SMA crossover, volume profile
- **Risk Management**: 2% max risk per trade, position sizing via ATR, circuit breaker at 20% drawdown, max 3 concurrent positions
- **Candlestick Charts**: Full OHLCV charts with RSI and volume panels, multiple timeframes (1m to 1D)
- **News Sentiment**: Alpha Vantage NEWS_SENTIMENT API with proper symbol mapping
- **MongoDB Persistence**: Account balance, trade history, and open positions survive restarts
- **Broker Abstraction**: Switch between paper trading and Interactive Brokers with one env var
- **Mobile-friendly**: Dark trading UI accessible from any device

## Tech Stack

| Layer | Tech |
|-------|------|
| Frontend | React 18 + TypeScript + Vite + Tailwind + Recharts |
| Backend | FastAPI (Python) + uvicorn |
| Database | MongoDB Atlas (free tier) |
| Data | Alpha Vantage (quotes, candles, news sentiment) |
| Broker | Simulated (default) or Interactive Brokers |

## Quick Start (Local)

```bash
# 1. Clone
git clone <repo-url> && cd cfd-trading-bot

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

Open http://localhost:5173 - the frontend proxies `/api` to the backend automatically.

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

4. **Access**: Your bot will be at `https://cfd-trading-bot.onrender.com`

### Render free tier notes:
- Spins down after 15 min of inactivity (cold start ~30s)
- 750 hours/month (enough for 1 service 24/7)
- To keep it warm, use a free cron ping service like UptimeRobot on the `/health` endpoint

## Architecture

```
Browser (any device)
    |
    v
[FastAPI Backend]
    |-- /api/signals     -> Signal engine (regime-adaptive scoring)
    |-- /api/chart/:sym  -> Candlestick data
    |-- /api/trade/open  -> Open position via broker
    |-- /api/trade/close -> Close position via broker
    |-- /api/account     -> Account balance & stats
    |-- /api/news        -> News sentiment
    |-- /*               -> Serves React frontend (SPA)
    |
    +-- DataProvider (quotes + candles)
    |     sim:  Alpha Vantage -> synthetic fallback
    |     ibkr: IB Gateway real-time data
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
cfd-trading-bot/
  backend/
    main.py              # FastAPI app + signal engine
    broker.py            # Abstract Broker + DataProvider interfaces
    broker_sim.py        # Simulated paper trading
    broker_ibkr.py       # Interactive Brokers implementation
    broker_factory.py    # Creates broker based on BROKER_TYPE
    database.py          # MongoDB persistence layer
    indicators.py        # RSI, MACD, ATR, ADX, StochRSI, BB, volume
    alpha_vantage.py     # Price data client
    alpha_vantage_news.py # News sentiment client
    realistic_prices.py  # Synthetic price fallback
    models.py            # Pydantic models
    .env.example         # Environment variable template
  frontend/
    src/
      components/
        Dashboard.tsx    # Main layout + tab navigation
        MainTab.tsx      # Charts + signals view
        ChartsTab.tsx    # Multi-chart view
        TradesTab.tsx    # Open positions + history
        CandlestickChart.tsx  # OHLCV + RSI + volume chart
        ...
  render.yaml            # One-click Render deployment
```

## License

MIT
