"""
NetScout Port Scanner Module
==============================
Concurrent TCP port scanner for discovered devices.
Identifies running services on common ports.
Non-blocking: uses ThreadPoolExecutor for parallel scanning.
"""

from __future__ import annotations

import socket
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger("netscout.portscanner")


# ─── Service Registry ─────────────────────────────────────────────────────────

COMMON_PORTS: Dict[int, dict] = {
    21:   {"name": "FTP",         "icon": "📁", "risk": "medium"},
    22:   {"name": "SSH",         "icon": "🔐", "risk": "low"},
    23:   {"name": "Telnet",      "icon": "⚠️",  "risk": "high"},
    25:   {"name": "SMTP",        "icon": "📧", "risk": "low"},
    53:   {"name": "DNS",         "icon": "🌐", "risk": "low"},
    67:   {"name": "DHCP",        "icon": "🔌", "risk": "low"},
    68:   {"name": "DHCP Client", "icon": "🔌", "risk": "low"},
    80:   {"name": "HTTP",        "icon": "🌍", "risk": "low"},
    110:  {"name": "POP3",        "icon": "📬", "risk": "low"},
    123:  {"name": "NTP",         "icon": "🕐", "risk": "low"},
    135:  {"name": "RPC",         "icon": "🔗", "risk": "medium"},
    137:  {"name": "NetBIOS-NS",  "icon": "🖥️",  "risk": "medium"},
    139:  {"name": "NetBIOS",     "icon": "🖥️",  "risk": "medium"},
    143:  {"name": "IMAP",        "icon": "📬", "risk": "low"},
    161:  {"name": "SNMP",        "icon": "📊", "risk": "medium"},
    443:  {"name": "HTTPS",       "icon": "🔒", "risk": "low"},
    445:  {"name": "SMB",         "icon": "📂", "risk": "high"},
    515:  {"name": "LPD/Print",   "icon": "🖨️",  "risk": "low"},
    554:  {"name": "RTSP/Camera", "icon": "📷", "risk": "medium"},
    631:  {"name": "IPP/Print",   "icon": "🖨️",  "risk": "low"},
    993:  {"name": "IMAPS",       "icon": "🔒", "risk": "low"},
    995:  {"name": "POP3S",       "icon": "🔒", "risk": "low"},
    1080: {"name": "SOCKS Proxy", "icon": "🔀", "risk": "medium"},
    1194: {"name": "OpenVPN",     "icon": "🔐", "risk": "low"},
    1433: {"name": "MSSQL",       "icon": "🗄️",  "risk": "high"},
    1900: {"name": "UPnP",        "icon": "🔌", "risk": "medium"},
    2049: {"name": "NFS",         "icon": "💾", "risk": "high"},
    2082: {"name": "cPanel",      "icon": "⚙️",  "risk": "medium"},
    2083: {"name": "cPanel SSL",  "icon": "🔒", "risk": "low"},
    2375: {"name": "Docker",      "icon": "🐳", "risk": "critical"},
    2376: {"name": "Docker SSL",  "icon": "🐳", "risk": "medium"},
    3000: {"name": "Dev Server",  "icon": "⚙️",  "risk": "low"},
    3306: {"name": "MySQL",       "icon": "🗄️",  "risk": "high"},
    3389: {"name": "RDP",         "icon": "🖥️",  "risk": "high"},
    3690: {"name": "SVN",         "icon": "📦", "risk": "low"},
    4000: {"name": "App Server",  "icon": "⚙️",  "risk": "low"},
    4443: {"name": "Alt HTTPS",   "icon": "🔒", "risk": "low"},
    4899: {"name": "RAdmin",      "icon": "🖥️",  "risk": "high"},
    5000: {"name": "Synology/App","icon": "💾", "risk": "low"},
    5432: {"name": "PostgreSQL",  "icon": "🗄️",  "risk": "high"},
    5900: {"name": "VNC",         "icon": "🖥️",  "risk": "high"},
    5985: {"name": "WinRM HTTP",  "icon": "🖥️",  "risk": "high"},
    5986: {"name": "WinRM HTTPS", "icon": "🖥️",  "risk": "medium"},
    6379: {"name": "Redis",       "icon": "🗄️",  "risk": "critical"},
    7000: {"name": "Cassandra",   "icon": "🗄️",  "risk": "high"},
    8000: {"name": "HTTP Alt",    "icon": "🌍", "risk": "low"},
    8080: {"name": "HTTP Proxy",  "icon": "🌍", "risk": "low"},
    8081: {"name": "HTTP Alt2",   "icon": "🌍", "risk": "low"},
    8443: {"name": "HTTPS Alt",   "icon": "🔒", "risk": "low"},
    8554: {"name": "RTSP Alt",    "icon": "📷", "risk": "medium"},
    8888: {"name": "Jupyter/HTTP","icon": "📓", "risk": "medium"},
    9000: {"name": "PHP-FPM/App", "icon": "⚙️",  "risk": "low"},
    9090: {"name": "Prometheus",  "icon": "📊", "risk": "medium"},
    9100: {"name": "Raw Print",   "icon": "🖨️",  "risk": "low"},
    9200: {"name": "Elasticsearch","icon": "🔍", "risk": "critical"},
    10000:{"name": "Webmin",      "icon": "⚙️",  "risk": "high"},
    27017:{"name": "MongoDB",     "icon": "🗄️",  "risk": "critical"},
    32400:{"name": "Plex",        "icon": "🎬", "risk": "low"},
    49152:{"name": "UPnP/Router", "icon": "📡", "risk": "medium"},
}

# Fast scan: just the most commonly found ports
FAST_SCAN_PORTS = [21, 22, 23, 80, 443, 445, 554, 3389, 5900, 8080, 9100]

# Full scan: all known service ports
FULL_SCAN_PORTS = list(COMMON_PORTS.keys())


# ─── Data Model ───────────────────────────────────────────────────────────────

@dataclass
class OpenPort:
    port: int
    service: str
    icon: str
    risk: str
    banner: str = ""
    response_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "port": self.port,
            "service": self.service,
            "icon": self.icon,
            "risk": self.risk,
            "banner": self.banner,
            "response_ms": round(self.response_ms, 2),
        }


# ─── Port Scanner ─────────────────────────────────────────────────────────────

class PortScanner:
    """
    Concurrent TCP connect scanner.
    Non-blocking — uses thread pool for parallel port checks.
    """

    def __init__(
        self,
        timeout: float = 1.0,
        max_workers: int = 200,
        grab_banner: bool = True,
    ):
        self.timeout = timeout
        self.max_workers = max_workers
        self.grab_banner = grab_banner

    def check_port(self, ip: str, port: int) -> Optional[OpenPort]:
        """
        Test if a single TCP port is open on the target IP.
        Returns OpenPort if open, None if closed/filtered.
        """
        t_start = time.perf_counter()
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(self.timeout)
                result = sock.connect_ex((ip, port))
                response_ms = (time.perf_counter() - t_start) * 1000

                if result == 0:
                    service_info = COMMON_PORTS.get(port, {
                        "name": f"port-{port}",
                        "icon": "🔓",
                        "risk": "unknown",
                    })

                    banner = ""
                    if self.grab_banner:
                        banner = self._grab_banner(sock, ip, port)

                    return OpenPort(
                        port=port,
                        service=service_info["name"],
                        icon=service_info["icon"],
                        risk=service_info["risk"],
                        banner=banner,
                        response_ms=response_ms,
                    )
        except (socket.timeout, ConnectionRefusedError, OSError):
            pass
        except Exception as e:
            logger.debug(f"Port check {ip}:{port} error: {e}")

        return None

    def _grab_banner(self, sock: socket.socket, ip: str, port: int) -> str:
        """Try to grab a service banner for version detection."""
        banner_ports = {80, 8080, 8081, 21, 22, 25, 110}
        if port not in banner_ports:
            return ""

        try:
            if port in (80, 8080, 8081):
                sock.send(b"HEAD / HTTP/1.0\r\nHost: " + ip.encode() + b"\r\n\r\n")
            else:
                pass  # Just receive

            sock.settimeout(1.0)
            data = sock.recv(256)
            banner = data.decode("utf-8", errors="ignore").strip()
            # Extract just the first line
            return banner.splitlines()[0][:100] if banner else ""
        except Exception:
            return ""

    def scan_device(
        self,
        ip: str,
        ports: Optional[List[int]] = None,
        mode: str = "fast",
    ) -> List[OpenPort]:
        """
        Scan a single device for open ports.

        Args:
            ip:    Target IP address
            ports: Specific ports to scan (None = use mode)
            mode:  "fast" (11 ports) | "full" (all known ports) | "custom"

        Returns:
            List of OpenPort objects for open ports
        """
        if ports is None:
            ports = FAST_SCAN_PORTS if mode == "fast" else FULL_SCAN_PORTS

        logger.debug(f"Scanning {ip} ({len(ports)} ports, mode={mode})")
        open_ports = []

        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(ports))) as executor:
            futures = {
                executor.submit(self.check_port, ip, port): port
                for port in ports
            }
            for future in as_completed(futures):
                result = future.result()
                if result:
                    open_ports.append(result)
                    logger.debug(f"  {ip}:{result.port} OPEN ({result.service})")

        open_ports.sort(key=lambda p: p.port)
        logger.info(f"Port scan {ip}: {len(open_ports)} open ports found")
        return open_ports

    def scan_network_ports(
        self,
        ips: List[str],
        ports: Optional[List[int]] = None,
        mode: str = "fast",
        device_max_workers: int = 10,
    ) -> Dict[str, List[OpenPort]]:
        """
        Scan multiple devices concurrently.
        Outer parallelism: devices. Inner: ports per device.
        """
        results: Dict[str, List[OpenPort]] = {}

        with ThreadPoolExecutor(max_workers=device_max_workers) as executor:
            futures = {
                executor.submit(self.scan_device, ip, ports, mode): ip
                for ip in ips
            }
            for future in as_completed(futures):
                ip = futures[future]
                try:
                    results[ip] = future.result()
                except Exception as e:
                    logger.error(f"Port scan failed for {ip}: {e}")
                    results[ip] = []

        return results

    @staticmethod
    def risk_summary(open_ports: List[OpenPort]) -> dict:
        """
        Summarize the security risk profile of a device based on open ports.
        """
        risk_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "unknown": 0}
        for p in open_ports:
            risk_counts[p.risk] = risk_counts.get(p.risk, 0) + 1

        # Overall risk level
        if risk_counts["critical"] > 0:
            overall = "critical"
        elif risk_counts["high"] > 0:
            overall = "high"
        elif risk_counts["medium"] > 0:
            overall = "medium"
        elif risk_counts["low"] > 0:
            overall = "low"
        else:
            overall = "none"

        return {
            "overall": overall,
            "counts": risk_counts,
            "risky_ports": [
                p.to_dict() for p in open_ports
                if p.risk in ("critical", "high")
            ],
        }
