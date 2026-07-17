#!/bin/bash

# CFD Trading Bot - health monitor with auto-restart.
# No git operations in here: this script must never commit or push.

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="/tmp/cfd-monitor.log"
CHECK_INTERVAL=300 # 5 minutes
BACKEND_PORT="${BACKEND_PORT:-8001}"
BACKEND_URL="http://localhost:${BACKEND_PORT}"

restart_backend() {
  echo "Restarting backend..." >> "$LOG_FILE"
  pkill -9 -f "python.*main" 2>/dev/null
  sleep 3
  cd "$PROJECT_DIR/backend" && source venv/bin/activate && python main.py --port "$BACKEND_PORT" > /tmp/backend.log 2>&1 &
  sleep 8
}

echo "[$(date)] Starting CFD Bot monitor on port $BACKEND_PORT" >> "$LOG_FILE"

while true; do
  echo "" >> "$LOG_FILE"
  echo "=== CHECK at $(date) ===" >> "$LOG_FILE"

  # 1. Backend health
  BACKEND_ALIVE=$(curl -s "$BACKEND_URL/" 2>/dev/null | grep -c "CFD Trading Bot API")
  if [ "$BACKEND_ALIVE" -eq 0 ]; then
    echo "[ISSUE] Backend not responding" >> "$LOG_FILE"
    restart_backend
  fi

  # 2. Account endpoint
  ACCOUNT=$(curl -s "$BACKEND_URL/api/account" 2>/dev/null | grep -o '"balance"')
  if [ -z "$ACCOUNT" ]; then
    echo "[ISSUE] Account endpoint broken" >> "$LOG_FILE"
    restart_backend
  fi

  # 3. Signals endpoint
  SIGNALS=$(curl -s "$BACKEND_URL/api/signals" 2>/dev/null | grep -o '"symbol"')
  if [ -z "$SIGNALS" ]; then
    echo "[ISSUE] Signals endpoint broken" >> "$LOG_FILE"
    restart_backend
  fi

  # 4. Frontend
  FRONTEND=$(curl -s http://localhost:5173 2>/dev/null | grep -c "CFD Trading Bot")
  if [ "$FRONTEND" -eq 0 ]; then
    echo "[ISSUE] Frontend not responding" >> "$LOG_FILE"
    pkill -9 -f "npm run dev" 2>/dev/null
    sleep 2
    cd "$PROJECT_DIR/frontend" && npm run dev > /tmp/frontend.log 2>&1 &
    sleep 8
  fi

  # 5. Backend log errors
  BACKEND_ERRORS=$(grep -ci "error\|exception" /tmp/backend.log 2>/dev/null)
  if [ "${BACKEND_ERRORS:-0}" -gt 0 ]; then
    echo "[WARNING] Found $BACKEND_ERRORS errors in backend log" >> "$LOG_FILE"
    tail -5 /tmp/backend.log >> "$LOG_FILE"
  fi

  # 6. API responsiveness
  RESPONSE_TIME=$(curl -s -w '%{time_total}' -o /dev/null "$BACKEND_URL/api/signals")
  if (( $(echo "$RESPONSE_TIME > 5" | bc -l) )); then
    echo "[SLOW] API response slow: ${RESPONSE_TIME}s" >> "$LOG_FILE"
  fi

  # 7. Data sanity
  BALANCE=$(curl -s "$BACKEND_URL/api/account" 2>/dev/null | grep -o '"balance": [0-9.]*' | head -1)
  SCORE=$(curl -s "$BACKEND_URL/api/signals" 2>/dev/null | grep -o '"score": [0-9.]*' | head -1)
  echo "[DATA] $BALANCE | First signal $SCORE" >> "$LOG_FILE"

  echo "[OK] Check complete, next in ${CHECK_INTERVAL}s" >> "$LOG_FILE"
  sleep $CHECK_INTERVAL
done
