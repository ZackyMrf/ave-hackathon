# Ave Accumulation Monitor

Crypto monitoring workspace that combines:

- A Python analysis engine (single token and market sweep)
- A FastAPI backend for analysis, trend matrix, chart data, and alerts
- A React dashboard for interactive monitoring and charting
- An advanced Telegram bot for commands, watchlist, and alert management

## What Is Implemented

### Core analysis

- Accumulation/risk analysis per token using AVE data
- Sweep scanning by category and chain
- Supported chains: solana, ethereum, bsc, base, arbitrum, optimism, polygon, avalanche
- Supported categories: all, trending, meme, defi, gaming, ai, new

### API server

The backend in api_server.py exposes endpoints for:

- Health/chains
- Token analysis and sweep
- Multi-token live prices
- Category-network trend matrix
- Klines/chart data
- AVE proxy endpoints (token, tokens, whales, holders)
- Alert CRUD and alert statistics

### Web dashboard (React + Vite)

- Token analyzer UI
- Sweep table with trend snapshots
- Interactive chart views (candlestick, line, area)
- Overlay indicators (MA/EMA)
- Live price refresh
- Alert panel (create/list/delete/toggle)

### Telegram bot (advanced)

- Commands: /start, /help, /analyze, /sweep, /alert, /watchlist
- Watchlist add/list/remove
- Alert create/list/delete/toggle
- Background monitoring worker (5-minute loop)

## Repository Layout

```text
ave-accumulation-monitor/
├─ api_server.py
├─ alerts_manager.py
├─ ave_api_service.py
├─ telegram_bot_advanced.py
├─ scripts/
│  ├─ ave_monitor.py
│  └─ help.py
├─ services/
│  └─ ave_cloud_wss.py
├─ frontend/
│  ├─ src/
│  └─ package.json
├─ archive/
│  ├─ demo/
│  └─ tests/
└─ README.md
```

## Requirements

- Python 3.10+
- Node.js 18+
- AVE API key
- Telegram bot token (only needed for bot/alert notifications)

## Setup

### 1. Python dependencies

```bash
pip install -r requirements-chart.txt
pip install fastapi uvicorn pydantic
```

### 2. Frontend dependencies

```bash
cd frontend
npm install
cd ..
```

### 3. Environment variables

Create a .env file in the project root:

```env
AVE_API_KEY=your_ave_api_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
API_BASE_URL=http://localhost:8000
```

For frontend override (optional):

```env
VITE_API_BASE=http://localhost:8000
```

## Run

### Option A: startup script

Windows PowerShell:

```powershell
.\startup.ps1
```

Linux/macOS:

```bash
bash startup.sh
```

### Option B: manual (3 terminals)

Terminal 1 (API):

```bash
python -m uvicorn api_server:app --host 0.0.0.0 --port 8000
```

Terminal 2 (Telegram bot):

```bash
python telegram_bot_advanced.py
```

Terminal 3 (Frontend):

```bash
cd frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

## CLI Usage

Single token analysis:

```bash
python scripts/ave_monitor.py --mode single --token SOL --chain solana
```

Sweep scan:

```bash
python scripts/ave_monitor.py --mode sweep --category trending --chain solana --top 5
```

JSON output:

```bash
python scripts/ave_monitor.py --mode single --token PEPE --chain ethereum --json
```

## API Quick Reference

- GET /api/health
- GET /api/chains
- GET /api/analyze?token=SOL&chain=solana
- GET /api/sweep?category=all&chain=solana&top=6
- GET /api/prices/live?tokens=sol,jup,pepe&chain=solana
- GET /api/trends/category-network?categories=trending,meme&chains=solana,base&top=5
- GET /api/klines
- GET /api/chart
- POST /api/alerts/create
- GET /api/alerts/user/{user_id}
- GET /api/alerts/token/{token}
- DELETE /api/alerts/{alert_id}
- PUT /api/alerts/{alert_id}/toggle
- GET /api/alerts/stats

Open interactive docs at http://localhost:8000/docs after API is running.

## Telegram Commands

```text
/start
/help
/analyze SOL solana
/sweep all solana
/alert create SOL solana price above 150
/alert list
/alert delete <alert_id>
/alert toggle <alert_id>
/watchlist add SOL solana
/watchlist list
/watchlist remove SOL
```

## Notes

- Alerts are persisted in alerts.json.
- Alert manager supports price/risk/volume/whale/trend types.
- Current advanced bot worker actively evaluates price and risk alerts in its loop.

## Additional Docs

- QUICKSTART.md
- MONITORING_GUIDE.md
- ARCHITECTURE.md

## Disclaimer

This project is for research/monitoring purposes only and is not financial advice.
