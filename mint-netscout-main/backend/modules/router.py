"""
NetScout Router Intelligence & Control Module
==============================================
Specialized logic for identifying and interacting with the network gateway.
Capabilities:
  1. Gateway Identification (IP, MAC, Vendor)
  2. Management Interface Discovery (HTTP/HTTPS/SSH)
  3. UPnP/SSDP Discovery for feature identification
  4. Basic Router Model Fingerprinting
"""

import logging
import socket
import urllib.request
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional
from backend.core.engine import get_local_network

logger = logging.getLogger("netscout.router")

class RouterIntelligence:
    def __init__(self):
        self.gateway_ip = ""
        self.gateway_mac = ""
        self.vendor = ""
        self.model = "Generic Router"
        self.capabilities = []

    def discover_gateway(self):
        """Identify the primary gateway and its properties."""
        nets = get_local_network()
        if not nets:
            return None
        
        self.gateway_ip = nets[0].get('gateway', "")
        if not self.gateway_ip:
            return None
            
        logger.info(f"🔍 Analyzing Gateway: {self.gateway_ip}")
        
        # In a real scenario, we'd get the MAC from ARP cache
        # For now, we'll just focus on what we can probe via network
        
        self.probe_upnp()
        self.probe_management()
        
        return self.to_dict()

    def probe_upnp(self):
        """Discover router features via UPnP (SSDP)."""
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
            sock.settimeout(2.0)
            sock.sendto(ssdp_msg.encode(), ("239.255.255.250", 1900))
            
            while True:
                data, addr = sock.recvfrom(2048)
                if addr[0] == self.gateway_ip:
                    # Found the router's UPnP response
                    res = data.decode('utf-8', errors='ignore')
                    if "LOCATION:" in res:
                        location = res.split("LOCATION:")[1].split("\r\n")[0].strip()
                        self._parse_upnp_desc(location)
                        self.capabilities.append("UPnP")
                        break
        except Exception as e:
            logger.debug(f"UPnP discovery failed: {e}")
        finally:
            sock.close()

    def _parse_upnp_desc(self, url: str):
        """Fetch and parse UPnP XML description for model info."""
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                tree = ET.parse(resp)
                root = tree.getroot()
                # XML namespaces can be tricky, but usually it's urn:schemas-upnp-org:device-1-0
                ns = {'ns': 'urn:schemas-upnp-org:device-1-0'}
                device = root.find('.//ns:device', ns)
                if device is not None:
                    friendly_name = device.findtext('ns:friendlyName', '', ns)
                    model_name = device.findtext('ns:modelName', '', ns)
                    manufacturer = device.findtext('ns:manufacturer', '', ns)
                    
                    if manufacturer: self.vendor = manufacturer
                    if model_name: self.model = model_name
                    elif friendly_name: self.model = friendly_name
                    
                    logger.info(f"🏠 Router identified: {self.vendor} {self.model}")
        except Exception as e:
            logger.debug(f"UPnP XML parse failed: {e}")

    def probe_management(self):
        """Check for common management ports and try to grab headers."""
        ports = [80, 443, 8080, 22, 23]
        for port in ports:
            try:
                with socket.create_connection((self.gateway_ip, port), timeout=1.0) as sock:
                    self.capabilities.append(f"Port {port}")
                    if port in (80, 8080):
                        # Try to get Server header
                        sock.send(b"HEAD / HTTP/1.0\r\n\r\n")
                        res = sock.recv(1024).decode('utf-8', errors='ignore')
                        if "Server:" in res:
                            server = res.split("Server:")[1].split("\r\n")[0].strip()
                            if server and self.model == "Generic Router":
                                self.model = server
            except:
                continue

    def to_dict(self):
        return {
            "ip": self.gateway_ip,
            "vendor": self.vendor,
            "model": self.model,
            "capabilities": self.capabilities,
            "admin_url": f"http://{self.gateway_ip}"
        }
