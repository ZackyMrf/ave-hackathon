# 🚀 Advanced Monitoring System - Integration Guide

**Ave Claw Hackathon Project**  
Integrated Telegram Bot + Web Dashboard with Real-Time Alert Management

---

## 📋 System Overview

The advanced monitoring system connects:

1. **Web Dashboard** (React + Vite) - Visual monitoring and alert configuration
2. **FastAPI Backend** - Monitoring logic and alert management
3. **Telegram Bot** - Real-time notifications and command interface
4. **Alert Engine** - Background worker for continuous monitoring

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     WEB CLIENT (React)                      │
│  • Chart visualization (TradingView-style candlesticks)     │
│  • Alert configuration UI                                   │
│  • Real-time monitoring stats                              │
└──────────────────┬──────────────────────────────────────────┘
                   │ REST API (JSON)
┌──────────────────▼──────────────────────────────────────────┐
│         FastAPI BACKEND (api_server.py)                      │
│  • /api/analyze - Token analysis                             │
│  • /api/sweep - Market token sweep                           │
│  • /api/chart - OHLC candlestick data                        │
│  • /api/alerts/* - Alert management endpoints               │
└──────────────────┬──────────────────────────────────────────┘
                   │
       ┌───────────┴─────────────────┐
       │                             │
┌──────▼──────────────┐  ┌───────────▼──────────────┐
│  Alerts Manager     │  │  Telegram Bot Worker     │
│ (alerts_manager.py) │  │ (telegram_bot_advanced)  │
│                     │  │                          │
│ • Alert CRUD        │  │ • Command handler        │
│ • Evaluation logic  │  │ • Message formatting     │
│ • Persistence       │  │ • Watchlist management   │
└─────────┬───────────┘  └──────────────────────────┘
          │
     [alerts.json] ────► Telegram API
```

---

## 🔧 Setup & Installation

### Backend Setup

1. **Install Dependencies**

   ```bash
   pip install fastapi uvicorn requests python-dotenv
   ```

2. **Set Environment Variables**

   ```bash
   export TELEGRAM_BOT_TOKEN="your_telegram_token"
   export AVE_API_KEY="your_ave_api_key"
   export API_BASE_URL="http://localhost:8000"
   ```

3. **Start FastAPI Server**
   ```bash
   python -m uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
   ```

### Telegram Bot Setup

1. **Create Bot with @BotFather**
   - Message @BotFather on Telegram
   - Create new bot, get TOKEN

2. **Start Bot**
   ```bash
   python telegram_bot_advanced.py
   ```

### Frontend Setup

1. **Install Dependencies**

   ```bash
   cd frontend
   npm install
   ```

2. **Start Development Server**

   ```bash
   npm run dev -- --host 0.0.0.0 --port 5173
   ```

3. **Build for Production**
   ```bash
   npm run build
   ```

---

## 📊 Alert Types & Configuration

### 1. **Price Alerts** (💰)

Monitor token price movements with thresholds

**Example:**

```
Alert Type: price
Condition: above
Threshold: 150
→ Triggers when token price exceeds $150
```

**Telegram Command:**

```
/alert create SOL solana price above 150
```

### 2. **Risk Score Alerts** (⚠️)

Monitor risk-adjusted score changes

**Example:**

```
Alert Type: risk
Condition: below
Threshold: 50
→ Triggers when risk score drops below 50
```

**Telegram Command:**

```
/alert create PUMP solana risk below 50
```

### 3. **Volume Spike Detection** (📊)

Alert on unusual volume multipliers

**Example:**

```
Alert Type: volume
Condition: above
Threshold: 3.0
→ Triggers when 24h volume > 3x normal
```

### 4. **Whale Movement Alerts** (🐋)

Monitor large holder position changes

**Example:**

```
Alert Type: whale
Condition: above
Threshold: 10
→ Triggers on significant whale position changes
```

### 5. **Trend Change Alerts** (📈)

Alert on market phase transitions

**Example:**

```
Alert Type: trend
Condition: change
Threshold: 15
→ Triggers on 15%+ trend shift
```

---

## 🤖 Telegram Bot Commands

### Information Commands

```
/start       - Show welcome message and bot capabilities
/help        - Display all available commands
/status      - Show portfolio and monitoring stats
```

### Token Analysis

```
/analyze SOL solana          - Get detailed token analysis
/sweep trending              - Scan top trending tokens
/sweep meme solana 10        - Scan top 10 meme tokens on Solana
```

**Valid categories:** trending, meme, defi, gaming, ai

### Alert Management

```
/alert create TOKEN CHAIN TYPE CONDITION THRESHOLD
  Example: /alert create JUP solana price above 1.50

/alert list      - Show all your active alerts
/alert delete ID - Delete specific alert
/alert toggle ID - Enable/disable alert
```

### Watchlist

```
/watchlist add TOKEN CHAIN      - Add token to watchlist
/watchlist list                 - Show your watchlist
/watchlist remove TOKEN         - Remove from watchlist
```

---

## 🎯 Web Dashboard Features

### 1. Single Token Probe

- Input token name and chain
- Instant risk score calculation
- Detailed signal breakdown
- Price, TVL, and holder metrics

### 2. Market Sweep

- Category-based token scanning (trending, meme, defi, gaming, ai)
- Top N results ranked by risk-adjusted score
- Touch to expand inline chart

### 3. TradingView-Style Charts

**Features:**

- Candlestick, line, and area chart types
- SMA20 and EMA20 technical indicators
- Volume bars with bullish/bearish coloring
- Timeframe switching (7D, 14D, 30D, 90D)
- Detailed hover tooltips (OHLCV values to 6 decimals)
- Cross-hair price tracking

### 4. Advanced Alerts Panel

- Create alerts directly for analyzed tokens
- Real-time alert list with toggle/delete
- Alert type selector (price, risk, volume, whale, trend)
- Condition selection (above, below, change %)
- Threshold input with live validation

### 5. Monitoring Statistics

- Total alerts count
- Active alerts counter
- Monitored tokens count
- Breakdown by alert type

---

## 📡 API Endpoints Reference

### Analysis Endpoints

```
GET /api/analyze?token=SOL&chain=solana
  Returns: Risk score, signals, whale data, price, TVL, holders

GET /api/sweep?category=trending&chain=solana&top=6
  Returns: List of top tokens by risk-adjusted score

GET /api/chart?token=SOL&chain=solana&days=30
  Returns: OHLC candlestick array (time, open, high, low, close, volume)
```

### Alert Endpoints

```
POST /api/alerts/create
  Body: {
    user_id: int,
    token: string,
    chain: string,
    alert_type: string,
    condition: string,
    threshold: float
  }
  Returns: Alert object with ID

GET /api/alerts/user/{user_id}
  Returns: Array of user's alerts with status

GET /api/alerts/token/{token}?chain=solana
  Returns: All alerts for token

GET /api/alerts/stats
  Returns: {
    total: int,
    enabled: int,
    monitored_tokens: int,
    by_type: { price:..., risk:..., volume:..., whale:..., trend:... }
  }

DELETE /api/alerts/{alert_id}
  Returns: { success: true }

PUT /api/alerts/{alert_id}/toggle
  Body: boolean (enabled state)
  Returns: { success: true, enabled: boolean }
```

---

## 💾 Data Storage

### alerts.json

Persistent storage for all alerts:

```json
[
  {
    "id": "1_SOL_solana_price_1712500000",
    "user_id": 1,
    "token": "SOL",
    "chain": "solana",
    "alert_type": "price",
    "condition": "above",
    "threshold": 150.0,
    "enabled": true,
    "created_at": "2026-04-07T12:34:56",
    "last_triggered": "2026-04-07T14:22:10",
    "notify_telegram": true,
    "notify_web": true
  }
]
```

---

## 🔄 Monitoring Workflow

### 1. User Creates Alert (Web)

```
User fills alert form → Creates alert via /api/alerts/create → Alert saved to alerts.json
```

### 2. Background Worker Evaluates

```
Every 5 minutes:
  → Fetch all enabled alerts
  → Get current token price/risk from Ave API
  → Compare against alert conditions
  → If triggered: Send Telegram notification + save timestamp
```

### 3. Telegram Notification

```
Alert triggered → Format message with token, type, current value
             → Send to user's Telegram inbox
             → User can manage alert via /alert commands
```

### 4. Web Dashboard Sync

```
User opens dashboard → Loads user's alerts
                  → Shows real-time alert list
                  → Can toggle/delete alerts
                  → Creates new alerts for current token
```

---

## 📈 Advanced Usage Scenarios

### Scenario 1: Track Emerging Token

```
1. Use /sweep meme to find emerging meme tokens
2. Click on interesting token in web dashboard to expand chart
3. Analyze risk score and signals
4. Create price alert (e.g., "Get alert if SOL > $200")
5. Create risk alert (e.g., "Get alert if risk score < 40")
6. Monitor in real-time via Telegram or dashboard
```

### Scenario 2: Whale Movement Alert

```
1. /analyze PUMP solana - Check holder distribution
2. Create whale alert for significant position changes
3. Telegram notifications when whales move
4. Dashboard shows whale top holders
```

### Scenario 3: Volume Spike Watchlist

```
1. Add 5 tokens to watchlist: /watchlist add TOKEN CHAIN
2. Create volume alerts (3x multiplier) for each
3. Get notified on Telegram when volume spikes
4. Use web dashboard to examine spike on chart
```

### Scenario 4: Risk Management

```
1. Create "safe" risk alerts (risk < 30)
2. Create "caution" alerts (risk > 70)
3. Dashboard stats show alert distribution
4. Proactively monitor portfolio tokens
```

---

## 🐛 Troubleshooting

### Issue: Alerts not triggering

**Solution:**

- Check worker is running (see terminal output)
- Verify Ave API key is valid
- Ensure alert thresholds are configured
- Check alerts.json file exists and is readable

### Issue: Telegram bot not responding

**Solution:**

- Verify TELEGRAM_BOT_TOKEN is set
- Check /start command in Telegram
- Review bot.log for error messages
- Ensure network connectivity

### Issue: Web dashboard not saving alerts

**Solution:**

- Verify backend API is running on port 8000
- Check browser console for network errors
- Ensure user_id is set correctly
- Check CORS middleware is enabled

### Issue: Chart data not loading

**Solution:**

- Verify token exists on chain
- Check Ave API connectivity
- Try different timeframe (7D vs 30D)
- Ensure days parameter is between 3-120

---

## 🔐 Security Considerations

1. **API Keys**: Store in environment, never in code
2. **User IDs**: Use actual user authentication (currently mocked)
3. **Rate Limiting**: Implement if many concurrent users
4. **Telegram**: Validate chat_id before sending messages
5. **Database**: Use proper database instead of JSON for production

---

## 📊 Performance Tips

1. **Alert Evaluation**: Adjust worker interval (currently 5 min)
2. **API Caching**: Cache Ave API responses to reduce calls
3. **WebSocket**: Use real-time updates instead of polling for large deployments
4. **Database**: Switch to PostgreSQL for scalability
5. **Monitoring**: Use APM tool to track performance

---

## 🎓 Learning Resources

- **FastAPI Docs**: https://fastapi.tiangolo.com
- **Telegram Bot API**: https://core.telegram.org/bots/api
- **Ave Bot Trade API**: https://docs-bot-api.ave.ai
- **React Hooks**: https://react.dev/reference/react/hooks
- **Chart.js**: https://www.chartjs.org (alternative to custom SVG)

---

## 📞 Support

For issues or features:

1. Check this guide first
2. Review logs (bot.log, console output)
3. Test endpoints with curl or Postman
4. Check environment variables
5. Verify all services are running

---

**Happy Monitoring! 🚀**  
Ave Claw Hackathon Project - Advanced Alert Integration
