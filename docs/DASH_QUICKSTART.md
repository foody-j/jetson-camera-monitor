# Dash Dashboard Quick Start 🚀

## 🎨 Beautiful Monitoring Dashboard

Professional, interactive dashboard with **real-time charts** powered by Plotly Dash.

---

## ⚡ Quick Start (3 Steps)

### 1. Install Dependencies
```bash
pip install dash dash-bootstrap-components plotly pyserial numpy
```

### 2. Run Dashboard
```bash
python scripts/run_dash_dashboard.py
```

### 3. Access Dashboard
Open browser: **http://localhost:8050**

---

## ✨ Features

### 🎨 Beautiful Dark Theme (Cyborg)
- Professional appearance
- Easy on eyes
- Modern design

### 📊 Interactive Charts
- **Real-time vibration graphs**
- Zoom, pan, hover
- Color-coded X/Y/Z axes
- Magnitude overlay

### 🎛️ Service Control
- Start/Stop individual services
- Bulk operations
- Status indicators
- Color-coded badges

### ⏰ Work Scheduler
- 8:30 AM - 7:00 PM automatic
- Manual override
- Next event countdown
- Edit schedule UI

### ⚠️ Smart Alerts
- Color-coded by severity
- Real-time notifications
- Timestamped
- Auto-scrolling list

---

## 🎯 Why Dash?

| Feature | Value |
|---------|-------|
| Charts | ✅ Interactive Plotly graphs |
| Design | ✅ Professional Bootstrap theme |
| Code | ✅ Pure Python (no HTML/CSS/JS) |
| Responsive | ✅ Works on mobile |
| Data-focused | ✅ Built for ML/data dashboards |

**Dash = Better looking + More features + Easier to maintain**

---

## 🔧 Configuration

Edit `config/system_config.json`:

```json
{
  "vibration": {
    "sensor": {
      "port": "/dev/ttyUSB0",
      "baudrate": 9600,
      "protocol": "modbus"
    }
  },
  "scheduler": {
    "work_hours": {
      "start": "08:30",
      "end": "19:00"
    }
  }
}
```

---

## 🐳 Docker

```bash
# Build
docker build -t monitoring-dash .

# Run
docker run -p 8050:8050 \
  --device=/dev/ttyUSB0 \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/data:/app/data \
  monitoring-dash
```

---

## 📊 Dashboard Layout

```
┌─────────────────────────────────────────────────┐
│  🤖 Frying AI Monitoring System     [✅Online]  │
├─────────────────────────────────────────────────┤
│ ┌──────────────┐   ┌──────────────────────────┐│
│ │⏰ Scheduler   │   │ 📊 Vibration Monitoring  ││
│ │              │   │                          ││
│ │Status: Active│   │ ┌──┐ ┌──┐ ┌──┐ ┌──┐     ││
│ │08:30 - 19:00 │   │ │⬆️│ │➡️│ │⬆️│ │➡️│     ││
│ │✅ Work Time  │   │ │2.4│ │2.1│ │5.6│ │2.3│ ││
│ │              │   │ └──┘ └──┘ └──┘ └──┘     ││
│ │[Override]    │   │                          ││
│ │[Edit]        │   │    Live Chart:           ││
│ └──────────────┘   │       ╱╲                 ││
│                    │    ╱╲╱  ╲                ││
│ ┌──────────────┐   │  ╱╲      ╲               ││
│ │🎛️ Services   │   │ ╱         ╲              ││
│ │              │   │   [Interactive]          ││
│ │📷[Start][Stop]  │   │   Zoom • Hover • Pan  ││
│ │📊[Start][Stop]  │   └──────────────────────────┘│
│ │🍟[Start][Stop]  │                              │
│ │              │   ┌──────────────────────────┐  │
│ │[Start All]   │   │ ⚠️ Recent Alerts         │  │
│ │[Stop All]    │   │ [🟢Low]  [🟡Med]  [🔴High]│  │
│ └──────────────┘   │ Timestamped & Colored    │  │
│                    └──────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

---

## 🎨 Color Coding

| Status | Color | Meaning |
|--------|-------|---------|
| Online | 🟢 Green | System operational |
| Running | 🟢 Green | Service active |
| Stopped | ⚪ Gray | Service inactive |
| Error | 🔴 Red | Service error |
| Low Alert | 🟢 Green | Minor vibration |
| Medium Alert | 🟡 Yellow | Monitor closely |
| High Alert | 🔴 Red | Action required |
| Critical Alert | 🟣 Purple | Stop operation |

---

## 📈 Vibration Chart Features

### Interactive
- **Hover**: See exact values
- **Zoom**: Click and drag
- **Pan**: Shift + drag
- **Reset**: Double-click

### Lines
- 🔴 **Red**: X-axis
- 🔵 **Cyan**: Y-axis
- 🔵 **Blue**: Z-axis
- 🟠 **Orange**: Magnitude (bold)

### Updates
- **Frequency**: 1 second
- **Buffer**: Last 300 points (5 minutes at 1Hz)
- **Auto-scroll**: Always shows latest

---

## 🔧 Troubleshooting

### Port Already in Use?
```bash
# Change port in dash_app.py or use:
PORT=8051 python scripts/run_dash_dashboard.py
```

### Charts Not Updating?
- Check vibration service is started
- Verify sensor connection
- Check console for errors

### Dash Won't Install?
```bash
# Try specific versions
pip install dash==2.14.0 dash-bootstrap-components==1.5.0 plotly==5.17.0
```

---

## 📚 Documentation

- **Full Guide**: `docs/MONITORING_SYSTEM_GUIDE.md`
- **Comparison**: `docs/DASHBOARD_COMPARISON.md`
- **Data Guide**: `docs/FRYING_AI_DATA_GUIDELINE.md`
- **Probe Guide**: `docs/PROBE_THERMOMETER_GUIDE.md`

---

## 🎯 Key Differences vs Flask

| Feature | Flask | Dash |
|---------|-------|------|
| Charts | ❌ None | ✅ **Interactive** |
| Theme | ⚪ Light | ✅ **Dark** |
| Code | 4 files | ✅ **1 file** |
| Maintenance | 3 languages | ✅ **Python only** |
| Professional | ⚠️ Basic | ✅ **Production-ready** |

**Dash = Better in every way** ⭐

---

## 🚀 Next Steps

1. ✅ Launch dashboard
2. ✅ Start services
3. ✅ Monitor vibration charts
4. ✅ Configure schedule
5. ✅ Enjoy beautiful UI!

---

**Access**: http://localhost:8050
**Port**: 8050 (Dash) vs 5000 (Flask)
**Theme**: Cyborg (Dark)
**Charts**: Real-time Plotly
**Status**: Production-Ready ✅
