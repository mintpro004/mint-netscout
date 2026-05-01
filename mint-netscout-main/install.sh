#!/bin/bash

# Mint NetScout SIGINT PRO — Robust Installer
# Optimized for Linux, Chromebook (Crostini), and Debian 12+

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() { echo -e "${BLUE}[*]${NC} $1"; }
success() { echo -e "${GREEN}[+]${NC} $1"; }
error() { echo -e "${RED}[!] ERROR:${NC} $1"; exit 1; }

log "Starting Mint NetScout SIGINT PRO Installation..."

# 1. Check for Sudo
if [ "$EUID" -ne 0 ]; then
  error "Please run the installer with sudo: sudo bash install.sh"
fi

# 2. Check Node.js Version
log "Checking Node.js version..."
if command -v node >/dev/null 2>&1; then
    NODE_VER=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
    if [ "$NODE_VER" -lt 20 ]; then
        log "Warning: Node.js v20+ is recommended (detected v$NODE_VER). Frontend build may fail."
    fi
else
    log "Warning: Node.js not found. GUI app setup will be skipped."
fi

# 3. Install System Dependencies
log "Updating system and installing base dependencies..."
apt-get update -qq || log "Warning: apt-get update failed, attempting to continue..."
apt-get install -y -qq libpcap-dev python3-pip python3-venv python3-full lsof curl > /dev/null || \
  error "Failed to install system dependencies. Ensure you have an internet connection and are on a Debian-based system."

# 4. Create/Reset Virtual Environment
log "Configuring dedicated Virtual Environment (.venv)..."
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
PARENT_DIR="$(dirname "$DIR")"
cd "$DIR"

# Ensure the invoking user owns the project directory before we start
if [ -n "$SUDO_USER" ]; then
    chown -R "$SUDO_USER":"$SUDO_USER" "$PARENT_DIR"
fi

# Clean up old venv if it exists
rm -rf .venv

# Create venv
python3 -m venv .venv
if [ -n "$SUDO_USER" ]; then
    chown -R "$SUDO_USER":"$SUDO_USER" .venv
fi

# 5. Install Python Requirements
log "Installing intelligence modules into virtual environment (with retries)..."
PIP_CMD="$DIR/.venv/bin/python3 -m pip install --quiet --upgrade pip"
if [ -n "$SUDO_USER" ]; then
    sudo -u "$SUDO_USER" $PIP_CMD
else
    $PIP_CMD
fi

INSTALL_CMD="$DIR/.venv/bin/python3 -m pip install --quiet --default-timeout=100 --retries 5 -r requirements.txt"
if [ -n "$SUDO_USER" ]; then
    log "Installing requirements as $SUDO_USER..."
    sudo -u "$SUDO_USER" $INSTALL_CMD || error "Pip installation failed."
else
    $INSTALL_CMD || error "Pip installation failed."
fi

# 6. Initialize Database
log "Initializing intelligence database..."
PYTHONPATH=$DIR "$DIR/.venv/bin/python3" -c "from backend.database.models import init_db; init_db()"
if [ -n "$SUDO_USER" ]; then
    chown -R "$SUDO_USER":"$SUDO_USER" data/ 2>/dev/null || true
fi

# 7. Generate Smart Launcher
log "Generating self-healing launcher (netscout.sh)..."
cat <<EOF > netscout.sh
#!/bin/bash
# Mint NetScout Smart Launcher
DIR="\$( cd "\$( dirname "\${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "\$DIR"

# 1. Port Self-Healing
PORT=5000
PID=\$(sudo lsof -t -i:\$PORT)
if [ ! -z "\$PID" ]; then
    echo "[*] Port \$PORT busy. Clearing stale instance (PID: \$PID)..."
    sudo kill -9 \$PID 2>/dev/null
    sleep 1
fi

echo '🛰️  Launching Mint NetScout SIGINT PRO...'
# Run using the venv python with sudo for raw socket access
sudo env PYTHONPATH="\$DIR" NETSCOUT_GUI_MODE="\$NETSCOUT_GUI_MODE" "\$DIR/.venv/bin/python3" -m backend.api.server
EOF

chmod +x netscout.sh
if [ -n "$SUDO_USER" ]; then
    chown "$SUDO_USER":"$SUDO_USER" netscout.sh
fi

# 8. Set Capabilities (Optional fallback for non-sudo runs)
log "Setting network capabilities on venv binary..."
REAL_PY="$(readlink -f $DIR/.venv/bin/python3)"
setcap cap_net_raw,cap_net_admin+eip "$REAL_PY" || log "Note: Could not set capabilities (Normal for some Chromebook/Container envs)."

# 9. GUI Setup (Electron)
log "Configuring Standalone GUI (Electron)..."
if command -v npm >/dev/null 2>&1; then
    cd "$PARENT_DIR/netscout-react"
    # Double check permissions again before npm install
    if [ -n "$SUDO_USER" ]; then
        chown -R "$SUDO_USER":"$SUDO_USER" .
        sudo -u "$SUDO_USER" npm install --quiet || log "Warning: npm install failed. GUI might not start."
    else
        npm install --quiet
    fi
    cd "$DIR"
else
    log "Warning: npm not found. GUI app setup skipped. Please install Node.js/npm manually."
fi

# 10. Register Desktop Entry
log "Registering Desktop Entry..."
DESKTOP_DIR="/home/$SUDO_USER/.local/share/applications"
if [ -z "$SUDO_USER" ]; then
    DESKTOP_DIR="$HOME/.local/share/applications"
fi
mkdir -p "$DESKTOP_DIR"

# Update paths in .desktop file to absolute paths
sed -i "s|Exec=.*|Exec=$PARENT_DIR/launch-gui.sh|" "$PARENT_DIR/netscout.desktop"
sed -i "s|Icon=.*|Icon=$PARENT_DIR/netscout-react/public/favicon.svg|" "$PARENT_DIR/netscout.desktop"

cp "$PARENT_DIR/netscout.desktop" "$DESKTOP_DIR/"
if [ -n "$SUDO_USER" ]; then
    chown "$SUDO_USER":"$SUDO_USER" "$DESKTOP_DIR/netscout.desktop"
    chown -R "$SUDO_USER":"$SUDO_USER" "$PARENT_DIR"
fi
chmod +x "$PARENT_DIR/launch-gui.sh"

echo -e "\n${GREEN}============================================================${NC}"
success "MINT NETSCOUT INSTALLATION COMPLETE"
echo -e "${GREEN}============================================================${NC}"
echo -e "\n[+] GUI LAUNCHER:   ${BLUE}$DIR/../launch-gui.sh${NC}"
echo -e "[+] CLI LAUNCHER:   ${BLUE}./netscout.sh${NC}"
echo -e "[+] DESKTOP APP:    Available in your Application Menu"
echo -e "\n${GREEN}============================================================${NC}\n"
