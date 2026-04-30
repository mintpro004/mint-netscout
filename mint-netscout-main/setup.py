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

def run_cmd(cmd, as_sudo=False):
    if as_sudo and os.getuid() != 0:
        cmd = f"sudo {cmd}"
    try:
        subprocess.check_call(cmd, shell=True)
        return True
    except subprocess.CalledProcessError:
        return False

def setup():
    system = platform.system()
    log(f"Detected System: {system}")
    
    # 1. OS-Specific System Dependencies
    if system == "Linux":
        log("Checking for system dependencies (libpcap, etc.)...")
        if run_cmd("which apt-get"):
            run_cmd("apt-get update && apt-get install -y libpcap-dev python3-pip python3-venv python3-full lsof curl", as_sudo=True)
    
    # 2. Virtual Environment Setup (Mandatory for reliability on modern Linux/Chromebook)
    venv_dir = os.path.join(os.getcwd(), ".venv")
    log(f"Configuring Virtual Environment: {venv_dir}")
    
    if os.path.exists(venv_dir):
        log("Cleaning up old environment...")
        shutil.rmtree(venv_dir)
        
    if not run_cmd(f"{sys.executable} -m venv {venv_dir}"):
        error("Failed to create virtual environment. Please install python3-venv.")
    
    active_python = os.path.join(venv_dir, "bin", "python")
    if system == "Windows":
        active_python = os.path.join(venv_dir, "Scripts", "python.exe")
            
    # 3. Install Python Dependencies
    log("Installing Python dependencies into virtual environment...")
    pip_base = f"{active_python} -m pip install --quiet --default-timeout=100 --retries 5"
    
    run_cmd(f"{pip_base} --upgrade pip")
    if not run_cmd(f"{pip_base} -r requirements.txt"):
        error("Failed to install dependencies in virtual environment.")

    # 4. Linux Capabilities (Raw Socket Access)
    if system == "Linux":
        log(f"Setting network capabilities on {active_python}...")
        # Resolve symlink to actual binary for setcap
        real_py = os.path.realpath(active_python)
        if not run_cmd(f"setcap cap_net_raw,cap_net_admin+eip {real_py}", as_sudo=True):
            log("Note: Could not set capabilities. Sudo will be required for scans.")

    # 5. Create Universal Launcher
    launcher = "netscout.sh"
    log(f"Generating launcher: {launcher}")
    with open(launcher, "w") as f:
        f.write("#!/bin/bash\n\n")
        f.write("DIR=\"$( cd \"$( dirname \"${BASH_SOURCE[0]}\" )\" >/dev/null 2>&1 && pwd )\"\n")
        f.write("cd \"$DIR\"\n\n")
        f.write("# Self-Healing: Clear port 5000 if already in use\n")
        f.write("PID=$(sudo lsof -t -i:5000)\n")
        f.write("if [ ! -z \"$PID\" ]; then\n")
        f.write("    echo \"[*] Clearing stale NetScout instance (PID: $PID)...\"\n")
        f.write("    sudo kill -9 $PID 2>/dev/null\n")
        f.write("    sleep 1\n")
        f.write("fi\n\n")
        f.write("echo '🛰️  Launching Mint NetScout SIGINT PRO...'\n")
        f.write(f"sudo \"{active_python}\" -m backend.api.server\n")
    
    run_cmd(f"chmod +x {launcher}")

    # 6. Initialize Database
    log("Initializing local database...")
    run_cmd(f"PYTHONPATH={os.getcwd()} {active_python} -c 'from backend.database.models import init_db; init_db()'")

    # 7. Final Instructions
    print("\n" + "="*60)
    print("🚀  MINT NETSCOUT SETUP COMPLETE")
    print("="*60)
    print(f"\n[+] EASY LAUNCH:   ./{launcher}")
    print(f"[+] MANUAL START:  sudo {active_python} -m backend.api.server")
    print("[+] DASHBOARD:     http://localhost:5000")
    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    setup()
