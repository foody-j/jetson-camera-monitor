# Data Collection Quick Reference

## 🚀 Quick Start

### Launch Data Collector
```bash
cd frying_ai
python web_viewer.py
# Access: http://localhost:5000
```

### Collect One Session

1. **Prepare**: Heat oil, position camera, connect sensors
2. **Start**: Enter food type → Click "Start Session"
3. **Monitor**: Watch frying process (2-5 minutes)
4. **Mark**: Insert probe → Read temp → Click "Mark Completion"
5. **Stop**: Click "Stop Session"
6. **Verify**: Check data in `frying_dataset/`

---

## 🎯 Ground Truth Guide

| Food | Internal Temp | Visual Cue |
|------|---------------|------------|
| Chicken | 74°C (165°F) | Golden brown |
| Shrimp | 63°C (145°F) | Pink/opaque |
| Potato | N/A | Golden yellow |
| Fish | 63°C (145°F) | Opaque, flaky |

**CRITICAL**: Always use food probe thermometer for accurate ground truth!

---

## 📊 Data Structure

```
frying_dataset/
└── foodtype_YYYYMMDD_HHMMSS/
    ├── images/                  # Sequential frames
    │   ├── t0000.jpg
    │   └── ...
    ├── session_data.json        # Metadata + completion time
    └── sensor_log.csv           # Temperature time-series
```

---

## ✅ Session Checklist

### Before
- [ ] Camera focused and mounted
- [ ] Sensors connected
- [ ] Web viewer running
- [ ] Probe thermometer ready

### During
- [ ] Start session with food type
- [ ] Monitor video feed
- [ ] Watch for doneness cues

### Completion
- [ ] Insert probe thermometer
- [ ] Wait for stable reading
- [ ] Click "Mark Completion"
- [ ] Enter probe temp + notes

### After
- [ ] Stop session
- [ ] Verify: `ls frying_dataset/SESSION_ID/images/ | wc -l`
- [ ] Check: `cat frying_dataset/SESSION_ID/session_data.json`

---

## 🤖 ML Pipeline

### 1. Extract Features
```bash
cd frying_ai
python food_segmentation.py --batch
```

### 2. Train Model
```python
from sklearn.ensemble import RandomForestRegressor
import pandas as pd

# Load data
df = load_all_sessions()  # Your function

# Features and target
X = df[['brown_ratio', 'golden_ratio', 'mean_hue', 'oil_temp', 'elapsed_time']]
y = df['time_to_completion']

# Train
model = RandomForestRegressor(n_estimators=100)
model.fit(X, y)

# Evaluate
print(f"MAE: {mean_absolute_error(y_test, y_pred):.2f}s")
```

### 3. Deploy
```python
import joblib

# Save
joblib.dump(model, 'models/predictor.pkl')

# Load and predict
model = joblib.load('models/predictor.pkl')
time_left = model.predict(current_features)
```

---

## 🎯 Target Metrics

| Metric | Target | Description |
|--------|--------|-------------|
| Sessions | 200+ | Total collected |
| Per Food | 40+ | Each type |
| MAE | <10s | Prediction error |
| R² | >0.85 | Model fit |

---

## 🔧 Validation

```bash
# Check session
ls -lh frying_dataset/SESSION_ID/

# Count images
ls frying_dataset/SESSION_ID/images/ | wc -l

# Verify CSV
head frying_dataset/SESSION_ID/sensor_log.csv

# Check metadata
cat frying_dataset/SESSION_ID/session_data.json | python -m json.tool
```

---

## ⚠️ Common Mistakes

1. **Forgetting to mark completion** → No ground truth!
2. **Inaccurate probe reading** → Bad labels
3. **Moving camera during session** → Inconsistent images
4. **Not testing sensors first** → Missing data
5. **Stopping too early** → Incomplete session

---

## 🔄 Workflow

```
Setup → Start Session → Monitor → Mark Completion → Stop → Verify → Repeat
   ↓                                                              ↑
   └──────────────────────────────────────────────────────────────┘
                    (Collect 200+ sessions)
                             ↓
                    Extract Features
                             ↓
                       Train Model
                             ↓
                    Evaluate & Deploy
```

---

## 📞 Need Help?

- **Full Guide**: `docs/FRYING_AI_DATA_GUIDELINE.md`
- **System Guide**: `docs/MONITORING_SYSTEM_GUIDE.md`
- **Quick Start**: `QUICKSTART.md`
