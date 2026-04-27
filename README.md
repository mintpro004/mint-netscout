# 🛰️ Mint NetScout SIGINT PRO

NetScout is a professional-grade, real-time network intelligence and monitoring system. Designed for security auditing and tactical discovery, it features a hybrid discovery engine capable of identifying hidden assets, fingerprinting devices, and monitoring network traffic.

---

## 📖 Complete User Guide

### 1. Installation & Setup
NetScout includes a **Self-Healing Setup** script that handles dependencies and system permissions automatically.

#### **Automatic Installation (Recommended)**
```bash
# Clone the repository
git clone https://github.com/mintpro004/mint-netscout.git
cd mint-netscout

# Run the robust installer (handles venv and dependencies automatically)
sudo bash install.sh
```

#### **Python Setup Alternative**
```bash
sudo python3 setup.py
```

---

### 2. Running the Tool
There are two ways to start NetScout:

- **Option A (Launcher):** Run `./netscout.sh` (Created during setup).
- **Option B (Manual):** Run `sudo python3 -m backend.api.server`.

Once started, the dashboard will be available at: **`http://localhost:5000`**

---

### 3. Discovery Modes
NetScout offers two levels of network discovery:

| Mode | Trigger | Description |
| :--- | :--- | :--- |
| **Standard Discovery** | `▶ DEEP SCAN` | Fast, multi-threaded scan using ARP, ICMP, and mDNS. Best for general monitoring. |
| **Aggressive Mode** | `☢ AGGRESSIVE` | Performs deep TCP probing on all potential IPs. Essential for finding hidden devices (Cams/IoT) that block standard pings. |

---

### 4. Asset Management & Investigation
Click on any device in the **Radar** or **Asset Registry** to open the management console:

- **🔍 Investigate:** Launches an immediate, full-port service audit of the specific device. Identifies running services and potential entry points.
- **🚫 Block Device:** Marks the device as "Untrusted" in the database and flags it in the UI (Simulates security isolation).
- **🗑 Remove:** Permanently deletes the asset's history and logs from the local database.
- **✓ Trust:** Verifies the device, adding it to the "Trusted Assets" whitelist.

---

### 5. Threat Intelligence Zone
This zone displays **Real-Time Security Events**. 
- If an active asset on your network attempts to communicate with a known malicious domain (from our integrated intelligence feed), it will be flagged here.
- You can immediately click **🔍 INVESTIGATE ASSET** from the threat card to begin a deep audit of the compromised device.

---

### 6. Chromebook (Crostini) Specifics
NetScout is fully optimized for the Chromebook Linux container:
- **Virtual Bridge:** Crostini uses a virtual network. NetScout automatically detects this and adjusts scan timings.
- **Capabilities:** If `setcap` fails during setup, simply ensure you launch the tool with `sudo` to maintain raw socket access for ARP scans.

---
Developed by **mintprojects** | v2.1.0-PRO
