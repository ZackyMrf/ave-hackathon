#!/usr/bin/env python3
"""
Ave Accumulation Monitor - Telegram Integration Module
Integrates with OpenClaw message system
"""

import os
import sys

# Import the telegram bot handler
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ave_telegram_bot import AveTelegramBot

# Global bot instance
_bot = None

def get_bot() -> AveTelegramBot:
    """Get or create bot instance"""
    global _bot
    if _bot is None:
        _bot = AveTelegramBot()
    return _bot

def process_message(message_text: str) -> str:
    """
    Process incoming Telegram message
    Returns response text or None if not an ave command
    
    Usage in OpenClaw:
        from ave_telegram_integration import process_message
        
        response = process_message("/ave TRUMP solana")
        if response:
            send_message(response)
    """
    bot = get_bot()
    return bot.handle_command(message_text)

def is_ave_command(message_text: str) -> bool:
    """Check if message is an ave command"""
    text = message_text.strip()
    ave_commands = ['/ave ', '/avesweep ', '/avehelp', '/ave_help', '/avechains']
    return any(text.startswith(cmd) for cmd in ave_commands)

# Command handlers for easy integration
COMMAND_PREFIXES = {
    '/ave': 'Single token analysis',
    '/avesweep': 'Category sweep scan',
    '/avehelp': 'Show help',
    '/avechains': 'List supported chains'
}

def get_command_list() -> str:
    """Get formatted command list"""
    lines = ["📊 *AVE MONITOR COMMANDS:*", ""]
    for cmd, desc in COMMAND_PREFIXES.items():
        lines.append(f"`{cmd}` — {desc}")
    return "\n".join(lines)

if __name__ == "__main__":
    # Test mode
    print("Ave Telegram Integration Module")
    print("=" * 50)
    print()
    
    test_messages = [
        "/avehelp",
        "/avechains",
        "/ave TRUMP solana",
        "/avesweep meme solana 5",
        "random message"
    ]
    
    for msg in test_messages:
        print(f">>> Input: {msg}")
        print(f"Is ave command: {is_ave_command(msg)}")
        
        if is_ave_command(msg):
            response = process_message(msg)
            print(f"Response length: {len(response)} chars")
            print(f"Preview: {response[:200]}...")
        
        print()
