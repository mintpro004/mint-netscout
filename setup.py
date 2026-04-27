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

    # 1. OS-Specific System Dependencies
    if system == "Linux":
        log("Checking for system dependencies (libpcap, etc.)...")
        if run_cmd("which apt-get"):
            run_cmd("sudo apt-get update && sudo apt-get install -y libpcap-dev python3-pip python3-venv")
    
    # 2. Install Python Dependencies
    log("Installing Python dependencies...")
    
    # Try standard installation first with the override flag
    pip_cmd = f"{sys.executable} -m pip install -r requirements.txt --break-system-packages"
    
    if not run_cmd(pip_cmd):
        log("System-wide install failed. Attempting Virtual Environment setup (Self-Healing)...")
        
        venv_dir = os.path.join(os.getcwd(), ".venv")
        if not os.path.exists(venv_dir):
            if not run_cmd(f"{sys.executable} -m venv {venv_dir}"):
                error("Failed to create virtual environment. Please install python3-venv.")
        
        venv_python = os.path.join(venv_dir, "bin", "python")
        if system == "Windows":
            venv_python = os.path.join(venv_dir, "Scripts", "python.exe")
            
        log(f"Installing dependencies into venv: {venv_dir}")
        if not run_cmd(f"{venv_python} -m pip install -r requirements.txt"):
            error("Failed to install dependencies in virtual environment.")
        
        # Create a launcher script
        launcher = "netscout.sh"
        with open(launcher, "w") as f:
            f.write(f"#!/bin/bash\nsudo {venv_python} -m backend.api.server\n")
        run_cmd(f"chmod +x {launcher}")
        log(f"✅ Created launcher: ./{launcher}")
        final_run_msg = f"./{launcher}"
    else:
        final_run_msg = "python3 -m backend.api.server"

    # 3. Linux Capabilities (Security Hardening)
    target_py = os.path.realpath(sys.executable)
    if system == "Linux":
        log(f"Setting capabilities for raw socket access on {target_py}...")
        if not run_cmd(f"sudo setcap cap_net_raw,cap_net_admin+eip {target_py}"):
            log("Note: Could not set capabilities. You may need to run with sudo.")

    # 4. Create Universal Launcher (Convenience)
    launcher = "netscout.sh"
    with open(launcher, "w") as f:
        f.write("#!/bin/bash\n")
        f.write(f"echo '🛰️ Launching Mint NetScout SIGINT PRO...'\n")
        f.write(f"sudo {target_py} -m backend.api.server\n")
    run_cmd(f"chmod +x {launcher}")
    log(f"✅ Created launcher: ./{launcher}")

    # 5. Initialize Database
    log("Initializing local database...")
    try:
        # We try to import locally if possible
        sys.path.insert(0, os.getcwd())
        from backend.database.models import init_db
        init_db()
    except Exception as e:
        log(f"Database init notice: {e} (Will be initialized on first run)")

    log(f"\n✅ Setup Complete! Run the tool with: {final_run_msg}")

if __name__ == "__main__":
    setup()
