#!/bin/bash
# Continuous trading optimization - run as cron job
# Usage: ./run_optimization.sh

echo "=== Trading Bot Optimization ==="
echo "Started: $(date)"

BACKEND_URL="http://localhost:8001"
SYMBOLS=("XAU" "BTC" "XAG")
RESOLUTIONS=("60" "5")
DAYS=3

# Test configurations
CONFIGS=(
  "strategy=simple_momentum,min_score=0.01,leverage=3,tp_pct=0.04,sl_pct=0.02"
  "strategy=simple_momentum,min_score=0.01,leverage=3,tp_pct=0.03,sl_pct=0.015"
  "strategy=simple_momentum,min_score=0.01,leverage=3,tp_pct=0.05,sl_pct=0.025"
  "strategy=simple_momentum,min_score=0.01,leverage=3,tp_pct=0.04,sl_pct=0.02,trailing_sl_pct=0.01"
  "strategy=adaptive_regime,min_score=0.01,leverage=3,tp_pct=0.04,sl_pct=0.02"
  "strategy=mms,min_score=0.01,leverage=3,tp_pct=0.03,sl_pct=0.02"
)

# Store results
RESULTS_FILE="/tmp/optimization_results_$(date +%Y%m%d_%H%M%S).json"
echo "[]" > "$RESULTS_FILE"

# Run each configuration
for config in "${CONFIGS[@]}"; do
  echo "Testing: $config"
  
  # Build URL
  URL="${BACKEND_URL}/api/backtest?symbol=XAU&resolution=60&days=${DAYS}&${config}"
  
  # Run in background and capture result
  RESULT=$(curl -s "$URL" 2>/dev/null)
  
  if [ $? -eq 0 ]; then
    echo "$RESULT" >> "$RESULTS_FILE"
    echo "  -> Done"
  else
    echo "  -> Failed"
  fi
  
  # Wait a bit between requests
  sleep 1
done

echo ""
echo "=== Results saved to $RESULTS_FILE ==="

# Find best result
echo ""
echo "=== Best Results ==="
python3 -c "
import json

try:
    with open('$RESULTS_FILE') as f:
        results = json.load(f)
    
    # Sort by P&L
    sorted_results = sorted(results, key=lambda x: x.get('metrics', {}).get('total_pnl', 0), reverse=True)
    
    print('Top 3 configurations:')
    for i, r in enumerate(sorted_results[:3]):
        m = r.get('metrics', {})
        print(f'{i+1}. {r.get(\"config\", {}).get(\"strategy\")}: \${m.get(\"total_pnl\", 0):.2f} ({m.get(\"win_rate\", 0)}% win)')
except Exception as e:
    print(f'Error: {e}')
"

echo ""
echo "Finished: $(date)"
