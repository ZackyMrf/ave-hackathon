#!/usr/bin/env python3
"""
Ave Accumulation Monitor - Telegram Bot (Simple Version)
Using requests library instead of python-telegram-bot
"""

import os
import sys
import time
import json
import requests
from typing import Dict, Optional

# Add scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))
from ave_monitor import AveAccumulationMonitor

# Config
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
OFFSET = 0

# Initialize monitor
ave_monitor = AveAccumulationMonitor()

def send_message(chat_id: int, text: str, parse_mode: str = "Markdown"):
    """Send message to Telegram"""
    try:
        r = requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode
        })
        return r.json()
    except Exception as e:
        print(f"Error sending message: {e}")
        return None

def format_report(report: Dict) -> str:
    """Format accumulation report"""
    if "error" in report:
        return f"❌ Error: {report['error']}"
    
    s = report["score"]
    sig = report["signals"]
    
    alert_emoji = {"green": "🟢", "yellow": "🟡", "orange": "🟠", "red": "🔴"}.get(s["alert_level"], "⚪")
    
    lines = [
        f"📊 *AVE MONITOR — {report['token'].upper()}*",
        "",
        f"Chain: `{report['chain']}`",
        f"Price: ${report['price']:.4f} | 24h: {report['price_change_24h']:+.1f}%",
        f"TVL: ${report['tvl']/1e6:.2f}M | Holders: {report['holders']:,}",
        "",
        f"🎯 *Score: {s['total']}/100* {alert_emoji}",
        f"Risk-Adj: {s['risk_adjusted']}/100 | Conf: {s['confidence']}%",
        f"Phase: {s['market_phase'].upper()}",
        "",
        "*Signals:*",
        f"⚡ Vol Divergence: {sig['volume_divergence']}/30",
        f"📈 Vol Momentum: {sig['volume_momentum']}/25",
        f"🏦 TVL Stability: {sig['tvl_stability']}/20",
        f"👥 Holders: {sig['holder_distribution']}/15",
        f"💎 TVL Conf: {sig['tvl_confidence']}/10",
        f"🐋 Whale: {sig['whale_score']}/40",
        f"📊 Anomaly: {sig['anomaly_score']}/27",
        f"📚 Pattern: {sig['pattern_match']}/8",
    ]
    
    if report.get("whales"):
        lines.extend(["", "*Top Whales:*"])
        for w in report["whales"][:3]:
            addr = f"{w['address'][:6]}...{w['address'][-4:]}"
            lines.append(f"`{addr}`: {w['balance_ratio']:.2f}%")
    
    lines.extend(["", "*Action:*"])
    if s["risk_adjusted"] >= 75:
        lines.append("🔴 *STRONG* — Monitor real-time")
    elif s["risk_adjusted"] >= 55:
        lines.append("🟠 *HIGH PROB* — Check again in 2h")
    elif s["risk_adjusted"] >= 35:
        lines.append("🟡 *WATCH* — Monitor daily")
    else:
        lines.append("🟢 *BACKGROUND* — No action yet")
    
    return "\n".join(lines)

def handle_start(chat_id: int):
    """Handle /start command"""
    text = (
        "📊 *Ave Accumulation Monitor*\n\n"
        "Detect smart money accumulation before price moves!\n\n"
        "*Commands:*\n"
        "/ave `<token>` `[chain]` — Single token analysis\n"
        "/avesweep `<category>` `[chain]` `[n]` — Sweep scan\n"
        "/help — Show help\n"
        "/chains — List supported chains\n\n"
        "Example: `/ave TRUMP solana`"
    )
    send_message(chat_id, text)

def handle_ave(chat_id: int, args: list):
    """Handle /ave command"""
    if not args:
        send_message(chat_id, "❌ Usage: /ave `<token>` `[chain]`\nExample: `/ave TRUMP solana`")
        return
    
    token = args[0].upper()
    chain = args[1].lower() if len(args) > 1 else 'solana'
    
    send_message(chat_id, f"🔍 Analyzing *{token}*...")
    
    try:
        report = ave_monitor.analyze_single_token(token, chain)
        response = format_report(report)
        
        # Split long messages
        if len(response) > 4000:
            parts = [response[i:i+4000] for i in range(0, len(response), 4000)]
            for part in parts:
                send_message(chat_id, part)
        else:
            send_message(chat_id, response)
    except Exception as e:
        send_message(chat_id, f"❌ Error: {str(e)}")

def handle_help(chat_id: int):
    """Handle /help command"""
    text = (
        "📊 *Ave Accumulation Monitor*\n\n"
        "*Commands:*\n"
        "/ave `<token>` `[chain]` — Single token\n"
        "/avesweep `<cat>` `[chain]` `[n]` — Sweep scan\n"
        "/help — Show this help\n"
        "/chains — List chains\n\n"
        "*Categories:* trending, meme, defi, gaming, ai\n\n"
        "*Chains:* solana, ethereum, bsc, base, arbitrum, optimism, polygon, avalanche\n\n"
        "⚠️ Not financial advice"
    )
    send_message(chat_id, text)

def handle_chains(chat_id: int):
    """Handle /chains command"""
    text = (
        "🌐 *Supported Chains:*\n\n"
        "• `solana` — ⚡ Fast, low fees\n"
        "• `ethereum` — 🔷 DeFi king\n"
        "• `bsc` — 🟡 Binance chain\n"
        "• `base` — 🔵 Coinbase L2\n"
        "• `arbitrum` — 🟣 Ethereum L2\n"
        "• `optimism` — 🔴 Ethereum L2\n"
        "• `polygon` — 🟣 Layer 2\n"
        "• `avalanche` — 🔺 Fast finality\n\n"
        "Default: `solana`"
    )
    send_message(chat_id, text)

def process_update(update: Dict):
    """Process incoming update"""
    global OFFSET
    
    if "message" not in update:
        return
    
    message = update["message"]
    chat_id = message["chat"]["id"]
    
    if "text" not in message:
        return
    
    text = message["text"]
    print(f"Received: {text}")
    
    # Parse command
    parts = text.split()
    command = parts[0].lower()
    args = parts[1:]
    
    if command == "/start":
        handle_start(chat_id)
    elif command == "/ave":
        handle_ave(chat_id, args)
    elif command == "/help":
        handle_help(chat_id)
    elif command == "/chains":
        handle_chains(chat_id)
    else:
        send_message(chat_id, f"Unknown command: {command}\nTry /help")

def main():
    """Main bot loop"""
    global OFFSET
    
    if not TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not set!")
        print("Export: export TELEGRAM_BOT_TOKEN='your-token'")
        sys.exit(1)
    
    print("🤖 Ave Bot Starting...")
    print(f"🔑 Token: {TOKEN[:20]}...")
    
    # Test connection
    r = requests.get(f"{BASE_URL}/getMe")
    if r.json().get("ok"):
        bot_info = r.json()["result"]
        print(f"✅ Connected as @{bot_info['username']}")
    else:
        print("❌ Failed to connect")
        sys.exit(1)
    
    print("📡 Waiting for messages...")
    
    while True:
        try:
            r = requests.get(f"{BASE_URL}/getUpdates", params={
                "offset": OFFSET,
                "limit": 10,
                "timeout": 30
            })
            data = r.json()
            
            if not data.get("ok"):
                print(f"API Error: {data}")
                time.sleep(5)
                continue
            
            for update in data.get("result", []):
                OFFSET = update["update_id"] + 1
                process_update(update)
            
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)
        
        time.sleep(1)

if __name__ == "__main__":
    main()
