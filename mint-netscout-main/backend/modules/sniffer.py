"""
NetScout Traffic Sniffer & Interception Module
==============================================
Real-time packet sniffing for:
  1. DNS query identification
  2. TLS SNI extraction (HTTPS domain tracking)
  3. Traffic volume monitoring per device
  4. Active ARP Spoofing for device 'blocking'
"""

import logging
import threading
import time
import re
from scapy.all import sniff, IP, TCP, UDP, DNS, DNSQR, ARP, send, Ether, get_if_hwaddr, get_if_addr
from backend.database.models import get_db, DeviceRepository

logger = logging.getLogger("netscout.sniffer")

# More robust domain regex
DOMAIN_REGEX = re.compile(r'([a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}')

class TrafficSniffer:
    def __init__(self, interface: str):
        self.interface = interface
        self._running = False
        self._thread = None
        self._block_list = set()  # MACs to block via ARP spoofing
        self._spoof_thread = None
        self._traffic_stats = {} # {ip: {'in': 0, 'out': 0}}
        self._stats_lock = threading.Lock()

    def start(self):
        if self._running: return
        self._running = True
        self._thread = threading.Thread(target=self._sniff_loop, daemon=True)
        self._thread.start()
        
        self._spoof_thread = threading.Thread(target=self._spoof_loop, daemon=True)
        self._spoof_thread.start()

        # Stats flusher thread
        self._flush_thread = threading.Thread(target=self._flush_stats_loop, daemon=True)
        self._flush_thread.start()

        logger.info(f"Traffic Sniffer & Spoof-Blocker started on {self.interface}")

    def stop(self):
        self._running = False
        if self._thread: self._thread.join(timeout=1)

    def set_blocking(self, mac_list: list):
        """Update the list of MAC addresses to block."""
        self._block_list = set(m.upper() for m in mac_list if m)

    def _sniff_loop(self):
        try:
            # Optimized BPF filter: Only capture DNS, TLS (SNI), and ARP
            # This drastically reduces CPU load in busy network environments
            bpf_filter = "udp port 53 or tcp port 443 or arp"
            sniff(
                iface=self.interface, 
                prn=self._handle_packet, 
                store=0, 
                stop_filter=lambda x: not self._running,
                filter=bpf_filter
            )
        except Exception as e:
            logger.error(f"Sniffer error: {e}")

    def _handle_packet(self, pkt):
        if not pkt.haslayer(IP): return
        
        src_ip = pkt[IP].src
        dst_ip = pkt[IP].dst
        pkt_len = len(pkt)
        
        # 1. Traffic Accounting
        with self._stats_lock:
            # Stats for SOURCE (Traffic OUT from this device)
            if src_ip not in self._traffic_stats: self._traffic_stats[src_ip] = {'in': 0, 'out': 0}
            self._traffic_stats[src_ip]['out'] += pkt_len
            
            # Stats for DESTINATION (Traffic IN to this device)
            if dst_ip not in self._traffic_stats: self._traffic_stats[dst_ip] = {'in': 0, 'out': 0}
            self._traffic_stats[dst_ip]['in'] += pkt_len

        # 2. DNS Extraction
        if pkt.haslayer(DNS) and pkt.getlayer(DNS).qr == 0:
            try:
                domain = pkt.getlayer(DNSQR).qname.decode().rstrip('.')
                self._log_visit(src_ip, domain)
            except: pass

        # 3. TLS SNI Extraction
        if pkt.haslayer(TCP) and pkt[TCP].dport == 443 and len(pkt[TCP].payload) > 100:
            try:
                payload = bytes(pkt[TCP].payload)
                if payload[0] == 0x16: # Handshake
                    raw_str = payload.decode('ascii', 'ignore').lower()
                    match = DOMAIN_REGEX.search(raw_str)
                    if match:
                        domain = match.group(0)
                        if len(domain) > 4 and '.' in domain:
                            self._log_visit(src_ip, domain)
            except: pass

    def _log_visit(self, ip: str, domain: str):
        if hasattr(self, 'log_callback') and self.log_callback:
            self.log_callback(ip, domain)

    def _flush_stats_loop(self):
        """Periodically flushes accumulated traffic stats to the DB via callback."""
        while self._running:
            time.sleep(10) # Flush every 10 seconds
            
            stats_to_flush = {}
            with self._stats_lock:
                stats_to_flush = self._traffic_stats
                self._traffic_stats = {} # Clear for next cycle
            
            if stats_to_flush and hasattr(self, 'traffic_callback') and self.traffic_callback:
                try:
                    self.traffic_callback(stats_to_flush)
                except Exception as e:
                    logger.error(f"Traffic flush error: {e}")

    def _spoof_loop(self):
        """Continuously ARP spoof blocked devices to redirect their traffic to us (and then drop it)."""
        while self._running:
            if not self._block_list:
                time.sleep(2)
                continue
            
            db = get_db()
            try:
                repo = DeviceRepository(db)
                # We need the gateway IP to spoof the device into thinking we are the gateway
                from backend.core.engine import get_local_network
                nets = get_local_network()
                if not nets: continue
                gw_ip = nets[0].get('gateway')
                if not gw_ip: continue

                for mac in self._block_list:
                    dev = repo.get_by_mac(mac)
                    if dev and dev.ip:
                        # Tell device [target] that I am [gateway]
                        # Ether(dst=dev.mac) -> ARP(op=2, psrc=gw_ip, pdst=dev.ip)
                        pkt = Ether(dst=dev.mac) / ARP(op=2, psrc=gw_ip, pdst=dev.ip)
                        send(pkt, iface=self.interface, verbose=False)
            except Exception as e:
                logger.error(f"Spoof loop error: {e}")
            finally:
                db.close()
            
            time.sleep(2) # Send every 2 seconds to maintain the "poison"
