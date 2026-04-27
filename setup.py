import os
import sys
import subprocess
import platform
import shutil

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
    
    # Track which python we are using for the launcher
    active_python = os.path.realpath(sys.executable)

    # 1. OS-Specific System Dependencies
    if system == "Linux":
        log("Checking for system dependencies (libpcap, etc.)...")
        if run_cmd("which apt-get"):
            run_cmd("sudo apt-get update && sudo apt-get install -y libpcap-dev python3-pip python3-venv")
    
    # 2. Install Python Dependencies
    log("Installing Python dependencies...")
    
    # Try standard installation first with override flag for PEP 668
    pip_cmd = f"{active_python} -m pip install -r requirements.txt --break-system-packages"
    
    if not run_cmd(pip_cmd):
        log("System-wide install restricted. Activating Self-Healing Virtual Environment...")
        
        venv_dir = os.path.join(os.getcwd(), ".venv")
        if not os.path.exists(venv_dir):
            if not run_cmd(f"{sys.executable} -m venv {venv_dir}"):
                error("Failed to create virtual environment. Please install python3-venv.")
        
        active_python = os.path.join(venv_dir, "bin", "python")
        if system == "Windows":
            active_python = os.path.join(venv_dir, "Scripts", "python.exe")
            
        log(f"Installing dependencies into venv: {venv_dir}")
        if not run_cmd(f"{active_python} -m pip install -r requirements.txt"):
            error("Failed to install dependencies in virtual environment.")

    # 3. Linux Capabilities (Raw Socket Access)
    if system == "Linux":
        log(f"Setting network capabilities on {active_python}...")
        # Resolve symlink to actual binary for setcap
        real_py = os.path.realpath(active_python)
        if not run_cmd(f"sudo setcap cap_net_raw,cap_net_admin+eip {real_py}"):
            log("Note: Could not set capabilities. Sudo will be required for scans.")

    # 4. Create Universal Launcher (Easy Start)
    launcher = "netscout.sh"
    with open(launcher, "w") as f:
        f.write("#!/bin/bash\n")
        f.write("echo '🛰️  Launching Mint NetScout SIGINT PRO...'\n")
        f.write(f"sudo {active_python} -m backend.api.server\n")
    run_cmd(f"chmod +x {launcher}")

    # 5. Initialize Database
    log("Initializing local database...")
    try:
        sys.path.insert(0, os.getcwd())
        from backend.database.models import init_db
        init_db()
    except Exception as e:
        log(f"Database will be initialized on first run.")

    # 6. Final Instructions
    print("\n" + "="*60)
    print("🚀  MINT NETSCOUT SETUP COMPLETE")
    print("="*60)
    print(f"\n[+] EASY LAUNCH:   ./{launcher}")
    print(f"[+] MANUAL START:  sudo {active_python} -m backend.api.server")
    print("[+] DASHBOARD:     http://localhost:5000")
    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    setup()
