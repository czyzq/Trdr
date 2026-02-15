# Setup Instructions

## Prerequisites

- Node.js 18+ (`node -v`)
- Python 3.10+ (`python3 --version`)
- MongoDB running locally or Atlas connection string
- GitHub CLI (`gh auth status`)

## Initial Setup

### 1. Clone & Navigate
```bash
cd ~/Documents/projects/polymarket-bot
```

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
# Starts on http://localhost:5176
```

### 3. Backend Setup
```bash
cd ../backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
# Starts on http://localhost:8001
```

### 4. Environment Variables

**Backend `.env`:**
```
MONGODB_URI=mongodb://localhost:27017/polymarket-bot
POLYMARKET_API_KEY=your_api_key
POLYMARKET_PRIVATE_KEY=your_private_key
PERPLEXITY_API_KEY=your_perplexity_key
LOG_LEVEL=INFO
```

**Frontend `.env`:**
```
VITE_API_URL=http://localhost:8001/api
```

### 5. Database

**Local MongoDB (Docker):**
```bash
docker-compose up -d mongodb
```

**Or Atlas (Cloud):**
- Create cluster at mongodb.com/cloud
- Get connection string
- Add to `.env` as `MONGODB_URI`

## Verification

- [ ] Frontend loads: http://localhost:5176
- [ ] Backend ready: http://localhost:8001/docs
- [ ] MongoDB connected: Check backend logs
- [ ] MCP configured: Test Perplexity integration

## Troubleshooting

**Port already in use:**
```bash
# Find & kill process on port 5176/8001
lsof -i :5176
kill -9 <PID>
```

**Python venv issues:**
```bash
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**MongoDB connection:**
```bash
mongosh  # Check if running locally
# Or test Atlas connection string in backend logs
```

---

*For detailed architecture, see PROJECT.md*
