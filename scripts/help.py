#!/usr/bin/env python3
"""
Ave Accumulation Monitor - Help & Usage Guide
"""

HELP_TEXT = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                    AVE ACCUMULATION MONITOR v2.0                             ║
║              Detect Smart Money Accumulation Before Price Moves              ║
╚══════════════════════════════════════════════════════════════════════════════╝

📖 OVERVIEW
───────────
Ave Accumulation Monitor adalah tool untuk mendeteksi sinyal akumulasi smart
money SEBELUM harga bergerak. Bedanya dengan price alert biasa:

  ❌ Price Alert: Memberitahu setelah harga naik (terlambat)
  ✅ Accumulation Monitor: Deteksi pembelian diam-diam (early alpha)

🎯 TWO OPERATING MODES
──────────────────────

┌─────────────────────────────────────────────────────────────────────────────┐
│ MODE A: SINGLE TOKEN MONITOR                                                │
│ Deep analysis pada satu token dengan full signal detection                   │
└─────────────────────────────────────────────────────────────────────────────┘

  USAGE:
    python ave_monitor.py --mode single --token <SYMBOL> --chain <CHAIN>

  EXAMPLES:
    # Monitor TRUMP di Solana
    python ave_monitor.py --mode single --token TRUMP --chain solana

    # Monitor PEPE di Ethereum dengan output JSON
    python ave_monitor.py --mode single --token PEPE --chain ethereum --json

    # Monitor by contract address
    python ave_monitor.py --mode single \\
      --token 6p6xgHyF7AeE6TZkSmFsko444wqoP15icUSqi2jfGiPN \\
      --chain solana

  COST: ~30 CU per call

┌─────────────────────────────────────────────────────────────────────────────┐
│ MODE B: SWEEP SCAN                                                          │
│ Scan multiple tokens dalam satu kategori, return top N                       │
└─────────────────────────────────────────────────────────────────────────────┘

  USAGE:
    python ave_monitor.py --mode sweep --category <CATEGORY> --chain <CHAIN>

  EXAMPLES:
    # Scan trending tokens di Solana
    python ave_monitor.py --mode sweep --category trending --chain solana

    # Scan meme tokens, ambil top 10
    python ave_monitor.py --mode sweep --category meme --chain ethereum --top 10

    # Output JSON untuk automation
    python ave_monitor.py --mode sweep --category defi --chain bsc --json

  CATEGORIES:
    • trending    - Token trending di chain tersebut
    • meme        - Meme coins (PEPE, DOGE, SHIB, etc.)
    • defi        - DeFi tokens (UNI, AAVE, COMP, etc.)
    • gaming      - Gaming tokens (IMX, GALA, SAND, etc.)
    • ai          - AI tokens (RNDR, FET, AGIX, etc.)

  COST: ~600 CU untuk 20 tokens

🔗 SUPPORTED CHAINS
───────────────────
  • solana      • ethereum    • bsc        • base
  • arbitrum    • optimism    • polygon    • avalanche

📊 SIGNAL SCORING SYSTEM
────────────────────────
┌─────────────────────────────────┬──────────┬────────────────────────────────┐
│ Signal                          │ Max Pts  │ What It Detects                │
├─────────────────────────────────┼──────────┼────────────────────────────────┤
│ Volume/Price Divergence         │   30     │ High volume, flat price        │
│ Volume Momentum Velocity        │   25     │ Accelerating volume            │
│ TVL Stability                   │   20     │ LPs holding positions          │
│ Holder Distribution             │   15     │ Growing holder count           │
│ TVL Confidence                  │   10     │ Deep liquidity                 │
│ Whale Activity                  │   40     │ New whales, accumulation       │
│ Anomaly Detection (Z-Score)     │   27     │ Statistical outliers           │
│ Historical Pattern Match        │    8     │ Pre-pump pattern match         │
└─────────────────────────────────┴──────────┴────────────────────────────────┘

🚨 ALERT LEVELS
───────────────
  🟢 GREEN   (< 35)   - Background watch, no action needed
  🟡 YELLOW  (35-54)  - Active watch, monitor daily
  🟠 ORANGE  (55-74)  - High probability window, check every 2-4h
  🔴 RED     (75-100) - Strong conviction, monitor real-time

🐋 WHALE DETECTION
──────────────────
  • New Whale Entry      : +20 pts (holder baru di top 25, 2%+ supply)
  • Whale Accumulation   : +15 pts (5%+ supply holder growing)
  • Whale Distribution   : -10 pts (gradual selling detected)

📈 HISTORICAL PATTERNS
──────────────────────
  Pattern A - "Silent Bludge" : 3-7 days before 50x pump
  Pattern B - "Slow Burn"     : 7-14 days before 20x pump
  Pattern C - "Pump &..."     : 24-48 hours before 100x+ pump

⚙️ COMMAND OPTIONS
──────────────────
  --mode {single,sweep}     Operating mode (required)
  --token SYMBOL            Token symbol or address (Mode A)
  --chain CHAIN             Blockchain name (default: solana)
  --category CAT            Category for sweep (Mode B)
  --top N                   Number of results (Mode B, default: 5)
  --json                    Output as JSON
  -h, --help                Show this help message

🔧 ENVIRONMENT VARIABLES
────────────────────────
  AVE_API_KEY               Override default API key

  Example:
    export AVE_API_KEY="your-api-key-here"
    python ave_monitor.py --mode single --token TRUMP --chain solana

📋 USAGE WORKFLOW
─────────────────

1. START WITH SWEEP SCAN
   $ python ave_monitor.py --mode sweep --category trending --chain solana
   
   → Lihat top 5 tokens dengan highest accumulation score

2. DEEP DIVE ON INTERESTING TOKEN
   $ python ave_monitor.py --mode single --token TRUMP --chain solana
   
   → Analyze semua signals, whale activity, pattern match

3. SET MONITORING SCHEDULE
   • Score 🟠 ORANGE (55-74): Check every 2-4 hours
   • Score 🔴 RED (75+): Monitor real-time, siap act

4. VALIDATE SIGNALS
   • Volume breakout above 4x baseline = confirmation
   • Whale follow-through dalam 2-4h = bullish
   • Holder growth acceleration = final phase

💡 PRO TIPS
───────────
  ✓ Best timeframe: 48-144h (2-6 days) sebelum pump
  ✓ Look for: Volume divergence + whale entry + pattern match
  ✓ Red flags: Whale distribution + declining holders
  ✓ Always DYOR: This is alpha tool, not financial advice

🎯 EXAMPLE SCENARIOS
────────────────────

SCENARIO 1: Early Detection
  $ python ave_monitor.py --mode single --token NEWCOIN --chain solana
  
  Result: Score 72/100 🟠 ORANGE
  - Volume divergence: 26/30
  - 2 new whales entered
  - Pattern match: 78% "Silent Bludge"
  
  Action: Monitor setiap 2 jam, siap entry kalau volume breakout

SCENARIO 2: Category Sweep
  $ python ave_monitor.py --mode sweep --category meme --chain solana --top 5
  
  Result: 
  #1 BONK - Score 68 🟠
  #2 WIF   - Score 61 🟠
  #3 BOME  - Score 54 🟡
  
  Action: Focus on BONK dan WIF, monitor untuk konfirmasi

SCENARIO 3: Multi-Chain Scan
  $ python ave_monitor.py --mode sweep --category trending --chain ethereum
  $ python ave_monitor.py --mode sweep --category trending --chain base
  
  Action: Compare accumulation signals across chains

⚠️ IMPORTANT NOTES
──────────────────
  • This tool detects ACCUMULATION patterns, not guarantee price movement
  • Past performance does not indicate future results
  • Always combine dengan fundamental analysis
  • Manage risk: Jangan all-in berdasarkan satu signal
  • API Rate Limits: ~600 CU/minute

📚 API REFERENCE
────────────────
  Base URL:    https://prod.ave-api.com
  Auth:        X-API-KEY header
  Docs:        https://ave-cloud.gitbook.io/data-api

🆘 TROUBLESHOOTING
──────────────────

Error: "Could not fetch data"
  → Cek chain name (case sensitive: solana, ethereum, bsc)
  → Coba pakai contract address langsung

Error: "API Error"
  → Cek API key masih valid
  → Mungkin rate limit, tunggu 1 menit

Low scores on all tokens
  → Market mungkin dalam bear phase
  → Coba category lain atau chain lain

📞 SUPPORT
──────────
  Ave AI Cloud Telegram: https://t.me/ave_ai_cloud
  API Registration:      https://cloud.ave.ai/register

═══════════════════════════════════════════════════════════════════════════════
"""

def print_help():
    print(HELP_TEXT)

if __name__ == "__main__":
    print_help()
