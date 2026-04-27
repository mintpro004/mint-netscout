#!/bin/bash
# Mint NetScout Smart Launcher
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

# 1. Port Self-Healing
PORT=5000
PID=$(sudo lsof -t -i:$PORT)
if [ ! -z "$PID" ]; then
    echo "[*] Port $PORT busy. Clearing stale instance (PID: $PID)..."
    sudo kill -9 $PID 2>/dev/null
    sleep 1
fi

echo '🛰️  Launching Mint NetScout SIGINT PRO...'
# Run using the venv python with sudo for raw socket access
sudo "$DIR/.venv/bin/python3" -m backend.api.server
