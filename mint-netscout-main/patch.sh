#!/usr/bin/env bash
# NetScout Emergency Fix — Run: sudo bash patch.sh
set -euo pipefail
G='\033[0;32m';C='\033[0;36m';Y='\033[1;33m';B='\033[1m';N='\033[0m'
ok(){ echo -e "${G}[OK]${N}    $1"; }
step(){ echo -e "\n${B}${C}▶ $1${N}"; }

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -n "${SUDO_USER:-}" ]] && chown -R "$SUDO_USER":"$SUDO_USER" "$DIR"

step "Patching fingerprint.py (OUIDatabase cache path)"
python3 - << 'PY'
import sys,os
p='/'+'/'.join(__file__.split('/')[:-1] if False else [])+'' # unused
import sys
path=sys.argv[1] if len(sys.argv)>1 else ''
# Find fingerprint.py
import subprocess
result=subprocess.run(['find',os.environ.get('DIR','.'),'backend','-name','fingerprint.py','-not','-path','*/venv/*'],capture_output=True,text=True)
files=[f for f in result.stdout.strip().split('\n') if f]
for path in files:
    with open(path) as f: src=f.read()
    if 'cache_path or os.path.join("data"' in src:
        old='        self.cache_path = cache_path or os.path.join("data", "oui_cache.json")'
        proj='os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))'
        new=f'        _root={proj}\n        _default=os.path.join(_root,"data","oui_cache.json")\n        os.makedirs(os.path.join(_root,"data"),exist_ok=True)\n        self.cache_path=os.path.abspath(cache_path or _default)'
        src=src.replace(old,new)
        # remove redundant makedirs in _load_cache
        src=src.replace('        cache_dir = os.path.dirname(self.cache_path)\n        if cache_dir:\n            os.makedirs(cache_dir, exist_ok=True)\n            \n        ','        ')
        with open(path,'w') as f: f.write(src)
        print(f"  patched: {path}")
    elif 'os.path.abspath(__file__)' in src:
        print(f"  already patched: {path}")
    else:
        print(f"  WARN: pattern not found in {path}")
PY
ok "fingerprint.py done"

step "Patching models.py (absolute DB path)"
python3 - << 'PY'
import subprocess,os,re
result=subprocess.run(['find',os.environ.get('DIR','.'),'backend','-name','models.py','-not','-path','*/venv/*'],capture_output=True,text=True)
for path in [f for f in result.stdout.strip().split('\n') if f]:
    with open(path) as f: src=f.read()
    if '_PROJECT_ROOT' in src:
        print(f"  already patched: {path}"); continue
    old='DB_PATH = os.environ.get("NETSCOUT_DB", os.path.join("data", "netscout.db"))\nengine = create_engine(f"sqlite:///{DB_PATH}", echo=False)'
    if old not in src:
        print(f"  pattern not found: {path}"); continue
    new='_PROJECT_ROOT=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))\n_DATA_DIR=os.path.join(_PROJECT_ROOT,"data")\nos.makedirs(_DATA_DIR,exist_ok=True)\nDB_PATH=os.environ.get("NETSCOUT_DB",os.path.join(_DATA_DIR,"netscout.db"))\nengine=create_engine(f"sqlite:///{DB_PATH}",echo=False)'
    with open(path,'w') as f: f.write(src.replace(old,new))
    print(f"  patched: {path}")
PY
ok "models.py done"

step "Patching server.py (SocketIO stability + scan logic)"
python3 - << 'PY'
import subprocess,os
result=subprocess.run(['find',os.environ.get('DIR','.'),'backend','-name','server.py','-not','-path','*/venv/*'],capture_output=True,text=True)
for path in [f for f in result.stdout.strip().split('\n') if f]:
    with open(path) as f: src=f.read()
    changed=False
    old='socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")'
    if old in src:
        src=src.replace(old,'socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet", ping_timeout=60, ping_interval=25, max_http_buffer_size=1048576, logger=False, engineio_logger=False)')
        changed=True; print(f"  fixed SocketIO: {path}")
    old2='device_repo.mark_all_offline()'
    if old2 in src:
        src=src.replace(old2,'found_macs={d["mac"] for d in results if d.get("mac")}\n                device_repo.mark_offline_except(found_macs)')
        changed=True; print(f"  fixed mark_all_offline: {path}")
    if changed:
        with open(path,'w') as f: f.write(src)
PY
ok "server.py done"

step "Adding mark_offline_except to models.py"
python3 - << 'PY'
import subprocess,os
result=subprocess.run(['find',os.environ.get('DIR','.'),'backend','-name','models.py','-not','-path','*/venv/*'],capture_output=True,text=True)
for path in [f for f in result.stdout.strip().split('\n') if f]:
    with open(path) as f: src=f.read()
    if 'mark_offline_except' in src:
        print(f"  already present: {path}"); continue
    if 'def mark_all_offline' not in src:
        print(f"  mark_all_offline not found: {path}"); continue
    method='''
    def mark_offline_except(self, active_macs: set):
        try:
            for device in self.db.query(Device).all():
                if device.mac not in active_macs:
                    device.is_up = False
            self.db.commit()
        except Exception:
            self.db.rollback()
'''
    idx=src.index('    def mark_all_offline')
    end=src.index('\n    def ',idx+1)
    src=src[:end]+'\n'+method+src[end:]
    with open(path,'w') as f: f.write(src)
    print(f"  added: {path}")
PY
ok "mark_offline_except done"

step "Deploying new React dashboard"
FBUILD="$DIR/frontend_build"
mkdir -p "$FBUILD"
cp "$DIR/frontend_build/index.html" "$FBUILD/index.html" 2>/dev/null || true
ok "Dashboard deployed → frontend_build/index.html"

[[ -n "${SUDO_USER:-}" ]] && chown -R "$SUDO_USER":"$SUDO_USER" "$DIR"

echo ""
echo -e "${G}${B}══════════════════════════════════${N}"
echo -e "${G}${B}  ✅ All patches applied!${N}"
echo -e "${G}${B}══════════════════════════════════${N}"
echo -e "\n  ${C}sudo bash setup.sh start${N}"
echo ""
