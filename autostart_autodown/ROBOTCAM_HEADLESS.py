#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Headless version of ROBOTCAM_UI.py (no Tkinter GUI)
Uses config.json for settings instead
"""

from ultralytics import YOLO
import cv2
from datetime import datetime, time as dtime, timedelta
import time
import os
import json
import argparse
import paho.mqtt.client as mqtt

# =========================
# Load Configuration
# =========================
def load_config(config_path="config.json"):
    """Load configuration from JSON file"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

# Parse command line arguments
parser = argparse.ArgumentParser(description='YOLO Robot Camera Monitor (Headless)')
parser.add_argument('--config', default='config.json', help='Path to config file')
parser.add_argument('--mode', choices=['auto', 'day', 'night'], help='Override mode from config')
args = parser.parse_args()

# Load config
config = load_config(args.config)
print(f"[CONFIG] Loaded from {args.config}")

# Apply command line override
if args.mode:
    config['mode'] = args.mode
    print(f"[CONFIG] Mode overridden to: {args.mode}")

# Parse configuration
FORCE_MODE = None if config['mode'] == 'auto' else config['mode']
day_start_str = config['day_start']
day_end_str = config['day_end']
sh, sm = int(day_start_str.split(':')[0]), int(day_start_str.split(':')[1])
eh, em = int(day_end_str.split(':')[0]), int(day_end_str.split(':')[1])
DAY_START = dtime(sh, sm)
DAY_END = dtime(eh, em)

MODEL_PATH = config['yolo_model']
CAMERA_INDEX = config['camera_index']
YOLO_CONF = config['yolo_confidence']
DETECTION_HOLD_SEC = config['detection_hold_sec']
NIGHT_CHECK_MINUTES = config['night_check_minutes']
MOTION_MIN_AREA = config['motion_min_area']
SNAPSHOT_DIR = config['snapshot_dir']
SAVE_COOLDOWN_SEC = config['snapshot_cooldown_sec']
DISPLAY_WINDOW = config['display_window']
WIN_W = config['window_width']
WIN_H = config['window_height']

# MQTT Configuration
MQTT_ENABLED = config.get('mqtt_enabled', False)
MQTT_BROKER = config.get('mqtt_broker', 'localhost')
MQTT_PORT = config.get('mqtt_port', 1883)
MQTT_TOPIC = config.get('mqtt_topic', 'robot/control')
MQTT_QOS = config.get('mqtt_qos', 1)
MQTT_CLIENT_ID = config.get('mqtt_client_id', 'robotcam_jetson')

# Fixed parameters
YOLO_IMGSZ = 640
MOG2_HISTORY = 500
MOG2_VARTHRESH = 16
BINARY_THRESH = 200
WARMUP_FRAMES = 30
WIN_NAME = "YOLOv12 ROBOT Monitor"

print(f"[CONFIG] mode={FORCE_MODE or 'auto'} | day={DAY_START.strftime('%H:%M')}~{DAY_END.strftime('%H:%M')}")
print(f"[CONFIG] camera={CAMERA_INDEX} | display={DISPLAY_WINDOW}")
print(f"[CONFIG] MQTT={MQTT_ENABLED} | broker={MQTT_BROKER}:{MQTT_PORT} | topic={MQTT_TOPIC}")

# =========================
# MQTT Setup
# =========================
mqtt_client = None
if MQTT_ENABLED:
    try:
        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                print("[MQTT] Connected successfully")
            else:
                print(f"[MQTT] Connection failed with code {rc}")

        def on_disconnect(client, userdata, rc):
            if rc != 0:
                print(f"[MQTT] Unexpected disconnection (code {rc})")

        mqtt_client = mqtt.Client(client_id=MQTT_CLIENT_ID)
        mqtt_client.on_connect = on_connect
        mqtt_client.on_disconnect = on_disconnect

        print(f"[MQTT] Connecting to {MQTT_BROKER}:{MQTT_PORT}...")
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        mqtt_client.loop_start()  # Start background thread

    except Exception as e:
        print(f"[MQTT] Failed to initialize: {e}")
        mqtt_client = None
else:
    print("[MQTT] Disabled in config")

# =========================
# Utility Functions
# =========================
def ensure_dir(path: str):
    """Create directory if it doesn't exist"""
    os.makedirs(path, exist_ok=True)

def is_daytime(now: datetime, start_t: dtime, end_t: dtime) -> bool:
    """Check if current time is within day hours"""
    today_start = now.replace(hour=start_t.hour, minute=start_t.minute, second=0, microsecond=0)
    today_end = now.replace(hour=end_t.hour, minute=end_t.minute, second=0, microsecond=0)
    return today_start <= now <= today_end

def mode_override(now: datetime, force_mode, start_t: dtime, end_t: dtime) -> bool:
    """Determine day/night mode with force override support"""
    if force_mode == "day":
        return True
    if force_mode == "night":
        return False
    return is_daytime(now, start_t, end_t)

def publish_mqtt(message: str):
    """Publish message to MQTT broker if enabled"""
    if mqtt_client is not None:
        try:
            result = mqtt_client.publish(MQTT_TOPIC, message, qos=MQTT_QOS)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"[MQTT] Published: {message}")
            else:
                print(f"[MQTT] Publish failed with code {result.rc}")
        except Exception as e:
            print(f"[MQTT] Publish error: {e}")

# =========================
# Initialize
# =========================
print(f"[INIT] Loading YOLO model: {MODEL_PATH}")
model = YOLO(MODEL_PATH)

print(f"[INIT] Opening camera {CAMERA_INDEX}...")
cap = cv2.VideoCapture(CAMERA_INDEX)
if not cap.isOpened():
    print(f"[ERROR] Failed to open camera {CAMERA_INDEX}")
    exit(1)

ret, test_frame = cap.read()
if ret:
    h, w = test_frame.shape[:2]
    print(f"[INIT] Camera OK - Resolution: {w}x{h}")
else:
    print("[ERROR] Camera opened but cannot read frames")
    exit(1)

# Create display window if enabled
if DISPLAY_WINDOW:
    cv2.namedWindow(WIN_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WIN_NAME, WIN_W, WIN_H)
    print(f"[INIT] Display window enabled: {WIN_W}x{WIN_H}")
else:
    print("[INIT] Running headless (no display)")

# Night mode background subtractor
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
bg = cv2.createBackgroundSubtractorMOG2(
    history=MOG2_HISTORY, varThreshold=MOG2_VARTHRESH, detectShadows=True
)
frame_idx = 0
last_snapshot_tick = None

# State variables
on_triggered = False
det_hold_start = None
night_check_active = False
night_no_person_deadline = None
off_triggered_once = False
prev_daytime = None

print("[INIT] Initialization complete. Starting main loop...")
print("[INFO] Press 'q' to quit (if display enabled)")

# =========================
# Main Loop
# =========================
try:
    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            print("[ERROR] Camera read failed. Exiting...")
            break

        now = datetime.now()
        daytime = mode_override(now, FORCE_MODE, DAY_START, DAY_END)

        # Day/Night transition detection
        if prev_daytime is None:
            prev_daytime = daytime

        # Day -> Night transition
        if (prev_daytime is True) and (daytime is False):
            night_check_active = True
            night_no_person_deadline = now + timedelta(minutes=NIGHT_CHECK_MINUTES)
            det_hold_start = None
            off_triggered_once = False
            print(f"[MODE] Switched to NIGHT mode. Checking for no-person for {NIGHT_CHECK_MINUTES} minutes...")

        # Night -> Day transition
        if (prev_daytime is False) and (daytime is True):
            on_triggered = False
            det_hold_start = None
            night_check_active = False
            night_no_person_deadline = None
            off_triggered_once = False
            print("[MODE] Switched to DAY mode.")

        prev_daytime = daytime

        # ========== DAY MODE: YOLO person detection ==========
        if daytime:
            results = model.predict(frame, conf=YOLO_CONF, imgsz=YOLO_IMGSZ, verbose=False)
            r = results[0]

            detected = False
            if r.boxes is not None and r.boxes.cls is not None and len(r.boxes.cls) > 0:
                detected = any(r.names.get(int(c), "") == "person" for c in r.boxes.cls)

            # Continuous detection logic
            if detected:
                if det_hold_start is None:
                    det_hold_start = now
                else:
                    hold_sec = (now - det_hold_start).total_seconds()
                    if hold_sec >= DETECTION_HOLD_SEC and not on_triggered:
                        print("=" * 50)
                        print("ON !!!")
                        print("=" * 50)
                        publish_mqtt("ON")
                        on_triggered = True
            else:
                det_hold_start = None

            vis = r.plot()
            mode_text = f"DAY: YOLO(person; {DETECTION_HOLD_SEC}s hold)"

        # ========== NIGHT MODE ==========
        else:
            frame_idx += 1

            # Stage 1: YOLO check for no-person
            if night_check_active:
                results = model.predict(frame, conf=YOLO_CONF, imgsz=YOLO_IMGSZ, verbose=False)
                r = results[0]

                detected = False
                if r.boxes is not None and r.boxes.cls is not None and len(r.boxes.cls) > 0:
                    detected = any(r.names.get(int(c), "") == "person" for c in r.boxes.cls)

                if detected:
                    # Reset deadline if person detected
                    night_no_person_deadline = now + timedelta(minutes=NIGHT_CHECK_MINUTES)

                # Check if deadline passed
                if (night_no_person_deadline is not None) and (now >= night_no_person_deadline):
                    if not off_triggered_once:
                        print("=" * 50)
                        print("OFF !!!")
                        print("=" * 50)
                        publish_mqtt("OFF")
                        off_triggered_once = True
                    night_check_active = False
                    night_no_person_deadline = None
                    print("[MODE] Entering snapshot mode...")

                vis = r.plot()
                if night_check_active and night_no_person_deadline is not None:
                    remain = int((night_no_person_deadline - now).total_seconds())
                    mode_text = f"NIGHT: YOLO check ({remain}s until OFF)"
                else:
                    mode_text = "NIGHT: YOLO check"

            # Stage 2: Motion detection snapshot mode
            else:
                if frame_idx <= WARMUP_FRAMES:
                    vis = frame.copy()
                else:
                    # Background subtraction
                    fg = bg.apply(frame)
                    _, thr = cv2.threshold(fg, BINARY_THRESH, 255, cv2.THRESH_BINARY)
                    clean = cv2.morphologyEx(thr, cv2.MORPH_OPEN, kernel, iterations=1)
                    contours, _ = cv2.findContours(clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                    motion = False
                    vis = frame.copy()
                    for cnt in contours:
                        area = cv2.contourArea(cnt)
                        if area >= MOTION_MIN_AREA:
                            x, y, w, h = cv2.boundingRect(cnt)
                            cv2.rectangle(vis, (x, y), (x+w, y+h), (0, 255, 0), 2)
                            motion = True

                    # Save snapshot on motion
                    if motion:
                        now_tick = time.monotonic()
                        can_save = (last_snapshot_tick is None) or ((now_tick - last_snapshot_tick) >= SAVE_COOLDOWN_SEC)
                        if can_save:
                            day_dir = now.strftime("%Y%m%d")
                            ts_name = now.strftime("%H%M%S")
                            out_dir = os.path.join(SNAPSHOT_DIR, day_dir)
                            os.makedirs(out_dir, exist_ok=True)
                            out_path = os.path.join(out_dir, f"{ts_name}.jpg")
                            cv2.imwrite(out_path, frame)
                            last_snapshot_tick = now_tick
                            print(f"[SNAPSHOT] {now.strftime('%Y-%m-%d %H:%M:%S')} -> {out_path}")

                mode_text = "NIGHT: MOTION-DETECT (snapshots)"

        # ========== Display ==========
        if DISPLAY_WINDOW:
            vis_resized = cv2.resize(vis, (WIN_W, WIN_H))
            sub = (f"time={now.strftime('%H:%M:%S')} | "
                   f"{'forced='+FORCE_MODE if FORCE_MODE else 'auto'} | "
                   f"day={DAY_START.strftime('%H:%M')}~{DAY_END.strftime('%H:%M')}")
            cv2.putText(vis_resized, mode_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255,255,255), 2, cv2.LINE_AA)
            cv2.putText(vis_resized, sub, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2, cv2.LINE_AA)

            cv2.imshow(WIN_NAME, vis_resized)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("\n[INFO] 'q' pressed. Exiting...")
                break
        else:
            # Headless mode - just sleep briefly
            time.sleep(0.03)  # ~30 FPS equivalent

finally:
    print("[CLEANUP] Releasing resources...")
    cap.release()
    if DISPLAY_WINDOW:
        cv2.destroyAllWindows()
    if mqtt_client is not None:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        print("[MQTT] Disconnected")
    print("[EXIT] Done.")
