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

# 2. Install System Dependencies
log "Updating system and installing base dependencies..."
apt-get update -qq || log "Warning: apt-get update failed, attempting to continue..."
apt-get install -y -qq libpcap-dev python3-pip python3-venv python3-full lsof curl > /dev/null || \
  error "Failed to install system dependencies. Ensure you have an internet connection and are on a Debian-based system."

# 3. Create/Reset Virtual Environment
log "Configuring dedicated Virtual Environment (.venv)..."
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

# Ensure correct ownership before proceeding
if [ -n "$SUDO_USER" ]; then
    chown -R "$SUDO_USER":"$SUDO_USER" "$DIR"
fi

# Clean up old venv if it exists
rm -rf .venv

# Create venv as the original user to avoid permission issues later, 
# but we need it for the root-run server too.
# Actually, better to create it and then fix permissions.
python3 -m venv .venv
if [ -n "$SUDO_USER" ]; then
    chown -R "$SUDO_USER":"$SUDO_USER" .venv
fi

# 4. Install Python Requirements
log "Installing intelligence modules into virtual environment (with retries)..."
# Run pip as the user who invoked sudo if possible, to keep cache in their home
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

# 5. Initialize Database
log "Initializing intelligence database..."
PYTHONPATH=$DIR "$DIR/.venv/bin/python3" -c "from backend.database.models import init_db; init_db()"
if [ -n "$SUDO_USER" ]; then
    chown -R "$SUDO_USER":"$SUDO_USER" data/ 2>/dev/null || true
fi

# 6. Generate Smart Launcher
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
sudo "\$DIR/.venv/bin/python3" -m backend.api.server
EOF

chmod +x netscout.sh
if [ -n "$SUDO_USER" ]; then
    chown "$SUDO_USER":"$SUDO_USER" netscout.sh
fi

# 7. Set Capabilities (Optional fallback for non-sudo runs)
log "Setting network capabilities on venv binary..."
REAL_PY="$(readlink -f $DIR/.venv/bin/python3)"
setcap cap_net_raw,cap_net_admin+eip "$REAL_PY" || log "Note: Could not set capabilities (Normal for some Chromebook/Container envs)."

echo -e "\n${GREEN}============================================================${NC}"
success "MINT NETSCOUT INSTALLATION COMPLETE"
echo -e "${GREEN}============================================================${NC}"
echo -e "\n[+] LAUNCH COMMAND: ${BLUE}./netscout.sh${NC}"
echo -e "[+] DASHBOARD:      ${BLUE}http://localhost:5000${NC}"
echo -e "\n${GREEN}============================================================${NC}\n"
