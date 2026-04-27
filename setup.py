import os
import sys
import subprocess
import platform

def log(msg):
    print(f"[*] {msg}")

def error(msg):
    print(f"[!] ERROR: {msg}")
    sys.exit(1)

def run_cmd(cmd):
    try:
        subprocess.check_call(cmd, shell=True)
        return True
    except subprocess.CalledProcessError:
        return False

def setup():
    system = platform.system()
    log(f"Detected System: {system}")

    # 1. Install Python Dependencies
    log("Installing dependencies from requirements.txt...")
    if not run_cmd(f"{sys.executable} -m pip install -r requirements.txt"):
        error("Failed to install dependencies.")

    # 2. OS-Specific Requirements
    if system == "Linux":
        log("Checking for libpcap (required for raw sockets)...")
        # Check for apt (Debian/Ubuntu)
        if run_cmd("which apt-get"):
            run_cmd("sudo apt-get update && sudo apt-get install -y libpcap-dev")
        
        log("Setting capabilities for raw socket access (avoids sudo)...")
        run_cmd(f"sudo setcap cap_net_raw,cap_net_admin+eip {sys.executable}")

    elif system == "Windows":
        log("Windows detected. Please ensure Npcap is installed for ARP scanning.")
        log("Download: https://npcap.com/#download")

    elif system == "Darwin":
        log("macOS detected. Installing libpcap via brew if available...")
        run_cmd("brew install libpcap")

    # 3. Initialize Database
    log("Initializing local database...")
    try:
        from backend.database.models import init_db
        init_db()
    except Exception as e:
        error(f"Failed to initialize database: {e}")

    log("✅ Setup Complete! Run the tool with: python3 -m backend.api.server")

if __name__ == "__main__":
    setup()
