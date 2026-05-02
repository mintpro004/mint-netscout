"""
NetScout Router Intelligence & Control Module
==============================================
Advanced logic for identifying, probing, and managing the network gateway.
"""

import logging
import socket
import time
import urllib.request
import xml.etree.ElementTree as ET
import concurrent.futures
from typing import Dict, List, Optional
from backend.core.engine import get_local_network

logger = logging.getLogger("netscout.router")

class RouterIntelligence:
    def __init__(self):
        self.gateway_ip = ""
        self.gateway_mac = ""
        self.vendor = "Generic"
        self.model = "Router"
        self.firmware = "Unknown"
        self.capabilities = []
        self.vulnerabilities = []
        self.management_urls = []

    def discover_gateway(self):
        """Identify and perform deep analysis on the primary gateway."""
        nets = get_local_network()
        if not nets:
            return None
        
        self.gateway_ip = nets[0].get('gateway', "")
        if not self.gateway_ip:
            return None
            
        logger.info(f"🔍 Deep Probing Gateway: {self.gateway_ip}")
        
        # Reset state for fresh probe
        self.capabilities = []
        self.vulnerabilities = []
        self.management_urls = []
        
        # ── CROSTINI WORKAROUND ──
        # If the gateway is the internal Crostini bridge, try common LAN IPs
        is_bridge = self.gateway_ip.startswith("100.115.")
        
        # Run probes in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            executor.submit(self.probe_upnp)
            executor.submit(self.probe_management, self.gateway_ip)
            
            if is_bridge:
                # Common router IPs on typical home networks
                # If these respond, they are likely the REAL physical gateway
                for test_ip in ["192.168.1.1", "192.168.0.1", "192.168.1.254", "10.0.0.1", "10.1.1.1"]:
                    executor.submit(self.probe_management, test_ip)
                    
            executor.submit(self.check_vulnerabilities)
        
        return self.to_dict()

    def probe_upnp(self):
        """Discover router features and model info via UPnP (SSDP)."""
        ssdp_msg = (
            "M-SEARCH * HTTP/1.1\r\n"
            "HOST: 239.255.255.250:1900\r\n"
            "MAN: \"ssdp:discover\"\r\n"
            "MX: 2\r\n"
            "ST: ssdp:all\r\n"
            "\r\n"
        )
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(2.5)
            sock.sendto(ssdp_msg.encode(), ("239.255.255.250", 1900))
            
            # Collect responses
            start_time = time.time()
            while time.time() - start_time < 2.5:
                try:
                    data, addr = sock.recvfrom(2048)
                    # For bridge environments, we accept any UPnP response as it's likely the real router
                    res = data.decode('utf-8', errors='ignore')
                    if "LOCATION:" in res:
                        location = res.split("LOCATION:")[1].split("\r\n")[0].strip()
                        self._parse_upnp_desc(location)
                        if "UPnP" not in self.capabilities:
                            self.capabilities.append("UPnP/SSDP")
                except socket.timeout:
                    break
        except Exception as e:
            logger.debug(f"UPnP discovery failed: {e}")
        finally:
            sock.close()

    def _parse_upnp_desc(self, url: str):
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                tree = ET.parse(resp)
                root = tree.getroot()
                ns = {'ns': 'urn:schemas-upnp-org:device-1-0'}
                device = root.find('.//ns:device', ns)
                if device is not None:
                    self.vendor = device.findtext('ns:manufacturer', self.vendor, ns)
                    self.model = device.findtext('ns:modelName', self.model, ns)
                    self.firmware = device.findtext('ns:modelNumber', self.firmware, ns)
                    
                    # Check for IGD (Internet Gateway Device) services
                    services = device.findall('.//ns:service', ns)
                    for svc in services:
                        stype = svc.findtext('ns:serviceType', '', ns)
                        if "WANIPConnection" in stype or "WANPPPConnection" in stype:
                            self.capabilities.append("NAT Control (IGD)")
        except: pass

    def probe_management(self, ip: str):
        """Find web/CLI management interfaces on a specific IP."""
        schemes = [("http", 80), ("https", 443), ("http", 8080), ("http", 8888)]
        
        for scheme, port in schemes:
            try:
                base_url = f"{scheme}://{ip}:{port}"
                # Fast connectivity check
                with socket.create_connection((ip, port), timeout=0.8):
                    if f"Port {port} ({scheme.upper()})" not in self.capabilities:
                        self.capabilities.append(f"Management Port {port} ({scheme.upper()})")
                    
                    # Try to confirm it's a router web UI
                    try:
                        req = urllib.request.Request(base_url, method="GET")
                        with urllib.request.urlopen(req, timeout=1.0) as resp:
                            if resp.status == 200:
                                if base_url not in self.management_urls:
                                    self.management_urls.append(base_url)
                                server = resp.headers.get("Server", "")
                                if server and self.vendor == "Generic":
                                    self.vendor = server
                    except:
                        # If port is open but GET fails, still list it as a potential URL
                        if base_url not in self.management_urls:
                            self.management_urls.append(base_url)
            except: continue

        # Check SSH/Telnet
        if ip == self.gateway_ip:
            for port, label in [(22, "SSH"), (23, "Telnet")]:
                try:
                    with socket.create_connection((ip, port), timeout=1.0):
                        self.capabilities.append(f"{label} Access")
                except: continue

    def check_vulnerabilities(self):
        """Simulate/Proactive security checks (Non-destructive)."""
        if "Telnet Access" in self.capabilities:
            self.vulnerabilities.append({
                "id": "R-01", "level": "critical", 
                "title": "Unencrypted Management (Telnet)", 
                "desc": "Gateway exposes unencrypted telnet interface."
            })
            
        if "UPnP/SSDP" in self.capabilities:
            self.vulnerabilities.append({
                "id": "R-02", "level": "medium", 
                "title": "UPnP Enabled", 
                "desc": "UPnP can be used by malware to open firewall ports."
            })

        for port, service in [(53, "DNS"), (123, "NTP")]:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(1.0)
                sock.sendto(b"\x00", (self.gateway_ip, port))
                self.capabilities.append(f"Exposed {service}")
            except: pass
            finally: sock.close()

    def to_dict(self):
        return {
            "ip": self.gateway_ip,
            "vendor": self.vendor,
            "model": self.model,
            "firmware": self.firmware,
            "capabilities": list(set(self.capabilities)),
            "management_urls": sorted(list(set(self.management_urls))),
            "vulnerabilities": self.vulnerabilities,
            "risk_score": len(self.vulnerabilities) * 25
        }
