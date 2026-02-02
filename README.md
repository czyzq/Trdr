# Polymarket Trading Bot 🤖

An AI-powered trading bot for [Polymarket](https://polymarket.com) that uses deep research from [Perplexity](https://perplexity.ai) (via MCP) to generate informed trading signals on prediction markets.

## Features

- 🔍 **Deep Research**: Perplexity AI researches market topics for informed decisions
- 📊 **Live Dashboard**: Monitor portfolio, positions, and P&L in real-time
- 📈 **Signal Generation**: Automatic buy/sell signals based on research + market data
- 🔐 **Risk Management**: Position sizing, stop-loss, and exposure limits
- 🛡️ **Safety First**: Manual override, rate limiting, and safety checks

## Tech Stack

**Frontend:**
- React + TypeScript (Vite)
- Real-time market updates
- Responsive UI

**Backend:**
- FastAPI (Python)
- MongoDB for data persistence
- Polymarket API integration
- MCP client for Perplexity research
- WebSocket for live updates

## Quick Start

### Prerequisites
- Node.js 18+
- Python 3.10+
- MongoDB
- Polymarket account (funded with USDC on Polygon)
- Perplexity API key

### Setup

```bash
# Clone & enter directory
cd polymarket-bot

# Frontend
cd frontend && npm install && npm run dev

# Backend (in new terminal)
cd backend && python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt && python main.py
```

See [SETUP.md](./SETUP.md) for detailed instructions.

## Project Structure

```
polymarket-bot/
├── frontend/          # React + Vite dashboard
├── backend/           # FastAPI trading engine
├── PROJECT.md         # Full planning & architecture
├── SETUP.md           # Installation guide
└── README.md          # This file
```

## What You Need

### API Keys
- **Polymarket**: API key + private key
- **Perplexity**: API key for research queries
- **MongoDB**: Connection string (local or Atlas)

### Development Tools
- git + GitHub CLI
- Docker (optional, for MongoDB)
- Text editor/IDE

## Roadmap

- [ ] Phase 1: Core infrastructure setup
- [ ] Phase 2: Research + signal generation
- [ ] Phase 3: Trading & portfolio features
- [ ] Phase 4: Advanced automation & backtesting

## Documentation

- [PROJECT.md](./PROJECT.md) - Full architecture, tech stack, features
- [SETUP.md](./SETUP.md) - Installation & troubleshooting
- [API Documentation](http://localhost:8000/docs) - Auto-generated (after backend starts)

## Contributing

This is a personal project. Contributions welcome via GitHub issues/PRs.

## License

MIT

---

**Built with ❤️ by pinchr**
