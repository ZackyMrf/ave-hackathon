#!/usr/bin/env python3
"""
Advanced Telegram Bot for Ave Accumulation Monitor
Integrated with alert system, watchlist, and real-time monitoring
"""
import os
import sys
import json
import time
import requests
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))
from ave_monitor import AveAccumulationMonitor

from alerts_manager import (
    init_alerts_manager,
    get_alerts_manager,
    ALERT_TYPE_PRICE,
    ALERT_TYPE_RISK,
    ALERT_TYPE_VOLUME,
    ALERT_TYPE_WHALE,
    CONDITION_ABOVE,
    CONDITION_BELOW,
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# Initialize
ave_monitor = AveAccumulationMonitor()
alerts_manager = init_alerts_manager(TOKEN)

# State management
user_sessions: Dict[int, Dict] = {}  # user_id -> {state, data}
watchlists: Dict[int, List[Dict]] = {}  # user_id -> [{token, chain, alerts}]
watchlist_lock = threading.Lock()

# Commands
COMMAND_START = "/start"
COMMAND_HELP = "/help"
COMMAND_ANALYZE = "/analyze"
COMMAND_ALERT = "/alert"
COMMAND_WATCHLIST = "/watchlist"
COMMAND_STATUS = "/status"
COMMAND_SWEEP = "/sweep"


def send_message(chat_id: int, text: str, parse_mode: str = "Markdown", reply_markup=None):
    """Send Telegram message"""
    try:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        r = requests.post(f"{BASE_URL}/sendMessage", json=payload, timeout=5)
        return r.json()
    except Exception as e:
        print(f"[send_message] Error: {e}")
        return None


def send_alert(chat_id: int, alert_type: str, message: str):
    """Send formatted alert"""
    emoji_map = {
        "price": "💰",
        "risk": "⚠️",
        "volume": "📊",
        "whale": "🐋",
        "trend": "📈",
    }
    emoji = emoji_map.get(alert_type, "🔔")
    
    text = f"{emoji} *ALERT*\n{message}"
    send_message(chat_id, text)


def format_token_info(token: str, chain: str) -> str:
    """Fetch and format token info"""
    try:
        resp = requests.get(
            f"{API_BASE_URL}/api/analyze",
            params={"token": token, "chain": chain},
            timeout=10,
        )
        data = resp.json()

        if "error" in data:
            return f"❌ Error: {data['error']}"

        s = data["score"]
        sig = data["signals"]
        
        alert_emoji = {
            "green": "🟢",
            "yellow": "🟡",
            "orange": "🟠",
            "red": "🔴",
        }.get(s["alert_level"], "⚪")

        lines = [
            f"📊 *{token.upper()}* ({chain})",
            f"Price: `${data['price']:.6f}` | 24h: {data['price_change_24h']:+.1f}%",
            f"TVL: `${data['tvl']/1e6:.2f}M` | Holders: {data['holders']:,}",
            "",
            f"*Score: {s['total']}/100* {alert_emoji}",
            f"Risk-Adjusted: {s['risk_adjusted']}/100",
            f"Confidence: {s['confidence']}%",
            f"Phase: {s['market_phase'].upper()}",
            "",
            "*Signals:*",
            f"⚡ Vol Divergence: {sig['volume_divergence']}/30",
            f"📈 Vol Momentum: {sig['volume_momentum']}/25",
            f"🏦 TVL Stability: {sig['tvl_stability']}/20",
            f"👥 Holders: {sig['holder_distribution']}/15",
            f"💎 Whale: {sig['whale_score']}/40",
        ]

        if data.get("whales"):
            lines.append("")
            lines.append("*Top Whales:*")
            for w in data["whales"][:3]:
                addr = f"{w['address'][:6]}...{w['address'][-4:]}"
                lines.append(f"  • {addr}: `{w['balance_ratio']:.2f}%`")

        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error fetching data: {str(e)}"


def handle_command_start(chat_id: int):
    """Handle /start command"""
    lines = [
        "👋 *Ave Accumulation Monitor - Advanced Bot*",
        "",
        "I provide real-time token monitoring, alerts, and watchlist management.",
        "",
        "*Available Commands:*",
        "/help - Show all commands",
        "/analyze `token` `chain` - Analyze token",
        "/alert - Create/manage alerts",
        "/watchlist - Manage watchlist",
        "/status - Show portfolio status",
        "/sweep `[category]` - Market sweep (default: all/network-wide)",
        "",
        "*Alert Types:*",
        "💰 Price alerts (above/below thresholds)",
        "⚠️ Risk score monitoring",
        "📊 Volume spike detection",
        "🐋 Whale movement tracking",
        "📈 Trend changes",
    ]
    send_message(chat_id, "\n".join(lines))


def handle_command_help(chat_id: int):
    """Handle /help command"""
    lines = [
        "*📚 Commands Guide*",
        "",
        "*Basic Commands:*",
        "`/analyze SOL solana` - Analyze Solana token",
        "`/sweep` - Run network-wide scan on default chain",
        "`/sweep all solana` - Network-wide scan on Solana",
        "`/sweep trending` - Apply category filter",
        "`/status` - Show your monitoring stats",
        "",
        "*Alert Management:*",
        "`/alert create` - Create new alert",
        "`/alert list` - Show your alerts",
        "`/alert delete` - Delete alert",
        "`/alert toggle` - Enable/disable alert",
        "",
        "*Watchlist:*",
        "`/watchlist add token chain` - Add to watchlist",
        "`/watchlist list` - Show watchlist",
        "`/watchlist remove token` - Remove from watchlist",
        "",
        "*Categories for sweep: all, trending, meme, defi, gaming, ai*",
        "*Chains: solana, ethereum, bsc, base, arbitrum*",
    ]
    send_message(chat_id, "\n".join(lines))


def handle_command_analyze(chat_id: int, args: List[str]):
    """Handle /analyze command"""
    if len(args) < 2:
        send_message(chat_id, "❌ Usage: `/analyze TOKEN CHAIN`\nExample: `/analyze SOL solana`")
        return

    token, chain = args[0], args[1]
    send_message(chat_id, f"🔄 Analyzing {token} on {chain}...")

    info = format_token_info(token, chain)
    send_message(chat_id, info)


def handle_command_sweep(chat_id: int, args: List[str]):
    """Handle /sweep command"""
    category = args[0] if args else "all"
    chain = args[1] if len(args) > 1 else "solana"

    try:
        resp = requests.get(
            f"{API_BASE_URL}/api/sweep",
            params={"category": category, "chain": chain, "top": 5},
            timeout=10,
        )
        data = resp.json()["results"]

        lines = [f"*📊 Top {len(data)} {category.upper()} Tokens ({chain})*", ""]

        for i, item in enumerate(data, 1):
            risk = item["risk_adjusted_score"]
            alert = "🔴" if risk >= 75 else "🟠" if risk >= 55 else "🟡"
            lines.append(f"{i}. `{item['token']}` {alert} {risk:.0f}%")
            lines.append(f"   Price: `${item['price']:.6f}` | TVL: `${item['tvl']/1e6:.2f}M`")

        send_message(chat_id, "\n".join(lines))
    except Exception as e:
        send_message(chat_id, f"❌ Sweep failed: {str(e)}")


def handle_command_alert_create(chat_id: int, args: List[str]):
    """Handle alert creation"""
    if len(args) < 4:
        lines = [
            "*Create Alert*",
            "Usage: `/alert create TOKEN CHAIN TYPE CONDITION THRESHOLD`",
            "",
            "*Examples:*",
            "`/alert create SOL solana price above 150` - Alert if SOL > $150",
            "`/alert create PUMP solana risk below 50` - Alert if risk < 50",
            "`/alert create MEME solana volume above 3` - Alert if volume > 3x",
        ]
        send_message(chat_id, "\n".join(lines))
        return

    try:
        token, chain, alert_type = args[0], args[1], args[2]
        condition = args[3]
        threshold = float(args[4])

        alert = alerts_manager.create_alert(
            user_id=chat_id,
            token=token,
            chain=chain,
            alert_type=alert_type,
            condition=condition,
            threshold=threshold,
        )

        send_message(
            chat_id,
            f"✅ Alert created!\n\n"
            f"Token: `{token}`\n"
            f"Type: {alert_type}\n"
            f"Condition: {condition} {threshold}\n"
            f"ID: `{alert.id}`",
        )
    except Exception as e:
        send_message(chat_id, f"❌ Error: {str(e)}")


def handle_command_alert_list(chat_id: int):
    """List user's alerts"""
    alerts = alerts_manager.get_user_alerts(chat_id)

    if not alerts:
        send_message(chat_id, "📭 You have no alerts yet.\nUse `/alert create` to add one.")
        return

    lines = [f"*Your Alerts ({len(alerts)})*", ""]

    for alert in alerts:
        status = "✅" if alert.enabled else "⏸️"
        lines.append(
            f"{status} `{alert.id}`\n"
            f"   {alert.token.upper()} ({alert.chain}) | {alert.alert_type}\n"
            f"   {alert.condition} {alert.threshold}"
        )

    lines.append("")
    lines.append("Use `/alert delete ID` or `/alert toggle ID`")
    send_message(chat_id, "\n".join(lines))


def handle_command_watchlist_add(chat_id: int, args: List[str]):
    """Add token to watchlist"""
    if len(args) < 2:
        send_message(chat_id, "❌ Usage: `/watchlist add TOKEN CHAIN`")
        return

    token, chain = args[0], args[1]

    with watchlist_lock:
        if chat_id not in watchlists:
            watchlists[chat_id] = []

        # Check if already in watchlist
        for item in watchlists[chat_id]:
            if item["token"].lower() == token.lower():
                send_message(chat_id, f"⚠️ {token} is already in your watchlist")
                return

        watchlists[chat_id].append({"token": token, "chain": chain})

    send_message(chat_id, f"✅ Added {token} to watchlist")


def handle_command_watchlist_list(chat_id: int):
    """Show watchlist"""
    with watchlist_lock:
        items = watchlists.get(chat_id, [])

    if not items:
        send_message(chat_id, "📭 Your watchlist is empty.\nUse `/watchlist add TOKEN CHAIN`")
        return

    lines = [f"*Your Watchlist ({len(items)})*", ""]

    for item in items:
        info = format_token_info(item["token"], item["chain"])
        # Extract first line only
        first_line = info.split("\n")[0]
        lines.append(first_line)

    send_message(chat_id, "\n".join(lines))


def handle_message(chat_id: int, message_text: str):
    """Route message to appropriate handler"""
    parts = message_text.strip().split()
    if not parts:
        handle_command_help(chat_id)
        return

    command = parts[0].lower()
    args = parts[1:]

    if command == COMMAND_START:
        handle_command_start(chat_id)
    elif command == COMMAND_HELP:
        handle_command_help(chat_id)
    elif command == COMMAND_ANALYZE:
        handle_command_analyze(chat_id, args)
    elif command == COMMAND_SWEEP:
        handle_command_sweep(chat_id, args)
    elif command == COMMAND_ALERT:
        if not args:
            send_message(chat_id, "Usage: `/alert create|list|delete|toggle`")
            return

        subcommand = args[0].lower()
        if subcommand == "create":
            handle_command_alert_create(chat_id, args[1:])
        elif subcommand == "list":
            handle_command_alert_list(chat_id)
        elif subcommand == "delete":
            if len(args) < 2:
                send_message(chat_id, "Usage: `/alert delete ALERT_ID`")
                return
            alert_id = args[1]
            if alerts_manager.delete_alert(alert_id):
                send_message(chat_id, "✅ Alert deleted")
            else:
                send_message(chat_id, "❌ Alert not found")
        elif subcommand == "toggle":
            if len(args) < 2:
                send_message(chat_id, "Usage: `/alert toggle ALERT_ID`")
                return
            alert_id = args[1]
            # Get current state
            alert = alerts_manager.alerts.get(alert_id)
            if alert:
                alerts_manager.update_alert_enabled(alert_id, not alert.enabled)
                status = "enabled" if not alert.enabled else "disabled"
                send_message(chat_id, f"✅ Alert {status}")
            else:
                send_message(chat_id, "❌ Alert not found")

    elif command == COMMAND_WATCHLIST:
        if not args:
            handle_command_watchlist_list(chat_id)
            return

        subcommand = args[0].lower()
        if subcommand == "add":
            handle_command_watchlist_add(chat_id, args[1:])
        elif subcommand == "list":
            handle_command_watchlist_list(chat_id)
        elif subcommand == "remove":
            if len(args) < 2:
                send_message(chat_id, "Usage: `/watchlist remove TOKEN`")
                return
            token = args[1]
            with watchlist_lock:
                watchlists[chat_id] = [
                    w for w in watchlists.get(chat_id, [])
                    if w["token"].lower() != token.lower()
                ]
            send_message(chat_id, f"✅ Removed {token} from watchlist")

    else:
        send_message(chat_id, f"❓ Unknown command: {command}\nUse /help for available commands")


def poll_updates():
    """Long poll for Telegram updates"""
    offset = 0
    poll_timeout = 30

    print("[bot] Starting update polling...")

    while True:
        try:
            resp = requests.get(
                f"{BASE_URL}/getUpdates",
                params={"offset": offset, "timeout": poll_timeout},
                timeout=poll_timeout + 5,
            )
            data = resp.json()

            if not data.get("ok"):
                print(f"[bot] Error: {data}")
                time.sleep(1)
                continue

            for update in data.get("result", []):
                update_id = update["update_id"]
                offset = max(offset, update_id + 1)

                if "message" in update:
                    msg = update["message"]
                    chat_id = msg["chat"]["id"]
                    text = msg.get("text", "")

                    print(f"[bot] User {chat_id}: {text}")
                    handle_message(chat_id, text)

        except Exception as e:
            print(f"[bot] Poll error: {e}")
            time.sleep(5)


def run_monitoring_worker():
    """Background worker to evaluate alerts"""
    print("[worker] Starting monitoring worker...")

    while True:
        try:
            time.sleep(300)  # Check every 5 minutes

            # Iterate through all alerts
            for alert in alerts_manager.alerts.values():
                if not alert.enabled:
                    continue

                try:
                    # Fetch current data
                    resp = requests.get(
                        f"{API_BASE_URL}/api/analyze",
                        params={"token": alert.token, "chain": alert.chain},
                        timeout=10,
                    )
                    data = resp.json()

                    if "error" in data:
                        continue

                    # Evaluate different alert types
                    if alert.alert_type == ALERT_TYPE_PRICE:
                        triggered = alerts_manager.evaluate_price_alert(
                            alert.token, alert.chain, data["price"]
                        )
                    elif alert.alert_type == ALERT_TYPE_RISK:
                        triggered = alerts_manager.evaluate_risk_alert(
                            alert.token, alert.chain, data["score"]["risk_adjusted"]
                        )
                    else:
                        continue

                    # Send notifications
                    for item in triggered:
                        if item["alert"] == alert and alert.notify_telegram:
                            details = f"Current: {item['current_value']:.2f}"
                            alerts_manager.send_telegram_alert(
                                alert.user_id, alert, details
                            )

                except Exception as e:
                    print(f"[worker] Error evaluating alert {alert.id}: {e}")

        except Exception as e:
            print(f"[worker] Error: {e}")
            time.sleep(10)


if __name__ == "__main__":
    # Start background worker
    worker_thread = threading.Thread(target=run_monitoring_worker, daemon=True)
    worker_thread.start()

    # Start main polling loop
    try:
        poll_updates()
    except KeyboardInterrupt:
        print("\n[bot] Shutting down...")
