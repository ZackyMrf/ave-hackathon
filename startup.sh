#!/usr/bin/env bash

# Unified startup script (backend + frontend + telegram bot)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

BACKEND_PID=""
BOT_PID=""
FRONTEND_PID=""

echo "================================================"
echo "Ave Monitoring System - Unified Startup"
echo "================================================"
echo ""

load_env() {
    if [ ! -f ".env" ]; then
        return
    fi

    while IFS= read -r line || [ -n "$line" ]; do
        line="${line#${line%%[![:space:]]*}}"
        if [ -z "$line" ] || [[ "$line" == \#* ]]; then
            continue
        fi
        if [[ "$line" == export* ]]; then
            line="${line#export }"
        fi
        if [[ "$line" != *=* ]]; then
            continue
        fi

        name="${line%%=*}"
        value="${line#*=}"
        name="${name%%[[:space:]]*}"
        value="${value%\"}"
        value="${value#\"}"
        value="${value%\'}"
        value="${value#\'}"
        export "$name=$value"
    done < ".env"
}

stop_listener() {
    local port="$1"
    if command -v lsof >/dev/null 2>&1; then
        local pids
        pids="$(lsof -ti tcp:"$port" -sTCP:LISTEN 2>/dev/null || true)"
        if [ -n "$pids" ]; then
            kill -9 $pids 2>/dev/null || true
            echo -e "${YELLOW}Stopped stale listener on :$port${NC}"
        fi
        return
    fi

    if command -v fuser >/dev/null 2>&1; then
        fuser -k "${port}/tcp" >/dev/null 2>&1 || true
    fi
}

cleanup() {
    echo ""
    echo -e "${YELLOW}[*] Shutting down services...${NC}"
    [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null || true
    [ -n "$BOT_PID" ] && kill "$BOT_PID" 2>/dev/null || true
    [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null || true
    echo -e "${GREEN}[✓] Cleanup complete${NC}"
}

trap cleanup EXIT INT TERM

echo "[*] Loading environment variables..."
load_env

if [ -z "${AVE_API_KEY:-}" ]; then
    echo -e "${RED}[ERROR] AVE_API_KEY is not set (.env or shell env)${NC}"
    exit 1
fi

PYTHON_BIN=""
if [ -x ".venv/bin/python" ]; then
    PYTHON_BIN=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    echo -e "${RED}[ERROR] Python not found${NC}"
    exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
    echo -e "${RED}[ERROR] npm not found${NC}"
    exit 1
fi

stop_listener 8000
stop_listener 5173

echo "[1/3] Starting API backend on :8000 ..."
"$PYTHON_BIN" -m uvicorn api_server:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
sleep 2
if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo -e "${RED}[ERROR] Backend exited early${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Backend running (PID: $BACKEND_PID)${NC}"

echo "[2/3] Starting Telegram bot ..."
if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
    "$PYTHON_BIN" telegram_bot_advanced.py &
    BOT_PID=$!
    sleep 2
    if kill -0 "$BOT_PID" 2>/dev/null; then
        echo -e "${GREEN}✓ Bot running (PID: $BOT_PID)${NC}"
    else
        echo -e "${YELLOW}[WARN] Bot exited early, continuing without bot${NC}"
        BOT_PID=""
    fi
else
    echo -e "${YELLOW}[WARN] TELEGRAM_BOT_TOKEN missing, bot skipped${NC}"
fi

echo "[3/3] Starting frontend on :5173 ..."
(
    cd frontend
    npm run dev -- --host 0.0.0.0 --port 5173
) &
FRONTEND_PID=$!
sleep 3
if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    echo -e "${RED}[ERROR] Frontend exited early${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Frontend running (PID: $FRONTEND_PID)${NC}"

echo ""
echo "================================================"
echo -e "${GREEN}✓ Services are up${NC}"
echo "================================================"
echo "Web: http://localhost:5173"
echo "API: http://localhost:8000"
echo "WS : ws://localhost:8000/ws/live-buysell"
echo ""
echo "Press Ctrl+C to stop all services"

wait
