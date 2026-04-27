# 🛰️ Mint NetScout SIGINT PRO

NetScout is a professional-grade, real-time network intelligence and monitoring system. Designed for security auditing and tactical discovery, it features a hybrid discovery engine capable of identifying hidden assets, fingerprinting devices, and monitoring network traffic.

## 🚀 Features

- **Standard & Aggressive Discovery:** Hybrid scanning using ARP, ICMP, mDNS, and deep TCP probing to find even the most stealthy devices.
- **Deep Fingerprinting:** Identifies manufacturer, device type (Camera, Printer, IoT), and OS hints via OUI and service analysis.
- **Security Auditing:** Investigate individual assets with full-port audits and vulnerability checks.
- **Real-time Monitoring:** WebSocket-based dashboard with live alerts for new devices and network events.
- **Cross-Platform:** Full support for Linux, Windows, macOS, and **Chromebooks (Crostini)**.

## 💻 Installation

### Self-Healing Installation
The included `setup.py` automatically configures your environment, installs dependencies, and sets necessary system capabilities.

```bash
# 1. Clone the repository
git clone https://github.com/mintpro004/mint-netscout.git
cd mint-netscout

# 2. Run the setup script (requires sudo for capabilities on Linux)
sudo python3 setup.py
```

### Manual Installation
```bash
pip install -r requirements.txt
python3 -m backend.api.server
```

## 📱 Chromebook (Crostini) Support
NetScout is fully optimized for Chromebooks. Because Crostini uses a virtualized network bridge, follow these tips:
1. **Permissions:** Always run the `setup.py` with `sudo` to ensure `python3` has `CAP_NET_RAW` permissions. This allows ARP scanning through the bridge.
2. **Aggressive Mode:** If standard discovery misses a device, use the **☢ AGGRESSIVE** scan button to probe the subnet via TCP.

## 🛠️ Usage
- **Web Dashboard:** `http://localhost:5000`
- **CLI Interface:** `python3 -m backend.cli scan`

---
Developed by **mintprojects** | v2.1.0-PRO
