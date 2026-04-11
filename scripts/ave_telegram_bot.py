#!/usr/bin/env python3
"""
Ave Accumulation Monitor - Telegram Bot Handler
Run via: python3 ave_telegram_bot.py
"""

import os
import sys
import json
import re
import subprocess
from typing import Optional, Dict, List

# Add parent directory to path to import ave_monitor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ave_monitor import AveAccumulationMonitor

class AveTelegramBot:
    """Telegram bot handler for Ave Accumulation Monitor"""
    
    def __init__(self):
        self.monitor = AveAccumulationMonitor()
        
    def parse_command(self, message: str) -> Optional[Dict]:
        """Parse Telegram message command"""
        message = message.strip()
        
        # Command: /ave <token> [chain]
        # Example: /ave TRUMP solana
        if message.startswith('/ave '):
            parts = message.split()
            if len(parts) >= 2:
                token = parts[1]
                chain = parts[2] if len(parts) > 2 else 'solana'
                return {
                    'command': 'single',
                    'token': token,
                    'chain': chain
                }
        
        # Command: /avesweep [category|chain] [chain] [top_n]
        # Examples:
        #   /avesweep
        #   /avesweep all solana 5
        #   /avesweep meme solana 5
        elif message.startswith('/avesweep'):
            parts = message.split()
            valid_chains = {'solana', 'ethereum', 'bsc', 'base', 'arbitrum', 'optimism', 'polygon', 'avalanche'}

            category = 'all'
            chain = 'solana'
            top_n = 5

            try:
                if len(parts) >= 2:
                    first = parts[1].lower()
                    if first in valid_chains:
                        chain = first
                        if len(parts) > 2:
                            top_n = int(parts[2])
                    else:
                        category = parts[1]
                        chain = parts[2] if len(parts) > 2 else 'solana'
                        if len(parts) > 3:
                            top_n = int(parts[3])
            except ValueError:
                return {
                    'command': 'sweep',
                    'category': category,
                    'chain': chain,
                    'top': 5
                }

            return {
                'command': 'sweep',
                'category': category,
                'chain': chain,
                'top': top_n
            }
        
        # Command: /avehelp
        elif message == '/avehelp' or message == '/ave_help':
            return {'command': 'help'}
        
        # Command: /avechains
        elif message == '/avechains':
            return {'command': 'chains'}
        
        return None
    
    def format_single_report_telegram(self, report: Dict) -> str:
        """Format single token report for Telegram"""
        if "error" in report:
            return f"❌ Error: {report['error']}"
        
        s = report["score"]
        sig = report["signals"]
        
        alert_emoji = {"green": "🟢", "yellow": "🟡", "orange": "🟠", "red": "🔴"}.get(s["alert_level"], "⚪")
        phase_emoji = {"bull": "🐂", "bear": "🐻", "consolidation": "➡️"}.get(s["market_phase"], "➡️")
        
        lines = [
            f"📊 *AVE ACCUMULATION MONITOR — {report['token'].upper()}*",
            "",
            f"🔗 Chain: `{report['chain']}`",
            f"💰 Price: ${report['price']:.4f} | 24h: {report['price_change_24h']:+.1f}%",
            f"🏦 TVL: ${report['tvl']/1e6:.2f}M | Holders: {report['holders']:,}",
            "",
            f"🎯 *ACCUMULATION SCORE: {s['total']}/100* {alert_emoji}",
            f"📉 Risk-Adjusted: {s['risk_adjusted']}/100 | Confidence: {s['confidence']}%",
            f"📈 Market Phase: {phase_emoji} {s['market_phase'].upper()}",
            "",
            "*SIGNAL BREAKDOWN:*",
            f"⚡ Volume Divergence: {sig['volume_divergence']}/30",
            f"📈 Volume Momentum: {sig['volume_momentum']}/25",
            f"🏦 TVL Stability: {sig['tvl_stability']}/20",
            f"👥 Holder Distribution: {sig['holder_distribution']}/15",
            f"💎 TVL Confidence: {sig['tvl_confidence']}/10",
            f"🐋 Whale Score: {sig['whale_score']}/40",
            f"📊 Anomaly: {sig['anomaly_score']}/27",
            f"📚 Pattern: {sig['pattern_match']}/8",
            "",
            "*WHALE ACTIVITY:*",
            f"🐋 {report['descriptions']['whale']}",
            "",
            f"📊 *Anomaly:* {report['descriptions']['anomaly']}",
            f"📚 *Pattern:* {report['descriptions']['pattern']}",
        ]
        
        # Top whales
        if report["whales"]:
            lines.extend(["", "*TOP WHALES:*"])
            for w in report["whales"][:5]:
                addr = w['address']
                short_addr = f"{addr[:6]}...{addr[-4:]}"
                lines.append(f"  `{short_addr}`: {w['balance_ratio']:.2f}%")
        
        # Next actions
        lines.extend(["", "*NEXT ACTIONS:*"])
        if s["risk_adjusted"] >= 75:
            lines.extend([
                "🔴 *STRONG CONVICTION* — Multiple signals firing!",
                "1️⃣ Monitor real-time for confirmation",
                "2️⃣ Watch for volume breakout >4x baseline",
                "3️⃣ Track whale follow-through in 2-4h"
            ])
        elif s["risk_adjusted"] >= 55:
            lines.extend([
                "🟠 *HIGH PROBABILITY WINDOW*",
                "1️⃣ Check again in 2 hours",
                "2️⃣ Monitor whale activity",
                "3️⃣ Watch holder growth acceleration"
            ])
        elif s["risk_adjusted"] >= 35:
            lines.extend([
                "🟡 *ACTIVE WATCH*",
                "1️⃣ Monitor daily",
                "2️⃣ Wait for more confirmation"
            ])
        else:
            lines.extend([
                "🟢 *BACKGROUND WATCH*",
                "1️⃣ No actionable pattern yet",
                "2️⃣ Check back in 24-48h"
            ])
        
        return "\n".join(lines)
    
    def format_sweep_report_telegram(self, results: List[Dict], category: str, chain: str) -> str:
        """Format sweep scan report for Telegram"""
        category_norm = str(category or 'all').strip().lower()
        scope_label = f"{chain} network-wide" if category_norm == 'all' else f"{category_norm} on {chain}"

        if not results:
            return f"❌ No tokens found for sweep scope '{scope_label}'"
        
        alert_emoji = {"green": "🟢", "yellow": "🟡", "orange": "🟠", "red": "🔴"}
        
        lines = [
            f"📊 *AVE ACCUMULATION SWEEP*",
            f"Scope: {scope_label.upper()}",
            f"Top {len(results)} results:",
            ""
        ]
        
        for i, r in enumerate(results, 1):
            s = r["score"]
            emoji = alert_emoji.get(s["alert_level"], "⚪")
            
            lines.append(f"#{i} *{r['token'].upper()}* | Score: {s['total']}/100 {emoji}")
            lines.append(f"   💰 ${r['price']:.4f} | TVL: ${r['tvl']/1e6:.1f}M")
            lines.append(f"   📊 Vol 24h: ${r['volume_24h']/1e6:.1f}M | Conf: {s['confidence']}%")
            
            # Multi-signal summary
            signals = []
            if s["whale_score"] >= 20:
                signals.append("🐋")
            if s["anomaly_score"] >= 8:
                signals.append("📊")
            if s["pattern_match"] >= 8:
                signals.append("📚")
            if s["volume_divergence"] >= 20:
                signals.append("⚡")
            
            if signals:
                lines.append(f"   🔥 Signals: {' '.join(signals)}")
            lines.append("")
        
        # Market sentiment
        avg_score = sum(r["score"]["risk_adjusted"] for r in results) / len(results)
        high_signals = sum(1 for r in results if r["score"]["alert_level"] in ["orange", "red"])
        
        lines.append("*📈 MARKET SENTIMENT:*")
        if avg_score >= 60:
            lines.append(f"Strong accumulation! {high_signals} tokens with high probability 🚀")
        elif avg_score >= 40:
            lines.append(f"Mixed signals. {high_signals} tokens need monitoring 👀")
        else:
            lines.append("Weak patterns. No immediate opportunities 💤")
        
        return "\n".join(lines)
    
    def get_help_text(self) -> str:
        """Get help text for Telegram"""
        return """📊 *AVE ACCUMULATION MONITOR BOT*

Detect smart money accumulation before price moves!

*COMMANDS:*

📈 */ave <token> [chain]*
   Single token analysis
   Example: `/ave TRUMP solana`
   Example: `/ave PEPE ethereum`

🔍 */avesweep [category|chain] [chain] [top_n]*
    Scan chain network-wide (default) with optional category filter
    Example: `/avesweep all solana 5`
   Example: `/avesweep meme ethereum 10`

📚 */avehelp*
   Show this help message

🌐 */avechains*
   List supported chains

*CATEGORIES:*
• `all` — Network-wide scan (default)
• `trending` — Trending tokens
• `meme` — Meme coins
• `defi` — DeFi tokens
• `gaming` — Gaming tokens
• `ai` — AI tokens

*SUPPORTED CHAINS:*
solana, ethereum, bsc, base, arbitrum, optimism, polygon, avalanche

*ALERT LEVELS:*
🟢 < 35 — Background watch
🟡 35-54 — Active watch
🟠 55-74 — High probability
🔴 75-100 — Strong conviction

⚠️ *Disclaimer:* This is an alpha detection tool, not financial advice. Always DYOR!"""
    
    def get_chains_text(self) -> str:
        """Get supported chains text"""
        chains = [
            ("solana", "⚡ Fast, low fees"),
            ("ethereum", "🔷 DeFi king"),
            ("bsc", "🟡 Binance chain"),
            ("base", "🔵 Coinbase L2"),
            ("arbitrum", "🟣 Ethereum L2"),
            ("optimism", "🔴 Ethereum L2"),
            ("polygon", "🟣 Layer 2"),
            ("avalanche", "🔺 Fast finality")
        ]
        
        lines = ["🌐 *SUPPORTED CHAINS:*", ""]
        for chain, desc in chains:
            lines.append(f"• `{chain}` — {desc}")
        
        lines.extend([
            "",
            "*Default chain:* `solana`",
            "*Usage:* Add chain name after token",
            "Example: `/ave TRUMP ethereum`"
        ])
        
        return "\n".join(lines)
    
    def handle_command(self, message: str) -> str:
        """Handle Telegram command and return response"""
        parsed = self.parse_command(message)
        
        if not parsed:
            return None  # Not an ave command
        
        cmd = parsed['command']
        
        if cmd == 'help':
            return self.get_help_text()
        
        elif cmd == 'chains':
            return self.get_chains_text()
        
        elif cmd == 'single':
            token = parsed['token']
            chain = parsed['chain']
            
            # Validate inputs
            if not re.match(r'^[a-zA-Z0-9_]+$', token) and len(token) < 40:
                return "❌ Invalid token symbol. Use letters/numbers only or full contract address."
            
            valid_chains = ['solana', 'ethereum', 'bsc', 'base', 'arbitrum', 'optimism', 'polygon', 'avalanche']
            if chain.lower() not in valid_chains:
                return f"❌ Unsupported chain: `{chain}`. Use: {', '.join(valid_chains)}"
            
            try:
                report = self.monitor.analyze_single_token(token, chain)
                return self.format_single_report_telegram(report)
            except Exception as e:
                return f"❌ Error analyzing {token}: {str(e)}"
        
        elif cmd == 'sweep':
            category = parsed['category']
            chain = parsed['chain']
            top_n = parsed['top']
            
            valid_categories = ['all', 'trending', 'meme', 'defi', 'gaming', 'ai', 'new']
            if category.lower() not in valid_categories:
                return f"❌ Invalid category: `{category}`. Use: {', '.join(valid_categories)}"
            
            valid_chains = ['solana', 'ethereum', 'bsc', 'base', 'arbitrum', 'optimism', 'polygon', 'avalanche']
            if chain.lower() not in valid_chains:
                return f"❌ Unsupported chain: `{chain}`. Use: {', '.join(valid_chains)}"
            
            if top_n < 1 or top_n > 20:
                return "❌ Top N must be between 1-20"
            
            try:
                results = self.monitor.sweep_scan(category, chain, top_n)
                return self.format_sweep_report_telegram(results, category, chain)
            except Exception as e:
                return f"❌ Error scanning sweep: {str(e)}"
        
        return "❌ Unknown command"


def main():
    """CLI test mode"""
    bot = AveTelegramBot()
    
    print("Ave Telegram Bot Handler")
    print("=" * 50)
    print()
    print("Test commands:")
    print("  /ave TRUMP solana")
    print("  /avesweep all solana 5")
    print("  /avehelp")
    print("  /avechains")
    print()
    
    # Test mode
    import sys
    if len(sys.argv) > 1:
        test_msg = " ".join(sys.argv[1:])
        print(f">>> Testing: {test_msg}")
        print()
        response = bot.handle_command(test_msg)
        if response:
            print(response)
        else:
            print("Not an ave command")
    else:
        print("Usage: python ave_telegram_bot.py '<command>'")
        print()
        print("Running help test:")
        print(bot.handle_command("/avehelp"))


if __name__ == "__main__":
    main()
