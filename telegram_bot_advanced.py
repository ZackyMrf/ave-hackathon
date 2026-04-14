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
from urllib.parse import urlencode
from urllib.parse import urlparse

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
WEB_APP_URL = os.getenv("WEB_APP_URL") or os.getenv("FRONTEND_URL") or "http://localhost:5173"

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
COMMAND_AVESWEEP = "/avesweep"
COMMAND_CHAINS = "/chains"
COMMAND_AVE = "/ave"


def sync_alerts_from_storage():
    """Sync alerts in memory with alerts.json written by API/web process."""
    try:
        alerts_manager.reload_alerts()
    except Exception as e:
        print(f"[bot] Alert sync failed: {e}")


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


def build_launch_web_markup(token: str = "", chain: str = "") -> Dict:
    """Build Telegram inline keyboard with Launch Web button."""
    base_url = str(WEB_APP_URL or "http://localhost:5173").strip()
    parsed = urlparse(base_url)
    host = str(parsed.hostname or "").strip().lower()

    # Telegram can reject button URLs like localhost/0.0.0.0; skip button in that case.
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return {}
    if host in {"localhost", "127.0.0.1", "0.0.0.0"}:
        return {}

    params = {}

    token_value = str(token or "").strip()
    chain_value = str(chain or "").strip()
    if token_value:
        params["token"] = token_value.upper()
    if chain_value:
        params["chain"] = chain_value.lower()

    target_url = base_url
    if params:
        separator = "&" if "?" in base_url else "?"
        target_url = f"{base_url}{separator}{urlencode(params)}"

    return {
        "inline_keyboard": [[{"text": "🚀 Launch Web", "url": target_url}]],
    }


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

        tvl     = float(data.get("tvl", 0) or 0)
        holders = int(data.get("holders", 0) or 0)
        price   = float(data.get("price", 0) or 0)

        # --- Scam / Fake Token Detection ---
        scam_flags = []
        if tvl < 1_000:
            scam_flags.append(f"TVL only ${tvl:.2f}")
        if holders < 50:
            scam_flags.append(f"only {holders} holders")
        if price == 0.0:
            scam_flags.append("price is $0.00")

        if len(scam_flags) >= 2:
            # HIGH — likely a fake token, stop here and provide guidance
            return (
                f"🚫 *TOKEN NOT FOUND / LIKELY INCORRECT*\n\n"
                f"Results for *{token.upper()}* ({chain}) are suspicious:\n"
                + "\n".join(f"  • {f}" for f in scam_flags)
                + "\n\n"
                "❌ *This is likely NOT the token you were looking for.*\n\n"
                "✅ *Solution:*\n"
                "Search using the correct *contract address (CA)*.\n"
                "Example:\n"
                f"`/ave {token} {chain}` ← using symbol _(prone to error)_\n"
                "→ Replace with the official token CA, for example:\n"
                "`/ave 0x5a98fcbea516cf06857215779fd812ca3bef1b32 ethereum`\n\n"
                "💡 Check the official CA on CoinGecko / CoinMarketCap."
            )
        # --- End Detection HIGH ---

        # Single caution flag — show a light warning above the result
        caution_line = ""
        if len(scam_flags) == 1:
            caution_line = (
                f"⚠️ _Caution: {scam_flags[0]} — ensure this is the correct token._\n"
                "_If incorrect, search again using the contract address (CA)._\n"
            )

        lines = []
        if caution_line:
            lines.append(caution_line)

        lines += [
            f"📊 *{token.upper()}* ({chain})",
            f"Price: `${price:.6f}` | 24h: {data['price_change_24h']:+.1f}%",
            f"TVL: `${tvl/1e6:.2f}M` | Holders: {holders:,}",
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


def claim_deeplink_login(chat_id: int, code: str, chat_meta: Optional[Dict] = None) -> Dict[str, str]:
    """Claim web deep-link login session in API backend."""
    if not code:
        return {"ok": "false", "detail": "Missing connect code"}

    payload = {
        "code": code,
        "chat_id": int(chat_id),
        "username": str((chat_meta or {}).get("username") or ""),
        "first_name": str((chat_meta or {}).get("first_name") or ""),
    }

    try:
        resp = requests.post(f"{API_BASE_URL}/api/telegram/deeplink/claim", json=payload, timeout=8)
        data = resp.json() if resp.content else {}
        if resp.ok and isinstance(data, dict) and data.get("success"):
            return {"ok": "true", "detail": "Connected"}

        detail = "Invalid login session"
        if isinstance(data, dict):
            detail = str(data.get("detail") or detail)
        return {"ok": "false", "detail": detail}
    except Exception as e:
        return {"ok": "false", "detail": f"Claim failed: {e}"}


def handle_command_start(chat_id: int, args: Optional[List[str]] = None, chat_meta: Optional[Dict] = None):
    """Handle /start command"""
    args = args or []

    if args and str(args[0]).startswith("connect_"):
        code = str(args[0])[len("connect_"):].strip()
        claimed = claim_deeplink_login(chat_id, code, chat_meta)
        if claimed.get("ok") == "true":
            send_message(
                chat_id,
                "✅ *Telegram Connected*\n"
                "Your Telegram account is now linked to Ave Monitor web login."
            )
        else:
            send_message(
                chat_id,
                f"⚠️ *Connect Failed*\n{claimed.get('detail', 'Invalid login session')}"
            )

    lines = [
        "👋 *Ave Accumulation Monitor - Advanced Bot*",
        "",
        "I provide real-time token monitoring, alerts, and watchlist management.",
        "",
        "*Available Commands:*",
        "/help - Show all commands",
        "/analyze `token` `chain` - Analyze token",
        "/ave `token` `[chain]` - Quick analyze (alias)",
        "/sweep `[category]` `[chain]` `[n]` - Market sweep",
        "/avesweep `[category]` `[chain]` `[n]` - Sweep alias",
        "/alert - Create/manage alerts",
        "/watchlist - Manage watchlist",
        "/status - Show portfolio status",
        "/chains - List supported chains",
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
        "`/ave SOL solana` - Quick analyze (alias)",
        "`/sweep` - Run network-wide scan on default chain",
        "`/sweep all solana` - Network-wide scan on Solana",
        "`/sweep trending solana 5` - Category filter with limit",
        "`/avesweep meme solana 5` - Sweep alias",
        "`/status` - Show your monitoring stats",
        "`/chains` - List supported chains",
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
    if str(info).startswith("❌"):
        send_message(chat_id, info)
        return

    markup = build_launch_web_markup(token, chain)
    sent = send_message(chat_id, info, reply_markup=markup if markup else None)

    # Fallback: if Telegram rejects button markup, still send analysis text.
    if not isinstance(sent, dict) or not sent.get("ok"):
        send_message(chat_id, info)


def handle_command_sweep(chat_id: int, args: List[str]):
    """Handle /sweep command"""
    valid_chains = {"solana", "ethereum", "bsc", "base", "arbitrum", "optimism", "polygon", "avalanche"}

    category = "all"
    chain = "solana"
    limit = 5

    try:
        if len(args) >= 1:
            first = args[0].lower()
            if first in valid_chains:
                chain = first
                if len(args) > 1:
                    try:
                        limit = int(args[1])
                    except ValueError:
                        pass
            else:
                category = first
                if len(args) > 1:
                    chain = args[1].lower()
                if len(args) > 2:
                    try:
                        limit = int(args[2])
                    except ValueError:
                        pass
    except (IndexError, ValueError):
        pass

    limit = max(1, min(limit, 20))
    scope = f"{chain} network-wide" if category == "all" else f"{category} on {chain}"
    send_message(chat_id, f"🔄 Sweeping {scope} (top {limit})...")

    # Try API first, then fall back to direct ave_monitor
    sweep_results = None
    try:
        resp = requests.get(
            f"{API_BASE_URL}/api/sweep",
            params={"category": category, "chain": chain, "top": limit},
            timeout=120,
        )
        if resp.ok:
            body = resp.json()
            sweep_results = body.get("results", [])
    except Exception:
        pass

    # Fallback: call ave_monitor directly
    if not sweep_results:
        try:
            sweep_results = ave_monitor.sweep_scan(category, chain, limit)
        except Exception as e:
            send_message(chat_id, f"❌ Sweep failed: {str(e)}")
            return

    if not sweep_results:
        send_message(chat_id, f"❌ No results found for {scope}")
        return

    lines = [f"*📊 Top {len(sweep_results)} {category.upper()} Tokens ({chain})*", ""]

    for i, item in enumerate(sweep_results[:10], 1):
        # Support both API response format and direct monitor format
        score_data = item.get("score", {})
        risk = score_data.get("risk_adjusted", 0) if isinstance(score_data, dict) else 0
        alert_level = score_data.get("alert_level", "green") if isinstance(score_data, dict) else "green"
        alert = {"green": "🟢", "yellow": "🟡", "orange": "🟠", "red": "🔴"}.get(alert_level, "⚪")
        token_name = str(item.get("token", "???")).upper()
        price = float(item.get("price", 0) or 0)
        tvl = float(item.get("tvl", 0) or 0)
        total_score = score_data.get("total", 0) if isinstance(score_data, dict) else 0

        lines.append(f"{i}. `{token_name}` {alert} Score: {total_score}/100")
        if price > 0:
            lines.append(f"   Price: `${price:.6f}` | TVL: `${tvl/1e6:.2f}M`")

    send_message(chat_id, "\n".join(lines))


def handle_command_status(chat_id: int):
    """Handle /status command — show user's monitoring stats"""
    sync_alerts_from_storage()
    alerts = alerts_manager.get_user_alerts(chat_id)

    with watchlist_lock:
        watchlist_items = watchlists.get(chat_id, [])

    active_alerts = sum(1 for a in alerts if a.enabled)
    total_alerts = len(alerts)
    watchlist_count = len(watchlist_items)

    lines = [
        "*📈 Your Monitoring Status*",
        "",
        f"🔔 Alerts: {active_alerts} active / {total_alerts} total",
        f"👁️ Watchlist: {watchlist_count} tokens",
        "",
    ]

    if alerts:
        lines.append("*Recent Alerts:*")
        for alert in alerts[:5]:
            status = "✅" if alert.enabled else "⏸️"
            lines.append(f"{status} {alert.token.upper()} ({alert.chain}) — {alert.alert_type} {alert.condition} {alert.threshold}")
        lines.append("")

    if watchlist_items:
        lines.append("*Watchlist:*")
        for item in watchlist_items[:5]:
            lines.append(f"• {item['token'].upper()} ({item['chain']})")
        lines.append("")

    if not alerts and not watchlist_items:
        lines.extend([
            "No active monitoring yet.",
            "",
            "*Get started:*",
            "`/alert create TOKEN chain price above 100`",
            "`/watchlist add TOKEN chain`",
        ])

    send_message(chat_id, "\n".join(lines))


def handle_command_chains(chat_id: int):
    """Handle /chains command"""
    lines = [
        "*🌐 Supported Chains:*",
        "",
        "• `solana` — ⚡ Fast, low fees",
        "• `ethereum` — 🔷 DeFi king",
        "• `bsc` — 🟡 Binance chain",
        "• `base` — 🔵 Coinbase L2",
        "• `arbitrum` — 🟣 Ethereum L2",
        "• `optimism` — 🔴 Ethereum L2",
        "• `polygon` — 🟣 Layer 2",
        "• `avalanche` — 🔺 Fast finality",
        "",
        "Default: `solana`",
    ]
    send_message(chat_id, "\n".join(lines))


def handle_command_ave(chat_id: int, args: List[str]):
    """Handle /ave command (alias for /analyze)"""
    if not args:
        send_message(chat_id, "❌ Usage: `/ave TOKEN [chain]`\nExample: `/ave SOL solana`")
        return

    token = args[0]
    chain = args[1] if len(args) > 1 else "solana"

    send_message(chat_id, f"🔄 Analyzing {token.upper()} on {chain}...")

    # Try API first
    info = format_token_info(token, chain)
    if str(info).startswith("❌"):
        # Fallback to direct monitor
        try:
            report = ave_monitor.analyze_single_token(token, chain)
            if "error" not in report:
                info = _format_direct_report(report)
            else:
                send_message(chat_id, f"❌ {report['error']}")
                return
        except Exception as e:
            send_message(chat_id, f"❌ Error: {str(e)}")
            return

    markup = build_launch_web_markup(token, chain)
    sent = send_message(chat_id, info, reply_markup=markup if markup else None)
    if not isinstance(sent, dict) or not sent.get("ok"):
        send_message(chat_id, info)


def _format_direct_report(report: Dict) -> str:
    """Format a direct ave_monitor report for Telegram."""
    s = report["score"]
    sig = report["signals"]

    alert_emoji = {
        "green": "🟢", "yellow": "🟡", "orange": "🟠", "red": "🔴",
    }.get(s["alert_level"], "⚪")

    lines = [
        f"📊 *{report['token'].upper()}* ({report['chain']})",
        f"Price: `${report['price']:.6f}` | 24h: {report['price_change_24h']:+.1f}%",
        f"TVL: `${report['tvl']/1e6:.2f}M` | Holders: {report['holders']:,}",
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

    if report.get("whales"):
        lines.append("")
        lines.append("*Top Whales:*")
        for w in report["whales"][:3]:
            addr = f"{w['address'][:6]}...{w['address'][-4:]}"
            lines.append(f"  • {addr}: `{w['balance_ratio']:.2f}%`")

    return "\n".join(lines)


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
    sync_alerts_from_storage()
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


def handle_message(chat_id: int, message_text: str, chat_meta: Optional[Dict] = None):
    """Route message to appropriate handler"""
    parts = message_text.strip().split()
    if not parts:
        handle_command_help(chat_id)
        return

    command = parts[0].lower()
    # Strip bot username suffix (e.g. /sweep@mybotname)
    if "@" in command:
        command = command.split("@")[0]
    args = parts[1:]

    if command == COMMAND_START:
        handle_command_start(chat_id, args, chat_meta)
    elif command == COMMAND_HELP:
        handle_command_help(chat_id)
    elif command == COMMAND_ANALYZE:
        handle_command_analyze(chat_id, args)
    elif command == COMMAND_AVE:
        # /ave supports subcommands: watch, unwatch, list
        if args and args[0].lower() == "watch":
            handle_command_watchlist_add(chat_id, args[1:])
        elif args and args[0].lower() == "unwatch":
            if len(args) < 2:
                send_message(chat_id, "Usage: `/ave unwatch TOKEN`")
                return
            token = args[1]
            with watchlist_lock:
                watchlists[chat_id] = [
                    w for w in watchlists.get(chat_id, [])
                    if w["token"].lower() != token.lower()
                ]
            send_message(chat_id, f"✅ Removed {token} from watchlist")
        elif args and args[0].lower() == "list":
            handle_command_watchlist_list(chat_id)
        else:
            handle_command_ave(chat_id, args)
    elif command in (COMMAND_SWEEP, COMMAND_AVESWEEP):
        handle_command_sweep(chat_id, args)
    elif command == COMMAND_CHAINS:
        handle_command_chains(chat_id)
    elif command == COMMAND_STATUS:
        handle_command_status(chat_id)
    elif command == COMMAND_ALERT:
        sync_alerts_from_storage()
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
                    chat_meta = msg.get("chat", {})

                    print(f"[bot] User {chat_id}: {text}")
                    handle_message(chat_id, text, chat_meta)

        except Exception as e:
            print(f"[bot] Poll error: {e}")
            time.sleep(5)


def run_monitoring_worker():
    """Background worker to evaluate alerts"""
    print("[worker] Starting monitoring worker...")

    while True:
        try:
            time.sleep(300)  # Check every 5 minutes

            # Pull newest alerts created/updated by web API process.
            sync_alerts_from_storage()

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
