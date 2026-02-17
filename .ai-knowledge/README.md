# CFD Trading Bot - Project Knowledge
**Last updated: 2026-02-17**

## About This Knowledge Base

This directory contains **project-specific** knowledge only:
- Code architecture
- Configuration files
- Bug tracking for THIS codebase
- Deployment details

**Trading expertise** is in my personal memory:
- `memory/trading/CORE.md` - core trading principles
- `memory/trading/strategies/LIBRARY.md` - strategy definitions
- `memory/trading/risk/RULES.md` - risk management

## Quick Links

| What | Where |
|------|-------|
| Trading strategies | `memory/trading/strategies/LIBRARY.md` |
| Risk management | `memory/trading/risk/RULES.md` |
| Market knowledge | `memory/trading/CORE.md` |
| This project's code | `code/` (this folder) |
| Current config | `active/` (this folder) |

## Project Structure

```
cfd-trading-bot/
├── backend/
│   ├── main.py              # FastAPI + async trading loop
│   ├── strategies.py        # AdaptiveRegime + MMS implementations
│   ├── broker_sim.py        # AsyncSimulatedBroker
│   ├── alpha_vantage.py     # Data provider
│   └── database.py          # MongoDB async operations
├── frontend/                # Vite + React UI
└── .ai-knowledge/          # This folder
    ├── active/             # Current config (HOT)
    ├── code/               # Code patterns (WARM)
    └── research/           # Research dumps (COLD)
```

## Active Configuration

See `active/current-strategy.md` for current parameters.

## Known Issues

See `code/known-issues.md` for bug tracking.

## When I Answer Questions

1. Read my trading expertise from `memory/trading/`
2. Read this project's config from `active/`
3. Read code from `~/dev/cfd-trading-bot/backend/`
4. Combine for accurate, actionable answers

---
*This is the bridge between my trading expertise and this specific codebase.*
