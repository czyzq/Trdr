#!/bin/bash

# CFD Trading Bot - Auto-Monitoring & Self-Healing Loop
# Mode B: Aggressive auto-fix with descriptive commits

PROJECT_DIR="/Users/openclaw/Documents/projects/cfd-trading-bot"
LOG_FILE="/tmp/cfd-monitor.log"
CHECK_INTERVAL=300 # 5 minutes

echo "[$(date)] Starting CFD Bot monitor (Mode B - Aggressive)" >> $LOG_FILE

while true; do
  echo "" >> $LOG_FILE
  echo "=== CHECK at $(date) ===" >> $LOG_FILE
  
  # 1. Check backend health
  BACKEND_ALIVE=$(curl -s http://localhost:8000/ 2>/dev/null | grep -c "CFD Trading Bot API")
  if [ "$BACKEND_ALIVE" -eq 0 ]; then
    echo "[ISSUE] Backend not responding" >> $LOG_FILE
    echo "Restarting backend..." >> $LOG_FILE
    pkill -9 -f "python.*main" 2>/dev/null
    sleep 3
    cd $PROJECT_DIR/backend && source venv/bin/activate && python main.py > /tmp/backend.log 2>&1 &
    sleep 8
    # Commit
    cd $PROJECT_DIR && git add -A && git commit -m "fix: auto-restart backend (health check failed)" >> $LOG_FILE 2>&1
  fi
  
  # 2. Check account endpoint
  ACCOUNT=$(curl -s http://localhost:8000/api/account 2>/dev/null | grep -o '"balance"')
  if [ -z "$ACCOUNT" ]; then
    echo "[ISSUE] Account endpoint broken" >> $LOG_FILE
    echo "Restarting backend..." >> $LOG_FILE
    pkill -9 -f "python.*main" 2>/dev/null
    sleep 3
    cd $PROJECT_DIR/backend && source venv/bin/activate && python main.py > /tmp/backend.log 2>&1 &
    sleep 8
    cd $PROJECT_DIR && git add -A && git commit -m "fix: auto-restart backend (account endpoint broken)" >> $LOG_FILE 2>&1
  fi
  
  # 3. Check signals endpoint
  SIGNALS=$(curl -s http://localhost:8000/api/signals 2>/dev/null | grep -o '"symbol"')
  if [ -z "$SIGNALS" ]; then
    echo "[ISSUE] Signals endpoint broken" >> $LOG_FILE
    echo "Restarting backend..." >> $LOG_FILE
    pkill -9 -f "python.*main" 2>/dev/null
    sleep 3
    cd $PROJECT_DIR/backend && source venv/bin/activate && python main.py > /tmp/backend.log 2>&1 &
    sleep 8
    cd $PROJECT_DIR && git add -A && git commit -m "fix: auto-restart backend (signals endpoint broken)" >> $LOG_FILE 2>&1
  fi
  
  # 4. Check frontend
  FRONTEND=$(curl -s http://localhost:5173 2>/dev/null | grep -c "CFD Trading Bot")
  if [ "$FRONTEND" -eq 0 ]; then
    echo "[ISSUE] Frontend not responding" >> $LOG_FILE
    echo "Restarting frontend..." >> $LOG_FILE
    pkill -9 -f "npm run dev" 2>/dev/null
    sleep 2
    cd $PROJECT_DIR/frontend && npm run dev > /tmp/frontend.log 2>&1 &
    sleep 8
    cd $PROJECT_DIR && git add -A && git commit -m "fix: auto-restart frontend (health check failed)" >> $LOG_FILE 2>&1
  fi
  
  # 5. Check backend logs for errors
  BACKEND_ERRORS=$(grep -i "error\|exception" /tmp/backend.log 2>/dev/null | wc -l)
  if [ "$BACKEND_ERRORS" -gt 0 ]; then
    echo "[WARNING] Found $BACKEND_ERRORS errors in backend log" >> $LOG_FILE
    tail -5 /tmp/backend.log >> $LOG_FILE
  fi
  
  # 6. Test API responsiveness
  RESPONSE_TIME=$(curl -s -w '%{time_total}' -o /dev/null http://localhost:8000/api/signals)
  if (( $(echo "$RESPONSE_TIME > 5" | bc -l) )); then
    echo "[SLOW] API response slow: ${RESPONSE_TIME}s" >> $LOG_FILE
  fi
  
  # 7. Verify real data is flowing
  BALANCE=$(curl -s http://localhost:8000/api/account 2>/dev/null | grep -o '"balance": [0-9.]*' | head -1)
  SCORE=$(curl -s http://localhost:8000/api/signals 2>/dev/null | grep -o '"score": [0-9.]*' | head -1)
  echo "[DATA] $BALANCE | First signal $SCORE" >> $LOG_FILE
  
  # 8. Check for frontend data binding
  LAST_SCAN=$(curl -s http://localhost:5173 2>/dev/null | grep -i "last scan" | head -1)
  if [ -z "$LAST_SCAN" ]; then
    echo "[ISSUE] Frontend not displaying account data" >> $LOG_FILE
  else
    echo "[OK] Frontend showing data" >> $LOG_FILE
  fi
  
  # Push commits to GitHub
  cd $PROJECT_DIR
  PENDING=$(git status --porcelain | wc -l)
  if [ "$PENDING" -gt 0 ]; then
    echo "[COMMIT] Pushing $PENDING changes to GitHub" >> $LOG_FILE
    git push origin main >> $LOG_FILE 2>&1
  fi
  
  echo "[OK] Check complete, next in ${CHECK_INTERVAL}s" >> $LOG_FILE
  sleep $CHECK_INTERVAL
done
