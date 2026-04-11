# 🎯 Advanced Monitoring System - QUICK START

## What's Built

✅ **Complete Telegram + Web Integration** for token monitoring alerts

- **Web Dashboard**: Create & manage alerts with TradingView-style charts
- **Telegram Bot**: Control monitoring via commands, get real-time alerts
- **Alert Engine**: Background worker evaluates conditions every 5 minutes
- **5 Alert Types**: Price, Risk, Volume, Whale, Trend monitoring

---

## 🚀 Run Everything (Choose One)

### **Windows (PowerShell)**

```powershell
# Set environment variables first
$ENV:TELEGRAM_BOT_TOKEN = "your_bot_token"
$ENV:AVE_API_KEY = "your_api_key"

# Run startup
.\startup.ps1
```

### **Linux/Mac (Bash)**

```bash
export TELEGRAM_BOT_TOKEN="your_bot_token"
export AVE_API_KEY="your_api_key"

bash startup.sh
```

### **Manual (3 Terminals)**

**Terminal 1 - Backend API**

```bash
python -m uvicorn api_server:app --host 0.0.0.0 --port 8000
```

**Terminal 2 - Telegram Bot**

```bash
python telegram_bot_advanced.py
```

**Terminal 3 - Frontend**

```bash
cd frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

---

## 📱 Access Points

| Service           | URL                        | Purpose                           |
| ----------------- | -------------------------- | --------------------------------- |
| **Web Dashboard** | http://localhost:5173      | Create/manage alerts, view charts |
| **API Docs**      | http://localhost:8000/docs | Test endpoints interactively      |
| **Telegram Bot**  | @YourBotName               | Commands & notifications          |

---

## ⚙️ Configuration

### Environment Variables (Required)

```bash
TELEGRAM_BOT_TOKEN=xxxxxxxxxxxx:xxxxxxxxxxx
AVE_API_KEY=your_ave_api_key_here
API_BASE_URL=http://localhost:8000  # Optional, defaults to localhost:8000
```

### Alert Storage

- **File**: `alerts.json` in project root
- **Auto-created** on first alert
- **Persists** across restarts
- **Backed by**: Thread-safe file I/O

---

## 📊 Example Workflow

### Step 1: Open Web Dashboard

Go to http://localhost:5173

### Step 2: Analyze Token

1. Enter token: `SOL`
2. Select chain: `solana`
3. Click "Analyze Now"
4. See risk score, signals, whale data

### Step 3: Create Alert

In the alerts panel (after analyzing):

1. Select alert type: `price`
2. Select condition: `above`
3. Enter threshold: `150`
4. Click "Create Alert"
5. See in "Active" tab

### Step 4: Get Telegram Notification

When condition is met:

- Bot sends: "💰 ALERT TRIGGERED: SOL price $155 > threshold $150"
- You can manage via: `/alert list`, `/alert toggle`, `/alert delete`

---

## 🎮 Telegram Commands

### Analysis

```
/analyze SOL solana           → Full token analysis
/sweep trending               → Top trending tokens
/sweep meme solana 5          → Top 5 meme tokens on Solana
```

### Alerts

```
/alert create SOL solana price above 150
/alert list                   → Show your alerts
/alert delete {alert-id}      → Delete alert
/alert toggle {alert-id}      → Enable/disable alert
```

### Watchlist

```
/watchlist add SOL solana     → Add to watchlist
/watchlist list               → Show watchlist
/watchlist remove SOL         → Remove from watchlist
```

### Info

```
/start    → Welcome message
/help     → All commands
/status   → Monitoring stats
```

---

## 🎨 Alert Types Explained

### 💰 Price Alert

"Alert me when SOL > $150"

```
Type: price | Condition: above | Threshold: 150
```

### ⚠️ Risk Alert

"Alert me when risk < 50"

```
Type: risk | Condition: below | Threshold: 50
```

### 📊 Volume Alert

"Alert me when volume > 3x normal"

```
Type: volume | Condition: above | Threshold: 3.0
```

### 🐋 Whale Alert

"Alert me on whale movement"

```
Type: whale | Condition: above | Threshold: 10
```

### 📈 Trend Alert

"Alert me on trend changes 15%+"

```
Type: trend | Condition: change | Threshold: 15
```

---

## 🔄 How It Works

```
USER CREATES ALERT
       ↓
[Web Dashboard] → POST /api/alerts/create
       ↓
[FastAPI Server] → Save to alerts.json
       ↓
[Background Worker] → Evaluates every 5 min
       ↓
CONDITION MET?
       ├→ YES → Send Telegram message
       └→ NO → Wait for next check
```

---

## 📡 API Endpoints

### Alert Management

```
POST   /api/alerts/create           Create new alert
GET    /api/alerts/user/{user_id}   List user alerts
GET    /api/alerts/token/{token}    List token alerts
DELETE /api/alerts/{alert_id}       Delete alert
PUT    /api/alerts/{alert_id}/toggle Enable/disable alert
GET    /api/alerts/stats            Global statistics
```

### Token Analysis

```
GET    /api/analyze?token=SOL&chain=solana  Detailed analysis
GET    /api/sweep?category=trending&top=6   Token sweep
GET    /api/chart?token=SOL&days=30         OHLC candlestick data
```

---

## 🧪 Testing Commands

### Test Alert Creation (cURL)

```bash
curl -X POST http://localhost:8000/api/alerts/create \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "token": "SOL",
    "chain": "solana",
    "alert_type": "price",
    "condition": "above",
    "threshold": 150.0
  }'
```

### Test Alert Listing

```bash
curl http://localhost:8000/api/alerts/user/1
```

### Test Stats

```bash
curl http://localhost:8000/api/alerts/stats
```

---

## ⚠️ Troubleshooting

### Telegram Bot Not Responding

- Check TOKEN is set: `echo $TELEGRAM_BOT_TOKEN`
- Try /start command in bot chat
- Check for errors in terminal

### Alerts Not Creating

- Verify backend is running on port 8000
- Check browser console (F12) for errors
- Ensure token/chain are valid

### Chart Not Loading

- Try different timeframe (7D vs 30D)
- Check token exists on chain
- Verify Ave API key is valid

### File Permission Issues

- Check `alerts.json` is writable
- Run with sudo if needed: `sudo python api_server.py`

---

## 📁 File Manifest

| File                       | Purpose                          |
| -------------------------- | -------------------------------- |
| `alerts_manager.py`        | Alert engine & evaluation        |
| `telegram_bot_advanced.py` | Telegram bot with commands       |
| `api_server.py`            | FastAPI backend + endpoints      |
| `frontend/src/App.jsx`     | React app with alerts UI         |
| `frontend/src/styles.css`  | Alert styling                    |
| `alerts.json`              | Alert persistence (auto-created) |
| `MONITORING_GUIDE.md`      | Complete documentation           |
| `startup.ps1`              | Windows startup script           |
| `startup.sh`               | Linux/Mac startup script         |

---

## 🎯 Next Steps

1. **Set Bot Token**: Get from @BotFather on Telegram
2. **Set API Key**: Get from Ave dashboard
3. **Run Services**: Use startup script or manual terminals
4. **Create Alert**: Use web dashboard or Telegram
5. **Monitor**: Check Telegram for notifications

---

## 🔐 Security Notes

- Token stored in environment variables
- API key never exposed to frontend
- Telegram chat IDs validated before sending
- Alert data persisted locally
- Consider adding authentication later

---

## 📈 Production Checklist

- [ ] Use PostgreSQL instead of JSON
- [ ] Implement user authentication
- [ ] Add WebSocket for real-time updates
- [ ] Set up alert history/audit log
- [ ] Add email notifications
- [ ] Deploy to cloud (AWS/GCP/Azure)
- [ ] Set up SSL/HTTPS
- [ ] Add rate limiting
- [ ] Implement backtesting
- [ ] Set up monitoring/logging

---

**🚀 You're all set! Start with the web dashboard or Telegram bot.**

For detailed guides, see `MONITORING_GUIDE.md`
