---
name: ave-accumulation-monitor
description: >
 Use this skill when the user wants to detect early token accumulation signals,
 monitor quiet smart money buying before price moves, scan for tokens with rising
 buy pressure but flat price, track divergence between volume and price action,
 or get pre-event alpha on tokens across Ave.ai's multi-chain data.

 Triggers on phrases like: "monitor this token", "is anyone accumulating X",
 "find tokens being quietly bought", "smart money signal", "pre-pump detection",
 "show me accumulation", "whale accumulation scan", "early signal on X",
 "is there buy pressure on X", "scan for stealth buys".

 This skill uses Ave.ai's native API (v2) as the data source. It does NOT
 simply re-surface price alerts — it detects accumulation *before* price moves,
 by reading volume/price divergence, buy/sell ratio imbalance, TVL stability,
 and holder growth patterns across multiple timeframes simultaneously.

compatibility: "Requires AVE_API_KEY environment variable. Ave.ai API v2 base URL: https://prod.ave-api.com"
---

# Ave Accumulation Monitor

An Ave.ai-native skill that detects **pre-movement accumulation signals** —
the quiet buying that smart money does *before* price reacts.

Most monitoring tools alert you when something already happened.
This skill finds signals before the crowd sees them.

---

## Quick Start

```bash
# Set API key
export AVE_API_KEY="your-api-key-from-ave-cloud"

# Mode A: Single token deep analysis
python scripts/ave_monitor.py --mode single --token TRUMP --chain solana

# Mode B: Sweep scan across category
python scripts/ave_monitor.py --mode sweep --category trending --chain solana --top 5
```

Get your API key: https://cloud.ave.ai/register

---

## Core Concept: The Accumulation Divergence Model

The key insight: **genuine accumulation leaves fingerprints before price moves.**

When smart money buys quietly, you see:
- Volume rising, price stays flat → buy pressure absorbed without dumps
- Buy volume outpacing sell volume at low 5m/1h timeframes
- TVL stable or rising → LP providers aren't running
- Holder count growing → distribution to new wallets
- Locked supply high → circulating supply constrained, squeeze incoming

When these signals appear together with flat or slightly positive price action,
that's the **accumulation window** — the moment before retail notices.

---

## API Integration (Ave.ai v2)

**Base URL:** `https://prod.ave-api.com`
**Auth Header:** `X-API-KEY: {AVE_API_KEY}`

### Endpoints Used by This Skill

#### 1. Token Search
```
GET /v2/tokens?keyword={symbol_or_address}&chain={chain}&limit=5
```
Use to resolve a token name/symbol to its contract address and chain.
Returns: `token`, `chain`, `current_price_usd`, `tvl`, `tx_volume_u_24h`,
`risk_score`, `holders`

#### 2. Token Detail
```
GET /v2/tokens/{token-id}
```
Returns detailed token info including pairs and metadata.

#### 3. Top Holders
```
GET /v2/tokens/top100/{token-id}
```
Returns top 100 holders for whale analysis.

#### 4. Price History (Klines)
```
GET /v2/klines/token/{token-id}?interval=1440&limit=30
```
Returns historical price and volume data for pattern detection.

#### 5. Trending/Ranks (Sweep Mode)
```
GET /v2/tokens/trending?chain={chain}&page_size=50
```
Returns trending tokens for sweep scan mode.

---

## Detection Logic

### Mode A: Single Token Monitor
*Triggered when user specifies a token/CA to watch.*

**Step 1: Resolve token**
→ Call `/v2/tokens?keyword={input}` to get `token` (CA) and `chain`

**Step 2: Fetch multi-timeframe data**
→ Call `/v2/tokens/{token-id}` for current snapshot
→ Call `/v2/klines/token/{token-id}` for historical baseline
→ Call `/v2/tokens/top100/{token-id}` for whale data

**Step 3: Score accumulation signals**
→ Run the Accumulation Score Engine (see below)

**Step 4: Generate output**
→ Return structured signal report

---

### Mode B: Sweep Scan
*Triggered when user wants to find accumulation opportunities across a category.*

**Step 1: Fetch trending list**
→ `GET /v2/tokens/trending?chain={chain}`

**Step 2: Filter candidates**
Apply pre-filter before scoring:
- `tvl` > 50,000 (minimum liquidity floor)
- `risk_score` < 80 (exclude extreme risk)
- `tx_count_24h` > 50 (minimum activity)

**Step 3: Score all candidates**
→ Run the Accumulation Score Engine on each

**Step 4: Return top signals**
→ Top N tokens sorted by accumulation score, with reasoning per token

---

## Accumulation Score Engine

Score is calculated 0–100. Higher = stronger pre-movement accumulation signal.

### Signal 1: Volume/Price Divergence `(0–30 pts)`

This is the core signal. Volume rising while price stays flat = quiet accumulation.

```
vol_24h = token_tx_volume_u_24h
avg_volume_30d = average from klines history
price_24h = token_price_change_24h

volume_ratio = vol_24h / avg_volume_30d if avg_volume_30d > 0 else 1

IF volume_ratio >= 2.5 AND abs(price_24h) < 3% → +30 pts (strong divergence)
IF volume_ratio >= 1.8 AND abs(price_24h) < 5% → +20 pts (moderate)
IF volume_ratio >= 1.3 AND abs(price_24h) < 7% → +10 pts (mild)
```

**Why it works:** Organic price discovery with volume surge shows up as price pump.
When volume surges but price stays muted, someone is absorbing sell pressure —
that's accumulation.

### Signal 2: Volume Momentum Velocity `(0–25 pts)`

```
vol_recent = average of last 3 days volume
vol_previous = average of days 4-6

IF vol_previous > 0:
    momentum = vol_recent / vol_previous
    
    IF momentum >= 3.0 → +25 pts (extreme acceleration)
    IF momentum >= 2.5 → +22 pts
    IF momentum >= 2.0 → +19 pts
    IF momentum >= 1.5 → +15 pts
```

**Why it works:** Accelerating volume day-over-day indicates increasing buy pressure
that's building up before the breakout.

### Signal 3: TVL Stability `(0–20 pts)`

```
tvl = main_pair_tvl

IF tvl > 10,000,000 → +20 pts (deep liquidity)
IF tvl > 5,000,000 → +18 pts
IF tvl > 2,000,000 → +16 pts
IF tvl > 1,000,000 → +14 pts
IF tvl > 500,000 → +12 pts
IF tvl > 200,000 → +10 pts
ELSE → +5 pts
```

**Why it works:** When smart money accumulates, LPs typically don't remove liquidity —
they're often on the same side. TVL drain + volume is panic; TVL stable + volume
is accumulation.

### Signal 4: Holder Distribution `(0–15 pts)`

```
holders_current = token.holders
holders_previous = from 7-day history

IF holders_previous > 0:
    growth = (holders_current - holders_previous) / holders_previous * 100
    
    IF growth >= 15% → +15 pts (excellent growth)
    IF growth >= 10% → +13 pts
    IF growth >= 8% → +12 pts
    IF growth >= 5% → +10 pts
    IF growth >= 3% → +8 pts
    IF growth > 0% → +6 pts
```

**Why it works:** When new wallets are entering a token heavily, it signals organic
distribution from large holders into many smaller ones — classic late-accumulation
pattern before retail FOMO.

### Signal 5: TVL Confidence `(0–10 pts)`

```
tvl = token.tvl

IF tvl > 50,000,000 → +10 pts (institutional depth)
IF tvl > 20,000,000 → +9 pts
IF tvl > 10,000,000 → +8 pts
IF tvl > 5,000,000 → +7 pts
IF tvl > 2,000,000 → +6 pts
IF tvl > 1,000,000 → +5 pts
```

**Why it works:** Deep liquidity means large moves can happen without excessive
slippage — a prerequisite for significant price action.

### Advanced Signals

#### Whale Accumulation Detector `(0–40 pts)`

```
FOR each holder in top25:
    IF holder.is_new AND holder.balance_ratio >= 2%:
        new_whales += 1
        score += 20
    
    IF holder.balance_ratio >= 5% AND holder.growing:
        accumulating_whales += 1
        score += 15

CAP score at 40 pts
```

#### Anomaly Detection (Z-Score) `(0–27 pts)`

```
z_score = (current_vol - avg_vol) / std_dev

IF z_score > 3.0 → +12 pts (extreme anomaly)
IF z_score > 2.5 → +10 pts (high anomaly)
IF z_score > 2.0 → +8 pts (unusual)

IF price_compression < 5% AND z_score > 1.5:
    score += 15 pts (classic accumulation pattern)
```

#### Historical Pattern Match `(0–8 pts)`

```
Compare current metrics against:
- Pattern A: "Silent Bludge" (3-7 days before 50x)
- Pattern B: "Slow Burn" (7-14 days before 20x)
- Pattern C: "Pump &..." (24-48h before 100x+)

IF match >= 75% → +8 pts
IF match >= 50% → +4 pts
```

### Dynamic Weighting by Market Phase

```
BULL PHASE (price +5%):
  volume_divergence: 35%
  volume_momentum: 25%
  tvl_stability: 15%
  holder_distribution: 10%
  tvl_confidence: 10%

CONSOLIDATION (-5% to +5%):
  tvl_stability: 30%
  volume_divergence: 25%
  volume_momentum: 20%
  holder_distribution: 20%
  tvl_confidence: 10%

BEAR PHASE (price -5%):
  holder_distribution: 30%
  volume_divergence: 20%
  tvl_stability: 20%
  volume_momentum: 15%
  tvl_confidence: 10%
```

### Risk Adjustment

```
Raw Score × Risk Multiplier:
- Low risk (0-30): ×0.92
- Medium risk (31-60): ×0.84
- High risk (61-85): ×0.70
- Extreme risk (86-100): ×0.60
```

### Score Interpretation

| Score | Signal Strength | Alert Level | Suggested Action |
|---|---|---|---|
| 75–100 | 🔴 **Strong Accumulation** | RED | High conviction pre-movement signal |
| 55–74 | 🟠 **Moderate Signal** | ORANGE | Watch closely, confirm with 15–30min followup |
| 35–54 | 🟡 **Weak Signal** | YELLOW | Background monitor, not actionable yet |
| 0–34 | 🟢 **No Signal** | GREEN | Normal activity, skip |

---

## Output Format

### Single Token Report

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 AVE ACCUMULATION MONITOR — {SYMBOL}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Chain: {chain}
Contract: {CA}
Price: ${current_price_usd} | 24h: {price_change_24h}%
TVL: ${tvl} | Holders: {holders:,}

ACCUMULATION SCORE: {score}/100 [{alert_emoji} {alert_level}]
Risk-Adjusted: {risk_adjusted}/100 | Confidence: {confidence}%
Market Phase: {phase_emoji} {market_phase}

Signal Breakdown:
 Volume/Price Divergence: {pts}/30 ⚡
 Volume Momentum Velocity: {pts}/25 📈
 TVL Stability: {pts}/20 🏦
 Holder Distribution: {pts}/15 👥
 TVL Confidence: {pts}/10 💰
 Whale Score: {pts}/40 🐋
 Anomaly Detection: {pts}/27 📊
 Pattern Match: {pts}/8 📚

Advanced Signals:
 🐋 Whale Activity: {whale_desc}
 📊 Anomaly: {anomaly_desc}
 📚 Pattern: {pattern_desc}

Top Whales:
  {address_short}: {balance_ratio}%
  ...

Ave Risk Score: {risk_score}/100

NEXT ACTIONS:
 {action_bullet_points}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Sweep Scan Report

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 AVE ACCUMULATION SWEEP — {category.upper()}
 Scanned {n} tokens | Chain: {chain}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 TOP SIGNALS:

1. {SYMBOL} [{chain}] | Score: {score}/100 {emoji}
   Price: ${price} | TVL: ${tvl}M | Vol 24h: ${volume}M
   🔥 Signals: {signal_summary}

2. {SYMBOL} ...

📈 CATEGORY SENTIMENT:
{market_summary}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Telegram Bot Commands

Bisa digunakan langsung dari Telegram tanpa CLI:

| Command | Description | Example |
|---------|-------------|---------|
| `/ave <token> [chain]` | Single token analysis | `/ave TRUMP solana` |
| `/avesweep <cat> [chain] [n]` | Sweep scan category | `/avesweep meme solana 5` |
| `/avehelp` | Show help message | `/avehelp` |
| `/avechains` | List supported chains | `/avechains` |

### Usage dari Telegram

Kirim command langsung:
```
/ave TRUMP solana
```

Response dalam format Markdown dengan emoji untuk readability.

---

## Supported Chains

- solana
- ethereum
- bsc
- base
- arbitrum
- optimism
- polygon
- avalanche

---

## File Structure

```
skills/ave-accumulation-monitor/
├── SKILL.md                          # This documentation
└── scripts/
    ├── ave_monitor.py                # Core analysis engine
    ├── ave_telegram_bot.py           # Telegram bot handler
    ├── ave_telegram_integration.py   # Integration module
    ├── alert_scheduler.py            # Automated alerts
    └── help.py                       # Full help guide
```

---

## Implementation Notes

### Rate Limiting
- Ave.ai free tier: standard rate limits apply
- Sweep scan: ~600 CU for 20 tokens
- Single token: ~30 CU per analysis
- Built-in delays: 0.3s between API calls

### Staleness Handling
Check `updated_at` timestamp on price responses.
If `now - updated_at > 120 seconds`, flag data as potentially stale in output.

### Chain Resolution
When user specifies token by symbol only (ambiguous):
1. Call `/v2/tokens?keyword={symbol}&limit=5`
2. If multiple results, return the one with highest `tvl`
3. If still ambiguous, ask user to specify chain

### Risk Gate
If `risk_score >= 85`, prepend output with:
```
⚠️ HIGH RISK TOKEN — Ave risk score: {score}/100
 Accumulation signal detected but exercise extreme caution.
 This token may have contract risk, honeypot mechanics, or other flags.
```

---

## What This Skill Does NOT Do

- Does not make trade recommendations
- Does not guarantee price movement
- Does not bypass Ave.ai's existing alerts (it complements them)
- Does not provide real-time streaming (pull-based, not push)
- Does not account for black swan events or external news

---

## Skill Philosophy

Most tools tell you what already happened.
This skill asks: *what's about to happen?*

The accumulation window is short. The signal is subtle.
This skill exists to catch it before the chart makes it obvious.

---

## References

- Ave.ai API Docs: https://ave-cloud.gitbook.io/data-api
- API Base URL: https://prod.ave-api.com
- API Registration: https://cloud.ave.ai/register

---

## License & Usage

This skill is open source. Users must:
1. Obtain their own Ave.ai API key
2. Set up their own Telegram bot token (for bot mode)
3. Comply with Ave.ai's terms of service

Not financial advice. DYOR.
