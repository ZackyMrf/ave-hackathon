# 📊 Ave Accumulation Monitor — Complete Documentation

> A multi-chain crypto accumulation monitoring platform based on real-time Ave.ai data, featuring an interactive dashboard, Telegram bot, and automated alert system.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Ave Skill — Concept & How It Works](#2-ave-skill--concept--how-it-works)
3. [System Architecture](#3-system-architecture)
4. [Repository Structure](#4-repository-structure)
5. [Ave API Integration](#5-ave-api-integration)
6. [Accumulation Score Engine](#6-accumulation-score-engine)
7. [Backend API Server](#7-backend-api-server)
8. [Live Buy/Sell Feed (WebSocket)](#8-live-buysell-feed-websocket)
9. [Alerts Manager](#9-alerts-manager)
10. [Telegram Bot (Advanced)](#10-telegram-bot-advanced)
11. [Frontend Dashboard (React + Vite)](#11-frontend-dashboard-react--vite)
12. [Setup & Installation](#12-setup--installation)
13. [How to Run](#13-how-to-run)
14. [API Endpoint Reference](#14-api-endpoint-reference)
15. [Environment Configuration](#15-environment-configuration)
16. [Security & Fake Token Detection](#16-security--fake-token-detection)
17. [Disclaimer](#17-disclaimer)

---

## 1. Project Overview

**Ave Accumulation Monitor** is a crypto intelligence platform that detects token accumulation signals *before* the price moves. This platform is designed to:

- 🔍 **Detect stealth accumulation** by smart money before retail reacts
- 🐋 **Track whale movements** in real-time
- 📈 **Run sweep scans** across token categories in one click
- 🔔 **Send automated alerts** to Telegram when specific conditions are met
- 📊 **Visualize data** in an interactive React-based dashboard

This platform **does not just display prices** — rather, it reads the divergence between volume and price, holder growth patterns, TVL stability, and whale activity to find *pre-movement* signals.

---

## 2. Ave Skill — Concept & How It Works

### 2.1 What is the Ave Skill?

The Ave Skill (`ave-accumulation-monitor`) is an integrated analysis module that uses the **Ave.ai API v2** as its primary data source. This skill is designed to answer the question:

> *"Is anyone quietly accumulating this token?"*

This skill triggers on phrases such as:
- `"monitor this token"`
- `"is anyone accumulating X"`
- `"find tokens being quietly bought"`
- `"smart money signal"`
- `"pre-pump detection"`
- `"show me accumulation"`
- `"whale accumulation scan"`
- `"early signal on X"`

### 2.2 The Accumulation Divergence Model

The core concept of this skill: **genuine accumulation leaves footprints before the price moves**.

When smart money buys quietly, the emerging patterns are:

| Signal | Meaning |
|--------|---------|
| Volume rises, price stays flat | Buying pressure is absorbed without dumps |
| Buy volume > Sell volume | Genuine buying pressure |
| TVL stable or rising | LP providers aren't fleeing |
| Holder count increases | Distribution to new wallets |
| Locked supply is high | Circulating supply is constrained |

When these signals appear together with *flat* or slightly positive price action, that is the **accumulation window** — the moment before the retail crowd notices.

### 2.3 Two Operation Modes

#### Mode A: Single Token Monitor
In-depth analysis of a single token based on symbol or contract address.

```
Flow:
1. Resolve token → /v2/tokens?keyword={input}
2. Fetch multi-timeframe data → /v2/tokens/{id}, /v2/klines/token/{id}
3. Fetch whale data → /v2/tokens/top100/{id}
4. Run Accumulation Score Engine
5. Generate structured signal report
```

#### Mode B: Sweep Scan
Automatically scan multiple tokens within a category to find the best accumulation candidates.

```
Flow:
1. Fetch trending list → /v2/tokens/trending?chain={chain}
2. Pre-filter: TVL > 50K, risk_score < 80, tx_count > 50
3. Score all candidates using Accumulation Score Engine
4. Return top-N tokens based on the highest score
```

### 2.4 Ave Skill File: `SKILL.md`

The `SKILL.md` file contains the complete skill specification in YAML front-matter + Markdown format, including:
- Trigger phrases description
- API compatibility
- Complete detection logic
- Output format
- Chain support

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     CLIENT LAYER                            │
│  ┌──────────────────┐        ┌────────────────────────────┐ │
│  │  React Dashboard │        │    Telegram Bot (Advanced) │ │
│  │  (Vite, port 5173)│        │   telegram_bot_advanced.py │ │
│  └────────┬─────────┘        └──────────────┬─────────────┘ │
└───────────┼──────────────────────────────────┼──────────────┘
            │ HTTP REST                        │ Long Poll
            ▼                                  ▼
┌─────────────────────────────────────────────────────────────┐
│                   BACKEND LAYER                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │          FastAPI Server (api_server.py)              │   │
│  │  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │   │
│  │  │ /analyze │  │ /sweep   │  │ /alerts (CRUD)    │  │   │
│  │  │ /prices  │  │ /klines  │  │ /telegram (deep)  │  │   │
│  │  │ /trends  │  │ /whales  │  │ /live-feed (WS)   │  │   │
│  │  └────┬─────┘  └─────┬────┘  └─────────┬─────────┘  │   │
│  └───────┼──────────────┼─────────────────┼───────────┘   │
│          │              │                 │                │
│  ┌───────▼──────────────▼─────────────────▼──────────────┐ │
│  │              AveAccumulationMonitor                    │ │
│  │              (scripts/ave_monitor.py)                  │ │
│  │         + AlertsManager (alerts_manager.py)            │ │
│  │         + AveApiService (ave_api_service.py)           │ │
│  │         + AveLiveBuySellFeed (ave_live_buysell_feed.py)│ │
│  └────────────────────────┬───────────────────────────────┘ │
└───────────────────────────┼─────────────────────────────────┘
                            │ HTTPS / WSS
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    AVE.AI API LAYER                         │
│  REST API: https://prod.ave-api.com (v2)                    │
│  Internal: https://api.agacve.com/v1                        │
│  WebSocket: wss://wss.ave-api.xyz (live feed)               │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Repository Structure

```
ave-accumulation-monitor/
│
├── 📄 api_server.py               # FastAPI backend server (2099 lines)
├── 📄 alerts_manager.py           # Alert CRUD, evaluation, & Telegram notifications
├── 📄 ave_api_service.py          # Ave API v1/v3 service wrapper
├── 📄 ave_helpers.py              # Helper utilities
├── 📄 ave_live_buysell_feed.py    # WebSocket live BUY/SELL feed from Ave Cloud
├── 📄 ave_monitor.py              # Core analysis engine (scripts/)
├── 📄 telegram_bot_advanced.py    # Telegram bot with watchlist & alerts
├── 📄 telegram_bot_simple.py      # Minimal version of Telegram bot
├── 📄 telegram_bot.py             # Basic Telegram bot
│
├── 📄 SKILL.md                    # Ave Skill specification (YAML + Markdown)
├── 📄 ARCHITECTURE.md             # Architecture documentation
├── 📄 MONITORING_GUIDE.md         # Monitoring guide
├── 📄 QUICKSTART.md               # Quick start guide
├── 📄 README.md                   # Project summary
│
├── 📁 scripts/
│   ├── ave_monitor.py             # Core analysis (Mode A & B)
│   └── help.py                    # CLI help text
│
├── 📁 services/
│   └── ave_cloud_wss.py           # Ave Cloud WebSocket service
│
├── 📁 frontend/                   # React + Vite dashboard
│   ├── index.html
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx                # Application root, routing, main state
│       ├── main.jsx               # React entry point
│       ├── styles.css             # Global CSS (72KB)
│       ├── mobile.css             # Mobile-specific styles
│       ├── TradingViewChart.jsx   # Candlestick chart component
│       ├── AdvancedMonitoring.jsx # Advanced monitoring component
│       ├── components/
│       │   ├── LandingScreen.jsx  # Landing page with Telegram connect
│       │   ├── PlatformTopNav.jsx # Platform top navigation
│       │   ├── ApiDocs.jsx        # Interactive API documentation page
│       │   ├── Sparkline.jsx      # Sparkline mini chart component
│       │   └── sections/
│       │       ├── DashboardSection.jsx    # Main dashboard (sweep, analyze)
│       │       ├── WhaleFeedSection.jsx    # Live whale transaction feed
│       │       ├── SignalEngineSection.jsx # Signal engine visualization
│       │       └── RiskMatrixSection.jsx   # Multi-chain risk matrix
│       ├── constants/
│       │   └── monitoring.js      # Token, chain, and category constants
│       ├── hooks/
│       │   └── ...                # Custom React hooks
│       └── utils/
│           └── monitoring.js      # Utility functions (formatting, URL resolvers, etc.)
│
├── 📁 scratch/                    # Test & experiment scripts
├── 📁 archive/                    # Demos & old tests
│
├── 📄 .env                        # Environment variables (not committed)
├── 📄 requirements.txt            # Python dependencies
├── 📄 requirements-chart.txt      # Chart/candlestick dependencies
├── 📄 startup.ps1                 # Windows PowerShell startup script
├── 📄 startup.sh                  # Linux/macOS startup script
├── 📄 Procfile                    # Deployment config (Heroku/Railway)
└── 📄 alerts.json                 # Persistent alert storage (auto-generated)
```

---

## 5. Ave API Integration

### 5.1 Ave.ai API v2 (Primary)

**Base URL:** `https://prod.ave-api.com`
**Auth:** Header `X-API-KEY: {AVE_API_KEY}`

#### Used Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /v2/tokens?keyword={q}&chain={chain}&limit=5` | Search tokens by symbol/address |
| `GET /v2/tokens/{token-id}` | Token details + pair info |
| `GET /v2/tokens/top100/{token-id}` | Top 100 holders for whale analysis |
| `GET /v2/klines/token/{token-id}?interval=1440&limit=30` | 30-day price & volume history |
| `GET /v2/tokens/trending?chain={chain}&page_size=50` | Trending list for sweep scan |

### 5.2 Ave API v1/v3 (AveApiService)

**File:** `ave_api_service.py`
**Base URL:** `https://api.agacve.com/v1`

Used as a **fallback** when v2 lookup fails.

```python
class AveApiService:
    def get_token_info(ca, chain)           # Token info by contract address
    def get_tokens_by_chain(chain, limit)  # Trending token list per chain
    def get_whale_movements(ca, chain)     # Whale movements
    def get_holder_distribution(ca, chain) # Holder distribution
```

**Token ID Format:** `{contract_address}-{chain}` (example: `6p6xgHyF7AeE6TZkSmFsko444wqoP15icUSqi2jfGiPN-solana`)

### 5.3 Ave WebSocket Feed

**URL:** `wss://wss.ave-api.xyz`
**Auth:** Header `X-API-KEY`
**Protocol:** JSON-RPC 2.0

Used in `ave_live_buysell_feed.py` for real-time streaming of BUY/SELL transactions:

```json
// Subscribe request
{
  "jsonrpc": "2.0",
  "method": "subscribe",
  "params": ["multi_tx", "{token_address}", "{chain}"],
  "id": 1
}

// Event response
{
  "result": {
    "tx": {
      "wallet_address": "...",
      "from_address": "...",
      "to_address": "...",
      "amount_usd": 1234.56,
      "transaction": "0xabc...",
      "chain": "solana",
      "amm": "raydium",
      "time": 1713000000
    }
  }
}
```

### 5.4 Supported Chains

| Chain | Alias |
|-------|-------|
| `solana` | — |
| `ethereum` | `eth` |
| `bsc` | — |
| `base` | — |
| `arbitrum` | — |
| `optimism` | — |
| `polygon` | — |
| `avalanche` | — |

---

## 6. Accumulation Score Engine

**File:** `scripts/ave_monitor.py` (also referenced in `SKILL.md`)

0–100 scoring system. Higher = stronger pre-movement accumulation signal.

### 6.1 Signal 1: Volume/Price Divergence (0–30 pts)

Core signal: volume rises while price stays flat = stealth accumulation.

```
volume_ratio = vol_24h / avg_volume_30d

If volume_ratio ≥ 2.5 AND |price_24h| < 3% → +30 pts (strong divergence)
If volume_ratio ≥ 1.8 AND |price_24h| < 5% → +20 pts (moderate)
If volume_ratio ≥ 1.3 AND |price_24h| < 7% → +10 pts (mild)
```

**Why it's effective:** Organic price discovery with a volume surge usually leads straight to a pump. When volume surges but the price is stagnant, someone is absorbing the selling pressure — that is accumulation.

### 6.2 Signal 2: Volume Momentum Velocity (0–25 pts)

Measures volume acceleration (last 3 days vs previous 3 days).

```
momentum = avg_vol_last_3_days / avg_vol_prev_3_days

If momentum ≥ 3.0 → +25 pts (extreme acceleration)
If momentum ≥ 2.5 → +22 pts
If momentum ≥ 2.0 → +19 pts
If momentum ≥ 1.5 → +15 pts
```

### 6.3 Signal 3: TVL Stability (0–20 pts)

```
If TVL > $10M  → +20 pts (very deep liquidity)
If TVL > $5M   → +18 pts
If TVL > $2M   → +16 pts
If TVL > $1M   → +14 pts
If TVL > $500K → +12 pts
If TVL > $200K → +10 pts
Else           → +5 pts
```

**Why it's effective:** TVL drain + volume = panic. Stable TVL + volume = accumulation.

### 6.4 Signal 4: Holder Distribution (0–15 pts)

```
growth = (holders_now - holders_7d_ago) / holders_7d_ago * 100

If growth ≥ 15% → +15 pts (exceptional growth)
If growth ≥ 10% → +13 pts
If growth ≥ 8%  → +12 pts
If growth ≥ 5%  → +10 pts
If growth ≥ 3%  → +8 pts
If growth > 0%  → +6 pts
```

### 6.5 Signal 5: TVL Confidence (0–10 pts)

```
If TVL > $50M  → +10 pts (institutional depth)
If TVL > $20M  → +9 pts
If TVL > $10M  → +8 pts
...
```

### 6.6 Advanced Signals

#### Whale Accumulation Detector (0–40 pts)
```
For each holder in top-25:
- New holder with balance ≥ 2%   → +20 pts/whale
- Holder with balance ≥ 5% & increasing → +15 pts/whale
(max 40 pts)
```

#### Anomaly Detection via Z-Score (0–27 pts)
```
z_score = (current_vol - avg_vol) / std_dev

z > 3.0 → +12 pts (extreme anomaly)
z > 2.5 → +10 pts
z > 2.0 → +8 pts

IF price_compression < 5% AND z > 1.5 → +15 bonus pts
```

#### Historical Pattern Match (0–8 pts)
Compared against 3 historical patterns:
- **"Silent Bludge"**: 3–7 days before 50x
- **"Slow Burn"**: 7–14 days before 20x
- **"Pump &..."**: 24–48 hours before 100x+

### 6.7 Dynamic Weighting by Market Phase

| Market Phase | Main Weights |
|---|---|
| Bull (price > +5%) | Vol/Price Divergence 35%, Momentum 25% |
| Consolidation (-5% to +5%) | TVL Stability 30%, Vol Divergence 25% |
| Bear (price < -5%) | Holder Distribution 30%, Vol Divergence 20% |

### 6.8 Risk Adjustment

| Risk Score | Multiplier |
|---|---|
| 0–30 (Low) | ×0.92 |
| 31–60 (Medium) | ×0.84 |
| 61–85 (High) | ×0.70 |
| 86–100 (Extreme) | ×0.60 |

### 6.9 Score Interpretation

| Score | Signal | Alert Level | Action |
|---|---|---|---|
| 75–100 | 🔴 **Strong Accumulation** | RED | High conviction pre-movement signal |
| 55–74 | 🟠 **Moderate Signal** | ORANGE | Monitor closely, confirm in 15–30 mins |
| 35–54 | 🟡 **Weak Signal** | YELLOW | Background monitor, not yet actionable |
| 0–34 | 🟢 **No Signal** | GREEN | Normal activity |

---

## 7. Backend API Server

**File:** `api_server.py`
**Framework:** FastAPI + Uvicorn
**Default Port:** `8000`
**Interactive Docs:** http://localhost:8000/docs

### 7.1 Main Endpoints

#### Health & Info
```
GET /api/health         → {"status": "ok"}
GET /api/chains         → {"chains": ["solana", "ethereum", ...]}
```

#### Token Analysis
```
GET /api/analyze?token=SOL&chain=solana
```
**Response:**
```json
{
  "token": "SOL",
  "chain": "solana",
  "address": "So111...",
  "price": 145.23,
  "price_change_24h": 2.3,
  "tvl": 1234567.89,
  "holders": 45000,
  "market_cap": 67000000000,
  "risk_score": 25,
  "score": {
    "total": 72,
    "risk_adjusted": 60,
    "confidence": 85,
    "alert_level": "orange",
    "market_phase": "consolidation"
  },
  "signals": {
    "volume_divergence": 20,
    "volume_momentum": 15,
    "tvl_stability": 18,
    "holder_distribution": 8,
    "tvl_confidence": 9,
    "whale_score": 2,
    "anomaly_score": 0,
    "pattern_match": 0
  },
  "whales": [...],
  "scam_warning": null
}
```

#### Sweep Scan
```
GET /api/sweep?category=trending&chain=solana&top=5
```

#### Live Prices (Multi-Token)
```
GET /api/prices/live?tokens=sol,jup,bonk&chain=solana
```

#### Category-Network Trend Matrix
```
GET /api/trends/category-network?categories=trending,meme&chains=solana,base&top=5
```

#### Klines / Chart Data
```
GET /api/klines?token=SOL&chain=solana&interval=60&limit=100
GET /api/chart?token=SOL&chain=solana&days=7
```

#### Ave Proxy Endpoints
```
GET /api/ave/token/{ca}?chain=solana
GET /api/ave/tokens?chain=solana&limit=50
GET /api/ave/whales/{ca}?chain=solana
GET /api/ave/holders/{ca}?chain=solana
```

#### Alert Management
```
POST   /api/alerts/create
GET    /api/alerts/user/{user_id}
GET    /api/alerts/token/{token}
DELETE /api/alerts/{alert_id}
PUT    /api/alerts/{alert_id}/toggle
GET    /api/alerts/stats
```

#### Telegram Integration (Deep Link)
```
GET  /api/telegram/config
POST /api/telegram/test
POST /api/telegram/deeplink/generate
POST /api/telegram/deeplink/claim
GET  /api/telegram/deeplink/status/{code}
```

#### Live Feed WebSocket
```
WS /api/live-feed       → Real-time BUY/SELL transactions streaming
```

### 7.2 Fake Token Detection

The API server features a fake/scam token protection layer:

```python
MIN_TVL = 100_000      # $100K minimum TVL
MIN_MARKETCAP = 1_000_000  # $1M minimum market cap

# Multi-flag checking:
flags = []
if tvl < 1_000:       flags.append(f"TVL only ${tvl:.2f}")
if holders < 50:       flags.append(f"only {holders} holders")
if price == 0.0:       flags.append("price is $0.00")

if len(flags) >= 2:
    # HIGH severity — highly likely a fake token
    result["scam_warning"] = {"severity": "high", ...}
elif len(flags) == 1:
    # CAUTION — requires re-verification
    result["scam_warning"] = {"severity": "caution", ...}
```

### 7.3 Token Resolution Logic

When a token is input as a symbol (not an address), the system will:
1. Search via `/v2/tokens?keyword={input}`
2. Select the one with the highest rank (exact match > TVL > market cap)
3. Penalize tokens with exact symbol matches but zero TVL/holders (likely fake)
4. If it fails, fallback to Ave API v1/v3

---

## 8. Live Buy/Sell Feed (WebSocket)

**File:** `ave_live_buysell_feed.py`

This module provides a real-time WebSocket connection to Ave Cloud for direct streaming of swap transactions.

### 8.1 Main Class: `AveLiveBuySellFeed`

```python
feed = AveLiveBuySellFeed(
    tracked_tokens=[
        {
            "symbol": "WIF",
            "token_address": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
            "chain": "solana"
        }
    ],
    ws_url="wss://wss.ave-api.xyz",
    api_key="your-ave-api-key",
    max_rows=150
)

# Stream with a callback
await feed.connect_and_stream(on_row=my_handler, should_stop=lambda: False)
```

### 8.2 Output Row Format

```json
{
  "wallet": "ABC123...XYZ",
  "side": "BUY",
  "symbol": "WIF",
  "usd": 1234.56,
  "chain": "solana",
  "amm": "raydium",
  "time": 1713000000,
  "txHash": "abc...",
  "swapLabel": "USDC -> WIF",
  "tokenAddress": "EKpQ..."
}
```

### 8.3 Filter Modes

| Mode | Description |
|------|-------------|
| `all` | All transactions |
| `usd1` | Only transactions > $1 |
| `usd10` | Only transactions > $10 |
| `buy` | Only BUY transactions |
| `sell` | Only SELL transactions |

### 8.4 CLI Usage

```bash
python ave_live_buysell_feed.py \
  --tokens "WIF:EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm:solana" \
  --filter buy \
  --chain-filter solana \
  --duration 120 \
  --max-events 50
```

### 8.5 Default Token Pool

The feed is equipped with a default token pool spanning 4 chains:

- **Solana:** WIF, TRUMP, JUP, BONK
- **Ethereum:** WETH, USDC, UNI, PEPE
- **BSC:** WBNB, USDT, CAKE, XVS
- **Base:** WETH, USDC, cbBTC, DAI

---

## 9. Alerts Manager

**File:** `alerts_manager.py`

The alert system responsible for the creation, evaluation, and delivery of notifications.

### 9.1 Alert Structure

```python
@dataclass
class Alert:
    id: str              # Format: {user_id}_{token}_{chain}_{type}_{timestamp}
    user_id: int         # Telegram chat ID
    token: str           # Symbol or contract address
    chain: str           # Chain name
    alert_type: str      # price | risk | volume | whale | trend
    condition: str       # above | below | change
    threshold: float     # Threshold value
    enabled: bool        # Active/inactive status
    created_at: str      # ISO timestamp
    last_triggered: str  # ISO timestamp of last trigger
    notify_telegram: bool
    notify_web: bool
```

### 9.2 Alert Types

| Type | Description | Example |
|------|-------------|---------|
| `price` | Token price alert | SOL above $150 |
| `risk` | Ave risk score alert | Risk score below 30 |
| `volume` | Volume spike vs average | Volume is 3x the usual amount |
| `whale` | Whale movements | New whale enters |
| `trend` | Market trend changes | Trend shifts from bear to bull |

### 9.3 Evaluation Conditions

```python
alerts_manager.evaluate_price_alert(token, chain, current_price)
alerts_manager.evaluate_risk_alert(token, chain, risk_score)
alerts_manager.evaluate_volume_alert(token, chain, vol_24h, avg_vol)
```

### 9.4 Persistent Storage

Alerts are saved in `alerts.json` and are reloaded every time the process restarts or changes are made by other processes. The use of `threading.Lock()` ensures atomic operations.

---

## 10. Telegram Bot (Advanced)

**File:** `telegram_bot_advanced.py`

A fully-featured Telegram bot with support for watchlists, alert management, and deep-link logins.

### 10.1 Command List

| Command | Description | Example |
|---------|-------------|---------|
| `/start` | Start the bot & welcome message | `/start` |
| `/help` | Show the command guide | `/help` |
| `/analyze TOKEN CHAIN` | In-depth analysis of a single token | `/analyze SOL solana` |
| `/ave TOKEN [CHAIN]` | Quick analyze (alias) | `/ave BONK solana` |
| `/sweep [CAT] [CHAIN] [N]` | Market sweep scan | `/sweep meme solana 5` |
| `/avesweep [CAT] [CHAIN] [N]` | Sweep alias | `/avesweep trending base 3` |
| `/alert create TOKEN CHAIN TYPE COND VAL` | Create a new alert | `/alert create SOL solana price above 150` |
| `/alert list` | View all active alerts | `/alert list` |
| `/alert delete ID` | Delete an alert | `/alert delete abc123_...` |
| `/alert toggle ID` | Enable/disable an alert | `/alert toggle abc123_...` |
| `/watchlist add TOKEN CHAIN` | Add to watchlist | `/watchlist add JUP solana` |
| `/watchlist list` | Display the watchlist | `/watchlist list` |
| `/watchlist remove TOKEN` | Remove from watchlist | `/watchlist remove JUP` |
| `/status` | User monitoring status | `/status` |
| `/chains` | List supported chains | `/chains` |

### 10.2 `/ave` Subcommands

The `/ave` command supports several additional subcommands:
- `/ave watch TOKEN CHAIN` → Add to watchlist
- `/ave unwatch TOKEN` → Remove from watchlist
- `/ave list` → Display the watchlist

### 10.3 Deep Link Login (Web ↔ Bot)

System connection between the web dashboard and Telegram:

1. **Web generates link:** `POST /api/telegram/deeplink/generate` → 6-digit code, valid for 10 minutes
2. **User clicks link:** `https://t.me/{botname}?start=connect_{code}`
3. **Bot claims:** `claim_deeplink_login(chat_id, code)` → `POST /api/telegram/deeplink/claim`
4. **Backend confirmation:** Session stored, web polls `/api/telegram/deeplink/status/{code}`

### 10.4 Token Analysis Output Format

```
📊 *SOL* (solana)
Price: `$145.230000` | 24h: +2.3%
TVL: `$1.23M` | Holders: 45,000

*Score: 72/100* 🟠
Risk-Adjusted: 60/100
Confidence: 85%
Phase: CONSOLIDATION

*Signals:*
⚡ Vol Divergence: 20/30
📈 Vol Momentum: 15/25
🏦 TVL Stability: 18/20
👥 Holders: 8/15
💎 Whale: 11/40

*Top Whales:*
  • ABC123...XYZ: `5.23%`
```

### 10.5 Background Monitoring Worker

The bot runs a worker loop every 5 minutes that will:
1. Reload recent alerts from `alerts.json`
2. Evaluate all active alerts against the latest price & risk data
3. Send Telegram notifications if conditions are met

---

## 11. Frontend Dashboard (React + Vite)

**Directory:** `frontend/`
**Stack:** React 18, Vite, Vanilla CSS

### 11.1 Pages / Sections

#### LandingScreen (`LandingScreen.jsx`)
The initial page displayed when a user hasn't connected to Telegram. Features:
- Ave Accumulation Monitor branding and animations
- "Connect Telegram" button highlighting the deep-link flow
- Platform feature descriptions

#### Platform Dashboard (`App.jsx`)
The application root that manages all states and routing between sections:
- **DashboardSection** — sweep scans & token analyzer
- **WhaleFeedSection** — real-time live whale transactions
- **SignalEngineSection** — Accumulation Score Engine visualization
- **RiskMatrixSection** — multi-chain & multi-category risk matrix

#### DashboardSection (`sections/DashboardSection.jsx`)
Main features:
- Single token analysis form (symbol or CA input)
- Sweep scan results table with sorting & filtering
- Sparkline charts per token
- Fake token warning overlay
- Results pagination

#### WhaleFeedSection (`sections/WhaleFeedSection.jsx`)
- Live BUY/SELL transaction streams via WebSocket API
- Color coding: 🟢 BUY / 🔴 SELL
- Direct explorer links (Etherscan, Solscan, etc.)
- Ave Pro & Bubblemaps links

#### TradingViewChart (`TradingViewChart.jsx`)
- Interactive candlestick charts based on Lightweight Charts
- Support: candlestick, line, area
- Indicator overlays: MA, EMA
- Kline data pulled directly from the Ave API

### 11.2 Utility: `utils/monitoring.js`

```javascript
formatMoney(value)                    // Format number to $X.XXM
scoreTone(score)                      // Returns CSS color class based on score
getRiskTier(score)                    // high | elevated | watch | low
shortAddress(value)                   // "ABC123...XYZ" (truncate address)
getAddressExplorerUrl(chain, address) // Explorer URL by chain
getAveProUrl(address, chain)          // Ave Pro token page URL
getBubbleMapUrl(address, chain)       // Bubblemaps visualization URL
getLinkAddress(address, chain)        // Resolves native tokens to wrapped equivalents
normalizeKlinePoints(points)          // OHLCV data normalization
resolveTokenInput(token, chain)       // Resolves token aliases → canonical IDs
```

### 11.3 Native Token Resolution

```javascript
// Native token placeholder → wrapped address mapping
// Solana SOL placeholder → WSOL
'solana:So11111111111111111111111111111111111111111' → 'So11111111111111111111111111111111111111112'

// Ethereum native ETH placeholder → WETH
'ethereum:0xeeee...eeee' → '0xC02aaA39b223FE8D0A0E5C4F27eAD9083C756Cc2'

// And so on for BSC, Base, Arbitrum, Optimism, Polygon, Avalanche
```

This resolution ensures that links to Bubblemaps and Ave Pro always direct to look-up-able tokens.

---

## 12. Setup & Installation

### 12.1 Prerequisites

- Python 3.10+
- Node.js 18+
- AVE API Key (register at https://cloud.ave.ai/register)
- Telegram Bot Token (optional, for the bot & notifications)

### 12.2 Clone & Install

```bash
# 1. Clone the repository
git clone https://github.com/username/ave-accumulation-monitor.git
cd ave-accumulation-monitor

# 2. Install Python dependencies
pip install -r requirements-chart.txt
pip install fastapi uvicorn pydantic websockets

# 3. Install frontend dependencies
cd frontend
npm install
cd ..
```

### 12.3 Environment Configuration

Create a `.env` file in the project root:

```env
# Required
AVE_API_KEY=your_ave_api_key_from_cloud_ave_ai

# Optional (for Telegram bot & alerts)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# Optional (default: http://localhost:8000)
API_BASE_URL=http://localhost:8000

# Optional (default: http://localhost:5173)
WEB_APP_URL=https://your-deployed-frontend.vercel.app
```

For the frontend, create `frontend/.env.local`:

```env
VITE_API_BASE=http://localhost:8000
```

---

## 13. How to Run

### Option A: Startup Script (Recommended)

**Windows PowerShell:**
```powershell
.\startup.ps1
```

**Linux/macOS:**
```bash
bash startup.sh
```

### Option B: Manual (3 Terminals)

**Terminal 1 — Backend API:**
```bash
python -m uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 — Telegram Bot:**
```bash
python telegram_bot_advanced.py
```

**Terminal 3 — Frontend:**
```bash
cd frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

### CLI Usage (Without Server)

**Single token analysis:**
```bash
python scripts/ave_monitor.py --mode single --token SOL --chain solana
python scripts/ave_monitor.py --mode single --token PEPE --chain ethereum --json
```

**Sweep scan:**
```bash
python scripts/ave_monitor.py --mode sweep --category trending --chain solana --top 5
python scripts/ave_monitor.py --mode sweep --category meme --chain base --top 10
```

**Live buy/sell feed:**
```bash
python ave_live_buysell_feed.py \
  --tokens "WIF:EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm:solana,JUP:JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN:solana" \
  --filter buy \
  --duration 300
```

---

## 14. API Endpoint Reference

### Complete List

```
GET  /api/health
GET  /api/chains

GET  /api/analyze?token=&chain=
GET  /api/sweep?category=&chain=&top=
GET  /api/prices/live?tokens=&chain=
GET  /api/trends/category-network?categories=&chains=&top=

GET  /api/klines?token=&chain=&interval=&limit=
GET  /api/chart?token=&chain=&days=

GET  /api/ave/token/{ca}?chain=
GET  /api/ave/tokens?chain=&limit=
GET  /api/ave/whales/{ca}?chain=
GET  /api/ave/holders/{ca}?chain=

POST   /api/alerts/create
GET    /api/alerts/user/{user_id}
GET    /api/alerts/token/{token}?chain=
DELETE /api/alerts/{alert_id}
PUT    /api/alerts/{alert_id}/toggle
GET    /api/alerts/stats

GET  /api/telegram/config
POST /api/telegram/test
POST /api/telegram/deeplink/generate
POST /api/telegram/deeplink/claim
GET  /api/telegram/deeplink/status/{code}
GET  /api/telegram/deeplink/pending

WS   /api/live-feed
```

### Rate Limiting Notes

- Ave.ai free tier: standard rate limits apply
- Sweep scan ~20 tokens: ~600 CU
- Single token analysis: ~30 CU
- Built-in delay: 0.3 seconds between API calls

---

## 15. Environment Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AVE_API_KEY` | ✅ | — | API key from cloud.ave.ai |
| `TELEGRAM_BOT_TOKEN` | ❌ | — | Bot token from @BotFather |
| `API_BASE_URL` | ❌ | `http://localhost:8000` | Backend API URL |
| `WEB_APP_URL` | ❌ | `http://localhost:5173` | Frontend app URL |
| `AVE_COOKIE` | ❌ | — | Authentication cookie for Ave API v1 |
| `VITE_API_BASE` | ❌ | `http://localhost:8000` | Backend URL configured for the frontend |

---

## 16. Security & Fake Token Detection

### 16.1 Fake Token Guard

The system implements two layers of protection against fake/scam tokens:

**Layer 1: Pre-filter in the Accumulation Score Engine**
```python
MIN_TVL        = 100_000   # $100K
MIN_MARKETCAP  = 1_000_000 # $1M
native_tokens  = {"ETH", "SOL", "BNB", "MATIC", "AVAX", "ARB", "OP"}

if not is_native:
    if tvl < MIN_TVL or market_cap < MIN_MARKETCAP:
        raise HTTPException(400, "Token is likely fake")
```

**Layer 2: Post-analysis scam warning**
```python
# Check 3 flags:
if tvl < 1_000:    flags.append("TVL only $X")
if holders < 50:   flags.append("only N holders")
if price == 0.0:   flags.append("price is $0.00")

# Severity:
# ≥2 flags → severity: "high"  (highly likely to be fake)
# 1 flag   → severity: "caution" (requires verification)
```

### 16.2 Smart Token Ranking

When token resolution finds multiple candidates with the exact same symbol:
1. Rank by match quality (exact address > exact symbol > partial)
2. Penalize symbols that match exactly but have TVL < $1 and holders < 5
3. Select the best match based on the largest TVL, then largest market cap

### 16.3 Risk Gate Warning

```
If risk_score ≥ 85 from Ave.ai:
→ Warning header is appended to all output

⚠️ HIGH RISK TOKEN — Ave risk score: 90/100
   Accumulation signal detected but exercise extreme caution.
```

---

## 17. Disclaimer

> This platform was built for **research and monitoring purposes** only.
>
> - **NOT** trading or investment advice
> - **DOES NOT** guarantee future price movements
> - **DOES NOT** replace in-depth analysis and DYOR (*Do Your Own Research*)
> - Always utilize official contract addresses from verified sources (CoinGecko, CoinMarketCap)
>
> Users must comply with Ave.ai's Terms of Service and applicable regulations in their respective jurisdictions.

---

## References

- Ave.ai API Docs: https://ave-cloud.gitbook.io/data-api
- API Base URL: https://prod.ave-api.com
- API Registration: https://cloud.ave.ai/register
- Ave Pro: https://pro.ave.ai
- Bubblemaps: https://v2.bubblemaps.io

---

*This document was generated for the Ave Accumulation Monitor — Ave.ai Hackathon 2026*
