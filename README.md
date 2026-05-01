<div align="center">

# 🛰️ Mint NetScout — SIGINT PRO

**Professional-grade real-time network intelligence, automated device fingerprinting, and security auditing**

![Version](https://img.shields.io/badge/version-2.1.0--PRO-00ffaa?style=flat-square&labelColor=020408)
![Python](https://img.shields.io/badge/python-3.10%2B-3776ab?style=flat-square&labelColor=020408)
![React](https://img.shields.io/badge/react-19-61dafb?style=flat-square&labelColor=020408)
![License](https://img.shields.io/badge/license-MIT-00ffaa?style=flat-square&labelColor=020408)

</div>

---

## Overview

Mint NetScout is a self-hosted network scanner and monitoring dashboard. It discovers every device on your LAN, fingerprints hardware vendors and OS types, tracks open ports, and surfaces threat-level alerts — all through a real-time React dashboard backed by a Flask + SocketIO server.

**Key capabilities:**

- Hybrid discovery engine — ARP, ICMP ping, mDNS, and optional deep TCP probing
- Automatic vendor/OS fingerprinting from MAC OUI database
- Real-time WebSocket alerts for new devices, port changes, and threat events
- Full device lifecycle management — trust, block, investigate, hide, remove
- Aggressive mode for detecting IoT/cameras that filter standard pings
- Persistent SQLite registry with traffic tracking and latency history

---

## Requirements

| Component | Minimum |
|-----------|---------|
| OS | Linux (Debian/Ubuntu/Kali) or Chromebook Crostini |
| Python | 3.10+ |
| Node.js | 18+ (only if modifying the React frontend) |
| Privileges | `sudo` or `CAP_NET_RAW` on the Python binary |
| RAM | 256 MB |

---

## Quick Start

```bash
git clone https://github.com/mintpro004/mint-netscout.git
cd mint-netscout
sudo bash mint-netscout-main/install.sh
./launch-gui.sh
```

Dashboard opens automatically at **http://localhost:5000** (or via the Electron GUI)

---

## Installation

### Automatic (Recommended)

```bash
sudo bash mint-netscout-main/install.sh
```

The installer:
1. Installs `libpcap-dev`, `python3-venv`, `python3-pip`, and `lsof` via apt
2. Creates an isolated `.venv` virtual environment in `mint-netscout-main/`
3. Installs all Python dependencies from `requirements.txt`
4. Initialises the SQLite database in `mint-netscout-main/data/`
5. Generates `netscout.sh` — a self-healing launcher
6. Sets `CAP_NET_RAW` on the venv Python binary
7. Installs frontend dependencies and configures the desktop entry

### Manual

```bash
cd mint-netscout-main
# System dependencies
sudo apt-get install -y libpcap-dev python3-pip python3-venv python3-full lsof

# Virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Database
python3 -c "from backend.database.models import init_db; init_db()"

# Run (sudo needed for raw socket access)
sudo .venv/bin/python3 -m backend.api.server
```

---

## Running

```bash
# Recommended — Unified GUI Launcher (starts both backend and frontend)
./launch-gui.sh

# CLI Launcher (backend only)
cd mint-netscout-main && ./netscout.sh
```

---

## Frontend Development

The dashboard is built with React + Vite. The compiled output lives in `frontend_build/` and is served directly by Flask — no separate web server needed.

```bash
cd netscout-react

# Install dependencies (first time only)
npm install

# Start dev server with hot reload (proxied to Flask on :5000)
npm run dev
# → http://localhost:5173

# Build for production (outputs to frontend_build/)
npm run build
```

The Vite dev proxy forwards `/api/*` and `/socket.io/*` to `localhost:5000`, so the Flask backend must be running when you use `npm run dev`.

### Project Layout

```
netscout-react/src/
├── api/index.js            # All REST calls + socket factory
├── hooks/
│   ├── useNetScout.js      # Central data + real-time state hook
│   └── useToast.js         # Stable event-emitter toast system
├── components/
│   ├── ui.jsx              # Shared primitives: Btn, Badge, Panel, Modal, Toast
│   ├── Sidebar.jsx         # Navigation panel
│   ├── Topbar.jsx          # Live metrics bar + scan buttons
│   ├── DeviceModal.jsx     # Device detail, investigate, block, hide, remove
│   └── Modals.jsx          # Add device, update, exit confirm
├── pages/
│   ├── Dashboard.jsx       # KPIs, radar, alert feed, latency chart
│   ├── Devices.jsx         # Filterable device table
│   └── Pages.jsx           # Threats, Alerts, Network, Settings
└── utils.js                # deviceIcon, fmtTime, fmtAgo, isValidIPv4, parsePorts
```

---

## Usage

### Dashboard

The main view shows four live KPI cards, a network radar plotting all online devices, an alert feed, a latency chart derived from real scan data, and system intelligence about active network interfaces.

### Scanning

| Button | Mode | Description |
|--------|------|-------------|
| `▶ DEEP SCAN` | Standard | ARP + ICMP + mDNS sweep. Fast and low-noise. |
| `☢ AGGRESSIVE` | Deep TCP | Full port probing on all IPs. Finds cameras, IoT, and devices that block ping. |

Scan progress is broadcast over WebSocket and shown in the banner. The monitor runs a background cycle every 30 seconds (configurable in Settings).

### Device Management

Click any device on the radar or in the Asset Registry to open the device modal:

| Action | Description |
|--------|-------------|
| 🔍 **Investigate** | Runs a full port scan on that device, shows open ports with risk classification |
| 🚫 **Block / 🔓 Unblock** | Marks device unverified/blocked in the database |
| 👁 **Hide** | Removes from main view without deleting (stored in browser localStorage) |
| 🗑 **Remove** | Permanently deletes from the database |

### Filters (Asset Registry)

Filter devices by: All · Online · Offline · Trusted · Unverified · Hidden

### Threat Zone

Displays real-time threat events when active assets contact known malicious endpoints. Click **INVESTIGATE** or **BLOCK** directly from the threat card.

### Alerts

Full alert log with severity badges. Use **ACK** per-alert or **ACK ALL** to clear the feed.

---

## Configuration

### Scan Frequency

Adjustable in the Settings page (30s aggressive / 2m balanced / 10m stealth). The monitor subtracts scan time from the interval so the actual cycle stays accurate.

### Permissions

If `setcap` fails during install (common on Crostini), launch with `sudo`:

```bash
sudo ./netscout.sh
```

ARP scans require `CAP_NET_RAW`. Without it, discovery falls back to ICMP-only mode — still functional but slower to detect offline transitions.

### Chromebook (Crostini) Notes

- NetScout auto-detects the virtual bridge used by Crostini and adjusts scan timing
- Always use `sudo ./netscout.sh` on Crostini since `setcap` on the venv binary typically fails
- Devices on the host ChromeOS side of the bridge may not be visible — this is a kernel network namespace limitation

---

## API Reference

All endpoints are served at `http://localhost:5000/api/`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/devices` | List all known devices |
| POST | `/api/devices/add` | Register a device manually |
| DELETE | `/api/devices/:mac` | Remove a device |
| POST | `/api/devices/:mac/trust` | `{ trusted: bool }` |
| POST | `/api/devices/:mac/block` | `{ blocked: bool }` |
| POST | `/api/devices/:mac/investigate` | Full port scan |
| POST | `/api/scan` | `{ aggressive: bool }` — trigger scan |
| GET | `/api/intel/unsafe` | Active threat events |
| GET | `/api/status` | Server status, network interfaces, permissions |
| GET | `/api/update/check` | Check for updates |

WebSocket events (Socket.IO): `scan_progress`, `scan_complete`, `scan_error`, `alert`

---

## Troubleshooting

**Port 5000 already in use**
The `netscout.sh` launcher automatically kills any process on port 5000 before starting. For manual runs: `sudo lsof -ti:5000 | xargs sudo kill -9`

**No devices found / ARP not working**
Run with `sudo`. Check with `ip link` that the correct interface is active. On VMs, ARP scans may only see the host gateway.

**`scapy` import error on install**
Ensure `libpcap-dev` is installed: `sudo apt-get install libpcap-dev`

**Dashboard blank / JS errors**
Rebuild the frontend: `cd netscout-react && npm run build`

**Database errors on first run**
Re-initialise: `python3 -c "from backend.database.models import init_db; init_db()"`

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Browser                                                │
│  React 19 + Vite  ←──── WebSocket (Socket.IO) ────┐   │
│  CSS Modules                                        │   │
└────────────────── REST /api/* ─────────────────────┼───┘
                                                     │
┌─────────────────────────────────────────────────────┼───┐
│  Flask + Flask-SocketIO + Eventlet                  │   │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐ │   │
│  │ Discovery   │  │ Port Scanner │  │  Monitor   │ │   │
│  │ Engine      │  │ (TCP/UDP)    │  │  Worker    │─┘   │
│  │ ARP+ICMP    │  │              │  │  30s cycle │     │
│  │ mDNS+NetBIOS│  └──────────────┘  └────────────┘     │
│  └─────────────┘                                        │
│  ┌──────────────────────────────────────────────────┐   │
│  │  SQLite  (SQLAlchemy ORM)                        │   │
│  │  Device registry · Alert log · Traffic tracking  │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## License

MIT — see `LICENSE`

---

<div align="center">
Developed by <strong>mintprojects</strong> · v2.1.0-PRO
</div>
