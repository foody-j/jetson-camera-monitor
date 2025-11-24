#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jetson Orin #2 - Integrated AI Monitoring System (LAB VERSION)
- Frying AI (튀김 AI - 2 cameras: video0 left, video1 right)
- Observe_add (Bucket detection: video2 left, video3 right)
- MQTT Communication
- PC Status Check
- Vibration Sensor Check
- Manual food type selection (LAB ONLY)
- Manual completion marking button (LAB ONLY)

Designed for laboratory pilot testing
"""

import tkinter as tk
from tkinter import ttk, messagebox
import cv2
from PIL import Image, ImageTk
from ultralytics import YOLO
from datetime import datetime
import time
import os
import json
import threading
import sys
import numpy as np
from collections import deque
from queue import Queue

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.communication.mqtt_client import MQTTClient
from src.core.system_info import SystemInfo

# Import GStreamer camera wrapper (optimized for UYVY format)
from gst_camera import GstCamera

# Import Frying AI segmenter
from frying_segmenter import FoodSegmenter

# Import psutil for system monitoring
try:
    import psutil
except ImportError:
    print("[경고] psutil 미설치 - PC 상태 기능 제한됨")
    psutil = None

# =========================
# Load Configuration
# =========================
def load_config(config_path="config_jetson2_lab.json"):
    """Load configuration from JSON file (LAB version)"""
    # Get script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_full_path = os.path.join(script_dir, config_path)

    with open(config_full_path, 'r', encoding='utf-8') as f:
        return json.load(f)

config = load_config()

# Frying AI Configuration (video0, video1)
FRYING_LEFT_CAMERA_INDEX = config.get('frying_left_camera_index', 0)
FRYING_RIGHT_CAMERA_INDEX = config.get('frying_right_camera_index', 1)
FRYING_SEG_MODEL = config.get('frying_seg_model', 'frying_seg.pt')
FRYING_CLS_MODEL = config.get('frying_cls_model', 'frying_cls.pt')

# Observe_add Configuration (video2, video3)
OBSERVE_LEFT_CAMERA_INDEX = config.get('observe_left_camera_index', 2)
OBSERVE_RIGHT_CAMERA_INDEX = config.get('observe_right_camera_index', 3)
OBSERVE_SEG_MODEL = config.get('observe_seg_model', '../observe_add/besta.pt')
OBSERVE_CLS_MODEL = config.get('observe_cls_model', '../observe_add/bestb.pt')

# Common AI settings
IMG_SIZE_SEG = config.get('img_size_seg', 640)
IMG_SIZE_CLS = config.get('img_size_cls', 224)
CONF_SEG = config.get('conf_seg', 0.5)
VOTE_N = config.get('vote_n', 7)  # Majority voting window
POSITIVE_LABEL = config.get('positive_label', 'filled')

# MQTT Configuration
MQTT_ENABLED = config.get('mqtt_enabled', False)
MQTT_BROKER = config.get('mqtt_broker', 'localhost')
MQTT_PORT = config.get('mqtt_port', 1883)
MQTT_TOPIC_FRYING = config.get('mqtt_topic_frying', 'frying/status')
MQTT_TOPIC_OBSERVE = config.get('mqtt_topic_observe', 'observe/status')
MQTT_TOPIC_OIL_TEMP_LEFT = config.get('mqtt_topic_oil_temp_left', 'frying/oil_temp/left')
MQTT_TOPIC_OIL_TEMP_RIGHT = config.get('mqtt_topic_oil_temp_right', 'frying/oil_temp/right')
MQTT_TOPIC_PROBE_TEMP_LEFT = config.get('mqtt_topic_probe_temp_left', 'frying/probe_temp/left')
MQTT_TOPIC_PROBE_TEMP_RIGHT = config.get('mqtt_topic_probe_temp_right', 'frying/probe_temp/right')
MQTT_TOPIC_FOOD_TYPE = config.get('mqtt_topic_food_type', 'frying/food_type')
MQTT_QOS = config.get('mqtt_qos', 1)
MQTT_CLIENT_ID = config.get('mqtt_client_id', 'jetson2_ai')

# Data Collection Configuration
TARGET_PROBE_TEMP = config.get('target_probe_temp', 75.0)
JPEG_QUALITY = config.get('jpeg_quality', 85)
FOOD_TYPES = config.get('food_types', ["chicken", "shrimp", "potato", "dumpling", "pork_cutlet", "fish"])

# GUI Configuration - WHITE MODE (768x1024 세로 모드)
WINDOW_WIDTH = config.get('window_width', 768)
WINDOW_HEIGHT = config.get('window_height', 1024)
FULLSCREEN_MODE = config.get('fullscreen', False)  # 전체화면 모드 설정
WINDOW_DECORATIONS = config.get('window_decorations', False)  # 창 테두리 표시 여부
LARGE_FONT = ("Noto Sans CJK KR", config.get('font_large', 22), "bold")
MEDIUM_FONT = ("Noto Sans CJK KR", config.get('font_medium', 16), "bold")
SMALL_FONT = ("Noto Sans CJK KR", config.get('font_small', 12))
NORMAL_FONT = ("Noto Sans CJK KR", config.get('font_normal', 14))
BUTTON_FONT = ("Noto Sans CJK KR", config.get('font_button', 16), "bold")

# Colors - WHITE MODE (matching Jetson #1)
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

# Camera resolution (GMSL) - from config
CAMERA_WIDTH = config.get('camera_width', 1920)
CAMERA_HEIGHT = config.get('camera_height', 1536)
CAMERA_FPS = config.get('camera_fps', 30)

# Display resolution (최적화)
DISPLAY_WIDTH = config.get('display_width', 600)
DISPLAY_HEIGHT = config.get('display_height', 450)

# GUI update interval
GUI_UPDATE_INTERVAL = config.get('gui_update_interval_ms', 50)

# Frame skip settings (CPU 절약)
FRYING_FRAME_SKIP = config.get('frying_frame_skip', 3)
OBSERVE_FRAME_SKIP = config.get('observe_frame_skip', 5)

# GMSL Driver settings
GMSL_MODE = config.get('gmsl_mode', 2)
GMSL_DRIVER_DIR = config.get('gmsl_driver_dir',
    '/home/dkuyj/jetson-camera-monitor/SG4A-NONX-G2Y-A1_ORIN_NANO_YUV_JP6.2_L4TR36.4.3')


# =========================
# Main Application Class
# =========================
class JetsonIntegratedApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Jetson #2 - AI Monitoring System")
        self.root.configure(bg=COLOR_BG)  # WHITE MODE

        # Window decorations (config에서 설정)
        if not WINDOW_DECORATIONS:
            self.root.overrideredirect(True)
            print(f"[디스플레이] 창 테두리 숨김")

        # Set window size and position
        if FULLSCREEN_MODE:
            # Fullscreen mode
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            self.root.geometry(f"{screen_width}x{screen_height}+0+0")
            print(f"[디스플레이] 전체화면 모드 ({screen_width}x{screen_height})")
        else:
            # Windowed mode
            self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+0+0")
            print(f"[디스플레이] 창 모드 ({WINDOW_WIDTH}x{WINDOW_HEIGHT})")

        # System info
        self.sys_info = SystemInfo(device_name="Jetson2", location="Kitchen")

        # MQTT client
        self.mqtt_client = None
        if MQTT_ENABLED:
            self.init_mqtt()

        # Load AI models with GPU (if available)
        print("[모델] AI 모델 로딩 중...")

        # Check CUDA availability
        import torch
        self.use_cuda = torch.cuda.is_available()
        if self.use_cuda:
            print(f"[GPU] CUDA 사용 가능! GPU 가속 활성화")
            self.device = 'cuda'
        else:
            print(f"[GPU] CUDA 미사용 - CPU 모드로 실행")
            self.device = 'cpu'

        # Frying AI segmenter
        self.frying_segmenter = FoodSegmenter(mode="auto")
        print(f"[모델] Frying segmenter 로드 완료")

        # Observe_add models
        self.observe_seg_model = YOLO(OBSERVE_SEG_MODEL)
        self.observe_cls_model = YOLO(OBSERVE_CLS_MODEL)

        # Move to GPU if available
        if self.use_cuda:
            try:
                self.observe_seg_model.to('cuda')
                self.observe_cls_model.to('cuda')
                print(f"[모델] Observe_add 모델 로드 완료 (GPU)")
            except Exception as e:
                print(f"[GPU] GPU 전환 실패, CPU 사용: {e}")
                self.device = 'cpu'
        else:
            print(f"[모델] Observe_add 모델 로드 완료 (CPU)")

        # Get classification names
        self.observe_cls_names = getattr(self.observe_cls_model.model, "names", None) or \
                                 getattr(self.observe_cls_model, "names", None)
        print(f"[모델] Observe 분류 클래스: {self.observe_cls_names}")

        # AI processing queues (백그라운드 스레드)
        self.frying_left_queue = Queue(maxsize=1)
        self.frying_right_queue = Queue(maxsize=1)
        self.observe_left_queue = Queue(maxsize=1)
        self.observe_right_queue = Queue(maxsize=1)

        # AI result queues
        self.frying_left_result = None
        self.frying_right_result = None
        self.observe_left_result = None
        self.observe_right_result = None

        # AI worker threads
        self.ai_threads = []

        # Subprocess tracking (진동센서 등)
        self.child_processes = []

        # Frame skip counters (CPU 절약)
        self.frying_frame_skip = 0
        self.observe_frame_skip = 0

        # Camera objects
        self.frying_left_cap = None
        self.frying_right_cap = None
        self.observe_left_cap = None
        self.observe_right_cap = None

        # Voting queues for stability (observe_add)
        self.observe_left_votes = deque(maxlen=VOTE_N)
        self.observe_right_votes = deque(maxlen=VOTE_N)

        # Last states for change detection
        self.observe_left_state = None
        self.observe_right_state = None

        # Temperature data (from MQTT)
        self.oil_temp_left = 0.0
        self.oil_temp_right = 0.0
        self.probe_temp_left = 0.0
        self.probe_temp_right = 0.0

        # Food type (from MQTT or manual selection)
        self.current_food_type = "unknown"

        # Running flags
        self.running = True
        self.frying_running = False
        self.observe_running = False

        # Data collection flags
        self.data_collection_active = False
        self.collection_session_id = None
        self.collection_start_time = None
        self.collection_frame_counter = 0
        self.collection_interval = config.get('data_collection_interval', 5)  # 5초마다 저장 (기본값)
        self.collection_timer = 0
        self.collection_metadata = []  # Store MQTT metadata during collection
        self.collection_completion_marked = False  # 완료 시점 마킹 여부
        self.collection_completion_time = None  # 완료 시점 타임스탬프
        self.collection_completion_info = {}  # 완료 시점의 온도/시간 정보

        # Latest frames for data collection
        self.latest_frying_left_frame = None
        self.latest_frying_right_frame = None
        self.latest_observe_left_frame = None
        self.latest_observe_right_frame = None

        # Build GUI
        self.build_gui()

        # Initialize cameras
        self.init_cameras()

        # Start update loops
        self.update_frying_left()
        self.update_frying_right()
        self.update_observe_left()
        self.update_observe_right()
        self.update_clock()

        # Fullscreen toggle
        self.is_fullscreen = False
        self.root.bind('<F11>', lambda e: self.toggle_fullscreen())
        self.root.bind('<Escape>', lambda e: self.exit_fullscreen())

        # Cleanup on close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def init_mqtt(self):
        """Initialize MQTT client"""
        try:
            self.mqtt_client = MQTTClient(
                broker_address=MQTT_BROKER,
                port=MQTT_PORT,
                client_id=MQTT_CLIENT_ID
            )

            # Subscribe to temperature topics
            self.mqtt_client.subscribe(MQTT_TOPIC_OIL_TEMP_LEFT, self.on_oil_temp_left)
            self.mqtt_client.subscribe(MQTT_TOPIC_OIL_TEMP_RIGHT, self.on_oil_temp_right)
            self.mqtt_client.subscribe(MQTT_TOPIC_PROBE_TEMP_LEFT, self.on_probe_temp_left)
            self.mqtt_client.subscribe(MQTT_TOPIC_PROBE_TEMP_RIGHT, self.on_probe_temp_right)

            # Subscribe to food type topic
            self.mqtt_client.subscribe(MQTT_TOPIC_FOOD_TYPE, self.on_food_type)

            self.mqtt_client.connect()
            print(f"[MQTT] 연결 성공: {MQTT_BROKER}:{MQTT_PORT}")
            print(f"[MQTT] 구독 토픽:")
            print(f"  - {MQTT_TOPIC_OIL_TEMP_LEFT}")
            print(f"  - {MQTT_TOPIC_OIL_TEMP_RIGHT}")
            print(f"  - {MQTT_TOPIC_PROBE_TEMP_LEFT}")
            print(f"  - {MQTT_TOPIC_PROBE_TEMP_RIGHT}")
            print(f"  - {MQTT_TOPIC_FOOD_TYPE}")
        except Exception as e:
            print(f"[MQTT] 연결 실패: {e}")
            self.mqtt_client = None

    def on_oil_temp_left(self, client, userdata, message):
        """MQTT callback for left oil temperature"""
        try:
            self.oil_temp_left = float(message.payload.decode())

            # Store metadata during data collection
            if self.data_collection_active:
                from datetime import datetime
                self.collection_metadata.append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "type": "oil_temperature",
                    "position": "left",
                    "value": self.oil_temp_left,
                    "unit": "celsius"
                })
        except:
            pass

    def on_oil_temp_right(self, client, userdata, message):
        """MQTT callback for right oil temperature"""
        try:
            self.oil_temp_right = float(message.payload.decode())

            # Store metadata during data collection
            if self.data_collection_active:
                from datetime import datetime
                self.collection_metadata.append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "type": "oil_temperature",
                    "position": "right",
                    "value": self.oil_temp_right,
                    "unit": "celsius"
                })
        except:
            pass

    def on_probe_temp_left(self, client, userdata, message):
        """MQTT callback for left probe temperature"""
        try:
            self.probe_temp_left = float(message.payload.decode())

            # Store metadata during data collection
            if self.data_collection_active:
                from datetime import datetime
                self.collection_metadata.append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "type": "probe_temperature",
                    "position": "left",
                    "value": self.probe_temp_left,
                    "unit": "celsius"
                })

                # Auto-mark completion if target temperature reached
                if not self.collection_completion_marked and self.probe_temp_left >= TARGET_PROBE_TEMP:
                    self.mark_completion_auto("left", self.probe_temp_left)
        except:
            pass

    def on_probe_temp_right(self, client, userdata, message):
        """MQTT callback for right probe temperature"""
        try:
            self.probe_temp_right = float(message.payload.decode())

            # Store metadata during data collection
            if self.data_collection_active:
                from datetime import datetime
                self.collection_metadata.append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "type": "probe_temperature",
                    "position": "right",
                    "value": self.probe_temp_right,
                    "unit": "celsius"
                })

                # Auto-mark completion if target temperature reached
                if not self.collection_completion_marked and self.probe_temp_right >= TARGET_PROBE_TEMP:
                    self.mark_completion_auto("right", self.probe_temp_right)
        except:
            pass

    def on_food_type(self, client, userdata, message):
        """MQTT callback for food type"""
        try:
            self.current_food_type = message.payload.decode()
            print(f"[MQTT] 음식 종류 변경: {self.current_food_type}")

            # Store metadata during data collection
            if self.data_collection_active:
                from datetime import datetime
                self.collection_metadata.append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "type": "food_type_change",
                    "value": self.current_food_type
                })
        except:
            pass

    def send_mqtt_message(self, topic, message):
        """Send MQTT message"""
        if self.mqtt_client and MQTT_ENABLED:
            try:
                self.mqtt_client.publish(topic, message, qos=MQTT_QOS)
            except Exception as e:
                print(f"[MQTT] 전송 실패: {e}")

    def build_gui(self):
        """Build the main GUI layout - WHITE MODE with Jetson #1 header"""
        # Top header - matching Jetson #1
        header_height = 110
        header_frame = tk.Frame(self.root, bg=COLOR_PANEL, height=header_height, bd=1, relief=tk.FLAT)
        header_frame.pack(fill=tk.X, padx=0, pady=0)
        header_frame.pack_propagate(False)

        # Header layout: 3 columns
        header_frame.columnconfigure(0, weight=1)  # Left: System status
        header_frame.columnconfigure(1, weight=1)  # Center: Title + Time
        header_frame.columnconfigure(2, weight=1)  # Right: Buttons

        # LEFT: System status + Date
        left_frame = tk.Frame(header_frame, bg=COLOR_PANEL)
        left_frame.grid(row=0, column=0, sticky="w", padx=8, pady=8)

        self.system_status_label = tk.Label(left_frame, text="시스템 정상",
                                           font=NORMAL_FONT, bg=COLOR_PANEL, fg=COLOR_OK)
        self.system_status_label.pack(anchor="w")

        self.date_label = tk.Label(left_frame, text="----/--/--",
                                   font=("Noto Sans CJK KR", 14),
                                   bg=COLOR_PANEL, fg=COLOR_TEXT_LIGHT)
        self.date_label.pack(anchor="w")

        # CENTER: Title + Time
        center_frame = tk.Frame(header_frame, bg=COLOR_PANEL)
        center_frame.grid(row=0, column=1, sticky="n", pady=5)

        tk.Label(center_frame, text="현대자동차 울산점",
                font=("Noto Sans CJK KR", 20, "bold"),
                bg=COLOR_PANEL, fg=COLOR_ACCENT).pack()

        self.time_label = tk.Label(center_frame, text="--:--:--",
                                   font=("Noto Sans CJK KR", 20, "bold"),
                                   bg=COLOR_PANEL, fg=COLOR_INFO)
        self.time_label.pack()

        # RIGHT: PC Status, Vibration Check, Settings buttons
        right_frame = tk.Frame(header_frame, bg=COLOR_PANEL)
        right_frame.grid(row=0, column=2, sticky="e", padx=8, pady=8)

        # PC Status button
        tk.Button(right_frame, text="PC 상태",
                 font=("Noto Sans CJK KR", 16, "bold"),
                 command=self.open_pc_status, bg="#00897B", fg="white",
                 relief=tk.FLAT, bd=0, activebackground="#00796B",
                 padx=12, pady=8).pack(side=tk.LEFT, padx=3)

        # Vibration check button
        tk.Button(right_frame, text="진동 체크",
                 font=("Noto Sans CJK KR", 16, "bold"),
                 command=self.open_vibration_check, bg=COLOR_INFO, fg="white",
                 relief=tk.FLAT, bd=0, activebackground=COLOR_BUTTON_HOVER,
                 padx=12, pady=8).pack(side=tk.LEFT, padx=3)

        # Settings button (placeholder)
        tk.Button(right_frame, text="설정",
                 font=("Noto Sans CJK KR", 16, "bold"),
                 command=self.open_settings, bg=COLOR_BUTTON, fg="white",
                 relief=tk.FLAT, bd=0, activebackground=COLOR_BUTTON_HOVER,
                 padx=12, pady=8).pack(side=tk.LEFT, padx=3)

        # Main content frame (세로 레이아웃 - 768x1024 최적화)
        self.content_frame = tk.Frame(self.root, bg=COLOR_BG)
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Configure grid weights (4 rows x 1 column for vertical layout)
        self.content_frame.rowconfigure(0, weight=1)  # Frying Left
        self.content_frame.rowconfigure(1, weight=1)  # Frying Right
        self.content_frame.rowconfigure(2, weight=1)  # Observe Left
        self.content_frame.rowconfigure(3, weight=1)  # Observe Right
        self.content_frame.columnconfigure(0, weight=1)  # Single column

        # Create 4 camera panels
        self.create_frying_left_panel()
        self.create_frying_right_panel()
        self.create_observe_left_panel()
        self.create_observe_right_panel()

        # Bottom control panel
        self.create_control_panel()

    def create_frying_left_panel(self):
        """Create Frying AI Left camera panel (세로 레이아웃)"""
        panel = tk.Frame(self.content_frame, bg=COLOR_PANEL, relief=tk.RAISED, borderwidth=1,
                        highlightbackground=COLOR_PANEL_BORDER, highlightthickness=1)
        panel.grid(row=0, column=0, padx=3, pady=2, sticky="nsew")

        # Title
        title = tk.Label(panel, text="🍤 튀김 AI - 왼쪽", font=MEDIUM_FONT, bg=COLOR_PANEL, fg=COLOR_TEXT)
        title.pack(pady=5)

        # Camera preview (세로 레이아웃 - 높이 축소)
        preview_container = tk.Frame(panel, bg="black", height=160)
        preview_container.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
        preview_container.pack_propagate(False)

        self.frying_left_label = tk.Label(preview_container, bg="black")
        self.frying_left_label.pack(expand=True)

        # Info frame (temperature + color features)
        info_frame = tk.Frame(panel, bg=COLOR_PANEL)
        info_frame.pack(pady=5)

        # Oil Temperature
        self.frying_left_temp_label = tk.Label(
            info_frame, text="기름: -- °C", font=SMALL_FONT, bg=COLOR_PANEL, fg=COLOR_ERROR
        )
        self.frying_left_temp_label.pack()

        # Probe Temperature
        self.frying_left_probe_label = tk.Label(
            info_frame, text="탐침: -- °C", font=SMALL_FONT, bg=COLOR_PANEL, fg=COLOR_INFO
        )
        self.frying_left_probe_label.pack()

        # Color features
        self.frying_left_color_label = tk.Label(
            info_frame, text="갈색: --% | 황금: --%", font=SMALL_FONT, bg=COLOR_PANEL, fg=COLOR_WARNING
        )
        self.frying_left_color_label.pack()

        # Status
        self.frying_left_status = tk.Label(
            panel, text="대기 중", font=SMALL_FONT, bg=COLOR_PANEL, fg=COLOR_TEXT_LIGHT
        )
        self.frying_left_status.pack(pady=2)

    def create_frying_right_panel(self):
        """Create Frying AI Right camera panel (세로 레이아웃)"""
        panel = tk.Frame(self.content_frame, bg=COLOR_PANEL, relief=tk.RAISED, borderwidth=1,
                        highlightbackground=COLOR_PANEL_BORDER, highlightthickness=1)
        panel.grid(row=1, column=0, padx=3, pady=2, sticky="nsew")

        # Title
        title = tk.Label(panel, text="🍤 튀김 AI - 오른쪽", font=MEDIUM_FONT, bg=COLOR_PANEL, fg=COLOR_TEXT)
        title.pack(pady=5)

        # Camera preview (세로 레이아웃 - 높이 축소)
        preview_container = tk.Frame(panel, bg="black", height=160)
        preview_container.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
        preview_container.pack_propagate(False)

        self.frying_right_label = tk.Label(preview_container, bg="black")
        self.frying_right_label.pack(expand=True)

        # Info frame (temperature + color features)
        info_frame = tk.Frame(panel, bg=COLOR_PANEL)
        info_frame.pack(pady=5)

        # Oil Temperature
        self.frying_right_temp_label = tk.Label(
            info_frame, text="기름: -- °C", font=SMALL_FONT, bg=COLOR_PANEL, fg=COLOR_ERROR
        )
        self.frying_right_temp_label.pack()

        # Probe Temperature
        self.frying_right_probe_label = tk.Label(
            info_frame, text="탐침: -- °C", font=SMALL_FONT, bg=COLOR_PANEL, fg=COLOR_INFO
        )
        self.frying_right_probe_label.pack()

        # Color features
        self.frying_right_color_label = tk.Label(
            info_frame, text="갈색: --% | 황금: --%", font=SMALL_FONT, bg=COLOR_PANEL, fg=COLOR_WARNING
        )
        self.frying_right_color_label.pack()

        # Status
        self.frying_right_status = tk.Label(
            panel, text="대기 중", font=SMALL_FONT, bg=COLOR_PANEL, fg=COLOR_TEXT_LIGHT
        )
        self.frying_right_status.pack(pady=2)

    def create_observe_left_panel(self):
        """Create Observe_add Left camera panel (세로 레이아웃)"""
        panel = tk.Frame(self.content_frame, bg=COLOR_PANEL, relief=tk.RAISED, borderwidth=1,
                        highlightbackground=COLOR_PANEL_BORDER, highlightthickness=1)
        panel.grid(row=2, column=0, padx=3, pady=2, sticky="nsew")

        # Title
        title = tk.Label(panel, text="🥘 바켓 감지 - 왼쪽", font=MEDIUM_FONT, bg=COLOR_PANEL, fg=COLOR_TEXT)
        title.pack(pady=5)

        # Camera preview (세로 레이아웃 - 높이 축소)
        preview_container = tk.Frame(panel, bg="black", height=160)
        preview_container.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
        preview_container.pack_propagate(False)

        self.observe_left_label = tk.Label(preview_container, bg="black")
        self.observe_left_label.pack(expand=True)

        # Status
        self.observe_left_status = tk.Label(
            panel, text="대기 중", font=SMALL_FONT, bg=COLOR_PANEL, fg=COLOR_TEXT_LIGHT
        )
        self.observe_left_status.pack(pady=5)

    def create_observe_right_panel(self):
        """Create Observe_add Right camera panel (세로 레이아웃)"""
        panel = tk.Frame(self.content_frame, bg=COLOR_PANEL, relief=tk.RAISED, borderwidth=1,
                        highlightbackground=COLOR_PANEL_BORDER, highlightthickness=1)
        panel.grid(row=3, column=0, padx=3, pady=2, sticky="nsew")

        # Title
        title = tk.Label(panel, text="🥘 바켓 감지 - 오른쪽", font=MEDIUM_FONT, bg=COLOR_PANEL, fg=COLOR_TEXT)
        title.pack(pady=5)

        # Camera preview (세로 레이아웃 - 높이 축소)
        preview_container = tk.Frame(panel, bg="black", height=160)
        preview_container.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
        preview_container.pack_propagate(False)

        self.observe_right_label = tk.Label(preview_container, bg="black")
        self.observe_right_label.pack(expand=True)

        # Status
        self.observe_right_status = tk.Label(
            panel, text="대기 중", font=SMALL_FONT, bg=COLOR_PANEL, fg=COLOR_TEXT_LIGHT
        )
        self.observe_right_status.pack(pady=5)

    def create_control_panel(self):
        """Create bottom control panel (세로 레이아웃 최적화)"""
        control_frame = tk.Frame(self.root, bg=COLOR_BG)
        control_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)

        # Start/Stop buttons
        btn_frame = tk.Frame(control_frame, bg=COLOR_BG)
        btn_frame.pack(side=tk.LEFT, padx=10)

        self.btn_start_frying = tk.Button(
            btn_frame,
            text="튀김 AI 시작",
            font=BUTTON_FONT,
            bg="#27AE60",
            fg="white",
            activebackground="#229954",
            command=self.start_frying_ai,
            width=10,
            height=1,
            relief=tk.FLAT
        )
        self.btn_start_frying.pack(side=tk.LEFT, padx=5)

        self.btn_stop_frying = tk.Button(
            btn_frame,
            text="튀김 AI 중지",
            font=BUTTON_FONT,
            bg=COLOR_ERROR,
            fg="white",
            activebackground="#C0392B",
            command=self.stop_frying_ai,
            width=10,
            height=1,
            state=tk.DISABLED,
            relief=tk.FLAT
        )
        self.btn_stop_frying.pack(side=tk.LEFT, padx=5)

        self.btn_start_observe = tk.Button(
            btn_frame,
            text="바켓 감지 시작",
            font=BUTTON_FONT,
            bg="#3498DB",
            fg="white",
            activebackground="#2980B9",
            command=self.start_observe_ai,
            width=10,
            height=1,
            relief=tk.FLAT
        )
        self.btn_start_observe.pack(side=tk.LEFT, padx=5)

        self.btn_stop_observe = tk.Button(
            btn_frame,
            text="바켓 감지 중지",
            font=BUTTON_FONT,
            bg=COLOR_ERROR,
            fg="white",
            activebackground="#C0392B",
            command=self.stop_observe_ai,
            width=10,
            height=1,
            state=tk.DISABLED,
            relief=tk.FLAT
        )
        self.btn_stop_observe.pack(side=tk.LEFT, padx=5)

        # Data collection buttons
        separator = tk.Frame(btn_frame, width=2, bg="#BDC3C7")
        separator.pack(side=tk.LEFT, fill=tk.Y, padx=15, pady=5)

        self.btn_start_collection = tk.Button(
            btn_frame,
            text="📊 수집 시작",
            font=BUTTON_FONT,
            bg="#9B59B6",
            fg="white",
            activebackground="#8E44AD",
            command=self.start_data_collection,
            width=10,
            height=1,
            relief=tk.FLAT
        )
        self.btn_start_collection.pack(side=tk.LEFT, padx=5)

        self.btn_mark_completion = tk.Button(
            btn_frame,
            text="✅ 완료 마킹",
            font=BUTTON_FONT,
            bg="#F39C12",
            fg="white",
            activebackground="#E67E22",
            command=self.mark_completion_manual,
            width=10,
            height=1,
            state=tk.DISABLED,
            relief=tk.FLAT
        )
        self.btn_mark_completion.pack(side=tk.LEFT, padx=5)

        self.btn_stop_collection = tk.Button(
            btn_frame,
            text="📊 수집 중지",
            font=BUTTON_FONT,
            bg=COLOR_ERROR,
            fg="white",
            activebackground="#C0392B",
            command=self.stop_data_collection,
            width=10,
            height=1,
            state=tk.DISABLED,
            relief=tk.FLAT
        )
        self.btn_stop_collection.pack(side=tk.LEFT, padx=5)

        # Collection status label
        status_frame = tk.Frame(control_frame, bg=COLOR_BG)
        status_frame.pack(side=tk.LEFT, padx=20)

        self.collection_status_label = tk.Label(
            status_frame,
            text="수집: 대기 중",
            font=NORMAL_FONT,
            bg=COLOR_BG,
            fg=COLOR_TEXT
        )
        self.collection_status_label.pack()

        # Exit button
        self.btn_exit = tk.Button(
            control_frame,
            text="종료",
            font=BUTTON_FONT,
            bg="#95A5A6",
            fg="white",
            activebackground="#7F8C8D",
            command=self.on_close,
            width=8,
            height=1,
            relief=tk.FLAT
        )
        self.btn_exit.pack(side=tk.RIGHT, padx=10)

    def init_cameras(self):
        """Initialize all 4 GMSL cameras"""
        print("[카메라] 카메라 초기화 중...")

        # Frying AI cameras (video0, video1)
        self.frying_left_cap = GstCamera(
            device_index=FRYING_LEFT_CAMERA_INDEX,
            width=CAMERA_WIDTH,
            height=CAMERA_HEIGHT,
            fps=CAMERA_FPS
        )
        if self.frying_left_cap.start():
            print(f"[카메라] 볶음 왼쪽 (video{FRYING_LEFT_CAMERA_INDEX}) 초기화 완료 ✓")

        self.frying_right_cap = GstCamera(
            device_index=FRYING_RIGHT_CAMERA_INDEX,
            width=CAMERA_WIDTH,
            height=CAMERA_HEIGHT,
            fps=CAMERA_FPS
        )
        if self.frying_right_cap.start():
            print(f"[카메라] 볶음 오른쪽 (video{FRYING_RIGHT_CAMERA_INDEX}) 초기화 완료 ✓")

        # Observe_add cameras (video2, video3)
        self.observe_left_cap = GstCamera(
            device_index=OBSERVE_LEFT_CAMERA_INDEX,
            width=CAMERA_WIDTH,
            height=CAMERA_HEIGHT,
            fps=CAMERA_FPS
        )
        if self.observe_left_cap.start():
            print(f"[카메라] 바켓 왼쪽 (video{OBSERVE_LEFT_CAMERA_INDEX}) 초기화 완료 ✓")

        self.observe_right_cap = GstCamera(
            device_index=OBSERVE_RIGHT_CAMERA_INDEX,
            width=CAMERA_WIDTH,
            height=CAMERA_HEIGHT,
            fps=CAMERA_FPS
        )
        if self.observe_right_cap.start():
            print(f"[카메라] 바켓 오른쪽 (video{OBSERVE_RIGHT_CAMERA_INDEX}) 초기화 완료 ✓")

        print("[카메라] 모든 카메라 초기화 완료!")

    def update_clock(self):
        """Update time and date in header"""
        if not self.running:
            return

        now = datetime.now()
        self.time_label.config(text=now.strftime("%H:%M:%S"))
        self.date_label.config(text=now.strftime("%Y/%m/%d"))

        self.root.after(1000, self.update_clock)

    def update_frying_left(self):
        """Update Frying AI left camera - OPTIMIZED with frame skip"""
        if not self.running:
            return

        ret, frame = self.frying_left_cap.read()
        if ret:
            vis = frame.copy()

            if self.frying_running:
                # Frame skip: AI 처리는 N프레임마다 (CPU 절약)
                self.frying_frame_skip += 1
                if self.frying_frame_skip >= FRYING_FRAME_SKIP:
                    self.frying_frame_skip = 0

                    # 백그라운드 스레드로 AI 처리 (non-blocking)
                    def process_ai():
                        try:
                            result = self.frying_segmenter.segment(frame, visualize=False)
                            self.frying_left_result = result
                        except Exception as e:
                            print(f"[튀김 왼쪽] Segmentation 오류: {e}")

                    threading.Thread(target=process_ai, daemon=True).start()

                # 이전 AI 결과 사용 (매 프레임 화면 업데이트)
                if self.frying_left_result is not None:
                    result = self.frying_left_result
                    try:
                        # Draw food mask overlay (green tint)
                        if result.food_mask is not None:
                            green_overlay = np.zeros_like(vis)
                            green_overlay[:, :] = (0, 255, 0)
                            mask_3ch = cv2.cvtColor(result.food_mask, cv2.COLOR_GRAY2BGR)
                            vis = cv2.addWeighted(vis, 0.7, cv2.bitwise_and(green_overlay, mask_3ch), 0.3, 0)

                        # Extract color features
                        feat = result.color_features
                        brown_pct = int(feat.brown_ratio * 100)
                        golden_pct = int(feat.golden_ratio * 100)
                        area_pct = int(result.food_area_ratio * 100)

                        # Draw features on frame
                        cv2.putText(vis, f"Brown: {brown_pct}%", (16, 40),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1, (60, 120, 200), 2)
                        cv2.putText(vis, f"Golden: {golden_pct}%", (16, 80),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 200, 255), 2)
                        cv2.putText(vis, f"Area: {area_pct}%", (16, 120),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2)

                        # Update GUI labels
                        self.frying_left_color_label.config(
                            text=f"갈색: {brown_pct}% | 황금: {golden_pct}%"
                        )
                    except:
                        pass

                # Update temperatures
                self.frying_left_temp_label.config(text=f"기름: {self.oil_temp_left:.1f} °C")

                # Probe temperature with color coding
                probe_color = COLOR_INFO
                if self.probe_temp_left >= TARGET_PROBE_TEMP:
                    probe_color = COLOR_OK
                elif self.probe_temp_left > 0:
                    probe_color = COLOR_WARNING
                self.frying_left_probe_label.config(
                    text=f"탐침: {self.probe_temp_left:.1f} °C",
                    fg=probe_color
                )

            # Display (resize once)
            display_frame = cv2.resize(vis, (DISPLAY_WIDTH, DISPLAY_HEIGHT), interpolation=cv2.INTER_NEAREST)
            display_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)

            img = Image.fromarray(display_frame)
            imgtk = ImageTk.PhotoImage(image=img)
            self.frying_left_label.imgtk = imgtk
            self.frying_left_label.configure(image=imgtk)

            # Store latest frame for data collection
            self.latest_frying_left_frame = frame.copy()

        self.root.after(GUI_UPDATE_INTERVAL, self.update_frying_left)

    def update_frying_right(self):
        """Update Frying AI right camera - OPTIMIZED with frame skip"""
        if not self.running:
            return

        ret, frame = self.frying_right_cap.read()
        if ret:
            vis = frame.copy()

            if self.frying_running:
                # Frame skip은 왼쪽과 공유 (같은 카운터)
                if self.frying_frame_skip == 0:  # 왼쪽에서 리셋된 경우
                    # 백그라운드 스레드로 AI 처리
                    def process_ai():
                        try:
                            result = self.frying_segmenter.segment(frame, visualize=False)
                            self.frying_right_result = result
                        except Exception as e:
                            print(f"[튀김 오른쪽] Segmentation 오류: {e}")

                    threading.Thread(target=process_ai, daemon=True).start()

                # 이전 AI 결과 사용
                if self.frying_right_result is not None:
                    result = self.frying_right_result
                    try:
                        # Draw food mask overlay (green tint)
                        if result.food_mask is not None:
                            green_overlay = np.zeros_like(vis)
                            green_overlay[:, :] = (0, 255, 0)
                            mask_3ch = cv2.cvtColor(result.food_mask, cv2.COLOR_GRAY2BGR)
                            vis = cv2.addWeighted(vis, 0.7, cv2.bitwise_and(green_overlay, mask_3ch), 0.3, 0)

                        # Extract color features
                        feat = result.color_features
                        brown_pct = int(feat.brown_ratio * 100)
                        golden_pct = int(feat.golden_ratio * 100)
                        area_pct = int(result.food_area_ratio * 100)

                        # Draw features on frame
                        cv2.putText(vis, f"Brown: {brown_pct}%", (16, 40),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1, (60, 120, 200), 2)
                        cv2.putText(vis, f"Golden: {golden_pct}%", (16, 80),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 200, 255), 2)
                        cv2.putText(vis, f"Area: {area_pct}%", (16, 120),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2)

                        # Update GUI labels
                        self.frying_right_color_label.config(
                            text=f"갈색: {brown_pct}% | 황금: {golden_pct}%"
                        )
                    except:
                        pass

                # Update temperatures
                self.frying_right_temp_label.config(text=f"기름: {self.oil_temp_right:.1f} °C")

                # Probe temperature with color coding
                probe_color = COLOR_INFO
                if self.probe_temp_right >= TARGET_PROBE_TEMP:
                    probe_color = COLOR_OK
                elif self.probe_temp_right > 0:
                    probe_color = COLOR_WARNING
                self.frying_right_probe_label.config(
                    text=f"탐침: {self.probe_temp_right:.1f} °C",
                    fg=probe_color
                )

            # Display
            display_frame = cv2.resize(vis, (DISPLAY_WIDTH, DISPLAY_HEIGHT), interpolation=cv2.INTER_NEAREST)
            display_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)

            img = Image.fromarray(display_frame)
            imgtk = ImageTk.PhotoImage(image=img)
            self.frying_right_label.imgtk = imgtk
            self.frying_right_label.configure(image=imgtk)

            # Store latest frame for data collection
            self.latest_frying_right_frame = frame.copy()

            # Periodic data collection (check every second, save every N seconds)
            if self.data_collection_active:
                self.collection_timer += GUI_UPDATE_INTERVAL / 1000.0  # Convert ms to seconds
                if self.collection_timer >= self.collection_interval:
                    self.collection_timer = 0
                    # Trigger data collection from all 4 cameras
                    self.save_collection_data(
                        self.latest_frying_left_frame,
                        self.latest_frying_right_frame,
                        self.latest_observe_left_frame,
                        self.latest_observe_right_frame
                    )

        self.root.after(GUI_UPDATE_INTERVAL, self.update_frying_right)

    def update_observe_left(self):
        """Update Observe_add left camera - OPTIMIZED with GPU + frame skip"""
        if not self.running:
            return

        ret, frame = self.observe_left_cap.read()
        if ret:
            vis = frame.copy()
            H, W = frame.shape[:2]

            if self.observe_running:
                # Frame skip: YOLO는 매우 무거움 (config로 조정)
                self.observe_frame_skip += 1
                if self.observe_frame_skip >= OBSERVE_FRAME_SKIP:
                    self.observe_frame_skip = 0

                    # 백그라운드 스레드로 YOLO 처리
                    def process_ai():
                        try:
                            r = self.observe_seg_model.predict(
                                frame, imgsz=IMG_SIZE_SEG, conf=CONF_SEG, verbose=False, device=self.device
                            )[0]
                            self.observe_left_result = r
                        except Exception as e:
                            print(f"[바켓 왼쪽] YOLO 오류: {e}")

                    threading.Thread(target=process_ai, daemon=True).start()

                # 이전 YOLO 결과 사용
                if self.observe_left_result is None:
                    # Display raw frame
                    display_frame = cv2.resize(vis, (DISPLAY_WIDTH, DISPLAY_HEIGHT), interpolation=cv2.INTER_NEAREST)
                    display_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(display_frame)
                    imgtk = ImageTk.PhotoImage(image=img)
                    self.observe_left_label.imgtk = imgtk
                    self.observe_left_label.configure(image=imgtk)
                    self.root.after(GUI_UPDATE_INTERVAL, self.update_observe_left)
                    return

                r = self.observe_left_result

                basket_mask = np.zeros((H, W), np.uint8)

                if r.masks is not None:
                    for i, cls_idx in enumerate(r.boxes.cls.cpu().numpy().astype(int)):
                        if r.names[cls_idx] == "basket":
                            m = (r.masks.data[i].cpu().numpy() > 0.5).astype(np.uint8) * 255
                            m = cv2.resize(m, (W, H), interpolation=cv2.INTER_NEAREST)
                            basket_mask = np.maximum(basket_mask, m)

                detected = False
                is_filled = False

                if basket_mask.any():
                    basket_mask = cv2.morphologyEx(
                        basket_mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=1
                    )
                    cnt = self.largest_contour(basket_mask)

                    if cnt is not None:
                        detected = True
                        cv2.drawContours(vis, [cnt], -1, (0, 255, 255), 2)

                        # Crop ROI
                        x, y, w, h = cv2.boundingRect(cnt)
                        x2, y2 = x + w, y + h
                        x, y = max(0, x), max(0, y)
                        x2, y2 = min(W, x2), min(H, y2)
                        roi = frame[y:y2, x:x2]

                        # Classification
                        cls_res = self.observe_cls_model.predict(
                            roi, imgsz=IMG_SIZE_CLS, conf=0.0, verbose=False, device=self.device
                        )[0]
                        top1_idx = int(cls_res.probs.top1)
                        top1_name = cls_res.names[top1_idx]
                        prob = float(cls_res.probs.top1conf)
                        is_filled = (top1_name.lower() == POSITIVE_LABEL.lower())

                        # Draw results
                        cv2.rectangle(vis, (x, y), (x2, y2), (255, 128, 0), 2)
                        cv2.putText(vis, f"{top1_name} ({prob:.2f})", (x, y-10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

                # Majority voting
                if detected:
                    self.observe_left_votes.append(is_filled)
                    filled_stable = (sum(self.observe_left_votes) >= (len(self.observe_left_votes)//2 + 1))
                    state_txt = "FILLED" if filled_stable else "EMPTY"
                    color = (0, 0, 255) if filled_stable else (200, 200, 200)

                    cv2.putText(vis, f"STATUS: {state_txt}", (16, 50),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 3)

                    # State change detection & MQTT
                    if state_txt != self.observe_left_state:
                        self.log_signal("왼쪽", state_txt)
                        self.send_mqtt_message(MQTT_TOPIC_OBSERVE, f"LEFT:{state_txt}")
                        self.observe_left_state = state_txt
                        self.observe_left_status.config(text=f"상태: {state_txt}")
                else:
                    self.observe_left_votes.clear()
                    cv2.putText(vis, "Basket Not Found", (16, 50),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                    if self.observe_left_state is not None:
                        self.log_signal("왼쪽", "NO_BASKET")
                        self.send_mqtt_message(MQTT_TOPIC_OBSERVE, "LEFT:NO_BASKET")
                        self.observe_left_state = None
                        self.observe_left_status.config(text="바켓 없음")

            # Display
            display_frame = cv2.resize(vis, (DISPLAY_WIDTH, DISPLAY_HEIGHT), interpolation=cv2.INTER_NEAREST)
            display_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)

            img = Image.fromarray(display_frame)
            imgtk = ImageTk.PhotoImage(image=img)
            self.observe_left_label.imgtk = imgtk
            self.observe_left_label.configure(image=imgtk)

            # Store latest frame for data collection
            self.latest_observe_left_frame = frame.copy()

        self.root.after(GUI_UPDATE_INTERVAL, self.update_observe_left)

    def update_observe_right(self):
        """Update Observe_add right camera - OPTIMIZED with GPU + frame skip"""
        if not self.running:
            return

        ret, frame = self.observe_right_cap.read()
        if ret:
            vis = frame.copy()
            H, W = frame.shape[:2]

            if self.observe_running:
                # Frame skip은 왼쪽과 공유 (같은 카운터)
                if self.observe_frame_skip == 0:  # 왼쪽에서 리셋된 경우
                    # 백그라운드 스레드로 YOLO 처리
                    def process_ai():
                        try:
                            r = self.observe_seg_model.predict(
                                frame, imgsz=IMG_SIZE_SEG, conf=CONF_SEG, verbose=False, device=self.device
                            )[0]
                            self.observe_right_result = r
                        except Exception as e:
                            print(f"[바켓 오른쪽] YOLO 오류: {e}")

                    threading.Thread(target=process_ai, daemon=True).start()

                # 이전 YOLO 결과 사용
                if self.observe_right_result is None:
                    # Display raw frame
                    display_frame = cv2.resize(vis, (DISPLAY_WIDTH, DISPLAY_HEIGHT), interpolation=cv2.INTER_NEAREST)
                    display_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(display_frame)
                    imgtk = ImageTk.PhotoImage(image=img)
                    self.observe_right_label.imgtk = imgtk
                    self.observe_right_label.configure(image=imgtk)
                    self.root.after(GUI_UPDATE_INTERVAL, self.update_observe_right)
                    return

                r = self.observe_right_result

                basket_mask = np.zeros((H, W), np.uint8)

                if r.masks is not None:
                    for i, cls_idx in enumerate(r.boxes.cls.cpu().numpy().astype(int)):
                        if r.names[cls_idx] == "basket":
                            m = (r.masks.data[i].cpu().numpy() > 0.5).astype(np.uint8) * 255
                            m = cv2.resize(m, (W, H), interpolation=cv2.INTER_NEAREST)
                            basket_mask = np.maximum(basket_mask, m)

                detected = False
                is_filled = False

                if basket_mask.any():
                    basket_mask = cv2.morphologyEx(
                        basket_mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=1
                    )
                    cnt = self.largest_contour(basket_mask)

                    if cnt is not None:
                        detected = True
                        cv2.drawContours(vis, [cnt], -1, (0, 255, 255), 2)

                        # Crop ROI
                        x, y, w, h = cv2.boundingRect(cnt)
                        x2, y2 = x + w, y + h
                        x, y = max(0, x), max(0, y)
                        x2, y2 = min(W, x2), min(H, y2)
                        roi = frame[y:y2, x:x2]

                        # Classification
                        cls_res = self.observe_cls_model.predict(
                            roi, imgsz=IMG_SIZE_CLS, conf=0.0, verbose=False, device=self.device
                        )[0]
                        top1_idx = int(cls_res.probs.top1)
                        top1_name = cls_res.names[top1_idx]
                        prob = float(cls_res.probs.top1conf)
                        is_filled = (top1_name.lower() == POSITIVE_LABEL.lower())

                        # Draw results
                        cv2.rectangle(vis, (x, y), (x2, y2), (255, 128, 0), 2)
                        cv2.putText(vis, f"{top1_name} ({prob:.2f})", (x, y-10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

                # Majority voting
                if detected:
                    self.observe_right_votes.append(is_filled)
                    filled_stable = (sum(self.observe_right_votes) >= (len(self.observe_right_votes)//2 + 1))
                    state_txt = "FILLED" if filled_stable else "EMPTY"
                    color = (0, 0, 255) if filled_stable else (200, 200, 200)

                    cv2.putText(vis, f"STATUS: {state_txt}", (16, 50),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 3)

                    # State change detection & MQTT
                    if state_txt != self.observe_right_state:
                        self.log_signal("오른쪽", state_txt)
                        self.send_mqtt_message(MQTT_TOPIC_OBSERVE, f"RIGHT:{state_txt}")
                        self.observe_right_state = state_txt
                        self.observe_right_status.config(text=f"상태: {state_txt}")
                else:
                    self.observe_right_votes.clear()
                    cv2.putText(vis, "Basket Not Found", (16, 50),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                    if self.observe_right_state is not None:
                        self.log_signal("오른쪽", "NO_BASKET")
                        self.send_mqtt_message(MQTT_TOPIC_OBSERVE, "RIGHT:NO_BASKET")
                        self.observe_right_state = None
                        self.observe_right_status.config(text="바켓 없음")

            # Display
            display_frame = cv2.resize(vis, (DISPLAY_WIDTH, DISPLAY_HEIGHT), interpolation=cv2.INTER_NEAREST)
            display_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)

            img = Image.fromarray(display_frame)
            imgtk = ImageTk.PhotoImage(image=img)
            self.observe_right_label.imgtk = imgtk
            self.observe_right_label.configure(image=imgtk)

            # Store latest frame for data collection
            self.latest_observe_right_frame = frame.copy()

        self.root.after(GUI_UPDATE_INTERVAL, self.update_observe_right)

    def largest_contour(self, mask, min_area=2000):
        """Find largest contour in mask"""
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            return None
        cnt = max(cnts, key=cv2.contourArea)
        if cv2.contourArea(cnt) < min_area:
            return None
        return cnt

    def log_signal(self, side, state):
        """Log state change signal"""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] 바켓 {side} -> {state}")

    def open_pc_status(self):
        """Open PC status dialog (matching Jetson #1)"""
        # Create popup window
        status_window = tk.Toplevel(self.root)
        status_window.title("PC 상태")
        status_window.geometry("600x650")
        status_window.configure(bg=COLOR_BG)

        # Center the window
        status_window.transient(self.root)
        status_window.grab_set()

        # Title
        tk.Label(status_window, text="[ PC 시스템 상태 ]", font=LARGE_FONT,
                bg=COLOR_BG, fg=COLOR_TEXT).pack(pady=20)

        # Info frame
        info_frame = tk.Frame(status_window, bg=COLOR_PANEL, bd=3, relief=tk.RAISED)
        info_frame.pack(pady=20, padx=40, fill=tk.BOTH, expand=True)

        if psutil is None:
            tk.Label(info_frame, text="psutil 라이브러리 미설치", font=MEDIUM_FONT,
                    bg=COLOR_PANEL, fg=COLOR_ERROR).pack(pady=20)
        else:
            try:
                # CPU Usage
                cpu_percent = psutil.cpu_percent(interval=0.5)
                cpu_color = COLOR_OK if cpu_percent < 70 else COLOR_WARNING if cpu_percent < 90 else COLOR_ERROR

                cpu_frame = tk.Frame(info_frame, bg=COLOR_PANEL)
                cpu_frame.pack(pady=10, padx=20, fill=tk.X)
                tk.Label(cpu_frame, text="CPU 사용률:", font=MEDIUM_FONT,
                        bg=COLOR_PANEL, fg=COLOR_TEXT, anchor="w").pack(side=tk.LEFT)
                tk.Label(cpu_frame, text=f"{cpu_percent:.1f}%", font=("Noto Sans CJK KR", 22, "bold"),
                        bg=COLOR_PANEL, fg=cpu_color, anchor="e").pack(side=tk.RIGHT)

                # GPU Usage (Jetson specific)
                try:
                    gpu_stats = self.sys_info.get_gpu_info()
                    gpu_percent = gpu_stats.get('gpu_utilization', 0)
                    gpu_color = COLOR_OK if gpu_percent < 70 else COLOR_WARNING if gpu_percent < 90 else COLOR_ERROR

                    gpu_frame = tk.Frame(info_frame, bg=COLOR_PANEL)
                    gpu_frame.pack(pady=10, padx=20, fill=tk.X)
                    tk.Label(gpu_frame, text="GPU 사용률:", font=MEDIUM_FONT,
                            bg=COLOR_PANEL, fg=COLOR_TEXT, anchor="w").pack(side=tk.LEFT)
                    tk.Label(gpu_frame, text=f"{gpu_percent:.1f}%", font=("Noto Sans CJK KR", 22, "bold"),
                            bg=COLOR_PANEL, fg=gpu_color, anchor="e").pack(side=tk.RIGHT)
                except:
                    pass

                # Memory Usage
                mem = psutil.virtual_memory()
                mem_percent = mem.percent
                mem_color = COLOR_OK if mem_percent < 70 else COLOR_WARNING if mem_percent < 90 else COLOR_ERROR

                mem_frame = tk.Frame(info_frame, bg=COLOR_PANEL)
                mem_frame.pack(pady=10, padx=20, fill=tk.X)
                tk.Label(mem_frame, text="메모리 사용률:", font=MEDIUM_FONT,
                        bg=COLOR_PANEL, fg=COLOR_TEXT, anchor="w").pack(side=tk.LEFT)
                tk.Label(mem_frame, text=f"{mem_percent:.1f}%", font=("Noto Sans CJK KR", 22, "bold"),
                        bg=COLOR_PANEL, fg=mem_color, anchor="e").pack(side=tk.RIGHT)

                # Disk Usage
                disk = psutil.disk_usage('/')
                disk_percent = disk.percent
                disk_color = COLOR_OK if disk_percent < 70 else COLOR_WARNING if disk_percent < 90 else COLOR_ERROR

                disk_frame = tk.Frame(info_frame, bg=COLOR_PANEL)
                disk_frame.pack(pady=10, padx=20, fill=tk.X)
                tk.Label(disk_frame, text="디스크 사용률:", font=MEDIUM_FONT,
                        bg=COLOR_PANEL, fg=COLOR_TEXT, anchor="w").pack(side=tk.LEFT)
                tk.Label(disk_frame, text=f"{disk_percent:.1f}%", font=("Noto Sans CJK KR", 22, "bold"),
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
                        tk.Label(temp_frame, text=f"{temp_celsius:.1f}°C", font=("Noto Sans CJK KR", 22, "bold"),
                                bg=COLOR_PANEL, fg=temp_color, anchor="e").pack(side=tk.RIGHT)
                except:
                    pass

                # System uptime
                uptime_seconds = int(psutil.boot_time())
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
                 bg=COLOR_INFO, fg="white", relief=tk.FLAT).pack(pady=20)

        print("[PC상태] PC 상태 창 열림")

    def open_vibration_check(self):
        """Open vibration sensor monitoring program"""
        import subprocess
        import os

        vibration_script = "/home/dkuyj/jetson-camera-monitor/vibration_sensor_simple.py"
        vibration_dir = "/home/dkuyj/jetson-camera-monitor"

        if not os.path.exists(vibration_script):
            print(f"[진동] 오류: {vibration_script} 파일이 없습니다")
            return

        try:
            # 진동 센서 프로그램을 별도 프로세스로 실행 (작업 디렉토리 지정)
            proc = subprocess.Popen(["python3", vibration_script], cwd=vibration_dir)
            self.child_processes.append(proc)
            print("[진동] 진동 센서 프로그램 실행")
        except Exception as e:
            print(f"[진동] 실행 오류: {e}")

    def open_settings(self):
        """Open settings dialog (placeholder)"""
        messagebox.showinfo("설정", "설정 기능은 준비 중입니다.\nconfig_jetson2.json 파일을 직접 수정하세요.")

    def select_food_type(self):
        """Show food type selection dialog"""
        # Create popup window
        dialog = tk.Toplevel(self.root)
        dialog.title("음식 종류 선택")
        dialog.geometry("500x450")
        dialog.configure(bg=COLOR_BG)
        dialog.transient(self.root)
        dialog.grab_set()

        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (500 // 2)
        y = (dialog.winfo_screenheight() // 2) - (450 // 2)
        dialog.geometry(f"500x450+{x}+{y}")

        selected_food = {"value": None}

        # Title
        tk.Label(dialog, text="[ 음식 종류 선택 ]", font=LARGE_FONT,
                bg=COLOR_BG, fg=COLOR_TEXT).pack(pady=20)

        # Buttons frame
        button_frame = tk.Frame(dialog, bg=COLOR_BG)
        button_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)

        # Food type buttons
        food_icons = {
            "chicken": "🍗",
            "shrimp": "🍤",
            "potato": "🥔",
            "dumpling": "🥟",
            "pork_cutlet": "🥩",
            "fish": "🐟"
        }

        food_names = {
            "chicken": "치킨",
            "shrimp": "새우",
            "potato": "감자",
            "dumpling": "만두",
            "pork_cutlet": "돈까스",
            "fish": "생선"
        }

        def select(food_type):
            selected_food["value"] = food_type
            dialog.destroy()

        for idx, food in enumerate(FOOD_TYPES):
            icon = food_icons.get(food, "🍴")
            name = food_names.get(food, food)

            btn = tk.Button(
                button_frame,
                text=f"{icon} {name}",
                font=("Noto Sans CJK KR", 18, "bold"),
                bg=COLOR_BUTTON,
                fg="white",
                activebackground=COLOR_BUTTON_HOVER,
                command=lambda f=food: select(f),
                width=15,
                height=2,
                relief=tk.FLAT
            )
            btn.pack(pady=8)

        # Cancel button
        tk.Button(dialog, text="[ 취소 ]", font=MEDIUM_FONT,
                 command=dialog.destroy, width=15,
                 bg="#95A5A6", fg="white", relief=tk.FLAT).pack(pady=20)

        dialog.wait_window()
        return selected_food["value"]

    def mark_completion_manual(self):
        """Manually mark completion point (button click)"""
        if not self.data_collection_active:
            return

        if self.collection_completion_marked:
            messagebox.showinfo("알림", "이미 완료 시점이 마킹되었습니다!")
            return

        from datetime import datetime
        elapsed = (datetime.now() - self.collection_start_time).total_seconds()

        self.collection_completion_marked = True
        self.collection_completion_time = datetime.now()
        self.collection_completion_info = {
            "method": "manual",
            "timestamp": self.collection_completion_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "elapsed_time_sec": elapsed,
            "frame_index": self.collection_frame_counter,
            "oil_temp_left": self.oil_temp_left,
            "oil_temp_right": self.oil_temp_right,
            "probe_temp_left": self.probe_temp_left,
            "probe_temp_right": self.probe_temp_right
        }

        # Update UI
        self.btn_mark_completion.config(state=tk.DISABLED, bg="#27AE60", text="✅ 완료됨")
        self.collection_status_label.config(
            text=f"수집 중 [{self.current_food_type}] - 완료 마킹됨 ({elapsed:.0f}초)",
            fg="#27AE60"
        )

        print(f"[완료마킹] 수동 마킹: {elapsed:.1f}초")
        print(f"[완료마킹] 탐침온도: L={self.probe_temp_left}°C, R={self.probe_temp_right}°C")

    def mark_completion_auto(self, position, probe_temp):
        """Automatically mark completion when probe temp reaches target"""
        if not self.data_collection_active:
            return

        if self.collection_completion_marked:
            return  # Already marked

        from datetime import datetime
        elapsed = (datetime.now() - self.collection_start_time).total_seconds()

        self.collection_completion_marked = True
        self.collection_completion_time = datetime.now()
        self.collection_completion_info = {
            "method": "auto",
            "trigger": f"probe_temp_{position}",
            "trigger_value": probe_temp,
            "timestamp": self.collection_completion_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "elapsed_time_sec": elapsed,
            "frame_index": self.collection_frame_counter,
            "oil_temp_left": self.oil_temp_left,
            "oil_temp_right": self.oil_temp_right,
            "probe_temp_left": self.probe_temp_left,
            "probe_temp_right": self.probe_temp_right
        }

        # Update UI
        self.btn_mark_completion.config(state=tk.DISABLED, bg="#27AE60", text="✅ 완료됨")
        self.collection_status_label.config(
            text=f"수집 중 [{self.current_food_type}] - 자동 완료 ({elapsed:.0f}초)",
            fg="#27AE60"
        )

        print(f"[완료마킹] 자동 마킹 ({position}): {elapsed:.1f}초")
        print(f"[완료마킹] 탐침온도: {probe_temp}°C (목표: {TARGET_PROBE_TEMP}°C)")

    def start_frying_ai(self):
        """Start Frying AI processing"""
        self.frying_running = True
        self.btn_start_frying.config(state=tk.DISABLED)
        self.btn_stop_frying.config(state=tk.NORMAL)
        self.frying_left_status.config(text="튀김 AI 작동 중")
        self.frying_right_status.config(text="튀김 AI 작동 중")
        print("[튀김 AI] 시작됨 (GPU 가속)")

    def stop_frying_ai(self):
        """Stop Frying AI processing"""
        self.frying_running = False
        self.btn_start_frying.config(state=tk.NORMAL)
        self.btn_stop_frying.config(state=tk.DISABLED)
        self.frying_left_status.config(text="대기 중")
        self.frying_right_status.config(text="대기 중")
        print("[튀김 AI] 중지됨")

    def start_observe_ai(self):
        """Start Observe_add AI processing"""
        self.observe_running = True
        self.btn_start_observe.config(state=tk.DISABLED)
        self.btn_stop_observe.config(state=tk.NORMAL)
        self.observe_left_status.config(text="바켓 감지 작동 중")
        self.observe_right_status.config(text="바켓 감지 작동 중")
        print("[바켓 감지] 시작됨")

    def stop_observe_ai(self):
        """Stop Observe_add AI processing"""
        self.observe_running = False
        self.btn_start_observe.config(state=tk.NORMAL)
        self.btn_stop_observe.config(state=tk.DISABLED)
        self.observe_left_status.config(text="대기 중")
        self.observe_right_status.config(text="대기 중")
        self.observe_left_votes.clear()
        self.observe_right_votes.clear()
        self.observe_left_state = None
        self.observe_right_state = None
        print("[바켓 감지] 중지됨")

    def start_data_collection(self):
        """Start manual data collection"""
        from datetime import datetime
        import os

        # Show food type selection dialog
        food_type = self.select_food_type()
        if food_type is None:
            return  # User cancelled

        self.current_food_type = food_type

        # Create session ID
        self.collection_session_id = datetime.now().strftime("session_%Y%m%d_%H%M%S")
        self.collection_start_time = datetime.now()
        self.collection_frame_counter = 0

        # Create session directories
        base_dir = os.path.expanduser("~/AI_Data")
        self.frying_session_dir = os.path.join(base_dir, "FryingData", self.collection_session_id)
        self.bucket_session_dir = os.path.join(base_dir, "BucketData", self.collection_session_id)

        for cam_idx in [0, 1]:
            os.makedirs(os.path.join(self.frying_session_dir, f"camera_{cam_idx}"), mode=0o755, exist_ok=True)
        for cam_idx in [2, 3]:
            os.makedirs(os.path.join(self.bucket_session_dir, f"camera_{cam_idx}"), mode=0o755, exist_ok=True)

        # Reset completion flags
        self.collection_completion_marked = False
        self.collection_completion_time = None
        self.collection_completion_info = {}

        # Update flags
        self.data_collection_active = True
        self.collection_metadata = []  # Reset metadata
        self.btn_start_collection.config(state=tk.DISABLED)
        self.btn_mark_completion.config(state=tk.NORMAL)
        self.btn_stop_collection.config(state=tk.NORMAL)
        self.collection_status_label.config(text=f"수집 중 [{food_type}]: {self.collection_session_id}", fg="#9B59B6")

        print(f"[데이터수집] 시작: {self.collection_session_id}")
        print(f"[데이터수집] 음식 종류: {self.current_food_type}")
        print(f"[데이터수집] 저장 경로: {base_dir}/AI_Data/")
        print(f"[데이터수집] MQTT 메타데이터 수집 활성화")

    def stop_data_collection(self):
        """Stop manual data collection"""
        from datetime import datetime
        import json

        if not self.data_collection_active:
            return

        self.data_collection_active = False
        duration = (datetime.now() - self.collection_start_time).total_seconds()

        # Organize temperature data by time
        temperature_timeline = []
        for item in self.collection_metadata:
            if item["type"] in ["oil_temperature", "probe_temperature"]:
                # Check if timestamp already exists
                existing = next((x for x in temperature_timeline if x["timestamp"] == item["timestamp"]), None)
                if existing:
                    # Add to existing entry
                    key = f"{item['type'].replace('_temperature', '_temp')}_{item['position']}"
                    existing[key] = item["value"]
                else:
                    # Create new entry
                    new_entry = {"timestamp": item["timestamp"]}
                    key = f"{item['type'].replace('_temperature', '_temp')}_{item['position']}"
                    new_entry[key] = item["value"]
                    temperature_timeline.append(new_entry)

        # Save session info with improved metadata
        session_info = {
            "session_id": self.collection_session_id,
            "food_type": self.current_food_type,
            "start_time": self.collection_start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "duration_sec": duration,
            "collection_interval": self.collection_interval,

            "completion_info": self.collection_completion_info if self.collection_completion_marked else None,
            "completion_marked": self.collection_completion_marked,

            "cameras_used": [0, 1, 2, 3],
            "total_frames_saved": self.collection_frame_counter,

            "camera_config": {
                "resolution": {
                    "width": config.get("camera_width", 1280),
                    "height": config.get("camera_height", 720)
                },
                "fps": config.get("camera_fps", 30)
            },

            "temperature_timeline": temperature_timeline,
            "raw_metadata": self.collection_metadata,
            "metadata_count": len(self.collection_metadata)
        }

        # Save to both directories
        for dir_path in [self.frying_session_dir, self.bucket_session_dir]:
            info_path = os.path.join(dir_path, "session_info.json")
            with open(info_path, 'w', encoding='utf-8') as f:
                json.dump(session_info, f, indent=2, ensure_ascii=False)

        # Update GUI
        self.btn_start_collection.config(state=tk.NORMAL)
        self.btn_mark_completion.config(state=tk.DISABLED, bg="#F39C12", text="✅ 완료 마킹")
        self.btn_stop_collection.config(state=tk.DISABLED)
        self.collection_status_label.config(text="수집: 대기 중", fg=COLOR_TEXT)

        print(f"[데이터수집] 종료: {self.collection_frame_counter}장 저장, {duration:.1f}초")
        print(f"[데이터수집] 음식 종류: {self.current_food_type}")
        print(f"[데이터수집] 완료 마킹: {'예' if self.collection_completion_marked else '아니오'}")
        print(f"[데이터수집] MQTT 메타데이터: {len(self.collection_metadata)}개 수집")

        # Show summary
        from tkinter import messagebox
        completion_text = ""
        if self.collection_completion_marked:
            elapsed = self.collection_completion_info.get("elapsed_time_sec", 0)
            method = self.collection_completion_info.get("method", "unknown")
            completion_text = f"\n완료 마킹: {method} ({elapsed:.1f}초)"

        messagebox.showinfo(
            "데이터 수집 완료",
            f"세션: {self.collection_session_id}\n"
            f"음식: {self.current_food_type}\n\n"
            f"총 저장: {self.collection_frame_counter}장\n"
            f"수집 시간: {duration:.1f}초{completion_text}\n"
            f"MQTT 메타데이터: {len(self.collection_metadata)}개\n\n"
            f"저장 경로:\n{os.path.expanduser('~/AI_Data/')}"
        )

        # Reset session
        self.collection_session_id = None
        self.collection_start_time = None
        self.current_food_type = "unknown"

    def save_collection_data(self, frying_left, frying_right, observe_left, observe_right):
        """Save frames from all 4 cameras during data collection"""
        if not self.data_collection_active:
            return

        from datetime import datetime
        import cv2

        timestamp = datetime.now().strftime("%H%M%S_%f")[:-3]  # HHMMss_mmm

        # Save frying cameras (camera 0, 1)
        for cam_idx, frame in [(0, frying_left), (1, frying_right)]:
            if frame is not None:
                save_path = os.path.join(
                    self.frying_session_dir,
                    f"camera_{cam_idx}",
                    f"cam{cam_idx}_{timestamp}.jpg"
                )
                cv2.imwrite(save_path, frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])

        # Save bucket cameras (camera 2, 3)
        for cam_idx, frame in [(2, observe_left), (3, observe_right)]:
            if frame is not None:
                save_path = os.path.join(
                    self.bucket_session_dir,
                    f"camera_{cam_idx}",
                    f"cam{cam_idx}_{timestamp}.jpg"
                )
                cv2.imwrite(save_path, frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])

        self.collection_frame_counter += 1

        # Update status
        if self.collection_frame_counter % 10 == 0:
            self.collection_status_label.config(
                text=f"수집 중: {self.collection_frame_counter}장 저장됨"
            )
            print(f"[데이터수집] {self.collection_frame_counter}장 저장됨")

    def toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        self.is_fullscreen = not self.is_fullscreen
        self.root.attributes('-fullscreen', self.is_fullscreen)

    def exit_fullscreen(self):
        """Exit fullscreen mode"""
        self.is_fullscreen = False
        self.root.attributes('-fullscreen', False)

    def on_close(self):
        """Cleanup and close application - 백그라운드에서 정리"""
        # messagebox를 위한 최상위 창 생성
        dialog = tk.Toplevel(self.root)
        dialog.withdraw()  # 숨기기
        dialog.attributes('-topmost', True)  # 항상 최상위

        # messagebox를 이 창의 자식으로 표시
        result = messagebox.askokcancel("종료", "프로그램을 종료하시겠습니까?", parent=dialog)
        dialog.destroy()

        if result:
            print("[종료] 시스템 종료 중...")
            self.running = False

            # 백그라운드 스레드에서 정리 작업 수행 (UI 프리징 방지)
            def cleanup_and_exit():
                try:
                    # Cleanup child processes (진동센서 등)
                    for proc in self.child_processes:
                        try:
                            if proc.poll() is None:
                                print(f"[종료] 자식 프로세스 종료 중... (PID: {proc.pid})")
                                proc.terminate()
                                try:
                                    proc.wait(timeout=1)  # 1초만 대기
                                except:
                                    proc.kill()
                        except Exception as e:
                            print(f"[종료] 자식 프로세스 종료 오류: {e}")

                    # Stop cameras
                    if self.frying_left_cap:
                        try:
                            self.frying_left_cap.stop()
                        except:
                            pass
                    if self.frying_right_cap:
                        try:
                            self.frying_right_cap.stop()
                        except:
                            pass
                    if self.observe_left_cap:
                        try:
                            self.observe_left_cap.stop()
                        except:
                            pass
                    if self.observe_right_cap:
                        try:
                            self.observe_right_cap.stop()
                        except:
                            pass

                    # Disconnect MQTT
                    if self.mqtt_client:
                        try:
                            self.mqtt_client.disconnect()
                        except:
                            pass

                except Exception as e:
                    print(f"[종료] 정리 중 오류: {e}")
                finally:
                    # UI는 메인 스레드에서 종료
                    self.root.after(0, self._final_destroy)

            # 백그라운드 스레드 시작
            import threading
            cleanup_thread = threading.Thread(target=cleanup_and_exit, daemon=True)
            cleanup_thread.start()

    def _final_destroy(self):
        """최종 창 파괴 (메인 스레드에서 실행)"""
        try:
            self.root.quit()
            self.root.destroy()
        except:
            pass
        print("[종료] 프로그램 종료 완료")
        import sys
        sys.exit(0)


# =========================
# Main Entry Point
# =========================
if __name__ == "__main__":
    print("=" * 50)
    print("Jetson #2 - AI Monitoring System")
    print("=" * 50)

    root = tk.Tk()
    app = JetsonIntegratedApp(root)
    root.mainloop()
