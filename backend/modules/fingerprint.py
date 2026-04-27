"""
NetScout Device Fingerprinting Module
======================================
Identifies device type, manufacturer, and OS from:
  1. MAC address OUI (IEEE database lookup)
  2. TTL fingerprinting (OS detection from ping TTL)
  3. mDNS service records (Apple Bonjour services)
  4. UPnP device descriptions
  5. NetBIOS node type

Device types: Mobile, IoT, PC, Router, Printer, TV, Gaming, Unknown
"""

from __future__ import annotations

import json
import logging
import os
import re
import socket
import struct
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("netscout.fingerprint")

# ─── Device Type Enum ─────────────────────────────────────────────────────────

DEVICE_TYPES = {
    "mobile":   {"icon": "📱", "label": "Mobile"},
    "pc":       {"icon": "💻", "label": "Computer"},
    "iot":      {"icon": "🔌", "label": "IoT Device"},
    "router":   {"icon": "📡", "label": "Router/AP"},
    "printer":  {"icon": "🖨️",  "label": "Printer"},
    "tv":       {"icon": "📺", "label": "Smart TV"},
    "gaming":   {"icon": "🎮", "label": "Gaming Console"},
    "nas":      {"icon": "💾", "label": "NAS/Storage"},
    "camera":   {"icon": "📷", "label": "IP Camera"},
    "unknown":  {"icon": "❓", "label": "Unknown"},
}


# ─── OUI Database ─────────────────────────────────────────────────────────────

# Vendor → device type heuristics
VENDOR_TYPE_HINTS: Dict[str, str] = {
    # Mobile
    "apple":       "mobile",
    "samsung":     "mobile",
    "huawei":      "mobile",
    "xiaomi":      "mobile",
    "oneplus":     "mobile",
    "oppo":        "mobile",
    "vivo":        "mobile",
    "motorola":    "mobile",
    "lg electron": "mobile",
    "htc":         "mobile",
    "nokia":       "mobile",

    # PCs / Laptops
    "intel corp":   "pc",
    "realtek":      "pc",
    "dell":         "pc",
    "hewlett":      "pc",
    "lenovo":       "pc",
    "asustek":      "pc",
    "acer":         "pc",
    "microsoft":    "pc",
    "gigabyte":     "pc",
    "msi":          "pc",

    # Routers / Network gear
    "cisco":        "router",
    "netgear":      "router",
    "tp-link":      "router",
    "asus":         "router",
    "ubiquiti":     "router",
    "mikrotik":     "router",
    "d-link":       "router",
    "linksys":      "router",
    "eero":         "router",
    "arris":        "router",
    "technicolor":  "router",

    # IoT
    "espressif":    "iot",
    "raspberry":    "iot",
    "arduino":      "iot",
    "tuya":         "iot",
    "shenzhen":     "iot",
    "amazon":       "iot",   # Echo devices
    "google":       "iot",   # Nest, Home

    # Smart TV / Streaming
    "roku":         "tv",
    "amazon tech":  "tv",
    "lg innotek":   "tv",
    "sony":         "tv",
    "vizio":        "tv",
    "hisense":      "tv",

    # Gaming
    "nintendo":     "gaming",
    "sony interact":"gaming",
    "valve":        "gaming",

    # Printers
    "canon":        "printer",
    "epson":        "printer",
    "brother":      "printer",
    "xerox":        "printer",
    "lexmark":      "printer",
    "ricoh":        "printer",

    # NAS / Storage
    "synology":     "nas",
    "qnap":         "nas",
    "western digi": "nas",
    "seagate":      "nas",

    # Cameras
    "hikvision":    "camera",
    "dahua":        "camera",
    "axis comm":    "camera",
    "amcrest":      "camera",
}


class OUIDatabase:
    """
    IEEE OUI (Organizationally Unique Identifier) database for MAC → Vendor lookup.
    Uses local JSON cache with fallback to online API.
    """

    # Bundled mini-OUI table for common vendors (offline fallback)
    BUILTIN_OUI: Dict[str, str] = {
        "00:00:0C": "Cisco Systems",
        "00:0A:95": "Apple",
        "00:16:CB": "Apple",
        "00:17:F2": "Apple",
        "00:1B:63": "Apple",
        "00:1C:B3": "Apple",
        "00:1D:4F": "Apple",
        "00:1E:52": "Apple",
        "00:1F:5B": "Apple",
        "00:21:E9": "Apple",
        "00:22:41": "Apple",
        "00:23:12": "Apple",
        "00:23:32": "Apple",
        "00:23:6C": "Apple",
        "00:24:36": "Apple",
        "00:25:00": "Apple",
        "00:25:4B": "Apple",
        "00:25:BC": "Apple",
        "00:26:08": "Apple",
        "00:26:4A": "Apple",
        "00:26:B0": "Apple",
        "00:26:BB": "Apple",
        "00:30:65": "Apple",
        "00:3E:E1": "Apple",
        "00:50:E4": "Apple",
        "04:26:65": "Apple",
        "04:D3:CF": "Apple",
        "08:00:07": "Apple",
        "0C:74:C2": "Apple",
        "10:40:F3": "Apple",
        "10:9A:DD": "Apple",
        "18:AF:61": "Apple",
        "1C:AB:A7": "Apple",
        "20:78:F0": "Apple",
        "24:A0:74": "Apple",
        "28:E1:4C": "Apple",
        "2C:BE:08": "Apple",
        "34:36:3B": "Apple",
        "34:51:C9": "Apple",
        "38:C9:86": "Apple",
        "3C:07:54": "Apple",
        "40:A6:D9": "Apple",
        "44:2A:60": "Apple",
        "48:43:7C": "Apple",
        "4C:57:CA": "Apple",
        "50:EA:D6": "Apple",
        "54:AE:27": "Apple",
        "58:55:CA": "Apple",
        "5C:97:F3": "Apple",
        "60:D9:C7": "Apple",
        "60:FB:42": "Apple",
        "64:70:33": "Apple",
        "68:96:7B": "Apple",
        "68:9C:70": "Apple",
        "6C:40:08": "Apple",
        "70:56:81": "Apple",
        "70:73:CB": "Apple",
        "74:E2:F5": "Apple",
        "78:7B:8A": "Apple",
        "7C:6D:62": "Apple",
        "80:BE:05": "Apple",
        "84:38:35": "Apple",
        "84:78:AC": "Apple",
        "88:1F:A1": "Apple",
        "88:63:DF": "Apple",
        "8C:00:6D": "Apple",
        "90:72:40": "Apple",
        "90:B0:ED": "Apple",
        "94:94:26": "Apple",
        "98:01:A7": "Apple",
        "9C:20:7B": "Apple",
        "A4:5E:60": "Apple",
        "A8:20:66": "Apple",
        "A8:60:B6": "Apple",
        "AC:BC:32": "Apple",
        "B0:34:95": "Apple",
        "B0:65:BD": "Apple",
        "B4:18:D1": "Apple",
        "B8:53:AC": "Apple",
        "BC:52:B7": "Apple",
        "C0:9F:42": "Apple",
        "C4:2C:03": "Apple",
        "C8:2A:14": "Apple",
        "C8:69:CD": "Apple",
        "CC:29:F5": "Apple",
        "D0:03:4B": "Apple",
        "D4:61:9D": "Apple",
        "D8:30:62": "Apple",
        "DC:37:14": "Apple",
        "E0:5F:45": "Apple",
        "E4:25:E7": "Apple",
        "E8:80:2E": "Apple",
        "EC:35:86": "Apple",
        "F0:24:75": "Apple",
        "F0:DB:F8": "Apple",
        "F4:F1:5A": "Apple",
        "F8:27:93": "Apple",
        "FC:D8:48": "Apple",
        # Samsung
        "00:02:78": "Samsung Electronics",
        "00:07:AB": "Samsung Electronics",
        "00:09:18": "Samsung Electronics",
        "00:0D:E5": "Samsung Electronics",
        "00:12:47": "Samsung Electronics",
        "00:12:FB": "Samsung Electronics",
        "00:13:77": "Samsung Electronics",
        "00:15:99": "Samsung Electronics",
        "00:16:32": "Samsung Electronics",
        "00:16:DB": "Samsung Electronics",
        "00:17:C9": "Samsung Electronics",
        "00:18:AF": "Samsung Electronics",
        "00:1A:8A": "Samsung Electronics",
        "00:1B:98": "Samsung Electronics",
        "00:1C:43": "Samsung Electronics",
        "00:1D:25": "Samsung Electronics",
        "00:1E:7D": "Samsung Electronics",
        "00:1F:CC": "Samsung Electronics",
        "00:21:19": "Samsung Electronics",
        "00:23:39": "Samsung Electronics",
        "00:23:D6": "Samsung Electronics",
        "00:24:54": "Samsung Electronics",
        "00:24:90": "Samsung Electronics",
        "00:24:E9": "Samsung Electronics",
        "00:25:66": "Samsung Electronics",
        "00:26:37": "Samsung Electronics",
        "00:26:5F": "Samsung Electronics",
        # Google
        "00:1A:11": "Google",
        "3C:5A:B4": "Google",
        "54:60:09": "Google",
        "F4:F5:D8": "Google",
        # Amazon
        "00:BB:3A": "Amazon Technologies",
        "34:D2:70": "Amazon Technologies",
        "40:B4:CD": "Amazon Technologies",
        "44:65:0D": "Amazon Technologies",
        "50:F5:DA": "Amazon Technologies",
        "68:37:E9": "Amazon Technologies",
        "74:75:48": "Amazon Technologies",
        "78:E1:03": "Amazon Technologies",
        "84:D6:D0": "Amazon Technologies",
        "A0:02:DC": "Amazon Technologies",
        "B4:7C:9C": "Amazon Technologies",
        "FC:65:DE": "Amazon Technologies",
        # Cisco
        "00:00:0C": "Cisco Systems",
        "00:01:42": "Cisco Systems",
        "00:01:43": "Cisco Systems",
        "00:01:63": "Cisco Systems",
        "00:01:64": "Cisco Systems",
        "00:01:96": "Cisco Systems",
        "00:01:97": "Cisco Systems",
        "00:02:16": "Cisco Systems",
        "00:02:17": "Cisco Systems",
        "00:02:3D": "Cisco Systems",
        # Raspberry Pi
        "28:CD:C1": "Raspberry Pi Foundation",
        "B8:27:EB": "Raspberry Pi Foundation",
        "DC:A6:32": "Raspberry Pi Foundation",
        "E4:5F:01": "Raspberry Pi Foundation",
        # Espressif (ESP8266/ESP32 IoT)
        "18:FE:34": "Espressif Systems",
        "24:0A:C4": "Espressif Systems",
        "2C:3A:E8": "Espressif Systems",
        "30:AE:A4": "Espressif Systems",
        "40:F5:20": "Espressif Systems",
        "5C:CF:7F": "Espressif Systems",
        "84:F3:EB": "Espressif Systems",
        "A4:7B:9D": "Espressif Systems",
        "AC:67:B2": "Espressif Systems",
        "B4:E6:2D": "Espressif Systems",
        "D8:BF:C0": "Espressif Systems",
        # TP-Link
        "14:CC:20": "TP-LINK Technologies",
        "18:D6:C7": "TP-LINK Technologies",
        "1C:FA:68": "TP-LINK Technologies",
        "24:69:68": "TP-LINK Technologies",
        "2C:D0:5A": "TP-LINK Technologies",
        "30:B5:C2": "TP-LINK Technologies",
        "38:2C:4A": "TP-LINK Technologies",
        "40:16:9F": "TP-LINK Technologies",
        "44:B3:2D": "TP-LINK Technologies",
        "50:C7:BF": "TP-LINK Technologies",
        "54:E6:FC": "TP-LINK Technologies",
        "60:32:B1": "TP-LINK Technologies",
        "64:66:B3": "TP-LINK Technologies",
        "6C:5A:B5": "TP-LINK Technologies",
        "70:4F:57": "TP-LINK Technologies",
        "74:DA:38": "TP-LINK Technologies",
        "78:8A:20": "TP-LINK Technologies",
        "84:16:F9": "TP-LINK Technologies",
        "90:F6:52": "TP-LINK Technologies",
        "A0:F3:C1": "TP-LINK Technologies",
        "B0:95:75": "TP-LINK Technologies",
        "C4:6E:1F": "TP-LINK Technologies",
        "E8:DE:27": "TP-LINK Technologies",
        "F0:A7:31": "TP-LINK Technologies",
        # Nintendo
        "00:09:BF": "Nintendo",
        "00:17:AB": "Nintendo",
        "00:19:1D": "Nintendo",
        "00:1A:E9": "Nintendo",
        "00:1B:EA": "Nintendo",
        "00:1C:BE": "Nintendo",
        "00:1E:35": "Nintendo",
        "00:1F:32": "Nintendo",
        "00:21:47": "Nintendo",
        "00:22:AA": "Nintendo",
        "00:23:CC": "Nintendo",
        "00:24:44": "Nintendo",
        "00:24:F3": "Nintendo",
        "04:03:D6": "Nintendo",
        "40:D2:8A": "Nintendo",
        "58:BD:A3": "Nintendo",
        "8C:56:C5": "Nintendo",
        "B8:AE:6E": "Nintendo",
        "D8:6B:F7": "Nintendo",
        "E0:E7:51": "Nintendo",
        # Sony (PlayStation)
        "00:01:4A": "Sony",
        "00:02:C7": "Sony",
        "00:04:1F": "Sony",
        "00:09:DD": "Sony",
        "00:0A:D9": "Sony",
        "00:0E:07": "Sony",
        "00:13:A9": "Sony",
        "00:15:C1": "Sony",
        "00:17:9A": "Sony",
        "00:19:C5": "Sony",
        "00:1A:80": "Sony",
        "00:1D:0D": "Sony",
        "00:1D:BA": "Sony",
        "00:1E:A6": "Sony",
        "00:22:3F": "Sony",
        "00:23:06": "Sony",
        "00:24:BE": "Sony",
        "00:26:43": "Sony",
        "28:0D:FC": "Sony",
        "2C:33:61": "Sony",
        "30:17:C8": "Sony",
        "40:B0:FA": "Sony",
        "78:84:3C": "Sony",
        "78:9F:70": "Sony",
        "8C:0D:76": "Sony",
        "A8:E0:73": "Sony",
        "B0:5A:DA": "Sony",
        "D4:58:E7": "Sony",
        "F8:D0:27": "Sony",
        # Netgear
        "00:09:5B": "NETGEAR",
        "00:0F:B5": "NETGEAR",
        "00:14:6C": "NETGEAR",
        "00:18:4D": "NETGEAR",
        "00:1B:2F": "NETGEAR",
        "00:1E:2A": "NETGEAR",
        "00:1F:33": "NETGEAR",
        "00:22:3F": "NETGEAR",
        "00:24:B2": "NETGEAR",
        "00:26:F2": "NETGEAR",
        "20:0C:C8": "NETGEAR",
        "28:C6:8E": "NETGEAR",
        "2C:30:33": "NETGEAR",
        "2C:B0:5D": "NETGEAR",
        "30:46:9A": "NETGEAR",
        "3C:37:86": "NETGEAR",
        "44:94:FC": "NETGEAR",
        "4F:0B:CB": "NETGEAR",
        "6C:B0:CE": "NETGEAR",
        "84:1B:5E": "NETGEAR",
        "A0:21:B7": "NETGEAR",
        "B0:39:56": "NETGEAR",
        "C0:3F:0E": "NETGEAR",
        "C4:04:15": "NETGEAR",
        "D8:61:62": "NETGEAR",
        "E0:46:9A": "NETGEAR",
        "E4:F4:C6": "NETGEAR",
        "F8:1A:67": "NETGEAR",
        # Ubiquiti
        "00:15:6D": "Ubiquiti Networks",
        "00:27:22": "Ubiquiti Networks",
        "04:18:D6": "Ubiquiti Networks",
        "0C:80:63": "Ubiquiti Networks",
        "18:E8:29": "Ubiquiti Networks",
        "24:A4:3C": "Ubiquiti Networks",
        "44:D9:E7": "Ubiquiti Networks",
        "60:22:32": "Ubiquiti Networks",
        "68:72:51": "Ubiquiti Networks",
        "6C:5E:3B": "Ubiquiti Networks",
        "74:83:C2": "Ubiquiti Networks",
        "78:8A:20": "Ubiquiti Networks",
        "80:2A:A8": "Ubiquiti Networks",
        "90:A7:C1": "Ubiquiti Networks",
        "B4:FB:E4": "Ubiquiti Networks",
        "DC:9F:DB": "Ubiquiti Networks",
        "E0:63:DA": "Ubiquiti Networks",
        "F0:9F:C2": "Ubiquiti Networks",
        "F4:E2:C6": "Ubiquiti Networks",
        "FC:EC:DA": "Ubiquiti Networks",
    }

    def __init__(self, cache_path: Optional[str] = None):
        # Use __file__-anchored path so it works regardless of CWD
        _project_root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)
        )))
        _default = os.path.join(_project_root, "data", "oui_cache.json")
        self.cache_path = os.path.abspath(cache_path or _default)
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
        self._cache: Dict[str, str] = {}
        self._load_cache()

    def _load_cache(self):
        """Load OUI cache from disk if it exists."""
        
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path) as f:
                    self._cache = json.load(f)
                logger.debug(f"Loaded {len(self._cache)} OUI entries from cache")
            except Exception as e:
                logger.warning(f"Could not load OUI cache: {e}")

    def _save_cache(self):
        """Persist cache to disk."""
        try:
            with open(self.cache_path, "w") as f:
                json.dump(self._cache, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save OUI cache: {e}")

    def lookup(self, mac: str) -> str:
        """
        Look up vendor for a MAC address.
        Priority: disk cache → builtin table → online API
        """
        if not mac or mac in ("", "00:00:00:00:00:00", "ff:ff:ff:ff:ff:ff"):
            return "Unknown"

        # Normalize: uppercase, colon-separated
        mac_clean = mac.upper().replace("-", ":").replace(".", ":")
        oui = ":".join(mac_clean.split(":")[:3])

        # 1. Check in-memory cache
        if oui in self._cache:
            return self._cache[oui]

        # 2. Check builtin table
        if oui in self.BUILTIN_OUI:
            vendor = self.BUILTIN_OUI[oui]
            self._cache[oui] = vendor
            return vendor

        # 3. Try online API (macvendors.com)
        try:
            url = f"https://api.macvendors.com/{oui}"
            req = urllib.request.Request(
                url, headers={"User-Agent": "NetScout/1.0"}
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                vendor = resp.read().decode("utf-8").strip()
                if vendor and "Not Found" not in vendor:
                    self._cache[oui] = vendor
                    self._save_cache()
                    return vendor
        except Exception:
            pass

        # 4. Try macaddress.io (alternative)
        try:
            url = f"https://api.maclookup.app/v2/macs/{oui}"
            req = urllib.request.Request(
                url, headers={"User-Agent": "NetScout/1.0"}
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read())
                vendor = data.get("company", "")
                if vendor and vendor != "Not found":
                    self._cache[oui] = vendor
                    self._save_cache()
                    return vendor
        except Exception:
            pass

        self._cache[oui] = "Unknown"
        return "Unknown"


# ─── TTL → OS Fingerprinting ──────────────────────────────────────────────────

def fingerprint_os_from_ttl(ttl: int) -> str:
    """
    Rough OS detection from ICMP TTL values.
    Not 100% reliable but good heuristic for common devices.
    """
    if ttl <= 0:
        return "Unknown"
    elif ttl <= 64:
        return "Linux/Android/iOS"
    elif ttl <= 128:
        return "Windows"
    elif ttl <= 255:
        return "Cisco/Network Device"
    return "Unknown"


# ─── Hostname → Device Type Hints ─────────────────────────────────────────────

HOSTNAME_TYPE_HINTS: Dict[str, str] = {
    "iphone":     "mobile",
    "ipad":       "mobile",
    "android":    "mobile",
    "galaxy":     "mobile",
    "pixel":      "mobile",
    "airpods":    "mobile",
    "macbook":    "pc",
    "imac":       "pc",
    "macmini":    "pc",
    "macpro":     "pc",
    "desktop":    "pc",
    "laptop":     "pc",
    "workstation":"pc",
    "router":     "router",
    "gateway":    "router",
    "modem":      "router",
    "ap-":        "router",
    "access-pt":  "router",
    "unifi":      "router",
    "printer":    "printer",
    "print":      "printer",
    "hp-":        "printer",
    "canon":      "printer",
    "epson":      "printer",
    "raspberrypi":"iot",
    "esp":        "iot",
    "arduino":    "iot",
    "nest":       "iot",
    "echo":       "iot",
    "alexa":      "iot",
    "roomba":     "iot",
    "camera":     "camera",
    "cam-":       "camera",
    "nvr":        "camera",
    "dvr":        "camera",
    "hikvision":  "camera",
    "appletv":    "tv",
    "roku":       "tv",
    "firetv":     "tv",
    "chromecast": "tv",
    "shield":     "tv",
    "ps4":        "gaming",
    "ps5":        "gaming",
    "xbox":       "gaming",
    "nintendo":   "gaming",
    "synology":   "nas",
    "qnap":       "nas",
    "nas-":       "nas",
}


def guess_device_type_from_hostname(hostname: str) -> Optional[str]:
    """Guess device type from hostname keywords."""
    if not hostname:
        return None
    lower = hostname.lower()
    for keyword, dtype in HOSTNAME_TYPE_HINTS.items():
        if keyword in lower:
            return dtype
    return None


def guess_device_type_from_vendor(vendor: str) -> str:
    """Guess device type from vendor name keywords."""
    if not vendor:
        return "unknown"
    lower = vendor.lower()
    for keyword, dtype in VENDOR_TYPE_HINTS.items():
        if keyword in lower:
            return dtype
    return "unknown"


# ─── Main Fingerprinter ───────────────────────────────────────────────────────

@dataclass
class DeviceFingerprint:
    """Complete device identification result."""
    vendor: str = "Unknown"
    device_type: str = "unknown"
    os_hint: str = ""
    confidence: int = 0   # 0-100

    def to_dict(self) -> dict:
        type_info = DEVICE_TYPES.get(self.device_type, DEVICE_TYPES["unknown"])
        return {
            "vendor": self.vendor,
            "device_type": self.device_type,
            "device_icon": type_info["icon"],
            "device_label": type_info["label"],
            "os_hint": self.os_hint,
            "confidence": self.confidence,
        }


class DeviceFingerprinter:
    """
    Orchestrates all fingerprinting methods to identify a device.
    More signals → higher confidence.
    """

    def __init__(self):
        self.oui_db = OUIDatabase()

    def fingerprint(
        self,
        mac: str = "",
        hostname: str = "",
        ttl: int = 0,
        open_ports: List[int] = None,
    ) -> DeviceFingerprint:
        """
        Identify a device using all available signals.
        Returns DeviceFingerprint with vendor, type, OS, and confidence.
        """
        fp = DeviceFingerprint()
        confidence_points = 0

        # ── MAC OUI Lookup ────────────────────────────────────────────────────
        if mac:
            fp.vendor = self.oui_db.lookup(mac)
            if fp.vendor != "Unknown":
                confidence_points += 30
                fp.device_type = guess_device_type_from_vendor(fp.vendor)
                if fp.device_type != "unknown":
                    confidence_points += 20

        # ── Hostname Hints ────────────────────────────────────────────────────
        if hostname:
            hostname_type = guess_device_type_from_hostname(hostname)
            if hostname_type:
                # Hostname overrides OUI guess (more specific)
                fp.device_type = hostname_type
                confidence_points += 25

        # ── TTL Fingerprinting ────────────────────────────────────────────────
        if ttl > 0:
            fp.os_hint = fingerprint_os_from_ttl(ttl)
            confidence_points += 10

            # Refine device type from OS
            if "Android" in fp.os_hint or "iOS" in fp.os_hint:
                if fp.device_type == "unknown":
                    fp.device_type = "mobile"
                    confidence_points += 10

        # ── Port-based Fingerprinting ─────────────────────────────────────────
        if open_ports:
            port_type = self._guess_from_ports(open_ports)
            if port_type and fp.device_type == "unknown":
                fp.device_type = port_type
                confidence_points += 15

        fp.confidence = min(confidence_points, 100)
        return fp

    def _guess_from_ports(self, ports: List[int]) -> Optional[str]:
        """Infer device type from open ports."""
        port_set = set(ports)

        # Printers: 9100 (raw print), 631 (IPP), 515 (LPD)
        if port_set & {9100, 631, 515}:
            return "printer"

        # IP Cameras: 554 (RTSP), 8554
        if port_set & {554, 8554}:
            return "camera"

        # NAS: 5000 (Synology), 8080, 445 (SMB), 2049 (NFS)
        if port_set & {5000, 445, 2049}:
            return "nas"

        # Router/AP: 23 (Telnet), 161 (SNMP)
        if port_set & {23, 161}:
            return "router"

        # PC-like: 22 (SSH), 3389 (RDP), 5900 (VNC)
        if port_set & {22, 3389, 5900}:
            return "pc"

        return None
