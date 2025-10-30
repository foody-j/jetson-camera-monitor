#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jetson Orin #1 - Integrated Monitoring System
- Auto-start/Auto-down (YOLO person detection + MQTT)
- Stir-fry Camera Monitoring (Data collection)
- Vibration Error Detection (USB2RS485 sensor - future)

Designed for kitchen staff (40-50 years old) - Large, clear, simple interface
"""

import tkinter as tk
from tkinter import ttk, messagebox
import cv2
from PIL import Image, ImageTk
from ultralytics import YOLO
from datetime import datetime, time as dtime, timedelta
import time
import os
import json
import threading
import paho.mqtt.client as mqtt

# =========================
# Load Configuration
# =========================
def load_config(config_path="config.json"):
    """Load configuration from JSON file"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

config = load_config()

# Auto-start/down configuration
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

# MQTT Configuration
MQTT_ENABLED = config.get('mqtt_enabled', False)
MQTT_BROKER = config.get('mqtt_broker', 'localhost')
MQTT_PORT = config.get('mqtt_port', 1883)
MQTT_TOPIC = config.get('mqtt_topic', 'robot/control')
MQTT_QOS = config.get('mqtt_qos', 1)
MQTT_CLIENT_ID = config.get('mqtt_client_id', 'robotcam_jetson')

# Stir-fry monitoring configuration
STIRFRY_CAMERA_INDEX = config.get('stirfry_camera_index', 2)  # Different camera
STIRFRY_SAVE_DIR = config.get('stirfry_save_dir', 'StirFry_Data')

# Fixed parameters
YOLO_IMGSZ = 416  # Reduced from 640 for better performance
MOG2_HISTORY = 500
MOG2_VARTHRESH = 16
BINARY_THRESH = 200
WARMUP_FRAMES = 30

# GUI Configuration
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 900
LARGE_FONT = ("NanumGothic", 24, "bold")
MEDIUM_FONT = ("NanumGothic", 18)
NORMAL_FONT = ("NanumGothic", 14)
STATUS_FONT = ("NanumGothic", 16, "bold")

# Colors
COLOR_OK = "#4CAF50"      # Green
COLOR_ERROR = "#F44336"   # Red
COLOR_WARNING = "#FFC107" # Yellow
COLOR_INFO = "#2196F3"    # Blue
COLOR_BG = "#263238"      # Dark gray
COLOR_PANEL = "#37474F"   # Medium gray
COLOR_TEXT = "#FFFFFF"    # White

print("[초기화] Jetson #1 통합 시스템 시작 중...")
print(f"[설정] 자동 ON/OFF: {FORCE_MODE or '자동'} | {DAY_START.strftime('%H:%M')}~{DAY_END.strftime('%H:%M')}")
print(f"[설정] 카메라 1 (자동): {CAMERA_INDEX} | 카메라 2 (볶음): {STIRFRY_CAMERA_INDEX}")
print(f"[설정] MQTT: {MQTT_ENABLED} | 브로커: {MQTT_BROKER}:{MQTT_PORT}")


# =========================
# Main Application Class
# =========================
class IntegratedMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ROBOTCAM 통합 시스템 - Jetson #1")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.configure(bg=COLOR_BG)

        # Try fullscreen (can exit with Escape)
        try:
            self.root.attributes('-fullscreen', False)
            self.root.bind("<Escape>", lambda e: self.root.attributes('-fullscreen', False))
        except:
            pass

        # Variables
        self.running = True
        self.mqtt_client = None
        self.yolo_model = None
        self.auto_cap = None
        self.stirfry_cap = None
        self.stirfry_recording = False
        self.stirfry_frame_count = 0
        self.developer_mode = False  # Developer mode toggle
        self.snapshot_count = 0  # Total snapshots taken
        self.last_snapshot_path = None  # Last snapshot file path
        self.last_snapshot_time = None  # Last snapshot timestamp

        # Auto-start/down state
        self.on_triggered = False
        self.det_hold_start = None
        self.night_check_active = False
        self.night_no_person_deadline = None
        self.off_triggered_once = False
        self.prev_daytime = None
        self.last_snapshot_tick = None
        self.frame_idx = 0
        self.yolo_frame_skip = 0  # Frame skip counter for performance

        # Background subtractor
        self.kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        self.bg = cv2.createBackgroundSubtractorMOG2(
            history=MOG2_HISTORY, varThreshold=MOG2_VARTHRESH, detectShadows=True
        )

        # Initialize GUI
        self.create_gui()

        # Initialize systems
        self.init_mqtt()
        self.init_cameras()
        self.init_yolo()

        # Start update loops
        self.update_clock()
        self.update_auto_system()
        self.update_stirfry_camera()

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        print("[초기화] GUI 초기화 완료")

    def create_gui(self):
        """Create the main GUI layout"""
        # Top header
        header_frame = tk.Frame(self.root, bg=COLOR_BG, height=80)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        header_frame.pack_propagate(False)

        tk.Label(header_frame, text="[ ROBOTCAM 통합 시스템 ]",
                font=("NanumGothic", 32, "bold"), bg=COLOR_BG, fg=COLOR_TEXT).pack(side=tk.LEFT, padx=20)

        # Clock/Date display
        clock_frame = tk.Frame(header_frame, bg=COLOR_BG)
        clock_frame.pack(side=tk.RIGHT, padx=20)

        self.time_label = tk.Label(clock_frame, text="--:--:--",
                                   font=("NanumGothic", 28, "bold"), bg=COLOR_BG, fg=COLOR_INFO)
        self.time_label.pack()

        self.date_label = tk.Label(clock_frame, text="----/--/--",
                                   font=MEDIUM_FONT, bg=COLOR_BG, fg=COLOR_TEXT)
        self.date_label.pack()

        # Main content area
        self.content_frame = tk.Frame(self.root, bg=COLOR_BG)
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Configure grid weights for equal distribution (2 or 3 panels)
        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.columnconfigure(1, weight=1)
        self.content_frame.columnconfigure(2, weight=1)
        self.content_frame.rowconfigure(0, weight=1)

        # Panel 1: Auto-start/down (LEFT)
        self.create_auto_panel(self.content_frame)

        # Panel 2: Stir-fry monitoring (MIDDLE)
        self.create_stirfry_panel(self.content_frame)

        # Panel 3: Developer mode (RIGHT - hidden by default)
        self.dev_panel = None
        self.create_dev_panel(self.content_frame)

        # Bottom status bar
        status_frame = tk.Frame(self.root, bg=COLOR_PANEL, height=60)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=10)
        status_frame.pack_propagate(False)

        self.dev_mode_btn = tk.Button(status_frame, text="[ 개발자 모드 ]", font=MEDIUM_FONT,
                 command=self.toggle_developer_mode, width=12, bg="#424242", fg=COLOR_TEXT)
        self.dev_mode_btn.pack(side=tk.LEFT, padx=20, pady=10)

        tk.Button(status_frame, text="[ 진동 체크 ]", font=MEDIUM_FONT,
                 command=self.open_vibration_check, width=12, bg=COLOR_INFO, fg=COLOR_TEXT).pack(side=tk.LEFT, padx=5, pady=10)

        tk.Button(status_frame, text="[ 설정 ]", font=MEDIUM_FONT,
                 command=self.open_settings, width=10).pack(side=tk.LEFT, padx=5, pady=10)

        tk.Button(status_frame, text="[ 종료 ]", font=MEDIUM_FONT,
                 command=self.on_closing, width=10, bg=COLOR_ERROR, fg=COLOR_TEXT).pack(side=tk.LEFT, padx=5, pady=10)

        self.system_status_label = tk.Label(status_frame, text="[ 시스템 정상 ]",
                                           font=STATUS_FONT, bg=COLOR_PANEL, fg=COLOR_OK)
        self.system_status_label.pack(side=tk.RIGHT, padx=20)

    def create_auto_panel(self, parent):
        """Panel 1: Auto-start/down system"""
        panel = tk.LabelFrame(parent, text="[ 자동 ON/OFF ]", font=LARGE_FONT,
                             bg=COLOR_PANEL, fg=COLOR_TEXT, bd=3, relief=tk.RAISED)
        panel.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        # Status indicators (large text)
        self.auto_mode_label = tk.Label(panel, text="모드: 주간", font=MEDIUM_FONT,
                                       bg=COLOR_PANEL, fg=COLOR_INFO)
        self.auto_mode_label.pack(pady=10)

        self.auto_detection_label = tk.Label(panel, text="감지: 대기 중", font=MEDIUM_FONT,
                                            bg=COLOR_PANEL, fg=COLOR_TEXT)
        self.auto_detection_label.pack(pady=5)

        self.auto_status_label = tk.Label(panel, text="상태: 정상", font=MEDIUM_FONT,
                                         bg=COLOR_PANEL, fg=COLOR_OK)
        self.auto_status_label.pack(pady=5)

        self.auto_mqtt_label = tk.Label(panel, text="MQTT: 연결 대기", font=MEDIUM_FONT,
                                       bg=COLOR_PANEL, fg=COLOR_WARNING)
        self.auto_mqtt_label.pack(pady=5)

        # Small preview area
        self.auto_preview_label = tk.Label(panel, text="[카메라 로딩 중...]",
                                          bg="black", fg="white", font=NORMAL_FONT)
        self.auto_preview_label.pack(pady=20, padx=20, fill=tk.BOTH, expand=True)

    def create_stirfry_panel(self, parent):
        """Panel 2: Stir-fry monitoring"""
        panel = tk.LabelFrame(parent, text="[ 볶음 모니터링 ]", font=LARGE_FONT,
                             bg=COLOR_PANEL, fg=COLOR_TEXT, bd=3, relief=tk.RAISED)
        panel.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        # Camera preview area (larger)
        self.stirfry_preview_label = tk.Label(panel, text="[카메라 로딩 중...]",
                                             bg="black", fg="white", font=NORMAL_FONT)
        self.stirfry_preview_label.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        # Status info
        info_frame = tk.Frame(panel, bg=COLOR_PANEL)
        info_frame.pack(pady=10)

        self.stirfry_recording_label = tk.Label(info_frame, text="녹화: OFF",
                                               font=MEDIUM_FONT, bg=COLOR_PANEL, fg=COLOR_TEXT)
        self.stirfry_recording_label.pack(pady=5)

        self.stirfry_count_label = tk.Label(info_frame, text="저장: 0장",
                                           font=MEDIUM_FONT, bg=COLOR_PANEL, fg=COLOR_TEXT)
        self.stirfry_count_label.pack(pady=5)

        # Control buttons
        btn_frame = tk.Frame(panel, bg=COLOR_PANEL)
        btn_frame.pack(pady=10)

        self.stirfry_start_btn = tk.Button(btn_frame, text="[ 시작 ]", font=MEDIUM_FONT,
                                          command=self.start_stirfry_recording, width=12,
                                          bg=COLOR_OK, fg=COLOR_TEXT)
        self.stirfry_start_btn.pack(side=tk.LEFT, padx=5)

        self.stirfry_stop_btn = tk.Button(btn_frame, text="[ 중지 ]", font=MEDIUM_FONT,
                                         command=self.stop_stirfry_recording, width=12,
                                         bg=COLOR_ERROR, fg=COLOR_TEXT, state=tk.DISABLED)
        self.stirfry_stop_btn.pack(side=tk.LEFT, padx=5)

    def create_dev_panel(self, parent):
        """Panel 3: Developer mode (debugging panel)"""
        panel = tk.LabelFrame(parent, text="[ 개발자 모드 ]", font=LARGE_FONT,
                             bg=COLOR_PANEL, fg=COLOR_WARNING, bd=3, relief=tk.RAISED)

        # Title
        tk.Label(panel, text="야간 모션 스냅샷 디버그", font=MEDIUM_FONT,
                bg=COLOR_PANEL, fg=COLOR_TEXT).pack(pady=10)

        # Snapshot stats
        stats_frame = tk.Frame(panel, bg=COLOR_PANEL)
        stats_frame.pack(pady=10, fill=tk.X, padx=20)

        self.dev_snapshot_count_label = tk.Label(stats_frame, text="스냅샷: 0장",
                                                 font=MEDIUM_FONT, bg=COLOR_PANEL, fg=COLOR_INFO)
        self.dev_snapshot_count_label.pack(pady=5)

        self.dev_last_snapshot_label = tk.Label(stats_frame, text="마지막 저장: -",
                                                font=NORMAL_FONT, bg=COLOR_PANEL, fg=COLOR_TEXT)
        self.dev_last_snapshot_label.pack(pady=5)

        # Last snapshot preview
        self.dev_snapshot_preview = tk.Label(panel, text="[스냅샷 미리보기]",
                                            bg="black", fg="white", font=NORMAL_FONT,
                                            width=50, height=15)
        self.dev_snapshot_preview.pack(pady=10, padx=10)

        # Motion detection info
        self.dev_motion_label = tk.Label(panel, text="모션 감지: 대기 중",
                                        font=NORMAL_FONT, bg=COLOR_PANEL, fg=COLOR_TEXT)
        self.dev_motion_label.pack(pady=5)

        # Test button - skip to snapshot mode
        tk.Button(panel, text="[ 스냅샷 모드 즉시 시작 ]", font=NORMAL_FONT,
                 command=self.force_snapshot_mode, bg=COLOR_ERROR, fg=COLOR_TEXT,
                 width=20).pack(pady=10)

        # Store panel reference but don't grid it yet
        self.dev_panel = panel

    def toggle_developer_mode(self):
        """Toggle developer mode panel"""
        self.developer_mode = not self.developer_mode

        if self.developer_mode:
            # Show developer panel
            self.dev_panel.grid(row=0, column=2, padx=10, pady=10, sticky="nsew")
            self.dev_mode_btn.config(bg=COLOR_WARNING, text="[ 개발자 모드 ON ]")
            print("[개발자] 개발자 모드 활성화")
        else:
            # Hide developer panel
            self.dev_panel.grid_forget()
            self.dev_mode_btn.config(bg="#424242", text="[ 개발자 모드 ]")
            print("[개발자] 개발자 모드 비활성화")

    def force_snapshot_mode(self):
        """Force skip to snapshot mode (for testing)"""
        print("[개발자] 스냅샷 모드 강제 시작")
        self.night_check_active = False
        self.night_no_person_deadline = None
        self.off_triggered_once = True
        self.auto_detection_label.config(text="감지: 테스트 모드 (스냅샷)", fg=COLOR_WARNING)
        messagebox.showinfo("테스트 모드", "스냅샷 모드가 즉시 시작되었습니다.\n모션 감지 시 자동 저장됩니다.")

    # =========================
    # Initialization
    # =========================
    def init_mqtt(self):
        """Initialize MQTT connection"""
        if not MQTT_ENABLED:
            print("[MQTT] 설정에서 비활성화됨")
            self.auto_mqtt_label.config(text="MQTT: 비활성화", fg=COLOR_TEXT)
            return

        try:
            def on_connect(client, userdata, flags, rc):
                if rc == 0:
                    print("[MQTT] 연결 성공")
                    self.auto_mqtt_label.config(text="MQTT: 연결됨", fg=COLOR_OK)
                else:
                    print(f"[MQTT] 연결 실패 (코드 {rc})")
                    self.auto_mqtt_label.config(text=f"MQTT: 오류({rc})", fg=COLOR_ERROR)

            def on_disconnect(client, userdata, rc):
                if rc != 0:
                    print(f"[MQTT] 예기치 않은 연결 끊김 (코드 {rc})")
                    self.auto_mqtt_label.config(text="MQTT: 연결 끊김", fg=COLOR_ERROR)

            self.mqtt_client = mqtt.Client(client_id=MQTT_CLIENT_ID)
            self.mqtt_client.on_connect = on_connect
            self.mqtt_client.on_disconnect = on_disconnect

            print(f"[MQTT] {MQTT_BROKER}:{MQTT_PORT}에 연결 중...")
            self.mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            self.mqtt_client.loop_start()

        except Exception as e:
            print(f"[MQTT] 초기화 실패: {e}")
            self.auto_mqtt_label.config(text=f"MQTT: 오류", fg=COLOR_ERROR)

    def init_cameras(self):
        """Initialize both cameras"""
        # Camera 1: Auto-start/down system
        try:
            self.auto_cap = cv2.VideoCapture(CAMERA_INDEX)
            if self.auto_cap.isOpened():
                print(f"[카메라] 자동 ON/OFF 카메라 {CAMERA_INDEX} 열림")
            else:
                print(f"[오류] 자동 ON/OFF 카메라 {CAMERA_INDEX} 열기 실패")
        except Exception as e:
            print(f"[오류] 자동 카메라 초기화 실패: {e}")

        # Camera 2: Stir-fry monitoring
        try:
            self.stirfry_cap = cv2.VideoCapture(STIRFRY_CAMERA_INDEX)
            if self.stirfry_cap.isOpened():
                print(f"[카메라] 볶음 모니터링 카메라 {STIRFRY_CAMERA_INDEX} 열림")
            else:
                print(f"[오류] 볶음 모니터링 카메라 {STIRFRY_CAMERA_INDEX} 열기 실패")
        except Exception as e:
            print(f"[오류] 볶음 카메라 초기화 실패: {e}")

    def init_yolo(self):
        """Initialize YOLO model"""
        try:
            print(f"[YOLO] 모델 로딩 중: {MODEL_PATH}")
            self.yolo_model = YOLO(MODEL_PATH)
            print("[YOLO] 모델 로드 완료")
        except Exception as e:
            print(f"[오류] YOLO 초기화 실패: {e}")
            self.auto_status_label.config(text="상태: YOLO 오류", fg=COLOR_ERROR)

    # =========================
    # Update Loops
    # =========================
    def update_clock(self):
        """Update time and date display"""
        if not self.running:
            return

        now = datetime.now()
        self.time_label.config(text=now.strftime("%H:%M:%S"))
        self.date_label.config(text=now.strftime("%Y년 %m월 %d일"))

        self.root.after(1000, self.update_clock)

    def update_auto_system(self):
        """Update auto-start/down system (YOLO + MQTT)"""
        if not self.running:
            return

        if self.auto_cap is None or not self.auto_cap.isOpened() or self.yolo_model is None:
            self.root.after(100, self.update_auto_system)
            return

        ok, frame = self.auto_cap.read()
        if not ok or frame is None:
            self.root.after(100, self.update_auto_system)
            return

        now = datetime.now()
        daytime = self.is_daytime_mode(now)

        # Handle mode transitions
        if self.prev_daytime is None:
            # First time initialization
            self.prev_daytime = daytime
            if daytime:
                print("[모드] 초기화: 주간 모드")
                self.auto_mode_label.config(text="모드: 주간", fg=COLOR_INFO)
            else:
                print("[모드] 초기화: 야간 모드")
                self.auto_mode_label.config(text="모드: 야간", fg=COLOR_INFO)
                self.night_check_active = True
                self.night_no_person_deadline = now + timedelta(minutes=NIGHT_CHECK_MINUTES)
                print(f"[모드] {NIGHT_CHECK_MINUTES}분간 사람 미감지 확인 시작...")

        # Day -> Night transition
        if (self.prev_daytime is True) and (daytime is False):
            self.night_check_active = True
            self.night_no_person_deadline = now + timedelta(minutes=NIGHT_CHECK_MINUTES)
            self.det_hold_start = None
            self.off_triggered_once = False
            print(f"[모드] 야간 모드로 전환됨")
            self.auto_mode_label.config(text="모드: 야간", fg=COLOR_INFO)

        # Night -> Day transition
        if (self.prev_daytime is False) and (daytime is True):
            self.on_triggered = False
            self.det_hold_start = None
            self.night_check_active = False
            self.night_no_person_deadline = None
            self.off_triggered_once = False
            print("[모드] 주간 모드로 전환됨")
            self.auto_mode_label.config(text="모드: 주간", fg=COLOR_INFO)

        self.prev_daytime = daytime

        # Process based on mode
        if daytime:
            self.process_day_mode(frame, now)
        else:
            self.process_night_mode(frame, now)

        # Update preview
        self.update_auto_preview(frame)

        self.root.after(20, self.update_auto_system)  # ~50 FPS for smoother display

    def process_day_mode(self, frame, now):
        """Process day mode: YOLO person detection"""
        # Skip frames for performance - process YOLO every 3 frames
        self.yolo_frame_skip += 1
        if self.yolo_frame_skip < 3:
            return  # Skip this frame, use previous detection result

        self.yolo_frame_skip = 0  # Reset counter

        # Run YOLO detection
        results = self.yolo_model.predict(frame, conf=YOLO_CONF, imgsz=YOLO_IMGSZ, verbose=False)
        r = results[0]

        detected = False
        person_count = 0

        # Draw bounding boxes on detected people
        if r.boxes is not None and r.boxes.cls is not None and len(r.boxes.cls) > 0:
            for i, cls in enumerate(r.boxes.cls):
                if r.names.get(int(cls), "") == "person":
                    detected = True
                    person_count += 1
                    # Draw green box around person
                    box = r.boxes.xyxy[i].cpu().numpy().astype(int)
                    cv2.rectangle(frame, (box[0], box[1]), (box[2], box[3]), (0, 255, 0), 3)
                    # Add label
                    cv2.putText(frame, "Person", (box[0], box[1]-10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        if detected:
            if self.det_hold_start is None:
                self.det_hold_start = now
                self.auto_detection_label.config(text=f"감지: 사람 {person_count}명", fg=COLOR_WARNING)
            else:
                hold_sec = (now - self.det_hold_start).total_seconds()
                remaining = int(DETECTION_HOLD_SEC - hold_sec)
                self.auto_detection_label.config(text=f"감지: {person_count}명 ({remaining}초)", fg=COLOR_WARNING)

                if hold_sec >= DETECTION_HOLD_SEC and not self.on_triggered:
                    print("=" * 50)
                    print("ON !!!")
                    print("=" * 50)
                    self.publish_mqtt("ON")
                    self.on_triggered = True
                    self.auto_detection_label.config(text="감지: ON 전송 완료", fg=COLOR_OK)
        else:
            self.det_hold_start = None
            if not self.on_triggered:
                self.auto_detection_label.config(text="감지: 대기 중", fg=COLOR_TEXT)

    def process_night_mode(self, frame, now):
        """Process night mode: No-person check + motion detection"""
        self.frame_idx += 1

        # Debug: Show current state in developer mode
        if self.developer_mode and self.frame_idx % 30 == 0:  # Every 30 frames
            if self.night_check_active:
                print(f"[디버그] 야간 체크 활성 | 프레임: {self.frame_idx}")
            else:
                print(f"[디버그] 스냅샷 모드 | 프레임: {self.frame_idx} | 워밍업: {self.frame_idx <= WARMUP_FRAMES}")

        if self.night_check_active:
            # Stage 1: YOLO check for no-person
            results = self.yolo_model.predict(frame, conf=YOLO_CONF, imgsz=YOLO_IMGSZ, verbose=False)
            r = results[0]

            detected = False
            if r.boxes is not None and r.boxes.cls is not None and len(r.boxes.cls) > 0:
                detected = any(r.names.get(int(c), "") == "person" for c in r.boxes.cls)

            if detected:
                # Reset deadline
                self.night_no_person_deadline = now + timedelta(minutes=NIGHT_CHECK_MINUTES)
                self.auto_detection_label.config(text="감지: 사람 있음 (리셋)", fg=COLOR_WARNING)

            # Check deadline
            if self.night_no_person_deadline is not None and now >= self.night_no_person_deadline:
                if not self.off_triggered_once:
                    print("=" * 50)
                    print("OFF !!!")
                    print("=" * 50)
                    self.publish_mqtt("OFF")
                    self.off_triggered_once = True
                    self.auto_detection_label.config(text="감지: OFF 전송 ✓", fg=COLOR_OK)
                self.night_check_active = False
                self.night_no_person_deadline = None
            else:
                if self.night_no_person_deadline is not None:
                    remain = int((self.night_no_person_deadline - now).total_seconds())
                    self.auto_detection_label.config(text=f"감지: {remain}초 남음", fg=COLOR_INFO)
        else:
            # Stage 2: Motion detection
            if self.frame_idx > WARMUP_FRAMES:
                fg = self.bg.apply(frame)
                _, thr = cv2.threshold(fg, BINARY_THRESH, 255, cv2.THRESH_BINARY)
                clean = cv2.morphologyEx(thr, cv2.MORPH_OPEN, self.kernel, iterations=1)
                contours, _ = cv2.findContours(clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                motion = False
                motion_areas = []

                # Draw motion detection boxes
                for cnt in contours:
                    area = cv2.contourArea(cnt)
                    if area >= MOTION_MIN_AREA:
                        motion = True
                        motion_areas.append(int(area))
                        # Draw blue box around motion
                        x, y, w, h = cv2.boundingRect(cnt)
                        cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
                        cv2.putText(frame, f"{int(area)}", (x, y-5),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)

                # Update developer panel
                if self.developer_mode:
                    if motion:
                        self.dev_motion_label.config(
                            text=f"모션 감지: {len(motion_areas)}개 영역 (면적: {sum(motion_areas)})",
                            fg=COLOR_WARNING)
                    else:
                        self.dev_motion_label.config(text="모션 감지: 없음", fg=COLOR_TEXT)

                if motion:
                    now_tick = time.monotonic()
                    can_save = (self.last_snapshot_tick is None) or ((now_tick - self.last_snapshot_tick) >= SAVE_COOLDOWN_SEC)
                    if can_save:
                        self.save_snapshot(frame, now)
                        self.last_snapshot_tick = now_tick
                        self.auto_detection_label.config(text="감지: 모션 저장됨", fg=COLOR_OK)
                else:
                    self.auto_detection_label.config(text="감지: 모션 대기", fg=COLOR_TEXT)

    def update_stirfry_camera(self):
        """Update stir-fry camera preview"""
        if not self.running:
            return

        if self.stirfry_cap is None or not self.stirfry_cap.isOpened():
            self.root.after(100, self.update_stirfry_camera)
            return

        ok, frame = self.stirfry_cap.read()
        if not ok or frame is None:
            self.root.after(100, self.update_stirfry_camera)
            return

        # If recording, save frames
        if self.stirfry_recording:
            self.save_stirfry_frame(frame)

        # Update preview
        self.update_stirfry_preview(frame)

        self.root.after(20, self.update_stirfry_camera)  # ~50 FPS for smoother display

    def update_auto_preview(self, frame):
        """Update auto system preview"""
        try:
            # Resize for preview (larger - more space now)
            preview = cv2.resize(frame, (560, 420))
            preview_rgb = cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(preview_rgb)
            imgtk = ImageTk.PhotoImage(image=img)
            self.auto_preview_label.imgtk = imgtk
            self.auto_preview_label.configure(image=imgtk, text="")
        except Exception as e:
            pass

    def update_stirfry_preview(self, frame):
        """Update stir-fry camera preview"""
        try:
            # Resize for preview (larger - more space now)
            preview = cv2.resize(frame, (560, 420))
            preview_rgb = cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(preview_rgb)
            imgtk = ImageTk.PhotoImage(image=img)
            self.stirfry_preview_label.imgtk = imgtk
            self.stirfry_preview_label.configure(image=imgtk, text="")
        except Exception as e:
            pass

    # =========================
    # Helper Functions
    # =========================
    def is_daytime_mode(self, now):
        """Check if current time is daytime"""
        if FORCE_MODE == "day":
            return True
        if FORCE_MODE == "night":
            return False

        today_start = now.replace(hour=DAY_START.hour, minute=DAY_START.minute, second=0, microsecond=0)
        today_end = now.replace(hour=DAY_END.hour, minute=DAY_END.minute, second=0, microsecond=0)
        return today_start <= now <= today_end

    def publish_mqtt(self, message):
        """Publish message to MQTT broker"""
        if self.mqtt_client is not None:
            try:
                result = self.mqtt_client.publish(MQTT_TOPIC, message, qos=MQTT_QOS)
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    print(f"[MQTT] 메시지 전송 완료: {message}")
                else:
                    print(f"[MQTT] 전송 실패 (코드 {result.rc})")
            except Exception as e:
                print(f"[MQTT] 전송 오류: {e}")

    def save_snapshot(self, frame, timestamp):
        """Save motion snapshot"""
        try:
            day_dir = timestamp.strftime("%Y%m%d")
            ts_name = timestamp.strftime("%H%M%S")
            out_dir = os.path.join(SNAPSHOT_DIR, day_dir)
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, f"{ts_name}.jpg")
            cv2.imwrite(out_path, frame)

            # Update tracking
            self.snapshot_count += 1
            self.last_snapshot_path = out_path
            self.last_snapshot_time = timestamp

            print(f"[스냅샷] {timestamp.strftime('%Y-%m-%d %H:%M:%S')} -> {out_path}")

            # Update developer panel
            if self.developer_mode:
                self.dev_snapshot_count_label.config(text=f"스냅샷: {self.snapshot_count}장", fg=COLOR_INFO)
                self.dev_last_snapshot_label.config(
                    text=f"마지막 저장: {timestamp.strftime('%H:%M:%S')}")

                # Update preview
                try:
                    preview = cv2.resize(frame, (320, 240))
                    preview_rgb = cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(preview_rgb)
                    imgtk = ImageTk.PhotoImage(image=img)
                    self.dev_snapshot_preview.imgtk = imgtk
                    self.dev_snapshot_preview.configure(image=imgtk, text="")
                except:
                    pass

        except Exception as e:
            print(f"[오류] 스냅샷 저장 실패: {e}")

    def save_stirfry_frame(self, frame):
        """Save stir-fry monitoring frame"""
        try:
            now = datetime.now()
            day_dir = now.strftime("%Y%m%d")
            ts_name = now.strftime("%H%M%S_%f")[:-3]  # Include milliseconds
            out_dir = os.path.join(STIRFRY_SAVE_DIR, day_dir)
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, f"{ts_name}.jpg")
            cv2.imwrite(out_path, frame)
            self.stirfry_frame_count += 1
            self.stirfry_count_label.config(text=f"저장: {self.stirfry_frame_count}장")
        except Exception as e:
            print(f"[오류] 볶음 프레임 저장 실패: {e}")

    # =========================
    # Control Functions
    # =========================
    def start_stirfry_recording(self):
        """Start stir-fry data recording"""
        self.stirfry_recording = True
        self.stirfry_frame_count = 0
        self.stirfry_recording_label.config(text="녹화: ON (진행중)", fg=COLOR_ERROR)
        self.stirfry_start_btn.config(state=tk.DISABLED)
        self.stirfry_stop_btn.config(state=tk.NORMAL)
        print("[볶음] 녹화 시작")

    def stop_stirfry_recording(self):
        """Stop stir-fry data recording"""
        self.stirfry_recording = False
        self.stirfry_recording_label.config(text="녹화: OFF", fg=COLOR_TEXT)
        self.stirfry_start_btn.config(state=tk.NORMAL)
        self.stirfry_stop_btn.config(state=tk.DISABLED)
        print(f"[볶음] 녹화 중지 - 총 프레임 수: {self.stirfry_frame_count}")
        messagebox.showinfo("녹화 완료", f"총 {self.stirfry_frame_count}장 저장되었습니다.")

    def open_vibration_check(self):
        """Open vibration sensor check dialog"""
        # Create popup window
        vib_window = tk.Toplevel(self.root)
        vib_window.title("진동 센서 체크")
        vib_window.geometry("600x400")
        vib_window.configure(bg=COLOR_BG)

        # Center the window
        vib_window.transient(self.root)
        vib_window.grab_set()

        # Title
        tk.Label(vib_window, text="[ 진동 센서 상태 ]", font=LARGE_FONT,
                bg=COLOR_BG, fg=COLOR_TEXT).pack(pady=20)

        # Status info
        info_frame = tk.Frame(vib_window, bg=COLOR_PANEL, bd=3, relief=tk.RAISED)
        info_frame.pack(pady=20, padx=40, fill=tk.BOTH, expand=True)

        tk.Label(info_frame, text="센서: 미연결", font=("NanumGothic", 20),
                bg=COLOR_PANEL, fg=COLOR_WARNING).pack(pady=20)

        tk.Label(info_frame, text="USB2RS485 연결 대기 중", font=MEDIUM_FONT,
                bg=COLOR_PANEL, fg=COLOR_TEXT).pack(pady=10)

        tk.Label(info_frame, text="향후 구현 예정:", font=NORMAL_FONT,
                bg=COLOR_PANEL, fg="#90A4AE").pack(pady=20)

        features = [
            "- 초기 시동 시 진동 체크",
            "- 로봇 캘리브레이션 후 검증",
            "- 이상 진동 감지 시 알림"
        ]

        for feature in features:
            tk.Label(info_frame, text=feature, font=NORMAL_FONT,
                    bg=COLOR_PANEL, fg=COLOR_TEXT, anchor="w").pack(pady=2)

        # Close button
        tk.Button(vib_window, text="[ 닫기 ]", font=MEDIUM_FONT,
                 command=vib_window.destroy, width=15,
                 bg=COLOR_INFO, fg=COLOR_TEXT).pack(pady=20)

        print("[진동] 진동 센서 체크 창 열림")

    def open_settings(self):
        """Open settings dialog (placeholder)"""
        messagebox.showinfo("설정", "설정 기능은 준비 중입니다.\nconfig.json 파일을 직접 수정하세요.")

    def on_closing(self):
        """Handle window close"""
        if messagebox.askokcancel("종료", "프로그램을 종료하시겠습니까?"):
            print("[종료] 시스템 종료 중...")
            self.running = False

            # Cleanup
            if self.auto_cap is not None:
                self.auto_cap.release()
            if self.stirfry_cap is not None:
                self.stirfry_cap.release()
            if self.mqtt_client is not None:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()

            self.root.destroy()
            print("[종료] 프로그램 종료 완료")


# =========================
# Main Entry Point
# =========================
if __name__ == "__main__":
    root = tk.Tk()
    app = IntegratedMonitorApp(root)
    root.mainloop()
