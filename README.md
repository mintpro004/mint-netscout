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
The included `setup.py` automatically configures your environment. It attempts a direct installation and, if blocked by your OS (PEP 668), it will automatically create a secure virtual environment and a launcher script.

```bash
# 1. Clone the repository
git clone https://github.com/mintpro004/mint-netscout.git
cd mint-netscout

# 2. Run the setup script (recommended)
sudo python3 setup.py
```

### 🛠️ Usage
- **Primary:** `./netscout.sh` (Created by setup)
- **Manual:** `python3 -m backend.api.server`
- **Dashboard:** `http://localhost:5000`

---
Developed by **mintprojects** | v2.1.0-PRO
