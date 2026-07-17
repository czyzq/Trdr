# Setup

Local development setup for the Trdr CFD trading bot. See `README.md` for the full feature overview and architecture.

## Prerequisites

- Python 3.10+
- Node 18+
- A free [Alpha Vantage API key](https://alphavantage.co/support/#api-key)
- Optional: a MongoDB Atlas connection string (without it, data lives in memory and is lost on restart)

## Backend

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: set ALPHA_VANTAGE_API_KEY, and MONGO_URI if you have one

python main.py --port 8001
```

The backend always runs on port **8001**. Health check: `curl http://localhost:8001/api/health`.

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — the Vite dev server proxies `/api` and `/cfd/api` to the backend on port 8001.

## Environment variables

All configuration is env-driven; nothing is hardcoded. See `backend/.env.example` for the full list:

| Variable | Required | Purpose |
|----------|----------|---------|
| `ALPHA_VANTAGE_API_KEY` | yes | Quotes, candles |
| `MONGO_URI` | recommended | Persistence (Atlas free M0 works) |
| `MONGO_DB` | no | DB name, default `cfd_trading_bot` |
| `BROKER_TYPE` | no | `sim` (default) or `ibkr` |
| `IMESSAGE_ALERT_RECIPIENT` | no | Phone number for iMessage alerts (Mac only) |

## Monitoring (optional)

`./monitor.sh` health-checks the backend/frontend every 5 minutes and restarts them if dead. It performs no git operations. Override the port with `BACKEND_PORT=8001 ./monitor.sh`.

## Deployment

Render deployment via `render.yaml` — see the "Deploy to Render" section in `README.md`.
