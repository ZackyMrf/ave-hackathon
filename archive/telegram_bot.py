#!/usr/bin/env python3
import os
import sys
import time
import json
import requests
import threading
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))
from ave_monitor import AveAccumulationMonitor

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
OFFSET = 0
CHECK_INTERVAL = 900  # 15 minutes

ave_monitor = AveAccumulationMonitor()
watchlists = {}
watchlist_lock = threading.Lock()


def send_message(chat_id, text, parse_mode="Markdown"):
    try:
        r = requests.post(
            f"{BASE_URL}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
        )
        return r.json()
    except Exception as e:
        print(f"[send_message] Error: {e}")
        return None


def format_report(report):
    if "error" in report:
        return f"\u274c Error: {report['error']}"

    s = report["score"]
    sig = report["signals"]
    alert_emoji = {"green": "\U0001f7e2", "yellow": "\U0001f7e1", "orange": "\U0001f7e0", "red": "\U0001f534"}.get(s["alert_level"], "\u26aa\ufe0f")

    lines = [
        f"\U0001f4ca AVE MONITOR \u2014 {report['token'].upper()}",
        "",
        f"Chain: {report['chain']}",
        f"Price: ${report['price']:.4f} | 24h: {report['price_change_24h']:+.1f}%",
        f"TVL: ${report['tvl'] / 1e6:.2f}M | 👥 Holders:        {report['holders']:,}",
        "",
        f"\U0001f3af Score: {s['total']}/100 {alert_emoji}",
        f"Risk-Adj: {s['risk_adjusted']}/100 | Conf: {s['confidence']}%",
        f"Phase: {s['market_phase'].upper()}",
        "",
        "Signals:",
        f"⚡️ Vol Divergence: {sig['volume_divergence']}/30",
        f"📈 Vol Momentum:    {sig['volume_momentum']}/25",
        f"🏦 TVL Stability:   {sig['tvl_stability']}/20",
        f"👥 Holders:               {sig['holder_distribution']}/15",
        f"💎 TVL Conf:             {sig['tvl_confidence']}/10",
        f"🐋 Whale:                   {sig['whale_score']}/40",
        f"📊 Anomaly:               {sig['anomaly_score']}/27",
        f"📚 Pattern:               {sig['pattern_match']}/8",
    ]

    if report.get("whales"):
        lines.extend(["", "Top Whales:"])
        for w in report["whales"][:3]:
            addr = f"{w['address'][:6]}...{w['address'][-4:]}"
            lines.append(f"  {addr}: {w['balance_ratio']:.2f}%")

    lines.extend(["", "Action:"])
    if s["risk_adjusted"] >= 75:
        lines.append("🔴 STRONG — Monitor real-time")
    elif s["risk_adjusted"] >= 55:
        lines.append("🟠 HIGH PROB — Check again in 2h")
    elif s["risk_adjusted"] >= 35:
        lines.append("🟡 WATCH — Monitor daily")
    else:
        lines.append("🟢 BACKGROUND — No action yet")

    return "\n".join(lines)


def watchlist_add(chat_id, token, chain):
    token, chain = token.lower(), chain.lower()
    token_id = f"{token}-{chain}"
    with watchlist_lock:
        if chat_id not in watchlists:
            watchlists[chat_id] = {}
        if token_id in watchlists[chat_id]:
            return f"{token.upper()} already in watchlist"
        result = ave_monitor.analyze_single_token(token, chain)
        if "error" in result:
            return f"❌ Could not fetch data for {token.upper()}"
        watchlists[chat_id][token_id] = {
            "token": token, "chain": chain,
            "added_at": datetime.now(),
            "last_score": result["score"]["risk_adjusted"],
            "last_alert_time": None,
        }
        return f"✅ Added {token.upper()} ({chain}) to watchlist\n\nChecking every 15 min, alert if score >= 60"


def watchlist_remove(chat_id, token, chain):
    token, chain = token.lower(), chain.lower()
    token_id = f"{token}-{chain}"
    with watchlist_lock:
        if chat_id not in watchlists or token_id not in watchlists[chat_id]:
            return f"{token.upper()} not in watchlist"
        del watchlists[chat_id][token_id]
        if not watchlists[chat_id]:
            del watchlists[chat_id]
        return f"✅ Removed {token.upper()} from watchlist"


def watchlist_list(chat_id):
    with watchlist_lock:
        if chat_id not in watchlists or not watchlists[chat_id]:
            return "Watchlist is empty\n\nAdd with: /ave watch <token> <chain>"
        lines = ["Your Watchlist:\n"]
        for item in watchlists[chat_id].values():
            added = item["added_at"].strftime("%H:%M")
            lines.append(f"- {item['token'].upper()} ({item['chain']}) Score: {item['last_score']}/100 Added {added}")
        lines.append(f"\nChecking every {CHECK_INTERVAL // 60} minutes")
        return "\n".join(lines)


def check_watchlists():
    print("Watchlist monitor started")
    while True:
        time.sleep(CHECK_INTERVAL)
        with watchlist_lock:
            chat_ids = list(watchlists.keys())
        for chat_id in chat_ids:
            with watchlist_lock:
                if chat_id not in watchlists:
                    continue
                tokens = list(watchlists[chat_id].items())
            for token_id, item in tokens:
                try:
                    result = ave_monitor.analyze_single_token(item["token"], item["chain"])
                    if "error" in result:
                        continue
                    current_score = result["score"]["risk_adjusted"]
                    prev_score = item["last_score"]
                    alert_msg = None
                    if current_score >= 75 and prev_score < 75:
                        alert_msg = f"🚨 STRONG SIGNAL! {item['token'].upper()} jumped to {current_score}/100"
                    elif current_score >= 60 and prev_score < 60:
                        alert_msg = f"Alert: {item['token'].upper()} score: {current_score}/100"
                    if alert_msg:
                        last_alert = item.get("last_alert_time")
                        cooldown_ok = last_alert is None or (datetime.now() - last_alert).seconds > 3600
                        if cooldown_ok:
                            send_message(chat_id, alert_msg + f"\n\nRun /ave {item['token']} {item['chain']} for details")
                            item["last_alert_time"] = datetime.now()
                    with watchlist_lock:
                        if chat_id in watchlists and token_id in watchlists[chat_id]:
                            watchlists[chat_id][token_id]["last_score"] = current_score
                    time.sleep(2)
                except Exception as e:
                    print(f"[check_watchlists] Error: {e}")


def handle_start(chat_id):
    send_message(chat_id,
        "Ave Accumulation Monitor\n\n"
        "/ave <token> [chain] - Single analysis\n"
        "/ave watch <token> <chain> - Add to watchlist\n"
        "/ave unwatch <token> <chain> - Remove from watchlist\n"
        "/ave list - Show watchlist\n"
        "/avesweep [category|chain] [chain] [n] - Sweep scan (default: all/network-wide)\n"
        "/chains - List chains\n"
        "/help - Show help")


def handle_help(chat_id):
    send_message(chat_id,
        "Commands:\n"
        "/ave <token> [chain]\n"
        "/ave watch <token> <chain>\n"
        "/ave unwatch <token> <chain>\n"
        "/ave list\n"
        "/avesweep [category|chain] [chain] [n]\n"
        "  examples: /avesweep all solana 5 | /avesweep solana 5 | /avesweep meme solana 5\n"
        "/chains")


def handle_chains(chat_id):
    chains = ["solana", "ethereum", "bsc", "base", "arbitrum", "optimism", "polygon", "avalanche"]
    send_message(chat_id, "Supported Chains:\n\n" + "\n".join(f"- {c}" for c in chains))


def handle_ave(chat_id, text):
    parts = text.split()
    if len(parts) == 1:
        return send_message(chat_id, "Usage: /ave <token> [chain]")
    token = parts[1].lower()
    chain = parts[2].lower() if len(parts) > 2 else "solana"
    send_message(chat_id, f"Analyzing {token.upper()}...")
    try:
        report = ave_monitor.analyze_single_token(token, chain)
        send_message(chat_id, format_report(report))
    except Exception as e:
        send_message(chat_id, f"Error: {e}")


def handle_ave_watch(chat_id, text):
    parts = text.split()
    if len(parts) < 4:
        return send_message(chat_id, "Usage: /ave watch <token> <chain>")
    send_message(chat_id, watchlist_add(chat_id, parts[2], parts[3]))


def handle_ave_unwatch(chat_id, text):
    parts = text.split()
    if len(parts) < 4:
        return send_message(chat_id, "Usage: /ave unwatch <token> <chain>")
    send_message(chat_id, watchlist_remove(chat_id, parts[2], parts[3]))


def handle_ave_list(chat_id):
    send_message(chat_id, watchlist_list(chat_id))


def handle_avesweep(chat_id, text):
    parts = text.split()
    valid_chains = {"solana", "ethereum", "bsc", "base", "arbitrum", "optimism", "polygon", "avalanche"}

    category = "all"
    chain = "solana"
    limit = 5

    try:
        if len(parts) >= 2:
            first = parts[1].lower()
            if first in valid_chains:
                chain = first
                if len(parts) > 2:
                    limit = int(parts[2])
            else:
                category = first
                if len(parts) > 2:
                    chain = parts[2].lower()
                if len(parts) > 3:
                    limit = int(parts[3])
    except ValueError:
        return send_message(chat_id, "Usage: /avesweep [category|chain] [chain] [n]")

    scope = f"{chain} network-wide" if category == "all" else f"{category} on {chain}"
    send_message(chat_id, f"Sweeping {scope}...")
    try:
        results = ave_monitor.sweep_scan(category, chain, limit)
        lines = [f"Sweep: {scope.upper()}\n"]
        for i, r in enumerate(results[:10], 1):
            s = r["score"]
            alert = {"green": "🟢", "yellow": "🟡", "orange": "🟠", "red": "🔴"}.get(s["alert_level"], "-")
            lines.append(f"{i}. {r['token'].upper()} | {s['total']}/100 [{alert}]")
        send_message(chat_id, "\n".join(lines))
    except Exception as e:
        send_message(chat_id, f"Error: {e}")


def process_update(update):
    if "message" not in update:
        return
    message = update["message"]
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()
    if not text:
        return
    if text == "/start":
        handle_start(chat_id)
    elif text == "/help":
        handle_help(chat_id)
    elif text == "/chains":
        handle_chains(chat_id)
    elif text == "/ave list":
        handle_ave_list(chat_id)
    elif text.startswith("/ave watch "):
        handle_ave_watch(chat_id, text)
    elif text.startswith("/ave unwatch "):
        handle_ave_unwatch(chat_id, text)
    elif text.startswith("/ave "):
        handle_ave(chat_id, text)
    elif text.startswith("/avesweep "):
        handle_avesweep(chat_id, text)


def main():
    global OFFSET
    print("Ave Bot Starting...")
    if not TOKEN:
        print("TELEGRAM_BOT_TOKEN not set")
        return
    threading.Thread(target=check_watchlists, daemon=True).start()
    try:
        r = requests.get(f"{BASE_URL}/getMe")
        if r.ok:
            print(f"Connected as @{r.json()['result']['username']}")
        else:
            print("Connection failed")
            return
    except Exception as e:
        print(f"Error: {e}")
        return
    print("Waiting for messages...")
    while True:
        try:
            r = requests.get(f"{BASE_URL}/getUpdates",
                           params={"offset": OFFSET, "limit": 10, "timeout": 30})
            if not r.ok:
                time.sleep(5)
                continue
            for update in r.json().get("result", []):
                OFFSET = update["update_id"] + 1
                process_update(update)
            time.sleep(1)
        except Exception as e:
            print(f"[main loop] Error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
