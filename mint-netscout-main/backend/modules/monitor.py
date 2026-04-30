"""
Mint NetScout Monitor Module
=============================
Real-time background monitor that orchestrates periodic network scans.
Handles simulated traffic analysis for threat detection.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import random
from typing import Callable, Dict, List, Optional, Set

from backend.core.engine import DiscoveryEngine, DiscoveredDevice, get_local_network
from backend.database.models import get_db, DeviceRepository, AlertRepository, SiteIntelligence

logger = logging.getLogger("netscout.monitor")

class Alert:
    def __init__(self, alert_type: str, message: str, severity: str = "info", device_ip: str = "", device_mac: str = "", device_hostname: str = "", **kwargs):
        self.alert_type = alert_type
        self.message = message
        self.severity = severity
        self.timestamp = time.time()
        self.device_ip = device_ip
        self.device_mac = device_mac
        self.device_hostname = device_hostname

    def to_dict(self) -> dict:
        return {
            "alert_type": self.alert_type,
            "message": self.message,
            "severity": self.severity,
            "timestamp": self.timestamp,
            "device_ip": self.device_ip,
            "device_mac": self.device_mac,
            "device_hostname": self.device_hostname,
        }

class MonitorWorker:
    def __init__(self, scan_interval: int = 30, on_event: Optional[Callable] = None):
        self.scan_interval = scan_interval
        self.on_event = on_event or (lambda alert: None)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._engine = DiscoveryEngine()
        self.current_devices: List[dict] = []

    def start(self):
        if self._running: return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info(f"Monitor started (interval: {self.scan_interval}s)")

    def stop(self):
        self._running = False
        if self._thread: self._thread.join(timeout=2)

    def _run(self):
        while self._running:
            cycle_start = time.time()
            try:
                self._perform_cycle()
            except Exception as e:
                logger.error(f"Monitor cycle error: {e}", exc_info=True)
            # FIX BE-06: subtract time the scan already took so interval is accurate
            elapsed = time.time() - cycle_start
            sleep_time = max(0, self.scan_interval - elapsed)
            time.sleep(sleep_time)

    def _perform_cycle(self):
        networks = get_local_network()
        if not networks: return
        primary = networks[0]

        logger.info(f"Performing intelligence sweep on {primary['subnet']}...")
        # Aggressive scan is handled by the engine if requested, monitor does standard periodic discovery
        discovered = self._engine.scan_network(subnet=primary['subnet'], interface=primary['interface'])

        db = get_db()
        try:
            repo = DeviceRepository(db)
            alert_repo = AlertRepository(db)

            active_macs = set()
            for d in discovered:
                # Update/Register with REAL data only
                device_data = d.to_dict()

                # Analyze real device behavior (joins/changes)
                self._analyze_device_behavior(repo, alert_repo, d)

                repo.upsert_device(device_data)
                # FIX BE-04: only add non-empty MACs to active set
                if d.mac:
                    active_macs.add(d.mac)

            repo.mark_offline_except(active_macs)
            self.current_devices = [d.to_dict() for d in discovered]

            # Real alert for scan completion
            self.on_event(Alert("scan_complete", f"Discovery cycle complete: {len(discovered)} real assets identified."))
        finally:
            db.close()

    def _analyze_device_behavior(self, repo, alert_repo, device: DiscoveredDevice):
        """Analyze real device behavior and log alerts for significant network events."""
        if not device.mac and not device.ip: return

        # Check if this is a new unknown device (REAL EVENT)
        existing = repo.get_by_mac(device.mac) if device.mac else repo.get_by_ip(device.ip)

        if not existing:
            self.on_event(Alert(
                alert_type="new_device",
                severity="warning",
                device_ip=device.ip,
                device_mac=device.mac,
                device_hostname=device.hostname,
                message=f"SECURITY ALERT: New unverified asset detected on network: {device.ip}"
            ))
        elif not existing.is_online:
            self.on_event(Alert(
                alert_type="device_joined",
                severity="info",
                device_ip=device.ip,
                device_mac=device.mac,
                device_hostname=device.hostname,
                message=f"Network Event: Known device {device.hostname or device.ip} has reconnected."
            ))

    def get_status(self) -> dict:

        return {
            "running": self._running,
            "scan_interval": self.scan_interval,
            "device_count": len(self.current_devices)
        }
