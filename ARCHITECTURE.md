# SYSTEM ARCHITECTURE - Advanced Monitoring Integration

## High-Level System Diagram

```
┌────────────────────────────────────────────────────────────────────────┐
│                          USER INTERFACES                              │
├────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌──────────────────┐              ┌──────────────────┐               │
│   │  WEB DASHBOARD   │              │  TELEGRAM BOT    │               │
│   │   (React + Vite) │              │                  │               │
│   │                  │              │  Commands:       │               │
│   │ • Analyze Token  │              │  /analyze        │               │
│   │ • Create Alert   │              │  /sweep          │               │
│   │ • View Charts    │              │  /alert create   │               │
│   │ • Manage Alerts  │              │  /alert list     │               │
│   │ • Watchlist      │              │  /watchlist      │               │
│   └────────┬─────────┘              └────────┬─────────┘               │
│            │                                 │                         │
│            │ HTTP/REST                       │ Polling                 │
│            │ Port 5173                       │ Telegram API            │
│                                              │                         │
└────────────┼──────────────────────────────────┼───────────────────────┘
             │                                  │
             │           ┌────────────────────┬─┘
             │           │                    │
             ▼           ▼                    ▼
        ┌─────────────────────────────────────────┐
        │    FASTAPI BACKEND (api_server.py)     │
        │   Running on Port 8000                  │
        ├─────────────────────────────────────────┤
        │                                          │
        │  Core Endpoints:                         │
        │  • /api/health                          │
        │  • /api/analyze - Token analysis        │
        │  • /api/sweep - Category sweep          │
        │  • /api/chart - OHLC candlelines       │
        │                                          │
        │  Alert Endpoints:                        │
        │  • POST   /api/alerts/create            │
        │  • GET    /api/alerts/user/{id}         │
        │  • GET    /api/alerts/token/{token}    │
        │  • DELETE /api/alerts/{alert_id}       │
        │  • PUT    /api/alerts/{id}/toggle      │
        │  • GET    /api/alerts/stats            │
        │                                          │
        │  Dependencies:                           │
        │  • AveAccumulationMonitor (scripts/)    │
        │  • AlertsManager (alerts_manager.py)   │
        │                                          │
        └───────┬──────────────────────┬──────────┘
                │                      │
                │ Loads               │ Manages
                │                      │
                ▼                      ▼
        ┌──────────────────┐  ┌──────────────────┐
        │ alerts.json      │  │ AlertsManager    │
        │                  │  │                  │
        │ Stored Alerts:   │  │ • Load alerts    │
        │ [{               │  │ • Create alert   │
        │   id: string,    │  │ • Delete alert   │
        │   user_id: int,  │  │ • Evaluate       │
        │   token: string, │  │ • Send alerts    │
        │   type: string,  │  │                  │
        │   condition: str │  └──────────────────┘
        │   threshold: num │
        │   enabled: bool  │
        │   created_at: ts │
        │ }]               │
        └──────────────────┘
```

## Component Interaction Flow

```
SCENARIO: User creates price alert via web dashboard
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║  1. USER INPUT (Web Dashboard)                                   ║
║     └─> Token: SOL, Type: price, Condition: above, Value: 150  ║
║                          │                                       ║
║                          ▼                                       ║
║  2. SEND REQUEST                                                 ║
║     └─> POST /api/alerts/create                                 ║
║            Headers: Content-Type: application/json              ║
║            Body: { user_id: 1, token: SOL, ... }                ║
║                          │                                       ║
║                          ▼                                       ║
║  3. FASTAPI PROCESSES                                            ║
║     └─> Validate input with Pydantic models                      ║
║     └─> Call alerts_manager.create_alert()                      ║
║                          │                                       ║
║                          ▼                                       ║
║  4. ALERTS MANAGER SAVES                                         ║
║     └─> Create Alert object                                      ║
║     └─> Add to alerts.json (thread-safe)                         ║
║     └─> Return created alert to API                              ║
║                          │                                       ║
║                          ▼                                       ║
║  5. API RESPONSE                                                 ║
║     └─> { success: true, alert: { id: "1_SOL_...", ... } }     ║
║     └─> Returns to web dashboard                                ║
║                          │                                       ║
║                          ▼                                       ║
║  6. DASHBOARD UPDATES                                            ║
║     └─> Show alert in "Active" list                              ║
║     └─> Update stats (total alerts: 1)                           ║
║                          │                                       ║
║                          ▼                                       ║
║  7. BACKGROUND WORKER (Independent)                              ║
║     └─> Every 5 minutes:                                         ║
║         • Fetch all enabled alerts                               ║
║         • Get current SOL price from Ave API                     ║
║         • Check if price >= 150                                  ║
║         • If YES → Send Telegram notification                    ║
║         • Save timestamp to alerts.json                          ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
```

## Data Flow: Alert Evaluation

```
BACKGROUND WORKER (5-minute interval)
═════════════════════════════════════════╗
                                         │
┌─────────────────────────────────────────┘
│
├─→ Load all alerts from alerts.json
│
├─→ Filter: enabled=true only
│
├─→ For each alert:
│   ├─→ Fetch current data from Ave API
│   │   ├─ GET /v2/tokens/{token_id} → price
│   │   └─ GET /v2/analysis/{token} → risk_score
│   │
│   ├─→ Evaluate condition:
│   │   ├─ IF type="price" AND current >= threshold → TRIGGER
│   │   ├─ IF type="risk" AND current <= threshold → TRIGGER
│   │   ├─ IF type="volume" AND (vol/avg) > threshold → TRIGGER
│   │   └─ ... (other types)
│   │
│   ├─→ IF TRIGGERED:
│   │   ├─ Format Telegram message
│   │   ├─ POST to Telegram API
│   │   ├─ Update last_triggered timestamp
│   │   └─ Save to alerts.json
│   │
│   └─→ Continue to next alert
│
└─→ Wait 5 minutes, repeat
```

## File Dependencies

```
api_server.py (FastAPI Main)
  ├── imports: AlertsManager from alerts_manager.py
  ├── imports: AveAccumulationMonitor from scripts/ave_monitor.py
  ├── reads: alerts.json (for loading via AlertsManager)
  ├── creates: alerts.json (if not exists)
  └── serves: All HTTP endpoints

telegram_bot_advanced.py (Telegram Integration)
  ├── imports: AlertsManager from alerts_manager.py
  ├── imports: AveAccumulationMonitor from scripts/ave_monitor.py
  ├── reads: alerts.json (for listing user alerts)
  ├── writes: alerts.json (for creating/deleting alerts)
  ├── calls: api_server.py endpoints internally
  ├── polls: Telegram API for messages
  └── sends: Telegram API alerts

alerts_manager.py (Alert Engine)
  ├── maintains: in-memory alerts dictionary
  ├── reads: alerts.json on initialization
  ├── writes: alerts.json on every create/delete/update
  ├── thread-safe: Uses threading.Lock()
  └── callable: From both api_server.py and telegram_bot_advanced.py

frontend/src/App.jsx (React Dashboard)
  ├── imports: AdvancedMonitoring.jsx (alert components)
  ├── state: alerts[], alertsTab, alertsStats
  ├── calls: API endpoints (fetch)
  │   ├─ GET  /api/analyze
  │   ├─ GET  /api/sweep
  │   ├─ GET  /api/chart
  │   ├─ POST /api/alerts/create
  │   ├─ GET  /api/alerts/user/{id}
  │   ├─ GET  /api/alerts/token/{token}
  │   ├─ DELETE /api/alerts/{id}
  │   └─ PUT  /api/alerts/{id}/toggle
  └── renders: TradingChart + AlertsPanel components

frontend/src/styles.css
  ├── defines: .alerts-panel, .alert-form, .alerts-list
  ├── defines: .monitoring-stats, .stat-card
  └── responsive: Media queries at 1200px, 920px, 600px

scripts/ave_monitor.py
  └── Used by: api_server.py, telegram_bot_advanced.py
      └── Provides: Token analysis, whale data, signals
```

## Network Topology

```
┌─────────────────────────────────────┐
│  USER'S MACHINE                     │
│                                     │
│  ┌───────────────────────────────┐  │
│  │  Browser (Port 5173)          │  │
│  │  http://localhost:5173        │  │
│  └───────────────┬───────────────┘  │
│                  │                   │
│  ┌───────────────┼───────────────┐  │
│  │ API Server    │               │  │
│  │ (Port 8000)   ▼               │  │
│  │                               │  │
│  │  localhost:8000/api/*         │  │
│  │  localhost:8000/docs          │  │
│  │  localhost:8000/openapi.json  │  │
│  └───────────────┬───────────────┘  │
│                  │                   │
│  ┌───────────────┼───────────────┐  │
│  │ Telegram Bot  │               │  │
│  │ (Worker)      ▼               │  │
│  │                               │  │
│  │  Polls Telegram API           │  │
│  │  Sends notifications          │  │
│  └───────────────────────────────┘  │
│                  │                   │
└──────────────────┼───────────────────┘
                   │
        ┌──────────┼──────────┐
        │          │          │
        ▼          ▼          ▼
    Internet
        │
        ├─→ Telegram API (long-polling, sendMessage)
        ├─→ Ave Klines API (token data, analysis)
        └─→ (optional) External APIs
```

## Sequence Diagram: Create & Evaluate Alert

```
Timeline:
═════════════════════════════════════════════════════════════════════

T=0:00  User opens browser
        └─> Frontend loads, initializes state

T=0:15  User types "SOL" and clicks "Analyze Now"
        └─> API call:  GET /api/analyze?token=SOL&chain=solana
        └─> Backend:   returns risk score, signals, whales
        └─> Display:   Show report card

T=1:00  User clicks "Create Alert"
        └─> Modal/Form:  alert_type=price, condition=above, threshold=150
        └─> API call:   POST /api/alerts/create
        └─> Backend:    AlertsManager.create_alert() → alerts.json
        └─> Response:   { success: true, alert: {...} }
        └─> Frontend:   Add to alerts[], show in list, update stats

T=5:00  Background worker executes (scheduled)
        └─> Load all enabled alerts from alerts.json
        └─> For our alert: Fetch current SOL price
        └─> Check: $current_price >= $150?
        └─> IF YES:
            └─> Format message: "💰 SOL at $152 > $150 threshold"
            └─> POST to Telegram /sendMessage
            └─> Update alerts.json: last_triggered = now
            └─> Next check: T=10:00
        └─> IF NO:
            └─> Silently continue
            └─> Next check: T=10:00

T=10:00 (+ recurring)
        └─> Worker checks again (~5 min intervals)

T=∞     User can manage alert anytime:
        └─> /alert list (Telegram)
        └─> /alert toggle {id} (Toggle on/off)
        └─> /alert delete {id} (Remove)
        └─> Dashboard UI (same operations)
```

## Alert Lifecycle

```
           CREATE
            │
            ▼
    ┌──────────────────┐
    │   ACTIVE STATE   │
    │ enabled = true   │◀────┐
    │                  │     │
    └────────┬─────────┘     │toggle on
             │               │
      ┌──────┴──────┐        │
      │             │        │
      ▼             ▼        │
   EVALUATE    disable       │
    │          enabled=false │
    │             │          │
    │             └──────────┘
    │
    └─→ price >= threshold?
         │
         ├─→ YES → TRIGGER ALERT → send telegram
         │         update last_triggered
         │         (stays enabled)
         │
         └─→ NO → wait 5 min → check again


DELETE ALERT
    │
    └─→ Alert ID removed from alerts.json
        Telegram notifications stop
        Web dashboard removes from list
```

This architecture ensures:
✅ Separation of concerns (UI, API, Engine)
✅ Scalability (independent worker threads)
✅ Reliability (file persistence, error handling)
✅ User flexibility (toggle, delete, manage anytime)
✅ Real-time notifications (Telegram receives immediately)
