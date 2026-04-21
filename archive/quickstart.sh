#!/bin/bash
# Ave Accumulation Monitor - Hackathon Quick Start
# Run this to setup everything in one command

set -e

echo "🦞 Ave Accumulation Monitor - Quick Setup"
echo "=========================================="
echo ""

# Check prerequisites
echo "📋 Checking prerequisites..."

if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 not found. Please install Python 3.11+"
    exit 1
fi

if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 not found. Please install pip"
    exit 1
fi

echo "✅ Python3 found"

# Check environment variables
echo ""
echo "🔑 Checking environment variables..."

if [ -z "$AVE_API_KEY" ]; then
    echo "⚠️  AVE_API_KEY not set"
    echo "   Get your key from: https://cloud.ave.ai/register"
    echo "   Then run: export AVE_API_KEY=your-key"
    MISSING_ENV=1
else
    echo "✅ AVE_API_KEY set"
fi

if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "⚠️  TELEGRAM_BOT_TOKEN not set"
    echo "   Get your token from: @BotFather"
    echo "   Then run: export TELEGRAM_BOT_TOKEN=your-token"
    MISSING_ENV=1
else
    echo "✅ TELEGRAM_BOT_TOKEN set"
fi

if [ ! -z "$MISSING_ENV" ]; then
    echo ""
    echo "❌ Please set missing environment variables and run again"
    exit 1
fi

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
pip3 install -q requests python-telegram-bot 2>/dev/null || echo "⚠️  Some packages may already be installed"
echo "✅ Dependencies installed"

# Check file structure
echo ""
echo "📁 Checking file structure..."

if [ ! -f "scripts/ave_monitor.py" ]; then
    echo "❌ scripts/ave_monitor.py not found"
    echo "   Make sure you're in the skill directory"
    exit 1
fi

if [ ! -f "telegram_bot.py" ]; then
    echo "❌ telegram_bot.py not found"
    exit 1
fi

echo "✅ File structure OK"

# Test API connection
echo ""
echo "🌐 Testing Ave.ai API connection..."
python3 -c "
import os
import sys
sys.path.insert(0, 'scripts')
from ave_monitor import AveAccumulationMonitor
monitor = AveAccumulationMonitor()
print('✅ API connection successful')
" || {
    echo "❌ API connection failed"
    echo "   Check your AVE_API_KEY"
    exit 1
}

# All checks passed
echo ""
echo "=========================================="
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo ""
echo "1. Run demo script:"
echo "   python3 demo/demo_script.py"
echo ""
echo "2. Start Telegram bot:"
echo "   screen -S ave-bot -dm python3 telegram_bot.py"
echo ""
echo "3. Test commands in Telegram:"
echo "   /ave jup solana"
echo "   /avesweep meme solana 5"
echo "   /ave watch pepe solana"
echo ""
echo "📖 Documentation:"
echo "   - README.md"
echo "   - SKILL_V2.md"
echo "   - demo/presentation.md"
echo ""
echo "🎉 Good luck in the hackathon!"
echo "=========================================="
