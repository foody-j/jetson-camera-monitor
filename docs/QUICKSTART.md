# Quick Start Guide

## 🚀 Launch in 3 Steps

### Step 1: Install Dependencies
```bash
pip install flask pyserial numpy
```

### Step 2: Configure RS485 (if needed)
```bash
# Check your RS485 device
ls -l /dev/ttyUSB*

# Edit config if device is different
vim config/system_config.json
# Change "port": "/dev/ttyUSB0" to your device
```

### Step 3: Run Dashboard
```bash
python scripts/run_monitoring_dashboard.py
```

### Step 4: Access Dashboard
Open browser: **http://localhost:5000**

---

## 🎛️ Using the Dashboard

### Start Services
1. Open http://localhost:5000
2. Click **"Start"** on service cards
3. Or click **"Start All Services"**

### View Vibration Data
- Check **Vibration Monitoring** panel
- See real-time X, Y, Z axes
- Watch for alerts

### Configure Schedule
1. Default: **8:30 AM - 7:00 PM**
2. Click **"Edit Schedule"** to change
3. Enable/disable **"Manual Override"** as needed

---

## ⚙️ Configuration File

Edit `config/system_config.json`:

```json
{
  "vibration": {
    "sensor": {
      "port": "/dev/ttyUSB0",     ← Your RS485 device
      "baudrate": 9600,            ← Match sensor baudrate
      "protocol": "modbus"         ← or "ascii"
    }
  },
  "scheduler": {
    "work_hours": {
      "start": "08:30",            ← Start time
      "end": "19:00"               ← End time
    }
  }
}
```

---

## 🐳 Docker (Optional)

```bash
# Build
docker build -t monitoring-system .

# Run
docker run -p 5000:5000 \
  --device=/dev/ttyUSB0 \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/data:/app/data \
  monitoring-system
```

---

## 🔧 Troubleshooting

### Can't access RS485 sensor?
```bash
sudo chmod 666 /dev/ttyUSB0
```

### Port 5000 already in use?
Edit `config/system_config.json`:
```json
"web_server": {
  "port": 5001  ← Change to different port
}
```

### Services won't start?
- Check if camera exists: `ls /dev/video0`
- Check RS485 connection: `ls /dev/ttyUSB0`
- View error in dashboard service cards

---

## 📖 Full Documentation

- **Complete Guide**: `docs/MONITORING_SYSTEM_GUIDE.md`
- **Main README**: `README_MONITORING.md`
- **Summary**: `IMPLEMENTATION_SUMMARY.md`

---

## ✨ Features

- ✅ **Vibration Monitoring** - RS485 sensors
- ✅ **Work Scheduler** - Auto 8:30 AM - 7:00 PM
- ✅ **Web Dashboard** - Real-time monitoring
- ✅ **Alerts** - 4-level thresholds
- ✅ **Data Logging** - CSV & JSON
- ✅ **Docker Ready** - No X11 needed

---

**That's it! You're ready to monitor! 🎉**
