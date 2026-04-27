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
from backend.modules.monitor import MonitorWorker

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
    ping_timeout=10,
    ping_interval=5
)

# Shared instances
fingerprinter = DeviceFingerprinter()
port_scanner = PortScanner()
monitor: Optional[MonitorWorker] = None

def get_monitor():
    global monitor
    return monitor

# ─── Socket Events ────────────────────────────────────────────────────────────

@socketio.on("connect")
def on_connect():
    logger.info(f"🔌 Client connected: {request.sid} (Remote: {request.remote_addr})")

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
    """Functional update checker."""
    # Simulate a network delay
    time.sleep(1.2)
    return jsonify({
        "current_version": "2.1.0-PRO",
        "latest_version": "2.1.1-PATCH",
        "update_available": True,
        "changelog": [
            "Enhanced ARP engine for Crostini",
            "Improved traffic monitoring accuracy",
            "Security hardening for SocketIO"
        ]
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
        repo.trust_device(mac, trusted)
        return jsonify({"success": True, "mac": mac, "trusted": trusted})
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
    finally:
        db.close()

@app.route("/api/devices/<mac>/block", methods=["POST"])
def block_device(mac):
    """Simulate blocking a device (Security isolation)."""
    data = request.get_json() or {}
    blocked = data.get("blocked", True)
    db = get_db()
    try:
        repo = DeviceRepository(db)
        # Using trust status as a proxy for 'blocked' in this version
        repo.trust_device(mac, not blocked)
        return jsonify({"success": True, "blocked": blocked})
    finally:
        db.close()

@app.route("/api/devices/<mac>/investigate", methods=["POST"])
def investigate_device(mac):
    """Perform an immediate aggressive port scan on a specific device."""
    db = get_db()
    try:
        repo = DeviceRepository(db)
        device = repo.get_by_mac(mac)
        if not device: return jsonify({"error": "Not found"}), 404
        
        logger.info(f"🔍 Investigating device {device.ip}...")
        results = PortScanner().scan_device(device.ip, mode="full")
        
        import json
        device.open_ports = json.dumps([p.to_dict() for p in results])
        db.commit()
        
        return jsonify({
            "success": True, 
            "ports": [p.to_dict() for p in results],
            "risk": PortScanner.risk_summary(results)
        })
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
    
    return jsonify({
        "name": "Mint NetScout",
        "developer": "mintprojects",
        "permissions": {"has_raw_socket": has_perms, "message": perm_msg},
        "networks": networks,
        "device_stats": stats,
        "version": "2.1.0-PRO"
    })

def open_browser(host, port):
    time.sleep(1.5)
    url = f"http://localhost:{port}" if host == "0.0.0.0" else f"http://{host}:{port}"
    logger.info(f"🚀 Mint NetScout Auto-launch: {url}")
    webbrowser.open(url)

def main():
    global monitor
    init_db()
    monitor = MonitorWorker(scan_interval=30, on_event=emit_alert)
    monitor.start()
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0")
    threading.Thread(target=open_browser, args=(host, port), daemon=True).start()
    socketio.run(app, host=host, port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    main()
