#!/usr/bin/env python3
"""
NetScout CLI
============
Command-line interface for quick network scans without the web UI.

Usage:
  python -m backend.cli scan              # Scan local network
  python -m backend.cli scan --full       # Full port scan too
  python -m backend.cli scan --subnet 192.168.1.0/24
  python -m backend.cli monitor           # Start real-time monitor
  python -m backend.cli ping 8.8.8.8     # Quick latency test
  python -m backend.cli devices           # List known devices from DB
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.utils.helpers import setup_logging, get_platform_info


def cmd_scan(args):
    from backend.core.engine import (
        DiscoveryEngine, get_local_network, check_permissions
    )
    from backend.modules.fingerprint import DeviceFingerprinter
    from backend.modules.port_scanner import PortScanner
    from backend.database.models import init_db, get_db, DeviceRepository

    setup_logging(args.log_level)

    # Platform info
    info = get_platform_info()
    print(f"\n🛰️  NetScout CLI — {info['system']} {info['release']}")
    if info["is_chromebook"]:
        print("   📱 Chromebook (Crostini) detected")

    # Permissions
    has_perms, msg = check_permissions()
    print(f"   {'✅' if has_perms else '⚠️ '} {msg}\n")

    # Detect network
    networks = get_local_network()
    if not networks:
        print("❌ No network interfaces found.")
        sys.exit(1)

    for net in networks:
        print(f"   📡 {net['interface']} — {net['subnet']} ({net['host_count']} hosts)")
        if net["gateway"]:
            print(f"      Gateway: {net['gateway']}")

    subnet = args.subnet or networks[0]["subnet"]
    interface = networks[0]["interface"]

    print(f"\n🔍 Scanning {subnet}...\n")
    t_start = time.time()

    fingerprinter = DeviceFingerprinter()
    port_scanner = PortScanner(timeout=0.8) if args.ports or args.full else None

    found = []

    def on_found(device, is_new=False):
        fp = fingerprinter.fingerprint(
            mac=device.mac,
            hostname=device.hostname,
            ttl=device.ttl,
        )
        tag = "🆕" if is_new else "  "
        trust = "❓" if not args.full else ""
        print(
            f"  {tag} {fp.to_dict()['device_icon']} "
            f"{device.ip:<16} "
            f"{device.mac:<18} "
            f"{fp.vendor:<22} "
            f"{device.hostname or '':<20} "
            f"{'%.1fms' % device.latency_ms:<10}"
        )
        found.append((device, fp))

    engine = DiscoveryEngine(on_device_found=on_found)

    print(f"  {'':2} {'':2} {'IP':<16} {'MAC':<18} {'Vendor':<22} {'Hostname':<20} {'Latency'}")
    print("  " + "─" * 100)

    devices = engine.scan_network(
        subnet=subnet,
        interface=interface,
        methods=["arp", "icmp", "mdns"],
    )

    elapsed = time.time() - t_start
    print(f"\n✅ Found {len(devices)} devices in {elapsed:.1f}s\n")

    # Port scan if requested
    if (args.ports or args.full) and devices:
        print("🔌 Port scanning discovered devices...\n")
        ips = [d.ip for d in devices]
        mode = "full" if args.full else "fast"
        results = port_scanner.scan_network_ports(ips, mode=mode, device_max_workers=5)
        for ip, ports in results.items():
            if ports:
                print(f"  {ip}:")
                for p in ports:
                    print(f"    {p.icon} {p.port:<6} {p.service:<20} [{p.risk}]")

    # Save to DB
    if not args.no_db:
        init_db()
        db = get_db()
        try:
            repo = DeviceRepository(db)
            for device, fp in found:
                if device.mac:
                    repo.upsert_device({**device.to_dict(), **fp.to_dict()})
            print(f"💾 Saved {len(found)} devices to database")
        finally:
            db.close()

    # JSON output
    if args.json:
        output = []
        for device, fp in found:
            output.append({**device.to_dict(), **fp.to_dict()})
        print("\n" + json.dumps(output, indent=2))


def cmd_monitor(args):
    from backend.modules.monitor import MonitorWorker
    setup_logging(args.log_level)

    print("\n🛰️  NetScout Monitor — Press Ctrl+C to stop\n")

    def on_event(alert):
        ts = time.strftime("%H:%M:%S", time.localtime(alert.timestamp))
        print(f"  {alert.emoji}  [{ts}] {alert.message}")

    worker = MonitorWorker(
        scan_interval=args.interval,
        on_event=on_event,
    )
    try:
        worker.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n⏹  Monitor stopped.")
        worker.stop()


def cmd_ping(args):
    from backend.modules.monitor import LatencyTester
    setup_logging("WARNING")

    target = args.target
    count = args.count
    print(f"\n📊 Pinging {target} ({count} packets)...\n")

    tester = LatencyTester(target=target, count=count)
    result = tester.ping_series()

    if "error" in result:
        print(f"❌ Error: {result['error']}")
        return

    print(f"  Min:    {result['min_ms']}ms")
    print(f"  Avg:    {result['avg_ms']}ms")
    print(f"  Max:    {result['max_ms']}ms")
    print(f"  Jitter: {result['jitter_ms']}ms")
    print(f"  Sent:   {count}  Received: {result['count']}")

    bar_width = 30
    for i, sample in enumerate(result["samples"]):
        filled = int((sample / max(result["max_ms"], 1)) * bar_width)
        bar = "█" * filled
        print(f"  [{i+1:2}] {sample:6.1f}ms {bar}")


def cmd_devices(args):
    from backend.database.models import init_db, get_db, DeviceRepository
    setup_logging("WARNING")

    init_db()
    db = get_db()
    try:
        repo = DeviceRepository(db)
        devices = repo.get_all(online_only=args.online)
        stats = repo.get_stats()

        print(f"\n📋 Devices in database ({stats['total']} total, {stats['online']} online)\n")
        print(f"  {'Icon':<4} {'IP':<16} {'MAC':<18} {'Vendor':<22} {'Type':<12} {'Status':<8} {'Last Seen'}")
        print("  " + "─" * 100)

        for d in devices:
            status = "🟢 Online" if d.is_online else "🔴 Offline"
            last = time.strftime("%m/%d %H:%M", time.localtime(d.last_seen)) if d.last_seen else "Never"
            print(
                f"  {d.device_icon:<4} {d.ip:<16} {d.mac:<18} "
                f"{d.vendor[:20]:<22} {d.device_type:<12} {status:<12} {last}"
            )
        print()
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        prog="netscout",
        description="🛰️  NetScout — Local Network Monitor",
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity"
    )
    sub = parser.add_subparsers(dest="command")

    # scan
    p_scan = sub.add_parser("scan", help="Scan the local network")
    p_scan.add_argument("--subnet", help="CIDR subnet to scan (auto-detected if omitted)")
    p_scan.add_argument("--ports", action="store_true", help="Run quick port scan on found devices")
    p_scan.add_argument("--full", action="store_true", help="Run full port scan (slow)")
    p_scan.add_argument("--no-db", action="store_true", help="Don't save results to database")
    p_scan.add_argument("--json", action="store_true", help="Output JSON")

    # monitor
    p_mon = sub.add_parser("monitor", help="Start real-time background monitoring")
    p_mon.add_argument("--interval", type=int, default=30, help="Scan interval in seconds")

    # ping
    p_ping = sub.add_parser("ping", help="Latency test to a target host")
    p_ping.add_argument("target", nargs="?", default="8.8.8.8")
    p_ping.add_argument("--count", type=int, default=10)

    # devices
    p_dev = sub.add_parser("devices", help="List devices from the database")
    p_dev.add_argument("--online", action="store_true", help="Show online devices only")

    args = parser.parse_args()

    dispatch = {
        "scan": cmd_scan,
        "monitor": cmd_monitor,
        "ping": cmd_ping,
        "devices": cmd_devices,
    }

    if args.command in dispatch:
        dispatch[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
