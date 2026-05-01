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
from scapy.all import sniff, IP, TCP, UDP, DNS, DNSQR, ARP, send, Ether, get_if_hwaddr, get_if_addr
from backend.database.models import get_db, DeviceRepository

logger = logging.getLogger("netscout.sniffer")

class TrafficSniffer:
    def __init__(self, interface: str):
        self.interface = interface
        self._running = False
        self._thread = None
        self._block_list = set()  # MACs to block via ARP spoofing
        self._spoof_thread = None

    def start(self):
        if self._running: return
        self._running = True
        self._thread = threading.Thread(target=self._sniff_loop, daemon=True)
        self._thread.start()
        
        self._spoof_thread = threading.Thread(target=self._spoof_loop, daemon=True)
        self._spoof_thread.start()
        logger.info(f"Traffic Sniffer & Spoof-Blocker started on {self.interface}")

    def stop(self):
        self._running = False
        if self._thread: self._thread.join(timeout=1)

    def set_blocking(self, mac_list: list):
        """Update the list of MAC addresses to block."""
        self._block_list = set(m.upper() for m in mac_list if m)

    def _sniff_loop(self):
        try:
            sniff(iface=self.interface, prn=self._handle_packet, store=0, stop_filter=lambda x: not self._running)
        except Exception as e:
            logger.error(f"Sniffer error: {e}")

    def _handle_packet(self, pkt):
        if not pkt.haslayer(IP): return
        
        src_ip = pkt[IP].src
        dst_ip = pkt[IP].dst
        
        # 1. DNS Extraction
        if pkt.haslayer(DNS) and pkt.getlayer(DNS).qr == 0:
            try:
                domain = pkt.getlayer(DNSQR).qname.decode().rstrip('.')
                self._log_visit(src_ip, domain)
            except: pass

        # 2. TLS SNI Extraction (Simple check for common patterns)
        # Most modern TLS ClientHello starts with \x16\x03\x01 or \x16\x03\x03
        if pkt.haslayer(TCP) and pkt[TCP].dport == 443 and len(pkt[TCP].payload) > 100:
            try:
                payload = bytes(pkt[TCP].payload)
                if payload[0] == 0x16: # Handshake
                    # Very basic extraction: search for common domain suffixes in the payload
                    # This is a heuristic fallback since full TLS parsing in scapy is heavy
                    raw_str = payload.decode('ascii', 'ignore')
                    # Look for things that look like domains
                    import re
                    match = re.search(r'([a-z0-9-]+\.)+[a-z]{2,}', raw_str)
                    if match:
                        self._log_visit(src_ip, match.group(0))
            except: pass

        # 3. Traffic Accounting
        # (This is simplified; a real impl would batch updates)
        # For now, we just skip frequent DB writes here and rely on the monitor for volume trends

    def _log_visit(self, ip: str, domain: str):
        # We need a mac to log a visit in our DB
        # This will be handled by the monitor/server linking IPs to MACs
        # For efficiency, we just pass this up or log it locally
        pass # Will be integrated into server/monitor callbacks

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
