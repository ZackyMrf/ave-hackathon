#!/bin/bash

# 🚀 Advanced Monitoring System - Startup Script
# Spins up all services: API Backend, Telegram Bot, Frontend Dev Server

set -e

echo "================================================"
echo "🚀 Ave Claw Advanced Monitoring System"
echo "================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Load .env file
echo "[*] Loading environment variables..."
if [ -f ".env" ]; then
    export $(cat .env | xargs)
    echo -e "${GREEN}✓ .env file loaded${NC}"
fi

# Check environment
echo "[*] Checking environment..."

if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo -e "${RED}[ERROR] TELEGRAM_BOT_TOKEN not set${NC}"
    echo "Export it: export TELEGRAM_BOT_TOKEN='your_token'"
    exit 1
fi

if [ -z "$AVE_API_KEY" ]; then
    echo -e "${RED}[ERROR] AVE_API_KEY not set${NC}"
    echo "Export it: export AVE_API_KEY='your_key'"
    exit 1
fi

echo -e "${GREEN}✓ Environment variables set${NC}"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}[*] Shutting down services...${NC}"
    kill $BACKEND_PID $BOT_PID $FRONTEND_PID 2>/dev/null || true
    echo -e "${GREEN}[✓] Cleanup complete${NC}"
}

trap cleanup EXIT

# Start Backend API Server
echo "[1/3] Starting FastAPI Backend Server..."
python -m uvicorn api_server:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
sleep 2
echo -e "${GREEN}✓ Backend running (PID: $BACKEND_PID)${NC}"
echo ""

# Start Telegram Bot
echo "[2/3] Starting Telegram Bot Worker..."
python telegram_bot_advanced.py &
BOT_PID=$!
sleep 2
echo -e "${GREEN}✓ Bot running (PID: $BOT_PID)${NC}"
echo ""

# Start Frontend Dev Server
echo "[3/3] Starting Frontend Dev Server..."
cd frontend
npm run dev -- --host 0.0.0.0 --port 5173 &
FRONTEND_PID=$!
sleep 3
echo -e "${GREEN}✓ Frontend running (PID: $FRONTEND_PID)${NC}"
echo ""

echo "================================================"
echo -e "${GREEN}✓ All services running!${NC}"
echo "================================================"
echo ""
echo "📱 Web Dashboard:   http://localhost:5173"
echo "🔌 API Backend:     http://localhost:8000"
echo "🤖 Telegram Bot:    @YourBotHandle"
echo ""
echo "Press Ctrl+C to stop all services..."
echo ""

# Keep script running
wait
