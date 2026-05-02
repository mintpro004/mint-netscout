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
PID=$(sudo lsof -t -i:$PORT 2>/dev/null || echo "")
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
echo "[*] Waiting for Intelligence Engine to initialize..."
MAX_RETRIES=30
COUNT=0
READY=0
while [ $COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:5000/api/status > /dev/null; then
        READY=1
        break
    fi
    sleep 1
    COUNT=$((COUNT + 1))
    if [ $((COUNT % 5)) -eq 0 ]; then
        echo "[*] Still waiting... ($COUNT/$MAX_RETRIES)"
    fi
done

if [ $READY -eq 0 ]; then
    echo "[!] Error: Backend failed to respond after ${MAX_RETRIES}s."
    echo "[*] --- Backend Log (Last 30 lines) ---"
    tail -n 30 "$LOG_FILE"
    echo "[*] ------------------------------------"
    sudo kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi

echo "[+] Intelligence Engine is READY."

# 3. Start Frontend (Electron as current User)
echo "[*] Launching Dashboard GUI..."
cd netscout-react

# Proactively fix Node path for NVM users in the launcher
if ! command -v npm >/dev/null 2>&1; then
    # Try common NVM paths
    NVM_NODE=$(find "$HOME/.config/nvm/versions/node/" -name node -type f -executable | sort -V | tail -n 1 2>/dev/null || true)
    if [ -n "$NVM_NODE" ]; then
        export PATH="$(dirname "$NVM_NODE"):$PATH"
    fi
fi

# Compatibility env vars for Chromebook/Crostini
export QT_X11_NO_MITSHM=1
export _X11_NO_MITSHM=1
export GDK_BACKEND=x11
export ELECTRON_DISABLE_GPU=1
export DISPLAY=${DISPLAY:-:0}
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}

# Chrome/Electron Stability Flags
export CHROME_DEVEL_CONFIG=1
export LIBGL_ALWAYS_SOFTWARE=1
export MESA_LOADER_DRIVER_OVERRIDE=swrast

# Check if we need to wrap in dbus-run-session
if command -v dbus-run-session >/dev/null 2>&1 && [ -z "$DBUS_SESSION_BUS_ADDRESS" ]; then
    echo "[*] Wrapping Electron in dbus-run-session..."
    dbus-run-session -- npm run gui
else
    # We run this as the current user, so it has access to the X server/DISPLAY
    npm run gui
fi
