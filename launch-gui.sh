#!/bin/bash

# Mint NetScout SIGINT PRO — Unified GUI Launcher
# Handles privilege escalation and orchestrates Backend + Frontend

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

# 1. Privilege Escalation (sudo)
if [ "$EUID" -ne 0 ]; then
    echo "[*] Elevating privileges for deep network scanning..."
    # Use sudo since pkexec might not be available
    sudo env DISPLAY=$DISPLAY XAUTHORITY=$XAUTHORITY "$0" "$@"
    exit $?
fi

# 2. Start Backend
echo "[*] Starting Intelligence Engine..."
./mint-netscout-main/netscout.sh > /dev/null 2>&1 &
BACKEND_PID=$!

# Wait for backend to be ready
echo "[*] Waiting for backend to initialize..."
MAX_RETRIES=15
COUNT=0
until curl -s http://localhost:5000/api/status > /dev/null; do
    sleep 1
    COUNT=$((COUNT + 1))
    if [ $COUNT -ge $MAX_RETRIES ]; then
        echo "[!] Error: Backend failed to start."
        kill $BACKEND_PID 2>/dev/null
        exit 1
    fi
done

# 3. Start Frontend (Electron)
echo "[*] Launching Dashboard GUI..."
cd netscout-react
# Note: --no-sandbox is required when running Electron as root
npm run gui -- --no-sandbox

# 4. Cleanup on Exit
echo "[*] Shutting down..."
kill $BACKEND_PID 2>/dev/null || true
