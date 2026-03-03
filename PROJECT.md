# Polymarket Trading Bot

## Overview
AI-powered trading bot for Polymarket that uses deep research from Perplexity (via MCP) to make informed trading decisions on crypto/prediction markets.

---

## Architecture & Tech Stack

### Frontend
- **Framework:** React + TypeScript (Vite)
- **State Management:** TBD (Redux, Zustand, or Context API)
- **UI Components:** Tailwind CSS
- **Port:** 5176
- **Features:**
  - Dashboard: Live market positions, P&L, portfolio
  - Market explorer: Browse/search Polymarket markets
  - Trade interface: Place/cancel orders
  - Research panel: Display Perplexity research summaries
  - Settings: API keys, trading parameters

### Backend
- **Framework:** FastAPI (Python)
- **Database:** MongoDB
- **Port:** 8001
- **Key Features:**
  - Polymarket API integration (websocket for live updates)
  - MCP client for Perplexity research
  - Trading logic & signal generation
  - Portfolio tracking
  - Webhook handlers for market updates

### External APIs & Services
1. **Polymarket API**
   - REST endpoints for market data, orders, portfolio
   - WebSocket for real-time updates
   - Authentication: Private key signing

2. **Perplexity (via MCP)**
   - Deep research on market topics
   - Sentiment analysis
   - News/data aggregation
   - Used to generate trading signals

3. **MCP (Model Context Protocol)**
   - Server: Perplexity research tool
   - Client: Backend bot agent

---

## Project Structure

```
polymarket-bot/
├── frontend/                    # React + Vite app
│   ├── src/
│   │   ├── components/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── MarketExplorer.tsx
│   │   │   ├── TradePanel.tsx
│   │   │   ├── ResearchPanel.tsx
│   │   │   └── Settings.tsx
│   │   ├── api/
│   │   │   └── client.ts        # Backend API calls
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.json
│
├── backend/                     # FastAPI server
│   ├── main.py                  # Entry point
│   ├── routers/
│   │   ├── markets.py           # Polymarket endpoints
│   │   ├── orders.py            # Trading endpoints
│   │   ├── portfolio.py         # User portfolio
│   │   └── research.py          # Perplexity research endpoints
│   ├── services/
│   │   ├── polymarket.py        # Polymarket API wrapper
│   │   ├── mcp_client.py        # MCP/Perplexity integration
│   │   ├── trading_engine.py    # Trading logic & signals
│   │   └── db.py                # MongoDB operations
│   ├── models/
│   │   ├── market.py
│   │   ├── order.py
│   │   ├── portfolio.py
│   │   └── research.py
│   ├── requirements.txt
│   └── docker-compose.yml       # MongoDB + services
│
├── PROJECT.md                   # This file
├── SETUP.md                     # Setup instructions
└── README.md                    # Project overview
```

---

## Key Features (Phase 1-3)

### Phase 1: Core Infrastructure
- ✅ GitHub repository setup
- [ ] Frontend + Backend scaffolding
- [ ] Database schema (markets, orders, portfolio, research)
- [ ] Polymarket API authentication & basic endpoints
- [ ] MCP setup for Perplexity integration

### Phase 2: Research & Signal Generation
- [ ] Perplexity research queries (market analysis, news)
- [ ] Signal generation engine (buy/sell confidence scores)
- [ ] Research history & tracking
- [ ] Dashboard to display research insights

### Phase 3: Trading Features
- [ ] Live portfolio tracking
- [ ] Order placement/cancellation
- [ ] Real-time market updates (WebSocket)
- [ ] P&L calculations
- [ ] Trading history & analytics

### Phase 4: Advanced Features
- [ ] Risk management (max position size, stop-loss)
- [ ] Multi-market correlation analysis
- [ ] Backtesting framework
- [ ] Automated trading with safety limits
- [ ] Email/SMS alerts

---

## What You Need

### API Keys & Credentials
1. **Polymarket**
   - API Key (if available)
   - Private key for signing transactions
   - Account funding (USDC on Polygon)

2. **Perplexity (for MCP)**
   - API key or MCP server endpoint
   - Research model selection

### Development Tools
- Node.js v18+
- Python 3.10+
- MongoDB (local or Atlas)
- git + GitHub CLI (`gh`)
- Docker (optional, for MongoDB)

### Libraries & Dependencies

**Frontend:**
```json
{
  "react": "^18.x",
  "typescript": "^5.x",
  "vite": "^5.x",
  "tailwindcss": "^3.x",
  "axios": "^1.x"
}
```

**Backend:**
```
fastapi==0.104.1
uvicorn==0.24.0
pymongo==4.6.0
python-dotenv==1.0.0
pydantic==2.5.0
httpx==0.25.2
websockets==12.0
# MCP & Perplexity
mcp-client==0.x.x  # TBD based on Perplexity setup
```

---

## Next Steps

1. ✅ Create repository & planning (this file)
2. [ ] Initialize frontend & backend scaffolding
3. [ ] Set up MongoDB
4. [ ] Create Polymarket API wrapper
5. [ ] Set up MCP client for Perplexity
6. [ ] Build basic dashboard
7. [ ] Test signal generation
8. [ ] Deploy & iterate

---

## Trading Strategy (Draft)

**Signal Generation:**
- Perplexity researches market/event
- Sentiment & confidence extracted
- Combined with market data (volume, spreads, odds)
- Buy signal: High confidence + favorable odds + low spread
- Sell signal: Target reached or research sentiment reverses

**Risk Controls:**
- Max position per market: TBD (% of portfolio)
- Max portfolio allocation: TBD (% to trading)
- Stop-loss: TBD (%)
- Manual override always available

---

## Questions for You

1. **Polymarket Account:** Do you have a funded account ready?
2. **Perplexity Integration:** Is MCP already set up, or do we start from scratch?
3. **Trading Capital:** What's your target initial allocation?
4. **Automation Level:** Full auto-trading, or manual confirmation for each trade?
5. **Markets Focus:** Any specific markets/categories (crypto, politics, sports, etc.)?

---

*Last updated: 2026-02-01*
