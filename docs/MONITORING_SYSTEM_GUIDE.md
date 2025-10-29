# Monitoring System Guide

## Overview

This is a comprehensive monitoring system for the Frying AI Automation project. It provides a centralized web-based dashboard to monitor and control multiple services:

- **Camera Monitoring**: Real-time video surveillance with motion detection
- **Vibration Monitoring**: RS485-based vibration sensor monitoring with alerts
- **Frying AI**: Deep frying automation with computer vision analysis
- **Work Scheduler**: Automatic start/stop based on configurable work hours

## Features

### 🎛️ Centralized Dashboard
- Single web interface to control all monitoring services
- Real-time status updates (1-second polling)
- Service start/stop controls
- System health monitoring

### ⏰ Work Scheduler
- Automatic service startup at **8:30 AM**
- Automatic shutdown at **7:00 PM**
- Configurable days of week
- Manual override support
- Grace period for safe shutdown

### 📊 Vibration Monitoring
- RS485/Modbus sensor support (USB to RS485 adapter)
- Real-time 3-axis acceleration monitoring
- Configurable alert thresholds (low, medium, high, critical)
- Statistical analysis (mean, max, RMS, trend)
- Data logging to CSV files
- Alert notifications

### 📷 Camera Monitoring
- Motion detection
- Automatic recording
- Screenshot capture
- Configurable resolution and FPS

### 🍟 Frying AI
- Real-time color analysis
- Temperature sensor integration
- Session-based data collection
- Food segmentation

## File Structure

```
my_ai_project/
├── src/                          # All source code
│   ├── core/                     # Core modules
│   │   ├── config.py             # Configuration management
│   │   └── utils.py              # Utility functions
│   │
│   ├── monitoring/               # Monitoring modules
│   │   ├── camera/               # Camera monitoring
│   │   │   ├── camera_base.py
│   │   │   ├── motion_detector.py
│   │   │   ├── recorder.py
│   │   │   └── monitor.py
│   │   │
│   │   ├── vibration/            # Vibration monitoring
│   │   │   ├── __init__.py
│   │   │   ├── rs485_sensor.py   # RS485 sensor interface
│   │   │   ├── vibration_analyzer.py  # Data analysis
│   │   │   └── vibration_detector.py  # Main detector
│   │   │
│   │   └── frying/               # Frying AI
│   │       ├── frying_data_collector.py
│   │       ├── food_segmentation.py
│   │       └── sensor_simulator.py
│   │
│   ├── gui/                      # Web dashboard
│   │   ├── main_app.py           # Flask application
│   │   ├── templates/
│   │   │   └── dashboard.html    # Main dashboard UI
│   │   └── static/
│   │       ├── css/
│   │       │   └── dashboard.css
│   │       └── js/
│   │           └── dashboard.js
│   │
│   └── scheduler/                # Work scheduler
│       ├── work_scheduler.py     # Schedule management
│       └── service_manager.py    # Service lifecycle
│
├── config/                       # Configuration files
│   └── system_config.json        # Main system configuration
│
├── data/                         # Data storage
│   ├── vibration_logs/           # Vibration data logs
│   ├── recordings/               # Camera recordings
│   ├── screenshots/              # Camera screenshots
│   └── frying_dataset/           # Frying AI data
│
├── scripts/                      # Entry point scripts
│   └── run_monitoring_dashboard.py  # Launch dashboard
│
└── docs/                         # Documentation
    └── MONITORING_SYSTEM_GUIDE.md
```

## Quick Start

### 1. Install Dependencies

```bash
pip install flask pyserial numpy
```

### 2. Configure Hardware

Edit `config/system_config.json` to match your hardware:

```json
{
  "vibration": {
    "sensor": {
      "port": "/dev/ttyUSB0",    # Your RS485 adapter
      "baudrate": 9600,           # Match sensor baudrate
      "protocol": "modbus",       # or "ascii"
      "slave_address": 1          # Modbus slave address
    }
  }
}
```

### 3. Launch Dashboard

```bash
# Option 1: Using Python
python scripts/run_monitoring_dashboard.py

# Option 2: Direct execution
./scripts/run_monitoring_dashboard.py
```

### 4. Access Dashboard

Open your browser and navigate to:
- **Local**: http://localhost:5000
- **Remote**: http://<jetson-ip>:5000

For Docker/SSH access, set up port forwarding:
```bash
ssh -L 5000:localhost:5000 user@jetson-ip
```

## Configuration

### System Configuration (`config/system_config.json`)

#### Vibration Monitoring
```json
{
  "vibration": {
    "enabled": true,
    "sensor": {
      "port": "/dev/ttyUSB0",
      "baudrate": 9600,
      "protocol": "modbus",        // "modbus" or "ascii"
      "slave_address": 1,
      "timeout": 1.0
    },
    "analyzer": {
      "window_size": 100,          // Number of samples to analyze
      "alert_thresholds": {
        "low": 2.0,                // m/s²
        "medium": 5.0,
        "high": 10.0,
        "critical": 20.0
      }
    },
    "sampling_rate": 10.0          // Hz (samples per second)
  }
}
```

#### Work Scheduler
```json
{
  "scheduler": {
    "enabled": true,
    "work_hours": {
      "start": "08:30",            // HH:MM format
      "end": "19:00",
      "enabled_days": [0, 1, 2, 3, 4, 5, 6]  // 0=Mon, 6=Sun
    },
    "auto_start_enabled": true,
    "auto_stop_enabled": true
  }
}
```

#### Web Server
```json
{
  "web_server": {
    "host": "0.0.0.0",             // Listen on all interfaces
    "port": 5000,
    "debug": false
  }
}
```

## Dashboard Usage

### Service Control

**Start Individual Service**:
1. Click the "Start" button on the service card
2. Service status indicator will turn green when running

**Stop Individual Service**:
1. Click the "Stop" button on the service card
2. Service status indicator will turn gray when stopped

**Bulk Control**:
- "Start All Services": Starts all configured services
- "Stop All Services": Stops all running services

### Work Scheduler

**Automatic Mode**:
- Services automatically start at configured start time
- Services automatically stop at configured end time
- Only operates on enabled days

**Manual Override**:
1. Click "Manual Override" button
2. Automatic scheduling is disabled
3. Manually control services as needed
4. Click button again to re-enable automatic scheduling

**Edit Schedule**:
1. Click "Edit Schedule" button
2. Modify start time, end time, and enabled days
3. Click "Save Changes"
4. New schedule takes effect immediately

### Vibration Monitoring

**Metrics Displayed**:
- **Current Magnitude**: Real-time vibration level (m/s²)
- **Mean Magnitude**: Average over window
- **Max Magnitude**: Peak value in window
- **RMS Value**: Root mean square (energy level)
- **Trend**: increasing, decreasing, or stable
- **Sample Count**: Total samples collected

**Axis Visualization**:
- X, Y, Z axis values displayed with color-coded bars
- Green: Normal (<2 m/s²)
- Yellow: Elevated (2-5 m/s²)
- Red: High (5-10 m/s²)
- Purple: Critical (>10 m/s²)

**Alerts**:
- Displayed in real-time in the "Recent Alerts" panel
- Color-coded by severity
- Includes timestamp and description

### Alert Thresholds

| Level | Default (m/s²) | Description |
|-------|----------------|-------------|
| Low | 2.0 | Minor vibration detected |
| Medium | 5.0 | Moderate vibration - monitor |
| High | 10.0 | High vibration - investigate |
| Critical | 20.0 | Dangerous vibration - stop operation |

## Hardware Setup

### RS485 Vibration Sensor

**Connection**:
1. Connect USB to RS485 adapter to Jetson
2. Connect sensor to RS485 terminals (A, B, GND)
3. Power sensor as per specifications
4. Verify device appears as `/dev/ttyUSB0` (or similar)

**Check Device**:
```bash
ls -l /dev/ttyUSB*
dmesg | grep tty
```

**Modbus Configuration**:
- Default slave address: 1
- Baudrate: 9600 (check sensor manual)
- Parity: None
- Stop bits: 1

**Supported Protocols**:
- **Modbus RTU**: Industrial standard (recommended)
- **ASCII**: Simple text-based protocol

### Testing Sensor

Test sensor connection:
```python
from src.monitoring.vibration import RS485VibrationSensor

config = {
    'port': '/dev/ttyUSB0',
    'baudrate': 9600,
    'protocol': 'modbus',
    'slave_address': 1
}

with RS485VibrationSensor(config) as sensor:
    if sensor.is_connected():
        reading = sensor.read()
        if reading:
            print(f"X: {reading.x_axis:.2f} m/s²")
            print(f"Y: {reading.y_axis:.2f} m/s²")
            print(f"Z: {reading.z_axis:.2f} m/s²")
            print(f"Magnitude: {reading.magnitude:.2f} m/s²")
```

## Data Logging

### Vibration Data

**CSV Format** (`data/vibration_logs/session_name.csv`):
```
timestamp,elapsed_time,x_axis,y_axis,z_axis,magnitude,temperature,frequency
1635000000.123,0.100,1.23,0.45,0.67,1.48,25.3,10.5
1635000000.223,0.200,1.25,0.47,0.69,1.52,25.4,10.6
...
```

**JSON Summary** (`data/vibration_logs/session_name_summary.json`):
- Session metadata
- Statistical summary
- Alert history
- Sensor configuration

### Camera Data

**Recordings**: `data/recordings/recording_YYYYMMDD_HHMMSS.avi`

**Screenshots**: `data/screenshots/screenshot_YYYYMMDD_HHMMSS.jpg`

### Frying AI Data

**Dataset**: `data/frying_dataset/foodtype_YYYYMMDD_HHMMSS/`
- `images/`: Timestamped frames
- `session_data.json`: Session metadata
- `sensor_log.csv`: Time-series data

## Troubleshooting

### Dashboard Won't Start

**Check Python path**:
```bash
python3 --version  # Should be Python 3.6+
```

**Install missing dependencies**:
```bash
pip install flask pyserial numpy
```

**Check config file**:
```bash
cat config/system_config.json | python -m json.tool
```

### Vibration Sensor Not Connecting

**Check device exists**:
```bash
ls -l /dev/ttyUSB*
```

**Check permissions**:
```bash
sudo chmod 666 /dev/ttyUSB0
# Or add user to dialout group:
sudo usermod -a -G dialout $USER
# Log out and back in
```

**Test with minicom**:
```bash
sudo apt install minicom
minicom -D /dev/ttyUSB0 -b 9600
```

### Services Won't Start

**Check logs**:
- Console output shows errors
- Service status shows "Error" with message

**Common issues**:
- Camera not available (check `/dev/video0`)
- RS485 device busy (close other programs)
- Insufficient permissions

### Scheduler Not Working

**Verify time settings**:
```bash
date
timedatectl
```

**Check enabled days**:
- 0 = Monday, 6 = Sunday
- Verify current day is in enabled_days

**Manual override active**:
- Click "Disable Override" button

## Docker Deployment

The dashboard works perfectly in Docker containers.

**docker-compose.yml**:
```yaml
services:
  monitoring:
    build: .
    ports:
      - "5000:5000"
    devices:
      - /dev/video0:/dev/video0      # Camera
      - /dev/ttyUSB0:/dev/ttyUSB0    # RS485
    volumes:
      - ./config:/app/config
      - ./data:/app/data
    environment:
      - TZ=Asia/Seoul
    command: python scripts/run_monitoring_dashboard.py
```

**Run**:
```bash
docker-compose up -d
docker-compose logs -f
```

## API Reference

### GET /api/status
Get complete system status (called every 1 second by frontend)

**Response**:
```json
{
  "initialized": true,
  "timestamp": 1635000000.123,
  "services": [...],
  "scheduler": {...},
  "vibration": {...},
  "alerts": [...]
}
```

### POST /api/service/<service_id>/start
Start a service (camera, vibration, frying)

### POST /api/service/<service_id>/stop
Stop a service

### POST /api/services/start_all
Start all services

### POST /api/services/stop_all
Stop all services

### POST /api/scheduler/override
Enable/disable manual override

**Body**:
```json
{"enable": true}
```

### POST /api/scheduler/update
Update work schedule

**Body**:
```json
{
  "start_time": "08:30",
  "end_time": "19:00",
  "enabled_days": [0, 1, 2, 3, 4, 5, 6]
}
```

### GET /api/vibration/latest
Get latest vibration reading

## Best Practices

1. **Always test sensor connection** before starting monitoring
2. **Configure alert thresholds** based on your equipment baseline
3. **Use manual override** when you need to control services manually
4. **Monitor alerts panel** for abnormal vibrations
5. **Check data logs regularly** for historical analysis
6. **Set appropriate work hours** to save resources
7. **Use Docker** for reliable deployment

## Support

For issues or questions:
- Check troubleshooting section
- Review logs in console output
- Verify hardware connections
- Check configuration file syntax

## Version
1.0.0 - Initial Release
