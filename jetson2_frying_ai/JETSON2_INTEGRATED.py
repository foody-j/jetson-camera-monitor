#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jetson Orin #2 - Integrated AI Monitoring System
- Frying AI (튀김 AI - 2 cameras: video0 left, video1 right)
- Observe_add (Bucket detection: video2 left, video3 right)
- MQTT Communication
- PC Status Check
- Vibration Sensor Check

Designed for kitchen staff (40-50 years old) - Large, clear, simple interface
"""

import tkinter as tk
from tkinter import ttk, messagebox
import tkinter.font as tkfont
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
import socket

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.communication.mqtt_client import MQTTClient
from src.core.system_info import SystemInfo

# Import GStreamer camera wrapper (threading - same as Jetson1)
from gst_camera import GstCamera

# Import multiprocessing image saver (prevents GUI freezing during data collection)
from image_saver_mp import get_image_saver, stop_image_saver

# Import Frying AI segmenter
from frying_segmenter import FoodSegmenter

# Import GPIO for Relay control
import Jetson.GPIO as GPIO

# Import psutil for system monitoring
try:
    import psutil
except ImportError:
    print("[경고] psutil 미설치 - PC 상태 기능 제한됨")
    psutil = None

# =========================
# Load Configuration
# =========================
def load_config(config_path="config_jetson2.json"):
    """Load configuration from JSON file"""
    # Get script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_full_path = os.path.join(script_dir, config_path)

    with open(config_full_path, 'r', encoding='utf-8') as f:
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

# Frying AI Configuration (video0, video1)
FRYING_ENABLED = config.get('frying_enabled', True)
FRYING_LEFT_CAMERA_INDEX = config.get('frying_left_camera_index', 0)
FRYING_RIGHT_CAMERA_INDEX = config.get('frying_right_camera_index', 1)
FRYING_SEG_MODEL = config.get('frying_seg_model', 'frying_seg.pt')
FRYING_CLS_MODEL = config.get('frying_cls_model', 'frying_cls.pt')

# Observe_add Configuration (video2, video3)
OBSERVE_ENABLED = config.get('observe_enabled', True)
OBSERVE_LEFT_ENABLED = config.get('observe_left_enabled', True)
OBSERVE_RIGHT_ENABLED = config.get('observe_right_enabled', True)
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

# Device Identification
DEVICE_ID = config.get('device_id', 'jetson2')
DEVICE_NAME = config.get('device_name', 'Jetson2_Frying_Station')
DEVICE_LOCATION = config.get('device_location', 'kitchen_frying')

# ==============================================================================
# MQTT 토픽 정리
# ==============================================================================
# [발행] Jetson2 → 로봇PC
#   - jetson2/status : Jetson2 통합 상태 (AI모드, 튀김AI, 관찰AI 등)
#
# [구독] 로봇PC → Jetson2
#   - HR/Status : 로봇 PC 상태 (솥 온도, 레시피, 프로세스 등)
#   - frying/pot1/food_type, frying/pot1/control : 튀김솥1 제어
#   - frying/pot2/food_type, frying/pot2/control : 튀김솥2 제어
#   - frying/pot1/oil_temp, frying/pot1/probe_temp : 튀김솥1 온도
#   - frying/pot2/oil_temp, frying/pot2/probe_temp : 튀김솥2 온도
# ==============================================================================

# MQTT Configuration
MQTT_ENABLED = config.get('mqtt_enabled', False)
MQTT_BROKER = config.get('mqtt_broker', 'localhost')
MQTT_PORT = config.get('mqtt_port', 1883)
MQTT_QOS = config.get('mqtt_qos', 1)
MQTT_CLIENT_ID = config.get('mqtt_client_id', 'jetson2_ai')
MQTT_PUBLISH_INTERVAL = config.get('mqtt_publish_interval', 5)  # seconds

# MQTT 발행 토픽 (Jetson2 → 로봇PC) - 단일 토픽으로 통합
MQTT_TOPIC_STATUS = config.get('mqtt_topic_status', 'jetson2/status')

# MQTT 구독 토픽 (로봇PC → Jetson2)
MQTT_TOPIC_ROBOT_STATUS = config.get('mqtt_topic_robot_status', 'HR/Status')
MQTT_TOPIC_POT1_OIL_TEMP = config.get('mqtt_topic_pot1_oil_temp', 'frying/pot1/oil_temp')
MQTT_TOPIC_POT1_PROBE_TEMP = config.get('mqtt_topic_pot1_probe_temp', 'frying/pot1/probe_temp')
MQTT_TOPIC_POT2_OIL_TEMP = config.get('mqtt_topic_pot2_oil_temp', 'frying/pot2/oil_temp')
MQTT_TOPIC_POT2_PROBE_TEMP = config.get('mqtt_topic_pot2_probe_temp', 'frying/pot2/probe_temp')
MQTT_TOPIC_FRYING_POT1_FOOD_TYPE = config.get('mqtt_topic_frying_pot1_food_type', 'frying/pot1/food_type')
MQTT_TOPIC_FRYING_POT1_CONTROL = config.get('mqtt_topic_frying_pot1_control', 'frying/pot1/control')
MQTT_TOPIC_FRYING_POT2_FOOD_TYPE = config.get('mqtt_topic_frying_pot2_food_type', 'frying/pot2/food_type')
MQTT_TOPIC_FRYING_POT2_CONTROL = config.get('mqtt_topic_frying_pot2_control', 'frying/pot2/control')
# AI Mode Setting
AI_MODE_ENABLED = config.get('ai_mode_enabled', False)

# Vibration Sensor Settings
VIBRATION_TEST_MODE = config.get('vibration_test_mode', False)  # True=VibrationRequest 시 즉시 NORMAL 응답

# Relay Control Settings
RELAY_MODE = config.get('relay_mode', 'pulse')
AUTO_RELAY_ENABLED = config.get('auto_relay_enabled', False)

# Data Collection Configuration
SAVE_RESOLUTION = config.get('save_resolution', {'width': 1280, 'height': 720})
SAVE_WIDTH = SAVE_RESOLUTION['width']
SAVE_HEIGHT = SAVE_RESOLUTION['height']
TARGET_PROBE_TEMP = config.get('target_probe_temp', 75.0)
JPEG_QUALITY = config.get('jpeg_quality', 85)
FOOD_TYPES = config.get('food_types', ["chicken", "shrimp", "potato", "dumpling", "pork_cutlet", "fish"])
RECORDING_DELAY_AFTER_DISCHARGE = config.get('recording_delay_after_discharge', 20)  # 배출 후 추가 녹화 시간 (초)

# GUI Configuration - WHITE MODE (768x1024 세로 모드)
WINDOW_WIDTH = config.get('window_width', 768)
WINDOW_HEIGHT = config.get('window_height', 1024)
FULLSCREEN_MODE = config.get('fullscreen', False)  # 전체화면 모드 설정
WINDOW_DECORATIONS = config.get('window_decorations', False)  # 창 테두리 표시 여부
# 폰트 이름 설정 - Segfault 방지를 위해 시스템 기본 폰트 사용 가능
# "Noto Sans CJK KR" 폰트가 세그폴트를 일으키면 "" (빈 문자열)로 변경
FONT_FAMILY = "TkDefaultFont"  # 시스템 기본 폰트 (빈 문자열은 segfault 유발)
LARGE_FONT = (FONT_FAMILY, config.get('font_large', 22), "bold")
MEDIUM_FONT = (FONT_FAMILY, config.get('font_medium', 16), "bold")
SMALL_FONT = (FONT_FAMILY, config.get('font_small', 12))
NORMAL_FONT = (FONT_FAMILY, config.get('font_normal', 14))
BUTTON_FONT = (FONT_FAMILY, config.get('font_button', 16), "bold")

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
GUI_FRAME_SKIP = config.get('gui_frame_skip', 3)  # GUI 표시 프레임 스킵 (3=10fps)


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
            # Fullscreen mode - 진짜 전체화면 속성 설정
            self.root.attributes('-fullscreen', True)
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            print(f"[디스플레이] 전체화면 모드 ({screen_width}x{screen_height})")
        else:
            # Windowed mode
            self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+0+0")
            print(f"[디스플레이] 창 모드 ({WINDOW_WIDTH}x{WINDOW_HEIGHT})")

        # System info
        self.sys_info = SystemInfo(device_name="Jetson2", location="Kitchen")

        # 로봇 상태 업데이트 (MQTT 콜백 → 메인 스레드 전달용)
        self._robot_status_update = None

        # GPIO relay control
        self.relay_enabled = False
        self.relay_mode = config.get('relay_mode', 'pulse')
        self.init_gpio()

        # MQTT client
        self.mqtt_client = None
        if MQTT_ENABLED:
            self.init_mqtt()

        # Load AI models with GPU (if available)
        print("[모델] AI 모델 로딩 중...")

        # Check CUDA availability
        import gc
        import torch

        # GPU 메모리 정리 (이전 실행 잔여물 제거)
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            print("[GPU] 이전 GPU 메모리 정리 완료")

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
        print(f"[DEBUG] 모델 로딩 완료, Queue 초기화 시작...")

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
        self.vibration_process = None  # 진동센서 프로세스 추적
        self.vibration_status = "IDLE"  # 진동센서 상태: IDLE, MEASURING, NORMAL, ABNORMAL

        # Frame skip counters (CPU 절약)
        self.frying_frame_skip = 0
        self.observe_frame_skip = 0
        # GUI 표시 프레임 스킵 (각 카메라별)
        self.gui_frame_skip_frying_left = 0
        self.gui_frame_skip_frying_right = 0
        self.gui_frame_skip_observe_left = 0
        self.gui_frame_skip_observe_right = 0

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

        # Pot status (for MQTT publishing)
        # 상태값: "IDLE" (대기), "COOKING" (조리 중), "UNKNOWN" (AI 판단 불가)
        self.pot1_pot_status = "UNKNOWN" if not AI_MODE_ENABLED else "IDLE"
        self.pot2_pot_status = "UNKNOWN" if not AI_MODE_ENABLED else "IDLE"

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

        # Data collection flags (LEGACY - for backward compatibility)
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

        # POT1 data collection (cameras 0, 1)
        self.pot1_collecting = False
        self.pot1_session_id = None
        self.pot1_start_time = None
        self.pot1_frame_counter = 0
        self.pot1_timer = 0
        self.pot1_food_type = "unknown"
        self.pot1_metadata = []
        self.pot1_completion_marked = False
        self.pot1_completion_time = None
        self.pot1_completion_info = {}
        # POT1 timeout (auto-stop if no message for N seconds)
        self.pot1_timeout_id = None
        self.pot1_timeout_seconds = 5  # 5초 동안 메시지 없으면 자동 중지
        # POT1 배출 후 지연 종료 타이머
        self.pot1_discharge_timer_id = None

        # POT2 data collection (cameras 2, 3)
        self.pot2_collecting = False
        self.pot2_session_id = None
        self.pot2_start_time = None
        self.pot2_frame_counter = 0
        self.pot2_timer = 0
        self.pot2_food_type = "unknown"
        self.pot2_metadata = []
        self.pot2_completion_marked = False
        self.pot2_completion_time = None
        self.pot2_completion_info = {}
        # POT2 timeout (auto-stop if no message for N seconds)
        self.pot2_timeout_id = None
        self.pot2_timeout_seconds = 5  # 5초 동안 메시지 없으면 자동 중지
        # POT2 배출 후 지연 종료 타이머
        self.pot2_discharge_timer_id = None

        # Latest frames for data collection
        self.latest_frying_left_frame = None
        self.latest_frying_right_frame = None
        self.latest_observe_left_frame = None
        self.latest_observe_right_frame = None

        # Pre-load fonts to avoid Segfault
        print(f"[DEBUG] 폰트 사전 로딩...")
        self._init_fonts()

        # Build GUI
        print(f"[DEBUG] GUI 빌드 시작...")
        self.build_gui()
        print(f"[DEBUG] GUI 빌드 완료")

        # Initialize cameras
        print(f"[DEBUG] 카메라 초기화 시작...")
        self.init_cameras()
        print(f"[DEBUG] 카메라 초기화 완료")

        # Start update loops
        self.update_frying_left()
        self.update_frying_right()
        self.update_observe_left()
        self.update_observe_right()
        self.update_clock()

        # Start periodic MQTT publishing
        if MQTT_ENABLED:
            self.publish_mqtt_periodic()

        # Fullscreen toggle
        self.is_fullscreen = False
        self.root.bind('<F11>', lambda e: self.toggle_fullscreen())
        self.root.bind('<Escape>', lambda e: self.exit_fullscreen())

        # Cleanup on close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def init_gpio(self):
        """Initialize GPIO for 24V Omron Relay control (via ULN2803)"""
        try:
            GPIO.setmode(GPIO.BOARD)
            GPIO.setup(29, GPIO.OUT, initial=GPIO.LOW)  # Pin 29 for Relay control
            GPIO.setup(31, GPIO.OUT, initial=GPIO.LOW)  # Pin 31 for Relay control
            print(f"[GPIO] Pin 29, 31 initialized for Relay control (초기 상태: OFF)")
            print(f"[GPIO] Relay mode: {self.relay_mode}")
        except Exception as e:
            print(f"[GPIO] 초기화 실패: {e}")

    def relay_turn_on(self):
        """Turn on 24V Omron Relay (자체 장비 ON)"""
        if not self.relay_enabled:
            try:
                if self.relay_mode == 'pulse':
                    # Pulse mode: Pin 31 (ON signal) -> HIGH -> wait -> LOW
                    GPIO.output(31, GPIO.HIGH)
                    time.sleep(0.2)  # 200ms pulse
                    GPIO.output(31, GPIO.LOW)
                    print("=" * 50)
                    print("Jetson #2 장비 ON (Pin 31 펄스 신호)")
                    print("=" * 50)
                else:
                    # Continuous mode: Keep HIGH
                    GPIO.output(31, GPIO.HIGH)
                    print("=" * 50)
                    print("Jetson #2 장비 ON (Pin 31 계속 HIGH)")
                    print("=" * 50)

                self.relay_enabled = True
            except Exception as e:
                print(f"[GPIO] Relay ON 실패: {e}")

    def relay_turn_off(self):
        """Turn off 24V Omron Relay (자체 장비 OFF)"""
        if self.relay_enabled:
            try:
                if self.relay_mode == 'pulse':
                    # Pulse mode: Pin 29 (OFF signal) -> HIGH -> wait -> LOW
                    GPIO.output(29, GPIO.HIGH)
                    time.sleep(0.2)  # 200ms pulse
                    GPIO.output(29, GPIO.LOW)
                    print("=" * 50)
                    print("Jetson #2 장비 OFF (Pin 29 펄스 신호)")
                    print("=" * 50)
                else:
                    # Continuous mode: Set LOW
                    GPIO.output(29, GPIO.LOW)
                    print("=" * 50)
                    print("Jetson #2 장비 OFF (Pin 29 LOW)")
                    print("=" * 50)

                self.relay_enabled = False
            except Exception as e:
                print(f"[GPIO] Relay OFF 실패: {e}")

    def init_mqtt(self):
        """Initialize MQTT client"""
        try:
            self.mqtt_client = MQTTClient(
                broker=MQTT_BROKER,
                port=MQTT_PORT,
                client_id=MQTT_CLIENT_ID
            )

            # Connect to broker FIRST
            if self.mqtt_client.connect(blocking=True, timeout=5.0):
                print(f"[MQTT] 연결 성공: {MQTT_BROKER}:{MQTT_PORT}")
                print(f"[MQTT] Device: {DEVICE_ID} ({DEVICE_NAME}) @ {get_ip_address()}")

                # Subscribe AFTER connection
                self.mqtt_client.subscribe(MQTT_TOPIC_POT1_OIL_TEMP, self.on_pot1_oil_temp)
                self.mqtt_client.subscribe(MQTT_TOPIC_POT1_PROBE_TEMP, self.on_pot1_probe_temp)
                self.mqtt_client.subscribe(MQTT_TOPIC_POT2_OIL_TEMP, self.on_pot2_oil_temp)
                self.mqtt_client.subscribe(MQTT_TOPIC_POT2_PROBE_TEMP, self.on_pot2_probe_temp)
                self.mqtt_client.subscribe(MQTT_TOPIC_FRYING_POT1_FOOD_TYPE, self.on_frying_pot1_food_type)
                self.mqtt_client.subscribe(MQTT_TOPIC_FRYING_POT1_CONTROL, self.on_frying_pot1_control)
                self.mqtt_client.subscribe(MQTT_TOPIC_FRYING_POT2_FOOD_TYPE, self.on_frying_pot2_food_type)
                self.mqtt_client.subscribe(MQTT_TOPIC_FRYING_POT2_CONTROL, self.on_frying_pot2_control)
                self.mqtt_client.subscribe("calibration/vibration/control", self.on_vibration_control)
                jetson1_relay_topic = config.get('mqtt_topic_jetson1_relay', 'jetson1/relay/status')
                self.mqtt_client.subscribe(jetson1_relay_topic, self.on_jetson1_relay_status)
                self.mqtt_client.subscribe(MQTT_TOPIC_ROBOT_STATUS, self.on_robot_status)

                print(f"[MQTT] 구독 토픽 (로봇→Jetson):")
                print(f"  - {MQTT_TOPIC_POT1_OIL_TEMP}")
                print(f"  - {MQTT_TOPIC_POT1_PROBE_TEMP}")
                print(f"  - {MQTT_TOPIC_POT2_OIL_TEMP}")
                print(f"  - {MQTT_TOPIC_POT2_PROBE_TEMP}")
                print(f"  - {MQTT_TOPIC_FRYING_POT1_FOOD_TYPE}")
                print(f"  - {MQTT_TOPIC_FRYING_POT1_CONTROL}")
                print(f"  - {MQTT_TOPIC_FRYING_POT2_FOOD_TYPE}")
                print(f"  - {MQTT_TOPIC_FRYING_POT2_CONTROL}")
                print(f"  - calibration/vibration/control")
                print(f"  - {jetson1_relay_topic} (Jetson #1 릴레이 동기화)")
                print(f"  - {MQTT_TOPIC_ROBOT_STATUS} (로봇 PC 상태)")
                print(f"[MQTT] 발행 토픽 (Jetson→로봇):")
                print(f"  - {MQTT_TOPIC_STATUS}")

                # Publish initial status
                self.publish_status()
                print(f"[MQTT] 초기 상태 발행 완료")
            else:
                print("[MQTT] 연결 실패")
                self.mqtt_client = None
        except Exception as e:
            print(f"[MQTT] 연결 실패: {e}")
            self.mqtt_client = None

    def on_pot1_oil_temp(self, client, userdata, message):
        """MQTT callback for POT1 oil temperature"""
        try:
            self.oil_temp_left = float(message.payload.decode())

            # Store metadata during POT1 data collection
            if self.pot1_collecting:
                from datetime import datetime
                self.pot1_metadata.append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "type": "oil_temperature",
                    "pot": "pot1",
                    "value": self.oil_temp_left,
                    "unit": "celsius"
                })
            # LEGACY: Also store in legacy collection
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

    def on_pot2_oil_temp(self, client, userdata, message):
        """MQTT callback for POT2 oil temperature"""
        try:
            self.oil_temp_right = float(message.payload.decode())

            # Store metadata during POT2 data collection
            if self.pot2_collecting:
                from datetime import datetime
                self.pot2_metadata.append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "type": "oil_temperature",
                    "pot": "pot2",
                    "value": self.oil_temp_right,
                    "unit": "celsius"
                })
            # LEGACY: Also store in legacy collection
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

    def on_pot1_probe_temp(self, client, userdata, message):
        """MQTT callback for POT1 probe temperature"""
        try:
            self.probe_temp_left = float(message.payload.decode())

            # Store metadata during POT1 data collection
            if self.pot1_collecting:
                from datetime import datetime
                self.pot1_metadata.append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "type": "probe_temperature",
                    "pot": "pot1",
                    "value": self.probe_temp_left,
                    "unit": "celsius"
                })

                # Auto-mark completion if target temperature reached
                if not self.pot1_completion_marked and self.probe_temp_left >= TARGET_PROBE_TEMP:
                    print(f"[POT1] 목표 온도 도달: {self.probe_temp_left}°C")
                    self.pot1_completion_marked = True
                    self.pot1_completion_time = datetime.now()
                    self.pot1_completion_info = {
                        "method": f"auto (probe_temp >= {TARGET_PROBE_TEMP}°C)",
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "probe_temp": self.probe_temp_left,
                        "oil_temp": self.oil_temp_left,
                        "elapsed_time_sec": (datetime.now() - self.pot1_start_time).total_seconds() if self.pot1_start_time else 0
                    }

            # LEGACY: Also store in legacy collection
            if self.data_collection_active:
                from datetime import datetime
                self.collection_metadata.append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "type": "probe_temperature",
                    "position": "left",
                    "value": self.probe_temp_left,
                    "unit": "celsius"
                })
                if not self.collection_completion_marked and self.probe_temp_left >= TARGET_PROBE_TEMP:
                    self.mark_completion_auto("left", self.probe_temp_left)
        except:
            pass

    def on_pot2_probe_temp(self, client, userdata, message):
        """MQTT callback for POT2 probe temperature"""
        try:
            self.probe_temp_right = float(message.payload.decode())

            # Store metadata during POT2 data collection
            if self.pot2_collecting:
                from datetime import datetime
                self.pot2_metadata.append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "type": "probe_temperature",
                    "pot": "pot2",
                    "value": self.probe_temp_right,
                    "unit": "celsius"
                })

                # Auto-mark completion if target temperature reached
                if not self.pot2_completion_marked and self.probe_temp_right >= TARGET_PROBE_TEMP:
                    print(f"[POT2] 목표 온도 도달: {self.probe_temp_right}°C")
                    self.pot2_completion_marked = True
                    self.pot2_completion_time = datetime.now()
                    self.pot2_completion_info = {
                        "method": f"auto (probe_temp >= {TARGET_PROBE_TEMP}°C)",
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "probe_temp": self.probe_temp_right,
                        "oil_temp": self.oil_temp_right,
                        "elapsed_time_sec": (datetime.now() - self.pot2_start_time).total_seconds() if self.pot2_start_time else 0
                    }

            # LEGACY: Also store in legacy collection
            if self.data_collection_active:
                from datetime import datetime
                self.collection_metadata.append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "type": "probe_temperature",
                    "position": "right",
                    "value": self.probe_temp_right,
                    "unit": "celsius"
                })
                if not self.collection_completion_marked and self.probe_temp_right >= TARGET_PROBE_TEMP:
                    self.mark_completion_auto("right", self.probe_temp_right)
        except:
            pass

    def on_food_type(self, client, userdata, message):
        """MQTT callback for food type - AUTO START collection"""
        try:
            self.current_food_type = message.payload.decode()
            print(f"[MQTT] 음식 종류 수신: {self.current_food_type}")

            # AUTO START: If not collecting, start automatically
            if not self.data_collection_active:
                print(f"[MQTT] 자동 수집 시작 - 음식: {self.current_food_type}")
                self.root.after(0, self.start_data_collection)
            else:
                # If already collecting, store as metadata event
                from datetime import datetime
                self.collection_metadata.append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "type": "food_type_change",
                    "value": self.current_food_type
                })
                print(f"[MQTT] 수집 중 음식 종류 변경: {self.current_food_type}")
        except Exception as e:
            print(f"[MQTT] 음식 종류 수신 오류: {e}")

    def on_frying_control(self, client, userdata, message):
        """MQTT callback for frying control commands - AUTO STOP"""
        try:
            command = message.payload.decode().strip().lower()
            print(f"[MQTT] 튀김 제어 명령 수신: {command}")

            if command == "stop":
                if self.data_collection_active:
                    print(f"[MQTT] 자동 수집 중지")
                    self.root.after(0, self.stop_data_collection)
                else:
                    print(f"[MQTT] 수집 중이 아님 - 무시")
        except Exception as e:
            print(f"[MQTT] 제어 명령 수신 오류: {e}")

    # POT1/POT2 Separate Control MQTT Callbacks
    def on_frying_pot1_food_type(self, client, userdata, message):
        """MQTT callback for pot1 food type - AUTO START collection"""
        try:
            self.pot1_food_type = message.payload.decode()
            print(f"[MQTT POT1] 음식 종류 수신: {self.pot1_food_type}")

            # Cancel previous timeout timer
            if self.pot1_timeout_id is not None:
                self.root.after_cancel(self.pot1_timeout_id)
                self.pot1_timeout_id = None

            if not self.pot1_collecting:
                print(f"[MQTT POT1] 자동 수집 시작 - 음식: {self.pot1_food_type}")
                self.root.after(0, self.start_pot1_collection)
            else:
                # Store metadata event
                from datetime import datetime
                self.pot1_metadata.append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "type": "food_type_change",
                    "value": self.pot1_food_type
                })
                print(f"[MQTT POT1] 이미 수집 중 (타이머 리셋)")

            # Start new timeout timer
            timeout_ms = self.pot1_timeout_seconds * 1000
            self.pot1_timeout_id = self.root.after(timeout_ms, self.on_pot1_timeout)
            print(f"[MQTT POT1] 타임아웃 {self.pot1_timeout_seconds}초 시작")

        except Exception as e:
            print(f"[MQTT POT1] 음식 종류 수신 오류: {e}")

    def on_frying_pot1_control(self, client, userdata, message):
        """MQTT callback for pot1 control commands (optional - timeout auto-stops)"""
        try:
            command = message.payload.decode().strip().lower()
            print(f"[MQTT POT1] 제어 명령 수신: {command}")

            if command == "stop":
                # Cancel timeout timer
                if self.pot1_timeout_id is not None:
                    self.root.after_cancel(self.pot1_timeout_id)
                    self.pot1_timeout_id = None

                if self.pot1_collecting:
                    print(f"[MQTT POT1] 명시적 중지")
                    self.root.after(0, self.stop_pot1_collection)
                else:
                    print(f"[MQTT POT1] 수집 중이 아님 - 무시")
        except Exception as e:
            print(f"[MQTT POT1] 제어 명령 수신 오류: {e}")

    def on_frying_pot2_food_type(self, client, userdata, message):
        """MQTT callback for pot2 food type - AUTO START collection"""
        try:
            self.pot2_food_type = message.payload.decode()
            print(f"[MQTT POT2] 음식 종류 수신: {self.pot2_food_type}")

            # Cancel previous timeout timer
            if self.pot2_timeout_id is not None:
                self.root.after_cancel(self.pot2_timeout_id)
                self.pot2_timeout_id = None

            if not self.pot2_collecting:
                print(f"[MQTT POT2] 자동 수집 시작 - 음식: {self.pot2_food_type}")
                self.root.after(0, self.start_pot2_collection)
            else:
                # Store metadata event
                from datetime import datetime
                self.pot2_metadata.append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "type": "food_type_change",
                    "value": self.pot2_food_type
                })
                print(f"[MQTT POT2] 이미 수집 중 (타이머 리셋)")

            # Start new timeout timer
            timeout_ms = self.pot2_timeout_seconds * 1000
            self.pot2_timeout_id = self.root.after(timeout_ms, self.on_pot2_timeout)
            print(f"[MQTT POT2] 타임아웃 {self.pot2_timeout_seconds}초 시작")

        except Exception as e:
            print(f"[MQTT POT2] 음식 종류 수신 오류: {e}")

    def on_frying_pot2_control(self, client, userdata, message):
        """MQTT callback for pot2 control commands (optional - timeout auto-stops)"""
        try:
            command = message.payload.decode().strip().lower()
            print(f"[MQTT POT2] 제어 명령 수신: {command}")

            if command == "stop":
                # Cancel timeout timer
                if self.pot2_timeout_id is not None:
                    self.root.after_cancel(self.pot2_timeout_id)
                    self.pot2_timeout_id = None

                if self.pot2_collecting:
                    print(f"[MQTT POT2] 명시적 중지")
                    self.root.after(0, self.stop_pot2_collection)
                else:
                    print(f"[MQTT POT2] 수집 중이 아님 - 무시")
        except Exception as e:
            print(f"[MQTT POT2] 제어 명령 수신 오류: {e}")

    # Timeout callbacks
    def on_pot1_timeout(self):
        """POT1 timeout - auto-stop if no food_type message for N seconds"""
        try:
            if self.pot1_collecting:
                print(f"[POT1 타임아웃] {self.pot1_timeout_seconds}초 동안 메시지 없음 → 자동 중지")
                self.stop_pot1_collection()
            self.pot1_timeout_id = None
        except Exception as e:
            print(f"[POT1 타임아웃] 오류: {e}")

    def on_pot2_timeout(self):
        """POT2 timeout - auto-stop if no food_type message for N seconds"""
        try:
            if self.pot2_collecting:
                print(f"[POT2 타임아웃] {self.pot2_timeout_seconds}초 동안 메시지 없음 → 자동 중지")
                self.stop_pot2_collection()
            self.pot2_timeout_id = None
        except Exception as e:
            print(f"[POT2 타임아웃] 오류: {e}")

    def on_robot_status(self, client, userdata, message):
        """로봇 PC 상태 메시지 파싱 (HR/Status)

        메시지 형식:
        {
            "Status": [
                {"DeviceNum": "0", "PTNum": "0", "NowRecipe": "...", "ProcessType": "...", ...},
                {"DeviceNum": "0", "PTNum": "1", "NowRecipe": "...", "ProcessType": "...", ...}
            ],
            "RBMotion": 1,
            "VibrationRequest": false
        }

        DeviceNum/PTNum 매핑:
        - DeviceNum "0" = 튀김 (Jetson2)
        - DeviceNum "1" = 볶음 (Jetson1)
        - PTNum "0" = 왼쪽, "1" = 오른쪽
        """
        try:
            payload = message.payload.decode()
            data = json.loads(payload)

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

            # Status 배열 추출
            status_list = data.get("Status", [])
            if not status_list:
                print(f"[로봇상태] Status 배열 없음")
                return

            # 각 솥 정보 처리 - Jetson2는 튀김솥(DeviceNum=0)만 처리
            for pot_data in status_list:
                device_num = pot_data.get("DeviceNum", "")

                # Jetson2는 튀김솥(DeviceNum=0)만 처리
                if device_num != "0":
                    continue

                pot_num = pot_data.get("PTNum", "")  # 0: 왼쪽, 1: 오른쪽

                # 필요한 정보 추출
                recipe = pot_data.get("NowRecipe", "")
                process_type = pot_data.get("ProcessType", "")  # 투입/조리/배출
                rb_status = pot_data.get("RBstatus", "")
                running_time = pot_data.get("RunningTime", "")
                target_time = pot_data.get("TargetTime", "")
                mode = pot_data.get("Mode", "")

                # Potstatus 정보
                pot_status = pot_data.get("Potstatus", {})
                temp = pot_status.get("PT_Temp", 0)
                power = pot_status.get("PT_Power", "False")

                # GUI 업데이트 요청을 Queue에 저장 (스레드 안전)
                self._robot_status_update = (pot_num, process_type, recipe, temp, running_time)

                # 디버그 출력
                print(f"[로봇상태] 튀김솥 PT{pot_num} | {process_type} | {recipe} | 온도:{temp}°C | {running_time}")

                # 녹화 시작/중지 트리거: 투입 시 시작, 배출 후 N초 뒤 종료
                if pot_num == "0":  # 왼쪽 = POT1
                    if process_type == "투입":
                        # 배출 타이머가 있으면 취소 (다시 투입된 경우)
                        if self.pot1_discharge_timer_id:
                            self.root.after_cancel(self.pot1_discharge_timer_id)
                            self.pot1_discharge_timer_id = None
                            print(f"[로봇상태] POT1(왼쪽) 배출 타이머 취소 (재투입)")
                        if not self.pot1_collecting:
                            self.pot1_food_type = recipe if recipe else "unknown"
                            print(f"[로봇상태] POT1(왼쪽) 데이터 수집 시작 - {self.pot1_food_type}")
                            self.root.after(0, self.start_pot1_collection)
                    elif process_type == "배출":
                        if self.pot1_collecting and not self.pot1_discharge_timer_id:
                            delay_ms = RECORDING_DELAY_AFTER_DISCHARGE * 1000
                            print(f"[로봇상태] POT1(왼쪽) 배출 감지 - {RECORDING_DELAY_AFTER_DISCHARGE}초 후 수집 종료 예정")
                            self.pot1_discharge_timer_id = self.root.after(delay_ms, self._delayed_stop_pot1_collection)

                elif pot_num == "1":  # 오른쪽 = POT2
                    if process_type == "투입":
                        # 배출 타이머가 있으면 취소 (다시 투입된 경우)
                        if self.pot2_discharge_timer_id:
                            self.root.after_cancel(self.pot2_discharge_timer_id)
                            self.pot2_discharge_timer_id = None
                            print(f"[로봇상태] POT2(오른쪽) 배출 타이머 취소 (재투입)")
                        if not self.pot2_collecting:
                            self.pot2_food_type = recipe if recipe else "unknown"
                            print(f"[로봇상태] POT2(오른쪽) 데이터 수집 시작 - {self.pot2_food_type}")
                            self.root.after(0, self.start_pot2_collection)
                    elif process_type == "배출":
                        if self.pot2_collecting and not self.pot2_discharge_timer_id:
                            delay_ms = RECORDING_DELAY_AFTER_DISCHARGE * 1000
                            print(f"[로봇상태] POT2(오른쪽) 배출 감지 - {RECORDING_DELAY_AFTER_DISCHARGE}초 후 수집 종료 예정")
                            self.pot2_discharge_timer_id = self.root.after(delay_ms, self._delayed_stop_pot2_collection)

        except json.JSONDecodeError as e:
            print(f"[로봇상태] JSON 파싱 오류: {e}")
        except Exception as e:
            print(f"[로봇상태] 처리 오류: {e}")

    def _update_robot_status_gui(self, pot_num, process_type, recipe, temp, running_time):
        """로봇 상태를 GUI에 반영 (메인 스레드에서 호출)"""
        try:
            # POT1 (왼쪽 튀김솥) - PTNum "0"
            if pot_num == "0":
                if hasattr(self, 'pot1_recipe_label'):
                    self.pot1_recipe_label.config(text=f"레시피: {recipe}" if recipe else "레시피: -")
                if hasattr(self, 'pot1_process_label'):
                    self.pot1_process_label.config(text=f"{process_type}" if process_type else "대기")
                if hasattr(self, 'pot1_time_label'):
                    self.pot1_time_label.config(text=f"{running_time}" if running_time else "-")

            # POT2 (오른쪽 튀김솥) - PTNum "1"
            elif pot_num == "1":
                if hasattr(self, 'pot2_recipe_label'):
                    self.pot2_recipe_label.config(text=f"레시피: {recipe}" if recipe else "레시피: -")
                if hasattr(self, 'pot2_process_label'):
                    self.pot2_process_label.config(text=f"{process_type}" if process_type else "대기")
                if hasattr(self, 'pot2_time_label'):
                    self.pot2_time_label.config(text=f"{running_time}" if running_time else "-")

        except Exception as e:
            print(f"[로봇상태] GUI 업데이트 오류: {e}")

    def publish_status(self):
        """Publish unified status to single topic: jetson2/status"""
        if not self.mqtt_client or not MQTT_ENABLED:
            return

        try:
            status_data = {
                "device_id": DEVICE_ID,
                "device_name": DEVICE_NAME,
                "ip_address": get_ip_address(),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "ai_mode": AI_MODE_ENABLED,
                "frying": {
                    "left": self.pot1_pot_status,
                    "right": self.pot2_pot_status
                },
                "observe": {
                    "left": self.observe_left_state if self.observe_left_state is not None else "UNKNOWN",
                    "right": self.observe_right_state if self.observe_right_state is not None else "UNKNOWN"
                },
                "vibration": {
                    "status": self.vibration_status
                },
                "system": self.system_info.get_dynamic_info() if hasattr(self, 'system_info') else {}
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
        # jetson2/status에 통합됨 - 이 함수는 더 이상 사용하지 않음
        pass

    def _init_fonts(self):
        """Pre-load fonts to avoid Segfault on first Label creation"""
        # 폰트 시스템 초기화를 완전히 건너뛰고 기본 폰트만 사용
        # tkfont.Font() 호출 자체가 Jetson에서 세그폴트를 일으킬 수 있음
        self.default_font = "TkDefaultFont"
        self.fonts = {}
        print(f"[폰트] 기본 폰트 사용: {self.default_font}")

    def build_gui(self):
        """Build the main GUI layout - WHITE MODE with compact header"""
        print(f"[DEBUG] build_gui: header_frame 생성...")
        # Top header - 1줄 컴팩트 레이아웃 (45px)
        header_height = 45
        header_frame = tk.Frame(self.root, bg=COLOR_PANEL, height=header_height, bd=1, relief=tk.FLAT)
        header_frame.pack(fill=tk.X, padx=0, pady=0)
        header_frame.pack_propagate(False)

        print(f"[DEBUG] build_gui: 첫 번째 Label 생성 (폰트 로딩)...", flush=True)
        # Tkinter 초기화 완료 대기
        self.root.update_idletasks()
        print(f"[DEBUG] build_gui: update_idletasks 완료", flush=True)

        # 1줄 레이아웃: 모든 요소를 가로로 배치
        # LEFT: MQTT 상태 (클릭 시 팝업)
        self.mqtt_status_btn = tk.Button(header_frame, text="● MQTT(0)",
                 font=(FONT_FAMILY, 10, "bold"),
                 command=self.show_mqtt_status_popup,
                 bg=COLOR_PANEL, fg=COLOR_ERROR,
                 relief=tk.FLAT, bd=0, cursor="hand2",
                 padx=5, pady=8)
        self.mqtt_status_btn.pack(side=tk.LEFT, padx=(5, 2))
        print(f"[DEBUG] build_gui: Label 생성 성공!", flush=True)

        # 구분선
        tk.Frame(header_frame, width=1, bg=COLOR_TEXT_LIGHT).pack(side=tk.LEFT, fill=tk.Y, padx=3, pady=8)

        # 수집 상태 표시
        self.recording_status_label = tk.Label(header_frame, text="",
                                           font=(FONT_FAMILY, 10, "bold"),
                                           bg=COLOR_PANEL, fg=COLOR_ERROR)
        self.recording_status_label.pack(side=tk.LEFT, padx=3)

        # 구분선 (수집 상태용 - 수집 중일 때만 보임)
        self.recording_separator = tk.Frame(header_frame, width=1, bg=COLOR_TEXT_LIGHT)

        # 시스템 상태
        self.system_status_label = tk.Label(header_frame, text="정상",
                                           font=(FONT_FAMILY, 10),
                                           bg=COLOR_PANEL, fg=COLOR_OK)
        self.system_status_label.pack(side=tk.LEFT, padx=3)

        # 구분선
        tk.Frame(header_frame, width=1, bg=COLOR_TEXT_LIGHT).pack(side=tk.LEFT, fill=tk.Y, padx=3, pady=8)

        # 날짜/시간 통합
        self.datetime_label = tk.Label(header_frame, text="--/-- --:--",
                                   font=(FONT_FAMILY, 11, "bold"),
                                   bg=COLOR_PANEL, fg=COLOR_INFO)
        self.datetime_label.pack(side=tk.LEFT, padx=3)

        # 구분선
        tk.Frame(header_frame, width=1, bg=COLOR_TEXT_LIGHT).pack(side=tk.LEFT, fill=tk.Y, padx=3, pady=8)

        # 연구실 이름 (축소)
        tk.Label(header_frame, text="SFLAB",
                font=(FONT_FAMILY, 11, "bold"),
                bg=COLOR_PANEL, fg=COLOR_ACCENT).pack(side=tk.LEFT, padx=3)

        # 구분선
        tk.Frame(header_frame, width=1, bg=COLOR_TEXT_LIGHT).pack(side=tk.LEFT, fill=tk.Y, padx=3, pady=8)

        # 디스크 용량 (축소)
        self.disk_label = tk.Label(header_frame, text="💾 --/--GB",
                                   font=(FONT_FAMILY, 10),
                                   bg=COLOR_PANEL, fg=COLOR_TEXT_LIGHT)
        self.disk_label.pack(side=tk.LEFT, padx=3)

        # RIGHT: 버튼들 (오른쪽 정렬)
        # Settings button
        tk.Button(header_frame, text="설정",
                 font=(FONT_FAMILY, 10, "bold"),
                 command=self.open_settings, bg=COLOR_BUTTON, fg="white",
                 relief=tk.FLAT, bd=0, activebackground=COLOR_BUTTON_HOVER,
                 padx=6, pady=4).pack(side=tk.RIGHT, padx=2)

        # Vibration check toggle button
        self.vibration_check_btn = tk.Button(header_frame, text="진동",
                 font=(FONT_FAMILY, 10, "bold"),
                 command=self.toggle_vibration_check, bg=COLOR_INFO, fg="white",
                 relief=tk.FLAT, bd=0, activebackground=COLOR_BUTTON_HOVER,
                 padx=6, pady=4)
        self.vibration_check_btn.pack(side=tk.RIGHT, padx=2)

        # PC Status button
        tk.Button(header_frame, text="PC",
                 font=(FONT_FAMILY, 10, "bold"),
                 command=self.open_pc_status, bg="#00897B", fg="white",
                 relief=tk.FLAT, bd=0, activebackground="#00796B",
                 padx=6, pady=4).pack(side=tk.RIGHT, padx=2)

        # Main content frame (세로 레이아웃 - 768x1024 최적화)
        self.content_frame = tk.Frame(self.root, bg=COLOR_BG)
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Configure grid weights (2 rows x 2 columns for 2x2 grid layout)
        self.content_frame.rowconfigure(0, weight=1)  # Row 0: Frying panels
        self.content_frame.rowconfigure(1, weight=1)  # Row 1: Observe panels
        self.content_frame.columnconfigure(0, weight=1)  # Column 0: Left cameras
        self.content_frame.columnconfigure(1, weight=1)  # Column 1: Right cameras

        # Create 4 camera panels
        self.create_frying_left_panel()
        self.create_frying_right_panel()
        self.create_observe_left_panel()
        self.create_observe_right_panel()

        # Bottom control panel
        self.create_control_panel()

    def create_frying_left_panel(self):
        """Create Frying AI Left camera panel (2x2 그리드 레이아웃)"""
        panel = tk.Frame(self.content_frame, bg=COLOR_PANEL, relief=tk.RAISED, borderwidth=1,
                        highlightbackground=COLOR_PANEL_BORDER, highlightthickness=1)
        panel.grid(row=0, column=0, padx=2, pady=1, sticky="nsew")

        # Title (축소)
        title = tk.Label(panel, text="🍤 튀김 AI - 왼쪽", font=(FONT_FAMILY, 12, "bold"), bg=COLOR_PANEL, fg=COLOR_TEXT)
        title.pack(pady=2)

        # Camera preview (세로 레이아웃 - 높이 더 축소)
        preview_container = tk.Frame(panel, bg="black", height=125)
        preview_container.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        preview_container.pack_propagate(False)

        self.frying_left_label = tk.Label(preview_container, bg="black")
        self.frying_left_label.place(x=0, y=0, relwidth=1, relheight=1)

        # Camera number label (top-right)
        self.frying_left_cam_number_label = tk.Label(preview_container, text="Cam 0",
                                                     bg="black", fg="yellow", font=(FONT_FAMILY, 10, "bold"))
        self.frying_left_cam_number_label.place(relx=1.0, rely=0, x=-5, y=5, anchor="ne")

        # Info frame (temperature + color features) - 축소
        info_frame = tk.Frame(panel, bg=COLOR_PANEL)
        info_frame.pack(pady=1)

        # Oil Temperature
        self.frying_left_temp_label = tk.Label(
            info_frame, text="기름: -- °C", font=(FONT_FAMILY, 10), bg=COLOR_PANEL, fg=COLOR_ERROR
        )
        self.frying_left_temp_label.pack()

        # Probe Temperature
        self.frying_left_probe_label = tk.Label(
            info_frame, text="탐침: -- °C", font=(FONT_FAMILY, 10), bg=COLOR_PANEL, fg=COLOR_INFO
        )
        self.frying_left_probe_label.pack()

        # Color features - DISABLED per user request
        # self.frying_left_color_label = tk.Label(
        #     info_frame, text="갈색: --% | 황금: --%", font=(FONT_FAMILY, 10), bg=COLOR_PANEL, fg=COLOR_WARNING
        # )
        # self.frying_left_color_label.pack()

        # Status
        self.frying_left_status = tk.Label(
            panel, text="대기 중", font=(FONT_FAMILY, 10), bg=COLOR_PANEL, fg=COLOR_TEXT_LIGHT
        )
        self.frying_left_status.pack(pady=1)

    def create_frying_right_panel(self):
        """Create Frying AI Right camera panel (2x2 그리드 레이아웃)"""
        panel = tk.Frame(self.content_frame, bg=COLOR_PANEL, relief=tk.RAISED, borderwidth=1,
                        highlightbackground=COLOR_PANEL_BORDER, highlightthickness=1)
        panel.grid(row=0, column=1, padx=2, pady=1, sticky="nsew")

        # Title (축소)
        title = tk.Label(panel, text="🍤 튀김 AI - 오른쪽", font=(FONT_FAMILY, 12, "bold"), bg=COLOR_PANEL, fg=COLOR_TEXT)
        title.pack(pady=2)

        # Camera preview (세로 레이아웃 - 높이 더 축소)
        preview_container = tk.Frame(panel, bg="black", height=125)
        preview_container.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        preview_container.pack_propagate(False)

        self.frying_right_label = tk.Label(preview_container, bg="black")
        self.frying_right_label.place(x=0, y=0, relwidth=1, relheight=1)

        # Camera number label (top-right)
        self.frying_right_cam_number_label = tk.Label(preview_container, text="Cam 1",
                                                      bg="black", fg="yellow", font=(FONT_FAMILY, 10, "bold"))
        self.frying_right_cam_number_label.place(relx=1.0, rely=0, x=-5, y=5, anchor="ne")

        # Info frame (temperature + color features) - 축소
        info_frame = tk.Frame(panel, bg=COLOR_PANEL)
        info_frame.pack(pady=1)

        # Oil Temperature
        self.frying_right_temp_label = tk.Label(
            info_frame, text="기름: -- °C", font=(FONT_FAMILY, 10), bg=COLOR_PANEL, fg=COLOR_ERROR
        )
        self.frying_right_temp_label.pack()

        # Probe Temperature
        self.frying_right_probe_label = tk.Label(
            info_frame, text="탐침: -- °C", font=(FONT_FAMILY, 10), bg=COLOR_PANEL, fg=COLOR_INFO
        )
        self.frying_right_probe_label.pack()

        # Color features - DISABLED per user request
        # self.frying_right_color_label = tk.Label(
        #     info_frame, text="갈색: --% | 황금: --%", font=(FONT_FAMILY, 10), bg=COLOR_PANEL, fg=COLOR_WARNING
        # )
        # self.frying_right_color_label.pack()

        # Status
        self.frying_right_status = tk.Label(
            panel, text="대기 중", font=(FONT_FAMILY, 10), bg=COLOR_PANEL, fg=COLOR_TEXT_LIGHT
        )
        self.frying_right_status.pack(pady=1)

    def create_observe_left_panel(self):
        """Create Observe_add Left camera panel (2x2 그리드 레이아웃)"""
        panel = tk.Frame(self.content_frame, bg=COLOR_PANEL, relief=tk.RAISED, borderwidth=1,
                        highlightbackground=COLOR_PANEL_BORDER, highlightthickness=1)
        panel.grid(row=1, column=0, padx=2, pady=1, sticky="nsew")

        # Title (축소)
        title = tk.Label(panel, text="🥘 바켓 감지 - 왼쪽", font=(FONT_FAMILY, 12, "bold"), bg=COLOR_PANEL, fg=COLOR_TEXT)
        title.pack(pady=2)

        # Camera preview (세로 레이아웃 - 높이 더 축소)
        preview_container = tk.Frame(panel, bg="black", height=125)
        preview_container.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        preview_container.pack_propagate(False)

        self.observe_left_label = tk.Label(preview_container, bg="black")
        self.observe_left_label.place(x=0, y=0, relwidth=1, relheight=1)

        # Camera number label (top-right)
        self.observe_left_cam_number_label = tk.Label(preview_container, text="Cam 2",
                                                      bg="black", fg="yellow", font=(FONT_FAMILY, 10, "bold"))
        self.observe_left_cam_number_label.place(relx=1.0, rely=0, x=-5, y=5, anchor="ne")

        # Status
        self.observe_left_status = tk.Label(
            panel, text="대기 중", font=(FONT_FAMILY, 10), bg=COLOR_PANEL, fg=COLOR_TEXT_LIGHT
        )
        self.observe_left_status.pack(pady=2)

    def create_observe_right_panel(self):
        """Create Observe_add Right camera panel (2x2 그리드 레이아웃)"""
        panel = tk.Frame(self.content_frame, bg=COLOR_PANEL, relief=tk.RAISED, borderwidth=1,
                        highlightbackground=COLOR_PANEL_BORDER, highlightthickness=1)
        panel.grid(row=1, column=1, padx=2, pady=1, sticky="nsew")

        # Title (축소)
        title = tk.Label(panel, text="🥘 바켓 감지 - 오른쪽", font=(FONT_FAMILY, 12, "bold"), bg=COLOR_PANEL, fg=COLOR_TEXT)
        title.pack(pady=2)

        # Camera preview (세로 레이아웃 - 높이 더 축소)
        preview_container = tk.Frame(panel, bg="black", height=125)
        preview_container.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        preview_container.pack_propagate(False)

        self.observe_right_label = tk.Label(preview_container, bg="black")
        self.observe_right_label.place(x=0, y=0, relwidth=1, relheight=1)

        # Camera number label (top-right)
        self.observe_right_cam_number_label = tk.Label(preview_container, text="Cam 3",
                                                       bg="black", fg="yellow", font=(FONT_FAMILY, 10, "bold"))
        self.observe_right_cam_number_label.place(relx=1.0, rely=0, x=-5, y=5, anchor="ne")

        # Status
        self.observe_right_status = tk.Label(
            panel, text="대기 중", font=(FONT_FAMILY, 10), bg=COLOR_PANEL, fg=COLOR_TEXT_LIGHT
        )
        self.observe_right_status.pack(pady=2)

    def create_control_panel(self):
        """Create bottom control panel (세로 레이아웃 최적화)"""
        control_frame = tk.Frame(self.root, bg=COLOR_BG)
        control_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=3, pady=3)

        # Start/Stop buttons (세로 모드 - 버튼 크기 축소)
        btn_frame = tk.Frame(control_frame, bg=COLOR_BG)
        btn_frame.pack(side=tk.LEFT, padx=5)

        self.btn_start_frying = tk.Button(
            btn_frame,
            text="튀김 시작",
            font=(FONT_FAMILY, 11),
            bg="#27AE60",
            fg="white",
            activebackground="#229954",
            command=self.start_frying_ai,
            width=8,
            height=1,
            relief=tk.FLAT
        )
        self.btn_start_frying.pack(side=tk.LEFT, padx=2)

        self.btn_stop_frying = tk.Button(
            btn_frame,
            text="튀김 중지",
            font=(FONT_FAMILY, 11),
            bg=COLOR_ERROR,
            fg="white",
            activebackground="#C0392B",
            command=self.stop_frying_ai,
            width=8,
            height=1,
            state=tk.DISABLED,
            relief=tk.FLAT
        )
        self.btn_stop_frying.pack(side=tk.LEFT, padx=2)

        self.btn_start_observe = tk.Button(
            btn_frame,
            text="바켓 시작",
            font=(FONT_FAMILY, 11),
            bg="#3498DB",
            fg="white",
            activebackground="#2980B9",
            command=self.start_observe_ai,
            width=8,
            height=1,
            relief=tk.FLAT
        )
        self.btn_start_observe.pack(side=tk.LEFT, padx=2)

        self.btn_stop_observe = tk.Button(
            btn_frame,
            text="바켓 중지",
            font=(FONT_FAMILY, 11),
            bg=COLOR_ERROR,
            fg="white",
            activebackground="#C0392B",
            command=self.stop_observe_ai,
            width=8,
            height=1,
            state=tk.DISABLED,
            relief=tk.FLAT
        )
        self.btn_stop_observe.pack(side=tk.LEFT, padx=2)

        # Data collection buttons (세로 모드 - 버튼 크기 축소)
        separator = tk.Frame(btn_frame, width=2, bg="#BDC3C7")
        separator.pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=3)

        self.btn_start_collection = tk.Button(
            btn_frame,
            text="수집 시작",
            font=(FONT_FAMILY, 11),
            bg="#9B59B6",
            fg="white",
            activebackground="#8E44AD",
            command=self.start_data_collection,
            width=8,
            height=1,
            relief=tk.FLAT
        )
        self.btn_start_collection.pack(side=tk.LEFT, padx=2)

        self.btn_stop_collection = tk.Button(
            btn_frame,
            text="수집 중지",
            font=(FONT_FAMILY, 11),
            bg=COLOR_ERROR,
            fg="white",
            activebackground="#C0392B",
            command=self.stop_data_collection,
            width=8,
            height=1,
            state=tk.DISABLED,
            relief=tk.FLAT
        )
        self.btn_stop_collection.pack(side=tk.LEFT, padx=2)

        # Collection status label (세로 모드 - 폰트 축소)
        status_frame = tk.Frame(control_frame, bg=COLOR_BG)
        status_frame.pack(side=tk.LEFT, padx=10)

        self.collection_status_label = tk.Label(
            status_frame,
            text="수집: 대기 중",
            font=(FONT_FAMILY, 10),
            bg=COLOR_BG,
            fg=COLOR_TEXT
        )
        self.collection_status_label.pack()

        # Exit button (세로 모드 - 버튼 크기 축소)
        self.btn_exit = tk.Button(
            control_frame,
            text="종료",
            font=(FONT_FAMILY, 11),
            bg="#95A5A6",
            fg="white",
            activebackground="#7F8C8D",
            command=self.on_close,
            width=6,
            height=1,
            relief=tk.FLAT
        )
        self.btn_exit.pack(side=tk.RIGHT, padx=5)

    def init_cameras(self):
        """Initialize GMSL cameras based on enabled settings (순차 초기화)"""
        print("[카메라] 카메라 순차 초기화 중...")

        # Initialize cameras to None first
        self.frying_left_cap = None
        self.frying_right_cap = None
        self.observe_left_cap = None
        self.observe_right_cap = None

        # 카메라 초기화 딜레이 (드라이버 안정화)
        CAMERA_INIT_DELAY = 4.0  # 초 (현장 IVC 채널 과부하 방지)

        # Frying AI cameras (video0, video1)
        if FRYING_ENABLED:
            print(f"[카메라] 튀김솥 왼쪽 초기화 중...")
            self.frying_left_cap = GstCamera(
                device_index=FRYING_LEFT_CAMERA_INDEX,
                width=CAMERA_WIDTH,
                height=CAMERA_HEIGHT,
                fps=CAMERA_FPS
            )
            if self.frying_left_cap.start():
                print(f"[카메라] 튀김솥 왼쪽 (video{FRYING_LEFT_CAMERA_INDEX}) 초기화 완료 ✓")
            else:
                print(f"[카메라] 튀김솥 왼쪽 (video{FRYING_LEFT_CAMERA_INDEX}) 초기화 실패 ✗")
                self.frying_left_cap = None

            time.sleep(CAMERA_INIT_DELAY)  # 순차 초기화 딜레이

            print(f"[카메라] 튀김솥 오른쪽 초기화 중...")
            self.frying_right_cap = GstCamera(
                device_index=FRYING_RIGHT_CAMERA_INDEX,
                width=CAMERA_WIDTH,
                height=CAMERA_HEIGHT,
                fps=CAMERA_FPS
            )
            if self.frying_right_cap.start():
                print(f"[카메라] 튀김솥 오른쪽 (video{FRYING_RIGHT_CAMERA_INDEX}) 초기화 완료 ✓")
            else:
                print(f"[카메라] 튀김솥 오른쪽 (video{FRYING_RIGHT_CAMERA_INDEX}) 초기화 실패 ✗")
                self.frying_right_cap = None

            time.sleep(CAMERA_INIT_DELAY)  # 순차 초기화 딜레이
        else:
            print(f"[카메라] 튀김솥 카메라 비활성화됨 (frying_enabled=false)")

        # Observe_add cameras (video2, video3)
        if OBSERVE_ENABLED:
            if OBSERVE_LEFT_ENABLED:
                print(f"[카메라] 바스켓 왼쪽 초기화 중...")
                self.observe_left_cap = GstCamera(
                    device_index=OBSERVE_LEFT_CAMERA_INDEX,
                    width=CAMERA_WIDTH,
                    height=CAMERA_HEIGHT,
                    fps=CAMERA_FPS
                )
                if self.observe_left_cap.start():
                    print(f"[카메라] 바스켓 왼쪽 (video{OBSERVE_LEFT_CAMERA_INDEX}) 초기화 완료 ✓")
                else:
                    print(f"[카메라] 바스켓 왼쪽 (video{OBSERVE_LEFT_CAMERA_INDEX}) 초기화 실패 ✗")
                    self.observe_left_cap = None
                time.sleep(CAMERA_INIT_DELAY)
            else:
                print(f"[카메라] 바스켓 왼쪽 비활성화됨 (observe_left_enabled=false)")

            if OBSERVE_RIGHT_ENABLED:
                print(f"[카메라] 바스켓 오른쪽 초기화 중...")
                self.observe_right_cap = GstCamera(
                    device_index=OBSERVE_RIGHT_CAMERA_INDEX,
                    width=CAMERA_WIDTH,
                    height=CAMERA_HEIGHT,
                    fps=CAMERA_FPS
                )
                if self.observe_right_cap.start():
                    print(f"[카메라] 바스켓 오른쪽 (video{OBSERVE_RIGHT_CAMERA_INDEX}) 초기화 완료 ✓")
                else:
                    print(f"[카메라] 바스켓 오른쪽 (video{OBSERVE_RIGHT_CAMERA_INDEX}) 초기화 실패 ✗")
                    self.observe_right_cap = None
            else:
                print(f"[카메라] 바스켓 오른쪽 비활성화됨 (observe_right_enabled=false)")
        else:
            print(f"[카메라] 바스켓 카메라 비활성화됨 (observe_enabled=false)")

        print("[카메라] 카메라 순차 초기화 완료!")

    def update_clock(self):
        """Update time and date in header"""
        if not self.running:
            return

        now = datetime.now()
        current_second = now.second

        # Only update if second has changed (reduce flickering)
        if not hasattr(self, '_last_second') or self._last_second != current_second:
            self._last_second = current_second
            # 날짜/시간 통합 표시
            self.datetime_label.config(text=now.strftime("%m/%d %H:%M:%S"))

            # MQTT 상태 업데이트
            self._update_mqtt_status_display()

            # 수집 상태 업데이트
            self._update_recording_status_display()

            # Update disk space (every minute to avoid overhead)
            if current_second == 0 or not hasattr(self, '_disk_updated'):
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
                    self._disk_updated = True
                except Exception as e:
                    self.disk_label.config(text="💾 --", fg=COLOR_TEXT)

        # 로봇 상태 업데이트 처리 (MQTT 콜백에서 전달받음)
        if self._robot_status_update:
            try:
                pn, pt, r, t, rt = self._robot_status_update
                self._update_robot_status_gui(pn, pt, r, t, rt)
                self._robot_status_update = None
            except Exception as e:
                pass  # 무시

        self.root.after(200, self.update_clock)

    def update_frying_left(self):
        """Update Frying AI left camera - OPTIMIZED with frame skip"""
        if not self.running:
            return

        if self.frying_left_cap is None:
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

                        # Extract color features (kept for future use, not displayed)
                        # feat = result.color_features
                        # brown_pct = int(feat.brown_ratio * 100)
                        # golden_pct = int(feat.golden_ratio * 100)
                        # area_pct = int(result.food_area_ratio * 100)

                        # Draw features on frame - DISABLED per user request
                        # cv2.putText(vis, f"Brown: {brown_pct}%", (16, 40),
                        #             cv2.FONT_HERSHEY_SIMPLEX, 1, (60, 120, 200), 2)
                        # cv2.putText(vis, f"Golden: {golden_pct}%", (16, 80),
                        #             cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 200, 255), 2)
                        # cv2.putText(vis, f"Area: {area_pct}%", (16, 120),
                        #             cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2)

                        # Update GUI labels - DISABLED per user request
                        # self.frying_left_color_label.config(
                        #     text=f"갈색: {brown_pct}% | 황금: {golden_pct}%"
                        # )
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

            # Store latest frame for data collection (매 프레임 저장)
            self.latest_frying_left_frame = frame.copy()

            # GUI 표시는 N프레임마다 (부하 감소)
            self.gui_frame_skip_frying_left += 1
            if self.gui_frame_skip_frying_left >= GUI_FRAME_SKIP:
                self.gui_frame_skip_frying_left = 0

                # Display (resize once)
                display_frame = cv2.resize(vis, (DISPLAY_WIDTH, DISPLAY_HEIGHT), interpolation=cv2.INTER_NEAREST)
                display_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)

                img = Image.fromarray(display_frame)
                imgtk = ImageTk.PhotoImage(image=img)
                self.frying_left_label.imgtk = imgtk
                self.frying_left_label.configure(image=imgtk)

            # POT1 data collection timer
            if self.pot1_collecting:
                self.pot1_timer += GUI_UPDATE_INTERVAL / 1000.0
                if self.pot1_timer >= self.collection_interval:
                    self.pot1_timer = 0
                    # Trigger POT1 data collection (cameras 0, 2, 3)
                    self.save_pot1_data(
                        self.latest_frying_left_frame,
                        self.latest_observe_left_frame,
                        self.latest_observe_right_frame
                    )

            # LEGACY: Data collection timer (shared across all active cameras)
            if self.data_collection_active:
                self.collection_timer += GUI_UPDATE_INTERVAL / 1000.0
                if self.collection_timer >= self.collection_interval:
                    self.collection_timer = 0
                    # Trigger data collection from all cameras
                    self.save_collection_data(
                        self.latest_frying_left_frame,
                        self.latest_frying_right_frame,
                        self.latest_observe_left_frame,
                        self.latest_observe_right_frame
                    )

        self.root.after(GUI_UPDATE_INTERVAL, self.update_frying_left)

    def update_frying_right(self):
        """Update Frying AI right camera - OPTIMIZED with frame skip"""
        if not self.running:
            return

        if self.frying_right_cap is None:
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

                        # Extract color features (kept for future use, not displayed)
                        # feat = result.color_features
                        # brown_pct = int(feat.brown_ratio * 100)
                        # golden_pct = int(feat.golden_ratio * 100)
                        # area_pct = int(result.food_area_ratio * 100)

                        # Draw features on frame - DISABLED per user request
                        # cv2.putText(vis, f"Brown: {brown_pct}%", (16, 40),
                        #             cv2.FONT_HERSHEY_SIMPLEX, 1, (60, 120, 200), 2)
                        # cv2.putText(vis, f"Golden: {golden_pct}%", (16, 80),
                        #             cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 200, 255), 2)
                        # cv2.putText(vis, f"Area: {area_pct}%", (16, 120),
                        #             cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2)

                        # Update GUI labels - DISABLED per user request
                        # self.frying_right_color_label.config(
                        #     text=f"갈색: {brown_pct}% | 황금: {golden_pct}%"
                        # )
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

            # Store latest frame for data collection (매 프레임 저장)
            self.latest_frying_right_frame = frame.copy()

            # GUI 표시는 N프레임마다 (부하 감소)
            self.gui_frame_skip_frying_right += 1
            if self.gui_frame_skip_frying_right >= GUI_FRAME_SKIP:
                self.gui_frame_skip_frying_right = 0

                # Display
                display_frame = cv2.resize(vis, (DISPLAY_WIDTH, DISPLAY_HEIGHT), interpolation=cv2.INTER_NEAREST)
                display_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)

                img = Image.fromarray(display_frame)
                imgtk = ImageTk.PhotoImage(image=img)
                self.frying_right_label.imgtk = imgtk
                self.frying_right_label.configure(image=imgtk)

            # Data collection timer (only if frying_left is not active)
            if self.data_collection_active and self.frying_left_cap is None:
                self.collection_timer += GUI_UPDATE_INTERVAL / 1000.0
                if self.collection_timer >= self.collection_interval:
                    self.collection_timer = 0
                    # Trigger data collection from all cameras
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

        if self.observe_left_cap is None:
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

            # Store latest frame for data collection (매 프레임 저장)
            self.latest_observe_left_frame = frame.copy()

            # GUI 표시는 N프레임마다 (부하 감소)
            self.gui_frame_skip_observe_left += 1
            if self.gui_frame_skip_observe_left >= GUI_FRAME_SKIP:
                self.gui_frame_skip_observe_left = 0

                # Display
                display_frame = cv2.resize(vis, (DISPLAY_WIDTH, DISPLAY_HEIGHT), interpolation=cv2.INTER_NEAREST)
                display_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)

                img = Image.fromarray(display_frame)
                imgtk = ImageTk.PhotoImage(image=img)
                self.observe_left_label.imgtk = imgtk
                self.observe_left_label.configure(image=imgtk)

            # POT2 data collection timer
            if self.pot2_collecting:
                self.pot2_timer += GUI_UPDATE_INTERVAL / 1000.0
                if self.pot2_timer >= self.collection_interval:
                    self.pot2_timer = 0
                    # Trigger POT2 data collection (cameras 1, 2, 3)
                    self.save_pot2_data(
                        self.latest_frying_right_frame,
                        self.latest_observe_left_frame,
                        self.latest_observe_right_frame
                    )

            # LEGACY: Data collection timer (only if frying cameras are not active)
            if self.data_collection_active and self.frying_left_cap is None and self.frying_right_cap is None:
                self.collection_timer += GUI_UPDATE_INTERVAL / 1000.0
                if self.collection_timer >= self.collection_interval:
                    self.collection_timer = 0
                    # Trigger data collection from all cameras
                    self.save_collection_data(
                        self.latest_frying_left_frame,
                        self.latest_frying_right_frame,
                        self.latest_observe_left_frame,
                        self.latest_observe_right_frame
                    )

        self.root.after(GUI_UPDATE_INTERVAL, self.update_observe_left)

    def update_observe_right(self):
        """Update Observe_add right camera - OPTIMIZED with GPU + frame skip"""
        if not self.running:
            return

        if self.observe_right_cap is None:
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

            # Store latest frame for data collection (매 프레임 저장)
            self.latest_observe_right_frame = frame.copy()

            # GUI 표시는 N프레임마다 (부하 감소)
            self.gui_frame_skip_observe_right += 1
            if self.gui_frame_skip_observe_right >= GUI_FRAME_SKIP:
                self.gui_frame_skip_observe_right = 0

                # Display
                display_frame = cv2.resize(vis, (DISPLAY_WIDTH, DISPLAY_HEIGHT), interpolation=cv2.INTER_NEAREST)
                display_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)

                img = Image.fromarray(display_frame)
                imgtk = ImageTk.PhotoImage(image=img)
                self.observe_right_label.imgtk = imgtk
                self.observe_right_label.configure(image=imgtk)

            # Data collection timer (last fallback - only if all other cameras are not active)
            if (self.data_collection_active and
                self.frying_left_cap is None and
                self.frying_right_cap is None and
                self.observe_left_cap is None):
                self.collection_timer += GUI_UPDATE_INTERVAL / 1000.0
                if self.collection_timer >= self.collection_interval:
                    self.collection_timer = 0
                    # Trigger data collection from all cameras
                    self.save_collection_data(
                        self.latest_frying_left_frame,
                        self.latest_frying_right_frame,
                        self.latest_observe_left_frame,
                        self.latest_observe_right_frame
                    )

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

    def toggle_auto_relay(self, window, status_label):
        """Toggle automatic relay control mode"""
        global AUTO_RELAY_ENABLED

        # Toggle the value
        AUTO_RELAY_ENABLED = not AUTO_RELAY_ENABLED

        # Update config_jetson2.json
        try:
            config['auto_relay_enabled'] = AUTO_RELAY_ENABLED
            with open('config_jetson2.json', 'w', encoding='utf-8') as f:
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
        """Open PC status dialog (matching Jetson #1)"""
        # Create popup window
        status_window = tk.Toplevel(self.root)
        status_window.title("PC 상태")
        status_window.geometry("700x900")
        status_window.configure(bg=COLOR_BG)

        # Center the window
        status_window.transient(self.root)
        status_window.grab_set()
        status_window.attributes('-topmost', True)
        status_window.lift()
        status_window.focus_force()

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
                tk.Label(cpu_frame, text=f"{cpu_percent:.1f}%", font=(FONT_FAMILY, 22, "bold"),
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
                    tk.Label(gpu_frame, text=f"{gpu_percent:.1f}%", font=(FONT_FAMILY, 22, "bold"),
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

        # Relay Control Section
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

        tk.Label(control_frame, text="※ 자동 모드: Jetson #1과 동기화 (MQTT)",
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
                 bg=COLOR_INFO, fg="white", relief=tk.FLAT).pack(pady=20)

        print("[PC상태] PC 상태 창 열림")

    def on_jetson1_relay_status(self, client, userdata, message):
        """MQTT callback for Jetson #1 relay status synchronization"""
        try:
            raw_message = message.payload.decode('utf-8')
            print("=" * 60)
            print(f"[릴레이 동기화] Jetson #1 릴레이 상태 수신:")
            print(f"  Raw: {raw_message}")

            # Parse JSON
            try:
                data = json.loads(raw_message)
                relay_status = data.get('relay_status', '').upper()
                source = data.get('source', 'unknown')
                timestamp = data.get('timestamp', '')

                print(f"  상태: {relay_status}")
                print(f"  소스: {source}")
                print(f"  시각: {timestamp}")

                # Control Jetson #2 relay based on Jetson #1 status
                if relay_status == 'ON':
                    print("[릴레이 동기화] Jetson #1 ON 감지 → Jetson #2 릴레이 ON")
                    self.relay_turn_on()
                elif relay_status == 'OFF':
                    print("[릴레이 동기화] Jetson #1 OFF 감지 → Jetson #2 릴레이 OFF")
                    self.relay_turn_off()
                else:
                    print(f"[릴레이 동기화] 알 수 없는 상태: {relay_status}")

                print("=" * 60)

            except json.JSONDecodeError:
                print(f"[릴레이 동기화] JSON 파싱 실패: {raw_message}")
                print("=" * 60)

        except Exception as e:
            print(f"[릴레이 동기화] 오류: {e}")
            import traceback
            traceback.print_exc()

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
            print(f"[진동] 디버깅 메시지는 journalctl -u jetson2-ai -f 로 확인하세요")

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
            jetson1_relay_topic = config.get('mqtt_topic_jetson1_relay', 'jetson1/relay/status')
            topics = [
                MQTT_TOPIC_POT1_OIL_TEMP,
                MQTT_TOPIC_POT1_PROBE_TEMP,
                MQTT_TOPIC_POT2_OIL_TEMP,
                MQTT_TOPIC_POT2_PROBE_TEMP,
                MQTT_TOPIC_FRYING_POT1_FOOD_TYPE,
                MQTT_TOPIC_FRYING_POT1_CONTROL,
                MQTT_TOPIC_FRYING_POT2_FOOD_TYPE,
                MQTT_TOPIC_FRYING_POT2_CONTROL,
                "calibration/vibration/control",
                jetson1_relay_topic,
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
        if self.pot1_collecting:
            recording_parts.append("POT1")
        if self.pot2_collecting:
            recording_parts.append("POT2")
        if self.data_collection_active:
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

    def show_mqtt_status_popup(self):
        """MQTT 상태 상세 팝업 표시"""
        popup = tk.Toplevel(self.root)
        popup.title("MQTT 상태")
        popup.geometry("450x400")
        popup.configure(bg=COLOR_PANEL)
        popup.transient(self.root)
        popup.grab_set()

        # 연결 상태
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

        # 구분선
        tk.Frame(popup, height=1, bg=COLOR_TEXT_LIGHT).pack(fill=tk.X, padx=10, pady=5)

        # 구독 토픽 목록
        tk.Label(popup, text="구독 중인 토픽:",
                font=(FONT_FAMILY, 11, "bold"),
                bg=COLOR_PANEL, fg=COLOR_TEXT).pack(anchor="w", padx=10)

        # 스크롤 가능한 토픽 리스트
        list_frame = tk.Frame(popup, bg=COLOR_BG)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

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

        # 발행 토픽
        tk.Frame(popup, height=1, bg=COLOR_TEXT_LIGHT).pack(fill=tk.X, padx=10, pady=5)
        tk.Label(popup, text=f"발행 토픽: {MQTT_TOPIC_STATUS}",
                font=(FONT_FAMILY, 10),
                bg=COLOR_PANEL, fg=COLOR_TEXT).pack(anchor="w", padx=10)

        # 닫기 버튼
        tk.Button(popup, text="닫기",
                 font=(FONT_FAMILY, 11, "bold"),
                 command=popup.destroy,
                 bg=COLOR_BUTTON, fg="white",
                 relief=tk.FLAT, padx=20, pady=5).pack(pady=10)

    def open_settings(self):
        """Open settings dialog (placeholder)"""
        showinfo_topmost("설정", "설정 기능은 준비 중입니다.\nconfig_jetson2.json 파일을 직접 수정하세요.")

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

        # If no food type from MQTT, use "manual" as default
        if self.current_food_type == "unknown":
            self.current_food_type = "manual"
            print(f"[수집] 음식 종류 미설정 - 'manual'로 수집 시작")

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
        self.btn_stop_collection.config(state=tk.NORMAL)
        self.collection_status_label.config(
            text=f"수집 중 [{self.current_food_type}]: {self.collection_session_id}",
            fg="#9B59B6"
        )

        print(f"[데이터수집] 시작: {self.collection_session_id}")
        print(f"[데이터수집] 음식 종류: {self.current_food_type} (MQTT)")
        print(f"[데이터수집] 저장 경로: {base_dir}/AI_Data/")
        print(f"[데이터수집] MQTT 메타데이터 수집 활성화")

    def stop_data_collection(self):
        """Stop manual data collection (비동기 처리로 GUI 프리징 방지)"""
        if not self.data_collection_active:
            return

        self.data_collection_active = False

        # 즉시 GUI 업데이트 (프리징 방지)
        self.btn_start_collection.config(state=tk.NORMAL)
        self.btn_stop_collection.config(state=tk.DISABLED)
        self.collection_status_label.config(text="수집: 저장 중...", fg=COLOR_WARNING)

        # 저장에 필요한 데이터 복사 (스레드 안전)
        save_data = {
            "session_id": self.collection_session_id,
            "food_type": self.current_food_type,
            "start_time": self.collection_start_time,
            "frame_counter": self.collection_frame_counter,
            "metadata": self.collection_metadata.copy(),
            "completion_marked": self.collection_completion_marked,
            "completion_info": self.collection_completion_info.copy() if self.collection_completion_info else {},
            "frying_session_dir": self.frying_session_dir,
            "bucket_session_dir": self.bucket_session_dir,
            "collection_interval": self.collection_interval
        }

        # 백그라운드에서 저장 후 메시지박스 표시
        import threading
        threading.Thread(
            target=self._save_collection_data_async,
            args=(save_data,),
            daemon=True
        ).start()

        # Reset session (즉시)
        self.collection_session_id = None
        self.collection_start_time = None
        self.current_food_type = "unknown"

    def _save_collection_data_async(self, save_data):
        """백그라운드에서 JSON 저장 후 메시지박스 표시"""
        from datetime import datetime
        import json

        try:
            end_time = datetime.now()
            duration = (end_time - save_data["start_time"]).total_seconds()

            # Organize temperature data by time
            temperature_timeline = []
            for item in save_data["metadata"]:
                if item["type"] in ["oil_temperature", "probe_temperature"]:
                    existing = next((x for x in temperature_timeline if x["timestamp"] == item["timestamp"]), None)
                    if existing:
                        key = f"{item['type'].replace('_temperature', '_temp')}_{item['position']}"
                        existing[key] = item["value"]
                    else:
                        new_entry = {"timestamp": item["timestamp"]}
                        key = f"{item['type'].replace('_temperature', '_temp')}_{item['position']}"
                        new_entry[key] = item["value"]
                        temperature_timeline.append(new_entry)

            # Save session info with improved metadata
            session_info = {
                "session_id": save_data["session_id"],
                "food_type": save_data["food_type"],
                "start_time": save_data["start_time"].strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
                "duration_sec": duration,
                "collection_interval": save_data["collection_interval"],

                "completion_info": save_data["completion_info"] if save_data["completion_marked"] else None,
                "completion_marked": save_data["completion_marked"],

                "cameras_used": [0, 1, 2, 3],
                "total_frames_saved": save_data["frame_counter"],

                "camera_config": {
                    "resolution": {
                        "width": config.get("camera_width", 1280),
                        "height": config.get("camera_height", 720)
                    },
                    "fps": config.get("camera_fps", 30)
                },

                "temperature_timeline": temperature_timeline,
                "raw_metadata": save_data["metadata"],
                "metadata_count": len(save_data["metadata"])
            }

            # Save to both directories
            for dir_path in [save_data["frying_session_dir"], save_data["bucket_session_dir"]]:
                info_path = os.path.join(dir_path, "session_info.json")
                with open(info_path, 'w', encoding='utf-8') as f:
                    json.dump(session_info, f, indent=2, ensure_ascii=False)

            print(f"[데이터수집] 종료: {save_data['frame_counter']}장 저장, {duration:.1f}초")
            print(f"[데이터수집] 음식 종류: {save_data['food_type']}")
            print(f"[데이터수집] 완료 마킹: {'예' if save_data['completion_marked'] else '아니오'}")
            print(f"[데이터수집] MQTT 메타데이터: {len(save_data['metadata'])}개 수집")

            # 메인 스레드에서 GUI 업데이트 및 메시지박스 표시
            completion_text = ""
            if save_data["completion_marked"]:
                elapsed = save_data["completion_info"].get("elapsed_time_sec", 0)
                method = save_data["completion_info"].get("method", "unknown")
                completion_text = f"\n완료 마킹: {method} ({elapsed:.1f}초)"

            msg = (
                f"세션: {save_data['session_id']}\n"
                f"음식: {save_data['food_type']}\n\n"
                f"총 저장: {save_data['frame_counter']}장\n"
                f"수집 시간: {duration:.1f}초{completion_text}\n"
                f"MQTT 메타데이터: {len(save_data['metadata'])}개\n\n"
                f"저장 경로:\n{os.path.expanduser('~/AI_Data/')}"
            )

            # 메인 스레드에서 실행
            self.root.after(0, lambda: self._on_collection_save_complete(msg))

        except Exception as e:
            print(f"[데이터수집] 저장 오류: {e}")
            self.root.after(0, lambda: self._on_collection_save_complete(f"저장 중 오류 발생: {e}"))

    def _on_collection_save_complete(self, msg):
        """저장 완료 후 GUI 업데이트 (메인 스레드에서 실행)"""
        self.collection_status_label.config(text="수집: 대기 중", fg=COLOR_TEXT)
        showinfo_topmost("데이터 수집 완료", msg)

    # POT1/POT2 Separate Collection Functions
    def start_pot1_collection(self):
        """Start POT1 data collection (cameras 0, 2, 3)"""
        from datetime import datetime
        import os

        # Create session ID
        self.pot1_session_id = datetime.now().strftime("session_%Y%m%d_%H%M%S")
        self.pot1_start_time = datetime.now()
        self.pot1_frame_counter = 0
        self.pot1_timer = 0

        # Create session directories - pot1/session_id/food_type/camera_X
        base_dir = os.path.expanduser("~/AI_Data/FryingData")
        self.pot1_session_dir = os.path.join(base_dir, "pot1", self.pot1_session_id, self.pot1_food_type)

        for cam_idx in [0, 2, 3]:
            os.makedirs(os.path.join(self.pot1_session_dir, f"camera_{cam_idx}"), mode=0o755, exist_ok=True)

        # Reset completion flags
        self.pot1_completion_marked = False
        self.pot1_completion_time = None
        self.pot1_completion_info = {}

        # Update flags
        self.pot1_collecting = True
        self.pot1_metadata = []  # Reset metadata

        print(f"[POT1 수집] 시작: {self.pot1_session_id}")
        print(f"[POT1 수집] 음식 종류: {self.pot1_food_type}")
        print(f"[POT1 수집] 저장 경로: {self.pot1_session_dir}")

    def stop_pot1_collection(self):
        """Stop POT1 data collection"""
        from datetime import datetime
        import json
        import os

        if not self.pot1_collecting:
            return

        self.pot1_collecting = False
        duration = (datetime.now() - self.pot1_start_time).total_seconds()

        # Save session info
        session_info = {
            "pot": "pot1",
            "session_id": self.pot1_session_id,
            "food_type": self.pot1_food_type,
            "start_time": self.pot1_start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "duration_sec": duration,
            "collection_interval": self.collection_interval,
            "completion_info": self.pot1_completion_info if self.pot1_completion_marked else None,
            "completion_marked": self.pot1_completion_marked,
            "cameras_used": [0, 2, 3],
            "total_frames_saved": self.pot1_frame_counter,
            "raw_metadata": self.pot1_metadata,
            "metadata_count": len(self.pot1_metadata)
        }

        # Save metadata
        info_path = os.path.join(self.pot1_session_dir, "session_info.json")
        with open(info_path, 'w', encoding='utf-8') as f:
            json.dump(session_info, f, indent=2, ensure_ascii=False)

        print(f"[POT1 수집] 종료: {self.pot1_frame_counter}장 저장, {duration:.1f}초")
        print(f"[POT1 수집] 음식 종류: {self.pot1_food_type}")

        # Reset session
        self.pot1_session_id = None
        self.pot1_start_time = None

    def start_pot2_collection(self):
        """Start POT2 data collection (cameras 1, 2, 3)"""
        from datetime import datetime
        import os

        # Create session ID
        self.pot2_session_id = datetime.now().strftime("session_%Y%m%d_%H%M%S")
        self.pot2_start_time = datetime.now()
        self.pot2_frame_counter = 0
        self.pot2_timer = 0

        # Create session directories - pot2/session_id/food_type/camera_X
        base_dir = os.path.expanduser("~/AI_Data/FryingData")
        self.pot2_session_dir = os.path.join(base_dir, "pot2", self.pot2_session_id, self.pot2_food_type)

        for cam_idx in [1, 2, 3]:
            os.makedirs(os.path.join(self.pot2_session_dir, f"camera_{cam_idx}"), mode=0o755, exist_ok=True)

        # Reset completion flags
        self.pot2_completion_marked = False
        self.pot2_completion_time = None
        self.pot2_completion_info = {}

        # Update flags
        self.pot2_collecting = True
        self.pot2_metadata = []  # Reset metadata

        print(f"[POT2 수집] 시작: {self.pot2_session_id}")
        print(f"[POT2 수집] 음식 종류: {self.pot2_food_type}")
        print(f"[POT2 수집] 저장 경로: {self.pot2_session_dir}")

    def stop_pot2_collection(self):
        """Stop POT2 data collection"""
        from datetime import datetime
        import json
        import os

        if not self.pot2_collecting:
            return

        self.pot2_collecting = False
        duration = (datetime.now() - self.pot2_start_time).total_seconds()

        # Save session info
        session_info = {
            "pot": "pot2",
            "session_id": self.pot2_session_id,
            "food_type": self.pot2_food_type,
            "start_time": self.pot2_start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "duration_sec": duration,
            "collection_interval": self.collection_interval,
            "completion_info": self.pot2_completion_info if self.pot2_completion_marked else None,
            "completion_marked": self.pot2_completion_marked,
            "cameras_used": [1, 2, 3],
            "total_frames_saved": self.pot2_frame_counter,
            "raw_metadata": self.pot2_metadata,
            "metadata_count": len(self.pot2_metadata)
        }

        # Save metadata
        info_path = os.path.join(self.pot2_session_dir, "session_info.json")
        with open(info_path, 'w', encoding='utf-8') as f:
            json.dump(session_info, f, indent=2, ensure_ascii=False)

        print(f"[POT2 수집] 종료: {self.pot2_frame_counter}장 저장, {duration:.1f}초")
        print(f"[POT2 수집] 음식 종류: {self.pot2_food_type}")

        # Reset session
        self.pot2_session_id = None
        self.pot2_start_time = None

    def _delayed_stop_pot1_collection(self):
        """배출 후 지연 종료 (타이머 콜백)"""
        self.pot1_discharge_timer_id = None
        if self.pot1_collecting:
            print(f"[로봇상태] POT1(왼쪽) 배출 후 {RECORDING_DELAY_AFTER_DISCHARGE}초 경과 - 수집 종료")
            self.stop_pot1_collection()

    def _delayed_stop_pot2_collection(self):
        """배출 후 지연 종료 (타이머 콜백)"""
        self.pot2_discharge_timer_id = None
        if self.pot2_collecting:
            print(f"[로봇상태] POT2(오른쪽) 배출 후 {RECORDING_DELAY_AFTER_DISCHARGE}초 경과 - 수집 종료")
            self.stop_pot2_collection()

    def save_pot1_data(self, frying_left, observe_left, observe_right):
        """Save POT1 frames (cameras 0, 2, 3) - 별도 프로세스에서 저장"""
        if not self.pot1_collecting:
            return

        from datetime import datetime

        timestamp = datetime.now().strftime("%H%M%S_%f")[:-3]  # HHMMss_mmm
        saver = get_image_saver(JPEG_QUALITY, SAVE_WIDTH, SAVE_HEIGHT)

        # Save POT1 cameras: camera_0 (frying left), camera_2 (observe left), camera_3 (observe right)
        for cam_idx, frame in [(0, frying_left), (2, observe_left), (3, observe_right)]:
            if frame is not None:
                save_path = os.path.join(self.pot1_session_dir, f"camera_{cam_idx}", f"camera_{cam_idx}_{timestamp}.jpg")
                saver.save(save_path, frame)
                self.pot1_frame_counter += 1

        if self.pot1_frame_counter % 10 == 0:
            print(f"[POT1 수집] {self.pot1_frame_counter}장 저장됨 (대기: {saver.get_queue_size()})")

    def save_pot2_data(self, frying_right, observe_left, observe_right):
        """Save POT2 frames (cameras 1, 2, 3) - 별도 프로세스에서 저장"""
        if not self.pot2_collecting:
            return

        from datetime import datetime

        timestamp = datetime.now().strftime("%H%M%S_%f")[:-3]  # HHMMss_mmm
        saver = get_image_saver(JPEG_QUALITY, SAVE_WIDTH, SAVE_HEIGHT)

        # Save POT2 cameras: camera_1 (frying right), camera_2 (observe left), camera_3 (observe right)
        for cam_idx, frame in [(1, frying_right), (2, observe_left), (3, observe_right)]:
            if frame is not None:
                save_path = os.path.join(self.pot2_session_dir, f"camera_{cam_idx}", f"camera_{cam_idx}_{timestamp}.jpg")
                saver.save(save_path, frame)
                self.pot2_frame_counter += 1

        if self.pot2_frame_counter % 10 == 0:
            print(f"[POT2 수집] {self.pot2_frame_counter}장 저장됨 (대기: {saver.get_queue_size()})")

    def save_collection_data(self, frying_left, frying_right, observe_left, observe_right):
        """Save frames from all 4 cameras during data collection (LEGACY) - 별도 프로세스에서 저장"""
        if not self.data_collection_active:
            return

        from datetime import datetime

        timestamp = datetime.now().strftime("%H%M%S_%f")[:-3]  # HHMMss_mmm
        saver = get_image_saver(JPEG_QUALITY, SAVE_WIDTH, SAVE_HEIGHT)

        # Save frying cameras (camera 0, 1)
        for cam_idx, frame in [(0, frying_left), (1, frying_right)]:
            if frame is not None:
                save_path = os.path.join(
                    self.frying_session_dir,
                    f"camera_{cam_idx}",
                    f"cam{cam_idx}_{timestamp}.jpg"
                )
                saver.save(save_path, frame)

        # Save bucket cameras (camera 2, 3)
        for cam_idx, frame in [(2, observe_left), (3, observe_right)]:
            if frame is not None:
                save_path = os.path.join(
                    self.bucket_session_dir,
                    f"camera_{cam_idx}",
                    f"cam{cam_idx}_{timestamp}.jpg"
                )
                saver.save(save_path, frame)

        self.collection_frame_counter += 1

        # Update status
        if self.collection_frame_counter % 10 == 0:
            self.collection_status_label.config(
                text=f"수집 중: {self.collection_frame_counter}장 저장됨"
            )
            print(f"[데이터수집] {self.collection_frame_counter}장 저장됨 (대기: {saver.get_queue_size()})")

    def toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        self.is_fullscreen = not self.is_fullscreen
        self.root.attributes('-fullscreen', self.is_fullscreen)

    def exit_fullscreen(self):
        """Exit fullscreen mode - 창 모드로 복원"""
        self.is_fullscreen = False
        self.root.attributes('-fullscreen', False)
        # 창 크기 복원
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+0+0")

    def on_close(self):
        """Cleanup and close application - 백그라운드에서 정리"""
        # 확인 팝업 없이 바로 종료
        print("[종료] 시스템 종료 중...")
        self.running = False

        # 백그라운드 스레드에서 정리 작업 수행 (UI 프리징 방지)
        def cleanup_and_exit():
            try:
                # Stop ongoing data collection to save session_info.json
                print("[종료] 데이터 수집 중지 및 메타데이터 저장 중...")
                if self.pot1_collecting:
                    self.stop_pot1_collection()
                if self.pot2_collecting:
                    self.stop_pot2_collection()
                if self.data_collection_active:
                    self.stop_data_collection()

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

                # Stop cameras with timeout
                print("[종료] 카메라 해제 중...")
                import threading

                def stop_camera_safe(cap, name):
                    try:
                        cap.stop()
                        print(f"[종료] {name} 해제 완료")
                    except Exception as e:
                        print(f"[종료] {name} 해제 오류: {e}")

                threads = []
                if self.frying_left_cap:
                    t = threading.Thread(target=stop_camera_safe, args=(self.frying_left_cap, "frying_left"))
                    t.daemon = True
                    t.start()
                    threads.append(t)
                if self.frying_right_cap:
                    t = threading.Thread(target=stop_camera_safe, args=(self.frying_right_cap, "frying_right"))
                    t.daemon = True
                    t.start()
                    threads.append(t)
                if self.observe_left_cap:
                    t = threading.Thread(target=stop_camera_safe, args=(self.observe_left_cap, "observe_left"))
                    t.daemon = True
                    t.start()
                    threads.append(t)
                if self.observe_right_cap:
                    t = threading.Thread(target=stop_camera_safe, args=(self.observe_right_cap, "observe_right"))
                    t.daemon = True
                    t.start()
                    threads.append(t)

                # Wait for all threads with timeout
                for t in threads:
                    t.join(timeout=2.0)

                print("[종료] 카메라 해제 완료")

                # Stop image saver process
                print("[종료] 이미지 저장 프로세스 종료 중...")
                stop_image_saver()
                print("[종료] 이미지 저장 프로세스 종료 완료")

                # Disconnect MQTT
                if self.mqtt_client:
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
    print("=" * 50)
    print("Jetson #2 - AI Monitoring System")
    print("=" * 50)

    root = tk.Tk()
    app = JetsonIntegratedApp(root)
    root.mainloop()
