#!/bin/bash

# Mint NetScout SIGINT PRO — Unified GUI Launcher
# Handles privilege escalation and orchestrates Backend + Frontend

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

# Cleanup function
cleanup() {
    echo "[*] Shutting down Intelligence Engine..."
    if [ ! -z "$BACKEND_PID" ]; then
        sudo kill $BACKEND_PID 2>/dev/null || true
    fi
    exit
}

# Trap signals for cleanup
trap cleanup SIGINT SIGTERM EXIT

# 1. Start Backend (Privileged)
echo "[*] Starting Intelligence Engine..."

# Proactively clear port 5000 before starting
PORT=5000
PID=$(sudo lsof -t -i:$PORT 2>/dev/null)
if [ ! -z "$PID" ]; then
    echo "[*] Clearing stale process on port $PORT (PID: $PID)..."
    sudo kill -9 $PID 2>/dev/null || true
    sleep 1
fi

export NETSCOUT_GUI_MODE=1
LOG_FILE="/tmp/netscout_backend.log"
> "$LOG_FILE"

# Run backend with sudo and capture output
sudo env PYTHONPATH="$DIR/mint-netscout-main" NETSCOUT_GUI_MODE=1 "$DIR/mint-netscout-main/.venv/bin/python3" -m backend.api.server > "$LOG_FILE" 2>&1 &
BACKEND_PID=$!

# 2. Wait for backend to be ready
echo "[*] Waiting for backend to initialize..."
MAX_RETRIES=20
COUNT=0
until curl -s http://localhost:5000/api/status > /dev/null; do
    sleep 1
    COUNT=$((COUNT + 1))
    if [ $COUNT -ge $MAX_RETRIES ]; then
        echo "[!] Error: Backend failed to start."
        echo "[*] --- Backend Log (Last 20 lines) ---"
        tail -n 20 "$LOG_FILE"
        echo "[*] ------------------------------------"
        sudo kill $BACKEND_PID 2>/dev/null || true
        exit 1
    fi
done

# 3. Start Frontend (Electron as current User)
echo "[*] Launching Dashboard GUI..."
cd netscout-react
# We run this as the current user, so it has access to the X server/DISPLAY
npm run gui
