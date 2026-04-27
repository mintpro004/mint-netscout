"""
NetScout Utilities
==================
Shared helpers: IP math, MAC formatting, OS detection, logging setup.
"""

from __future__ import annotations

import ipaddress
import logging
import platform
import re
import socket
import struct
import sys
import time
from typing import List, Optional, Tuple

# ─── Logging ──────────────────────────────────────────────────────────────────

def setup_logging(level: str = "INFO", log_file: Optional[str] = None):
    """Configure colorised console + optional file logging."""
    try:
        import colorlog
        formatter = colorlog.ColoredFormatter(
            "%(log_color)s%(asctime)s [%(name)s] %(levelname)s%(reset)s: %(message)s",
            datefmt="%H:%M:%S",
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "bold_red",
            },
        )
    except ImportError:
        formatter = logging.Formatter(
            "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            datefmt="%H:%M:%S",
        )

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    if log_file:
        fh = logging.FileHandler(log_file)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
        ))
        root.addHandler(fh)


# ─── IP Helpers ───────────────────────────────────────────────────────────────

def ip_to_int(ip: str) -> int:
    return struct.unpack("!I", socket.inet_aton(ip))[0]

def int_to_ip(n: int) -> str:
    return socket.inet_ntoa(struct.pack("!I", n))

def is_private_ip(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return False

def subnet_host_count(subnet: str) -> int:
    try:
        return ipaddress.IPv4Network(subnet, strict=False).num_addresses - 2
    except ValueError:
        return 0

def ip_in_subnet(ip: str, subnet: str) -> bool:
    try:
        return ipaddress.ip_address(ip) in ipaddress.ip_network(subnet, strict=False)
    except ValueError:
        return False

def get_broadcast(subnet: str) -> str:
    try:
        return str(ipaddress.IPv4Network(subnet, strict=False).broadcast_address)
    except ValueError:
        return ""

def sort_ips(ips: List[str]) -> List[str]:
    """Sort IP addresses numerically."""
    try:
        return sorted(ips, key=lambda ip: ip_to_int(ip))
    except Exception:
        return sorted(ips)


# ─── MAC Helpers ──────────────────────────────────────────────────────────────

def normalize_mac(mac: str) -> str:
    """Normalize a MAC address to uppercase colon-separated format."""
    if not mac:
        return ""
    clean = re.sub(r"[^0-9a-fA-F]", "", mac)
    if len(clean) != 12:
        return mac.upper()
    return ":".join(clean[i:i+2] for i in range(0, 12, 2)).upper()

def mac_oui(mac: str) -> str:
    """Extract OUI (first 3 octets) from a MAC address."""
    norm = normalize_mac(mac)
    if not norm:
        return ""
    return ":".join(norm.split(":")[:3])

def is_valid_mac(mac: str) -> bool:
    pattern = re.compile(r"^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$")
    return bool(pattern.match(mac))

def is_multicast_mac(mac: str) -> bool:
    """Multicast MACs have the LSB of first octet set."""
    try:
        first_octet = int(mac.split(":")[0], 16)
        return bool(first_octet & 1)
    except Exception:
        return False

def is_locally_administered_mac(mac: str) -> bool:
    """Locally administered MACs (VMs, VPNs) have bit 1 of first octet set."""
    try:
        first_octet = int(mac.split(":")[0], 16)
        return bool(first_octet & 2)
    except Exception:
        return False


# ─── OS Detection ─────────────────────────────────────────────────────────────

def get_platform_info() -> dict:
    system = platform.system()
    release = platform.release()
    machine = platform.machine()

    is_chromebook = False
    if system == "Linux":
        try:
            with open("/etc/os-release") as f:
                content = f.read()
                if "cros" in content.lower() or "chromeos" in content.lower():
                    is_chromebook = True
        except FileNotFoundError:
            pass
        try:
            if "penguin" in open("/etc/hostname").read().lower():
                is_chromebook = True
        except FileNotFoundError:
            pass

    return {
        "system": system,
        "release": release,
        "machine": machine,
        "is_chromebook": is_chromebook,
        "is_wsl": "microsoft" in platform.uname().release.lower(),
        "python": sys.version,
    }


# ─── Retry Decorator ──────────────────────────────────────────────────────────

def retry(times: int = 3, delay: float = 0.5, exceptions=(Exception,)):
    """Simple retry decorator for flaky network calls."""
    def decorator(fn):
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(times):
                try:
                    return fn(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt < times - 1:
                        time.sleep(delay * (attempt + 1))
            raise last_exc
        return wrapper
    return decorator


# ─── Rate Limiter ─────────────────────────────────────────────────────────────

class RateLimiter:
    """Simple token-bucket rate limiter for API calls."""
    def __init__(self, calls_per_second: float = 5.0):
        self.interval = 1.0 / calls_per_second
        self._last_call = 0.0

    def wait(self):
        now = time.monotonic()
        elapsed = now - self._last_call
        if elapsed < self.interval:
            time.sleep(self.interval - elapsed)
        self._last_call = time.monotonic()


# ─── Progress Reporter ────────────────────────────────────────────────────────

class ProgressBar:
    """Simple terminal progress bar (no external deps)."""
    def __init__(self, total: int, prefix: str = "", width: int = 40):
        self.total = total
        self.prefix = prefix
        self.width = width
        self.current = 0

    def update(self, n: int = 1):
        self.current = min(self.current + n, self.total)
        self._render()

    def _render(self):
        pct = self.current / max(self.total, 1)
        filled = int(self.width * pct)
        bar = "█" * filled + "░" * (self.width - filled)
        sys.stdout.write(f"\r{self.prefix} [{bar}] {self.current}/{self.total}")
        sys.stdout.flush()
        if self.current >= self.total:
            print()
