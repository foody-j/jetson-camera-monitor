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
import sys
import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.communication.mqtt_client import MQTTClient
from src.core.system_info import SystemInfo
from src.monitoring.camera.camera_factory import (
    CameraConfig, CameraType, UniversalCamera, GMSLDriverManager
)

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
CAMERA_TYPE = config.get('camera_type', 'usb')  # Default to USB if not specified
CAMERA_RESOLUTION = config.get('camera_resolution', {'width': 640, 'height': 360})
CAMERA_FPS = config.get('camera_fps', 30)
GMSL_MODE = config.get('gmsl_mode', 2)
GMSL_RESOLUTION_MODE = config.get('gmsl_resolution_mode', 1)
GMSL_DRIVER_DIR = config.get('gmsl_driver_dir',
    '/home/dkuyj/jetson-camera-monitor/SG4A-NONX-G2Y-A1_ORIN_NANO_YUV_JP6.2_L4TR36.4.3')
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

# Stir-fry monitoring configuration - TWO CAMERAS
STIRFRY_LEFT_CAMERA_TYPE = config.get('stirfry_left_camera_type', 'usb')
STIRFRY_LEFT_CAMERA_INDEX = config.get('stirfry_left_camera_index', 1)  # Video1 (CN5)
STIRFRY_LEFT_GMSL_MODE = config.get('stirfry_left_gmsl_mode', 2)
STIRFRY_LEFT_GMSL_RESOLUTION_MODE = config.get('stirfry_left_gmsl_resolution_mode', 1)

STIRFRY_RIGHT_CAMERA_TYPE = config.get('stirfry_right_camera_type', 'usb')
STIRFRY_RIGHT_CAMERA_INDEX = config.get('stirfry_right_camera_index', 2)  # Video2 (CN6)
STIRFRY_RIGHT_GMSL_MODE = config.get('stirfry_right_gmsl_mode', 2)
STIRFRY_RIGHT_GMSL_RESOLUTION_MODE = config.get('stirfry_right_gmsl_resolution_mode', 1)

STIRFRY_SAVE_DIR = config.get('stirfry_save_dir', 'StirFry_Data')

# Fixed parameters
YOLO_IMGSZ = 416  # Reduced from 640 for better performance
MOG2_HISTORY = 500
MOG2_VARTHRESH = 16
BINARY_THRESH = 200
WARMUP_FRAMES = 30

# GUI Configuration - Auto-adaptive for any display size
# These are fallback values - will be auto-calculated based on screen
WINDOW_WIDTH = 720        # Fallback
WINDOW_HEIGHT = 1280      # Fallback
LARGE_FONT = ("NanumGothic", 32, "bold")     # Will auto-scale
MEDIUM_FONT = ("NanumGothic", 24)            # Will auto-scale
NORMAL_FONT = ("NanumGothic", 18)            # Will auto-scale
STATUS_FONT = ("NanumGothic", 20, "bold")    # Will auto-scale
BUTTON_FONT = ("NanumGothic", 22, "bold")    # Will auto-scale

# Colors - Premium/Luxury Theme
COLOR_OK = "#00C853"      # Vibrant Green
COLOR_ERROR = "#D32F2F"   # Deep Red
COLOR_WARNING = "#F57C00" # Deep Orange
COLOR_INFO = "#1976D2"    # Deep Blue
COLOR_BG = "#FAFAFA"      # Off-white background
COLOR_PANEL = "#FFFFFF"   # Pure white panels
COLOR_PANEL_BORDER = "#E0E0E0"  # Subtle border
COLOR_TEXT = "#263238"    # Charcoal text
COLOR_TEXT_LIGHT = "#607D8B"  # Light gray text
COLOR_ACCENT = "#6200EA"  # Purple accent
COLOR_BUTTON = "#1976D2"  # Blue buttons
COLOR_BUTTON_HOVER = "#1565C0"  # Darker blue on hover

print("[초기화] Jetson #1 통합 시스템 시작 중...")

# Check CUDA availability for GPU acceleration
USE_CUDA = False
try:
    if cv2.cuda.getCudaEnabledDeviceCount() > 0:
        USE_CUDA = True
        print(f"[GPU] CUDA 사용 가능! GPU 가속 활성화 (디바이스: {cv2.cuda.getCudaEnabledDeviceCount()}개)")
    else:
        print("[GPU] CUDA 미지원, CPU 모드로 실행")
except:
    print("[GPU] CUDA 체크 실패, CPU 모드로 실행")

print(f"[설정] 자동 ON/OFF: {FORCE_MODE or '자동'} | {DAY_START.strftime('%H:%M')}~{DAY_END.strftime('%H:%M')}")
print(f"[설정] 카메라 0 (사람 감시): {CAMERA_TYPE.upper()} #{CAMERA_INDEX} @ {CAMERA_RESOLUTION['width']}x{CAMERA_RESOLUTION['height']}")
print(f"[설정] 카메라 1 (볶음 왼쪽): {STIRFRY_LEFT_CAMERA_TYPE.upper()} #{STIRFRY_LEFT_CAMERA_INDEX} @ 1920x1536")
print(f"[설정] 카메라 2 (볶음 오른쪽): {STIRFRY_RIGHT_CAMERA_TYPE.upper()} #{STIRFRY_RIGHT_CAMERA_INDEX} @ 1920x1536")
print(f"[설정] MQTT: {MQTT_ENABLED} | 브로커: {MQTT_BROKER}:{MQTT_PORT}")


# =========================
# Main Application Class
# =========================
class IntegratedMonitorApp:
    def __init__(self, root):
        self.root = root
        self.running = True

        # Just fullscreen and loading screen - NOTHING ELSE!
        self.root.configure(bg="#000000")
        self.root.attributes('-fullscreen', True)

        # Show loading screen
        self.loading_label = tk.Label(
            self.root,
            text="⏳ ROBOTCAM 시작 중...",
            font=("Arial", 64, "bold"),
            bg="#000000",
            fg="#00ff00"
        )
        self.loading_label.pack(expand=True)

        # Close handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Schedule everything else for AFTER mainloop starts
        self.root.after(50, self.init_all_variables)

    def init_all_variables(self):
        """Initialize ALL variables after mainloop starts"""
        print("[변수초기화] 시작...", flush=True)
        self.loading_label.config(text="⏳ 시스템 초기화 중...")

        self.mqtt_client = None
        self.system_info = SystemInfo(device_name="Jetson1", location="Kitchen")
        self.yolo_model = None
        self.auto_cap = None
        self.stirfry_left_cap = None
        self.stirfry_right_cap = None
        self.stirfry_recording = False
        self.stirfry_left_frame_count = 0
        self.stirfry_right_frame_count = 0
        self.developer_mode = False
        self.snapshot_count = 0
        self.shutdown_tap_count = 0
        self.last_tap_time = 0
        self.last_snapshot_path = None
        self.last_snapshot_time = None
        self.on_triggered = False
        self.det_hold_start = None
        self.night_check_active = False
        self.night_no_person_deadline = None
        self.off_triggered_once = False
        self.prev_daytime = None
        self.last_snapshot_tick = None
        self.frame_idx = 0
        self.yolo_frame_skip = 0
        self.auto_preview_visible = True
        self.stirfry_left_preview_visible = True
        self.stirfry_right_preview_visible = True
        self.last_person_detected_time = None
        self.preview_hide_delay = config.get('preview_hide_delay', 30)
        self.person_detected = False
        self.motion_detected = False
        self.kernel = None
        self.bg = None

        # Latest frames from background threads
        self.latest_auto_frame = None
        self.latest_left_frame = None
        self.latest_right_frame = None
        self.frame_locks = {
            'auto': threading.Lock(),
            'left': threading.Lock(),
            'right': threading.Lock()
        }

        print("[변수초기화] 완료!", flush=True)

        # Now schedule GUI build
        self.root.after(50, self.build_gui_async)

    def detect_screen_size(self):
        """Auto-detect screen resolution and calculate adaptive sizes"""
        # Get actual screen dimensions
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()

        print(f"[디스플레이] 감지된 화면 크기: {self.screen_width}x{self.screen_height}")

        # Detect orientation
        if self.screen_height > self.screen_width:
            self.is_vertical = True
            print("[디스플레이] 세로 방향 (Portrait) 감지")
        else:
            self.is_vertical = False
            print("[디스플레이] 가로 방향 (Landscape) 감지")

        # Calculate adaptive sizes based on screen height
        # Base: 1280px height → scale proportionally
        base_height = 1280
        scale_factor = self.screen_height / base_height

        # Ensure minimum scale for small screens
        if scale_factor < 0.7:
            scale_factor = 0.7
            print("[디스플레이] 최소 스케일 적용 (0.7)")

        # Store scale factor for layout calculations
        self.scale_factor = scale_factor

        # Calculate font sizes with scaling
        self.large_font_size = max(20, int(32 * scale_factor))
        self.medium_font_size = max(16, int(24 * scale_factor))
        self.normal_font_size = max(12, int(18 * scale_factor))
        self.status_font_size = max(14, int(20 * scale_factor))
        self.button_font_size = max(16, int(22 * scale_factor))

        # Apply dynamic fonts
        global LARGE_FONT, MEDIUM_FONT, NORMAL_FONT, STATUS_FONT, BUTTON_FONT
        LARGE_FONT = ("NanumGothic", self.large_font_size, "bold")
        MEDIUM_FONT = ("NanumGothic", self.medium_font_size)
        NORMAL_FONT = ("NanumGothic", self.normal_font_size)
        STATUS_FONT = ("NanumGothic", self.status_font_size, "bold")
        BUTTON_FONT = ("NanumGothic", self.button_font_size, "bold")

        print(f"[디스플레이] 폰트 크기 자동 조정: "
              f"대형={self.large_font_size}pt, "
              f"중간={self.medium_font_size}pt, "
              f"버튼={self.button_font_size}pt")

    def create_gui(self):
        """Create the main GUI layout - AUTO-ADAPTIVE for any screen"""
        # Calculate adaptive dimensions
        header_height = int(140 * self.scale_factor)  # Taller for more info
        padding = int(10 * self.scale_factor)

        # Top header - Adaptive height with more info
        header_frame = tk.Frame(self.root, bg=COLOR_PANEL, height=header_height, bd=1, relief=tk.FLAT)
        header_frame.pack(fill=tk.X, padx=0, pady=0)
        header_frame.pack_propagate(False)

        # Header layout: 3 columns
        header_frame.columnconfigure(0, weight=1)  # Left: System status
        header_frame.columnconfigure(1, weight=1)  # Center: Title + Time
        header_frame.columnconfigure(2, weight=1)  # Right: Vibration button

        # LEFT: System status + Date (compact)
        left_frame = tk.Frame(header_frame, bg=COLOR_PANEL)
        left_frame.grid(row=0, column=0, sticky="w", padx=8, pady=8)

        self.system_status_label = tk.Label(left_frame, text="시스템 정상",
                                           font=NORMAL_FONT, bg=COLOR_PANEL, fg=COLOR_OK)
        self.system_status_label.pack(anchor="w")

        self.date_label = tk.Label(left_frame, text="----/--/--",
                                   font=("NanumGothic", int(self.normal_font_size * 0.9)),
                                   bg=COLOR_PANEL, fg=COLOR_TEXT_LIGHT)
        self.date_label.pack(anchor="w")

        # CENTER: Title + Time (compact)
        center_frame = tk.Frame(header_frame, bg=COLOR_PANEL)
        center_frame.grid(row=0, column=1, sticky="n", pady=5)

        tk.Label(center_frame, text="현대자동차 울산점",
                font=("NanumGothic", int(self.large_font_size * 0.85), "bold"),
                bg=COLOR_PANEL, fg=COLOR_ACCENT).pack()

        self.time_label = tk.Label(center_frame, text="--:--:--",
                                   font=("NanumGothic", int(22 * self.scale_factor), "bold"),
                                   bg=COLOR_PANEL, fg=COLOR_INFO)
        self.time_label.pack()

        # RIGHT: Vibration check button + Settings button (compact)
        right_frame = tk.Frame(header_frame, bg=COLOR_PANEL)
        right_frame.grid(row=0, column=2, sticky="e", padx=8, pady=8)

        # PC Status button
        tk.Button(right_frame, text="PC 상태",
                 font=("NanumGothic", int(self.button_font_size * 0.85), "bold"),
                 command=self.open_pc_status, bg="#00897B", fg="white",
                 relief=tk.FLAT, bd=0, activebackground="#00796B",
                 padx=12, pady=8).pack(side=tk.LEFT, padx=3)

        # Vibration check button
        tk.Button(right_frame, text="진동 체크",
                 font=("NanumGothic", int(self.button_font_size * 0.85), "bold"),
                 command=self.open_vibration_check, bg=COLOR_INFO, fg="white",
                 relief=tk.FLAT, bd=0, activebackground=COLOR_BUTTON_HOVER,
                 padx=12, pady=8).pack(side=tk.LEFT, padx=3)

        # Settings button (moved from bottom)
        self.settings_btn = tk.Button(right_frame, text="설정",
                 font=("NanumGothic", int(self.button_font_size * 0.85), "bold"),
                 command=self.handle_settings_tap, bg=COLOR_BUTTON, fg="white",
                 relief=tk.FLAT, bd=0, activebackground=COLOR_BUTTON_HOVER,
                 padx=12, pady=8)
        self.settings_btn.pack(side=tk.LEFT, padx=3)

        # Main content area - ADAPTIVE STACK
        self.content_frame = tk.Frame(self.root, bg=COLOR_BG)
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=padding, pady=int(padding/2))

        # Configure rows/columns for vertical stacking
        self.content_frame.rowconfigure(0, weight=1)  # Auto panel
        self.content_frame.rowconfigure(1, weight=1)  # Stir-fry panels row
        self.content_frame.rowconfigure(2, weight=1)  # Dev panel
        self.content_frame.columnconfigure(0, weight=1)  # Left column
        self.content_frame.columnconfigure(1, weight=1)  # Right column

        # Panel 1: Auto-start/down (TOP - spans both columns)
        self.create_auto_panel(self.content_frame)

        # Panel 2 & 3: Stir-fry monitoring LEFT and RIGHT (MIDDLE)
        self.create_stirfry_left_panel(self.content_frame)
        self.create_stirfry_right_panel(self.content_frame)

        # Panel 4: Developer mode (BOTTOM - hidden by default, spans both columns)
        self.dev_panel = None
        self.create_dev_panel(self.content_frame)

        # Hidden shutdown button (shown after 5 taps on Settings button in header)
        # Note: Settings button is now in the header (top right)
        self.shutdown_btn = tk.Button(self.root, text="종료", font=BUTTON_FONT,
                 command=self.confirm_shutdown, bg=COLOR_ERROR, fg="white",
                 relief=tk.FLAT, bd=0, activebackground="#C62828")
        # Don't pack it - keep it hidden until 5 taps on Settings

    def create_auto_panel(self, parent):
        """Panel 1: Auto-start/down system - TOP with HORIZONTAL status (spans both columns)"""
        pad = int(10 * self.scale_factor)
        panel = tk.LabelFrame(parent, text="자동 ON/OFF (사람 감시)", font=LARGE_FONT,
                             bg=COLOR_PANEL, fg=COLOR_ACCENT, bd=2, relief=tk.FLAT,
                             highlightbackground=COLOR_PANEL_BORDER, highlightthickness=1)
        panel.grid(row=0, column=0, columnspan=2, padx=pad, pady=int(pad/2), sticky="nsew")

        # Status indicators in HORIZONTAL layout (space efficient)
        status_container = tk.Frame(panel, bg=COLOR_PANEL)
        status_container.pack(pady=10, padx=10, fill=tk.X)

        # Grid layout: 2 rows x 2 columns
        status_container.columnconfigure(0, weight=1)
        status_container.columnconfigure(1, weight=1)

        self.auto_mode_label = tk.Label(status_container, text="모드: 주간", font=MEDIUM_FONT,
                                       bg=COLOR_PANEL, fg=COLOR_INFO, anchor="w")
        self.auto_mode_label.grid(row=0, column=0, sticky="w", padx=5, pady=2)

        self.auto_detection_label = tk.Label(status_container, text="감지: 대기 중", font=MEDIUM_FONT,
                                            bg=COLOR_PANEL, fg=COLOR_TEXT, anchor="w")
        self.auto_detection_label.grid(row=0, column=1, sticky="w", padx=5, pady=2)

        self.auto_status_label = tk.Label(status_container, text="상태: 초기화 중...", font=MEDIUM_FONT,
                                         bg=COLOR_PANEL, fg=COLOR_INFO, anchor="w")
        self.auto_status_label.grid(row=1, column=0, sticky="w", padx=5, pady=2)

        self.auto_mqtt_label = tk.Label(status_container, text="MQTT: 연결 대기", font=MEDIUM_FONT,
                                       bg=COLOR_PANEL, fg=COLOR_WARNING, anchor="w")
        self.auto_mqtt_label.grid(row=1, column=1, sticky="w", padx=5, pady=2)

        # Camera preview area (more space now)
        self.auto_preview_label = tk.Label(panel, text="[카메라 로딩 중...]",
                                          bg="black", fg="white", font=NORMAL_FONT)
        self.auto_preview_label.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

    def create_stirfry_left_panel(self, parent):
        """Panel 2: Stir-fry monitoring LEFT - MIDDLE LEFT"""
        pad = int(10 * self.scale_factor)
        panel = tk.LabelFrame(parent, text="볶음 모니터링 (왼쪽)", font=LARGE_FONT,
                             bg=COLOR_PANEL, fg=COLOR_ACCENT, bd=2, relief=tk.FLAT,
                             highlightbackground=COLOR_PANEL_BORDER, highlightthickness=1)
        panel.grid(row=1, column=0, padx=pad, pady=int(pad/2), sticky="nsew")

        # Camera preview area
        self.stirfry_left_preview_label = tk.Label(panel, text="[카메라 로딩 중...]",
                                                   bg="black", fg="white", font=NORMAL_FONT)
        self.stirfry_left_preview_label.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        # Status info
        info_frame = tk.Frame(panel, bg=COLOR_PANEL)
        info_frame.pack(pady=10)

        self.stirfry_left_count_label = tk.Label(info_frame, text="저장: 0장",
                                                 font=MEDIUM_FONT, bg=COLOR_PANEL, fg=COLOR_TEXT)
        self.stirfry_left_count_label.pack(pady=5)

    def create_stirfry_right_panel(self, parent):
        """Panel 3: Stir-fry monitoring RIGHT - MIDDLE RIGHT"""
        pad = int(10 * self.scale_factor)
        panel = tk.LabelFrame(parent, text="볶음 모니터링 (오른쪽)", font=LARGE_FONT,
                             bg=COLOR_PANEL, fg=COLOR_ACCENT, bd=2, relief=tk.FLAT,
                             highlightbackground=COLOR_PANEL_BORDER, highlightthickness=1)
        panel.grid(row=1, column=1, padx=pad, pady=int(pad/2), sticky="nsew")

        # Camera preview area
        self.stirfry_right_preview_label = tk.Label(panel, text="[카메라 로딩 중...]",
                                                    bg="black", fg="white", font=NORMAL_FONT)
        self.stirfry_right_preview_label.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        # Status info
        info_frame = tk.Frame(panel, bg=COLOR_PANEL)
        info_frame.pack(pady=10)

        self.stirfry_right_count_label = tk.Label(info_frame, text="저장: 0장",
                                                  font=MEDIUM_FONT, bg=COLOR_PANEL, fg=COLOR_TEXT)
        self.stirfry_right_count_label.pack(pady=5)

        # Control buttons - Shared between both cameras (place in right panel)
        btn_frame = tk.Frame(panel, bg=COLOR_PANEL)
        btn_frame.pack(pady=15, fill=tk.X, padx=20)

        self.stirfry_start_btn = tk.Button(btn_frame, text="시작", font=BUTTON_FONT,
                                          command=self.start_stirfry_recording,
                                          bg=COLOR_OK, fg="white", relief=tk.FLAT, bd=0,
                                          activebackground="#00B248", height=2)
        self.stirfry_start_btn.pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)

        self.stirfry_stop_btn = tk.Button(btn_frame, text="중지", font=BUTTON_FONT,
                                         command=self.stop_stirfry_recording,
                                         bg=COLOR_ERROR, fg="white", state=tk.DISABLED,
                                         relief=tk.FLAT, bd=0, activebackground="#C62828", height=2)
        self.stirfry_stop_btn.pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)

    def create_dev_panel(self, parent):
        """Panel 4: Developer mode (debugging panel) - BOTTOM with scrolling (spans both columns)"""
        pad = int(10 * self.scale_factor)
        panel = tk.LabelFrame(parent, text="개발자 모드", font=LARGE_FONT,
                             bg=COLOR_PANEL, fg=COLOR_WARNING, bd=2, relief=tk.FLAT,
                             highlightbackground=COLOR_PANEL_BORDER, highlightthickness=1)

        # Create canvas and scrollbar for scrollable content
        canvas = tk.Canvas(panel, bg=COLOR_PANEL, highlightthickness=0)
        scrollbar = tk.Scrollbar(panel, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=COLOR_PANEL)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Add all content to scrollable_frame instead of panel
        # Title
        tk.Label(scrollable_frame, text="야간 모션 스냅샷 디버그", font=MEDIUM_FONT,
                bg=COLOR_PANEL, fg=COLOR_TEXT).pack(pady=10)

        # Snapshot stats
        stats_frame = tk.Frame(scrollable_frame, bg=COLOR_PANEL)
        stats_frame.pack(pady=10, fill=tk.X, padx=20)

        self.dev_snapshot_count_label = tk.Label(stats_frame, text="스냅샷: 0장",
                                                 font=MEDIUM_FONT, bg=COLOR_PANEL, fg=COLOR_INFO)
        self.dev_snapshot_count_label.pack(pady=5)

        self.dev_last_snapshot_label = tk.Label(stats_frame, text="마지막 저장: -",
                                                font=NORMAL_FONT, bg=COLOR_PANEL, fg=COLOR_TEXT)
        self.dev_last_snapshot_label.pack(pady=5)

        # Last snapshot preview - smaller to fit better
        self.dev_snapshot_preview = tk.Label(scrollable_frame, text="[스냅샷 미리보기]",
                                            bg="black", fg="white", font=NORMAL_FONT)
        self.dev_snapshot_preview.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        # Motion detection info
        self.dev_motion_label = tk.Label(scrollable_frame, text="모션 감지: 대기 중",
                                        font=NORMAL_FONT, bg=COLOR_PANEL, fg=COLOR_TEXT)
        self.dev_motion_label.pack(pady=5)

        # Test button - skip to snapshot mode
        tk.Button(scrollable_frame, text="스냅샷 모드 즉시 시작", font=BUTTON_FONT,
                 command=self.force_snapshot_mode, bg=COLOR_ERROR, fg="white",
                 relief=tk.FLAT, bd=0, activebackground="#C62828").pack(pady=15, padx=20, fill=tk.X)

        # Enable mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)  # Windows/MacOS
        canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))  # Linux scroll up
        canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))   # Linux scroll down

        # Store panel reference but don't grid it yet
        self.dev_panel = panel

    def toggle_developer_mode(self):
        """Toggle developer mode panel - Click same button to exit"""
        self.developer_mode = not self.developer_mode

        pad = int(10 * self.scale_factor)
        if self.developer_mode:
            # Show developer panel (spans both columns)
            self.dev_panel.grid(row=2, column=0, columnspan=2, padx=pad, pady=int(pad/2), sticky="nsew")
            self.dev_mode_btn.config(
                bg=COLOR_WARNING,
                text="개발자 종료",
                fg="white",
                activebackground="#E65100"  # Darker orange on hover
            )
            print("[개발자] 개발자 모드 활성화 (다시 클릭하여 종료)")
        else:
            # Hide developer panel
            self.dev_panel.grid_forget()
            self.dev_mode_btn.config(
                bg="#607D8B",
                text="개발자 모드",
                fg="white",
                activebackground="#546E7A"  # Darker gray on hover
            )
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
    def build_gui_async(self):
        """Build the actual GUI after mainloop has started"""
        print("[GUI] mainloop 시작됨! 실제 GUI 생성 중...")

        # Update loading message
        self.loading_label.config(text="화면 설정 중...")
        self.root.update()

        # Detect screen size now
        self.detect_screen_size()

        # Create OpenCV background subtractor
        self.loading_label.config(text="OpenCV 초기화 중...")
        self.root.update()
        self.kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        self.bg = cv2.createBackgroundSubtractorMOG2(
            history=MOG2_HISTORY, varThreshold=MOG2_VARTHRESH, detectShadows=True
        )

        # Remove loading screen
        self.loading_label.config(text="GUI 생성 중...")
        self.root.update()
        self.loading_label.pack_forget()

        # Create the actual complex GUI
        self.create_gui()
        print("[GUI] GUI 생성 완료!")

        # Force render
        self.root.update_idletasks()
        self.root.update()

        # Initialize MQTT (lightweight)
        self.init_mqtt()

        # Start clock
        self.update_clock()

        # Schedule heavy initialization (cameras + YOLO) for later
        print("[GUI] 1초 후 카메라/YOLO 초기화 시작...")
        self.root.after(1000, self.init_systems_async)

    def init_systems_async(self):
        """Initialize heavy systems (cameras + YOLO) in background thread"""
        print("[초기화] 백그라운드 초기화 시작...")

        # Update status to show loading
        self.auto_status_label.config(text="상태: 카메라 초기화 중...", fg=COLOR_INFO)

        # Run heavy initialization in background thread
        def _init_thread():
            try:
                print("[스레드] 카메라 초기화 중...")
                self.init_cameras()

                # Start background camera reader threads (non-blocking!)
                print("[스레드] 카메라 읽기 스레드 시작...")
                self.start_camera_reader_threads()

                # Update GUI from thread (schedule on main thread)
                self.root.after(0, lambda: self.auto_status_label.config(
                    text="상태: YOLO 로딩 중...", fg=COLOR_INFO))

                print("[스레드] YOLO 초기화 중...")
                self.init_yolo()

                # Start update loops on main thread (they now just display latest frames)
                print("[스레드] 업데이트 루프 시작...")
                self.root.after(0, self.update_auto_system)
                self.root.after(0, self.update_stirfry_left_camera)
                self.root.after(0, self.update_stirfry_right_camera)

                # Update final status on main thread
                self.root.after(0, lambda: self.auto_status_label.config(
                    text="상태: 준비 완료", fg=COLOR_OK))

                print("[스레드] 모든 시스템 초기화 완료!")

            except Exception as e:
                print(f"[오류] 초기화 실패: {e}")
                self.root.after(0, lambda: self.auto_status_label.config(
                    text=f"상태: 초기화 오류", fg=COLOR_ERROR))

        # Start background thread
        init_thread = threading.Thread(target=_init_thread, daemon=True)
        init_thread.start()
        print("[초기화] 백그라운드 스레드 시작됨")

    def start_camera_reader_threads(self):
        """Start background threads to continuously read camera frames"""
        def read_auto_camera():
            # Warmup: Skip first 30 frames (reduced for faster startup)
            print("[카메라스레드] 자동 카메라 워밍업 시작...")
            warmup_count = 0
            fail_count = 0
            max_fails = 50  # Prevent infinite loop

            while warmup_count < 30 and fail_count < max_fails and self.running:
                if self.auto_cap and self.auto_cap.isOpened():
                    ret, frame = self.auto_cap.read()
                    if ret and frame is not None:
                        warmup_count += 1
                        # No progress logs - too noisy
                    else:
                        fail_count += 1
                else:
                    print("[카메라스레드] 자동 카메라가 열려있지 않음, 대기 중...")
                    time.sleep(0.1)
                    fail_count += 1
                time.sleep(0.01)  # Slightly longer delay during warmup

            if fail_count >= max_fails:
                print(f"[카메라스레드] 자동 카메라 워밍업 실패 (연속 실패: {fail_count})")
                return

            print(f"[카메라스레드] 자동 카메라 워밍업 완료 ({warmup_count}프레임)")

            # Main loop
            frame_count = 0
            consecutive_fails = 0
            while self.running:
                if self.auto_cap and self.auto_cap.isOpened():
                    ret, frame = self.auto_cap.read()
                    if ret and frame is not None and frame.size > 0:
                        # Check if frame is valid (not all zeros/green)
                        if frame.mean() > 1.0:  # Valid frame should have non-zero mean
                            with self.frame_locks['auto']:
                                self.latest_auto_frame = frame.copy()
                            frame_count += 1
                            consecutive_fails = 0
                            if frame_count == 1:
                                print(f"[카메라스레드] 자동 카메라 첫 유효 프레임 획득! 크기: {frame.shape}")
                            # No periodic logs - too noisy
                        else:
                            consecutive_fails += 1
                            if consecutive_fails % 50 == 0:
                                print(f"[카메라스레드] 자동 카메라 빈 프레임 연속 수신: {consecutive_fails}")
                    else:
                        consecutive_fails += 1
                else:
                    print("[카메라스레드] 자동 카메라 연결 끊김")
                    break
                time.sleep(0.001)  # Small delay to prevent CPU spinning

        def read_left_camera():
            # Warmup: Skip first 30 frames (reduced for faster startup)
            print("[카메라스레드] 왼쪽 카메라 워밍업 시작...")
            warmup_count = 0
            fail_count = 0
            max_fails = 50

            while warmup_count < 30 and fail_count < max_fails and self.running:
                if self.stirfry_left_cap and self.stirfry_left_cap.isOpened():
                    ret, frame = self.stirfry_left_cap.read()
                    if ret and frame is not None:
                        warmup_count += 1
                        # No progress logs - too noisy
                    else:
                        fail_count += 1
                else:
                    print("[카메라스레드] 왼쪽 카메라가 열려있지 않음, 대기 중...")
                    time.sleep(0.1)
                    fail_count += 1
                time.sleep(0.01)

            if fail_count >= max_fails:
                print(f"[카메라스레드] 왼쪽 카메라 워밍업 실패 (연속 실패: {fail_count})")
                return

            print(f"[카메라스레드] 왼쪽 카메라 워밍업 완료 ({warmup_count}프레임)")

            # Main loop
            frame_count = 0
            consecutive_fails = 0
            while self.running:
                if self.stirfry_left_cap and self.stirfry_left_cap.isOpened():
                    ret, frame = self.stirfry_left_cap.read()
                    if ret and frame is not None and frame.size > 0:
                        if frame.mean() > 1.0:
                            with self.frame_locks['left']:
                                self.latest_left_frame = frame.copy()
                            frame_count += 1
                            consecutive_fails = 0
                            if frame_count == 1:
                                print(f"[카메라스레드] 왼쪽 카메라 첫 유효 프레임 획득! 크기: {frame.shape}")
                            # No periodic logs - too noisy
                        else:
                            consecutive_fails += 1
                            if consecutive_fails % 50 == 0:
                                print(f"[카메라스레드] 왼쪽 카메라 빈 프레임 연속 수신: {consecutive_fails}")
                    else:
                        consecutive_fails += 1
                else:
                    print("[카메라스레드] 왼쪽 카메라 연결 끊김")
                    break
                time.sleep(0.001)

        def read_right_camera():
            # Warmup: Skip first 120 frames for GMSL cameras (1920x1536 needs more warmup)
            print("[카메라스레드] 오른쪽 카메라 워밍업 시작...")
            warmup_count = 0
            fail_count = 0
            max_fails = 150

            while warmup_count < 120 and fail_count < max_fails and self.running:
                if self.stirfry_right_cap and self.stirfry_right_cap.isOpened():
                    ret, frame = self.stirfry_right_cap.read()
                    if ret and frame is not None:
                        warmup_count += 1
                        if warmup_count % 20 == 0:
                            print(f"[카메라스레드] 오른쪽 카메라 워밍업 중... {warmup_count}/120")
                    else:
                        fail_count += 1
                else:
                    print("[카메라스레드] 오른쪽 카메라가 열려있지 않음, 대기 중...")
                    time.sleep(0.1)
                    fail_count += 1
                time.sleep(0.01)

            if fail_count >= max_fails:
                print(f"[카메라스레드] 오른쪽 카메라 워밍업 실패 (연속 실패: {fail_count})")
                return

            print(f"[카메라스레드] 오른쪽 카메라 워밍업 완료 ({warmup_count}프레임)")

            # Main loop
            frame_count = 0
            consecutive_fails = 0
            while self.running:
                if self.stirfry_right_cap and self.stirfry_right_cap.isOpened():
                    ret, frame = self.stirfry_right_cap.read()
                    if ret and frame is not None and frame.size > 0:
                        if frame.mean() > 1.0:
                            with self.frame_locks['right']:
                                self.latest_right_frame = frame.copy()
                            frame_count += 1
                            consecutive_fails = 0
                            if frame_count == 1:
                                print(f"[카메라스레드] 오른쪽 카메라 첫 유효 프레임 획득! 크기: {frame.shape}")
                            elif frame_count % 100 == 0:
                                print(f"[카메라스레드] 오른쪽 카메라 프레임 {frame_count}개 처리 완료")
                        else:
                            consecutive_fails += 1
                            if consecutive_fails % 50 == 0:
                                print(f"[카메라스레드] 오른쪽 카메라 빈 프레임 연속 수신: {consecutive_fails}")
                    else:
                        consecutive_fails += 1
                else:
                    print("[카메라스레드] 오른쪽 카메라 연결 끊김")
                    break
                time.sleep(0.001)

        # Start daemon threads (will auto-exit when program exits)
        threading.Thread(target=read_auto_camera, daemon=True).start()
        threading.Thread(target=read_left_camera, daemon=True).start()
        threading.Thread(target=read_right_camera, daemon=True).start()
        print("[카메라스레드] 3개 카메라 읽기 스레드 시작됨!")

    def init_mqtt(self):
        """Initialize MQTT connection with new centralized client"""
        if not MQTT_ENABLED:
            print("[MQTT] 설정에서 비활성화됨")
            self.auto_mqtt_label.config(text="MQTT: 비활성화", fg=COLOR_TEXT)
            return

        try:
            print(f"[MQTT] {MQTT_BROKER}:{MQTT_PORT}에 연결 중...")

            # Create MQTT client with system info
            self.mqtt_client = MQTTClient(
                broker=MQTT_BROKER,
                port=MQTT_PORT,
                client_id=MQTT_CLIENT_ID,
                topic_prefix="frying_ai/jetson1",
                system_info=self.system_info.to_dict()
            )

            # Connect to broker
            if self.mqtt_client.connect(blocking=True, timeout=5.0):
                print("[MQTT] 연결 성공")
                self.auto_mqtt_label.config(text="MQTT: 연결됨", fg=COLOR_OK)
            else:
                print("[MQTT] 연결 실패")
                self.auto_mqtt_label.config(text="MQTT: 오류", fg=COLOR_ERROR)

        except Exception as e:
            print(f"[MQTT] 초기화 실패: {e}")
            self.auto_mqtt_label.config(text=f"MQTT: 오류", fg=COLOR_ERROR)

    def init_cameras(self):
        """Initialize both cameras with universal camera abstraction"""
        # Camera 1: Auto-start/down system
        try:
            # Create camera configuration
            auto_config = CameraConfig(
                camera_type=CameraType.GMSL if CAMERA_TYPE.lower() == 'gmsl' else CameraType.USB,
                camera_index=CAMERA_INDEX,
                resolution=(CAMERA_RESOLUTION['width'], CAMERA_RESOLUTION['height']),
                fps=CAMERA_FPS,
                gmsl_mode=GMSL_MODE,
                gmsl_resolution_mode=GMSL_RESOLUTION_MODE,
                driver_dir=GMSL_DRIVER_DIR
            )

            # Create universal camera
            self.auto_cap_wrapper = UniversalCamera(auto_config)
            if self.auto_cap_wrapper.initialize():
                # Get the underlying cv2.VideoCapture for compatibility
                self.auto_cap = self.auto_cap_wrapper.cap
                print(f"[카메라] 자동 ON/OFF 카메라 초기화 완료: {CAMERA_TYPE.upper()} #{CAMERA_INDEX}")
            else:
                print(f"[오류] 자동 ON/OFF 카메라 초기화 실패")
                self.auto_cap = None
        except Exception as e:
            print(f"[오류] 자동 카메라 초기화 실패: {e}")
            self.auto_cap = None

        # Camera 2: Stir-fry monitoring LEFT
        try:
            # Create camera configuration - use actual 1920x1536 resolution
            stirfry_left_config = CameraConfig(
                camera_type=CameraType.GMSL if STIRFRY_LEFT_CAMERA_TYPE.lower() == 'gmsl' else CameraType.USB,
                camera_index=STIRFRY_LEFT_CAMERA_INDEX,
                resolution=(1920, 1536),  # Full resolution for stir-fry monitoring
                fps=CAMERA_FPS,
                gmsl_mode=STIRFRY_LEFT_GMSL_MODE,
                gmsl_resolution_mode=STIRFRY_LEFT_GMSL_RESOLUTION_MODE,
                driver_dir=GMSL_DRIVER_DIR
            )

            # Create universal camera
            self.stirfry_left_cap_wrapper = UniversalCamera(stirfry_left_config)
            if self.stirfry_left_cap_wrapper.initialize():
                # Get the underlying cv2.VideoCapture for compatibility
                self.stirfry_left_cap = self.stirfry_left_cap_wrapper.cap
                print(f"[카메라] 볶음 모니터링 왼쪽 카메라 초기화 완료: {STIRFRY_LEFT_CAMERA_TYPE.upper()} #{STIRFRY_LEFT_CAMERA_INDEX} @ 1920x1536")
            else:
                print(f"[오류] 볶음 모니터링 왼쪽 카메라 초기화 실패")
                self.stirfry_left_cap = None
        except Exception as e:
            print(f"[오류] 볶음 왼쪽 카메라 초기화 실패: {e}")
            import traceback
            traceback.print_exc()
            self.stirfry_left_cap = None

        # Camera 3: Stir-fry monitoring RIGHT
        try:
            # Create camera configuration - use actual 1920x1536 resolution
            stirfry_right_config = CameraConfig(
                camera_type=CameraType.GMSL if STIRFRY_RIGHT_CAMERA_TYPE.lower() == 'gmsl' else CameraType.USB,
                camera_index=STIRFRY_RIGHT_CAMERA_INDEX,
                resolution=(1920, 1536),  # Full resolution for stir-fry monitoring
                fps=CAMERA_FPS,
                gmsl_mode=STIRFRY_RIGHT_GMSL_MODE,
                gmsl_resolution_mode=STIRFRY_RIGHT_GMSL_RESOLUTION_MODE,
                driver_dir=GMSL_DRIVER_DIR
            )

            # Create universal camera
            self.stirfry_right_cap_wrapper = UniversalCamera(stirfry_right_config)
            if self.stirfry_right_cap_wrapper.initialize():
                # Get the underlying cv2.VideoCapture for compatibility
                self.stirfry_right_cap = self.stirfry_right_cap_wrapper.cap
                print(f"[카메라] 볶음 모니터링 오른쪽 카메라 초기화 완료: {STIRFRY_RIGHT_CAMERA_TYPE.upper()} #{STIRFRY_RIGHT_CAMERA_INDEX} @ 1920x1536")
            else:
                print(f"[오류] 볶음 모니터링 오른쪽 카메라 초기화 실패")
                self.stirfry_right_cap = None
        except Exception as e:
            print(f"[오류] 볶음 오른쪽 카메라 초기화 실패: {e}")
            import traceback
            traceback.print_exc()
            self.stirfry_right_cap = None

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
        """Update time and date display - smooth updates"""
        if not self.running:
            return

        now = datetime.now()

        # Only update if second has changed (reduce flickering)
        current_second = now.second
        if not hasattr(self, '_last_second') or self._last_second != current_second:
            self._last_second = current_second
            self.time_label.config(text=now.strftime("%H:%M:%S"))

            # Only update date once per minute (at second 0)
            if current_second == 0 or not hasattr(self, '_date_set'):
                self.date_label.config(text=now.strftime("%Y년 %m월 %d일"))
                self._date_set = True

        # Update every 200ms for smooth second transitions
        self.root.after(200, self.update_clock)

    def update_auto_system(self):
        """Update auto-start/down system (YOLO + MQTT)"""
        if not self.running:
            return

        if self.auto_cap is None or not self.auto_cap.isOpened() or self.yolo_model is None:
            self.root.after(100, self.update_auto_system)
            return

        # Get latest frame from background thread (NON-BLOCKING!)
        with self.frame_locks['auto']:
            frame = self.latest_auto_frame

        if frame is None:
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

        self.root.after(33, self.update_auto_system)  # ~30 FPS (less CPU usage)

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
            # Update detection state and time (for auto-hide feature)
            self.person_detected = True
            self.last_person_detected_time = now

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
            # No person detected
            self.person_detected = False
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
                # Update detection state and time (for auto-hide feature)
                self.person_detected = True
                self.last_person_detected_time = now

                # Reset deadline
                self.night_no_person_deadline = now + timedelta(minutes=NIGHT_CHECK_MINUTES)
                self.auto_detection_label.config(text="감지: 사람 있음 (리셋)", fg=COLOR_WARNING)
            else:
                # No person detected
                self.person_detected = False

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
                    # Update motion detection state
                    self.motion_detected = True

                    now_tick = time.monotonic()
                    can_save = (self.last_snapshot_tick is None) or ((now_tick - self.last_snapshot_tick) >= SAVE_COOLDOWN_SEC)
                    if can_save:
                        self.save_snapshot(frame, now)
                        self.last_snapshot_tick = now_tick
                        self.auto_detection_label.config(text="감지: 모션 저장됨", fg=COLOR_OK)
                else:
                    # No motion detected
                    self.motion_detected = False
                    self.auto_detection_label.config(text="감지: 모션 대기", fg=COLOR_TEXT)

    def update_stirfry_left_camera(self):
        """Update stir-fry LEFT camera preview"""
        if not self.running:
            return

        if self.stirfry_left_cap is None or not self.stirfry_left_cap.isOpened():
            self.root.after(100, self.update_stirfry_left_camera)
            return

        # Get latest frame from background thread (NON-BLOCKING!)
        with self.frame_locks['left']:
            frame = self.latest_left_frame

        if frame is None:
            self.root.after(100, self.update_stirfry_left_camera)
            return

        # If recording, save frames
        if self.stirfry_recording:
            self.save_stirfry_left_frame(frame)

        # Update preview
        self.update_stirfry_left_preview(frame)

        self.root.after(33, self.update_stirfry_left_camera)  # ~30 FPS (less CPU usage)

    def update_stirfry_right_camera(self):
        """Update stir-fry RIGHT camera preview"""
        if not self.running:
            return

        if self.stirfry_right_cap is None or not self.stirfry_right_cap.isOpened():
            self.root.after(100, self.update_stirfry_right_camera)
            return

        # Get latest frame from background thread (NON-BLOCKING!)
        with self.frame_locks['right']:
            frame = self.latest_right_frame

        if frame is None:
            self.root.after(100, self.update_stirfry_right_camera)
            return

        # If recording, save frames
        if self.stirfry_recording:
            self.save_stirfry_right_frame(frame)

        # Update preview
        self.update_stirfry_right_preview(frame)

        self.root.after(33, self.update_stirfry_right_camera)  # ~30 FPS (less CPU usage)

    def update_auto_preview(self, frame):
        """Update auto system preview with auto-zoom and auto-hide"""
        try:
            # Option 3: Check if preview should be shown
            should_show = self.should_show_preview("auto")

            if not should_show:
                # Hide preview - show message instead
                if self.auto_preview_visible:
                    self.auto_preview_label.configure(image="", text="[대기 중 - 화면 절전]")
                    self.auto_preview_visible = False
                    print("[화면절전] 자동 카메라 화면 숨김 (캡처는 계속됨)")
                return
            else:
                # Show preview
                if not self.auto_preview_visible:
                    self.auto_preview_visible = True
                    print("[화면복구] 자동 카메라 화면 복구")

            # FIXED SIZE: Resize to 640x512 to maintain 5:4 aspect ratio (1920x1536)
            # Use GPU acceleration if available
            if USE_CUDA:
                try:
                    gpu_frame = cv2.cuda_GpuMat()
                    gpu_frame.upload(frame)
                    gpu_resized = cv2.cuda.resize(gpu_frame, (640, 512))
                    preview = gpu_resized.download()
                except:
                    # Fallback to CPU if GPU fails
                    preview = cv2.resize(frame, (640, 512), interpolation=cv2.INTER_LINEAR)
            else:
                preview = cv2.resize(frame, (640, 512), interpolation=cv2.INTER_LINEAR)

            preview_rgb = cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(preview_rgb)
            imgtk = ImageTk.PhotoImage(image=img)
            self.auto_preview_label.imgtk = imgtk
            self.auto_preview_label.configure(image=imgtk, text="")
        except Exception as e:
            pass

    def update_stirfry_left_preview(self, frame):
        """Update stir-fry LEFT camera preview with auto-zoom and auto-hide"""
        try:
            # Option 3: Check if preview should be shown (only when recording)
            should_show = self.should_show_preview("stirfry_left")

            if not should_show:
                # Hide preview - show message instead
                if self.stirfry_left_preview_visible:
                    self.stirfry_left_preview_label.configure(image="", text="[녹화 대기 중]")
                    self.stirfry_left_preview_visible = False
                return
            else:
                # Show preview
                if not self.stirfry_left_preview_visible:
                    self.stirfry_left_preview_visible = True

            # FIXED SIZE: Resize to 640x512 to maintain 5:4 aspect ratio (1920x1536)
            # Use GPU acceleration if available
            if USE_CUDA:
                try:
                    gpu_frame = cv2.cuda_GpuMat()
                    gpu_frame.upload(frame)
                    gpu_resized = cv2.cuda.resize(gpu_frame, (640, 512))
                    preview = gpu_resized.download()
                except:
                    # Fallback to CPU if GPU fails
                    preview = cv2.resize(frame, (640, 512), interpolation=cv2.INTER_LINEAR)
            else:
                preview = cv2.resize(frame, (640, 512), interpolation=cv2.INTER_LINEAR)

            preview_rgb = cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(preview_rgb)
            imgtk = ImageTk.PhotoImage(image=img)
            self.stirfry_left_preview_label.imgtk = imgtk
            self.stirfry_left_preview_label.configure(image=imgtk, text="")
        except Exception as e:
            pass

    def update_stirfry_right_preview(self, frame):
        """Update stir-fry RIGHT camera preview with auto-zoom and auto-hide"""
        try:
            # Option 3: Check if preview should be shown (only when recording)
            should_show = self.should_show_preview("stirfry_right")

            if not should_show:
                # Hide preview - show message instead
                if self.stirfry_right_preview_visible:
                    self.stirfry_right_preview_label.configure(image="", text="[녹화 대기 중]")
                    self.stirfry_right_preview_visible = False
                return
            else:
                # Show preview
                if not self.stirfry_right_preview_visible:
                    self.stirfry_right_preview_visible = True

            # FIXED SIZE: Resize to 640x512 to maintain 5:4 aspect ratio (1920x1536)
            # Use GPU acceleration if available
            if USE_CUDA:
                try:
                    gpu_frame = cv2.cuda_GpuMat()
                    gpu_frame.upload(frame)
                    gpu_resized = cv2.cuda.resize(gpu_frame, (640, 512))
                    preview = gpu_resized.download()
                except:
                    # Fallback to CPU if GPU fails
                    preview = cv2.resize(frame, (640, 512), interpolation=cv2.INTER_LINEAR)
            else:
                preview = cv2.resize(frame, (640, 512), interpolation=cv2.INTER_LINEAR)

            preview_rgb = cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(preview_rgb)
            imgtk = ImageTk.PhotoImage(image=img)
            self.stirfry_right_preview_label.imgtk = imgtk
            self.stirfry_right_preview_label.configure(image=imgtk, text="")
        except Exception as e:
            pass

    # =========================
    # Helper Functions
    # =========================

    def should_show_preview(self, camera_type="auto"):
        """
        Option 3: Determine if camera preview should be shown
        Returns True if preview should be visible, False to hide
        """
        if camera_type == "auto":
            # Auto camera: hide after 30s of no person detection
            if self.last_person_detected_time is None:
                # First time, initialize to now to prevent immediate hiding
                from datetime import datetime
                self.last_person_detected_time = datetime.now()
                return True  # First time, always show

            from datetime import datetime
            elapsed = (datetime.now() - self.last_person_detected_time).total_seconds()
            return elapsed < self.preview_hide_delay

        elif camera_type in ["stirfry_left", "stirfry_right"]:
            # Stir-fry cameras: only show when recording
            return self.stirfry_recording

        return True

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
        """Publish message to MQTT broker with enhanced data"""
        if self.mqtt_client is not None and self.mqtt_client.is_connected():
            try:
                # Enhanced payload with system metrics
                payload = {
                    "command": message,  # "ON" or "OFF"
                    "source": "auto_start_system",
                    "person_detected": self.person_detected,
                    "motion_detected": self.motion_detected,
                    "system_metrics": self.system_info.get_dynamic_info()
                }

                # Publish to robot/control topic
                success = self.mqtt_client.publish(
                    topic_suffix="robot/control",
                    payload=payload,
                    qos=MQTT_QOS
                )

                if success:
                    print(f"[MQTT] 메시지 전송 완료: {message}")
                else:
                    print(f"[MQTT] 전송 실패")

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

    def save_stirfry_left_frame(self, frame):
        """Save stir-fry LEFT monitoring frame"""
        try:
            now = datetime.now()
            day_dir = now.strftime("%Y%m%d")
            ts_name = now.strftime("%H%M%S_%f")[:-3]  # Include milliseconds
            out_dir = os.path.join(STIRFRY_SAVE_DIR, "left", day_dir)
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, f"left_{ts_name}.jpg")
            cv2.imwrite(out_path, frame)
            self.stirfry_left_frame_count += 1
            self.stirfry_left_count_label.config(text=f"저장: {self.stirfry_left_frame_count}장")
        except Exception as e:
            print(f"[오류] 볶음 왼쪽 프레임 저장 실패: {e}")

    def save_stirfry_right_frame(self, frame):
        """Save stir-fry RIGHT monitoring frame"""
        try:
            now = datetime.now()
            day_dir = now.strftime("%Y%m%d")
            ts_name = now.strftime("%H%M%S_%f")[:-3]  # Include milliseconds
            out_dir = os.path.join(STIRFRY_SAVE_DIR, "right", day_dir)
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, f"right_{ts_name}.jpg")
            cv2.imwrite(out_path, frame)
            self.stirfry_right_frame_count += 1
            self.stirfry_right_count_label.config(text=f"저장: {self.stirfry_right_frame_count}장")
        except Exception as e:
            print(f"[오류] 볶음 오른쪽 프레임 저장 실패: {e}")

    # =========================
    # Control Functions
    # =========================
    def start_stirfry_recording(self):
        """Start stir-fry data recording for BOTH cameras"""
        self.stirfry_recording = True
        self.stirfry_left_frame_count = 0
        self.stirfry_right_frame_count = 0
        self.stirfry_start_btn.config(state=tk.DISABLED)
        self.stirfry_stop_btn.config(state=tk.NORMAL)
        print("[볶음] 녹화 시작 (왼쪽 + 오른쪽)")

    def stop_stirfry_recording(self):
        """Stop stir-fry data recording for BOTH cameras"""
        self.stirfry_recording = False
        self.stirfry_start_btn.config(state=tk.NORMAL)
        self.stirfry_stop_btn.config(state=tk.DISABLED)
        total_frames = self.stirfry_left_frame_count + self.stirfry_right_frame_count
        print(f"[볶음] 녹화 중지 - 왼쪽: {self.stirfry_left_frame_count}장, 오른쪽: {self.stirfry_right_frame_count}장")
        messagebox.showinfo("녹화 완료",
                          f"왼쪽: {self.stirfry_left_frame_count}장\n오른쪽: {self.stirfry_right_frame_count}장\n총: {total_frames}장")

    def open_pc_status(self):
        """Open PC/Jetson status monitoring dialog"""
        # Create popup window
        status_window = tk.Toplevel(self.root)
        status_window.title("PC 상태 모니터링")
        status_window.geometry("700x600")
        status_window.configure(bg=COLOR_BG)

        # Center the window
        status_window.transient(self.root)
        status_window.grab_set()

        # Title
        tk.Label(status_window, text="[ Jetson Orin Nano 상태 ]", font=LARGE_FONT,
                bg=COLOR_BG, fg=COLOR_TEXT).pack(pady=20)

        # Status info frame
        info_frame = tk.Frame(status_window, bg=COLOR_PANEL, bd=3, relief=tk.RAISED)
        info_frame.pack(pady=10, padx=40, fill=tk.BOTH, expand=True)

        # Get real-time system info
        try:
            import psutil

            # CPU Usage
            cpu_percent = psutil.cpu_percent(interval=0.5)
            cpu_color = COLOR_OK if cpu_percent < 70 else COLOR_WARNING if cpu_percent < 90 else COLOR_ERROR

            cpu_frame = tk.Frame(info_frame, bg=COLOR_PANEL)
            cpu_frame.pack(pady=10, padx=20, fill=tk.X)
            tk.Label(cpu_frame, text="CPU 사용률:", font=MEDIUM_FONT,
                    bg=COLOR_PANEL, fg=COLOR_TEXT, anchor="w").pack(side=tk.LEFT)
            tk.Label(cpu_frame, text=f"{cpu_percent:.1f}%", font=("NanumGothic", 22, "bold"),
                    bg=COLOR_PANEL, fg=cpu_color, anchor="e").pack(side=tk.RIGHT)

            # Memory Usage
            mem = psutil.virtual_memory()
            mem_percent = mem.percent
            mem_color = COLOR_OK if mem_percent < 70 else COLOR_WARNING if mem_percent < 90 else COLOR_ERROR

            mem_frame = tk.Frame(info_frame, bg=COLOR_PANEL)
            mem_frame.pack(pady=10, padx=20, fill=tk.X)
            tk.Label(mem_frame, text="메모리 사용률:", font=MEDIUM_FONT,
                    bg=COLOR_PANEL, fg=COLOR_TEXT, anchor="w").pack(side=tk.LEFT)
            tk.Label(mem_frame, text=f"{mem_percent:.1f}%", font=("NanumGothic", 22, "bold"),
                    bg=COLOR_PANEL, fg=mem_color, anchor="e").pack(side=tk.RIGHT)

            # Disk Usage
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            disk_color = COLOR_OK if disk_percent < 70 else COLOR_WARNING if disk_percent < 90 else COLOR_ERROR

            disk_frame = tk.Frame(info_frame, bg=COLOR_PANEL)
            disk_frame.pack(pady=10, padx=20, fill=tk.X)
            tk.Label(disk_frame, text="디스크 사용률:", font=MEDIUM_FONT,
                    bg=COLOR_PANEL, fg=COLOR_TEXT, anchor="w").pack(side=tk.LEFT)
            tk.Label(disk_frame, text=f"{disk_percent:.1f}%", font=("NanumGothic", 22, "bold"),
                    bg=COLOR_PANEL, fg=disk_color, anchor="e").pack(side=tk.RIGHT)

            # Temperature (Jetson specific)
            try:
                with open('/sys/devices/virtual/thermal/thermal_zone0/temp', 'r') as f:
                    temp_raw = int(f.read().strip())
                    temp_celsius = temp_raw / 1000.0
                    temp_color = COLOR_OK if temp_celsius < 70 else COLOR_WARNING if temp_celsius < 85 else COLOR_ERROR

                    temp_frame = tk.Frame(info_frame, bg=COLOR_PANEL)
                    temp_frame.pack(pady=10, padx=20, fill=tk.X)
                    tk.Label(temp_frame, text="CPU 온도:", font=MEDIUM_FONT,
                            bg=COLOR_PANEL, fg=COLOR_TEXT, anchor="w").pack(side=tk.LEFT)
                    tk.Label(temp_frame, text=f"{temp_celsius:.1f}°C", font=("NanumGothic", 22, "bold"),
                            bg=COLOR_PANEL, fg=temp_color, anchor="e").pack(side=tk.RIGHT)
            except:
                pass

            # System uptime
            uptime_seconds = int(psutil.boot_time())
            from datetime import datetime
            boot_time = datetime.fromtimestamp(uptime_seconds)
            uptime = datetime.now() - boot_time
            uptime_str = f"{uptime.days}일 {uptime.seconds // 3600}시간"

            uptime_frame = tk.Frame(info_frame, bg=COLOR_PANEL)
            uptime_frame.pack(pady=10, padx=20, fill=tk.X)
            tk.Label(uptime_frame, text="가동 시간:", font=MEDIUM_FONT,
                    bg=COLOR_PANEL, fg=COLOR_TEXT, anchor="w").pack(side=tk.LEFT)
            tk.Label(uptime_frame, text=uptime_str, font=MEDIUM_FONT,
                    bg=COLOR_PANEL, fg=COLOR_INFO, anchor="e").pack(side=tk.RIGHT)

        except Exception as e:
            tk.Label(info_frame, text=f"시스템 정보 읽기 실패: {e}", font=NORMAL_FONT,
                    bg=COLOR_PANEL, fg=COLOR_ERROR).pack(pady=20)

        # Close button
        tk.Button(status_window, text="[ 닫기 ]", font=MEDIUM_FONT,
                 command=status_window.destroy, width=15,
                 bg=COLOR_INFO, fg="white").pack(pady=20)

        print("[PC상태] PC 상태 창 열림")

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
                 bg=COLOR_INFO, fg="white").pack(pady=20)

        print("[진동] 진동 센서 체크 창 열림")

    def handle_settings_tap(self):
        """Handle settings button tap - 5 taps reveals shutdown"""
        import time
        current_time = time.time()

        # Reset counter if more than 2 seconds since last tap
        if current_time - self.last_tap_time > 2.0:
            self.shutdown_tap_count = 0

        self.last_tap_time = current_time
        self.shutdown_tap_count += 1

        print(f"[설정] 탭 횟수: {self.shutdown_tap_count}/5")

        if self.shutdown_tap_count >= 5:
            # Show shutdown button after 5 quick taps (replace settings button temporarily)
            print("[설정] 종료 버튼 활성화")
            self.settings_btn.pack_forget()  # Hide settings button
            self.shutdown_btn.pack(side=tk.LEFT, padx=3)  # Show in same location
            self.shutdown_tap_count = 0  # Reset
        elif self.shutdown_tap_count == 1:
            # Schedule settings dialog to open after a short delay
            # This allows subsequent taps to register first
            self.root.after(500, self.open_settings_delayed)

    def open_settings_delayed(self):
        """Open settings dialog after delay - only if still at 1 tap"""
        if self.shutdown_tap_count <= 1:
            messagebox.showinfo("설정", "설정 기능은 준비 중입니다.\nconfig.json 파일을 직접 수정하세요.")

    def open_settings(self):
        """Open settings dialog immediately (for direct calls)"""
        messagebox.showinfo("설정", "설정 기능은 준비 중입니다.\nconfig.json 파일을 직접 수정하세요.")

    def confirm_shutdown(self):
        """Confirm shutdown and close"""
        if messagebox.askokcancel("종료 확인", "정말 시스템을 종료하시겠습니까?"):
            self.on_closing()
        else:
            # Cancel - hide shutdown button, show settings again
            self.shutdown_btn.pack_forget()
            self.settings_btn.pack(side=tk.LEFT, padx=3)

    def on_closing(self):
        """Handle window close"""
        if messagebox.askokcancel("종료", "프로그램을 종료하시겠습니까?"):
            print("[종료] 시스템 종료 중...")
            self.running = False

            # Cleanup cameras
            if hasattr(self, 'auto_cap_wrapper') and self.auto_cap_wrapper is not None:
                self.auto_cap_wrapper.release()
            elif self.auto_cap is not None:
                self.auto_cap.release()

            if hasattr(self, 'stirfry_left_cap_wrapper') and self.stirfry_left_cap_wrapper is not None:
                self.stirfry_left_cap_wrapper.release()
            elif self.stirfry_left_cap is not None:
                self.stirfry_left_cap.release()

            if hasattr(self, 'stirfry_right_cap_wrapper') and self.stirfry_right_cap_wrapper is not None:
                self.stirfry_right_cap_wrapper.release()
            elif self.stirfry_right_cap is not None:
                self.stirfry_right_cap.release()

            # Cleanup MQTT
            if self.mqtt_client is not None:
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
