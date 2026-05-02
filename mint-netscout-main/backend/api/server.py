"""
Mint NetScout API Server
=========================
Flask + SocketIO server for real-time network intelligence.
Provides REST endpoints and WebSocket events for the dashboard.
"""

from __future__ import annotations

import eventlet
eventlet.monkey_patch()

import json
import logging
import os
import sys
import threading
import webbrowser
import time
from pathlib import Path
from typing import Dict, List, Optional, Set
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.database.models import (
    get_db, init_db, Device, DeviceRepository, 
    AlertRepository, SiteIntelligence, SiteVisit
)
from backend.core.engine import DiscoveryEngine, get_local_network, check_permissions
from backend.modules.fingerprint import DeviceFingerprinter
from backend.modules.port_scanner import PortScanner
from backend.modules.monitor import MonitorWorker, NetworkAlert
from backend.modules.sniffer import TrafficSniffer
from backend.modules.router import RouterIntelligence

# ─── Setup ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)
logger = logging.getLogger("netscout.server")

app = Flask(__name__, static_folder="../../frontend_build")
CORS(app)
socketio = SocketIO(
    app, 
    cors_allowed_origins="*", 
    async_mode="eventlet",
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=1048576,
    logger=False,
    engineio_logger=False
)

# Shared instances
fingerprinter = DeviceFingerprinter()
port_scanner = PortScanner()
router_intel = RouterIntelligence()
monitor: Optional[MonitorWorker] = None
sniffer: Optional[TrafficSniffer] = None

def get_monitor():
    global monitor
    return monitor

# ─── Socket Events ────────────────────────────────────────────────────────────

@socketio.on("connect")
def on_connect():
    logger.info(f"🔌 Client connected: {request.sid} (Remote: {request.remote_addr})")
    _sync_sniffer_blocking()
    # Trigger a background scan if requested on connection
    if os.environ.get("NETSCOUT_AUTO_SCAN") == "1":
        trigger_scan_api()

def _sync_sniffer_blocking():
    if sniffer:
        db = get_db()
        try:
            blocked_macs = [d.mac for d in db.query(Device).filter_by(is_blocked=True).all()]
            sniffer.set_blocking(blocked_macs)
        finally:
            db.close()

@socketio.on("disconnect")
def on_disconnect(*args):
    logger.info(f"🔌 Client disconnected: {request.sid}")

@socketio.on_error_default
def default_error_handler(e):
    logger.error(f"❌ SocketIO Error: {str(e)}", exc_info=True)

def emit_alert(alert):
    """Callback from MonitorWorker to broadcast alert to all connected WebSocket clients."""
    db = get_db()
    try:
        alert_repo = AlertRepository(db)
        alert_repo.log_alert(alert.to_dict())
    finally:
        db.close()

    socketio.emit("alert", alert.to_dict())

    # Also emit device update if it's a join/leave
    if alert.alert_type in ("device_joined", "device_left", "scan_complete"):
        socketio.emit("scan_complete", {"message": alert.message})


# ─── REST API Endpoints ───────────────────────────────────────────────────────

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, "index.html")

@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Content-Security-Policy"] = "default-src 'self' 'unsafe-inline' 'unsafe-eval' https://fonts.googleapis.com https://fonts.gstatic.com https://cdnjs.cloudflare.com;"
    return response

@app.route("/api/router", methods=["GET"])
def get_router_info():
    """Identify and probe the network gateway."""
    info = router_intel.discover_gateway()
    if not info:
        return jsonify({"success": False, "error": "Could not identify gateway"}), 404
    return jsonify({"success": True, "router": info})

@app.route("/api/system/stats", methods=["GET"])
def get_system_stats():
    """Return hardware and OS stats for the host."""
    import psutil
    import platform
    return jsonify({
        "os": platform.system(),
        "release": platform.release(),
        "arch": platform.machine(),
        "cpu_count": psutil.cpu_count(),
        "memory_total": round(psutil.virtual_memory().total / (1024**3), 2), # GB
        "cpu_usage": psutil.cpu_percent(),
        "memory_usage": psutil.virtual_memory().percent,
    })

@app.route("/api/devices/add", methods=["POST"])
def add_device_manual():
    """Manually register a device."""
    data = request.get_json() or {}
    ip = data.get("ip")
    mac = data.get("mac", "").upper()
    if not ip:
        return jsonify({"success": False, "error": "IP is required"}), 400
    
    db = get_db()
    try:
        repo = DeviceRepository(db)
        device_data = {
            "ip": ip,
            "mac": mac,
            "hostname": data.get("hostname", "Manual Entry"),
            "vendor": data.get("vendor", "Generic"),
            "device_type": data.get("type", "unknown"),
            "is_trusted": True
        }
        repo.upsert_device(device_data)
        return jsonify({"success": True, "message": f"Device {ip} added successfully"})
    finally:
        db.close()

@app.route("/api/update/check", methods=["GET"])
def check_updates():
    """Real GitHub-based update checker."""
    import subprocess
    repo_url = "https://api.github.com/repos/mintpro004/mint-netscout/commits/main"
    current_version = "2.1.0-PRO"
    
    try:
        # Check if we are in a git repo to get local hash
        local_hash = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        
        # Query GitHub for the latest commit on main
        import urllib.request
        req = urllib.request.Request(repo_url, headers={"User-Agent": "NetScout-Updater"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            remote_hash = data.get("sha", "")
            
            update_available = local_hash != remote_hash
            
            return jsonify({
                "current_version": current_version,
                "latest_version": f"REV-{remote_hash[:7]}",
                "update_available": update_available,
                "local_sha": local_hash[:7],
                "remote_sha": remote_hash[:7],
                "last_checked": time.time(),
                "changelog": [
                    data.get("commit", {}).get("message", "New updates available on GitHub")
                ]
            })
    except Exception as e:
        logger.error(f"Update check failed: {e}")
        # Fallback to current state if offline or error
        return jsonify({
            "current_version": current_version,
            "latest_version": current_version,
            "update_available": False,
            "error": "Could not contact update server",
            "last_checked": time.time()
        })

@app.route("/api/devices", methods=["GET"])
def get_devices():
    """Return all discovered devices."""
    online_only = request.args.get("online", "false").lower() == "true"
    db = get_db()
    try:
        repo = DeviceRepository(db)
        devices = repo.get_all(online_only=online_only)
        return jsonify({
            "devices": [d.to_dict() for d in devices],
            "count": len(devices),
        })
    finally:
        db.close()

@app.route("/api/devices/<mac>/trust", methods=["POST"])
def trust_device(mac):
    data = request.get_json() or {}
    trusted = data.get("trusted", True)
    db = get_db()
    try:
        repo = DeviceRepository(db)
        device = repo.get_by_mac(mac)
        if not device:
            return jsonify({"success": False, "error": "Device not found"}), 404
        repo.trust_device(mac, trusted)
        return jsonify({"success": True, "mac": mac, "trusted": trusted})
    except Exception as e:
        db.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        db.close()

@app.route("/api/devices/<mac>/register", methods=["POST"])
def register_device(mac):
    data = request.get_json() or {}
    alias = data.get("alias", "New Device")
    db = get_db()
    try:
        repo = DeviceRepository(db)
        repo.register_device(mac, alias)
        return jsonify({"success": True, "mac": mac, "alias": alias})
    finally:
        db.close()

@app.route("/api/devices/<mac>", methods=["DELETE"])
def remove_device(mac):
    """Remove a device from the database."""
    db = get_db()
    try:
        repo = DeviceRepository(db)
        repo.delete_device(mac)
        return jsonify({"success": True, "message": f"Device {mac} removed"})
    except Exception as e:
        db.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        db.close()

@app.route("/api/devices/<mac>/block", methods=["POST"])
def block_device(mac):
    """Block or unblock a device (security isolation via ARP spoofing)."""
    data = request.get_json() or {}
    blocked = data.get("blocked", True)
    db = get_db()
    try:
        # Normalize MAC
        mac_upper = mac.upper()
        device = db.query(Device).filter_by(mac=mac_upper).first()
        if not device:
            return jsonify({"success": False, "error": "Device not found"}), 404
        
        device.is_blocked = blocked
        if blocked:
            device.is_trusted = False
            
        db.commit()
        logger.info(f"🛡️ Device {mac_upper} block state updated to: {blocked}")
        
        # Sync with sniffer
        _sync_sniffer_blocking()
        
        return jsonify({"success": True, "blocked": blocked, "mac": mac_upper})
    except Exception as e:
        logger.error(f"Block device error: {e}", exc_info=True)
        db.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        db.close()

@app.route("/api/devices/<mac>/investigate", methods=["POST"])
def investigate_device(mac):
    """Perform an immediate aggressive scan on a specific device."""
    db = get_db()
    try:
        repo = DeviceRepository(db)
        device = repo.get_by_mac(mac)
        if not device: return jsonify({"error": "Not found"}), 404
        
        logger.info(f"🔍 Deep investigation of device {device.ip}...")
        
        # Aggressive scan for this specific host
        from backend.core.engine import DiscoveryEngine
        engine = DiscoveryEngine()
        # Note: subnet can be just the IP for a single host scan
        results = engine.scan_network(subnet=f"{device.ip}/32", aggressive=True)
        
        if results:
            found = results[0]
            device.hostname = found.hostname or device.hostname
            device.vendor = found.vendor or device.vendor
            device.device_type = found.device_type or device.device_type
            device.os_hint = found.os_hint or device.os_hint
            device.is_online = True
            
            # Convert open_ports to JSON for DB storage
            import json
            device.open_ports = json.dumps(found.open_ports)
            db.commit()
        
        # Calculate risk summary
        from backend.modules.port_scanner import OpenPort
        open_ports_obj = []
        import json
        for p in json.loads(device.open_ports or "[]"):
            if isinstance(p, dict):
                open_ports_obj.append(OpenPort(
                    port=p.get('port'), 
                    service=p.get('service', 'unknown'),
                    icon=p.get('icon', '🔓'),
                    risk=p.get('risk', 'unknown'),
                    banner=p.get('banner', '')
                ))
            else:
                # Fallback for simple int list
                open_ports_obj.append(OpenPort(port=p, service='unknown', icon='🔓', risk='unknown'))

        risk = PortScanner.risk_summary(open_ports_obj)
        
        return jsonify({
            "success": True, 
            "device": device.to_dict(),
            "ports": json.loads(device.open_ports),
            "risk": {
                "level": risk["overall"],
                "reason": f"Device has {len(open_ports_obj)} open ports. Highest risk: {risk['overall'].upper()}."
            }
        })
    except Exception as e:
        logger.error(f"Investigate error: {e}", exc_info=True)
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@app.route("/api/scan", methods=["POST"])
def trigger_scan_api():
    data = request.get_json() or {}
    subnet = data.get("subnet")
    aggressive = data.get("aggressive", False)
    
    def run_scan():
        msg = "Aggressive Deep Discovery started..." if aggressive else "Standard Discovery started..."
        socketio.emit("scan_progress", {"status": "scanning", "message": msg})
        try:
            networks = get_local_network()
            if not networks: return
            primary = networks[0]
            engine = DiscoveryEngine()
            
            # Using the new engine scan with aggressive support
            devices = engine.scan_network(
                subnet=subnet or primary["subnet"], 
                interface=primary["interface"],
                aggressive=aggressive
            )
            
            db = get_db()
            try:
                repo = DeviceRepository(db)
                results = []
                for d in devices:
                    device_data = d.to_dict()
                    repo.upsert_device(device_data)
                    results.append(device_data)
                repo.mark_offline_except({d["mac"] for d in results if d.get("mac")})
            finally:
                db.close()
            socketio.emit("scan_complete", {"status": "complete", "devices": results})
        except Exception as e:
            logger.error(f"Scan API error: {e}", exc_info=True)
            socketio.emit("scan_error", {"error": str(e)})
            
    socketio.start_background_task(run_scan)
    return jsonify({"success": True, "message": "Scan initiated"})

@app.route("/api/intel/unsafe", methods=["GET"])
def get_unsafe_zone():
    db = get_db()
    try:
        visits = db.query(SiteVisit).filter_by(is_malicious=True).all()
        devices_at_risk = []
        for v in visits:
            d = db.get(Device, v.device_id)
            if d:
                devices_at_risk.append({
                    "device": d.to_dict(),
                    "threat": v.domain,
                    "at": v.timestamp
                })
        return jsonify({"unsafe_zone": devices_at_risk})
    finally:
        db.close()

@app.route("/api/intel/history", methods=["GET"])
def get_intel_history():
    """Return all recent site visits for traffic analysis."""
    db = get_db()
    try:
        visits = db.query(SiteVisit).order_by(SiteVisit.timestamp.desc()).limit(100).all()
        history = []
        for v in visits:
            d = db.get(Device, v.device_id)
            history.append({
                "domain": v.domain,
                "timestamp": v.timestamp,
                "is_malicious": v.is_malicious,
                "device": d.to_dict() if d else None
            })
        return jsonify({"history": history})
    finally:
        db.close()

@app.route("/api/intel/mark", methods=["POST"])
def mark_intel():
    """Manually move a domain to safe or unsafe zone."""
    data = request.get_json() or {}
    domain = data.get("domain")
    status = data.get("status", "unsafe") # safe or unsafe
    if not domain: return jsonify({"error": "No domain"}), 400
    
    db = get_db()
    try:
        intel = db.query(SiteIntelligence).filter_by(domain=domain).first()
        if not intel:
            intel = SiteIntelligence(domain=domain, status=status)
            db.add(intel)
        else:
            intel.status = status
        
        # Also update visits to reflect new status
        db.query(SiteVisit).filter_by(domain=domain).update({"is_malicious": (status == "unsafe")})
        db.commit()
        return jsonify({"success": True, "domain": domain, "status": status})
    finally:
        db.close()

@app.route("/api/status", methods=["GET"])
def get_status():
    has_perms, perm_msg = check_permissions()
    networks = get_local_network()
    db = get_db()
    try:
        repo = DeviceRepository(db)
        stats = repo.get_stats()
    finally:
        db.close()
    
    import psutil
    return jsonify({
        "name": "Mint NetScout",
        "developer": "mintprojects",
        "permissions": {"has_raw_socket": has_perms, "message": perm_msg},
        "networks": networks,
        "device_stats": stats,
        "system_load": psutil.cpu_percent(),
        "version": "2.1.0-PRO"
    })

def open_browser(host, port):
    # Check if we are in GUI mode
    if os.environ.get("NETSCOUT_GUI_MODE") == "1":
        logger.info("🖥️  GUI Mode detected: skipping browser auto-launch.")
        return

    time.sleep(1.5)
    url = f"http://localhost:{port}" if host == "0.0.0.0" else f"http://{host}:{port}"
    logger.info(f"🚀 Mint NetScout Auto-launch: {url}")
    webbrowser.open(url)

def start_background_tasks():
    """Initialize monitor and sniffer in separate threads after server start."""
    global monitor, sniffer
    
    # Deferred startup to allow server to bind instantly
    time.sleep(2.0)
    
    # 1. Start Monitor (Skip heavy initial scan if FAST_BOOT is enabled)
    interval = 60 if os.environ.get("NETSCOUT_FAST_BOOT") == "1" else 30
    monitor = MonitorWorker(scan_interval=interval, on_event=emit_alert)
    monitor.start()

    # 2. Start Sniffer on primary interface
    nets = get_local_network()
    if nets:
        sniffer = TrafficSniffer(interface=nets[0]['interface'])
        
        # Link sniffer to DB logging
        def log_sniffer_visit(ip, domain):
            db = get_db()
            try:
                repo = DeviceRepository(db)
                dev = repo.get_by_ip(ip)
                
                # If device is unknown, create a placeholder so we can log traffic
                if not dev:
                    logger.info(f"🆕 Traffic from unknown IP {ip}: Creating placeholder.")
                    repo.upsert_device({
                        "ip": ip,
                        "mac": "", # Will be filled by ARP monitor later
                        "hostname": "Unknown Asset",
                        "vendor": "Pending Discovery",
                        "device_type": "unknown"
                    })
                    dev = repo.get_by_ip(ip)
                
                if dev:
                    # Log the visit (linked via MAC or IP stub)
                    mac_to_use = dev.mac or f"STUB:{dev.ip}"
                    is_malicious = repo.log_visit(mac_to_use, domain)
                    
                    if is_malicious:
                        emit_alert(NetworkAlert(
                            "threat_detected", 
                            message=f"THREAT: Device {dev.hostname or dev.ip} contacted known malicious domain: {domain}",
                            device_ip=dev.ip, device_mac=dev.mac
                        ))
            except Exception as e:
                logger.error(f"Traffic logging error: {e}")
            finally:
                db.close()
        
        sniffer.log_callback = log_sniffer_visit
        sniffer.start()
        _sync_sniffer_blocking()

def main():
    init_db()
    
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0")
    
    # Start background tasks in a separate thread to not block server binding
    threading.Thread(target=start_background_tasks, daemon=True).start()
    
    threading.Thread(target=open_browser, args=(host, port), daemon=True).start()
    
    logger.info(f"🛰️  Starting Mint NetScout Intelligence Server on {host}:{port}")
    socketio.run(app, host=host, port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    main()
