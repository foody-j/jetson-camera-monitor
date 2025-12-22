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
import tkinter.font as tkfont
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
import socket

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.communication.mqtt_client import MQTTClient
from src.core.system_info import SystemInfo

# Import GStreamer camera wrapper (optimized for UYVY format)
from gst_camera import GstCamera

# Import GPIO for Relay control
import Jetson.GPIO as GPIO

# Import Night Review module
from night_review_module import NightReviewManager

# =========================
# Load Configuration
# =========================
def load_config(config_path="config.json"):
    """Load configuration from JSON file"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_ip_address():
    """Get local IP address"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "unknown"

# =========================
# Popup Helper Functions
# =========================
def show_popup_topmost(func, title, message, **kwargs):
    """Show messagebox always on top"""
    # Create temporary toplevel window
    temp = tk.Toplevel()
    temp.withdraw()
    temp.attributes('-topmost', True)
    temp.lift()
    temp.focus_force()

    try:
        result = func(title, message, parent=temp, **kwargs)
    finally:
        temp.destroy()

    return result

def showinfo_topmost(title, message):
    """Show info dialog always on top"""
    return show_popup_topmost(messagebox.showinfo, title, message)

def showwarning_topmost(title, message):
    """Show warning dialog always on top"""
    return show_popup_topmost(messagebox.showwarning, title, message)

def showerror_topmost(title, message):
    """Show error dialog always on top"""
    return show_popup_topmost(messagebox.showerror, title, message)

def askokcancel_topmost(title, message):
    """Show ok/cancel dialog always on top"""
    return show_popup_topmost(messagebox.askokcancel, title, message)

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
CAMERA_PERSON_ENABLED = config.get('camera_person_enabled', True)
CAMERA_INDEX = config['camera_index']
CAMERA_TYPE = config.get('camera_type', 'usb')  # Default to USB if not specified
CAMERA_RESOLUTION = config.get('camera_resolution', {'width': 640, 'height': 360})
CAMERA_FPS = config.get('camera_fps', 30)
YOLO_CONF = config['yolo_confidence']
DETECTION_HOLD_SEC = config['detection_hold_sec']
NIGHT_CHECK_MINUTES = config['night_check_minutes']
MOTION_MIN_AREA = config['motion_min_area']
SNAPSHOT_DIR = config['snapshot_dir']
SAVE_COOLDOWN_SEC = config['snapshot_cooldown_sec']

# Device Identification
DEVICE_ID = config.get('device_id', 'jetson1')
DEVICE_NAME = config.get('device_name', 'Jetson1_StirFry_Station')
DEVICE_LOCATION = config.get('device_location', 'kitchen_stirfry')

# ==============================================================================
# MQTT 토픽 정리
# ==============================================================================
# [발행] Jetson1 → 로봇PC
#   - jetson1/status : Jetson1 통합 상태 (AI모드, 릴레이, 볶음 등)
#
# [구독] 로봇PC → Jetson1
#   - HR/Status : 로봇 PC 상태 (솥 온도, 레시피, 프로세스 등)
#   - stirfry/pot1/food_type, stirfry/pot1/control : 볶음솥1 제어
#   - stirfry/pot2/food_type, stirfry/pot2/control : 볶음솥2 제어
# ==============================================================================

# MQTT Configuration
MQTT_ENABLED = config.get('mqtt_enabled', False)
MQTT_BROKER = config.get('mqtt_broker', 'localhost')
MQTT_PORT = config.get('mqtt_port', 1883)
MQTT_QOS = config.get('mqtt_qos', 1)
MQTT_CLIENT_ID = config.get('mqtt_client_id', 'jetson1_ai')
MQTT_PUBLISH_INTERVAL = config.get('mqtt_publish_interval', 5)  # seconds

# MQTT 발행 토픽 (Jetson1 → 로봇PC) - 단일 토픽으로 통합
MQTT_TOPIC_STATUS = config.get('mqtt_topic_status', 'jetson1/status')

# MQTT 구독 토픽 (로봇PC → Jetson1)
MQTT_TOPIC_ROBOT_STATUS = config.get('mqtt_topic_robot_status', 'HR/Status')
MQTT_TOPIC_STIRFRY_POT1_FOOD_TYPE = config.get('mqtt_topic_stirfry_pot1_food_type', 'stirfry/pot1/food_type')
MQTT_TOPIC_STIRFRY_POT1_CONTROL = config.get('mqtt_topic_stirfry_pot1_control', 'stirfry/pot1/control')
MQTT_TOPIC_STIRFRY_POT2_FOOD_TYPE = config.get('mqtt_topic_stirfry_pot2_food_type', 'stirfry/pot2/food_type')
MQTT_TOPIC_STIRFRY_POT2_CONTROL = config.get('mqtt_topic_stirfry_pot2_control', 'stirfry/pot2/control')
# AI Mode Setting
AI_MODE_ENABLED = config.get('ai_mode_enabled', False)

# Vibration Sensor Settings
VIBRATION_TEST_MODE = config.get('vibration_test_mode', False)  # True=VibrationRequest 시 즉시 NORMAL 응답

# Relay Control Settings
RELAY_MODE = config.get('relay_mode', 'pulse')
AUTO_RELAY_ENABLED = config.get('auto_relay_enabled', True)
JETSON2_SHUTDOWN_DELAY_SEC = config.get('jetson2_shutdown_delay_sec', 3)

# Stir-fry monitoring configuration - TWO CAMERAS
STIRFRY_LEFT_ENABLED = config.get('stirfry_left_enabled', True)
STIRFRY_LEFT_CAMERA_TYPE = config.get('stirfry_left_camera_type', 'usb')
STIRFRY_LEFT_CAMERA_INDEX = config.get('stirfry_left_camera_index', 1)  # Video1 (CN5)

STIRFRY_RIGHT_ENABLED = config.get('stirfry_right_enabled', True)
STIRFRY_RIGHT_CAMERA_TYPE = config.get('stirfry_right_camera_type', 'usb')
STIRFRY_RIGHT_CAMERA_INDEX = config.get('stirfry_right_camera_index', 2)  # Video2 (CN6)

STIRFRY_SAVE_DIR = config.get('stirfry_save_dir', 'StirFry_Data')

# Stir-fry save settings (configurable)
STIRFRY_SAVE_RESOLUTION = config.get('stirfry_save_resolution', {'width': 960, 'height': 768})
STIRFRY_JPEG_QUALITY = config.get('stirfry_jpeg_quality', 70)
STIRFRY_FRAME_SKIP = config.get('stirfry_frame_skip', 6)
RECORDING_DELAY_AFTER_DISCHARGE = config.get('recording_delay_after_discharge', 20)  # 배출 후 추가 녹화 시간 (초)

# Motion detection & YOLO parameters (configurable via config.json)
YOLO_IMGSZ = config.get('yolo_imgsz', 416)  # YOLO 입력 이미지 크기 (높을수록 정확, 느림)
MOG2_HISTORY = 500  # MOG2 배경 모델 히스토리 프레임 수
MOG2_VARTHRESH = config.get('mog2_varthresh', 16)  # MOG2 분산 임계값 (낮을수록 민감)
BINARY_THRESH = config.get('binary_thresh', 200)  # 이진화 임계값 (높을수록 덜 민감)
WARMUP_FRAMES = 30  # 카메라 워밍업 프레임 수

# GUI Configuration - from config.json (768x1024 세로 모드)
WINDOW_WIDTH = config.get('window_width', 768)
WINDOW_HEIGHT = config.get('window_height', 1024)
FULLSCREEN_MODE = config.get('fullscreen', False)  # 전체화면 모드 설정
WINDOW_DECORATIONS = config.get('window_decorations', False)  # 창 테두리 표시 여부
# 폰트 이름 설정 - Segfault 방지를 위해 시스템 기본 폰트 사용 가능
# "Noto Sans CJK KR" 폰트가 세그폴트를 일으키면 "" (빈 문자열)로 변경
FONT_FAMILY = "TkDefaultFont"  # 시스템 기본 폰트 (빈 문자열은 segfault 유발)
LARGE_FONT = (FONT_FAMILY, config.get('font_large', 28), "bold")
MEDIUM_FONT = (FONT_FAMILY, config.get('font_medium', 20))
NORMAL_FONT = (FONT_FAMILY, config.get('font_normal', 16))
STATUS_FONT = (FONT_FAMILY, config.get('font_status', 18), "bold")
BUTTON_FONT = (FONT_FAMILY, config.get('font_button', 20), "bold")

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

# Check PyTorch CUDA availability for YOLO GPU acceleration
import torch
USE_CUDA = torch.cuda.is_available()
if USE_CUDA:
    print(f"[GPU] PyTorch CUDA 사용 가능! YOLO GPU 가속 활성화 ({torch.cuda.get_device_name(0)})")
else:
    print("[GPU] PyTorch CUDA 미지원 - YOLO는 CPU 모드로 실행")

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
        self.root.title("Jetson #1 - Integrated Monitoring System")
        self.running = True

        # Configure window (config에서 설정)
        self.root.configure(bg=COLOR_BG)

        # Window decorations (config에서 설정)
        if not WINDOW_DECORATIONS:
            self.root.overrideredirect(True)
            print(f"[디스플레이] 창 테두리 숨김")

        # Set window size and position
        if FULLSCREEN_MODE:
            # Fullscreen mode - 진짜 전체화면 속성 설정
            self.root.attributes('-fullscreen', True)
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            print(f"[디스플레이] 전체화면 모드 ({screen_width}x{screen_height})")
        else:
            # Windowed mode
            self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+0+0")
            print(f"[디스플레이] 창 모드 ({WINDOW_WIDTH}x{WINDOW_HEIGHT})")

        # Keyboard shortcuts
        self.root.bind('<F11>', lambda e: self.toggle_fullscreen())
        self.root.bind('<Escape>', lambda e: self.root.attributes('-fullscreen', False))

        # Close handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Initialize variables
        print("[초기화] 변수 초기화 중...", flush=True)
        self.mqtt_client = None
        self.mqtt_message_log = []  # 최근 MQTT 메시지 저장 (원본 보기용)
        self.mqtt_message_log_max = 50  # 최대 저장 개수
        self.system_info = SystemInfo(device_name="Jetson1", location="Kitchen")
        self.yolo_model = None
        self.device = 'cpu'  # Will be set to 'cuda' in init_yolo() if available

        # GStreamer cameras
        self.auto_cap = None
        self.stirfry_left_cap = None
        self.stirfry_right_cap = None

        # Subprocess tracking (진동센서 등)
        self.child_processes = []
        self.vibration_process = None  # 진동센서 프로세스 추적
        self.vibration_status = "IDLE"  # 진동센서 상태: IDLE, MEASURING, NORMAL, ABNORMAL

        # Stir-fry monitoring state - POT1 (left camera = camera_0)
        self.stirfry_pot1_recording = False  # 수동 시작
        self.stirfry_pot1_frame_count = 0
        self.stirfry_pot1_frame_skip_counter = 0
        self.stirfry_pot1_food_type = "unknown"
        self.stirfry_pot1_metadata = []
        self.stirfry_pot1_session_id = None
        self.stirfry_pot1_session_start_time = None

        # Stir-fry monitoring state - POT2 (right camera = camera_1)
        self.stirfry_pot2_recording = False  # 수동 시작
        self.stirfry_pot2_frame_count = 0
        self.stirfry_pot2_frame_skip_counter = 0
        self.stirfry_pot2_food_type = "unknown"
        self.stirfry_pot2_metadata = []
        self.stirfry_pot2_session_id = None
        self.stirfry_pot2_session_start_time = None

        # POT1 timeout (auto-stop if no message for N seconds)
        self.pot1_timeout_id = None
        self.pot1_timeout_seconds = 5  # 5초 동안 메시지 없으면 자동 중지

        # POT2 timeout (auto-stop if no message for N seconds)
        self.pot2_timeout_id = None
        self.pot2_timeout_seconds = 5  # 5초 동안 메시지 없으면 자동 중지

        # 배출 후 지연 종료 타이머
        self.pot1_discharge_timer_id = None
        self.pot2_discharge_timer_id = None

        # Manual stir-fry recording state (수동 녹화용)
        self.stirfry_recording = False
        self.stirfry_left_frame_count = 0
        self.stirfry_right_frame_count = 0
        self.stirfry_session_id = None
        self.stirfry_session_start_time = None
        self.stirfry_metadata = []
        self.current_stirfry_food_type = "unknown"

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

        # Relay control via GPIO
        self.relay_enabled = False  # Relay current state

        # OpenCV background subtractor
        self.kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        self.bg = cv2.createBackgroundSubtractorMOG2(
            history=MOG2_HISTORY, varThreshold=MOG2_VARTHRESH, detectShadows=True
        )

        print("[초기화] 변수 초기화 완료!", flush=True)

        # Detect screen size and build GUI
        self.detect_screen_size()

        # Pre-load fonts to avoid Segfault
        print("[초기화] 폰트 사전 로딩...")
        self._init_fonts()

        self.create_gui()

        # Initialize GPIO for Relay control
        print("[초기화] GPIO 릴레이 제어 초기화 중...")
        self.init_gpio()

        # Initialize cameras and YOLO
        print("[초기화] 카메라 및 YOLO 초기화 중...")
        self.init_mqtt()
        self.init_cameras()
        self.init_yolo()

        # Start update loops
        self.update_clock()
        self.update_auto_system()
        self.update_stirfry_left_camera()
        self.update_stirfry_right_camera()

        # Start periodic MQTT publishing
        if MQTT_ENABLED:
            self.publish_mqtt_periodic()

        # Initialize Night Review manager
        self.night_review_manager = NightReviewManager(self, config)
        if self.night_review_manager.enabled:
            print(f"[초기화] 야간 리뷰 활성화 (매일 {self.night_review_manager.review_time})")

        print("[초기화] 모든 시스템 초기화 완료!")

    def detect_screen_size(self):
        """Use configured window size for layout calculations"""
        # Use configured window dimensions
        self.screen_width = WINDOW_WIDTH
        self.screen_height = WINDOW_HEIGHT

        print(f"[디스플레이] 설정된 창 크기: {self.screen_width}x{self.screen_height}")

        # Detect orientation
        if self.screen_height > self.screen_width:
            self.is_vertical = True
            print("[디스플레이] 세로 방향 (Portrait) 모드")
        else:
            self.is_vertical = False
            print("[디스플레이] 가로 방향 (Landscape) 모드")

        # Calculate adaptive sizes based on configured height
        # Base: 1024px height (768x1024 display) → scale proportionally
        base_height = 1024
        scale_factor = self.screen_height / base_height

        # Ensure minimum scale for small screens
        if scale_factor < 0.7:
            scale_factor = 0.7
            print("[디스플레이] 최소 스케일 적용 (0.7)")

        # Store scale factor for layout calculations
        self.scale_factor = scale_factor

        # Calculate font sizes with scaling (optimized for 768x1024)
        self.large_font_size = max(20, int(config.get('font_large', 28) * scale_factor))
        self.medium_font_size = max(16, int(config.get('font_medium', 20) * scale_factor))
        self.normal_font_size = max(12, int(config.get('font_normal', 16) * scale_factor))
        self.status_font_size = max(14, int(config.get('font_status', 18) * scale_factor))
        self.button_font_size = max(16, int(config.get('font_button', 20) * scale_factor))

        # Apply dynamic fonts
        global LARGE_FONT, MEDIUM_FONT, NORMAL_FONT, STATUS_FONT, BUTTON_FONT
        LARGE_FONT = (FONT_FAMILY, self.large_font_size, "bold")
        MEDIUM_FONT = (FONT_FAMILY, self.medium_font_size)
        NORMAL_FONT = (FONT_FAMILY, self.normal_font_size)
        STATUS_FONT = (FONT_FAMILY, self.status_font_size, "bold")
        BUTTON_FONT = (FONT_FAMILY, self.button_font_size, "bold")

        print(f"[디스플레이] 폰트 크기 자동 조정: "
              f"대형={self.large_font_size}pt, "
              f"중간={self.medium_font_size}pt, "
              f"버튼={self.button_font_size}pt")

    def _init_fonts(self):
        """Pre-load fonts to avoid Segfault on first Label creation"""
        # 폰트 시스템 초기화를 완전히 건너뛰고 기본 폰트만 사용
        # tkfont.Font() 호출 자체가 Jetson에서 세그폴트를 일으킬 수 있음
        self.default_font = "TkDefaultFont"
        self.fonts = {}
        print(f"[폰트] 기본 폰트 사용: {self.default_font}")

    def create_gui(self):
        """Create the main GUI layout - AUTO-ADAPTIVE for any screen"""
        # Calculate adaptive dimensions (1줄 컴팩트 레이아웃)
        header_height = int(45 * self.scale_factor)  # 1줄 레이아웃 (90 → 45)
        padding = int(8 * self.scale_factor)

        # Top header - 1줄 컴팩트 레이아웃
        header_frame = tk.Frame(self.root, bg=COLOR_PANEL, height=header_height, bd=1, relief=tk.FLAT)
        header_frame.pack(fill=tk.X, padx=0, pady=0)
        header_frame.pack_propagate(False)

        # 1줄 레이아웃: 모든 요소를 가로로 배치
        # LEFT: MQTT 상태 (클릭 시 팝업)
        self.mqtt_status_btn = tk.Button(header_frame, text="● MQTT(0)",
                 font=(FONT_FAMILY, int(10 * self.scale_factor), "bold"),
                 command=self.show_mqtt_status_popup,
                 bg=COLOR_PANEL, fg=COLOR_ERROR,
                 relief=tk.FLAT, bd=0, cursor="hand2",
                 padx=5, pady=8)
        self.mqtt_status_btn.pack(side=tk.LEFT, padx=(5, 2))

        # 구분선
        tk.Frame(header_frame, width=1, bg=COLOR_TEXT_LIGHT).pack(side=tk.LEFT, fill=tk.Y, padx=3, pady=8)

        # 수집 상태 표시
        self.recording_status_label = tk.Label(header_frame, text="",
                                           font=(FONT_FAMILY, int(10 * self.scale_factor), "bold"),
                                           bg=COLOR_PANEL, fg=COLOR_ERROR)
        self.recording_status_label.pack(side=tk.LEFT, padx=3)

        # 구분선 (수집 상태용 - 수집 중일 때만 보임)
        self.recording_separator = tk.Frame(header_frame, width=1, bg=COLOR_TEXT_LIGHT)

        # 시스템 상태
        self.system_status_label = tk.Label(header_frame, text="정상",
                                           font=(FONT_FAMILY, int(10 * self.scale_factor)),
                                           bg=COLOR_PANEL, fg=COLOR_OK)
        self.system_status_label.pack(side=tk.LEFT, padx=3)

        # 구분선
        tk.Frame(header_frame, width=1, bg=COLOR_TEXT_LIGHT).pack(side=tk.LEFT, fill=tk.Y, padx=3, pady=8)

        # 날짜/시간 통합
        self.datetime_label = tk.Label(header_frame, text="--/-- --:--",
                                   font=(FONT_FAMILY, int(11 * self.scale_factor), "bold"),
                                   bg=COLOR_PANEL, fg=COLOR_INFO)
        self.datetime_label.pack(side=tk.LEFT, padx=3)

        # 구분선
        tk.Frame(header_frame, width=1, bg=COLOR_TEXT_LIGHT).pack(side=tk.LEFT, fill=tk.Y, padx=3, pady=8)

        # 연구실 이름 (축소)
        tk.Label(header_frame, text="SFLAB",
                font=(FONT_FAMILY, int(11 * self.scale_factor), "bold"),
                bg=COLOR_PANEL, fg=COLOR_ACCENT).pack(side=tk.LEFT, padx=3)

        # 구분선
        tk.Frame(header_frame, width=1, bg=COLOR_TEXT_LIGHT).pack(side=tk.LEFT, fill=tk.Y, padx=3, pady=8)

        # 디스크 용량 (축소)
        self.disk_label = tk.Label(header_frame, text="💾 --/--GB",
                                   font=(FONT_FAMILY, int(10 * self.scale_factor)),
                                   bg=COLOR_PANEL, fg=COLOR_TEXT_LIGHT)
        self.disk_label.pack(side=tk.LEFT, padx=3)

        # RIGHT: 버튼들 (오른쪽 정렬)
        # Settings button
        self.settings_btn = tk.Button(header_frame, text="설정",
                 font=(FONT_FAMILY, int(10 * self.scale_factor), "bold"),
                 command=self.handle_settings_tap, bg=COLOR_BUTTON, fg="white",
                 relief=tk.FLAT, bd=0, activebackground=COLOR_BUTTON_HOVER,
                 padx=6, pady=4)
        self.settings_btn.pack(side=tk.RIGHT, padx=2)

        # Vibration check toggle button
        self.vibration_check_btn = tk.Button(header_frame, text="진동",
                 font=(FONT_FAMILY, int(10 * self.scale_factor), "bold"),
                 command=self.toggle_vibration_check, bg=COLOR_INFO, fg="white",
                 relief=tk.FLAT, bd=0, activebackground=COLOR_BUTTON_HOVER,
                 padx=6, pady=4)
        self.vibration_check_btn.pack(side=tk.RIGHT, padx=2)

        # PC Status button
        tk.Button(header_frame, text="PC",
                 font=(FONT_FAMILY, int(10 * self.scale_factor), "bold"),
                 command=self.open_pc_status, bg="#00897B", fg="white",
                 relief=tk.FLAT, bd=0, activebackground="#00796B",
                 padx=6, pady=4).pack(side=tk.RIGHT, padx=2)

        # Bottom control bar FIRST (so it's always visible at bottom)
        self.create_bottom_control_bar()

        # Main content area - ADAPTIVE STACK (fills remaining space)
        self.content_frame = tk.Frame(self.root, bg=COLOR_BG)
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=padding, pady=int(padding/2))

        # Configure rows for 2-level layout (optimized for 768x1024)
        # Row 0: Auto panel (전체 너비)
        # Row 1: Stir-fry LEFT | RIGHT (2칸으로 나눔)
        self.content_frame.rowconfigure(0, weight=2)  # Auto panel (사람 감시) - 줄임
        self.content_frame.rowconfigure(1, weight=3)  # Stir-fry row - 늘림
        self.content_frame.rowconfigure(2, weight=0)  # Dev panel (hidden by default)
        self.content_frame.columnconfigure(0, weight=1)  # Left column
        self.content_frame.columnconfigure(1, weight=1)  # Right column

        # Panel 1: Auto-start/down (ROW 0, 전체 너비)
        self.create_auto_panel(self.content_frame)

        # Panel 2: Stir-fry monitoring LEFT (ROW 1, LEFT)
        self.create_stirfry_left_panel(self.content_frame)

        # Panel 3: Stir-fry monitoring RIGHT (ROW 1, RIGHT)
        self.create_stirfry_right_panel(self.content_frame)

        # Panel 4: Developer mode (ROW 3 - hidden by default)
        self.dev_panel = None
        self.create_dev_panel(self.content_frame)

        # Hidden shutdown button (shown after 5 taps on Settings button in header)
        # Note: Settings button is now in the header (top right)
        self.shutdown_btn = tk.Button(self.root, text="종료", font=BUTTON_FONT,
                 command=self.confirm_shutdown, bg=COLOR_ERROR, fg="white",
                 relief=tk.FLAT, bd=0, activebackground="#C62828")
        # Don't pack it - keep it hidden until 5 taps on Settings

    def create_auto_panel(self, parent):
        """Panel 1: Auto-start/down system - ROW 0 (전체 너비) - 세로 모드 최적화"""
        pad = int(6 * self.scale_factor)
        panel = tk.LabelFrame(parent, text="자동 ON/OFF (사람 감시)",
                             font=(FONT_FAMILY, int(self.large_font_size * 0.5), "bold"),
                             bg=COLOR_PANEL, fg=COLOR_ACCENT, bd=2, relief=tk.FLAT,
                             highlightbackground=COLOR_PANEL_BORDER, highlightthickness=1)
        panel.grid(row=0, column=0, columnspan=2, padx=pad, pady=int(pad/2), sticky="nsew")

        # Status indicators in HORIZONTAL layout (space efficient) - 축소
        status_container = tk.Frame(panel, bg=COLOR_PANEL)
        status_container.pack(pady=5, padx=5, fill=tk.X)

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

        # Camera preview area with camera number overlay - FIXED HEIGHT for 768x1024
        preview_height = int(280 * self.scale_factor)  # 줄임: 350 -> 280
        preview_container = tk.Frame(panel, bg="black", height=preview_height)
        preview_container.pack(pady=5, padx=5, fill=tk.X)
        preview_container.pack_propagate(False)  # Prevent container from expanding

        self.auto_preview_label = tk.Label(preview_container, text="[카메라 로딩 중...]",
                                          bg="black", fg="white", font=NORMAL_FONT)
        self.auto_preview_label.place(x=0, y=0, relwidth=1, relheight=1)

        # Camera number label (top-right)
        self.auto_cam_number_label = tk.Label(preview_container, text="Cam 3",
                                              bg="black", fg="yellow", font=(FONT_FAMILY, 10, "bold"))
        self.auto_cam_number_label.place(relx=1.0, rely=0, x=-5, y=5, anchor="ne")

    def create_stirfry_left_panel(self, parent):
        """Panel 2: Stir-fry monitoring LEFT - ROW 1, LEFT - 세로 모드 최적화"""
        pad = int(6 * self.scale_factor)
        panel = tk.LabelFrame(parent, text="볶음 모니터링 (왼쪽)",
                             font=(FONT_FAMILY, int(self.large_font_size * 0.5), "bold"),
                             bg=COLOR_PANEL, fg=COLOR_ACCENT, bd=2, relief=tk.FLAT,
                             highlightbackground=COLOR_PANEL_BORDER, highlightthickness=1)
        panel.grid(row=1, column=0, padx=pad, pady=int(pad/2), sticky="nsew")

        # Camera preview area - fixed height (늘림: 160 -> 220)
        preview_height = int(220 * self.scale_factor)
        preview_container = tk.Frame(panel, bg="black", height=preview_height)
        preview_container.pack(pady=3, padx=5, fill=tk.X)
        preview_container.pack_propagate(False)

        self.stirfry_left_preview_label = tk.Label(preview_container, text="[카메라 로딩 중...]",
                                                   bg="black", fg="white", font=NORMAL_FONT)
        self.stirfry_left_preview_label.place(x=0, y=0, relwidth=1, relheight=1)

        # Camera number label (top-right)
        self.stirfry_left_cam_number_label = tk.Label(preview_container, text="Cam 0",
                                                      bg="black", fg="yellow", font=(FONT_FAMILY, 10, "bold"))
        self.stirfry_left_cam_number_label.place(relx=1.0, rely=0, x=-5, y=5, anchor="ne")

        # Status info - 축소
        info_frame = tk.Frame(panel, bg=COLOR_PANEL)
        info_frame.pack(pady=3, fill=tk.X)

        self.stirfry_left_count_label = tk.Label(info_frame, text="저장: 0장",
                                                 font=(FONT_FAMILY, int(self.medium_font_size * 0.9)),
                                                 bg=COLOR_PANEL, fg=COLOR_TEXT)
        self.stirfry_left_count_label.pack(pady=2)

    def create_stirfry_right_panel(self, parent):
        """Panel 3: Stir-fry monitoring RIGHT - ROW 1, RIGHT - 세로 모드 최적화"""
        pad = int(6 * self.scale_factor)
        panel = tk.LabelFrame(parent, text="볶음 모니터링 (오른쪽)",
                             font=(FONT_FAMILY, int(self.large_font_size * 0.5), "bold"),
                             bg=COLOR_PANEL, fg=COLOR_ACCENT, bd=2, relief=tk.FLAT,
                             highlightbackground=COLOR_PANEL_BORDER, highlightthickness=1)
        panel.grid(row=1, column=1, padx=pad, pady=int(pad/2), sticky="nsew")

        # Camera preview area - fixed height (늘림: 160 -> 220)
        preview_height = int(220 * self.scale_factor)
        preview_container = tk.Frame(panel, bg="black", height=preview_height)
        preview_container.pack(pady=3, padx=5, fill=tk.X)
        preview_container.pack_propagate(False)

        self.stirfry_right_preview_label = tk.Label(preview_container, text="[카메라 로딩 중...]",
                                                    bg="black", fg="white", font=NORMAL_FONT)
        self.stirfry_right_preview_label.place(x=0, y=0, relwidth=1, relheight=1)

        # Camera number label (top-right)
        self.stirfry_right_cam_number_label = tk.Label(preview_container, text="Cam 1",
                                                       bg="black", fg="yellow", font=(FONT_FAMILY, 10, "bold"))
        self.stirfry_right_cam_number_label.place(relx=1.0, rely=0, x=-5, y=5, anchor="ne")

        # Status info - 축소
        info_frame = tk.Frame(panel, bg=COLOR_PANEL)
        info_frame.pack(pady=3, fill=tk.X)

        self.stirfry_right_count_label = tk.Label(info_frame, text="저장: 0장",
                                                  font=(FONT_FAMILY, int(self.medium_font_size * 0.9)),
                                                  bg=COLOR_PANEL, fg=COLOR_TEXT)
        self.stirfry_right_count_label.pack(pady=2)

    def create_bottom_control_bar(self):
        """하단 컨트롤 바 (녹화 버튼들) - 세로 모드 최적화"""
        control_bar = tk.Frame(self.root, bg=COLOR_PANEL, bd=1, relief=tk.FLAT,
                              highlightbackground=COLOR_PANEL_BORDER, highlightthickness=1)
        control_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=0, pady=0)

        btn_container = tk.Frame(control_bar, bg=COLOR_PANEL)
        btn_container.pack(pady=4, padx=5, fill=tk.X)

        self.stirfry_start_btn = tk.Button(btn_container, text="녹화 시작",
                                          font=(FONT_FAMILY, int(self.button_font_size * 0.7), "bold"),
                                          command=self.start_stirfry_recording,
                                          bg=COLOR_OK, fg="white", relief=tk.FLAT, bd=0,
                                          activebackground="#00B248", height=1)
        self.stirfry_start_btn.pack(side=tk.LEFT, padx=3, fill=tk.BOTH, expand=True)

        self.stirfry_stop_btn = tk.Button(btn_container, text="녹화 중지",
                                         font=(FONT_FAMILY, int(self.button_font_size * 0.7), "bold"),
                                         command=self.stop_stirfry_recording,
                                         bg=COLOR_ERROR, fg="white", state=tk.DISABLED,
                                         relief=tk.FLAT, bd=0, activebackground="#C62828", height=1)
        self.stirfry_stop_btn.pack(side=tk.LEFT, padx=3, fill=tk.BOTH, expand=True)

        tk.Button(btn_container, text="종료",
                 font=(FONT_FAMILY, int(self.button_font_size * 0.7), "bold"),
                 command=self.on_closing,
                 bg="#424242", fg="white", relief=tk.FLAT, bd=0,
                 activebackground="#616161", height=1).pack(side=tk.LEFT, padx=3, fill=tk.BOTH, expand=True)

        # Developer mode button
        self.dev_mode_btn = tk.Button(btn_container, text="개발자 모드",
                 font=(FONT_FAMILY, int(self.button_font_size * 0.7), "bold"),
                 command=self.toggle_developer_mode,
                 bg="#607D8B", fg="white", relief=tk.FLAT, bd=0,
                 activebackground="#546E7A", height=1)
        self.dev_mode_btn.pack(side=tk.LEFT, padx=3, fill=tk.BOTH, expand=True)

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

        # Night review button - manually trigger review
        tk.Button(scrollable_frame, text="🌙 야간 리뷰 보기", font=BUTTON_FONT,
                 command=self.show_night_review, bg="#5C6BC0", fg="white",
                 relief=tk.FLAT, bd=0, activebackground="#3F51B5").pack(pady=10, padx=20, fill=tk.X)

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
            # Show developer panel (ROW 2, 전체 너비)
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
        showinfo_topmost("테스트 모드", "스냅샷 모드가 즉시 시작되었습니다.\n모션 감지 시 자동 저장됩니다.")

    def show_night_review(self):
        """Manually trigger night review window (developer mode)"""
        if hasattr(self, 'night_review_manager'):
            print("[개발자] 야간 리뷰 수동 실행")
            self.night_review_manager.show_review()
        else:
            showwarning_topmost("오류", "야간 리뷰 모듈이 초기화되지 않았습니다.")

    # =========================
    # Initialization
    # =========================
    def init_gpio(self):
        """Initialize GPIO for 24V Omron Relay control (via ULN2803)"""
        try:
            GPIO.setmode(GPIO.BOARD)
            GPIO.setup(29, GPIO.OUT, initial=GPIO.LOW)  # Pin 29 for Relay control
            GPIO.setup(31, GPIO.OUT, initial=GPIO.LOW)  # Pin 31 for Relay control
            print("[GPIO] Pin 29, 31 initialized for Relay control (초기 상태: OFF)")

            # Relay control mode: 'pulse' or 'continuous'
            self.relay_mode = config.get('relay_mode', 'pulse')  # Default: pulse mode
            print(f"[GPIO] Relay mode: {self.relay_mode}")
        except Exception as e:
            print(f"[GPIO] 초기화 실패: {e}")

    def relay_turn_on(self, publish_to_jetson2=True):
        """Turn on 24V Omron Relay (제어 PC ON)

        Args:
            publish_to_jetson2: If True, publish relay status to Jetson #2 immediately.
                               If False, caller must manually call publish_relay_status() later.
        """
        if not self.relay_enabled:
            try:
                if self.relay_mode == 'pulse':
                    # Pulse mode: Pin 31 (ON signal) -> HIGH -> wait -> LOW
                    GPIO.output(31, GPIO.HIGH)
                    time.sleep(0.2)  # 200ms pulse
                    GPIO.output(31, GPIO.LOW)
                    print("=" * 50)
                    print("제어 PC ON (Pin 31 펄스 신호)")
                    print("=" * 50)
                else:
                    # Continuous mode: Keep HIGH
                    GPIO.output(31, GPIO.HIGH)
                    print("=" * 50)
                    print("제어 PC ON (Pin 31 계속 HIGH)")
                    print("=" * 50)

                self.relay_enabled = True

                # Publish relay status to MQTT for Jetson #2 (optional)
                if publish_to_jetson2:
                    self.publish_relay_status("ON")

            except Exception as e:
                print(f"[GPIO] Relay ON 실패: {e}")

    def relay_turn_off(self):
        """Turn off 24V Omron Relay (제어 PC OFF)"""
        if self.relay_enabled:
            try:
                if self.relay_mode == 'pulse':
                    # Pulse mode: Pin 29 (OFF signal) -> HIGH -> wait -> LOW
                    GPIO.output(29, GPIO.HIGH)
                    time.sleep(0.2)  # 200ms pulse
                    GPIO.output(29, GPIO.LOW)
                    print("=" * 50)
                    print("제어 PC OFF (Pin 29 펄스 신호)")
                    print("=" * 50)
                else:
                    # Continuous mode: Set LOW
                    GPIO.output(29, GPIO.LOW)
                    print("=" * 50)
                    print("제어 PC OFF (Pin 29 LOW)")
                    print("=" * 50)

                self.relay_enabled = False

                # Publish relay status to MQTT for Jetson #2
                self.publish_relay_status("OFF")

            except Exception as e:
                print(f"[GPIO] Relay OFF 실패: {e}")

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

            # Connect to broker FIRST
            if self.mqtt_client.connect(blocking=True, timeout=5.0):
                print(f"[MQTT] 연결 성공: {MQTT_BROKER}:{MQTT_PORT}")
                print(f"[MQTT] Device: {DEVICE_ID} ({DEVICE_NAME}) @ {get_ip_address()}")

                # Subscribe AFTER connection
                self.mqtt_client.subscribe(MQTT_TOPIC_STIRFRY_POT1_FOOD_TYPE, self.on_stirfry_pot1_food_type)
                self.mqtt_client.subscribe(MQTT_TOPIC_STIRFRY_POT1_CONTROL, self.on_stirfry_pot1_control)
                self.mqtt_client.subscribe(MQTT_TOPIC_STIRFRY_POT2_FOOD_TYPE, self.on_stirfry_pot2_food_type)
                self.mqtt_client.subscribe(MQTT_TOPIC_STIRFRY_POT2_CONTROL, self.on_stirfry_pot2_control)
                self.mqtt_client.subscribe("calibration/vibration/control", self.on_vibration_control)
                self.mqtt_client.subscribe(MQTT_TOPIC_ROBOT_STATUS, self.on_robot_status)

                print(f"[MQTT] 구독 토픽 (로봇→Jetson):")
                print(f"  - {MQTT_TOPIC_STIRFRY_POT1_FOOD_TYPE}")
                print(f"  - {MQTT_TOPIC_STIRFRY_POT1_CONTROL}")
                print(f"  - {MQTT_TOPIC_STIRFRY_POT2_FOOD_TYPE}")
                print(f"  - {MQTT_TOPIC_STIRFRY_POT2_CONTROL}")
                print(f"  - calibration/vibration/control")
                print(f"  - {MQTT_TOPIC_ROBOT_STATUS} (로봇 PC 상태)")
                print(f"[MQTT] 발행 토픽 (Jetson→로봇):")
                print(f"  - {MQTT_TOPIC_STATUS}")

                # Publish initial status
                self.publish_status()
                print(f"[MQTT] 초기 상태 발행 완료")

                self.auto_mqtt_label.config(text="MQTT: 연결됨", fg=COLOR_OK)
            else:
                print("[MQTT] 연결 실패")
                self.auto_mqtt_label.config(text="MQTT: 오류", fg=COLOR_ERROR)

        except Exception as e:
            print(f"[MQTT] 초기화 실패: {e}")
            self.auto_mqtt_label.config(text=f"MQTT: 오류", fg=COLOR_ERROR)

    def on_stirfry_pot1_food_type(self, client, userdata, message):
        """MQTT callback for pot1 food type - AUTO START recording"""
        try:
            self.stirfry_pot1_food_type = message.payload.decode()
            print(f"[MQTT POT1] 볶음 음식 종류 수신: {self.stirfry_pot1_food_type}")

            # Cancel previous timeout timer
            if self.pot1_timeout_id is not None:
                self.root.after_cancel(self.pot1_timeout_id)
                self.pot1_timeout_id = None

            # AUTO START: If not recording, start automatically
            if not self.stirfry_pot1_recording:
                print(f"[MQTT POT1] 자동 녹화 시작 - 음식: {self.stirfry_pot1_food_type}")
                self.root.after(0, self.start_stirfry_pot1_recording)
            else:
                # If already recording, store as metadata event
                from datetime import datetime
                self.stirfry_pot1_metadata.append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "type": "food_type_change",
                    "value": self.stirfry_pot1_food_type
                })
                print(f"[MQTT POT1] 이미 녹화 중 (타이머 리셋)")

            # Start new timeout timer
            timeout_ms = self.pot1_timeout_seconds * 1000
            self.pot1_timeout_id = self.root.after(timeout_ms, self.on_pot1_timeout)
            print(f"[MQTT POT1] 타임아웃 {self.pot1_timeout_seconds}초 시작")

        except Exception as e:
            print(f"[MQTT POT1] 음식 종류 수신 오류: {e}")

    def on_stirfry_pot1_control(self, client, userdata, message):
        """MQTT callback for pot1 control commands (optional - timeout auto-stops)"""
        try:
            command = message.payload.decode().strip().lower()
            print(f"[MQTT POT1] 볶음 제어 명령 수신: {command}")

            if command == "stop":
                # Cancel timeout timer
                if self.pot1_timeout_id is not None:
                    self.root.after_cancel(self.pot1_timeout_id)
                    self.pot1_timeout_id = None

                if self.stirfry_pot1_recording:
                    print(f"[MQTT POT1] 명시적 중지")
                    self.root.after(0, self.stop_stirfry_pot1_recording)
                else:
                    print(f"[MQTT POT1] 녹화 중이 아님 - 무시")
        except Exception as e:
            print(f"[MQTT POT1] 제어 명령 수신 오류: {e}")

    def on_stirfry_pot2_food_type(self, client, userdata, message):
        """MQTT callback for pot2 food type - AUTO START recording"""
        try:
            self.stirfry_pot2_food_type = message.payload.decode()
            print(f"[MQTT POT2] 볶음 음식 종류 수신: {self.stirfry_pot2_food_type}")

            # Cancel previous timeout timer
            if self.pot2_timeout_id is not None:
                self.root.after_cancel(self.pot2_timeout_id)
                self.pot2_timeout_id = None

            # AUTO START: If not recording, start automatically
            if not self.stirfry_pot2_recording:
                print(f"[MQTT POT2] 자동 녹화 시작 - 음식: {self.stirfry_pot2_food_type}")
                self.root.after(0, self.start_stirfry_pot2_recording)
            else:
                # If already recording, store as metadata event
                from datetime import datetime
                self.stirfry_pot2_metadata.append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "type": "food_type_change",
                    "value": self.stirfry_pot2_food_type
                })
                print(f"[MQTT POT2] 이미 녹화 중 (타이머 리셋)")

            # Start new timeout timer
            timeout_ms = self.pot2_timeout_seconds * 1000
            self.pot2_timeout_id = self.root.after(timeout_ms, self.on_pot2_timeout)
            print(f"[MQTT POT2] 타임아웃 {self.pot2_timeout_seconds}초 시작")

        except Exception as e:
            print(f"[MQTT POT2] 음식 종류 수신 오류: {e}")

    def on_stirfry_pot2_control(self, client, userdata, message):
        """MQTT callback for pot2 control commands (optional - timeout auto-stops)"""
        try:
            command = message.payload.decode().strip().lower()
            print(f"[MQTT POT2] 볶음 제어 명령 수신: {command}")

            if command == "stop":
                # Cancel timeout timer
                if self.pot2_timeout_id is not None:
                    self.root.after_cancel(self.pot2_timeout_id)
                    self.pot2_timeout_id = None

                if self.stirfry_pot2_recording:
                    print(f"[MQTT POT2] 명시적 중지")
                    self.root.after(0, self.stop_stirfry_pot2_recording)
                else:
                    print(f"[MQTT POT2] 녹화 중이 아님 - 무시")
        except Exception as e:
            print(f"[MQTT POT2] 제어 명령 수신 오류: {e}")

    def on_pot1_timeout(self):
        """POT1 timeout - auto-stop if no food_type message for N seconds"""
        try:
            if self.stirfry_pot1_recording:
                print(f"[POT1 타임아웃] {self.pot1_timeout_seconds}초 동안 메시지 없음 → 자동 중지")
                self.stop_stirfry_pot1_recording()
            self.pot1_timeout_id = None
        except Exception as e:
            print(f"[POT1 타임아웃] 오류: {e}")

    def on_pot2_timeout(self):
        """POT2 timeout - auto-stop if no food_type message for N seconds"""
        try:
            if self.stirfry_pot2_recording:
                print(f"[POT2 타임아웃] {self.pot2_timeout_seconds}초 동안 메시지 없음 → 자동 중지")
                self.stop_stirfry_pot2_recording()
            self.pot2_timeout_id = None
        except Exception as e:
            print(f"[POT2 타임아웃] 오류: {e}")

    def on_robot_status(self, client, userdata, message):
        """로봇 PC 상태 메시지 파싱 - Jetson1은 볶음솥(DeviceNum=1)만 처리"""
        try:
            payload = message.payload.decode()
            data = json.loads(payload)

            # MQTT 메시지 로그에 저장 (원본 보기용)
            self._log_mqtt_message(message.topic, payload)

            # VibrationRequest 처리
            vibration_request = data.get("VibrationRequest", False)
            if vibration_request:
                print(f"[로봇상태] VibrationRequest 수신: {vibration_request}")
                if VIBRATION_TEST_MODE:
                    # 테스트 모드: 즉시 NORMAL 응답
                    print(f"[진동] 테스트 모드 - 즉시 NORMAL 응답")
                    self.vibration_status = "NORMAL"
                    self.publish_status()  # 즉시 상태 발행
                else:
                    # 실제 모드: 진동센서 측정 시작
                    self.start_vibration_check()

            # Status 배열에서 볶음솥(DeviceNum=1) 찾기
            # DeviceNum: "0"=튀김(Jetson2), "1"=볶음(Jetson1)
            # PTNum: "0"=왼쪽, "1"=오른쪽
            status_list = data.get("Status", [])
            for status in status_list:
                device_num = status.get("DeviceNum", "")

                # Jetson1은 볶음솥(DeviceNum=1)만 처리
                if device_num != "1":
                    continue

                pt_num = status.get("PTNum", "")  # 0: 왼쪽, 1: 오른쪽
                recipe = status.get("NowRecipe", "")
                process_type = status.get("ProcessType", "")  # 투입/조리/배출
                running_time = status.get("RunningTime", "")
                pot_status = status.get("Potstatus", {})
                temp = pot_status.get("PT_Temp", 0)

                print(f"[로봇상태] 볶음솥 PT{pt_num} | {process_type} | {recipe} | 온도:{temp} | {running_time}")

                # 녹화 시작/중지 트리거: 투입 시 시작, 배출 후 N초 뒤 종료
                if pt_num == "0":  # 왼쪽 = POT1
                    if process_type == "투입":
                        # 배출 타이머가 있으면 취소 (다시 투입된 경우)
                        if self.pot1_discharge_timer_id:
                            self.root.after_cancel(self.pot1_discharge_timer_id)
                            self.pot1_discharge_timer_id = None
                            print(f"[로봇상태] POT1(왼쪽) 배출 타이머 취소 (재투입)")
                        if not self.stirfry_pot1_recording:
                            self.stirfry_pot1_food_type = recipe if recipe else "unknown"
                            print(f"[로봇상태] POT1(왼쪽) 녹화 시작 - {self.stirfry_pot1_food_type}")
                            self.root.after(0, self.start_stirfry_pot1_recording)
                    elif process_type == "배출":
                        if self.stirfry_pot1_recording and not self.pot1_discharge_timer_id:
                            delay_ms = RECORDING_DELAY_AFTER_DISCHARGE * 1000
                            print(f"[로봇상태] POT1(왼쪽) 배출 감지 - {RECORDING_DELAY_AFTER_DISCHARGE}초 후 녹화 종료 예정")
                            self.pot1_discharge_timer_id = self.root.after(delay_ms, self._delayed_stop_pot1_recording)

                elif pt_num == "1":  # 오른쪽 = POT2
                    if process_type == "투입":
                        # 배출 타이머가 있으면 취소 (다시 투입된 경우)
                        if self.pot2_discharge_timer_id:
                            self.root.after_cancel(self.pot2_discharge_timer_id)
                            self.pot2_discharge_timer_id = None
                            print(f"[로봇상태] POT2(오른쪽) 배출 타이머 취소 (재투입)")
                        if not self.stirfry_pot2_recording:
                            self.stirfry_pot2_food_type = recipe if recipe else "unknown"
                            print(f"[로봇상태] POT2(오른쪽) 녹화 시작 - {self.stirfry_pot2_food_type}")
                            self.root.after(0, self.start_stirfry_pot2_recording)
                    elif process_type == "배출":
                        if self.stirfry_pot2_recording and not self.pot2_discharge_timer_id:
                            delay_ms = RECORDING_DELAY_AFTER_DISCHARGE * 1000
                            print(f"[로봇상태] POT2(오른쪽) 배출 감지 - {RECORDING_DELAY_AFTER_DISCHARGE}초 후 녹화 종료 예정")
                            self.pot2_discharge_timer_id = self.root.after(delay_ms, self._delayed_stop_pot2_recording)

        except json.JSONDecodeError as e:
            print(f"[로봇상태] JSON 파싱 오류: {e}")
        except Exception as e:
            print(f"[로봇상태] 처리 오류: {e}")

    def init_cameras(self):
        """Initialize cameras based on enabled settings"""
        print("[카메라] 카메라 초기화 시작...")

        # Initialize cameras to None first
        self.auto_cap = None
        self.stirfry_left_cap = None
        self.stirfry_right_cap = None

        # Camera 1: Auto-start/down system (Person detection)
        if CAMERA_PERSON_ENABLED:
            try:
                print(f"[카메라] 사람 감지 카메라 ({CAMERA_TYPE.upper()} #{CAMERA_INDEX}) 시작 중...")
                self.auto_cap = GstCamera(
                    device_index=CAMERA_INDEX,
                    width=CAMERA_RESOLUTION['width'],
                    height=CAMERA_RESOLUTION['height'],
                    fps=CAMERA_FPS
                )
                if self.auto_cap.start():
                    print(f"[카메라] 사람 감지 카메라 초기화 완료 ✓")
                else:
                    print(f"[카메라] 사람 감지 카메라 초기화 실패 ✗")
                    self.auto_cap = None
            except Exception as e:
                print(f"[카메라] 사람 감지 카메라 초기화 실패: {e}")
                self.auto_cap = None
        else:
            print(f"[카메라] 사람 감지 카메라 비활성화됨 (camera_person_enabled=false)")

        # Camera 2: Stir-fry monitoring LEFT
        if STIRFRY_LEFT_ENABLED:
            try:
                print(f"[카메라] 볶음 왼쪽 카메라 ({STIRFRY_LEFT_CAMERA_TYPE.upper()} #{STIRFRY_LEFT_CAMERA_INDEX}) 시작 중...")
                self.stirfry_left_cap = GstCamera(
                    device_index=STIRFRY_LEFT_CAMERA_INDEX,
                    width=1920,
                    height=1536,
                    fps=CAMERA_FPS
                )
                if self.stirfry_left_cap.start():
                    print(f"[카메라] 볶음 왼쪽 카메라 초기화 완료 ✓")
                else:
                    print(f"[카메라] 볶음 왼쪽 카메라 초기화 실패 ✗")
                    self.stirfry_left_cap = None
            except Exception as e:
                print(f"[카메라] 볶음 왼쪽 카메라 초기화 실패: {e}")
                self.stirfry_left_cap = None
        else:
            print(f"[카메라] 볶음 왼쪽 카메라 비활성화됨 (stirfry_left_enabled=false)")

        # Camera 3: Stir-fry monitoring RIGHT
        if STIRFRY_RIGHT_ENABLED:
            try:
                print(f"[카메라] 볶음 오른쪽 카메라 ({STIRFRY_RIGHT_CAMERA_TYPE.upper()} #{STIRFRY_RIGHT_CAMERA_INDEX}) 시작 중...")
                self.stirfry_right_cap = GstCamera(
                    device_index=STIRFRY_RIGHT_CAMERA_INDEX,
                    width=1920,
                    height=1536,
                    fps=CAMERA_FPS
                )
                if self.stirfry_right_cap.start():
                    print(f"[카메라] 볶음 오른쪽 카메라 초기화 완료 ✓")
                else:
                    print(f"[카메라] 볶음 오른쪽 카메라 초기화 실패 ✗")
                    self.stirfry_right_cap = None
            except Exception as e:
                print(f"[카메라] 볶음 오른쪽 카메라 초기화 실패: {e}")
                self.stirfry_right_cap = None
        else:
            print(f"[카메라] 볶음 오른쪽 카메라 비활성화됨 (stirfry_right_enabled=false)")

        print("[카메라] 카메라 초기화 완료!")

    def init_yolo(self):
        """Initialize YOLO model with GPU acceleration"""
        try:
            import torch
            self.device = 'cuda' if torch.cuda.is_available() else 'cpu'

            print(f"[YOLO] 모델 로딩 중: {MODEL_PATH}")
            self.yolo_model = YOLO(MODEL_PATH)

            # Move model to GPU if available
            if self.device == 'cuda':
                self.yolo_model.to(self.device)
                print(f"[YOLO] 모델 로드 완료 (GPU 가속 활성화)")
            else:
                print(f"[YOLO] 모델 로드 완료 (CPU 모드)")
        except Exception as e:
            print(f"[오류] YOLO 초기화 실패: {e}")
            self.auto_status_label.config(text="상태: YOLO 오류", fg=COLOR_ERROR)
            self.device = 'cpu'

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
            # 날짜/시간 통합 표시
            self.datetime_label.config(text=now.strftime("%m/%d %H:%M:%S"))

            # MQTT 상태 업데이트
            self._update_mqtt_status_display()

            # 수집 상태 업데이트
            self._update_recording_status_display()

            # Only update date once per minute (at second 0)
            if current_second == 0 or not hasattr(self, '_date_set'):
                self._date_set = True

                # Check night review time (every minute)
                if hasattr(self, 'night_review_manager'):
                    self.night_review_manager.check_review_time()

                # Update disk space (every minute to avoid overhead)
                try:
                    import psutil
                    disk = psutil.disk_usage('/')
                    used_gb = disk.used / (1024**3)
                    total_gb = disk.total / (1024**3)
                    percent = disk.percent
                    disk_color = COLOR_OK if percent < 70 else COLOR_WARNING if percent < 90 else COLOR_ERROR
                    self.disk_label.config(
                        text=f"💾 {used_gb:.0f}/{total_gb:.0f}GB",
                        fg=disk_color
                    )
                except Exception as e:
                    self.disk_label.config(text="💾 --", fg=COLOR_TEXT)

        # Update every 200ms for smooth second transitions
        self.root.after(200, self.update_clock)

    def update_auto_system(self):
        """Update auto-start/down system (YOLO + MQTT)"""
        if not self.running:
            return

        if self.auto_cap is None or not self.auto_cap.isOpened() or self.yolo_model is None:
            self.root.after(100, self.update_auto_system)
            return

        # Read frame directly from GstCamera (no locks needed!)
        try:
            ret, frame = self.auto_cap.read()
            if not ret or frame is None:
                self.root.after(50, self.update_auto_system)
                return
        except Exception as e:
            print(f"[Error] Auto camera read error: {e}")
            self.root.after(50, self.update_auto_system)
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

        self.root.after(50, self.update_auto_system)  # 20 FPS (prevent freezing)

    def process_day_mode(self, frame, now):
        """Process day mode: YOLO person detection"""
        # Skip frames for performance - process YOLO every 3 frames
        self.yolo_frame_skip += 1
        if self.yolo_frame_skip < 3:
            return  # Skip this frame, use previous detection result

        self.yolo_frame_skip = 0  # Reset counter

        # Run YOLO detection (GPU accelerated)
        results = self.yolo_model.predict(frame, conf=YOLO_CONF, imgsz=YOLO_IMGSZ, verbose=False, device=self.device)
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
                    print("주간 모드 시작 시퀀스")
                    print("=" * 50)

                    # Turn on relay only if auto relay is enabled
                    if AUTO_RELAY_ENABLED:
                        # Step 1: Turn on Jetson #1 first (MQTT broker needs to boot)
                        print("[1/3] Jetson #1 제어 PC 부팅 중...")
                        self.relay_turn_on(publish_to_jetson2=False)  # Don't publish to Jetson 2 yet
                        print("[1/3] Jetson #1 릴레이 ON (브로커 부팅 시작)")

                        # Step 2: Wait for MQTT broker to boot up
                        print("[2/3] MQTT 브로커 부팅 대기 중... (10초)")
                        time.sleep(10)  # Wait 10 seconds for broker to start

                        # Step 3: Now turn on Jetson #2 and Robot PC
                        print("[3/3] Jetson #2 및 로봇 PC 시작 중...")
                        self.publish_relay_status("ON")  # Turn on Jetson #2's control PC
                        self.publish_mqtt("ON")          # Turn on Robot PC
                        print("[3/3] 전체 시작 완료")
                    else:
                        # If auto relay is disabled, just send MQTT ON
                        print("[릴레이] 자동 제어 비활성화됨 - MQTT ON만 전송")
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
            # Stage 1: YOLO check for no-person (GPU accelerated)
            results = self.yolo_model.predict(frame, conf=YOLO_CONF, imgsz=YOLO_IMGSZ, verbose=False, device=self.device)
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
                    print("야간 모드 종료 시퀀스 시작")
                    print("=" * 50)

                    # Step 1: Turn off Jetson #2 first (via MQTT relay sync)
                    if AUTO_RELAY_ENABLED:
                        print("[1/3] Jetson #2 제어 PC 종료 신호 전송 중...")
                        self.publish_relay_status("OFF")
                        print("[1/3] Jetson #2에 OFF 신호 전송 완료")

                        # Step 2: Wait for Jetson #2 to receive and shutdown
                        print(f"[2/3] Jetson #2 종료 대기 중... ({JETSON2_SHUTDOWN_DELAY_SEC}초)")
                        time.sleep(JETSON2_SHUTDOWN_DELAY_SEC)

                        # Step 3: Turn off Robot PC and Jetson #1
                        print("[3/3] 로봇 PC 및 Jetson #1 제어 PC 종료 중...")
                        self.publish_mqtt("OFF")  # Turn off Robot PC
                        self.relay_turn_off()     # Turn off Jetson #1's control PC
                        print("[3/3] 전체 종료 완료")
                    else:
                        # If auto relay is disabled, just send MQTT OFF
                        print("[릴레이] 자동 제어 비활성화됨 - MQTT OFF만 전송")
                        self.publish_mqtt("OFF")

                    self.off_triggered_once = True
                    self.auto_detection_label.config(text="감지: OFF 전송 ✓", fg=COLOR_OK)
                self.night_check_active = False
                self.night_no_person_deadline = None
            else:
                if self.night_no_person_deadline is not None:
                    remain = int((self.night_no_person_deadline - now).total_seconds())
                    # Clamp to minimum 0 to prevent negative display
                    remain = max(0, remain)
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

        # Read frame directly from GstCamera
        try:
            ret, frame = self.stirfry_left_cap.read()
            if not ret or frame is None:
                self.root.after(50, self.update_stirfry_left_camera)
                return
        except Exception as e:
            print(f"[Error] Left camera read error: {e}")
            self.root.after(50, self.update_stirfry_left_camera)
            return

        # If recording POT1 or manual recording, save frames (skip frames to prevent freezing + save storage)
        if self.stirfry_pot1_recording or self.stirfry_recording:
            # Each camera manages its own counter independently
            if not hasattr(self, 'stirfry_left_skip_counter'):
                self.stirfry_left_skip_counter = 0

            self.stirfry_left_skip_counter += 1
            # Save every Nth frame (configurable via STIRFRY_FRAME_SKIP)
            if self.stirfry_left_skip_counter >= STIRFRY_FRAME_SKIP:
                # Debug: First save notification
                if self.stirfry_pot1_frame_count == 0:
                    print("[볶음 POT1] 첫 프레임 저장 시작...")
                # Save in background thread to prevent GUI blocking
                threading.Thread(target=self.save_stirfry_left_frame, args=(frame.copy(),), daemon=True).start()
                self.stirfry_left_skip_counter = 0  # Reset counter after saving

        # Update preview
        self.update_stirfry_left_preview(frame)

        self.root.after(50, self.update_stirfry_left_camera)  # 20 FPS (prevent freezing)

    def update_stirfry_right_camera(self):
        """Update stir-fry RIGHT camera preview"""
        if not self.running:
            return

        if self.stirfry_right_cap is None or not self.stirfry_right_cap.isOpened():
            self.root.after(100, self.update_stirfry_right_camera)
            return

        # Read frame directly from GstCamera
        try:
            ret, frame = self.stirfry_right_cap.read()
            if not ret or frame is None:
                self.root.after(50, self.update_stirfry_right_camera)
                return
        except Exception as e:
            print(f"[Error] Right camera read error: {e}")
            self.root.after(50, self.update_stirfry_right_camera)
            return

        # If recording POT2 or manual recording, save frames (skip frames to prevent freezing + save storage)
        if self.stirfry_pot2_recording or self.stirfry_recording:
            # Each camera manages its own counter independently
            if not hasattr(self, 'stirfry_right_skip_counter'):
                self.stirfry_right_skip_counter = 0

            self.stirfry_right_skip_counter += 1
            # Save every Nth frame (configurable via STIRFRY_FRAME_SKIP)
            if self.stirfry_right_skip_counter >= STIRFRY_FRAME_SKIP:
                # Debug: First save notification
                if self.stirfry_pot2_frame_count == 0:
                    print("[볶음 POT2] 첫 프레임 저장 시작...")
                # Save in background thread to prevent GUI blocking
                threading.Thread(target=self.save_stirfry_right_frame, args=(frame.copy(),), daemon=True).start()
                self.stirfry_right_skip_counter = 0  # Reset counter after saving

        # Update preview
        self.update_stirfry_right_preview(frame)

        self.root.after(50, self.update_stirfry_right_camera)  # 20 FPS (prevent freezing)

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
                    preview = cv2.resize(frame, (640, 512), interpolation=cv2.INTER_NEAREST)
            else:
                preview = cv2.resize(frame, (640, 512), interpolation=cv2.INTER_NEAREST)

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

            # Get container size for aspect-fill resize (no letterbox)
            container_width = self.stirfry_left_preview_label.winfo_width()
            container_height = self.stirfry_left_preview_label.winfo_height()

            # Use default size if container not yet rendered
            if container_width <= 1 or container_height <= 1:
                container_width = int(340 * self.scale_factor)
                container_height = int(220 * self.scale_factor)

            # Resize to fill container (aspect-fill, may crop)
            h, w = frame.shape[:2]
            aspect_frame = w / h
            aspect_container = container_width / container_height

            if aspect_frame > aspect_container:
                # Frame is wider - fit height, crop width
                new_h = container_height
                new_w = int(new_h * aspect_frame)
            else:
                # Frame is taller - fit width, crop height
                new_w = container_width
                new_h = int(new_w / aspect_frame)

            # Resize with GPU if available
            if USE_CUDA:
                try:
                    gpu_frame = cv2.cuda_GpuMat()
                    gpu_frame.upload(frame)
                    gpu_resized = cv2.cuda.resize(gpu_frame, (new_w, new_h))
                    preview = gpu_resized.download()
                except:
                    preview = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            else:
                preview = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

            # Center crop to container size
            y_offset = (new_h - container_height) // 2
            x_offset = (new_w - container_width) // 2
            preview = preview[y_offset:y_offset+container_height, x_offset:x_offset+container_width]

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

            # Get container size for aspect-fill resize (no letterbox)
            container_width = self.stirfry_right_preview_label.winfo_width()
            container_height = self.stirfry_right_preview_label.winfo_height()

            # Use default size if container not yet rendered
            if container_width <= 1 or container_height <= 1:
                container_width = int(340 * self.scale_factor)
                container_height = int(220 * self.scale_factor)

            # Resize to fill container (aspect-fill, may crop)
            h, w = frame.shape[:2]
            aspect_frame = w / h
            aspect_container = container_width / container_height

            if aspect_frame > aspect_container:
                # Frame is wider - fit height, crop width
                new_h = container_height
                new_w = int(new_h * aspect_frame)
            else:
                # Frame is taller - fit width, crop height
                new_w = container_width
                new_h = int(new_w / aspect_frame)

            # Resize with GPU if available
            if USE_CUDA:
                try:
                    gpu_frame = cv2.cuda_GpuMat()
                    gpu_frame.upload(frame)
                    gpu_resized = cv2.cuda.resize(gpu_frame, (new_w, new_h))
                    preview = gpu_resized.download()
                except:
                    preview = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            else:
                preview = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

            # Center crop to container size
            y_offset = (new_h - container_height) // 2
            x_offset = (new_w - container_width) // 2
            preview = preview[y_offset:y_offset+container_height, x_offset:x_offset+container_width]

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
            # Auto camera: hide after preview_hide_delay of no person detection
            # If preview_hide_delay is 999999 (from config), effectively never hide
            if self.last_person_detected_time is None:
                # First time, initialize to now to prevent immediate hiding
                self.last_person_detected_time = datetime.now()
                return True  # First time, always show

            elapsed = (datetime.now() - self.last_person_detected_time).total_seconds()
            # If delay is very large (999999), always show
            if self.preview_hide_delay >= 999999:
                return True
            return elapsed < self.preview_hide_delay

        elif camera_type in ["stirfry_left", "stirfry_right"]:
            # Stir-fry cameras: always show preview (상시 표시)
            return True

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

    def publish_relay_status(self, status):
        """Publish relay status to MQTT for Jetson #2 synchronization"""
        # relay_enabled는 jetson1/status에 포함되어 주기적으로 발행됨
        print(f"[MQTT] 릴레이 상태: {status} (jetson1/status에 포함)")

    def publish_mqtt(self, message):
        """Publish message to MQTT broker with enhanced data"""
        # jetson1/status에 통합됨
        print(f"[MQTT] 메시지 전송 완료: {message}")

    def publish_status(self):
        """Publish unified status to single topic: jetson1/status"""
        if self.mqtt_client is None or not self.mqtt_client.is_connected():
            return

        try:
            status_data = {
                "device_id": DEVICE_ID,
                "device_name": DEVICE_NAME,
                "ip_address": get_ip_address(),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "ai_mode": AI_MODE_ENABLED,
                "person_detected": self.person_detected,
                "relay_enabled": self.relay_enabled,
                "recording": {
                    "left": self.stirfry_pot1_recording or self.stirfry_recording,
                    "right": self.stirfry_pot2_recording or self.stirfry_recording
                },
                "vibration": {
                    "status": self.vibration_status
                },
                "system": self.system_info.get_dynamic_info()
            }

            payload = json.dumps(status_data, ensure_ascii=False)
            self.mqtt_client.client.publish(MQTT_TOPIC_STATUS, payload, qos=MQTT_QOS)

        except Exception as e:
            print(f"[MQTT] 상태 발행 오류: {e}")

    def publish_mqtt_periodic(self):
        """Periodically publish unified status to MQTT"""
        if not self.running:
            return

        self.publish_status()

        # Schedule next publish
        interval_ms = int(MQTT_PUBLISH_INTERVAL * 1000)
        self.root.after(interval_ms, self.publish_mqtt_periodic)

    def send_mqtt_message(self, topic, message, include_device_info=True):
        """Send MQTT message with optional device info"""
        # jetson1/status에 통합됨 - 이 함수는 더 이상 사용하지 않음
        pass

    def save_snapshot(self, frame, timestamp):
        """Save motion snapshot"""
        try:
            day_dir = timestamp.strftime("%Y%m%d")
            ts_name = timestamp.strftime("%H%M%S")
            # Use home directory to avoid permission issues
            base_dir = os.path.expanduser(f"~/{SNAPSHOT_DIR}")
            out_dir = os.path.join(base_dir, day_dir)
            os.makedirs(out_dir, mode=0o755, exist_ok=True)
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
        """Save stir-fry LEFT monitoring frame (POT1, camera_0)"""
        try:
            now = datetime.now()
            ts_name = now.strftime("%H%M%S_%f")[:-3]  # Include milliseconds

            # Use POT1 session-based folder structure with camera_0
            base_dir = os.path.expanduser(f"~/{STIRFRY_SAVE_DIR}")
            session_dir = os.path.join(base_dir, "pot1", self.stirfry_pot1_session_id, self.stirfry_pot1_food_type)
            out_dir = os.path.join(session_dir, "camera_0")

            # Create directory with proper permissions
            os.makedirs(out_dir, mode=0o755, exist_ok=True)

            # Resize based on config (configurable resolution)
            save_width = STIRFRY_SAVE_RESOLUTION['width']
            save_height = STIRFRY_SAVE_RESOLUTION['height']
            resized = cv2.resize(frame, (save_width, save_height), interpolation=cv2.INTER_AREA)

            out_path = os.path.join(out_dir, f"camera_0_{ts_name}.jpg")
            # Save with configurable JPEG quality
            cv2.imwrite(out_path, resized, [cv2.IMWRITE_JPEG_QUALITY, STIRFRY_JPEG_QUALITY])
            self.stirfry_pot1_frame_count += 1

            # Update GUI on main thread
            self.root.after(0, lambda: self.stirfry_left_count_label.config(text=f"POT1: {self.stirfry_pot1_frame_count}장"))

            # Debug log
            if self.stirfry_pot1_frame_count % 10 == 0:
                print(f"[볶음 POT1] {self.stirfry_pot1_frame_count}장 저장됨")
        except Exception as e:
            print(f"[오류] POT1 프레임 저장 실패: {e}")
            import traceback
            traceback.print_exc()

    def save_stirfry_right_frame(self, frame):
        """Save stir-fry RIGHT monitoring frame (POT2, camera_1)"""
        try:
            now = datetime.now()
            ts_name = now.strftime("%H%M%S_%f")[:-3]  # Include milliseconds

            # Use POT2 session-based folder structure with camera_1
            base_dir = os.path.expanduser(f"~/{STIRFRY_SAVE_DIR}")
            session_dir = os.path.join(base_dir, "pot2", self.stirfry_pot2_session_id, self.stirfry_pot2_food_type)
            out_dir = os.path.join(session_dir, "camera_1")

            # Create directory with proper permissions
            os.makedirs(out_dir, mode=0o755, exist_ok=True)

            # Resize based on config (configurable resolution)
            save_width = STIRFRY_SAVE_RESOLUTION['width']
            save_height = STIRFRY_SAVE_RESOLUTION['height']
            resized = cv2.resize(frame, (save_width, save_height), interpolation=cv2.INTER_AREA)

            out_path = os.path.join(out_dir, f"camera_1_{ts_name}.jpg")
            # Save with configurable JPEG quality
            cv2.imwrite(out_path, resized, [cv2.IMWRITE_JPEG_QUALITY, STIRFRY_JPEG_QUALITY])
            self.stirfry_pot2_frame_count += 1

            # Update GUI on main thread
            self.root.after(0, lambda: self.stirfry_right_count_label.config(text=f"POT2: {self.stirfry_pot2_frame_count}장"))

            # Debug log
            if self.stirfry_pot2_frame_count % 10 == 0:
                print(f"[볶음 POT2] {self.stirfry_pot2_frame_count}장 저장됨")
        except Exception as e:
            print(f"[오류] POT2 프레임 저장 실패: {e}")
            import traceback
            traceback.print_exc()

    # =========================
    # Control Functions
    # =========================
    # POT1 Recording Control (Left Camera = camera_0)
    def start_stirfry_pot1_recording(self):
        """Start stir-fry POT1 data recording (left camera = camera_0)"""
        from datetime import datetime

        self.stirfry_pot1_recording = True
        self.stirfry_pot1_frame_count = 0
        self.stirfry_left_skip_counter = 0  # Reset frame skip counter

        # Create session ID
        self.stirfry_pot1_session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.stirfry_pot1_session_start_time = datetime.now()
        self.stirfry_pot1_metadata = []  # Reset metadata

        # Store initial metadata
        self.stirfry_pot1_metadata.append({
            "timestamp": self.stirfry_pot1_session_start_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "type": "session_start",
            "session_id": self.stirfry_pot1_session_id,
            "food_type": self.stirfry_pot1_food_type
        })

        print(f"[볶음 POT1] 녹화 시작 - 세션: {self.stirfry_pot1_session_id}, 음식: {self.stirfry_pot1_food_type}")

    def stop_stirfry_pot1_recording(self):
        """Stop stir-fry POT1 data recording (left camera = camera_0)"""
        from datetime import datetime
        import json

        self.stirfry_pot1_recording = False
        self.stirfry_left_skip_counter = 0  # Reset frame skip counter

        # Add session end metadata
        if self.stirfry_pot1_session_start_time:
            session_end_time = datetime.now()
            duration = (session_end_time - self.stirfry_pot1_session_start_time).total_seconds()

            self.stirfry_pot1_metadata.append({
                "timestamp": session_end_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                "type": "session_end",
                "duration_seconds": duration,
                "frame_count": self.stirfry_pot1_frame_count
            })

            # Save metadata JSON file
            try:
                base_dir = os.path.expanduser(f"~/{STIRFRY_SAVE_DIR}")
                metadata_dir = os.path.join(base_dir, "pot1", self.stirfry_pot1_session_id, self.stirfry_pot1_food_type)
                os.makedirs(metadata_dir, mode=0o755, exist_ok=True)

                metadata_file = os.path.join(metadata_dir, "metadata.json")
                metadata_content = {
                    "pot": "pot1",
                    "session_id": self.stirfry_pot1_session_id,
                    "food_type": self.stirfry_pot1_food_type,
                    "start_time": self.stirfry_pot1_session_start_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "end_time": session_end_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "duration_seconds": duration,
                    "frame_count": self.stirfry_pot1_frame_count,
                    "resolution": {
                        "width": STIRFRY_SAVE_RESOLUTION['width'],
                        "height": STIRFRY_SAVE_RESOLUTION['height']
                    },
                    "jpeg_quality": STIRFRY_JPEG_QUALITY,
                    "frame_skip": STIRFRY_FRAME_SKIP,
                    "device_id": DEVICE_ID,
                    "device_name": DEVICE_NAME,
                    "camera": "camera_0",
                    "events": self.stirfry_pot1_metadata
                }

                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(metadata_content, f, ensure_ascii=False, indent=2)

                print(f"[볶음 POT1] 메타데이터 저장 완료: {metadata_file}")
            except Exception as e:
                print(f"[오류] POT1 메타데이터 저장 실패: {e}")

        print(f"[볶음 POT1] 녹화 중지 - 프레임: {self.stirfry_pot1_frame_count}장")

    def _delayed_stop_pot1_recording(self):
        """배출 후 지연 종료 (타이머 콜백)"""
        self.pot1_discharge_timer_id = None
        if self.stirfry_pot1_recording:
            print(f"[로봇상태] POT1(왼쪽) 배출 후 {RECORDING_DELAY_AFTER_DISCHARGE}초 경과 - 녹화 종료")
            self.stop_stirfry_pot1_recording()

    # POT2 Recording Control (Right Camera = camera_1)
    def start_stirfry_pot2_recording(self):
        """Start stir-fry POT2 data recording (right camera = camera_1)"""
        from datetime import datetime

        self.stirfry_pot2_recording = True
        self.stirfry_pot2_frame_count = 0
        self.stirfry_right_skip_counter = 0  # Reset frame skip counter

        # Create session ID
        self.stirfry_pot2_session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.stirfry_pot2_session_start_time = datetime.now()
        self.stirfry_pot2_metadata = []  # Reset metadata

        # Store initial metadata
        self.stirfry_pot2_metadata.append({
            "timestamp": self.stirfry_pot2_session_start_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "type": "session_start",
            "session_id": self.stirfry_pot2_session_id,
            "food_type": self.stirfry_pot2_food_type
        })

        print(f"[볶음 POT2] 녹화 시작 - 세션: {self.stirfry_pot2_session_id}, 음식: {self.stirfry_pot2_food_type}")

    def stop_stirfry_pot2_recording(self):
        """Stop stir-fry POT2 data recording (right camera = camera_1)"""
        from datetime import datetime
        import json

        self.stirfry_pot2_recording = False
        self.stirfry_right_skip_counter = 0  # Reset frame skip counter

        # Add session end metadata
        if self.stirfry_pot2_session_start_time:
            session_end_time = datetime.now()
            duration = (session_end_time - self.stirfry_pot2_session_start_time).total_seconds()

            self.stirfry_pot2_metadata.append({
                "timestamp": session_end_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                "type": "session_end",
                "duration_seconds": duration,
                "frame_count": self.stirfry_pot2_frame_count
            })

            # Save metadata JSON file
            try:
                base_dir = os.path.expanduser(f"~/{STIRFRY_SAVE_DIR}")
                metadata_dir = os.path.join(base_dir, "pot2", self.stirfry_pot2_session_id, self.stirfry_pot2_food_type)
                os.makedirs(metadata_dir, mode=0o755, exist_ok=True)

                metadata_file = os.path.join(metadata_dir, "metadata.json")
                metadata_content = {
                    "pot": "pot2",
                    "session_id": self.stirfry_pot2_session_id,
                    "food_type": self.stirfry_pot2_food_type,
                    "start_time": self.stirfry_pot2_session_start_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "end_time": session_end_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "duration_seconds": duration,
                    "frame_count": self.stirfry_pot2_frame_count,
                    "resolution": {
                        "width": STIRFRY_SAVE_RESOLUTION['width'],
                        "height": STIRFRY_SAVE_RESOLUTION['height']
                    },
                    "jpeg_quality": STIRFRY_JPEG_QUALITY,
                    "frame_skip": STIRFRY_FRAME_SKIP,
                    "device_id": DEVICE_ID,
                    "device_name": DEVICE_NAME,
                    "camera": "camera_1",
                    "events": self.stirfry_pot2_metadata
                }

                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(metadata_content, f, ensure_ascii=False, indent=2)

                print(f"[볶음 POT2] 메타데이터 저장 완료: {metadata_file}")
            except Exception as e:
                print(f"[오류] POT2 메타데이터 저장 실패: {e}")

        print(f"[볶음 POT2] 녹화 중지 - 프레임: {self.stirfry_pot2_frame_count}장")

    def _delayed_stop_pot2_recording(self):
        """배출 후 지연 종료 (타이머 콜백)"""
        self.pot2_discharge_timer_id = None
        if self.stirfry_pot2_recording:
            print(f"[로봇상태] POT2(오른쪽) 배출 후 {RECORDING_DELAY_AFTER_DISCHARGE}초 경과 - 녹화 종료")
            self.stop_stirfry_pot2_recording()

    # LEGACY: Old combined recording functions (kept for backward compatibility)
    def start_stirfry_recording(self):
        """Start stir-fry data recording for BOTH cameras"""
        from datetime import datetime

        self.stirfry_recording = True
        self.stirfry_left_frame_count = 0
        self.stirfry_right_frame_count = 0
        self.stirfry_frame_skip_counter = 0  # Reset frame skip counter

        # Create session ID
        self.stirfry_session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.stirfry_session_start_time = datetime.now()
        self.stirfry_metadata = []  # Reset metadata

        # Store initial metadata
        self.stirfry_metadata.append({
            "timestamp": self.stirfry_session_start_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "type": "session_start",
            "session_id": self.stirfry_session_id,
            "food_type": self.current_stirfry_food_type
        })

        self.stirfry_start_btn.config(state=tk.DISABLED)
        self.stirfry_stop_btn.config(state=tk.NORMAL)
        print(f"[볶음] 녹화 시작 - 세션: {self.stirfry_session_id}, 음식: {self.current_stirfry_food_type}")

    def stop_stirfry_recording(self):
        """Stop stir-fry data recording for BOTH cameras (비동기 처리로 GUI 프리징 방지)"""
        from datetime import datetime

        self.stirfry_recording = False
        self.stirfry_frame_skip_counter = 0  # Reset frame skip counter

        # 즉시 GUI 업데이트 (프리징 방지)
        self.stirfry_start_btn.config(state=tk.NORMAL)
        self.stirfry_stop_btn.config(state=tk.DISABLED)

        # 저장에 필요한 데이터 복사 (스레드 안전)
        if self.stirfry_session_start_time:
            save_data = {
                "session_id": self.stirfry_session_id,
                "food_type": self.current_stirfry_food_type,
                "start_time": self.stirfry_session_start_time,
                "left_frame_count": self.stirfry_left_frame_count,
                "right_frame_count": self.stirfry_right_frame_count,
                "metadata": self.stirfry_metadata.copy()
            }

            # 백그라운드에서 저장 후 메시지박스 표시
            import threading
            threading.Thread(
                target=self._save_stirfry_data_async,
                args=(save_data,),
                daemon=True
            ).start()

        total_frames = self.stirfry_left_frame_count + self.stirfry_right_frame_count
        print(f"[볶음] 녹화 중지 - 왼쪽: {self.stirfry_left_frame_count}장, 오른쪽: {self.stirfry_right_frame_count}장")

    def _save_stirfry_data_async(self, save_data):
        """백그라운드에서 JSON 저장 후 메시지박스 표시"""
        from datetime import datetime
        import json

        try:
            session_end_time = datetime.now()
            duration = (session_end_time - save_data["start_time"]).total_seconds()

            # Add session end metadata
            save_data["metadata"].append({
                "timestamp": session_end_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                "type": "session_end",
                "duration_seconds": duration,
                "left_frame_count": save_data["left_frame_count"],
                "right_frame_count": save_data["right_frame_count"],
                "total_frames": save_data["left_frame_count"] + save_data["right_frame_count"]
            })

            # Save metadata JSON file
            base_dir = os.path.expanduser(f"~/{STIRFRY_SAVE_DIR}")
            metadata_dir = os.path.join(base_dir, save_data["session_id"])
            os.makedirs(metadata_dir, mode=0o755, exist_ok=True)

            metadata_file = os.path.join(metadata_dir, "metadata.json")
            metadata_content = {
                "session_id": save_data["session_id"],
                "food_type": save_data["food_type"],
                "start_time": save_data["start_time"].strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": session_end_time.strftime("%Y-%m-%d %H:%M:%S"),
                "duration_seconds": duration,
                "left_frames": save_data["left_frame_count"],
                "right_frames": save_data["right_frame_count"],
                "total_frames": save_data["left_frame_count"] + save_data["right_frame_count"],
                "resolution": {
                    "width": STIRFRY_SAVE_RESOLUTION['width'],
                    "height": STIRFRY_SAVE_RESOLUTION['height']
                },
                "jpeg_quality": STIRFRY_JPEG_QUALITY,
                "frame_skip": STIRFRY_FRAME_SKIP,
                "device_id": DEVICE_ID,
                "device_name": DEVICE_NAME,
                "events": save_data["metadata"]
            }

            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata_content, f, ensure_ascii=False, indent=2)

            print(f"[볶음] 메타데이터 저장 완료: {metadata_file}")

            # 메인 스레드에서 메시지박스 표시
            total_frames = save_data["left_frame_count"] + save_data["right_frame_count"]
            msg = (
                f"세션: {save_data['session_id']}\n"
                f"음식: {save_data['food_type']}\n"
                f"왼쪽: {save_data['left_frame_count']}장\n"
                f"오른쪽: {save_data['right_frame_count']}장\n"
                f"총: {total_frames}장"
            )
            self.root.after(0, lambda: showinfo_topmost("녹화 완료", msg))

        except Exception as e:
            print(f"[오류] 메타데이터 저장 실패: {e}")
            self.root.after(0, lambda: showinfo_topmost("녹화 완료", f"저장 중 오류 발생: {e}"))

    def toggle_auto_relay(self, window, status_label):
        """Toggle automatic relay control mode"""
        global AUTO_RELAY_ENABLED

        # Toggle the value
        AUTO_RELAY_ENABLED = not AUTO_RELAY_ENABLED

        # Update config.json
        try:
            config['auto_relay_enabled'] = AUTO_RELAY_ENABLED
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            # Update UI
            auto_mode_text = "활성화 (ON)" if AUTO_RELAY_ENABLED else "비활성화 (OFF)"
            auto_mode_color = COLOR_OK if AUTO_RELAY_ENABLED else COLOR_ERROR
            status_label.config(text=auto_mode_text, fg=auto_mode_color)

            mode_str = "활성화" if AUTO_RELAY_ENABLED else "비활성화"
            showinfo_topmost("자동 모드", f"자동 릴레이 제어가 {mode_str}되었습니다")
            print(f"[릴레이] 자동 제어 모드: {mode_str}")

        except Exception as e:
            showerror_topmost("오류", f"설정 저장 실패: {e}")
            print(f"[릴레이] 자동 모드 토글 오류: {e}")

    def manual_relay_control(self, action, window, status_label):
        """Manual relay control (ON/OFF)"""
        try:
            if action == 'ON':
                if not self.relay_enabled:
                    self.relay_turn_on()
                    status_label.config(text="현재 상태: 켜짐 (ON)", fg=COLOR_OK)
                    showinfo_topmost("릴레이 제어", "릴레이가 켜졌습니다 (ON)")
                else:
                    showinfo_topmost("릴레이 제어", "이미 켜져 있습니다")
            elif action == 'OFF':
                if self.relay_enabled:
                    self.relay_turn_off()
                    status_label.config(text="현재 상태: 꺼짐 (OFF)", fg=COLOR_ERROR)
                    showinfo_topmost("릴레이 제어", "릴레이가 꺼졌습니다 (OFF)")
                else:
                    showinfo_topmost("릴레이 제어", "이미 꺼져 있습니다")
        except Exception as e:
            showerror_topmost("오류", f"릴레이 제어 실패: {e}")
            print(f"[릴레이] 수동 제어 오류: {e}")

    def open_pc_status(self):
        """Open PC/Jetson status monitoring dialog"""
        # Create popup window
        status_window = tk.Toplevel(self.root)
        status_window.title("PC 상태 모니터링")
        status_window.geometry("700x800")
        status_window.configure(bg=COLOR_BG)

        # Center the window
        status_window.transient(self.root)
        status_window.grab_set()
        status_window.attributes('-topmost', True)
        status_window.lift()
        status_window.focus_force()

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
            tk.Label(cpu_frame, text=f"{cpu_percent:.1f}%", font=(FONT_FAMILY, 22, "bold"),
                    bg=COLOR_PANEL, fg=cpu_color, anchor="e").pack(side=tk.RIGHT)

            # Memory Usage
            mem = psutil.virtual_memory()
            mem_percent = mem.percent
            mem_color = COLOR_OK if mem_percent < 70 else COLOR_WARNING if mem_percent < 90 else COLOR_ERROR

            mem_frame = tk.Frame(info_frame, bg=COLOR_PANEL)
            mem_frame.pack(pady=10, padx=20, fill=tk.X)
            tk.Label(mem_frame, text="메모리 사용률:", font=MEDIUM_FONT,
                    bg=COLOR_PANEL, fg=COLOR_TEXT, anchor="w").pack(side=tk.LEFT)
            tk.Label(mem_frame, text=f"{mem_percent:.1f}%", font=(FONT_FAMILY, 22, "bold"),
                    bg=COLOR_PANEL, fg=mem_color, anchor="e").pack(side=tk.RIGHT)

            # Disk Usage
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            disk_color = COLOR_OK if disk_percent < 70 else COLOR_WARNING if disk_percent < 90 else COLOR_ERROR

            disk_frame = tk.Frame(info_frame, bg=COLOR_PANEL)
            disk_frame.pack(pady=10, padx=20, fill=tk.X)
            tk.Label(disk_frame, text="디스크 사용률:", font=MEDIUM_FONT,
                    bg=COLOR_PANEL, fg=COLOR_TEXT, anchor="w").pack(side=tk.LEFT)
            tk.Label(disk_frame, text=f"{disk_percent:.1f}%", font=(FONT_FAMILY, 22, "bold"),
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
                    tk.Label(temp_frame, text=f"{temp_celsius:.1f}°C", font=(FONT_FAMILY, 22, "bold"),
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

        # AI Mode (Relay) Control Section
        control_frame = tk.Frame(status_window, bg=COLOR_PANEL, bd=3, relief=tk.RAISED)
        control_frame.pack(pady=10, padx=40, fill=tk.X)

        tk.Label(control_frame, text="[ 릴레이 제어 ]", font=LARGE_FONT,
                bg=COLOR_PANEL, fg=COLOR_TEXT).pack(pady=10)

        # Auto relay mode toggle
        auto_mode_frame = tk.Frame(control_frame, bg=COLOR_PANEL)
        auto_mode_frame.pack(pady=10, fill=tk.X, padx=20)

        tk.Label(auto_mode_frame, text="자동 제어 모드:", font=MEDIUM_FONT,
                bg=COLOR_PANEL, fg=COLOR_TEXT).pack(side=tk.LEFT)

        auto_mode_text = "활성화 (ON)" if AUTO_RELAY_ENABLED else "비활성화 (OFF)"
        auto_mode_color = COLOR_OK if AUTO_RELAY_ENABLED else COLOR_ERROR

        auto_mode_status = tk.Label(auto_mode_frame, text=auto_mode_text,
                                    font=(FONT_FAMILY, 20, "bold"),
                                    bg=COLOR_PANEL, fg=auto_mode_color)
        auto_mode_status.pack(side=tk.RIGHT)

        # Toggle button
        toggle_frame = tk.Frame(control_frame, bg=COLOR_PANEL)
        toggle_frame.pack(pady=5)

        tk.Button(toggle_frame, text="[ 자동 모드 토글 ]", font=MEDIUM_FONT,
                 command=lambda: self.toggle_auto_relay(status_window, auto_mode_status),
                 width=20, bg=COLOR_INFO, fg="white",
                 relief=tk.FLAT, bd=0, padx=10, pady=8).pack()

        tk.Label(control_frame, text="※ 자동 모드: 출근/퇴근 시간에 자동으로 릴레이 ON/OFF",
                font=(FONT_FAMILY, 14), bg=COLOR_PANEL, fg=COLOR_TEXT_LIGHT).pack(pady=5)

        # Separator
        tk.Frame(control_frame, height=2, bg=COLOR_PANEL_BORDER).pack(fill=tk.X, padx=20, pady=10)

        # Current relay status
        relay_status_text = "켜짐 (ON)" if self.relay_enabled else "꺼짐 (OFF)"
        relay_status_color = COLOR_OK if self.relay_enabled else COLOR_ERROR

        status_label = tk.Label(control_frame, text=f"현재 상태: {relay_status_text}",
                               font=MEDIUM_FONT, bg=COLOR_PANEL, fg=relay_status_color)
        status_label.pack(pady=10)

        # Control buttons
        button_frame = tk.Frame(control_frame, bg=COLOR_PANEL)
        button_frame.pack(pady=15)

        tk.Button(button_frame, text="[ 릴레이 ON ]", font=MEDIUM_FONT,
                 command=lambda: self.manual_relay_control('ON', status_window, status_label),
                 width=15, bg=COLOR_OK, fg="white",
                 relief=tk.FLAT, bd=0, padx=10, pady=8).pack(side=tk.LEFT, padx=10)

        tk.Button(button_frame, text="[ 릴레이 OFF ]", font=MEDIUM_FONT,
                 command=lambda: self.manual_relay_control('OFF', status_window, status_label),
                 width=15, bg=COLOR_ERROR, fg="white",
                 relief=tk.FLAT, bd=0, padx=10, pady=8).pack(side=tk.LEFT, padx=10)

        # Warning label
        tk.Label(control_frame, text="※ 수동으로 제어하면 자동 모드가 재개됩니다",
                font=NORMAL_FONT, bg=COLOR_PANEL, fg=COLOR_WARNING).pack(pady=5)

        # Close button
        tk.Button(status_window, text="[ 닫기 ]", font=MEDIUM_FONT,
                 command=status_window.destroy, width=15,
                 bg=COLOR_INFO, fg="white").pack(pady=20)

        print("[PC상태] PC 상태 창 열림")

    def on_vibration_control(self, client, userdata, message):
        """MQTT callback for vibration control - robust parsing"""
        try:
            # 받은 메시지 전체를 로그로 출력 (디버깅용)
            raw_message = message.payload.decode('utf-8')
            print("=" * 60)
            print(f"[진동 MQTT] 수신 메시지 (topic: {message.topic}):")
            print(f"  Raw: {raw_message}")

            # 파싱 시도 1: JSON 형태
            command = None
            try:
                data = json.loads(raw_message)
                print(f"  Parsed JSON: {data}")

                # 다양한 키 시도
                for key in ["command", "cmd", "action", "control", "status"]:
                    if key in data:
                        command = str(data[key]).upper()
                        print(f"  Command key '{key}': {command}")
                        break
            except json.JSONDecodeError:
                # JSON이 아니면 단순 문자열로 처리
                command = raw_message.upper().strip()
                print(f"  Plain text command: {command}")

            # 명령어 인식 (유연하게)
            if command:
                # START 키워드들
                if any(word in command for word in ["START", "BEGIN", "ON", "OPEN", "RUN"]):
                    print("[진동 MQTT] ✓ 시작 명령 인식")
                    self.start_vibration_check()

                # STOP 키워드들
                elif any(word in command for word in ["STOP", "END", "OFF", "CLOSE", "QUIT"]):
                    print("[진동 MQTT] ✓ 종료 명령 인식")
                    self.stop_vibration_check()

                else:
                    print(f"[진동 MQTT] ⚠ 알 수 없는 명령: {command}")
            else:
                print("[진동 MQTT] ⚠ 명령을 찾을 수 없음")

            print("=" * 60)

        except Exception as e:
            print(f"[진동 MQTT] 파싱 오류: {e}")
            import traceback
            traceback.print_exc()

    def start_vibration_check(self):
        """Start vibration sensor monitoring program"""
        import subprocess
        import os

        if self.vibration_process is not None:
            print("[진동] 이미 실행 중입니다")
            return

        # 상대 경로로 수정 (jetson-food-ai 기준)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        vibration_script = os.path.join(base_dir, "vibration_sensor_simple.py")

        if not os.path.exists(vibration_script):
            print(f"[진동] 오류: {vibration_script} 파일이 없습니다")
            return

        try:
            # 진동 센서 프로그램을 별도 프로세스로 실행
            # stdout/stderr=None → 부모 프로세스(이 프로그램)의 출력으로 리다이렉트 (journalctl에서 보임)
            self.vibration_process = subprocess.Popen(
                ["python3", vibration_script],
                cwd=base_dir,
                stdout=None,  # 부모 프로세스의 stdout으로 출력 (journalctl에서 보임)
                stderr=None   # 부모 프로세스의 stderr로 출력 (journalctl에서 보임)
            )
            self.child_processes.append(self.vibration_process)
            print(f"[진동] 프로세스 시작 (PID: {self.vibration_process.pid})")
            print(f"[진동] 디버깅 메시지는 journalctl -u jetson1-ai -f 로 확인하세요")

            # Update status and button
            self.vibration_status = "MEASURING"
            self.vibration_check_btn.config(text="진동 중지", bg=COLOR_ERROR)
        except Exception as e:
            print(f"[진동] 실행 오류: {e}")
            self.vibration_process = None
            self.vibration_status = "IDLE"

    def stop_vibration_check(self):
        """Stop vibration sensor monitoring program"""
        if self.vibration_process is None:
            print("[진동] 실행 중인 프로세스 없음")
            return

        try:
            print(f"[진동] 프로세스 종료 중 (PID: {self.vibration_process.pid})")
            self.vibration_process.terminate()  # SIGTERM 전송

            try:
                self.vibration_process.wait(timeout=3)  # 3초 대기
                print("[진동] 프로세스 정상 종료")
            except subprocess.TimeoutExpired:
                print("[진동] 타임아웃 - 강제 종료")
                self.vibration_process.kill()  # SIGKILL 전송
                self.vibration_process.wait()

            # child_processes 리스트에서도 제거
            if self.vibration_process in self.child_processes:
                self.child_processes.remove(self.vibration_process)

            # Update status and button
            self.vibration_status = "IDLE"
            self.vibration_check_btn.config(text="진동 시작", bg=COLOR_INFO)

        except Exception as e:
            print(f"[진동] 종료 오류: {e}")
        finally:
            self.vibration_process = None
            self.vibration_status = "IDLE"

    def toggle_vibration_check(self):
        """Toggle vibration sensor monitoring (GUI button)"""
        if self.vibration_process is None:
            print("[진동] GUI 버튼으로 수동 시작")
            self.start_vibration_check()
        else:
            print("[진동] GUI 버튼으로 수동 종료")
            self.stop_vibration_check()

    def open_vibration_check(self):
        """Open vibration sensor monitoring program (deprecated - use toggle)"""
        print("[진동] GUI 버튼으로 수동 실행 (MQTT 호환)")
        self.start_vibration_check()

    def _get_mqtt_subscribed_topics(self):
        """MQTT 구독 중인 토픽 목록 반환"""
        topics = []
        if MQTT_ENABLED and self.mqtt_client:
            topics = [
                MQTT_TOPIC_STIRFRY_POT1_FOOD_TYPE,
                MQTT_TOPIC_STIRFRY_POT1_CONTROL,
                MQTT_TOPIC_STIRFRY_POT2_FOOD_TYPE,
                MQTT_TOPIC_STIRFRY_POT2_CONTROL,
                "calibration/vibration/control",
                MQTT_TOPIC_ROBOT_STATUS,
            ]
        return topics

    def _update_mqtt_status_display(self):
        """MQTT 상태 버튼 업데이트"""
        if not hasattr(self, 'mqtt_status_btn'):
            return

        if MQTT_ENABLED and self.mqtt_client:
            topic_count = len(self._get_mqtt_subscribed_topics())
            self.mqtt_status_btn.config(
                text=f"● MQTT({topic_count})",
                fg=COLOR_OK
            )
        else:
            self.mqtt_status_btn.config(
                text="● MQTT(X)",
                fg=COLOR_ERROR
            )

    def _update_recording_status_display(self):
        """상단 헤더에 수집 상태 표시 업데이트"""
        if not hasattr(self, 'recording_status_label'):
            return

        recording_parts = []
        if self.stirfry_pot1_recording:
            recording_parts.append("POT1")
        if self.stirfry_pot2_recording:
            recording_parts.append("POT2")
        if self.stirfry_recording:
            recording_parts.append("수동")

        if recording_parts:
            status_text = f"🔴 {'+'.join(recording_parts)} 수집중"
            self.recording_status_label.config(text=status_text, fg=COLOR_ERROR)
            # 구분선 표시
            self.recording_separator.pack(side=tk.LEFT, fill=tk.Y, padx=3, pady=8)
        else:
            self.recording_status_label.config(text="")
            # 구분선 숨김
            self.recording_separator.pack_forget()

    def _log_mqtt_message(self, topic, payload):
        """MQTT 메시지를 로그에 저장 (원본 보기용 + 파일 저장)"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = {
            "time": timestamp,
            "topic": topic,
            "payload": payload
        }
        self.mqtt_message_log.append(log_entry)
        # 최대 개수 초과 시 오래된 것 삭제
        if len(self.mqtt_message_log) > self.mqtt_message_log_max:
            self.mqtt_message_log.pop(0)

        # 파일로도 저장 (날짜별)
        try:
            date_str = datetime.now().strftime("%Y-%m-%d")
            log_dir = os.path.join(os.path.dirname(__file__), "mqtt_logs")
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, f"mqtt_{date_str}.log")

            full_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"[{full_timestamp}] {topic}\n{payload}\n\n")
        except Exception as e:
            print(f"[MQTT 로그] 파일 저장 실패: {e}")

    def show_mqtt_status_popup(self):
        """MQTT 상태 상세 팝업 표시 (탭 형태)"""
        from tkinter import ttk

        popup = tk.Toplevel(self.root)
        popup.title("MQTT 상태")
        popup.geometry("550x500")
        popup.configure(bg=COLOR_PANEL)
        popup.transient(self.root)
        popup.grab_set()

        # 연결 상태 (상단 고정)
        status_frame = tk.Frame(popup, bg=COLOR_PANEL)
        status_frame.pack(fill=tk.X, padx=10, pady=10)

        if MQTT_ENABLED and self.mqtt_client:
            status_text = f"● 연결됨: {MQTT_BROKER}:{MQTT_PORT}"
            status_color = COLOR_OK
        elif MQTT_ENABLED:
            status_text = "● 연결 끊김"
            status_color = COLOR_ERROR
        else:
            status_text = "● MQTT 비활성화 (config)"
            status_color = COLOR_TEXT_LIGHT

        tk.Label(status_frame, text=status_text,
                font=(FONT_FAMILY, 12, "bold"),
                bg=COLOR_PANEL, fg=status_color).pack(anchor="w")

        tk.Label(status_frame, text=f"Client ID: {MQTT_CLIENT_ID}",
                font=(FONT_FAMILY, 10),
                bg=COLOR_PANEL, fg=COLOR_TEXT).pack(anchor="w")

        # 탭 컨테이너
        style = ttk.Style()
        style.configure("TNotebook", background=COLOR_PANEL)
        style.configure("TNotebook.Tab", font=(FONT_FAMILY, 10, "bold"), padding=[10, 5])

        notebook = ttk.Notebook(popup)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # === 탭 1: 구독 토픽 ===
        tab_topics = tk.Frame(notebook, bg=COLOR_PANEL)
        notebook.add(tab_topics, text="구독 토픽")

        tk.Label(tab_topics, text="구독 중인 토픽:",
                font=(FONT_FAMILY, 11, "bold"),
                bg=COLOR_PANEL, fg=COLOR_TEXT).pack(anchor="w", padx=5, pady=5)

        list_frame = tk.Frame(tab_topics, bg=COLOR_BG)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        topic_listbox = tk.Listbox(list_frame, font=(FONT_FAMILY, 9),
                                   bg=COLOR_BG, fg=COLOR_TEXT,
                                   yscrollcommand=scrollbar.set,
                                   selectmode=tk.SINGLE)
        topic_listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=topic_listbox.yview)

        topics = self._get_mqtt_subscribed_topics()
        for i, topic in enumerate(topics, 1):
            topic_listbox.insert(tk.END, f"{i}. {topic}")

        if not topics:
            topic_listbox.insert(tk.END, "(구독 중인 토픽 없음)")

        tk.Label(tab_topics, text=f"발행 토픽: {MQTT_TOPIC_STATUS}",
                font=(FONT_FAMILY, 10),
                bg=COLOR_PANEL, fg=COLOR_TEXT).pack(anchor="w", padx=5, pady=5)

        # === 탭 2: 원본 메시지 ===
        tab_messages = tk.Frame(notebook, bg=COLOR_PANEL)
        notebook.add(tab_messages, text=f"원본 메시지 ({len(self.mqtt_message_log)})")

        msg_header = tk.Frame(tab_messages, bg=COLOR_PANEL)
        msg_header.pack(fill=tk.X, padx=5, pady=5)

        tk.Label(msg_header, text=f"최근 {self.mqtt_message_log_max}개 메시지:",
                font=(FONT_FAMILY, 11, "bold"),
                bg=COLOR_PANEL, fg=COLOR_TEXT).pack(side=tk.LEFT)

        def refresh_messages():
            msg_text.config(state=tk.NORMAL)
            msg_text.delete(1.0, tk.END)
            if not self.mqtt_message_log:
                msg_text.insert(tk.END, "(수신된 메시지 없음)")
            else:
                for entry in reversed(self.mqtt_message_log):  # 최신순
                    msg_text.insert(tk.END, f"[{entry['time']}] {entry['topic']}\n", "topic")
                    # JSON 예쁘게 포맷팅
                    try:
                        formatted = json.dumps(json.loads(entry['payload']), indent=2, ensure_ascii=False)
                        msg_text.insert(tk.END, f"{formatted}\n\n")
                    except:
                        msg_text.insert(tk.END, f"{entry['payload']}\n\n")
            msg_text.config(state=tk.DISABLED)
            # 탭 제목 업데이트
            notebook.tab(tab_messages, text=f"원본 메시지 ({len(self.mqtt_message_log)})")

        tk.Button(msg_header, text="새로고침",
                 font=(FONT_FAMILY, 9),
                 command=refresh_messages,
                 bg=COLOR_BUTTON, fg="white",
                 relief=tk.FLAT, padx=10).pack(side=tk.RIGHT)

        msg_frame = tk.Frame(tab_messages, bg=COLOR_BG)
        msg_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        msg_scrollbar = tk.Scrollbar(msg_frame)
        msg_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        msg_text = tk.Text(msg_frame, font=(FONT_FAMILY, 9),
                          bg=COLOR_BG, fg=COLOR_TEXT,
                          yscrollcommand=msg_scrollbar.set,
                          wrap=tk.WORD, state=tk.DISABLED)
        msg_text.pack(fill=tk.BOTH, expand=True)
        msg_scrollbar.config(command=msg_text.yview)

        # 토픽 강조 태그
        msg_text.tag_configure("topic", foreground=COLOR_OK, font=(FONT_FAMILY, 9, "bold"))

        # 초기 메시지 로드
        refresh_messages()

        # 닫기 버튼
        tk.Button(popup, text="닫기",
                 font=(FONT_FAMILY, 11, "bold"),
                 command=popup.destroy,
                 bg=COLOR_BUTTON, fg="white",
                 relief=tk.FLAT, padx=20, pady=5).pack(pady=10)

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
            showinfo_topmost("설정", "설정 기능은 준비 중입니다.\nconfig.json 파일을 직접 수정하세요.")

    def open_settings(self):
        """Open settings dialog immediately (for direct calls)"""
        showinfo_topmost("설정", "설정 기능은 준비 중입니다.\nconfig.json 파일을 직접 수정하세요.")

    def confirm_shutdown(self):
        """Confirm shutdown and close - 바로 종료"""
        self.on_closing()

    def toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        current = self.root.attributes('-fullscreen')
        self.root.attributes('-fullscreen', not current)
        if not current:
            print("[화면] Fullscreen 모드")
        else:
            print("[화면] Windowed 모드")

    def on_closing(self):
        """Handle window close - 백그라운드에서 정리"""
        # 확인 팝업 없이 바로 종료
        print("[종료] 시스템 종료 중...")
        self.running = False

        # 백그라운드 스레드에서 정리 작업 수행 (UI 프리징 방지)
        def cleanup_and_exit():
            try:
                # Stop ongoing recordings/data collection to save metadata
                print("[종료] 녹화/수집 중지 및 메타데이터 저장 중...")
                if self.stirfry_recording:
                    self.stop_stirfry_recording()
                if hasattr(self, 'stirfry_pot1_recording') and self.stirfry_pot1_recording:
                    self.stop_pot1_recording()
                if hasattr(self, 'stirfry_pot2_recording') and self.stirfry_pot2_recording:
                    self.stop_pot2_recording()

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

                # Cleanup GstCamera cameras with timeout
                print("[종료] 카메라 해제 중...")
                import threading

                def stop_camera_safe(cap, name):
                    try:
                        cap.stop()
                        print(f"[종료] {name} 해제 완료")
                    except Exception as e:
                        print(f"[종료] {name} 해제 오류: {e}")

                threads = []
                if self.auto_cap is not None:
                    t = threading.Thread(target=stop_camera_safe, args=(self.auto_cap, "auto_cap"))
                    t.daemon = True
                    t.start()
                    threads.append(t)

                if self.stirfry_left_cap is not None:
                    t = threading.Thread(target=stop_camera_safe, args=(self.stirfry_left_cap, "stirfry_left"))
                    t.daemon = True
                    t.start()
                    threads.append(t)

                if self.stirfry_right_cap is not None:
                    t = threading.Thread(target=stop_camera_safe, args=(self.stirfry_right_cap, "stirfry_right"))
                    t.daemon = True
                    t.start()
                    threads.append(t)

                # Wait for all threads with timeout
                for t in threads:
                    t.join(timeout=2.0)

                print("[종료] 카메라 해제 완료")

                # Cleanup MQTT
                if self.mqtt_client is not None:
                    try:
                        self.mqtt_client.disconnect()
                    except:
                        pass

                # Cleanup GPIO
                try:
                    print("[종료] GPIO 정리 중...")
                    # Set pins to LOW before cleanup
                    GPIO.output(29, GPIO.LOW)
                    GPIO.output(31, GPIO.LOW)
                    time.sleep(0.1)

                    # Change to input mode with pull-down for clean shutdown
                    GPIO.setup(29, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
                    GPIO.setup(31, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
                    time.sleep(0.1)

                    GPIO.cleanup()
                    print("[종료] GPIO 정리 완료")
                except Exception as e:
                    print(f"[종료] GPIO 정리 오류: {e}")

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
    root = tk.Tk()
    app = IntegratedMonitorApp(root)
    root.mainloop()
