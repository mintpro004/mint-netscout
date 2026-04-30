"""
NetScout Backend Tests
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest
import time


# ─── MAC / OUI Tests ──────────────────────────────────────────────────────────

class TestMACUtils:
    def test_normalize_mac_colons(self):
        from backend.utils.helpers import normalize_mac
        assert normalize_mac("aa:bb:cc:dd:ee:ff") == "AA:BB:CC:DD:EE:FF"

    def test_normalize_mac_dashes(self):
        from backend.utils.helpers import normalize_mac
        assert normalize_mac("aa-bb-cc-dd-ee-ff") == "AA:BB:CC:DD:EE:FF"

    def test_normalize_mac_dots(self):
        from backend.utils.helpers import normalize_mac
        assert normalize_mac("aabb.ccdd.eeff") == "AA:BB:CC:DD:EE:FF"

    def test_mac_oui_extraction(self):
        from backend.utils.helpers import mac_oui
        assert mac_oui("B8:27:EB:12:34:56") == "B8:27:EB"

    def test_valid_mac(self):
        from backend.utils.helpers import is_valid_mac
        assert is_valid_mac("AA:BB:CC:DD:EE:FF") is True
        assert is_valid_mac("not-a-mac") is False
        assert is_valid_mac("") is False

    def test_multicast_mac(self):
        from backend.utils.helpers import is_multicast_mac
        assert is_multicast_mac("01:00:5E:00:00:01") is True
        assert is_multicast_mac("00:11:22:33:44:55") is False

    def test_locally_administered(self):
        from backend.utils.helpers import is_locally_administered_mac
        assert is_locally_administered_mac("02:00:00:00:00:01") is True
        assert is_locally_administered_mac("00:11:22:33:44:55") is False


# ─── OUI Lookup Tests ─────────────────────────────────────────────────────────

class TestOUIDatabase:
    def test_apple_oui_lookup(self):
        from backend.modules.fingerprint import OUIDatabase
        db = OUIDatabase()
        vendor = db.lookup("B8:27:EB:12:34:56")  # Raspberry Pi OUI
        assert "Raspberry" in vendor or vendor == "Unknown"

    def test_unknown_oui(self):
        from backend.modules.fingerprint import OUIDatabase
        db = OUIDatabase()
        vendor = db.lookup("DE:AD:BE:EF:00:01")
        assert isinstance(vendor, str)

    def test_empty_mac(self):
        from backend.modules.fingerprint import OUIDatabase
        db = OUIDatabase()
        assert db.lookup("") == "Unknown"
        assert db.lookup("00:00:00:00:00:00") == "Unknown"

    def test_builtin_table_hit(self):
        from backend.modules.fingerprint import OUIDatabase
        db = OUIDatabase()
        # Apple MAC known to be in builtin table
        vendor = db.lookup("00:1B:63:AA:BB:CC")
        assert vendor == "Apple"


# ─── Fingerprinting Tests ─────────────────────────────────────────────────────

class TestFingerprinter:
    def setup_method(self):
        from backend.modules.fingerprint import DeviceFingerprinter
        self.fp = DeviceFingerprinter()

    def test_raspberry_pi_fingerprint(self):
        result = self.fp.fingerprint(mac="B8:27:EB:12:34:56")
        assert result.vendor in ("Raspberry Pi Foundation", "Unknown")

    def test_hostname_hint_router(self):
        result = self.fp.fingerprint(hostname="home-router")
        assert result.device_type == "router"

    def test_hostname_hint_iphone(self):
        result = self.fp.fingerprint(hostname="Johns-iPhone")
        assert result.device_type == "mobile"

    def test_ttl_linux(self):
        from backend.modules.fingerprint import fingerprint_os_from_ttl
        assert "Linux" in fingerprint_os_from_ttl(64)
        assert "Linux" in fingerprint_os_from_ttl(60)

    def test_ttl_windows(self):
        from backend.modules.fingerprint import fingerprint_os_from_ttl
        assert "Windows" in fingerprint_os_from_ttl(128)
        assert "Windows" in fingerprint_os_from_ttl(100)

    def test_ttl_cisco(self):
        from backend.modules.fingerprint import fingerprint_os_from_ttl
        assert "Cisco" in fingerprint_os_from_ttl(255)

    def test_port_printer_detection(self):
        result = self.fp.fingerprint(open_ports=[9100, 631])
        assert result.device_type == "printer"

    def test_port_camera_detection(self):
        result = self.fp.fingerprint(open_ports=[554])
        assert result.device_type == "camera"

    def test_to_dict(self):
        result = self.fp.fingerprint(mac="B8:27:EB:00:00:01")
        d = result.to_dict()
        assert "vendor" in d
        assert "device_type" in d
        assert "device_icon" in d
        assert "confidence" in d


# ─── IP Utility Tests ─────────────────────────────────────────────────────────

class TestIPUtils:
    def test_ip_to_int(self):
        from backend.utils.helpers import ip_to_int, int_to_ip
        n = ip_to_int("192.168.1.1")
        assert int_to_ip(n) == "192.168.1.1"

    def test_private_ip(self):
        from backend.utils.helpers import is_private_ip
        assert is_private_ip("192.168.1.1") is True
        assert is_private_ip("10.0.0.1") is True
        assert is_private_ip("8.8.8.8") is False

    def test_subnet_host_count(self):
        from backend.utils.helpers import subnet_host_count
        assert subnet_host_count("192.168.1.0/24") == 254
        assert subnet_host_count("10.0.0.0/16") == 65534

    def test_ip_in_subnet(self):
        from backend.utils.helpers import ip_in_subnet
        assert ip_in_subnet("192.168.1.100", "192.168.1.0/24") is True
        assert ip_in_subnet("10.0.0.1", "192.168.1.0/24") is False

    def test_sort_ips(self):
        from backend.utils.helpers import sort_ips
        ips = ["192.168.1.10", "192.168.1.2", "192.168.1.1"]
        sorted_ips = sort_ips(ips)
        assert sorted_ips[0] == "192.168.1.1"
        assert sorted_ips[1] == "192.168.1.2"


# ─── Port Scanner Tests ───────────────────────────────────────────────────────

class TestPortScanner:
    def setup_method(self):
        from backend.modules.port_scanner import PortScanner
        self.scanner = PortScanner(timeout=0.3)

    def test_closed_port(self):
        # Port 1 should be closed on localhost
        result = self.scanner.check_port("127.0.0.1", 1)
        assert result is None

    def test_service_registry(self):
        from backend.modules.port_scanner import COMMON_PORTS
        assert 80 in COMMON_PORTS
        assert 443 in COMMON_PORTS
        assert 22 in COMMON_PORTS
        assert COMMON_PORTS[80]["name"] == "HTTP"
        assert COMMON_PORTS[443]["name"] == "HTTPS"

    def test_risk_summary_empty(self):
        from backend.modules.port_scanner import PortScanner
        summary = PortScanner.risk_summary([])
        assert summary["overall"] == "none"

    def test_port_list_structure(self):
        from backend.modules.port_scanner import FAST_SCAN_PORTS, FULL_SCAN_PORTS
        assert len(FAST_SCAN_PORTS) > 0
        assert len(FULL_SCAN_PORTS) > len(FAST_SCAN_PORTS)
        assert 80 in FULL_SCAN_PORTS
        assert 443 in FULL_SCAN_PORTS


# ─── Database Tests ───────────────────────────────────────────────────────────

class TestDatabase:
    def setup_method(self):
        # Use in-memory SQLite for tests
        import os
        os.environ["NETSCOUT_DB"] = ":memory:"
        from backend.database.models import init_db, get_db, DeviceRepository
        # Reinitialize with in-memory DB
        from backend.database import models
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        engine = create_engine("sqlite:///:memory:")
        models.Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)

    def test_upsert_device(self):
        from backend.database.models import DeviceRepository
        db = self.Session()
        try:
            repo = DeviceRepository(db)
            device = repo.upsert_device({
                "mac": "AA:BB:CC:DD:EE:FF",
                "ip": "192.168.1.100",
                "hostname": "test-device",
                "vendor": "Test Vendor",
                "device_type": "pc",
                "device_icon": "💻",
            })
            assert device is not None
            assert device.ip == "192.168.1.100"
            assert device.vendor == "Test Vendor"
        finally:
            db.close()

    def test_upsert_updates_existing(self):
        from backend.database.models import DeviceRepository
        db = self.Session()
        try:
            repo = DeviceRepository(db)
            repo.upsert_device({"mac": "AA:BB:CC:DD:EE:FF", "ip": "192.168.1.100"})
            repo.upsert_device({"mac": "AA:BB:CC:DD:EE:FF", "ip": "192.168.1.200"})
            devices = repo.get_all()
            assert len(devices) == 1
            assert devices[0].ip == "192.168.1.200"
        finally:
            db.close()

    def test_skip_empty_mac(self):
        from backend.database.models import DeviceRepository
        db = self.Session()
        try:
            repo = DeviceRepository(db)
            result = repo.upsert_device({"mac": "", "ip": "192.168.1.1"})
            assert result is None
        finally:
            db.close()


# ─── Discovery Device Model Tests ─────────────────────────────────────────────

class TestDiscoveredDevice:
    def test_to_dict(self):
        from backend.core.engine import DiscoveredDevice
        d = DiscoveredDevice(
            ip="192.168.1.1",
            mac="AA:BB:CC:DD:EE:FF",
            hostname="router",
            latency_ms=1.5,
            discovery_method="arp",
        )
        result = d.to_dict()
        assert result["ip"] == "192.168.1.1"
        assert result["mac"] == "AA:BB:CC:DD:EE:FF"
        assert result["latency_ms"] == 1.5

    def test_is_online_fresh(self):
        from backend.core.engine import DiscoveredDevice
        d = DiscoveredDevice(ip="192.168.1.1")
        assert d.is_online is True

    def test_is_online_stale(self):
        from backend.core.engine import DiscoveredDevice
        d = DiscoveredDevice(ip="192.168.1.1")
        d.last_seen = time.time() - 100
        assert d.is_online is False


# ─── Alert Tests ─────────────────────────────────────────────────────────────

class TestAlerts:
    def test_alert_severity_mapping(self):
        from backend.modules.monitor import NetworkAlert
        alert = NetworkAlert(alert_type="unknown_device", message="test")
        assert alert.severity == "critical"

    def test_alert_to_dict(self):
        from backend.modules.monitor import NetworkAlert
        alert = NetworkAlert(
            alert_type="device_joined",
            device_ip="192.168.1.5",
            message="Device joined",
        )
        d = alert.to_dict()
        assert d["alert_type"] == "device_joined"
        assert d["device_ip"] == "192.168.1.5"
        assert "timestamp" in d

    def test_device_left_severity(self):
        from backend.modules.monitor import NetworkAlert
        alert = NetworkAlert(alert_type="device_left")
        assert alert.severity == "warning"
