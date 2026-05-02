"""
NetScout Discovery Engine
=========================
Phase 1: Device Discovery via ARP + ICMP hybrid scanning.

Strategy:
  1. ARP sweep  — most reliable, catches sleeping phones
  2. ICMP ping  — fallback for cross-subnet / VPN scenarios
  3. mDNS probe — catches Apple devices via Bonjour
  4. NetBIOS    — catches Windows shares

Concurrency: asyncio + ThreadPoolExecutor for non-blocking scans.
Permissions:  Requires CAP_NET_RAW (Linux) or Administrator (Windows).
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
import struct
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set

logger = logging.getLogger("netscout.discovery")


# ─── Data Models ─────────────────────────────────────────────────────────────

@dataclass
class DiscoveredDevice:
    """Represents a device found during a network scan."""
    ip: str
    mac: str = ""
    hostname: str = ""
    ttl: int = 0
    latency_ms: float = 0.0
    discovery_method: str = ""   # "arp", "icmp", "mdns", "netbios"
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    # FIX BE-01 & BE-02: Added missing fingerprint + open_ports fields
    vendor: str = "Unknown"
    device_type: str = "unknown"
    os_hint: str = ""
    arch_hint: str = "unknown"
    device_icon: str = "❓"
    open_ports: List = field(default_factory=list)  # list of port dicts or ints

    @property
    def is_online(self) -> bool:
        return (time.time() - self.last_seen) < 30

    def to_dict(self) -> dict:
        return {
            "ip": self.ip,
            "mac": self.mac,
            "hostname": self.hostname,
            "ttl": self.ttl,
            "latency_ms": round(self.latency_ms, 2),
            "discovery_method": self.discovery_method,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "is_online": self.is_online,
            "vendor": self.vendor,
            "device_type": self.device_type,
            "os_hint": self.os_hint,
            "arch_hint": self.arch_hint,
            "device_icon": self.device_icon,
            "open_ports": self.open_ports,
        }


# ─── Permission Check ─────────────────────────────────────────────────────────

def check_permissions() -> tuple[bool, str]:
    """
    Checks if the process has sufficient permissions for raw socket access.
    Returns (has_permission, message).
    """
    import os
    import platform

    system = platform.system()

    # Try to open a raw socket to see if we actually have permission
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        s.close()
        return True, "Raw socket access granted"
    except PermissionError:
        pass
    except Exception:
        pass

    if system in ("Linux", "Darwin"):
        if os.geteuid() == 0:
            return True, "Running as root"
        return False, (
            "Limited permissions — ARP scanning disabled. "
            "Run with sudo OR: sudo setcap cap_net_raw+eip $(which python3)"
        )
    elif system == "Windows":
        try:
            import ctypes
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
            return is_admin, (
                "Running as Administrator" if is_admin
                else "Run as Administrator for full ARP scanning"
            )
        except Exception:
            return False, "Could not determine Windows admin status"

    return False, "Insufficient permissions for raw sockets"


# ─── Network Interface Detection ──────────────────────────────────────────────

def get_local_network() -> list[dict]:
    """
    Auto-detects local network interfaces and their subnets.
    Returns list of {"interface": str, "ip": str, "subnet": str, "gateway": str}
    """
    import netifaces

    networks = []
    # Relaxed filtering: allow bridges (br-) as they are common on many setups
    ignored_prefixes = ("lo", "docker", "virbr", "veth")

    for iface in netifaces.interfaces():
        if any(iface.startswith(p) for p in ignored_prefixes):
            continue

        addrs = netifaces.ifaddresses(iface)
        ipv4 = addrs.get(netifaces.AF_INET, [])

        for addr in ipv4:
            ip = addr.get("addr", "")
            netmask = addr.get("netmask", "")
            if not ip or ip.startswith("127.") or not netmask:
                continue

            try:
                network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
                # Skip huge networks (> /16) to prevent runaway scans
                if network.prefixlen < 16:
                    logger.warning(f"Skipping large network {network} on {iface}")
                    continue

                # Get gateway
                gateway = ""
                gateways = netifaces.gateways()
                default_gw = gateways.get("default", {}).get(netifaces.AF_INET)
                if default_gw and default_gw[1] == iface:
                    gateway = default_gw[0]

                networks.append({
                    "interface": iface,
                    "ip": ip,
                    "subnet": str(network),
                    "gateway": gateway,
                    "prefix_len": network.prefixlen,
                    "host_count": network.num_addresses - 2,
                })
                logger.info(f"📡 Detected network: {network} on {iface} (Gateway: {gateway})")
            except Exception as e:
                logger.debug(f"Skipping {iface}: {e}")

    if not networks:
        logger.warning("No active network interfaces detected!")

    return networks


# ─── TCP Stealth Scanner ──────────────────────────────────────────────────────

class TCPStealthScanner:
    """
    Identifies 'hidden' devices that block ICMP/ARP by probing common TCP ports.
    If a port responds with SYN-ACK or RST, the host is alive.
    """
    STEALTH_PORTS = [80, 443, 22, 135, 445, 8080]

    def __init__(self, timeout: float = 0.5):
        self.timeout = timeout

    def probe(self, ip: str) -> Optional[DiscoveredDevice]:
        """Probe common ports on an IP to see if it exists."""
        for port in self.STEALTH_PORTS:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(self.timeout)
                    # connect_ex returns 0 for success (SYN-ACK) 
                    # and other codes for errors. Some firewalls return RST (ECONNREFUSED)
                    # which STILL confirms the host is alive.
                    result = s.connect_ex((ip, port))
                    if result in (0, socket.errno.ECONNREFUSED):
                        return DiscoveredDevice(
                            ip=ip,
                            discovery_method="tcp_stealth",
                            latency_ms=self.timeout * 1000 / 2 # estimation
                        )
            except Exception:
                continue
        return None

    def scan(self, subnet: str) -> List[DiscoveredDevice]:
        """Scan a subnet using TCP stealth probes."""
        network = ipaddress.IPv4Network(subnet, strict=False)
        hosts = [str(ip) for ip in network.hosts()]
        results = []

        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = {executor.submit(self.probe, ip): ip for ip in hosts}
            for future in as_completed(futures):
                dev = future.result()
                if dev:
                    results.append(dev)
        
        return results


# ─── ARP Scanner ──────────────────────────────────────────────────────────────

class ARPScanner:
    """
    Sends ARP requests to each IP in a subnet.
    ARP is layer-2 — far more reliable than ICMP for local LAN discovery.
    Catches sleeping phones, tablets, IoT devices that block pings.
    """

    def __init__(self, interface: str, timeout: float = 2.0):
        self.interface = interface
        self.timeout = timeout

    def scan(self, subnet: str) -> List[DiscoveredDevice]:
        """
        Perform ARP sweep of the entire subnet.
        Uses scapy for raw ARP packet crafting.
        """
        try:
            from scapy.all import ARP, Ether, srp
            logger.info(f"ARP sweep: {subnet} on {self.interface}")

            network = ipaddress.IPv4Network(subnet, strict=False)
            target_ips = [str(ip) for ip in network.hosts()]

            # Batch into groups of 256 for efficiency
            BATCH_SIZE = 256
            devices: List[DiscoveredDevice] = []

            for i in range(0, len(target_ips), BATCH_SIZE):
                batch = target_ips[i:i + BATCH_SIZE]
                ip_range = "/".join([batch[0], batch[-1]])

                # Craft ARP "who-has" broadcast packet
                arp_request = ARP(pdst=batch)
                broadcast = Ether(dst="ff:ff:ff:ff:ff:ff")
                packet = broadcast / arp_request

                t_start = time.perf_counter()
                answered, _ = srp(
                    packet,
                    timeout=self.timeout,
                    iface=self.interface,
                    verbose=False,
                    retry=1,
                )
                elapsed = (time.perf_counter() - t_start) * 1000

                for sent, received in answered:
                    device = DiscoveredDevice(
                        ip=received.psrc,
                        mac=received.hwsrc.upper(),
                        latency_ms=elapsed / len(answered),
                        discovery_method="arp",
                    )
                    devices.append(device)
                    logger.debug(f"ARP: {device.ip} → {device.mac}")

            logger.info(f"ARP scan complete: {len(devices)} devices found")
            return devices

        except ImportError:
            logger.error("Scapy not installed. Run: pip install scapy")
            return []
        except PermissionError:
            logger.error("ARP scan requires root/admin. Falling back to ICMP.")
            return []
        except Exception as e:
            logger.error(f"ARP scan error: {e}")
            return []

    def get_arp_table(self) -> Dict[str, str]:
        """
        Read the OS ARP table cache — instant, no packets sent.
        Useful for known-online devices between scan cycles.
        """
        arp_table = {}
        try:
            output = subprocess.check_output(
                ["arp", "-n"], stderr=subprocess.DEVNULL, text=True
            )
            for line in output.strip().splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 3 and ":" in parts[2]:
                    ip = parts[0]
                    mac = parts[2].upper().replace("-", ":")
                    arp_table[ip] = mac
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Fallback: /proc/net/arp on Linux
            try:
                with open("/proc/net/arp") as f:
                    for line in f.readlines()[1:]:
                        parts = line.split()
                        if len(parts) >= 4 and parts[3] != "00:00:00:00:00:00":
                            arp_table[parts[0]] = parts[3].upper()
            except FileNotFoundError:
                pass
        return arp_table


# ─── ICMP Pinger ──────────────────────────────────────────────────────────────

class ICMPPinger:
    """
    ICMP ping scanner — fallback for cross-subnet scenarios.
    Uses concurrent threads for high-speed parallel pinging.
    Note: Many devices (especially iPhones) block ICMP when screen is off.
          Always combine with ARP for complete discovery.
    """

    def __init__(self, timeout: float = 1.5, max_workers: int = 100):
        self.timeout = timeout
        self.max_workers = max_workers

    def ping_one(self, ip: str) -> Optional[DiscoveredDevice]:
        """Ping a single IP, return DiscoveredDevice if alive."""
        import platform
        system = platform.system()

        if system == "Windows":
            cmd = ["ping", "-n", "1", "-w", str(int(self.timeout * 1000)), ip]
        else:
            cmd = ["ping", "-c", "1", "-W", str(int(self.timeout)), ip]

        try:
            t_start = time.perf_counter()
            result = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=self.timeout + 0.5,
            )
            latency = (time.perf_counter() - t_start) * 1000

            if result.returncode == 0:
                return DiscoveredDevice(
                    ip=ip,
                    latency_ms=latency,
                    discovery_method="icmp",
                )
        except subprocess.TimeoutExpired:
            pass
        except Exception as e:
            logger.debug(f"Ping {ip}: {e}")

        return None

    def scan(self, subnet: str) -> List[DiscoveredDevice]:
        """Concurrent ICMP ping sweep of entire subnet."""
        network = ipaddress.IPv4Network(subnet, strict=False)
        host_ips = [str(ip) for ip in network.hosts()]

        logger.info(f"ICMP sweep: {subnet} ({len(host_ips)} hosts)")
        devices = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self.ping_one, ip): ip for ip in host_ips}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    devices.append(result)
                    logger.debug(f"ICMP alive: {result.ip} ({result.latency_ms:.1f}ms)")

        logger.info(f"ICMP scan complete: {len(devices)} devices responding")
        return devices


# ─── mDNS Resolver ────────────────────────────────────────────────────────────

class MDNSResolver:
    """
    Resolves .local hostnames via mDNS (Bonjour/Avahi).
    Particularly effective for Apple devices.
    """

    def resolve_hostname(self, ip: str) -> str:
        """Try multiple hostname resolution methods."""
        # Method 1: Reverse DNS
        try:
            hostname = socket.gethostbyaddr(ip)[0]
            if hostname and not hostname.startswith(ip):
                return hostname.split(".")[0]  # strip domain
        except socket.herror:
            pass

        # Method 2: mDNS query via avahi-resolve (Linux)
        try:
            result = subprocess.run(
                ["avahi-resolve", "--address", ip],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0 and result.stdout:
                parts = result.stdout.strip().split()
                if len(parts) >= 2:
                    return parts[1].rstrip(".")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Method 3: NetBIOS nmblookup (Windows/Linux with samba)
        try:
            result = subprocess.run(
                ["nmblookup", "-A", ip],
                capture_output=True, text=True, timeout=3
            )
            for line in result.stdout.splitlines():
                if "<00>" in line and "GROUP" not in line:
                    name = line.strip().split()[0]
                    if name and name != ip:
                        return name
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        return ""

    def batch_resolve(self, devices: List[DiscoveredDevice], max_workers: int = 50):
        """Resolve hostnames for a list of devices concurrently."""
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self.resolve_hostname, d.ip): d
                for d in devices
            }
            for future in as_completed(futures):
                device = futures[future]
                try:
                    hostname = future.result()
                    if hostname:
                        device.hostname = hostname
                except Exception as e:
                    logger.debug(f"Hostname resolve failed for {device.ip}: {e}")


from backend.modules.fingerprint import DeviceFingerprinter
from backend.modules.port_scanner import PortScanner

# ─── Discovery Engine (Orchestrator) ─────────────────────────────────────────

class DiscoveryEngine:
    """
    Main orchestrator for device discovery.
    Combines ARP + ICMP + mDNS for maximum device detection coverage.
    Emits progress callbacks for real-time UI updates.
    """
    _scan_lock = threading.Lock()

    def __init__(self, on_device_found: Optional[Callable] = None):
        self.on_device_found = on_device_found  # callback(device: DiscoveredDevice)
        self._known_devices: Dict[str, DiscoveredDevice] = {}
        self._scan_running = False
        self.mdns = MDNSResolver()
        self.fingerprinter = DeviceFingerprinter()

    def scan_network(
        self,
        subnet: Optional[str] = None,
        interface: Optional[str] = None,
        methods: List[str] = None,
        aggressive: bool = False
    ) -> List[DiscoveredDevice]:
        """
        Run a full network discovery scan.
        """
        if methods is None:
            methods = ["arp", "icmp", "mdns", "tcp_stealth"]

        targets = []
        if subnet and interface:
            targets.append({"subnet": subnet, "interface": interface})
        else:
            nets = get_local_network()
            if not nets: return []
            targets = nets

        all_devices: Dict[str, DiscoveredDevice] = {}
        has_perms, perm_msg = check_permissions()

        with self._scan_lock:
            self._scan_running = True

            for target in targets:
                curr_subnet = target['subnet']
                curr_iface = target['interface']
                logger.info(f"🛰️ Initiating discovery on {curr_subnet} ({curr_iface})")

                # ── Phase 1: ARP Sweep ──────────────
                if "arp" in methods:
                    if has_perms:
                        arp_scanner = ARPScanner(interface=curr_iface)
                        arp_devices = arp_scanner.scan(curr_subnet)
                        for device in arp_devices:
                            all_devices[device.ip] = device

                        arp_table = arp_scanner.get_arp_table()
                        for ip, mac in arp_table.items():
                            if ip not in all_devices:
                                # Only add if it belongs to the current subnet
                                try:
                                    if ipaddress.IPv4Address(ip) in ipaddress.IPv4Network(curr_subnet):
                                        all_devices[ip] = DiscoveredDevice(ip=ip, mac=mac, discovery_method="arp_cache")
                                except: pass
                            elif not all_devices[ip].mac:
                                all_devices[ip].mac = mac
                    else:
                        logger.warning("Skipping ARP scan (insufficient permissions)")

                # ── Phase 2: ICMP Ping ──────────────────
                if "icmp" in methods:
                    icmp_scanner = ICMPPinger()
                    icmp_devices = icmp_scanner.scan(curr_subnet)
                    for device in icmp_devices:
                        if device.ip not in all_devices:
                            all_devices[device.ip] = device
                        else:
                            if device.latency_ms > 0:
                                all_devices[device.ip].latency_ms = device.latency_ms

            # ── Phase 3: Aggressive TCP Probing (Hidden Devices) ────────────────
            if aggressive or "tcp_stealth" in methods:
                stealth = TCPStealthScanner()
                # Aggregate all unknown IPs from all scanned subnets
                all_hosts = []
                for target in targets:
                    net = ipaddress.IPv4Network(target['subnet'], strict=False)
                    all_hosts.extend([str(ip) for ip in net.hosts()])
                
                unknown_ips = [ip for ip in all_hosts if ip not in all_devices]
                
                if unknown_ips:
                    logger.info(f"Deep scanning {len(unknown_ips)} hidden IPs via TCP...")
                    if aggressive:
                        probe_ports = [80, 443, 554, 8554, 9100, 631, 22, 23, 8080, 5000]
                        scanner = PortScanner(timeout=0.5, max_workers=200)
                        probe_results = scanner.scan_network_ports(unknown_ips, ports=probe_ports, mode="custom")
                        for ip, open_ports in probe_results.items():
                            if open_ports:
                                if ip not in all_devices:
                                    all_devices[ip] = DiscoveredDevice(ip=ip, discovery_method="tcp_aggressive")
                                all_devices[ip].open_ports = [p.to_dict() for p in open_ports]
                    else:
                        with ThreadPoolExecutor(max_workers=50) as executor:
                            futures = {executor.submit(stealth.probe, ip): ip for ip in unknown_ips}
                            for future in as_completed(futures):
                                dev = future.result()
                                if dev: all_devices[dev.ip] = dev

            # Attempt to resolve missing MACs for found IPs via ARP cache again
            if has_perms:
                arp_scanner = ARPScanner(interface=interface)
                arp_table = arp_scanner.get_arp_table()
                for ip, dev in all_devices.items():
                    if not dev.mac and ip in arp_table:
                        dev.mac = arp_table[ip]

            # ── Phase 4: Hostname Resolution ─────────────────────────────────────
            if "mdns" in methods:
                device_list = list(all_devices.values())
                logger.info(f"Resolving hostnames for {len(device_list)} devices...")
                self.mdns.batch_resolve(device_list)

            # ── Phase 5: Deep Fingerprinting ─────────────────────────────────────
            for d in all_devices.values():
                # FIX BE-01: safe port extraction — open_ports is now a proper field
                ports = []
                try:
                    if d.open_ports:
                        first = d.open_ports[0]
                        ports = [p['port'] for p in d.open_ports] if isinstance(first, dict) else list(d.open_ports)
                except (IndexError, KeyError, TypeError):
                    ports = []

                try:
                    fp = self.fingerprinter.fingerprint(
                        mac=d.mac, hostname=d.hostname, ttl=d.ttl, open_ports=ports
                    )
                    # Fields now exist on dataclass — safe to set directly
                    d.vendor = fp.vendor
                    d.device_type = fp.device_type
                    d.os_hint = fp.os_hint
                    d.arch_hint = fp.arch_hint
                    d.device_icon = fp.to_dict().get("device_icon", "❓")
                except Exception as fp_err:
                    logger.debug(f"Fingerprint failed for {d.ip}: {fp_err}")

            self._scan_running = False

        # ── Phase 6: Result Compilation ────────────────────
        result = []
        for ip, device in all_devices.items():
            device.last_seen = time.time()
            is_new = ip not in self._known_devices
            self._known_devices[ip] = device
            if self.on_device_found:
                self.on_device_found(device, is_new=is_new)
            result.append(device)

        return result

    def get_known_devices(self) -> List[DiscoveredDevice]:
        """Return all previously discovered devices."""
        return list(self._known_devices.values())

    def mark_devices_offline(self, current_ips: Set[str]):
        """
        Compare current scan results with known devices.
        Returns list of devices that went offline.
        """
        offline = []
        for ip, device in self._known_devices.items():
            if ip not in current_ips:
                if device.is_online:
                    offline.append(device)
        return offline


# ─── Quick Test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
    )

    def on_found(device: DiscoveredDevice, is_new: bool = False):
        tag = "NEW" if is_new else "UPD"
        print(f"  [{tag}] {device.ip:<16} {device.mac:<18} {device.hostname:<20} "
              f"({device.discovery_method}, {device.latency_ms:.1f}ms)")

    engine = DiscoveryEngine(on_device_found=on_found)

    print("\n🔍 Detecting local networks...")
    networks = get_local_network()
    for net in networks:
        print(f"  Interface: {net['interface']} | Subnet: {net['subnet']} | "
              f"Gateway: {net['gateway']}")

    print("\n🛰️  Starting discovery scan...\n")
    devices = engine.scan_network()
    print(f"\n✅ Found {len(devices)} devices\n")
