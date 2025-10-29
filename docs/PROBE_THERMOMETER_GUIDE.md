# Food Probe Thermometer Usage Guide

## ❓ Common Questions

### Q: When do I insert the probe thermometer?

**A: Insert probe when food LOOKS almost done (visual inspection)**

### Q: Do I have to manually record data?

**A: NO! System records everything automatically. You only click ONE button.**

---

## 🎯 The Simple Truth

### What's Automatic ✅

- 📷 Camera recording (continuous)
- 📊 Temperature sensor logging (every frame)
- 💾 Image saving (1-2 FPS)
- 📝 CSV file writing (automatic)
- ⏱️ Timestamp recording (automatic)

### What's Manual ❌

- 🔴 Click "Start Session" (once at beginning)
- 🟢 **Click "Mark Completion"** (once when probe shows correct temp)
- ⚫ Click "Stop Session" (once at end)

**That's it! Only 3 clicks total.**

---

## 📖 Detailed Workflow

### Step-by-Step Process

```
┌─────────────────────────────────────────────────┐
│ 1. START SESSION                                │
│    Click "Start Session"                        │
│    Enter food type: "chicken_wings"             │
│    System starts AUTO-RECORDING everything      │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│ 2. MONITOR FRYING (2-5 minutes)                 │
│    YOU: Watch video feed                        │
│    SYSTEM: Records images + temps automatically │
│                                                  │
│    Visual changes you'll see:                   │
│    - Pale → Light golden → Golden → Brown       │
│    - Bubbles: Vigorous → Moderate → Gentle      │
│    - Food: Sinking → Floating                   │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│ 3. VISUAL CHECK (when food looks ~80-90% done)  │
│    Chicken: Light golden brown                  │
│    Shrimp: Starting to curl, pink edges         │
│    Fries: Yellow-golden color                   │
│                                                  │
│    ⚠️ DON'T insert probe yet!                   │
│    Just observe with your eyes                  │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│ 4. INSERT PROBE (when you think it's ready)     │
│    - Carefully insert into thickest part        │
│    - Wait 5-10 seconds for reading              │
│    - Read the temperature                       │
│                                                  │
│    Example: Probe shows 74°C                    │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│ 5. DECISION TIME                                │
│                                                  │
│    If temp is CORRECT (e.g., 74°C for chicken): │
│       → IMMEDIATELY click "Mark Completion"     │
│       → Enter probe temp: 74                    │
│       → Add notes: "Perfect golden brown"       │
│       → This is your GROUND TRUTH!              │
│                                                  │
│    If temp is TOO LOW (e.g., 65°C):            │
│       → Remove probe                            │
│       → Continue frying                         │
│       → Check again in 30-60 seconds            │
│       → System keeps recording (automatic)      │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│ 6. OPTIONAL: Continue Recording                 │
│    After marking completion:                    │
│    - Can record 10-30 more seconds (optional)   │
│    - Captures "overcooked" boundary             │
│    - Helps ML model learn limits                │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│ 7. STOP SESSION                                 │
│    Click "Stop Session"                         │
│    System saves all data to disk                │
│    Done!                                        │
└─────────────────────────────────────────────────┘
```

---

## 🌡️ Temperature Targets

### Internal Temperature (Probe Reading)

| Food Type | Target Temp | Color/Visual |
|-----------|-------------|--------------|
| **Chicken** | 74°C (165°F) | Golden brown, juices clear |
| **Chicken Wings** | 74°C (165°F) | Crispy skin, golden |
| **Shrimp** | 63°C (145°F) | Pink/white, curled, opaque |
| **Fish** | 63°C (145°F) | Opaque, flakes easily |
| **Pork** | 63°C (145°F) | Light pink center |
| **Potato Fries** | N/A (visual only) | Golden yellow, crispy |
| **Onion Rings** | N/A (visual only) | Golden brown |

### When to Insert Probe

**Visual Cues by Food Type**:

**Chicken/Chicken Wings**:
- Color: Light golden → Insert probe
- Skin: Starting to crisp
- Time: Around 3-4 minutes (depends on size)

**Shrimp**:
- Color: Pink edges visible → Insert probe
- Shape: Starting to curl
- Time: Around 2-3 minutes

**Fish**:
- Color: Edges turning golden → Insert probe
- Surface: Slightly crispy
- Time: Around 3-4 minutes

**Pork**:
- Color: Light golden → Insert probe
- Surface: Firm to the touch
- Time: Around 3-5 minutes

---

## 🎓 Important Concepts

### What is "Ground Truth"?

**Ground Truth** = The exact moment when food is perfectly cooked

- This is THE MOST IMPORTANT data point!
- Everything before this = "not done yet"
- Everything after this = "overcooked"
- ML model learns to predict THIS moment

### Why Use Probe Thermometer?

**Visual inspection alone is NOT reliable**:
- ❌ Food can look done but be raw inside
- ❌ Food can look perfect but be overcooked
- ❌ Oil color varies (fresh vs. used oil)
- ❌ Lighting affects appearance

**Probe thermometer is OBJECTIVE**:
- ✅ Internal temperature doesn't lie
- ✅ Food safety standard (e.g., 74°C for chicken)
- ✅ Consistent across all sessions
- ✅ Reproducible results

---

## 📊 What Gets Recorded

### Automatically Recorded (No Action Needed)

**Every 0.5-1.0 seconds**:
```
Frame 0000:
  - Image: t0000.jpg (camera capture)
  - Timestamp: 1698500000.000
  - Elapsed: 0.0 seconds
  - Oil Temp: 180.0°C
  - Fryer Temp: 185.0°C
  ✅ Automatically saved

Frame 0001:
  - Image: t0001.jpg
  - Timestamp: 1698500000.500
  - Elapsed: 0.5 seconds
  - Oil Temp: 179.8°C
  - Fryer Temp: 184.9°C
  ✅ Automatically saved

... continues until you stop ...

Frame 0360:
  - Image: t0360.jpg
  - Timestamp: 1698500180.000
  - Elapsed: 180.0 seconds
  - Oil Temp: 178.5°C
  - Fryer Temp: 184.2°C
  ✅ Automatically saved
```

### Manually Marked (One Click)

**When you click "Mark Completion"**:
```
⭐ GROUND TRUTH MARKER ⭐
  - Completion Frame: 0360
  - Completion Time: 180.0 seconds
  - Probe Temperature: 74.0°C
  - Notes: "Perfect golden brown, crispy"
  ✅ Saved in session_data.json
```

---

## 🔍 Example Session

### Real-World Example: Chicken Wings

**Setup**:
- Food: 500g chicken wings
- Oil: Fresh oil, 180°C target
- Camera: Positioned 40cm above

**Timeline**:

**0:00** - Click "Start Session"
- Enter: "chicken_wings"
- System starts recording
- Wings are pale, raw color

**0:30** - Monitor
- Wings sizzling, lots of bubbles
- Still pale color
- Don't check yet

**1:00** - Monitor
- Color starting to change
- Light yellow appearing
- Don't check yet

**1:30** - Monitor
- Light golden color
- Bubbles reducing
- Don't check yet

**2:00** - Monitor
- Golden color
- Wings starting to float
- Don't check yet

**2:30** - Visual inspection
- Nice golden brown
- Skin looks crispy
- Time to check! 👇

**2:32** - Insert probe
- Insert into thickest wing
- Wait 10 seconds
- Reading stabilizes...

**2:42** - Read probe: **74°C** ✅
- Temperature is perfect!
- Immediately click "Mark Completion"
- Enter probe temp: 74
- Notes: "Perfect golden, crispy skin"
- ⭐ GROUND TRUTH RECORDED

**2:45** - Optional: Continue 30 more seconds
- Observe transition to "slightly overcooked"
- Helps ML learn boundaries

**3:15** - Click "Stop Session"
- System saves all data
- Done!

**Result**:
```
Session: chicken_wings_20251028_143012
- Total frames: 390 (at 2 FPS for 195 seconds)
- Completion marked at: frame 324 (162 seconds)
- Probe temp: 74°C
- Data quality: ✅ Perfect
```

---

## ✅ Best Practices

### DO ✅

1. **Wait for visual cues** before inserting probe
2. **Insert probe carefully** to avoid burns
3. **Wait 5-10 seconds** for temperature to stabilize
4. **Click "Mark Completion" immediately** when temp is correct
5. **Record probe temperature accurately**
6. **Add descriptive notes** (color, texture, etc.)
7. **Continue recording 10-30s after** completion (optional but helpful)

### DON'T ❌

1. **Don't insert probe too early** (wastes time, unnecessary checks)
2. **Don't forget to click "Mark Completion"** (NO GROUND TRUTH!)
3. **Don't approximate temperature** (be precise: 74°C not "about 75")
4. **Don't click completion if temp is wrong** (wait and check again)
5. **Don't move camera during session** (affects data quality)
6. **Don't skip notes** (future you will thank present you)

---

## 🎯 Quality Checklist

After each session, verify:

- [ ] Session started with correct food type
- [ ] Images captured continuously (check count)
- [ ] **Completion was marked** (check session_data.json)
- [ ] **Probe temperature recorded** (not null)
- [ ] Notes added (describe appearance)
- [ ] CSV file complete (matches image count)
- [ ] Session stopped properly (files saved)

---

## ❓ FAQ

**Q: What if I forget to mark completion?**
A: Session is useless for ML training (no ground truth). Delete it and redo.

**Q: Can I mark completion multiple times?**
A: No, system only records first mark. Be careful!

**Q: What if probe temp is between targets (e.g., 70°C)?**
A: Either wait for correct temp OR mark it and note "slightly undercooked" in notes.

**Q: Do I need probe for french fries?**
A: No, use visual cues (golden yellow color). Mark when perfect visually.

**Q: What if probe is broken/unavailable?**
A: For meat: Don't collect data (unreliable). For vegetables: Use visual cues only.

**Q: Can I check probe multiple times before marking?**
A: YES! Check as many times as needed. Only click "Mark Completion" once when perfect.

**Q: What if I mark completion too early by mistake?**
A: Stop session immediately, delete data, start fresh. Quality > quantity.

---

## 📞 Remember

**The Probe Thermometer is Your Friend**

- It tells you the TRUTH about doneness
- It makes your ML model ACCURATE
- It ensures FOOD SAFETY
- It provides CONSISTENT ground truth

**The "Mark Completion" button is the MOST IMPORTANT button**

- Everything depends on clicking it at the RIGHT moment
- When probe shows target temp → Click immediately!
- This creates your ground truth
- This is what ML learns from

**One bad ground truth = One wasted session**
**One perfect ground truth = One valuable training example**

---

**Version**: 1.0.0
**Last Updated**: 2025-10-28
