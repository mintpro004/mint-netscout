"""
Mint NetScout Database Models
==============================
SQLite-backed persistent storage using SQLAlchemy ORM.
Stores device history, scan records, and alert logs.
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean, Column, Float, ForeignKey, Integer, String, Text,
    create_engine, func,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

# ─── Config ───────────────────────────────────────────────────────────────────

# Anchor data dir to project root regardless of CWD
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
)))
_DATA_DIR = os.path.join(_PROJECT_ROOT, "data")
os.makedirs(_DATA_DIR, exist_ok=True)
DB_PATH = os.environ.get("NETSCOUT_DB", os.path.join(_DATA_DIR, "netscout.db"))
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
SessionLocal = sessionmaker(bind=engine)


# ─── Base ─────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ─── Models ───────────────────────────────────────────────────────────────────

class Device(Base):
    """
    Persistent record of a discovered network device.
    MAC address is the primary key for device identity.
    """
    __tablename__ = "devices"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    mac         = Column(String(17), unique=True, index=True, nullable=False)
    ip          = Column(String(15), index=True)
    hostname    = Column(String(255), default="")
    alias       = Column(String(255), default="")
    vendor      = Column(String(255), default="Unknown")
    device_type = Column(String(50), default="unknown")
    device_icon = Column(String(10), default="❓")
    os_hint     = Column(String(100), default="")
    is_trusted  = Column(Boolean, default=False)
    is_blocked  = Column(Boolean, default=False)
    is_registered = Column(Boolean, default=False)

    # Timing
    first_seen  = Column(Float, default=time.time)
    last_seen   = Column(Float, default=time.time)
    is_online   = Column(Boolean, default=True)

    # Network details
    open_ports  = Column(Text, default="[]")   # JSON list
    latency_ms  = Column(Float, default=0.0)
    traffic_in  = Column(Float, default=0.0)   # MB
    traffic_out = Column(Float, default=0.0)   # MB

    # Relationships
    scans       = relationship("ScanRecord", back_populates="device")
    visits      = relationship("SiteVisit", back_populates="device")

    def to_dict(self) -> dict:
        import json
        return {
            "id": self.id,
            "mac": self.mac,
            "ip": self.ip,
            "hostname": self.hostname or "",
            "alias": self.alias or "",
            "vendor": self.vendor,
            "device_type": self.device_type,
            "device_icon": self.device_icon,
            "os_hint": self.os_hint,
            "is_trusted": self.is_trusted,
            "is_blocked": self.is_blocked,
            "is_registered": self.is_registered,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "is_online": self.is_online,
            "open_ports": json.loads(self.open_ports or "[]"),
            "latency_ms": self.latency_ms,
        }

    def __repr__(self):
        return f"<Device {self.ip} ({self.mac}) - {self.vendor}>"


class SiteIntelligence(Base):
    """
    Threat intelligence for domains and IPs.
    """
    __tablename__ = "site_intelligence"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    domain      = Column(String(255), unique=True, index=True)
    status      = Column(String(20), default="safe")  # safe, unsafe, restricted
    category    = Column(String(100), default="general")
    threat_score= Column(Integer, default=0)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "domain": self.domain,
            "status": self.status,
            "category": self.category,
            "threat_score": self.threat_score
        }


class SiteVisit(Base):
    """
    Log of sites visited by devices (Simulated Threat Intel).
    """
    __tablename__ = "site_visits"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    device_id   = Column(Integer, ForeignKey("devices.id"))
    domain      = Column(String(255))
    timestamp   = Column(Float, default=time.time)
    is_malicious= Column(Boolean, default=False)

    device = relationship("Device", back_populates="visits")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "domain": self.domain,
            "timestamp": self.timestamp,
            "is_malicious": self.is_malicious
        }


class ScanRecord(Base):
    """
    Log of each scan run — used for trending and history.
    """
    __tablename__ = "scan_records"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    device_id    = Column(Integer, ForeignKey("devices.id"), nullable=True)
    scan_time    = Column(Float, default=time.time)
    ip_at_scan   = Column(String(15))
    latency_ms   = Column(Float, default=0.0)
    method       = Column(String(20))  # arp, icmp, mdns, tcp_stealth

    device = relationship("Device", back_populates="scans")


class AlertLog(Base):
    """
    Persistent record of network alerts and events.
    """
    __tablename__ = "alert_log"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    alert_type     = Column(String(50))
    severity       = Column(String(20))
    device_ip      = Column(String(15), default="")
    device_mac     = Column(String(17), default="")
    device_hostname= Column(String(255), default="")
    message        = Column(Text)
    timestamp      = Column(Float, default=time.time)
    acknowledged   = Column(Boolean, default=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "device_ip": self.device_ip,
            "device_mac": self.device_mac,
            "device_hostname": self.device_hostname,
            "message": self.message,
            "timestamp": self.timestamp,
            "acknowledged": self.acknowledged,
        }


class LatencyRecord(Base):
    """
    ISP latency history for trend graphs.
    """
    __tablename__ = "latency_records"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    timestamp  = Column(Float, default=time.time)
    target     = Column(String(50), default="8.8.8.8")
    avg_ms     = Column(Float)
    min_ms     = Column(Float)
    max_ms     = Column(Float)
    jitter_ms  = Column(Float)
    packet_loss= Column(Float, default=0.0)


# ─── Database Operations ──────────────────────────────────────────────────────

def init_db():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(engine)
    
    # Seed SiteIntelligence if empty
    db = SessionLocal()
    try:
        if db.query(SiteIntelligence).count() == 0:
            seeds = [
                SiteIntelligence(domain="google.com", status="safe", category="search"),
                SiteIntelligence(domain="github.com", status="safe", category="dev"),
                SiteIntelligence(domain="malicious-example.net", status="unsafe", category="malware", threat_score=90),
                SiteIntelligence(domain="tracker-ads.com", status="unsafe", category="tracking", threat_score=40),
                SiteIntelligence(domain="shady-crypto.org", status="unsafe", category="phishing", threat_score=75),
                SiteIntelligence(domain="dark-leak-forum.onion", status="unsafe", category="breach", threat_score=95),
                SiteIntelligence(domain="botnet-cnc-server.io", status="unsafe", category="cnc", threat_score=100),
                SiteIntelligence(domain="crypto-miner-pool.biz", status="restricted", category="mining", threat_score=60),
                SiteIntelligence(domain="corporate-vpn.net", status="safe", category="network"),
                SiteIntelligence(domain="internal-wiki.local", status="safe", category="internal"),
            ]
            db.add_all(seeds)
            db.commit()
    finally:
        db.close()
    
    print(f"✅ Mint NetScout Database initialized: {DB_PATH}")


def get_db() -> Session:
    """Get a database session."""
    return SessionLocal()


class DeviceRepository:
    """CRUD operations for Device records."""

    def __init__(self, db: Session):
        self.db = db

    def upsert_device(self, device_data: dict) -> Device:
        """Insert or update a device by MAC address or IP fallback."""
        mac = device_data.get("mac", "").upper()
        ip = device_data.get("ip", "")
        
        # IF we don't have a MAC, we allow it ONLY if we have an IP (stub device)
        if not mac and not ip:
            return None

        # Try MAC first if available
        device = None
        if mac:
            device = self.db.query(Device).filter_by(mac=mac).first()
        
        if not device and ip:
            # If no MAC match or no MAC provided, try IP match for devices that also don't have a MAC
            # This allows updating a stub device
            device = self.db.query(Device).filter_by(ip=ip, mac="").first()

        if device:
            # Update existing - PROTECT MANUAL FLAGS
            # FIX BE-08: upgrade mac even if existing device had empty mac
            if mac and not device.mac:
                device.mac = mac
            device.ip = ip or device.ip
            
            # Only update hostname if not manually aliased
            if not device.alias:
                device.hostname = device_data.get("hostname", device.hostname) or device.hostname
            
            device.last_seen = time.time()
            device.is_online = True
            
            # Update non-manual fields
            device.latency_ms = device_data.get("latency_ms", device.latency_ms)
            device.traffic_in = device_data.get("traffic_in", device.traffic_in)
            device.traffic_out = device_data.get("traffic_out", device.traffic_out)
            
            if device_data.get("vendor") not in ("Unknown", "", None):
                device.vendor = device_data["vendor"]
            if device_data.get("device_type") not in ("unknown", "", None):
                device.device_type = device_data["device_type"]
                device.device_icon = device_data.get("device_icon", device.device_icon)
            if device_data.get("os_hint"):
                device.os_hint = device_data["os_hint"]
            
            # MANUALLY PRESERVE AND LOG STATE PROTECTION
            # We do NOT touch is_blocked, is_trusted, is_registered here
        else:
            # Create new
            import json
            device = Device(
                mac=mac,
                ip=ip or "",
                hostname=device_data.get("hostname", ""),
                vendor=device_data.get("vendor", "Unknown"),
                device_type=device_data.get("device_type", "unknown"),
                device_icon=device_data.get("device_icon", "❓"),
                os_hint=device_data.get("os_hint", ""),
                latency_ms=device_data.get("latency_ms", 0.0),
                open_ports=json.dumps(device_data.get("open_ports", [])),
                first_seen=time.time(),
                last_seen=time.time(),
            )
            self.db.add(device)

        self.db.commit()
        self.db.refresh(device)
        return device

    def get_all(self, online_only: bool = False) -> List[Device]:
        q = self.db.query(Device)
        if online_only:
            q = q.filter(Device.is_online == True)
        return q.order_by(Device.last_seen.desc()).all()

    def get_by_mac(self, mac: str) -> Optional[Device]:
        if not mac: return None
        return self.db.query(Device).filter_by(mac=mac.upper()).first()

    def get_by_ip(self, ip: str) -> Optional[Device]:
        if not ip: return None
        return self.db.query(Device).filter_by(ip=ip).first()

    def delete_device(self, mac: str):
        """Permanently remove a device from the database."""
        device = self.db.query(Device).filter_by(mac=mac).first()
        if device:
            self.db.delete(device)
            self.db.commit()

    def mark_all_offline(self):
        """Mark devices not seen in recent scans as offline."""
        cutoff = time.time() - 120  # 2 minutes
        self.db.query(Device).filter(
            Device.last_seen < cutoff,
            Device.is_online == True
        ).update({"is_online": False})
        self.db.commit()

    def mark_offline_except(self, active_macs: set):
        """Mark devices offline if their MAC is not in active_macs set."""
        try:
            # Convert set elements to uppercase for safety
            mac_list = [str(m).upper() for m in active_macs if m]
            
            # Update all that are NOT in the list and currently online
            self.db.query(Device).filter(
                Device.mac.notin_(mac_list),
                Device.is_online == True
            ).update({"is_online": False}, synchronize_session=False)
            
            self.db.commit()
        except Exception as e:
            self.db.rollback()


    def trust_device(self, mac: str, trusted: bool = True):
        device = self.get_by_mac(mac)
        if device:
            device.is_trusted = trusted
            self.db.commit()
            
    def register_device(self, mac: str, alias: str):
        device = self.get_by_mac(mac)
        if device:
            device.alias = alias
            device.is_registered = True
            self.db.commit()

    def get_stats(self) -> dict:
        total = self.db.query(func.count(Device.id)).scalar()
        online = self.db.query(func.count(Device.id)).filter(
            Device.is_online == True
        ).scalar()
        trusted = self.db.query(func.count(Device.id)).filter(
            Device.is_trusted == True
        ).scalar()
        registered = self.db.query(func.count(Device.id)).filter(
            Device.is_registered == True
        ).scalar()
        by_type = {}
        rows = self.db.query(Device.device_type, func.count(Device.id)).group_by(
            Device.device_type
        ).all()
        for dtype, count in rows:
            by_type[dtype] = count

        return {
            "total": total,
            "online": online,
            "offline": total - online,
            "trusted": trusted,
            "registered": registered,
            "unknown": total - (trusted + registered),
            "by_type": by_type,
        }
    
    def log_visit(self, mac: str, domain: str):
        # Handle STUB MACs for unknown devices
        if mac.startswith("STUB:"):
            ip = mac.split(":")[1]
            device = self.get_by_ip(ip)
        else:
            device = self.get_by_mac(mac)
            
        if not device: return
        
        intel = self.db.query(SiteIntelligence).filter_by(domain=domain).first()
        is_malicious = intel and intel.status == "unsafe"
        
        visit = SiteVisit(
            device_id=device.id,
            domain=domain,
            is_malicious=is_malicious
        )
        self.db.add(visit)
        self.db.commit()
        return is_malicious


class AlertRepository:
    """CRUD for AlertLog."""

    def __init__(self, db: Session):
        self.db = db

    def log_alert(self, alert_data: dict) -> AlertLog:
        alert = AlertLog(
            alert_type=alert_data.get("alert_type", ""),
            severity=alert_data.get("severity", "info"),
            device_ip=alert_data.get("device_ip", ""),
            device_mac=alert_data.get("device_mac", ""),
            device_hostname=alert_data.get("device_hostname", ""),
            message=alert_data.get("message", ""),
            timestamp=alert_data.get("timestamp", time.time()),
        )
        self.db.add(alert)
        self.db.commit()
        return alert

    def get_recent(self, limit: int = 50) -> List[AlertLog]:
        return (
            self.db.query(AlertLog)
            .order_by(AlertLog.timestamp.desc())
            .limit(limit)
            .all()
        )

    def acknowledge(self, alert_id: int):
        alert = self.db.query(AlertLog).filter_by(id=alert_id).first()
        if alert:
            alert.acknowledged = True
            self.db.commit()

    def get_unacknowledged(self) -> List[AlertLog]:
        return (
            self.db.query(AlertLog)
            .filter(AlertLog.acknowledged == False)
            .order_by(AlertLog.timestamp.desc())
            .all()
        )
