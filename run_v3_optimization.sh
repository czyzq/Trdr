#!/bin/bash

# v3 Optimization Cron Job
# Runs every 30 minutes to test next optimization

cd ~/dev/cfd-trading-bot/backend
source venv/bin/activate

LOGFILE="/tmp/v3_optimization.log"
LIST_FILE="/Users/pinchr/dev/cfd-trading-bot/OPTIMIZATION_PROGRESS.md"

echo "=== v3 Optimization Run: $(date) ===" >> $LOGFILE

# Read current step
STEP=$(cat /tmp/v3_step.txt 2>/dev/null || echo "1")
echo "Current step: $STEP" >> $LOGFILE

case $STEP in
    1)
        echo "Testing: Volume Tiers" >> $LOGFILE
        # Test volume tiers effect
        python3 << 'EOF' >> $LOGFILE 2>&1
import json, urllib.request

# Compare base vs volume tiers
base = json.loads(urllib.request.urlopen("http://localhost:8012/api/backtest?symbol=BTC&resolution=5&days=30&strategy=adaptive_regime&min_score=0.01&leverage=50&tp_pct=0.05&sl_pct=0.02").read())
print(f"Base: {base['metrics']['total_pnl']}")
EOF
        echo "2" > /tmp/v3_step.txt
        ;;
    2)
        echo "Testing: ATR-based SL/TP" >> $LOGFILE
        # Test ATR-based exit (would need code changes)
        echo "ATR needs code implementation" >> $LOGFILE
        echo "3" > /tmp/v3_step.txt
        ;;
    3)
        echo "Testing: Max exposure cap" >> $LOGFILE
        # Test with different leverage
        python3 << 'EOF' >> $LOGFILE 2>&1
import json, urllib.request

for lev in [30, 40, 50]:
    url = f"http://localhost:8012/api/backtest?symbol=BTC&resolution=5&days=30&strategy=adaptive_regime&min_score=0.01&leverage={lev}&tp_pct=0.05&sl_pct=0.02"
    d = json.loads(urllib.request.urlopen(url).read())
    print(f"L={lev}: ${d['metrics']['total_pnl']}")
EOF
        echo "4" > /tmp/v3_step.txt
        ;;
    4)
        echo "Testing: Different symbols" >> $LOGFILE
        python3 << 'EOF' >> $LOGFILE 2>&1
import json, urllib.request

for sym in ["XAU", "ETH", "US100"]:
    try:
        url = f"http://localhost:8012/api/backtest?symbol={sym}&resolution=5&days=30&strategy=adaptive_regime&min_score=0.01&leverage=30&tp_pct=0.05&sl_pct=0.02"
        d = json.loads(urllib.request.urlopen(url).read())
        print(f"{sym}: ${d['metrics']['total_pnl']} ({d['metrics']['win_rate']}% win)")
    except:
        print(f"{sym}: ERROR")
EOF
        echo "5" > /tmp/v3_step.txt
        ;;
    5)
        echo "Testing: 90-day backtest" >> $LOGFILE
        python3 << 'EOF' >> $LOGFILE 2>&1
import json, urllib.request

url = "http://localhost:8012/api/backtest?symbol=BTC&resolution=5&days=90&strategy=adaptive_regime&min_score=0.01&leverage=50&tp_pct=0.05&sl_pct=0.02"
d = json.loads(urllib.request.urlopen(url).read())
print(f"90-day: ${d['metrics']['total_pnl']} (${d['metrics']['total_pnl']/3:.0f}/month)")
EOF
        echo "1" > /tmp/v3_step.txt  # Reset
        ;;
    *)
        echo "1" > /tmp/v3_step.txt
        ;;
esac

echo "Done. Next step: $(cat /tmp/v3_step.txt)" >> $LOGFILE
