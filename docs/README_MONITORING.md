# Frying AI Monitoring System

## 🚀 Centralized Monitoring Dashboard

A comprehensive web-based monitoring system for the Frying AI Automation project, featuring:

- **📷 Camera Monitoring** - Real-time video with motion detection
- **📊 Vibration Monitoring** - RS485 sensor with real-time alerts
- **🍟 Frying AI** - Computer vision analysis for deep frying
- **⏰ Work Scheduler** - Automatic service start/stop (8:30 AM - 7:00 PM)

## ✨ Key Features

### Single Centralized Interface
- Monitor all services from one web dashboard
- Real-time status updates
- Easy service control (start/stop)
- Works perfectly in Docker containers

### Vibration Monitoring (New!)
- **USB to RS485** sensor support
- **Real-time 3-axis** acceleration monitoring (X, Y, Z)
- **Configurable alerts**: low, medium, high, critical thresholds
- **Statistical analysis**: mean, max, RMS, trend detection
- **Data logging**: CSV files with session summaries
- **Protocol support**: Modbus RTU and ASCII

### Automatic Scheduler (New!)
- Auto-start services at **8:30 AM**
- Auto-stop services at **7:00 PM**
- Configurable days of week
- Manual override support
- Countdown to next event

## 📦 Installation

### Prerequisites
```bash
# Python 3.6+
python3 --version

# Install dependencies
pip install flask pyserial numpy opencv-python
```

### Quick Setup
```bash
# 1. Configure hardware (edit if needed)
vim config/system_config.json

# 2. Run dashboard
python scripts/run_monitoring_dashboard.py

# 3. Access at http://localhost:5000
```

## 📁 New File Structure

```
my_ai_project/
├── src/
│   ├── core/              # Configuration & utilities
│   ├── monitoring/
│   │   ├── camera/        # Camera monitoring
│   │   ├── vibration/     # Vibration monitoring (NEW)
│   │   └── frying/        # Frying AI
│   ├── gui/               # Web dashboard (NEW)
│   │   ├── main_app.py
│   │   ├── templates/
│   │   └── static/
│   └── scheduler/         # Work scheduler (NEW)
│
├── config/                # Configuration files
├── data/                  # Data storage
├── scripts/               # Entry point scripts
└── docs/                  # Documentation
```

## 🎛️ Usage

### Launch Dashboard
```bash
./scripts/run_monitoring_dashboard.py
```

### Access Dashboard
- Local: http://localhost:5000
- Remote: http://<jetson-ip>:5000
- SSH tunnel: `ssh -L 5000:localhost:5000 user@jetson`

### Control Services

**From Web Dashboard**:
1. Open dashboard in browser
2. Click "Start" on desired service card
3. Monitor status in real-time
4. Click "Stop" to terminate

**Bulk Operations**:
- "Start All Services" - Start everything
- "Stop All Services" - Stop everything

### Scheduler

**Automatic Mode** (default):
- Services start at 8:30 AM
- Services stop at 7:00 PM
- Operates Monday-Sunday

**Manual Override**:
1. Click "Manual Override" button
2. Manually control services
3. Click again to re-enable auto mode

**Edit Schedule**:
1. Click "Edit Schedule"
2. Change start/end times
3. Select active days
4. Save changes

## ⚙️ Configuration

### Vibration Sensor Setup

Edit `config/system_config.json`:

```json
{
  "vibration": {
    "sensor": {
      "port": "/dev/ttyUSB0",      // Your RS485 adapter
      "baudrate": 9600,             // Match sensor settings
      "protocol": "modbus",         // or "ascii"
      "slave_address": 1            // Modbus address
    },
    "analyzer": {
      "alert_thresholds": {
        "low": 2.0,                 // m/s²
        "medium": 5.0,
        "high": 10.0,
        "critical": 20.0
      }
    }
  }
}
```

### Work Hours

```json
{
  "scheduler": {
    "work_hours": {
      "start": "08:30",
      "end": "19:00",
      "enabled_days": [0, 1, 2, 3, 4, 5, 6]
    }
  }
}
```

## 🐳 Docker Deployment

Perfect for containerized environments!

```yaml
services:
  monitoring:
    build: .
    ports:
      - "5000:5000"
    devices:
      - /dev/video0:/dev/video0
      - /dev/ttyUSB0:/dev/ttyUSB0
    volumes:
      - ./config:/app/config
      - ./data:/app/data
    environment:
      - TZ=Asia/Seoul
```

## 📊 Dashboard Panels

### Service Control Panel
- Individual service cards (Camera, Vibration, Frying AI)
- Status indicators (green = running, gray = stopped)
- Start/Stop buttons
- Bulk control buttons

### Scheduler Panel
- Current status (work time? auto mode?)
- Work hours display
- Next event countdown
- Override and edit controls

### Vibration Monitoring Panel
- Current magnitude
- Statistical metrics (mean, max, RMS)
- Trend analysis
- 3-axis visualization with color coding
- Sample count

### Alerts Panel
- Real-time alert notifications
- Color-coded by severity
- Timestamp and description
- Last 10 alerts displayed

## 🔧 Troubleshooting

### Sensor Connection Issues

```bash
# Check device
ls -l /dev/ttyUSB*

# Fix permissions
sudo chmod 666 /dev/ttyUSB0

# Or add to group
sudo usermod -a -G dialout $USER
```

### Dashboard Won't Start

```bash
# Check dependencies
pip install flask pyserial numpy

# Verify config
cat config/system_config.json | python -m json.tool
```

### Time Zone Issues

```bash
# Check system time
timedatectl

# Set timezone
sudo timedatectl set-timezone Asia/Seoul
```

## 📈 Data Logging

### Vibration Logs
- Location: `data/vibration_logs/`
- Format: CSV with timestamp, axes, magnitude
- Summary: JSON with statistics and alerts

### Camera Data
- Recordings: `data/recordings/`
- Screenshots: `data/screenshots/`

### Frying AI Data
- Sessions: `data/frying_dataset/`
- Images, sensor logs, metadata

## 🎯 Alert Thresholds

| Level | Default | Color | Action |
|-------|---------|-------|--------|
| Low | 2.0 m/s² | Green | Normal |
| Medium | 5.0 m/s² | Yellow | Monitor |
| High | 10.0 m/s² | Red | Investigate |
| Critical | 20.0 m/s² | Purple | Stop operation |

## 📚 Documentation

- **[Complete Guide](docs/MONITORING_SYSTEM_GUIDE.md)** - Detailed documentation
- **[API Reference](docs/MONITORING_SYSTEM_GUIDE.md#api-reference)** - REST API docs
- **[Hardware Setup](docs/MONITORING_SYSTEM_GUIDE.md#hardware-setup)** - RS485 wiring

## 🔄 Migration from Old Structure

Old files are still in place:
- `camera_monitor/` - Original camera code
- `frying_ai/` - Original frying AI code
- `run_monitor.py` - Old entry point

New centralized system is in:
- `src/` - All organized code
- `scripts/run_monitoring_dashboard.py` - New entry point

Both can coexist during transition.

## 🚦 System Requirements

- Python 3.6+
- Linux (Jetson Orin Nano or Ubuntu)
- USB to RS485 adapter (for vibration monitoring)
- Camera (optional, for camera monitoring)
- 2GB RAM minimum

## 📝 Version

**1.0.0** - Initial Release
- Centralized web dashboard
- Vibration monitoring with RS485
- Automatic work scheduler
- Service lifecycle management

## 🤝 Contributing

This is an internal project for Frying AI automation.

## 📄 License

Proprietary - Frying AI Project

---

**Made with ❤️ for NVIDIA Jetson Orin Nano**
