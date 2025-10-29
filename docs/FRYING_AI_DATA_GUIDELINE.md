# Frying AI Data Collection & Application Guideline

## 📋 Overview

This guide provides comprehensive instructions for collecting, labeling, and applying data for the Frying AI system. The goal is to build a machine learning model that can predict when food is perfectly cooked based on visual (color) and sensor (temperature) data.

---

## 🎯 Project Goal

**Predict Frying Completion Time**

Input:
- Real-time images of food frying
- Temperature sensor data (oil temp, fryer temp)
- Elapsed time

Output:
- Predicted doneness level (0-100%)
- Estimated time remaining
- Alert when food is ready

---

## 📊 Data Collection Overview

### What Data Is Collected

**1. Visual Data (Images)**
- **Format**: JPEG images
- **Frequency**: 1-2 FPS (frames per second)
- **Resolution**: 640x360 or higher
- **Content**: Top-down view of food in fryer
- **Naming**: `t0000.jpg`, `t0001.jpg`, ... (sequential)

**2. Sensor Data (Temperature)**
- **Oil Temperature**: Temperature of frying oil (°C)
- **Fryer Temperature**: Heater/ambient temperature (°C)
- **Internal Temperature**: Food probe temperature (°C) - used for ground truth
- **Frequency**: Same as image capture (synchronized)
- **Format**: CSV time-series

**3. Session Metadata**
- Food type (chicken, shrimp, potato, etc.)
- Start time and end time
- Completion point (ground truth timestamp)
- Probe temperature at completion
- Session notes
- Weather conditions (optional)

### Data Structure

```
data/frying_dataset/
├── chicken_20251028_143012/          # Session ID
│   ├── images/                        # Image sequence
│   │   ├── t0000.jpg
│   │   ├── t0001.jpg
│   │   └── ...
│   ├── session_data.json              # Metadata
│   └── sensor_log.csv                 # Time-series sensor data
│
├── shrimp_20251028_150045/
│   ├── images/
│   ├── session_data.json
│   └── sensor_log.csv
│
└── analysis_results/                  # Feature extraction results
    ├── chicken_20251028_143012_features.json
    └── ...
```

---

## 🛠️ Equipment Setup

### Required Equipment

1. **Camera**
   - USB webcam or CSI camera
   - Mounted above fryer
   - Clear top-down view
   - Good lighting
   - Heat-resistant mounting

2. **Temperature Sensors**
   - **Oil thermometer**: K-type thermocouple or PT100
   - **Food probe**: Digital meat thermometer (essential for ground truth)
   - **Fryer sensor**: Ambient/heater temperature
   - RS485 or serial connection to Jetson

3. **Jetson Orin Nano**
   - Running Ubuntu
   - Camera connected
   - Sensors connected via USB/GPIO
   - Adequate storage (100GB+ recommended)

4. **Frying Equipment**
   - Deep fryer or wok
   - Consistent heat source
   - Safety equipment (fire extinguisher, apron, gloves)

### Camera Positioning

```
        [Camera]
            |
         [Mount]
            |
    ==================
    |                |
    |     [Food]     |  ← Fryer
    |    [  Oil ]    |
    |                |
    ==================
```

**Best Practices**:
- Mount 30-50 cm above oil surface
- Directly above center of fryer
- Avoid steam/smoke obstruction
- Use protective casing if needed
- Ensure stable mounting (vibration-free)

---

## 📝 Data Collection Procedure

### Preparation

**1. System Setup**
```bash
# Navigate to project
cd /home/dkutest/my_ai_project

# Activate environment (if using virtual env)
source venv/bin/activate

# Test camera
python tests/test_camera.py

# Test sensors
python tests/test_sensors.py
```

**2. Environment Preparation**
- Clean fryer and oil
- Set up camera position
- Connect all sensors
- Verify temperature readings
- Prepare food items
- Document ambient conditions

**3. Launch Data Collector**
```bash
# Option 1: Web interface
cd frying_ai
python web_viewer.py

# Option 2: Direct CLI
python frying_data_collector.py
```

### Data Collection Workflow

**Step 1: Start Session**

Via Web Interface (http://localhost:5000):
1. Enter **Food Type** (e.g., "chicken_wings")
2. Add **Session Notes** (e.g., "Fresh oil, 180°C, 500g batch")
3. Click **"Start Session"**
4. System creates new session folder
5. Image and sensor logging begins

Via CLI:
```python
from frying_data_collector import FryingDataCollector

collector = FryingDataCollector()
collector.initialize()
collector.start_session(food_type="chicken_wings", notes="Fresh oil, 180°C")
```

**Step 2: Monitor Frying Process**

- System automatically captures:
  - Images every 0.5-1.0 seconds (1-2 FPS)
  - Temperature readings synchronized with images
  - Elapsed time since session start

- Observer monitors:
  - Food color changes (light → golden → brown)
  - Oil bubbling intensity
  - Food floating behavior
  - Steam production

- Web viewer shows:
  - Live video feed
  - Current elapsed time
  - Real-time temperature readings
  - Food segmentation overlay (green mask)

**Step 3: Mark Completion (Ground Truth)**

**CRITICAL**: This is the most important step!

When food is **perfectly cooked** (determined by food probe thermometer):

Via Web Interface:
1. Insert food probe thermometer
2. Wait for temperature to stabilize
3. Read **Probe Temperature** (e.g., 165°F / 74°C for chicken)
4. Click **"Mark Completion"**
5. Enter probe temperature
6. Add notes (e.g., "Golden brown, crispy exterior")
7. Confirm

Via CLI:
```python
# Mark the exact moment food is done
collector.mark_completion(
    probe_temp=74.0,  # °C
    notes="Golden brown, internal temp 74°C"
)
```

**Ground Truth Guidelines by Food Type**:

| Food Type | Internal Temp (°C) | Internal Temp (°F) | Visual Cues |
|-----------|--------------------|--------------------|-------------|
| Chicken | 74°C | 165°F | Golden brown, juices clear |
| Shrimp | 63°C | 145°F | Pink/white, opaque, curled |
| Potato (fries) | N/A | N/A | Golden yellow, crispy edges |
| Fish | 63°C | 145°F | Opaque, flakes easily |
| Pork | 63°C | 145°F | Light pink center, firm |

**Step 4: Continue Recording (Optional)**

After marking completion, you can:
- Continue recording for a few more seconds (to capture overcooking)
- Or immediately stop the session

**Recommendation**: Record 10-30 seconds **after** completion to capture the transition to "overcooked" state. This helps the model learn boundaries.

**Step 5: Stop Session**

Via Web Interface:
1. Click **"Stop Session"**
2. System finalizes data:
   - Closes CSV file
   - Saves session_data.json
   - Generates summary

Via CLI:
```python
collector.stop_session()
```

**Step 6: Verify Data**

```bash
# Check session folder
ls -lh frying_dataset/chicken_20251028_143012/

# Verify image count
ls frying_dataset/chicken_20251028_143012/images/ | wc -l

# Check CSV
head -n 5 frying_dataset/chicken_20251028_143012/sensor_log.csv

# Review metadata
cat frying_dataset/chicken_20251028_143012/session_data.json | python -m json.tool
```

---

## 🎓 Best Practices

### Session Planning

**Vary Conditions** (for robust model):
- Different food types (chicken, shrimp, potato, fish)
- Different batch sizes (small, medium, large)
- Different oil temperatures (160°C, 170°C, 180°C, 190°C)
- Different oil conditions (fresh, used 1x, used 3x, used 5x)
- Different ambient temperatures (morning vs. afternoon)
- Different food states (frozen vs. thawed)

**Target Dataset Size**:
- **Minimum**: 50 sessions (10 per food type)
- **Recommended**: 200+ sessions (40+ per food type)
- **Ideal**: 500+ sessions (comprehensive coverage)

### Ground Truth Accuracy

**Critical Success Factor**: Accurate ground truth labeling!

**Use Food Probe Thermometer**:
- Insert into thickest part of food
- Wait 5-10 seconds for stabilization
- Read temperature accurately
- Record immediately in system

**Visual Inspection**:
- Cut food sample to verify doneness
- Check color consistency
- Verify texture (crispy vs. soggy)
- Taste test (if safe)

**Consistency**:
- Use same criteria across all sessions
- Train all operators on ground truth procedure
- Document exceptions or uncertainties

### Safety

- **Never leave fryer unattended**
- Keep fire extinguisher nearby
- Wear protective equipment (apron, gloves)
- Ensure proper ventilation
- Keep camera equipment away from hot oil
- Use heat-resistant mounting
- Have emergency stop procedure

---

## 📈 Feature Extraction

After collecting raw data, extract features for ML training.

### Run Food Segmentation

```bash
cd frying_ai

# Analyze single session
python food_segmentation.py --session frying_dataset/chicken_20251028_143012

# Batch analyze all sessions
python food_segmentation.py --batch

# Output: frying_dataset/analysis_results/
```

### Extracted Features

For each frame, the system extracts:

**Color Features (HSV)**:
- `brown_ratio`: Percentage of brown pixels (0.0 - 1.0)
- `golden_ratio`: Percentage of golden pixels (0.0 - 1.0)
- `mean_hue`: Average hue value (0 - 180)
- `mean_saturation`: Average saturation (0 - 255)
- `mean_value`: Average brightness (0 - 255)

**Color Features (LAB)**:
- `mean_l`: Lightness (0 - 100)
- `mean_a`: Green-Red axis (-128 to 127)
- `mean_b`: Blue-Yellow axis (-128 to 127)

**Spatial Features**:
- `food_area_ratio`: Food pixels / total pixels (0.0 - 1.0)

**Temporal Features** (derived):
- `elapsed_time`: Seconds since session start
- `time_to_completion`: Seconds until marked completion (TARGET)

### Feature Engineering

Additional features to compute:

**Rate of Change**:
```python
brown_ratio_delta = (brown_ratio[t] - brown_ratio[t-10]) / 10.0
golden_ratio_delta = (golden_ratio[t] - golden_ratio[t-10]) / 10.0
```

**Moving Averages**:
```python
brown_ratio_ma5 = np.mean(brown_ratio[t-5:t])
brown_ratio_ma10 = np.mean(brown_ratio[t-10:t])
```

**Sensor Features**:
```python
oil_temp_stable = np.std(oil_temp[t-10:t]) < 5.0  # Boolean
temp_drop = oil_temp[0] - oil_temp[t]  # Temperature drop
```

### Output Format

**Per-frame features** (`session_id_features.json`):
```json
{
  "session_id": "chicken_20251028_143012",
  "food_type": "chicken",
  "completion_time": 180.5,
  "frames": [
    {
      "timestamp": 0.0,
      "frame_id": "t0000",
      "brown_ratio": 0.02,
      "golden_ratio": 0.15,
      "mean_hue": 25.3,
      "mean_saturation": 120.5,
      "mean_value": 180.2,
      "food_area_ratio": 0.35,
      "oil_temp": 175.2,
      "elapsed_time": 0.0,
      "time_to_completion": 180.5
    },
    ...
  ]
}
```

---

## 🤖 Machine Learning Pipeline

### Data Preparation

**1. Load and Merge Data**

```python
import pandas as pd
import json
import glob

def load_all_sessions():
    """Load all session feature data into single DataFrame"""
    all_data = []

    for feature_file in glob.glob("frying_dataset/analysis_results/*_features.json"):
        with open(feature_file, 'r') as f:
            session = json.load(f)

        for frame in session['frames']:
            frame['food_type'] = session['food_type']
            frame['session_id'] = session['session_id']
            all_data.append(frame)

    df = pd.DataFrame(all_data)
    return df

df = load_all_sessions()
print(f"Total frames: {len(df)}")
print(f"Total sessions: {df['session_id'].nunique()}")
```

**2. Feature Selection**

```python
# Define feature columns
feature_cols = [
    'brown_ratio',
    'golden_ratio',
    'mean_hue',
    'mean_saturation',
    'mean_value',
    'mean_l',
    'mean_a',
    'mean_b',
    'food_area_ratio',
    'oil_temp',
    'elapsed_time'
]

# Target variable
target_col = 'time_to_completion'

X = df[feature_cols]
y = df[target_col]
```

**3. Train/Test Split**

```python
from sklearn.model_selection import train_test_split

# Split by session (not by frame) to avoid data leakage
sessions = df['session_id'].unique()
train_sessions, test_sessions = train_test_split(
    sessions, test_size=0.2, random_state=42
)

train_df = df[df['session_id'].isin(train_sessions)]
test_df = df[df['session_id'].isin(test_sessions)]

X_train = train_df[feature_cols]
y_train = train_df[target_col]
X_test = test_df[feature_cols]
y_test = test_df[target_col]
```

### Model Training

**Phase 1: Baseline (Linear Regression)**

```python
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score

# Train model
model = LinearRegression()
model.fit(X_train, y_train)

# Evaluate
y_pred = model.predict(X_test)
mae = mean_absolute_error(y_test, y_pred)
r2 = r2_score(y_test, y_pred)

print(f"MAE: {mae:.2f} seconds")
print(f"R²: {r2:.3f}")
```

**Phase 2: Random Forest**

```python
from sklearn.ensemble import RandomForestRegressor

model = RandomForestRegressor(
    n_estimators=100,
    max_depth=15,
    min_samples_split=10,
    random_state=42
)
model.fit(X_train, y_train)

y_pred = model.predict(X_test)
mae = mean_absolute_error(y_test, y_pred)
r2 = r2_score(y_test, y_pred)

print(f"MAE: {mae:.2f} seconds")
print(f"R²: {r2:.3f}")
```

**Phase 3: XGBoost (Advanced)**

```python
import xgboost as xgb

model = xgb.XGBRegressor(
    n_estimators=200,
    learning_rate=0.05,
    max_depth=10,
    random_state=42
)
model.fit(X_train, y_train)

y_pred = model.predict(X_test)
mae = mean_absolute_error(y_test, y_pred)
r2 = r2_score(y_test, y_pred)

print(f"MAE: {mae:.2f} seconds")
print(f"R²: {r2:.3f}")
```

### Model Evaluation

**Metrics**:
- **MAE** (Mean Absolute Error): Average prediction error in seconds
  - Target: < 10 seconds
- **R²** (Coefficient of Determination): Model fit quality
  - Target: > 0.85
- **RMSE** (Root Mean Squared Error): Penalizes large errors
  - Target: < 15 seconds

**Per-Food-Type Evaluation**:
```python
for food_type in df['food_type'].unique():
    test_food = test_df[test_df['food_type'] == food_type]
    X_food = test_food[feature_cols]
    y_food = test_food[target_col]

    y_pred_food = model.predict(X_food)
    mae_food = mean_absolute_error(y_food, y_pred_food)

    print(f"{food_type}: MAE = {mae_food:.2f}s")
```

**Feature Importance**:
```python
import matplotlib.pyplot as plt

# For Random Forest or XGBoost
importance = model.feature_importances_
feature_importance = pd.DataFrame({
    'feature': feature_cols,
    'importance': importance
}).sort_values('importance', ascending=False)

print(feature_importance)

# Plot
plt.figure(figsize=(10, 6))
plt.barh(feature_importance['feature'], feature_importance['importance'])
plt.xlabel('Importance')
plt.title('Feature Importance')
plt.tight_layout()
plt.savefig('feature_importance.png')
```

### Model Deployment

**Save Model**:
```python
import joblib

# Save model
joblib.dump(model, 'models/frying_predictor_v1.pkl')

# Save feature scaler (if used)
joblib.dump(scaler, 'models/feature_scaler_v1.pkl')
```

**Load and Use**:
```python
# Load model
model = joblib.load('models/frying_predictor_v1.pkl')

# Real-time prediction
current_features = {
    'brown_ratio': 0.25,
    'golden_ratio': 0.40,
    'mean_hue': 22.5,
    'mean_saturation': 145.2,
    'mean_value': 180.8,
    'mean_l': 75.3,
    'mean_a': 12.5,
    'mean_b': 35.2,
    'food_area_ratio': 0.38,
    'oil_temp': 178.5,
    'elapsed_time': 120.0
}

X_current = pd.DataFrame([current_features])
time_remaining = model.predict(X_current)[0]

print(f"Estimated time remaining: {time_remaining:.1f} seconds")

if time_remaining < 10:
    print("⚠️ ALERT: Food is almost ready!")
```

---

## 📊 Data Quality Checks

### Session Validation

After each session, verify:

```python
def validate_session(session_path):
    """Validate session data quality"""
    issues = []

    # Check image count
    images = glob.glob(f"{session_path}/images/*.jpg")
    if len(images) < 50:
        issues.append(f"Too few images: {len(images)}")

    # Check CSV
    csv_path = f"{session_path}/sensor_log.csv"
    if not os.path.exists(csv_path):
        issues.append("Missing sensor_log.csv")
    else:
        df = pd.read_csv(csv_path)
        if len(df) != len(images):
            issues.append(f"Image/CSV mismatch: {len(images)} images, {len(df)} CSV rows")

    # Check metadata
    json_path = f"{session_path}/session_data.json"
    if not os.path.exists(json_path):
        issues.append("Missing session_data.json")
    else:
        with open(json_path, 'r') as f:
            metadata = json.load(f)

        if 'completion_frame' not in metadata:
            issues.append("Completion time not marked!")

        if not metadata.get('food_type'):
            issues.append("Food type not specified")

    if issues:
        print(f"❌ Validation failed for {session_path}:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    else:
        print(f"✅ Session validated: {session_path}")
        return True
```

### Dataset Statistics

```python
def dataset_statistics():
    """Print dataset statistics"""
    sessions = glob.glob("frying_dataset/*/session_data.json")

    stats = {
        'total_sessions': len(sessions),
        'food_types': {},
        'total_frames': 0,
        'avg_duration': []
    }

    for session_file in sessions:
        with open(session_file, 'r') as f:
            session = json.load(f)

        food_type = session.get('food_type', 'unknown')
        stats['food_types'][food_type] = stats['food_types'].get(food_type, 0) + 1

        duration = session.get('duration', 0)
        stats['avg_duration'].append(duration)

        images = glob.glob(f"{os.path.dirname(session_file)}/images/*.jpg")
        stats['total_frames'] += len(images)

    print("=" * 50)
    print("DATASET STATISTICS")
    print("=" * 50)
    print(f"Total sessions: {stats['total_sessions']}")
    print(f"Total frames: {stats['total_frames']}")
    print(f"Average duration: {np.mean(stats['avg_duration']):.1f} seconds")
    print(f"\nSessions by food type:")
    for food_type, count in stats['food_types'].items():
        print(f"  - {food_type}: {count} sessions")
    print("=" * 50)
```

---

## 🎯 Target Metrics

### Data Collection Goals

- **Total Sessions**: 200+ (40+ per food type)
- **Session Duration**: 2-5 minutes typical
- **Image Quality**: Clear, well-lit, stable
- **Ground Truth Accuracy**: ±2°C temperature, ±5 seconds timing
- **Data Completeness**: 100% (all sessions have images + CSV + metadata)

### Model Performance Goals

- **MAE**: < 10 seconds (prediction error)
- **R²**: > 0.85 (model fit)
- **Per-Food-Type MAE**: < 15 seconds
- **Real-Time Latency**: < 100ms (prediction time)
- **False Positive Rate**: < 5% (premature alerts)
- **False Negative Rate**: < 2% (missed perfect doneness)

---

## 🔄 Continuous Improvement

### Data Collection Tips

1. **Label edge cases**: Undercooked, overcooked, burnt
2. **Document anomalies**: Unexpected behaviors
3. **Vary conditions**: Don't collect all data in one day
4. **Review regularly**: Check data quality weekly
5. **Retrain periodically**: Add new sessions monthly

### Model Iteration

1. **Start simple**: Linear regression baseline
2. **Add complexity**: Random Forest → XGBoost
3. **Feature engineering**: Add derived features
4. **Hyperparameter tuning**: GridSearchCV
5. **Cross-validation**: K-fold validation
6. **A/B testing**: Compare model versions in production

---

## 📚 Reference

### Session Metadata Schema

```json
{
  "session_id": "chicken_20251028_143012",
  "food_type": "chicken",
  "start_time": 1698500000.123,
  "end_time": 1698500180.456,
  "duration": 180.333,
  "completion_frame": 181,
  "completion_time": 180.5,
  "probe_temp": 74.0,
  "notes": "Fresh oil, 180°C target",
  "camera_config": {
    "resolution": [640, 360],
    "fps": 2
  },
  "sensor_config": {
    "mode": "simulate"
  }
}
```

### Sensor Log Schema (CSV)

```
timestamp,elapsed_time,oil_temp,fryer_temp,internal_temp
1698500000.123,0.000,180.0,185.0,20.0
1698500000.623,0.500,179.5,184.8,22.5
1698500001.123,1.000,179.0,184.5,25.0
...
```

---

## 🆘 Troubleshooting

### Common Issues

**Images are blurry**:
- Clean camera lens
- Adjust focus
- Reduce steam/smoke
- Improve lighting

**Temperature readings inconsistent**:
- Verify sensor connections
- Calibrate sensors
- Check for loose wiring
- Use higher-quality sensors

**Completion timing uncertain**:
- Use food probe thermometer
- Document visual cues
- Cut sample for verification
- Be consistent with criteria

**Dataset imbalanced**:
- Collect more sessions for underrepresented foods
- Use data augmentation (carefully)
- Apply class weights in model training

---

## ✅ Checklist

### Pre-Session
- [ ] Camera mounted and focused
- [ ] Sensors connected and reading
- [ ] Data collector running
- [ ] Food probe thermometer ready
- [ ] Safety equipment in place

### During Session
- [ ] Session started with correct food type
- [ ] Monitor video feed for issues
- [ ] Watch for perfect doneness
- [ ] Probe thermometer ready

### Mark Completion
- [ ] Insert probe into thickest part
- [ ] Wait for temperature stabilization
- [ ] Record accurate temperature
- [ ] Click "Mark Completion"
- [ ] Add descriptive notes

### Post-Session
- [ ] Stop session properly
- [ ] Verify image count
- [ ] Check CSV completeness
- [ ] Review session_data.json
- [ ] Run validation script

### Dataset Management
- [ ] Organize sessions by date
- [ ] Back up data regularly
- [ ] Run feature extraction
- [ ] Check dataset statistics
- [ ] Document anomalies

---

## 📞 Support

For questions:
1. Review this guide
2. Check troubleshooting section
3. Validate data with provided scripts
4. Document issues for improvement

---

**Version**: 1.0.0
**Last Updated**: 2025-10-28
**Status**: Ready for Production Data Collection
