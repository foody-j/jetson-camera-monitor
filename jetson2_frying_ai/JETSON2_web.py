#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jetson2 Web Refactored - Headless + FastAPI Dashboard
- Removes tkinter GUI
- Runs FastAPI web dashboard + MJPEG streams
- Keeps core AI logic (frying + observe) and MQTT status
"""

import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import base64
import traceback
from collections import deque
from datetime import datetime
from typing import Dict, Optional
import atexit
import errno
import fcntl

import cv2
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_LOCK_FD = None

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gst_camera import GstCamera
from frying_segmenter import FoodSegmenter
from lift_event_tracker import LiftEventTracker
from image_saver_mp import get_image_saver, stop_image_saver
from src.communication.mqtt_client import MQTTClient
from src.core.system_info import SystemInfo
from web.app import create_app

try:
    import torch
    from ultralytics import YOLO
    _YOLO_AVAILABLE = True
except Exception:
    _YOLO_AVAILABLE = False

try:
    import Jetson.GPIO as GPIO
    _GPIO_AVAILABLE = True
except Exception:
    GPIO = None
    _GPIO_AVAILABLE = False


def load_config(config_path: str = "config_jetson2_web.json") -> dict:
    config_full_path = os.path.join(SCRIPT_DIR, config_path)
    with open(config_full_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _path_exists(path: str) -> bool:
    if not path:
        return False
    if os.path.isabs(path):
        return os.path.exists(path)
    return os.path.exists(path) or os.path.exists(os.path.join(SCRIPT_DIR, path))


def _acquire_single_instance(lock_name: str) -> None:
    global _LOCK_FD
    lock_path = os.path.join("/tmp", lock_name)
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as e:
        if e.errno in (errno.EACCES, errno.EAGAIN):
            print(f"[Main] Already running (lock: {lock_path}). Exiting.")
            sys.exit(1)
        raise
    os.ftruncate(fd, 0)
    os.write(fd, str(os.getpid()).encode("utf-8"))
    os.fsync(fd)
    _LOCK_FD = fd

    def _release_lock():
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            os.close(fd)
        except Exception:
            pass

    atexit.register(_release_lock)


def get_ip_address() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "unknown"


def get_tailscale_ip() -> Optional[str]:
    try:
        result = subprocess.run(
            ["tailscale", "ip", "-4"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        ip = result.stdout.strip()
        return ip or None
    except Exception:
        return None


def run_quick_bring_up(config: dict) -> None:
    """Run vendor quick bring-up script with predefined inputs."""
    script_path = config.get("quick_bring_up_script")
    if not script_path:
        return
    if not os.path.isabs(script_path):
        script_path = os.path.join(SCRIPT_DIR, script_path)
    if not os.path.exists(script_path):
        print(f"[BringUp] Script not found: {script_path}")
        return

    cam_type = str(config.get("quick_bring_up_cam_type", 2))
    cam_count = int(config.get("quick_bring_up_cam_count", 4))
    port = str(config.get("quick_bring_up_port", 0))
    resolution = str(config.get("quick_bring_up_resolution", 1))
    use_sudo = bool(config.get("quick_bring_up_use_sudo", True))
    timeout_sec = float(config.get("quick_bring_up_timeout_sec", 120))

    lines = [cam_type] * cam_count + [port, resolution]
    input_text = "\n".join(lines) + "\n"

    try:
        print(f"[BringUp] Running: {script_path} (sudo={use_sudo})")
        cmd = [script_path]
        if use_sudo:
            cmd = ["sudo", "-n", script_path]
        result = subprocess.run(
            cmd,
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_sec,
        )
        if result.stdout:
            print(result.stdout.strip())
        if result.stderr:
            print(result.stderr.strip())
        if result.returncode != 0 and use_sudo:
            if "password" in (result.stderr or "").lower():
                print("[BringUp] sudo 비밀번호 필요: 'sudo -v' 실행 후 재시도하세요.")
    except Exception as e:
        print(f"[BringUp] Failed: {e}")


def run_gmsl_init_script(config: dict) -> bool:
    """Run init_gmsl_cameras.sh style script (Jetson1 방식)."""
    init_script = config.get("gmsl_init_script", "init_gmsl_cameras.sh")
    if not init_script:
        return True
    if not os.path.isabs(init_script):
        init_script = os.path.join(os.path.dirname(SCRIPT_DIR), init_script)
    if not os.path.exists(init_script):
        print(f"[GMSL] 초기화 스크립트 없음: {init_script}")
        return False

    print("[GMSL] 초기화 스크립트 실행 중...")
    try:
        result = subprocess.run(
            ["bash", init_script],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.stdout:
            print(result.stdout.strip())
        if result.stderr:
            print(result.stderr.strip())
        if result.returncode != 0:
            print(f"[GMSL] 초기화 실패 (exit={result.returncode})")
            return False
        print("[GMSL] 초기화 완료")
        return True
    except Exception as e:
        print(f"[GMSL] 초기화 오류: {e}")
        return False


class CameraWorker(threading.Thread):
    """Camera capture worker (latest frame only)."""

    def __init__(self, cam_id: int, cam_index: int, config: dict):
        super().__init__(daemon=True)
        self.cam_id = cam_id
        self.cam_index = cam_index
        self.config = config

        self.camera = GstCamera(
            cam_index,
            width=config.get("camera_width", 1920),
            height=config.get("camera_height", 1536),
            fps=config.get("camera_fps", 30),
        )

        self.frame_queue = deque(maxlen=1)
        self.latest_frame: Optional[np.ndarray] = None
        self.latest_frame_lock = threading.Lock()
        self.web_frame: Optional[bytes] = None
        self.web_frame_lock = threading.Lock()
        self.overlay_frame: Optional[bytes] = None
        self.overlay_lock = threading.Lock()
        self.overlay_enabled = bool(self.config.get("overlay_enabled", False))

        self.stats = {
            "fps": 0,
            "frame_count": 0,
            "last_frame_ts": 0,
            "drop_count": 0,
        }

        self.running = False
        self._last_web_update = 0.0
        self._recover_event = threading.Event()
        self._recover_lock = threading.Lock()
        self._recovering = False
        self._last_camera_frame_ts = 0.0
        self._last_stale_log_ts = 0.0

    def run(self):
        self.running = True

        if not self._start_camera():
            self.running = False
            return

        fps_calc_time = time.time()
        fps_frame_count = 0

        while self.running:
            if self._recover_event.is_set():
                self._recover_event.clear()
                self._recover_camera()
                fps_calc_time = time.time()
                fps_frame_count = 0
            now = time.time()
            stale_sec = float(self.config.get("camera_stale_log_sec", 5.0))
            cam_ts = getattr(self.camera, "last_frame_ts", 0.0) or 0.0
            if cam_ts > 0:
                if cam_ts > self._last_camera_frame_ts:
                    self._last_camera_frame_ts = cam_ts
                elif stale_sec > 0 and now - cam_ts >= stale_sec and now - self._last_stale_log_ts >= stale_sec:
                    print(f"[CAM{self.cam_id}] Frame stalled ({now - cam_ts:.1f}s since last new frame)")
                    self._last_stale_log_ts = now

            ret, frame = self.camera.read()
            if not ret or frame is None:
                time.sleep(0.01)
                continue

            if len(self.frame_queue) == self.frame_queue.maxlen:
                self.stats["drop_count"] += 1
            self.frame_queue.append(frame)
            with self.latest_frame_lock:
                self.latest_frame = frame.copy()

            self._update_web_frame(frame)

            fps_frame_count += 1
            if now - fps_calc_time >= 1.0:
                self.stats["fps"] = fps_frame_count
                fps_frame_count = 0
                fps_calc_time = now

            self.stats["frame_count"] += 1
            self.stats["last_frame_ts"] = now

        self.camera.stop()

    def _start_camera(self) -> bool:
        start_delay = float(self.config.get("camera_start_delay_sec", 0.0))
        if start_delay > 0:
            time.sleep(start_delay)

        retry_count = int(self.config.get("camera_retry_count", 3))
        retry_interval = float(self.config.get("camera_retry_interval_sec", 1.0))

        started = False
        for attempt in range(1, retry_count + 1):
            if self.camera.start():
                started = True
                break
            print(f"[CAM{self.cam_id}] Start failed (attempt {attempt}/{retry_count})")
            time.sleep(retry_interval)

        if not started:
            print(f"[CAM{self.cam_id}] Failed to start after {retry_count} attempts")
            return False
        return True

    def _recover_camera(self) -> None:
        with self._recover_lock:
            if self._recovering:
                return
            self._recovering = True
        try:
            print(f"[CAM{self.cam_id}] Recovering camera...")
            try:
                self.camera.stop()
            except Exception:
                pass

            self.frame_queue.clear()
            with self.latest_frame_lock:
                self.latest_frame = None
            with self.web_frame_lock:
                self.web_frame = None
            with self.overlay_lock:
                self.overlay_frame = None
            self.stats["fps"] = 0
            self.stats["last_frame_ts"] = 0

            self.camera = GstCamera(
                self.cam_index,
                width=self.config.get("camera_width", 1920),
                height=self.config.get("camera_height", 1536),
                fps=self.config.get("camera_fps", 30),
            )

            if not self._start_camera():
                print(f"[CAM{self.cam_id}] Recover failed (start error)")
            else:
                print(f"[CAM{self.cam_id}] Recover success")
        finally:
            with self._recover_lock:
                self._recovering = False

    def request_recover(self) -> None:
        self._recover_event.set()

    def is_recovering(self) -> bool:
        with self._recover_lock:
            return self._recovering

    def _update_web_frame(self, frame: np.ndarray) -> None:
        now = time.time()
        interval = 1.0 / max(self.config.get("web_preview_fps", 5), 1)
        if now - self._last_web_update < interval:
            return

        roi = None
        if self.cam_id == self.config.get("observe_left_camera_index", 2):
            roi = self.config.get("observe_roi_cam2")
        elif self.cam_id == self.config.get("observe_right_camera_index", 3):
            roi = self.config.get("observe_roi_cam3")
        frame_for_preview = _apply_roi(frame, roi)

        h, w = frame_for_preview.shape[:2]
        target_w = _safe_int(self.config.get("web_preview_width", 640), 640)
        target_h = int(h * target_w / max(w, 1))
        small = cv2.resize(frame_for_preview, (target_w, target_h))

        ret, jpg = cv2.imencode(
            ".jpg",
            small,
            [cv2.IMWRITE_JPEG_QUALITY, _safe_int(self.config.get("web_preview_quality", 70), 70)],
        )
        if ret:
            with self.web_frame_lock:
                self.web_frame = jpg.tobytes()
        self._last_web_update = now

    def get_frame_for_ai(self) -> Optional[np.ndarray]:
        try:
            return self.frame_queue.popleft()
        except IndexError:
            return None

    def get_web_frame(self) -> Optional[bytes]:
        with self.web_frame_lock:
            return self.web_frame

    def set_overlay_frame(self, jpg_bytes: bytes) -> None:
        with self.overlay_lock:
            self.overlay_frame = jpg_bytes

    def set_overlay_enabled(self, enabled: bool) -> None:
        self.overlay_enabled = enabled

    def get_stream_frame(self) -> Optional[bytes]:
        if self.overlay_enabled:
            with self.overlay_lock:
                if self.overlay_frame:
                    return self.overlay_frame
        return self.get_web_frame()

    def get_latest_frame(self) -> Optional[np.ndarray]:
        with self.latest_frame_lock:
            return None if self.latest_frame is None else self.latest_frame.copy()

    def stop(self) -> None:
        self.running = False


class FryingAIWorker(threading.Thread):
    """Frying AI inference worker."""

    def __init__(self, pot_id: int, camera_worker: CameraWorker, config: dict):
        super().__init__(daemon=True)
        self.pot_id = pot_id
        self.camera = camera_worker
        self.config = config

        device = "cuda" if _YOLO_AVAILABLE and torch.cuda.is_available() else "cpu"

        self.segmenter = FoodSegmenter(
            model_path=config.get("frying_seg_model", "frying_seg.pt"),
            imgsz=config.get("frying_seg_imgsz", 640),
            conf=config.get("frying_seg_conf", 0.2),
            mask_threshold=config.get("frying_seg_mask_thresh", 0.3),
            device=device,
        )
        pot_name = "POT1" if pot_id == 0 else "POT2"
        self.tracker = LiftEventTracker(pot_name, config)

        self.latest_result = {
            "pot_id": pot_id,
            "status": "IDLE",
            "lift_count": 0,
            "area_ratio": 0.0,
            "brown_ratio": 0.0,
            "golden_ratio": 0.0,
            "food_type": None,
            "running_time": 0,
            "completion_detected": False,
            "last_update": 0,
        }
        self.result_lock = threading.Lock()

        self.running = False
        self.enabled = True
        self._last_overlay_ts = 0.0
        self._last_log_ts = 0.0
        self._snapshot_lock = threading.Lock()
        self._last_frame = None
        self._last_mask = None
        self._last_metrics = {}

    def start_session(self, food_type: str, target_time: int) -> None:
        session_id = f"pot{self.pot_id}_{int(time.time())}"
        self.tracker.start_session(session_id=session_id, food_type=food_type, target_time=target_time)
        with self.result_lock:
            self.latest_result["status"] = "COOKING"
            self.latest_result["food_type"] = food_type

    def stop_session(self) -> None:
        self.tracker.stop_session()
        with self.result_lock:
            self.latest_result["status"] = "IDLE"
            self.latest_result["food_type"] = None
            self.latest_result["completion_detected"] = False

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled

    def run(self):
        self.running = True
        infer_interval = 1.0 / max(self.config.get("frying_infer_fps", 5), 1)
        last_infer = 0.0

        while self.running:
            if not self.enabled:
                time.sleep(0.05)
                continue
            now = time.time()
            if now - last_infer < infer_interval:
                time.sleep(0.005)
                continue

            frame = self.camera.get_frame_for_ai()
            if frame is None:
                time.sleep(0.01)
                continue

            try:
                seg_result = self.segmenter.segment(frame)
                tracker_result = self.tracker.process_frame(seg_result)
                log_interval = _safe_float(self.config.get("frying_log_interval_sec", 5), 5.0)
                if log_interval > 0 and now - self._last_log_ts >= log_interval:
                    print(
                        f"[Frying AI] pot{self.pot_id} "
                        f"area={seg_result.food_area_ratio:.3f} "
                        f"brown={seg_result.color_features.brown_ratio:.3f} "
                        f"golden={seg_result.color_features.golden_ratio:.3f} "
                        f"lift={tracker_result.get('lift_count', 0)}"
                    )
                    self._last_log_ts = now

                with self.result_lock:
                    self.latest_result.update(
                        {
                            "pot_id": self.pot_id,
                            "lift_count": tracker_result.get("lift_count", 0),
                            "area_ratio": float(seg_result.food_area_ratio),
                            "brown_ratio": float(seg_result.color_features.brown_ratio),
                            "golden_ratio": float(seg_result.color_features.golden_ratio),
                            "running_time": tracker_result.get("running_time", 0),
                            "completion_detected": tracker_result.get("completion_detected", False),
                            "last_update": now,
                        }
                    )
                last_infer = now
                self._update_overlay(frame, seg_result)
                self._update_snapshot(frame, seg_result)
            except Exception as e:
                print(f"[Frying AI] pot{self.pot_id} error: {e}")
                traceback.print_exc()

    def get_result(self) -> dict:
        with self.result_lock:
            return dict(self.latest_result)

    def stop(self) -> None:
        self.running = False

    def _update_overlay(self, frame: np.ndarray, seg_result) -> None:
        if not self.camera or not self.camera.overlay_enabled:
            return
        overlay_fps = _safe_float(self.config.get("overlay_fps", 1), 1.0)
        if overlay_fps <= 0:
            return
        now = time.time()
        if now - self._last_overlay_ts < 1.0 / overlay_fps:
            return

        mask = getattr(seg_result, "food_mask", None)
        if mask is None:
            return

        target_w = _safe_int(self.config.get("web_preview_width", 640), 640)
        h, w = frame.shape[:2]
        target_h = int(h * target_w / max(w, 1))
        if target_w <= 1 or target_h <= 1:
            return
        small = cv2.resize(frame, (target_w, target_h))
        if small is None or small.size == 0:
            return
        mask_small = cv2.resize(mask, (target_w, target_h), interpolation=cv2.INTER_NEAREST)
        if mask_small is None or mask_small.size == 0:
            return

        color = np.zeros_like(small)
        color[:, :, 1] = 255  # green
        alpha = 0.35
        mask_bool = mask_small > 0
        if not np.any(mask_bool):
            return
        overlay = small.copy()
        try:
            overlay[mask_bool] = cv2.addWeighted(small[mask_bool], 1 - alpha, color[mask_bool], alpha, 0)
        except Exception:
            return

        ret, jpg = cv2.imencode(
            ".jpg",
            overlay,
            [cv2.IMWRITE_JPEG_QUALITY, _safe_int(self.config.get("web_preview_quality", 70), 70)],
        )
        if ret:
            self.camera.set_overlay_frame(jpg.tobytes())
            self._last_overlay_ts = now

    def _update_snapshot(self, frame: np.ndarray, seg_result) -> None:
        try:
            metrics = {
                "area_ratio": float(seg_result.food_area_ratio),
                "brown_ratio": float(seg_result.color_features.brown_ratio),
                "golden_ratio": float(seg_result.color_features.golden_ratio),
                "mean_hsv": [float(x) for x in seg_result.color_features.mean_hsv],
                "std_hsv": [float(x) for x in seg_result.color_features.std_hsv],
                "mean_lab": [float(x) for x in seg_result.color_features.mean_lab],
            }
            mask = seg_result.food_mask.copy() if seg_result.food_mask is not None else None
            with self._snapshot_lock:
                self._last_frame = frame.copy()
                self._last_mask = mask
                self._last_metrics = metrics
        except Exception:
            pass

    def get_snapshot(self):
        with self._snapshot_lock:
            if self._last_frame is None:
                return None, None, {}
            frame = self._last_frame.copy()
            mask = None if self._last_mask is None else self._last_mask.copy()
            metrics = dict(self._last_metrics)
            return frame, mask, metrics


def _safe_int(value, default: int) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def _safe_float(value, default: float) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _clamp_int(value: float, lo: int, hi: int) -> int:
    return max(lo, min(int(value), hi))


def _square_crop(img: np.ndarray) -> np.ndarray:
    """Center-crop to square while preserving aspect ratio."""
    h, w = img.shape[:2]
    side = min(h, w)
    x1 = (w - side) // 2
    y1 = (h - side) // 2
    return img[y1:y1 + side, x1:x1 + side].copy()


def _apply_roi(frame: np.ndarray, roi) -> np.ndarray:
    if frame is None or roi is None:
        return frame
    try:
        x, y, w, h = roi
    except Exception:
        return frame
    if w <= 1 or h <= 1:
        return frame
    fh, fw = frame.shape[:2]
    x1 = max(0, min(int(x), fw - 1))
    y1 = max(0, min(int(y), fh - 1))
    x2 = max(0, min(int(x + w), fw))
    y2 = max(0, min(int(y + h), fh))
    if x2 <= x1 or y2 <= y1:
        return frame
    return frame[y1:y2, x1:x2].copy()


class ObserveAIWorker(threading.Thread):
    """Observe (bucket) AI inference worker."""

    def __init__(
        self,
        cam_id: int,
        camera_worker: CameraWorker,
        config: dict,
        seg_model_path: str,
        cls_model_path: str,
        event_logger=None,
    ):
        super().__init__(daemon=True)
        self.cam_id = cam_id
        self.camera = camera_worker
        self.config = config
        self.event_logger = event_logger

        self.seg_model_path = seg_model_path
        self.cls_model_path = cls_model_path
        if cam_id == config.get("observe_left_camera_index", 2):
            self.roi = config.get("observe_roi_cam2")
        elif cam_id == config.get("observe_right_camera_index", 3):
            self.roi = config.get("observe_roi_cam3")
        else:
            self.roi = None

        self.device = "cuda" if _YOLO_AVAILABLE and torch.cuda.is_available() else "cpu"

        self.seg_model = None
        self.cls_model = None
        if _YOLO_AVAILABLE:
            try:
                self.seg_model = YOLO(self._resolve_model_path(seg_model_path))
                if self.device == "cuda":
                    self.seg_model.to("cuda")
                print(f"[Observe AI] cam{self.cam_id} seg model loaded: {seg_model_path}")
            except Exception as e:
                print(f"[Observe AI] cam{self.cam_id} seg model load failed: {e}")

            try:
                self.cls_model = YOLO(self._resolve_model_path(cls_model_path))
                if self.device == "cuda":
                    self.cls_model.to("cuda")
                print(f"[Observe AI] cam{self.cam_id} cls model loaded: {cls_model_path}")
            except Exception as e:
                print(f"[Observe AI] cam{self.cam_id} cls model load failed: {e}")

        self.votes = deque(maxlen=int(config.get("vote_n", 7)))
        self.latest_result = {
            "cam_id": cam_id,
            "status": "DISABLED" if not self.seg_model or not self.cls_model else "UNKNOWN",
            "detected": False,
            "filled": False,
            "top1": None,
            "prob": 0.0,
            "last_update": 0,
        }
        self.result_lock = threading.Lock()
        self.running = False
        self.enabled = True
        self._last_overlay_ts = 0.0
        self._snapshot_lock = threading.Lock()
        self._last_frame = None
        self._last_mask = None
        self._last_metrics = {}
        self._last_status = None

    def _resolve_model_path(self, path: str) -> str:
        if os.path.isabs(path):
            return path
        return os.path.join(SCRIPT_DIR, path)

    def run(self):
        if not self.seg_model or not self.cls_model:
            return

        self.running = True
        infer_interval = 1.0 / max(self.config.get("observe_infer_fps", 2), 1)
        last_infer = 0.0

        while self.running:
            if not self.enabled:
                time.sleep(0.05)
                continue
            now = time.time()
            if now - last_infer < infer_interval:
                time.sleep(0.01)
                continue

            frame = self.camera.get_frame_for_ai()
            if frame is None:
                time.sleep(0.01)
                continue
            frame = _apply_roi(frame, self.roi)

            try:
                seg_imgsz = self.config.get("observe_img_size_seg", self.config.get("img_size_seg", 640))
                cls_imgsz = self.config.get("observe_img_size_cls", self.config.get("img_size_cls", 224))
                seg_conf = float(self.config.get("observe_conf_seg", self.config.get("conf_seg", 0.5)))
                inner_margin = float(self.config.get("observe_inner_margin", 0.15))
                bbox_pad = int(self.config.get("observe_bbox_pad", 10))
                filled_prob_min = float(self.config.get("observe_filled_prob_min", 0.0))
                min_vote_samples = int(self.config.get("observe_vote_min_samples", 1))

                seg_res = self.seg_model.predict(
                    frame,
                    imgsz=seg_imgsz,
                    conf=seg_conf,
                    verbose=False,
                    device=self.device,
                )[0]

                H, W = frame.shape[:2]
                in_mask = None

                detected = False
                is_filled = False
                top1_name = None
                prob = 0.0
                has_dets = False

                if seg_res.boxes is not None and len(seg_res.boxes) > 0:
                    has_dets = True
                    boxes_xyxy = seg_res.boxes.xyxy.cpu().numpy()
                    confs = seg_res.boxes.conf.cpu().numpy()
                    cls_ids = seg_res.boxes.cls.cpu().numpy().astype(int)
                    names = seg_res.names

                    def _is_in_class(name: str) -> bool:
                        name_lower = (name or "").lower()
                        return name_lower == "in" or "in" in name_lower

                    in_indices = [i for i in range(len(cls_ids)) if _is_in_class(names[int(cls_ids[i])])]
                    if in_indices:
                        # cam3(오른쪽 버킷 카메라)는 왼쪽 경계(x1)가 가장 오른쪽인 박스를 선택한다.
                        # 넓은 박스가 좌측을 많이 덮어도 우측 버킷을 더 안정적으로 고른다.
                        if self.cam_id == self.config.get("observe_right_camera_index", 3):
                            right_ratio = float(self.config.get("observe_cam3_right_min_ratio", 0.5))
                            right_ratio = max(0.0, min(1.0, right_ratio))
                            split_x = W * right_ratio
                            right_indices = [
                                i for i in in_indices if ((boxes_xyxy[i][0] + boxes_xyxy[i][2]) * 0.5) >= split_x
                            ]
                            # cam3는 우측 후보가 없으면 선택하지 않는다(좌측 오선택 방지).
                            if not right_indices:
                                in_indices = []
                            else:
                                best_in = max(right_indices, key=lambda i: boxes_xyxy[i][0])  # x1 max
                        else:
                            best_in = max(in_indices, key=lambda i: confs[i])
                        if in_indices:
                            x1, y1, x2, y2 = boxes_xyxy[best_in]

                            x1 = _clamp_int(x1 - bbox_pad, 0, W - 1)
                            y1 = _clamp_int(y1 - bbox_pad, 0, H - 1)
                            x2 = _clamp_int(x2 + bbox_pad, 0, W - 1)
                            y2 = _clamp_int(y2 + bbox_pad, 0, H - 1)

                            bw = x2 - x1
                            bh = y2 - y1
                            mx = int(bw * inner_margin)
                            my = int(bh * inner_margin)
                            ix1 = _clamp_int(x1 + mx, 0, W - 1)
                            iy1 = _clamp_int(y1 + my, 0, H - 1)
                            ix2 = _clamp_int(x2 - mx, 0, W - 1)
                            iy2 = _clamp_int(y2 - my, 0, H - 1)

                            if ix2 > ix1 and iy2 > iy1:
                                inner = frame[iy1:iy2, ix1:ix2].copy()
                                inner_sq = _square_crop(inner)
                                inner_sq = cv2.resize(inner_sq, (cls_imgsz, cls_imgsz), interpolation=cv2.INTER_AREA)
                                cls_res = self.cls_model.predict(
                                    inner_sq,
                                    imgsz=cls_imgsz,
                                    conf=0.0,
                                    verbose=False,
                                    device=self.device,
                                )[0]
                                top1_idx = int(cls_res.probs.top1)
                                top1_name = cls_res.names[top1_idx]
                                prob = float(cls_res.probs.top1conf)
                                is_filled = (
                                    top1_name.lower() == self.config.get("positive_label", "filled").lower()
                                    and prob >= filled_prob_min
                                )
                                detected = True

                                if seg_res.masks is not None and len(seg_res.masks.data) > best_in:
                                    m = seg_res.masks.data[best_in].cpu().numpy().astype(np.uint8)
                                    if m.max() <= 1:
                                        m = m * 255
                                    in_mask = cv2.resize(m, (W, H), interpolation=cv2.INTER_NEAREST)

                status = "NO_BASKET"
                filled_stable = False
                if detected:
                    self.votes.append(is_filled)
                    filled_stable = (
                        len(self.votes) >= max(1, min_vote_samples)
                        and sum(self.votes) >= (len(self.votes) // 2 + 1)
                    )
                    status = "FILLED" if filled_stable else "EMPTY"
                else:
                    self.votes.clear()
                    if has_dets:
                        status = "NO_IN"

                with self.result_lock:
                    self.latest_result.update(
                        {
                            "status": status,
                            "detected": detected,
                            "filled": filled_stable,
                            "top1": top1_name,
                            "prob": prob,
                            "last_update": now,
                        }
                    )
                if status != self._last_status:
                    if top1_name is None:
                        print(f"[Observe AI] cam{self.cam_id} status -> {status}")
                    else:
                        print(f"[Observe AI] cam{self.cam_id} status -> {status} (top1={top1_name}, prob={prob:.2f})")
                    if self.event_logger:
                        self.event_logger(
                            "observe_status_change",
                            cam_id=self.cam_id,
                            status=status,
                            previous_status=self._last_status,
                            detected=detected,
                            filled=filled_stable,
                            top1=top1_name,
                            prob=round(prob, 4),
                            has_dets=has_dets,
                            expected_status=None,
                            is_correct=None,
                        )
                    self._last_status = status
                last_infer = now
                self._update_overlay(frame, in_mask)
                self._update_snapshot(frame, in_mask, status, prob, top1_name)
            except Exception as e:
                print(f"[Observe AI] cam{self.cam_id} error: {e}")
                if self.event_logger:
                    self.event_logger("observe_error", cam_id=self.cam_id, error=str(e))

    def get_result(self) -> dict:
        with self.result_lock:
            return dict(self.latest_result)

    def stop(self) -> None:
        self.running = False

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled

    def _update_overlay(self, frame: np.ndarray, basket_mask: np.ndarray) -> None:
        if not self.camera or not self.camera.overlay_enabled:
            return
        overlay_fps = _safe_float(self.config.get("overlay_fps", 1), 1.0)
        if overlay_fps <= 0:
            return
        now = time.time()
        if now - self._last_overlay_ts < 1.0 / overlay_fps:
            return

        if basket_mask is None or not basket_mask.any():
            return

        target_w = _safe_int(self.config.get("web_preview_width", 640), 640)
        h, w = frame.shape[:2]
        target_h = int(h * target_w / max(w, 1))
        if target_w <= 1 or target_h <= 1:
            return
        small = cv2.resize(frame, (target_w, target_h))
        if small is None or small.size == 0:
            return
        mask_small = cv2.resize(basket_mask, (target_w, target_h), interpolation=cv2.INTER_NEAREST)
        if mask_small is None or mask_small.size == 0:
            return

        color = np.zeros_like(small)
        color[:, :, 1] = 255
        alpha = 0.35
        mask_bool = mask_small > 0
        if not np.any(mask_bool):
            return
        overlay = small.copy()
        try:
            overlay[mask_bool] = cv2.addWeighted(small[mask_bool], 1 - alpha, color[mask_bool], alpha, 0)
        except Exception:
            return

        ret, jpg = cv2.imencode(
            ".jpg",
            overlay,
            [cv2.IMWRITE_JPEG_QUALITY, _safe_int(self.config.get("web_preview_quality", 70), 70)],
        )
        if ret:
            self.camera.set_overlay_frame(jpg.tobytes())
            self._last_overlay_ts = now

    def _update_snapshot(self, frame, mask, status, prob, top1_name) -> None:
        try:
            metrics = {
                "status": status,
                "top1": top1_name,
                "prob": float(prob),
            }
            with self._snapshot_lock:
                self._last_frame = frame.copy()
                self._last_mask = mask.copy() if mask is not None else None
                self._last_metrics = metrics
        except Exception:
            pass

    def get_snapshot(self):
        with self._snapshot_lock:
            if self._last_frame is None:
                return None, None, {}
            frame = self._last_frame.copy()
            mask = None if self._last_mask is None else self._last_mask.copy()
            metrics = dict(self._last_metrics)
            return frame, mask, metrics


class Jetson2Web:
    """Main controller for headless + web dashboard."""

    def __init__(self, config: dict):
        self.config = config
        self.running = False

        self.debug_print = bool(config.get("debug_print_enabled", False))
        self.ai_mode_enabled = bool(config.get("ai_mode_enabled", False))

        self.cameras: Dict[int, Optional[CameraWorker]] = {}
        self._init_cameras()

        self.frying_workers: Dict[int, FryingAIWorker] = {}
        self.observe_workers: Dict[int, ObserveAIWorker] = {}
        self._init_ai_workers()
        self.lift_tracker_pot1 = LiftEventTracker("POT1", config)
        self.lift_tracker_pot2 = LiftEventTracker("POT2", config)

        self.mqtt_client: Optional[MQTTClient] = None
        self._init_mqtt()

        self.system_info = SystemInfo(
            device_name=config.get("device_name", "Jetson2_Web"),
            location=config.get("device_location", "unknown"),
        )

        self.web_thread: Optional[threading.Thread] = None
        self.collection_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.camera_watchdog_thread: Optional[threading.Thread] = None
        self.camera_watchdog_stop = threading.Event()
        self.camera_watchdog_start_ts = time.time()
        self.camera_fail_counts = {}

        self.pot1_food_type = None
        self.pot2_food_type = None
        self.pot1_target_time = None
        self.pot2_target_time = None
        self.pot1_status = "IDLE"
        self.pot2_status = "IDLE"
        self.frying_running = False
        self.observe_running = False
        self.observe_left_state = None
        self.observe_right_state = None
        self.observe_left_effective = None   # 투입 판정 포함한 발행 상태
        self.observe_right_effective = None
        self.vibration_status = "IDLE"
        self.last_vibration_event = {"event": "INIT", "status": "IDLE", "timestamp": None}
        self.vibration_abnormal_hold_sec = float(config.get("vibration_abnormal_hold_sec", 5.0))
        self.vibration_abnormal_timer = None
        self._last_chk_vibration = False
        self._last_vibration_request = False

        self.relay_enabled = False
        self.relay_mode = config.get("relay_mode", "pulse")
        self.auto_relay_enabled = bool(config.get("auto_relay_enabled", False))

        self.vibration_process = None
        self.child_processes = []

        self.data_collection_active = False
        self.current_food_type = "unknown"
        self.collection_session_id = None
        self.collection_start_time = None
        self.collection_frame_counter = 0
        self.collection_metadata = []
        self.collection_completion_marked = False
        self.collection_completion_time = None
        self.collection_completion_info = {}
        self.collection_timer = 0.0
        self.collection_interval = float(config.get("data_collection_interval_normal", 1))
        self.collection_last_ts = 0.0
        self.frying_session_dir = None
        self.bucket_session_dir = None

        self.pot1_collecting = False
        self.pot2_collecting = False
        self.pot1_session_id = None
        self.pot2_session_id = None
        self.pot1_start_time = None
        self.pot2_start_time = None
        self.pot1_frame_counter = 0
        self.pot2_frame_counter = 0
        self.pot1_timer = 0.0
        self.pot2_timer = 0.0
        self.pot1_last_collection_ts = 0.0
        self.pot2_last_collection_ts = 0.0
        self.pot1_metadata = []
        self.pot2_metadata = []
        self.pot1_completion_marked = False
        self.pot2_completion_marked = False
        self.pot1_completion_time = None
        self.pot2_completion_time = None
        self.pot1_completion_info = {}
        self.pot2_completion_info = {}
        self.pot1_discharge_timer = None
        self.pot2_discharge_timer = None
        self.pot1_discharge_idle_timer = None
        self.pot2_discharge_idle_timer = None
        self.pot1_timeout_timer = None
        self.pot2_timeout_timer = None
        self.pot1_timeout_seconds = int(config.get("pot1_timeout_seconds", 5))
        self.pot2_timeout_seconds = int(config.get("pot2_timeout_seconds", 5))
        self.pot1_taltal_pending = False
        self.pot2_taltal_pending = False
        self.pot1_taltal_timer = None
        self.pot2_taltal_timer = None
        self.pot1_robot_status = {}
        self.pot2_robot_status = {}
        self.pot1_session_dir = None
        self.pot2_session_dir = None

        self.recording_delay_after_discharge = float(
            config.get("recording_delay_after_discharge", 50)
        )
        self.discharge_to_idle_delay_sec = float(
            config.get("discharge_to_idle_delay_sec", 60)
        )
        self.data_collection_interval_normal = float(
            config.get("data_collection_interval_normal", 1)
        )
        self.data_collection_interval_fast = float(
            config.get("data_collection_interval_fast", 0.5)
        )
        self.save_resolution = config.get("save_resolution", {"width": 1920, "height": 1536})
        self.jpeg_quality = int(config.get("jpeg_quality", 100))
        self.target_probe_temp = float(config.get("target_probe_temp", 75.0))
        self.food_types = config.get("food_types", [])
        self.vibration_test_mode = bool(config.get("vibration_test_mode", False))
        self.dynamic_camera_enabled = bool(config.get("dynamic_camera_enabled", False))
        self.overlay_enabled = bool(config.get("overlay_enabled", False))
        self.temps = {
            "pot1_oil": None,
            "pot1_probe": None,
            "pot2_oil": None,
            "pot2_probe": None,
        }
        self.robot_status = {}

        self.mqtt_message_log = deque(maxlen=int(config.get("mqtt_log_maxlen", 200)))
        self.mqtt_log_dir = os.path.join(SCRIPT_DIR, "mqtt_logs")
        self.ops_log_dir = os.path.join(SCRIPT_DIR, "ops_logs")
        self.relay_log_dir = os.path.join(SCRIPT_DIR, "relay_logs")
        self._ops_log_lock = threading.Lock()
        self._relay_log_lock = threading.Lock()

    def _init_cameras(self) -> None:
        cam_width = self.config.get("camera_width", 1920)
        cam_height = self.config.get("camera_height", 1536)
        cam_fps = self.config.get("camera_fps", 30)

        if self.config.get("frying_left_enabled", True):
            idx = self.config.get("frying_left_camera_index", 0)
            self.cameras[0] = CameraWorker(0, idx, self.config)
        else:
            self.cameras[0] = None

        if self.config.get("frying_right_enabled", True):
            idx = self.config.get("frying_right_camera_index", 1)
            self.cameras[1] = CameraWorker(1, idx, self.config)
        else:
            self.cameras[1] = None

        if self.config.get("observe_left_enabled", True):
            idx = self.config.get("observe_left_camera_index", 2)
            self.cameras[2] = CameraWorker(2, idx, self.config)
        else:
            self.cameras[2] = None

        if self.config.get("observe_right_enabled", True):
            idx = self.config.get("observe_right_camera_index", 3)
            self.cameras[3] = CameraWorker(3, idx, self.config)
        else:
            self.cameras[3] = None

        if self.debug_print:
            print(f"[Cameras] width={cam_width}, height={cam_height}, fps={cam_fps}")

    def _init_ai_workers(self) -> None:
        if self.config.get("frying_enabled", True):
            if self.cameras.get(0) is not None:
                self.frying_workers[0] = FryingAIWorker(0, self.cameras[0], self.config)
            if self.cameras.get(1) is not None:
                self.frying_workers[1] = FryingAIWorker(1, self.cameras[1], self.config)

        if self.config.get("observe_enabled", True):
            left_seg = self.config.get("observe_left_seg_model", "")
            right_seg = self.config.get("observe_right_seg_model", "") or left_seg
            left_cls = self.config.get("observe_left_cls_model", "")
            right_cls = self.config.get("observe_right_cls_model", "") or left_cls

            if self.cameras.get(2) is not None and left_seg and left_cls and _path_exists(left_seg) and _path_exists(left_cls):
                self.observe_workers[2] = ObserveAIWorker(
                    2,
                    self.cameras[2],
                    self.config,
                    left_seg,
                    left_cls,
                    event_logger=self._log_ops_event,
                )
            if self.cameras.get(3) is not None and right_seg and right_cls and _path_exists(right_seg) and _path_exists(right_cls):
                self.observe_workers[3] = ObserveAIWorker(
                    3,
                    self.cameras[3],
                    self.config,
                    right_seg,
                    right_cls,
                    event_logger=self._log_ops_event,
                )

    def _init_mqtt(self) -> None:
        if not self.config.get("mqtt_enabled", False):
            return

        self.mqtt_client = MQTTClient(
            broker=self.config.get("mqtt_broker", "localhost"),
            port=self.config.get("mqtt_port", 1883),
            client_id=self.config.get("mqtt_client_id", "jetson2_web"),
        )

        self.mqtt_client.connect(blocking=True, timeout=5.0)

        qos = self.config.get("mqtt_qos", 1)
        self.mqtt_client.subscribe(self.config.get("mqtt_topic_robot_status", "HR/Status"), self.on_robot_status, qos=qos)
        self.mqtt_client.subscribe(self.config.get("mqtt_topic_pot1_oil_temp", "frying/pot1/oil_temp"), self.on_pot1_oil_temp, qos=qos)
        self.mqtt_client.subscribe(self.config.get("mqtt_topic_pot1_probe_temp", "frying/pot1/probe_temp"), self.on_pot1_probe_temp, qos=qos)
        self.mqtt_client.subscribe(self.config.get("mqtt_topic_pot2_oil_temp", "frying/pot2/oil_temp"), self.on_pot2_oil_temp, qos=qos)
        self.mqtt_client.subscribe(self.config.get("mqtt_topic_pot2_probe_temp", "frying/pot2/probe_temp"), self.on_pot2_probe_temp, qos=qos)
        self.mqtt_client.subscribe(self.config.get("mqtt_topic_frying_pot1_food_type", "frying/pot1/food_type"), self.on_pot1_food_type, qos=qos)
        self.mqtt_client.subscribe(self.config.get("mqtt_topic_frying_pot1_control", "frying/pot1/control"), self.on_pot1_control, qos=qos)
        self.mqtt_client.subscribe(self.config.get("mqtt_topic_frying_pot2_food_type", "frying/pot2/food_type"), self.on_pot2_food_type, qos=qos)
        self.mqtt_client.subscribe(self.config.get("mqtt_topic_frying_pot2_control", "frying/pot2/control"), self.on_pot2_control, qos=qos)
        self.mqtt_client.subscribe(self.config.get("mqtt_topic_vibration_control", "calibration/vibration/control"), self.on_vibration_control, qos=qos)
        jetson1_relay_topic = self.config.get("mqtt_topic_jetson1_relay", "jetson1/relay/status")
        if jetson1_relay_topic:
            self.mqtt_client.subscribe(jetson1_relay_topic, self.on_jetson1_relay_status, qos=qos)

    def init_gpio(self) -> None:
        if not _GPIO_AVAILABLE:
            print("[GPIO] Jetson.GPIO not available")
            return
        try:
            GPIO.setmode(GPIO.BOARD)
            GPIO.setup(29, GPIO.OUT, initial=GPIO.LOW)
            GPIO.setup(31, GPIO.OUT, initial=GPIO.LOW)
            print("[GPIO] Pin 29, 31 initialized for Relay control (OFF)")
            print(f"[GPIO] Relay mode: {self.relay_mode}")
        except Exception as e:
            print(f"[GPIO] 초기화 실패: {e}")

    def relay_turn_on(self) -> None:
        if not _GPIO_AVAILABLE:
            self._log_ops_event("relay_on_skipped", reason="gpio_unavailable")
            return
        if self.relay_enabled:
            self._log_ops_event("relay_on_skipped", reason="already_on")
            return
        try:
            if self.relay_mode == "pulse":
                GPIO.output(31, GPIO.HIGH)
                time.sleep(0.2)
                GPIO.output(31, GPIO.LOW)
                print("[GPIO] Relay ON (pulse)")
            else:
                GPIO.output(31, GPIO.HIGH)
                print("[GPIO] Relay ON (continuous)")
            self.relay_enabled = True
            self._log_ops_event("relay_on", mode=self.relay_mode)
            self._log_relay_event("ON", mode=self.relay_mode)
        except Exception as e:
            print(f"[GPIO] Relay ON 실패: {e}")
            self._log_ops_event("relay_on_error", error=str(e))
            self._log_relay_event("ON_ERROR", error=str(e))

    def relay_turn_off(self, force: bool = False) -> None:
        if not _GPIO_AVAILABLE:
            self._log_ops_event("relay_off_skipped", reason="gpio_unavailable")
            return
        if not self.relay_enabled and not force:
            self._log_ops_event("relay_off_skipped", reason="already_off", force=force)
            return
        try:
            if self.relay_mode == "pulse":
                GPIO.output(29, GPIO.HIGH)
                time.sleep(0.2)
                GPIO.output(29, GPIO.LOW)
                print("[GPIO] Relay OFF (pulse)")
            else:
                GPIO.output(29, GPIO.LOW)
                print("[GPIO] Relay OFF (continuous)")
            self.relay_enabled = False
            self._log_ops_event("relay_off", mode=self.relay_mode, force=force)
            self._log_relay_event("OFF", mode=self.relay_mode, force=force)
        except Exception as e:
            print(f"[GPIO] Relay OFF 실패: {e}")
            self._log_ops_event("relay_off_error", error=str(e), force=force)
            self._log_relay_event("OFF_ERROR", error=str(e), force=force)

    def on_pot1_food_type(self, client, userdata, message):
        self._log_mqtt_message(message.topic, message.payload)
        food_type = message.payload.decode().strip()
        self.pot1_food_type = food_type
        self.pot1_status = "COOKING"
        self._cancel_discharge_idle_timer(1)
        if not self.frying_running:
            self._set_frying_enabled(True)
        if not self.observe_running:
            self._set_observe_enabled(True)

        if self.pot1_timeout_timer:
            try:
                self.pot1_timeout_timer.cancel()
            except Exception:
                pass
            self.pot1_timeout_timer = None

        if not self.pot1_collecting:
            self.start_pot1_collection()
        else:
            self.pot1_metadata.append(
                {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "type": "food_type_change",
                    "value": self.pot1_food_type,
                }
            )

        target_time = self._get_target_time(self.pot1_target_time)
        worker = self.frying_workers.get(0)
        if worker:
            worker.start_session(food_type, target_time)

        self.pot1_timeout_timer = threading.Timer(self.pot1_timeout_seconds, self.on_pot1_timeout)
        self.pot1_timeout_timer.start()
        if self.debug_print:
            print(f"[MQTT] POT1 food_type={food_type}, target={target_time}")

    def on_pot2_food_type(self, client, userdata, message):
        self._log_mqtt_message(message.topic, message.payload)
        food_type = message.payload.decode().strip()
        self.pot2_food_type = food_type
        self.pot2_status = "COOKING"
        self._cancel_discharge_idle_timer(2)
        if not self.frying_running:
            self._set_frying_enabled(True)
        if not self.observe_running:
            self._set_observe_enabled(True)

        if self.pot2_timeout_timer:
            try:
                self.pot2_timeout_timer.cancel()
            except Exception:
                pass
            self.pot2_timeout_timer = None

        if not self.pot2_collecting:
            self.start_pot2_collection()
        else:
            self.pot2_metadata.append(
                {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "type": "food_type_change",
                    "value": self.pot2_food_type,
                }
            )

        target_time = self._get_target_time(self.pot2_target_time)
        worker = self.frying_workers.get(1)
        if worker:
            worker.start_session(food_type, target_time)

        self.pot2_timeout_timer = threading.Timer(self.pot2_timeout_seconds, self.on_pot2_timeout)
        self.pot2_timeout_timer.start()
        if self.debug_print:
            print(f"[MQTT] POT2 food_type={food_type}, target={target_time}")

    def on_pot1_control(self, client, userdata, message):
        self._log_mqtt_message(message.topic, message.payload)
        command = message.payload.decode().strip().lower()
        if command == "stop":
            if self.pot1_timeout_timer:
                try:
                    self.pot1_timeout_timer.cancel()
                except Exception:
                    pass
                self.pot1_timeout_timer = None
            self.pot1_status = "IDLE"
            self._cancel_discharge_idle_timer(1)
            if self.pot1_collecting:
                self.stop_pot1_collection()
            worker = self.frying_workers.get(0)
            if worker:
                worker.stop_session()

    def on_pot2_control(self, client, userdata, message):
        self._log_mqtt_message(message.topic, message.payload)
        command = message.payload.decode().strip().lower()
        if command == "stop":
            if self.pot2_timeout_timer:
                try:
                    self.pot2_timeout_timer.cancel()
                except Exception:
                    pass
                self.pot2_timeout_timer = None
            self.pot2_status = "IDLE"
            self._cancel_discharge_idle_timer(2)
            if self.pot2_collecting:
                self.stop_pot2_collection()
            worker = self.frying_workers.get(1)
            if worker:
                worker.stop_session()

    def on_pot1_oil_temp(self, client, userdata, message):
        self._log_mqtt_message(message.topic, message.payload)
        try:
            self.temps["pot1_oil"] = float(message.payload.decode())
        except Exception:
            return
        if self.pot1_collecting:
            self.pot1_metadata.append(
                {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "type": "oil_temperature",
                    "pot": "pot1",
                    "value": self.temps["pot1_oil"],
                    "unit": "celsius",
                }
            )
        if self.data_collection_active:
            self.collection_metadata.append(
                {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "type": "oil_temperature",
                    "position": "left",
                    "value": self.temps["pot1_oil"],
                    "unit": "celsius",
                }
            )

    def on_pot1_probe_temp(self, client, userdata, message):
        self._log_mqtt_message(message.topic, message.payload)
        try:
            self.temps["pot1_probe"] = float(message.payload.decode())
        except Exception:
            return
        if self.pot1_collecting:
            self.pot1_metadata.append(
                {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "type": "probe_temperature",
                    "pot": "pot1",
                    "value": self.temps["pot1_probe"],
                    "unit": "celsius",
                }
            )
            if not self.pot1_completion_marked and self.temps["pot1_probe"] >= self.target_probe_temp:
                self.pot1_completion_marked = True
                self.pot1_completion_time = datetime.now()
                self.pot1_completion_info = {
                    "method": f"auto (probe_temp >= {self.target_probe_temp}°C)",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "probe_temp": self.temps["pot1_probe"],
                    "oil_temp": self.temps["pot1_oil"],
                    "elapsed_time_sec": (datetime.now() - self.pot1_start_time).total_seconds()
                    if self.pot1_start_time
                    else 0,
                }
        if self.data_collection_active:
            self.collection_metadata.append(
                {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "type": "probe_temperature",
                    "position": "left",
                    "value": self.temps["pot1_probe"],
                    "unit": "celsius",
                }
            )
            if not self.collection_completion_marked and self.temps["pot1_probe"] >= self.target_probe_temp:
                self.mark_completion_auto("left", self.temps["pot1_probe"])

    def on_pot2_oil_temp(self, client, userdata, message):
        self._log_mqtt_message(message.topic, message.payload)
        try:
            self.temps["pot2_oil"] = float(message.payload.decode())
        except Exception:
            return
        if self.pot2_collecting:
            self.pot2_metadata.append(
                {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "type": "oil_temperature",
                    "pot": "pot2",
                    "value": self.temps["pot2_oil"],
                    "unit": "celsius",
                }
            )
        if self.data_collection_active:
            self.collection_metadata.append(
                {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "type": "oil_temperature",
                    "position": "right",
                    "value": self.temps["pot2_oil"],
                    "unit": "celsius",
                }
            )

    def on_pot2_probe_temp(self, client, userdata, message):
        self._log_mqtt_message(message.topic, message.payload)
        try:
            self.temps["pot2_probe"] = float(message.payload.decode())
        except Exception:
            return
        if self.pot2_collecting:
            self.pot2_metadata.append(
                {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "type": "probe_temperature",
                    "pot": "pot2",
                    "value": self.temps["pot2_probe"],
                    "unit": "celsius",
                }
            )
            if not self.pot2_completion_marked and self.temps["pot2_probe"] >= self.target_probe_temp:
                self.pot2_completion_marked = True
                self.pot2_completion_time = datetime.now()
                self.pot2_completion_info = {
                    "method": f"auto (probe_temp >= {self.target_probe_temp}°C)",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "probe_temp": self.temps["pot2_probe"],
                    "oil_temp": self.temps["pot2_oil"],
                    "elapsed_time_sec": (datetime.now() - self.pot2_start_time).total_seconds()
                    if self.pot2_start_time
                    else 0,
                }
        if self.data_collection_active:
            self.collection_metadata.append(
                {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "type": "probe_temperature",
                    "position": "right",
                    "value": self.temps["pot2_probe"],
                    "unit": "celsius",
                }
            )
            if not self.collection_completion_marked and self.temps["pot2_probe"] >= self.target_probe_temp:
                self.mark_completion_auto("right", self.temps["pot2_probe"])

    def on_robot_status(self, client, userdata, message):
        self._log_mqtt_message(message.topic, message.payload)
        try:
            payload = message.payload.decode()
            data = json.loads(payload)
        except Exception:
            return

        status_list = data.get("Status", [])
        vibration_request = data.get("VibrationRequest", False)
        chk_vibration = False
        seen_device = False
        for pot_data in status_list:
            if str(pot_data.get("DeviceNum", "")) != "0":
                continue
            seen_device = True
            chk_val = pot_data.get("ChkVibration", False)
            if isinstance(chk_val, str):
                chk_val = chk_val.strip().lower() == "true"
            if chk_val:
                chk_vibration = True
                break

        chk_rising = seen_device and chk_vibration and not self._last_chk_vibration
        req_rising = bool(vibration_request) and not self._last_vibration_request

        if seen_device and chk_vibration != self._last_chk_vibration:
            if chk_vibration:
                print("[로봇상태] ChkVibration=True 감지")
            else:
                print("[로봇상태] ChkVibration=False 감지")
        self._last_chk_vibration = chk_vibration if seen_device else self._last_chk_vibration
        self._last_vibration_request = bool(vibration_request)

        if chk_rising:
            if self.vibration_test_mode:
                self._set_vibration_status("NORMAL", "TEST_MODE_NORMAL")
            else:
                self.start_vibration_check()
        elif req_rising:
            if self.vibration_test_mode:
                self._set_vibration_status("NORMAL", "TEST_MODE_NORMAL")
            else:
                self.start_vibration_check()

        if not status_list:
            return

        rb_motion = data.get("RBMotion", None)
        if rb_motion in [1, 2]:
            if self.collection_interval != self.data_collection_interval_fast:
                self.collection_interval = self.data_collection_interval_fast
        else:
            if self.collection_interval != self.data_collection_interval_normal:
                self.collection_interval = self.data_collection_interval_normal

        for pot_data in status_list:
            if str(pot_data.get("DeviceNum", "")) != "0":
                continue

            pot_num = str(pot_data.get("PTNum", ""))
            recipe = pot_data.get("NowRecipe", "")
            process_type = pot_data.get("ProcessType", "")
            rb_status = pot_data.get("RBstatus", "")
            running_time = pot_data.get("RunningTime", "")
            target_time = pot_data.get("TargetTime", "")
            mode = pot_data.get("Mode", "")

            pot_status = pot_data.get("Potstatus", {})
            temp = pot_status.get("PT_Temp", 0)
            power = pot_status.get("PT_Power", "False")
            pt_level = pot_status.get("PT_Level", 0)
            rt_speed = pot_status.get("RT_Speed", 0)
            rt_dir = pot_status.get("RT_Dir", 0)

            robot_meta = {
                "rb_motion": rb_motion,
                "recipe": recipe,
                "process_type": process_type,
                "running_time": running_time,
                "target_time": target_time,
                "mode": mode,
                "pot_temp": temp,
                "pot_level": pt_level,
                "pot_power": power,
                "rt_speed": rt_speed,
                "rt_dir": rt_dir,
                "rb_status": rb_status,
            }

            is_cleaning = "청소" in recipe if recipe else False

            if pot_num == "0":
                self.robot_status["pot1"] = pot_data
                self.pot1_target_time = target_time
                self.pot1_robot_status = robot_meta
                if process_type in ["투입", "조리"] and not is_cleaning:
                    if self.pot1_discharge_timer:
                        try:
                            self.pot1_discharge_timer.cancel()
                        except Exception:
                            pass
                        self.pot1_discharge_timer = None
                    if not self.pot1_collecting:
                        self.pot1_food_type = recipe if recipe else "unknown"
                        self.start_pot1_collection()
                elif is_cleaning:
                    pass
                elif process_type == "배출":
                    self._set_discharge_with_idle_timer(1, reason="robot_process_discharge")
                    if self.pot1_collecting and not self.pot1_discharge_timer:
                        self.pot1_discharge_timer = threading.Timer(
                            self.recording_delay_after_discharge,
                            self._delayed_stop_pot1_collection,
                        )
                        self.pot1_discharge_timer.start()

            elif pot_num == "1":
                self.robot_status["pot2"] = pot_data
                self.pot2_target_time = target_time
                self.pot2_robot_status = robot_meta
                if process_type in ["투입", "조리"] and not is_cleaning:
                    if self.pot2_discharge_timer:
                        try:
                            self.pot2_discharge_timer.cancel()
                        except Exception:
                            pass
                        self.pot2_discharge_timer = None
                    if not self.pot2_collecting:
                        self.pot2_food_type = recipe if recipe else "unknown"
                        self.start_pot2_collection()
                elif is_cleaning:
                    pass
                elif process_type == "배출":
                    self._set_discharge_with_idle_timer(2, reason="robot_process_discharge")
                    if self.pot2_collecting and not self.pot2_discharge_timer:
                        self.pot2_discharge_timer = threading.Timer(
                            self.recording_delay_after_discharge,
                            self._delayed_stop_pot2_collection,
                        )
                        self.pot2_discharge_timer.start()

    def on_pot1_timeout(self):
        if self.pot1_collecting:
            print(f"[POT1 타임아웃] {self.pot1_timeout_seconds}초 동안 메시지 없음 → 자동 중지")
            self.stop_pot1_collection()
        self.pot1_timeout_timer = None

    def on_pot2_timeout(self):
        if self.pot2_collecting:
            print(f"[POT2 타임아웃] {self.pot2_timeout_seconds}초 동안 메시지 없음 → 자동 중지")
            self.stop_pot2_collection()
        self.pot2_timeout_timer = None

    def _delayed_stop_pot1_collection(self):
        self.pot1_discharge_timer = None
        if self.pot1_collecting:
            print(f"[POT1] 배출 후 {self.recording_delay_after_discharge}초 경과 - 수집 종료")
            self.stop_pot1_collection()

    def _delayed_stop_pot2_collection(self):
        self.pot2_discharge_timer = None
        if self.pot2_collecting:
            print(f"[POT2] 배출 후 {self.recording_delay_after_discharge}초 경과 - 수집 종료")
            self.stop_pot2_collection()

    def _cancel_discharge_idle_timer(self, pot: int) -> None:
        timer_attr = "pot1_discharge_idle_timer" if pot == 1 else "pot2_discharge_idle_timer"
        timer = getattr(self, timer_attr)
        if timer:
            try:
                timer.cancel()
            except Exception:
                pass
            setattr(self, timer_attr, None)

    def _set_discharge_with_idle_timer(self, pot: int, reason: str = "") -> None:
        if pot == 1:
            if self.pot1_status != "DISCHARGE":
                self.pot1_status = "DISCHARGE"
                print(f"[POT1] 상태 변경: DISCHARGE ({reason})")
                self._log_ops_event("pot_status_changed", pot=1, status="DISCHARGE", reason=reason)
            if self.pot1_discharge_idle_timer is None:
                self.pot1_discharge_idle_timer = threading.Timer(
                    self.discharge_to_idle_delay_sec,
                    self._set_pot1_idle_after_discharge,
                )
                self.pot1_discharge_idle_timer.start()
        else:
            if self.pot2_status != "DISCHARGE":
                self.pot2_status = "DISCHARGE"
                print(f"[POT2] 상태 변경: DISCHARGE ({reason})")
                self._log_ops_event("pot_status_changed", pot=2, status="DISCHARGE", reason=reason)
            if self.pot2_discharge_idle_timer is None:
                self.pot2_discharge_idle_timer = threading.Timer(
                    self.discharge_to_idle_delay_sec,
                    self._set_pot2_idle_after_discharge,
                )
                self.pot2_discharge_idle_timer.start()

    def _set_pot1_idle_after_discharge(self) -> None:
        self.pot1_discharge_idle_timer = None
        if self.pot1_status == "DISCHARGE":
            self.pot1_status = "IDLE"
            print(f"[POT1] 상태 변경: IDLE (DISCHARGE 후 {self.discharge_to_idle_delay_sec:.0f}초)")
            self._log_ops_event("pot_status_changed", pot=1, status="IDLE", reason="discharge_timeout")

    def _set_pot2_idle_after_discharge(self) -> None:
        self.pot2_discharge_idle_timer = None
        if self.pot2_status == "DISCHARGE":
            self.pot2_status = "IDLE"
            print(f"[POT2] 상태 변경: IDLE (DISCHARGE 후 {self.discharge_to_idle_delay_sec:.0f}초)")
            self._log_ops_event("pot_status_changed", pot=2, status="IDLE", reason="discharge_timeout")

    def _set_frying_enabled(self, enabled: bool) -> None:
        self.frying_running = enabled
        for worker in self.frying_workers.values():
            worker.set_enabled(enabled)

    def _set_observe_enabled(self, enabled: bool) -> None:
        self.observe_running = enabled
        for worker in self.observe_workers.values():
            worker.set_enabled(enabled)

    def set_overlay_enabled(self, enabled: bool) -> None:
        self.overlay_enabled = enabled
        for cam in self.cameras.values():
            if cam is not None:
                cam.set_overlay_enabled(enabled)

    def build_ai_snapshot(self, set_id: int):
        if set_id == 1:
            cam_ids = [0, 2]
        else:
            cam_ids = [1, 3]

        results = {}
        for cam_id in cam_ids:
            if cam_id in (0, 1):
                worker = self.frying_workers.get(0 if cam_id == 0 else 1)
            else:
                worker = self.observe_workers.get(cam_id)
            if not worker:
                results[str(cam_id)] = {"image": None, "metrics": {"status": "NO_WORKER"}}
                continue
            frame, mask, metrics = worker.get_snapshot()
            if frame is None:
                results[str(cam_id)] = {"image": None, "metrics": {"status": "NO_FRAME"}}
                continue

            target_w = _safe_int(self.config.get("web_preview_width", 640), 640)
            h, w = frame.shape[:2]
            target_h = int(h * target_w / max(w, 1))
            small = cv2.resize(frame, (target_w, target_h))

            if mask is not None and mask.any():
                mask_small = cv2.resize(mask, (target_w, target_h), interpolation=cv2.INTER_NEAREST)
                color = np.zeros_like(small)
                color[:, :, 1] = 255
                alpha = 0.35
                mask_bool = mask_small > 0
                overlay = small.copy()
                overlay[mask_bool] = cv2.addWeighted(small[mask_bool], 1 - alpha, color[mask_bool], alpha, 0)
            else:
                overlay = small

            ret, jpg = cv2.imencode(
                ".jpg",
                overlay,
                [cv2.IMWRITE_JPEG_QUALITY, _safe_int(self.config.get("web_preview_quality", 70), 70)],
            )
            if not ret:
                results[str(cam_id)] = {"image": None, "metrics": metrics}
                continue
            b64 = base64.b64encode(jpg.tobytes()).decode("ascii")
            results[str(cam_id)] = {"image": b64, "metrics": metrics}

        return results

    def schedule_taltal_capture(self, pot: int, delay_sec: float = 2.0):
        def do_capture():
            if pot == 1:
                self.pot1_taltal_pending = False
                self.capture_taltal_frame(pot=1)
            else:
                self.pot2_taltal_pending = False
                self.capture_taltal_frame(pot=2)

        if pot == 1:
            if self.pot1_taltal_timer:
                self.pot1_taltal_timer.cancel()
            self.pot1_taltal_pending = True
            self.pot1_taltal_timer = threading.Timer(delay_sec, do_capture)
            self.pot1_taltal_timer.start()
            print(f"[POT1] 탈탈 캡처 예약 ({delay_sec}초 후)")
        else:
            if self.pot2_taltal_timer:
                self.pot2_taltal_timer.cancel()
            self.pot2_taltal_pending = True
            self.pot2_taltal_timer = threading.Timer(delay_sec, do_capture)
            self.pot2_taltal_timer.start()
            print(f"[POT2] 탈탈 캡처 예약 ({delay_sec}초 후)")

    def capture_taltal_frame(self, pot: int):
        if pot == 1:
            frame = self.cameras.get(0).get_latest_frame() if self.cameras.get(0) else None
            if frame is not None:
                print("[POT1 탈탈] 프레임 캡처 완료")
            else:
                print("[POT1 탈탈] 최신 프레임 없음 - 스킵")
        else:
            frame = self.cameras.get(1).get_latest_frame() if self.cameras.get(1) else None
            if frame is not None:
                print("[POT2 탈탈] 프레임 캡처 완료")
            else:
                print("[POT2 탈탈] 최신 프레임 없음 - 스킵")

    def _get_target_time(self, target_time_raw: Optional[str]) -> int:
        if not target_time_raw:
            return int(self.config.get("default_target_time_sec", 180))

        if isinstance(target_time_raw, (int, float)):
            return int(target_time_raw)

        text = str(target_time_raw)
        if ":" in text:
            parts = text.split(":")
            if len(parts) == 3:
                try:
                    mm = int(parts[1])
                    ss = int(parts[2])
                    return mm * 60 + ss
                except ValueError:
                    pass
        if "분" in text:
            minutes = 0
            seconds = 0
            try:
                if "분" in text:
                    minutes = int(text.split("분")[0].strip())
                if "초" in text:
                    seconds = int(text.split("분")[-1].split("초")[0].strip())
            except Exception:
                pass
            return minutes * 60 + seconds

        try:
            return int(float(text))
        except ValueError:
            return int(self.config.get("default_target_time_sec", 180))

    def mark_completion_auto(self, position: str, probe_temp: float) -> None:
        if not self.data_collection_active:
            return
        if self.collection_completion_marked:
            return
        elapsed = 0
        if self.collection_start_time:
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
            "oil_temp_left": self.temps["pot1_oil"],
            "oil_temp_right": self.temps["pot2_oil"],
            "probe_temp_left": self.temps["pot1_probe"],
            "probe_temp_right": self.temps["pot2_probe"],
        }
        print(f"[완료마킹] 자동 마킹 ({position}): {elapsed:.1f}초, probe={probe_temp}")

    def start_data_collection(self) -> None:
        if self.current_food_type == "unknown":
            self.current_food_type = "manual"
        self.collection_session_id = datetime.now().strftime("session_%Y%m%d_%H%M%S")
        self.collection_start_time = datetime.now()
        self.collection_frame_counter = 0

        base_dir = os.path.expanduser("~/AI_Data")
        self.frying_session_dir = os.path.join(base_dir, "FryingData", self.collection_session_id)
        self.bucket_session_dir = os.path.join(base_dir, "BucketData", self.collection_session_id)

        for cam_idx in [0, 1]:
            os.makedirs(os.path.join(self.frying_session_dir, f"camera_{cam_idx}"), mode=0o755, exist_ok=True)
        for cam_idx in [2, 3]:
            os.makedirs(os.path.join(self.bucket_session_dir, f"camera_{cam_idx}"), mode=0o755, exist_ok=True)

        self.collection_completion_marked = False
        self.collection_completion_time = None
        self.collection_completion_info = {}
        self.data_collection_active = True
        self.collection_metadata = []
        print(f"[데이터수집] 시작: {self.collection_session_id}")

    def stop_data_collection(self) -> None:
        if not self.data_collection_active:
            return
        self.data_collection_active = False

        save_data = {
            "session_id": self.collection_session_id,
            "food_type": self.current_food_type,
            "start_time": self.collection_start_time,
            "frame_counter": self.collection_frame_counter,
            "metadata": list(self.collection_metadata),
            "completion_marked": self.collection_completion_marked,
            "completion_info": dict(self.collection_completion_info) if self.collection_completion_info else {},
            "frying_session_dir": self.frying_session_dir,
            "bucket_session_dir": self.bucket_session_dir,
            "collection_interval": self.collection_interval,
        }

        threading.Thread(target=self._save_collection_data_async, args=(save_data,), daemon=True).start()

        self.collection_session_id = None
        self.collection_start_time = None
        self.current_food_type = "unknown"

    def _save_collection_data_async(self, save_data: dict) -> None:
        try:
            end_time = datetime.now()
            duration = (end_time - save_data["start_time"]).total_seconds()

            temperature_timeline = []
            for item in save_data["metadata"]:
                if item["type"] in ["oil_temperature", "probe_temperature"]:
                    existing = next(
                        (x for x in temperature_timeline if x["timestamp"] == item["timestamp"]),
                        None,
                    )
                    key = f"{item['type'].replace('_temperature', '_temp')}_{item.get('position', item.get('pot', ''))}"
                    if existing:
                        existing[key] = item["value"]
                    else:
                        temperature_timeline.append({"timestamp": item["timestamp"], key: item["value"]})

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
                        "width": self.config.get("camera_width", 1280),
                        "height": self.config.get("camera_height", 720),
                    },
                    "fps": self.config.get("camera_fps", 30),
                },
                "temperature_timeline": temperature_timeline,
                "raw_metadata": save_data["metadata"],
                "metadata_count": len(save_data["metadata"]),
            }

            for dir_path in [save_data["frying_session_dir"], save_data["bucket_session_dir"]]:
                info_path = os.path.join(dir_path, "session_info.json")
                with open(info_path, "w", encoding="utf-8") as f:
                    json.dump(session_info, f, indent=2, ensure_ascii=False)

            print(f"[데이터수집] 종료: {save_data['frame_counter']}장 저장, {duration:.1f}초")
        except Exception as e:
            print(f"[데이터수집] 저장 오류: {e}")

    def start_pot1_collection(self) -> None:
        self.pot1_session_id = datetime.now().strftime("session_%Y%m%d_%H%M%S")
        self.pot1_start_time = datetime.now()
        self.pot1_frame_counter = 0
        self.pot1_last_collection_ts = 0.0
        self.pot1_status = "COOKING"
        self._cancel_discharge_idle_timer(1)

        base_dir = os.path.expanduser("~/AI_Data")
        food = self.pot1_food_type or "unknown"
        self.pot1_session_dir = os.path.join(base_dir, "pot1", self.pot1_session_id, food)
        for cam_idx in [0, 2]:
            os.makedirs(os.path.join(self.pot1_session_dir, f"camera_{cam_idx}"), mode=0o755, exist_ok=True)

        self.pot1_completion_marked = False
        self.pot1_completion_time = None
        self.pot1_completion_info = {}
        self.pot1_collecting = True
        self.pot1_metadata = []

        target_time = self._get_target_time(self.pot1_target_time)
        self.lift_tracker_pot1.start_session(self.pot1_session_id, food, target_time)

        self._set_frying_enabled(True)
        self._set_observe_enabled(True)

        print(f"[POT1 수집] 시작: {self.pot1_session_id} | 음식: {food}")

    def stop_pot1_collection(self) -> None:
        if not self.pot1_collecting:
            return
        self.pot1_collecting = False
        self.pot1_status = "IDLE"
        self._cancel_discharge_idle_timer(1)
        duration = (datetime.now() - self.pot1_start_time).total_seconds() if self.pot1_start_time else 0

        self.lift_tracker_pot1.stop_session()
        try:
            self.lift_tracker_pot1.save_session_data(self.pot1_session_dir)
        except Exception as e:
            print(f"[POT1 수집] Lift data 저장 오류: {e}")

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
            "cameras_used": [0, 2],
            "total_frames_saved": self.pot1_frame_counter,
            "raw_metadata": list(self.pot1_metadata),
            "metadata_count": len(self.pot1_metadata),
        }
        info_path = os.path.join(self.pot1_session_dir, "session_info.json")
        threading.Thread(target=self._save_session_info, args=(info_path, session_info), daemon=True).start()

        print(f"[POT1 수집] 종료: {self.pot1_frame_counter}장 저장, {duration:.1f}초")

        self.pot1_session_id = None
        self.pot1_start_time = None
        if not self.pot2_collecting:
            self._set_frying_enabled(False)
            self._set_observe_enabled(False)

        if self.pot1_taltal_timer:
            self.pot1_taltal_timer.cancel()
            self.pot1_taltal_timer = None
        self.pot1_taltal_pending = False

    def start_pot2_collection(self) -> None:
        self.pot2_session_id = datetime.now().strftime("session_%Y%m%d_%H%M%S")
        self.pot2_start_time = datetime.now()
        self.pot2_frame_counter = 0
        self.pot2_last_collection_ts = 0.0
        self.pot2_status = "COOKING"
        self._cancel_discharge_idle_timer(2)

        base_dir = os.path.expanduser("~/AI_Data")
        food = self.pot2_food_type or "unknown"
        self.pot2_session_dir = os.path.join(base_dir, "pot2", self.pot2_session_id, food)
        for cam_idx in [1, 3]:
            os.makedirs(os.path.join(self.pot2_session_dir, f"camera_{cam_idx}"), mode=0o755, exist_ok=True)

        self.pot2_completion_marked = False
        self.pot2_completion_time = None
        self.pot2_completion_info = {}
        self.pot2_collecting = True
        self.pot2_metadata = []

        target_time = self._get_target_time(self.pot2_target_time)
        self.lift_tracker_pot2.start_session(self.pot2_session_id, food, target_time)

        self._set_frying_enabled(True)
        self._set_observe_enabled(True)

        print(f"[POT2 수집] 시작: {self.pot2_session_id} | 음식: {food}")

    def stop_pot2_collection(self) -> None:
        if not self.pot2_collecting:
            return
        self.pot2_collecting = False
        self.pot2_status = "IDLE"
        self._cancel_discharge_idle_timer(2)
        duration = (datetime.now() - self.pot2_start_time).total_seconds() if self.pot2_start_time else 0

        self.lift_tracker_pot2.stop_session()
        try:
            self.lift_tracker_pot2.save_session_data(self.pot2_session_dir)
        except Exception as e:
            print(f"[POT2 수집] Lift data 저장 오류: {e}")

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
            "cameras_used": [1, 3],
            "total_frames_saved": self.pot2_frame_counter,
            "raw_metadata": list(self.pot2_metadata),
            "metadata_count": len(self.pot2_metadata),
        }
        info_path = os.path.join(self.pot2_session_dir, "session_info.json")
        threading.Thread(target=self._save_session_info, args=(info_path, session_info), daemon=True).start()

        print(f"[POT2 수집] 종료: {self.pot2_frame_counter}장 저장, {duration:.1f}초")

        self.pot2_session_id = None
        self.pot2_start_time = None
        if not self.pot1_collecting:
            self._set_frying_enabled(False)
            self._set_observe_enabled(False)

        if self.pot2_taltal_timer:
            self.pot2_taltal_timer.cancel()
            self.pot2_taltal_timer = None
        self.pot2_taltal_pending = False

    def _save_session_info(self, info_path: str, session_info: dict) -> None:
        try:
            with open(info_path, "w", encoding="utf-8") as f:
                json.dump(session_info, f, indent=2, ensure_ascii=False)
            print(f"[세션저장] 완료: {info_path}")
        except Exception as e:
            print(f"[세션저장] 실패: {e}")

    def save_pot1_data(self, frying_left, observe_left) -> None:
        if not self.pot1_collecting:
            return
        timestamp = datetime.now().strftime("%H%M%S_%f")[:-3]
        full_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        saver = get_image_saver(self.jpeg_quality, self.save_resolution["width"], self.save_resolution["height"])

        for cam_idx, frame in [(0, frying_left), (2, observe_left)]:
            if frame is not None:
                save_path = os.path.join(self.pot1_session_dir, f"camera_{cam_idx}", f"camera_{cam_idx}_{timestamp}.jpg")
                saver.save(save_path, frame)
                self.pot1_frame_counter += 1

        meta_path = os.path.join(self.pot1_session_dir, "meta", f"meta_{timestamp}.json")
        os.makedirs(os.path.dirname(meta_path), exist_ok=True)
        meta_data = {"timestamp": full_timestamp, "frame_id": timestamp, "pot": "pot1", **self.pot1_robot_status}
        try:
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta_data, f, ensure_ascii=False)
        except Exception as e:
            print(f"[POT1 메타] 저장 실패: {e}")

    def save_pot2_data(self, frying_right, observe_right) -> None:
        if not self.pot2_collecting:
            return
        timestamp = datetime.now().strftime("%H%M%S_%f")[:-3]
        full_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        saver = get_image_saver(self.jpeg_quality, self.save_resolution["width"], self.save_resolution["height"])

        for cam_idx, frame in [(1, frying_right), (3, observe_right)]:
            if frame is not None:
                save_path = os.path.join(self.pot2_session_dir, f"camera_{cam_idx}", f"camera_{cam_idx}_{timestamp}.jpg")
                saver.save(save_path, frame)
                self.pot2_frame_counter += 1

        meta_path = os.path.join(self.pot2_session_dir, "meta", f"meta_{timestamp}.json")
        os.makedirs(os.path.dirname(meta_path), exist_ok=True)
        meta_data = {"timestamp": full_timestamp, "frame_id": timestamp, "pot": "pot2", **self.pot2_robot_status}
        try:
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta_data, f, ensure_ascii=False)
        except Exception as e:
            print(f"[POT2 메타] 저장 실패: {e}")

    def save_collection_data(self, frying_left, frying_right, observe_left, observe_right) -> None:
        if not self.data_collection_active:
            return
        timestamp = datetime.now().strftime("%H%M%S_%f")[:-3]
        saver = get_image_saver(self.jpeg_quality, self.save_resolution["width"], self.save_resolution["height"])
        for cam_idx, frame in [(0, frying_left), (1, frying_right)]:
            if frame is not None:
                save_path = os.path.join(self.frying_session_dir, f"camera_{cam_idx}", f"cam{cam_idx}_{timestamp}.jpg")
                saver.save(save_path, frame)
        for cam_idx, frame in [(2, observe_left), (3, observe_right)]:
            if frame is not None:
                save_path = os.path.join(self.bucket_session_dir, f"camera_{cam_idx}", f"cam{cam_idx}_{timestamp}.jpg")
                saver.save(save_path, frame)
        self.collection_frame_counter += 1

    def _collection_loop(self) -> None:
        while not self.stop_event.is_set():
            if self.pot1_collecting:
                if time.time() - self.pot1_last_collection_ts >= self.collection_interval:
                    self.pot1_last_collection_ts = time.time()
                    cam0 = self.cameras.get(0)
                    cam2 = self.cameras.get(2)
                    self.save_pot1_data(
                        cam0.get_latest_frame() if cam0 else None,
                        cam2.get_latest_frame() if cam2 else None,
                    )
            if self.pot2_collecting:
                if time.time() - self.pot2_last_collection_ts >= self.collection_interval:
                    self.pot2_last_collection_ts = time.time()
                    cam1 = self.cameras.get(1)
                    cam3 = self.cameras.get(3)
                    self.save_pot2_data(
                        cam1.get_latest_frame() if cam1 else None,
                        cam3.get_latest_frame() if cam3 else None,
                    )
            if self.data_collection_active:
                if time.time() - self.collection_last_ts >= self.collection_interval:
                    self.collection_last_ts = time.time()
                    cam0 = self.cameras.get(0)
                    cam1 = self.cameras.get(1)
                    cam2 = self.cameras.get(2)
                    cam3 = self.cameras.get(3)
                    self.save_collection_data(
                        cam0.get_latest_frame() if cam0 else None,
                        cam1.get_latest_frame() if cam1 else None,
                        cam2.get_latest_frame() if cam2 else None,
                        cam3.get_latest_frame() if cam3 else None,
                    )
            time.sleep(0.05)

    def on_jetson1_relay_status(self, client, userdata, message):
        self._log_mqtt_message(message.topic, message.payload)
        try:
            raw_message = message.payload.decode("utf-8")
            relay_status = ""
            try:
                data = json.loads(raw_message)
                relay_status = str(data.get("relay_status", "")).upper()
            except json.JSONDecodeError:
                relay_status = raw_message.upper().strip()
            if relay_status == "ON":
                self.relay_turn_on()
            elif relay_status == "OFF":
                self.relay_turn_off(force=True)
        except Exception as e:
            print(f"[릴레이 동기화] 오류: {e}")

    def on_vibration_control(self, client, userdata, message):
        self._log_mqtt_message(message.topic, message.payload)
        try:
            raw_message = message.payload.decode("utf-8")
            command = None
            try:
                data = json.loads(raw_message)
                for key in ["command", "cmd", "action", "control", "status"]:
                    if key in data:
                        command = str(data[key]).upper()
                        break
            except json.JSONDecodeError:
                command = raw_message.upper().strip()

            if command in ["START", "ON", "BEGIN"]:
                self.start_vibration_check()
            elif command in ["STOP", "OFF", "END"]:
                self.stop_vibration_check()
        except Exception as e:
            print(f"[진동 MQTT] 오류: {e}")

    def start_vibration_check(self):
        if self.vibration_process is not None:
            try:
                running_pid = self.vibration_process.pid
            except Exception:
                running_pid = "unknown"
            print(f"[진동] 시작 스킵: 이미 실행 중(pid={running_pid}) status={self.vibration_status}")
            self._set_vibration_event("SKIPPED_ALREADY_RUNNING", self.vibration_status)
            self._log_ops_event(
                "vibration_check_skipped",
                reason="already_running",
                pid=running_pid,
                status=self.vibration_status,
            )
            return
        base_dir = os.path.dirname(os.path.abspath(SCRIPT_DIR))
        vibration_script = os.path.join(base_dir, "test_vibration_pymodbus3_finalrev.py")
        baseline_file = os.path.join(base_dir, "vibration_baseline_jetson2.json")
        result_file = os.path.join(base_dir, "vibration_result.json")

        if not os.path.exists(vibration_script):
            print(f"[진동] 오류: {vibration_script} 파일이 없습니다")
            self._set_vibration_status("ERROR", "FAILED_SCRIPT_MISSING")
            self._log_ops_event("vibration_check_failed", reason="script_missing", script=vibration_script)
            return

        def run_vibration_check():
            cmd = []
            try:
                env = os.environ.copy()
                env["VIB_UNIT_IDS"] = "0x50,0x51,0x52"
                cmd = ["python3", vibration_script, "--headless", "--check", "--duration", "10"]
                if os.path.exists(baseline_file):
                    cmd += ["--baseline", baseline_file]
                cmd += ["--result", result_file]
                self.vibration_process = subprocess.Popen(
                    cmd,
                    cwd=base_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    env=env,
                    text=True,
                )
                self.child_processes.append(self.vibration_process)
                print(
                    "[진동] 프로세스 시작 "
                    f"pid={self.vibration_process.pid} cmd={' '.join(cmd)} "
                    f"baseline={'Y' if os.path.exists(baseline_file) else 'N'}"
                )
                self._log_ops_event(
                    "vibration_check_started",
                    pid=self.vibration_process.pid,
                    baseline_exists=os.path.exists(baseline_file),
                    unit_ids=env.get("VIB_UNIT_IDS", ""),
                )
                self._set_vibration_event("STARTED", "MEASURING")
                stdout, _ = self.vibration_process.communicate(timeout=30)
                exit_code = self.vibration_process.returncode
                tail_lines = [line for line in (stdout or "").strip().splitlines() if line][-5:]
                for line in tail_lines:
                    print(f"[진동][stdout] {line}")
                if exit_code == 0 and os.path.exists(result_file):
                    with open(result_file, "r", encoding="utf-8") as f:
                        result = json.load(f)
                    status = result.get("status", "ERROR")
                    self._set_vibration_status(status, "COMPLETED")
                    print(f"[진동] 완료: exit={exit_code} status={status} result={result_file}")
                    self._log_ops_event(
                        "vibration_check_completed",
                        exit_code=exit_code,
                        status=status,
                        result_file=result_file,
                    )
                else:
                    self._set_vibration_status("ERROR", "FAILED_NONZERO_OR_NO_RESULT")
                    print(
                        f"[진동] 실패: exit={exit_code} result_exists={os.path.exists(result_file)} "
                        f"status={self.vibration_status}"
                    )
                    self._log_ops_event(
                        "vibration_check_failed",
                        reason="nonzero_or_no_result",
                        exit_code=exit_code,
                        result_exists=os.path.exists(result_file),
                    )
            except subprocess.TimeoutExpired:
                print("[진동] 타임아웃(30초): 프로세스 강제 종료")
                try:
                    self.vibration_process.kill()
                    self.vibration_process.wait(timeout=2)
                except Exception:
                    pass
                self._set_vibration_status("ERROR", "FAILED_TIMEOUT")
                self._log_ops_event("vibration_check_failed", reason="timeout")
            except Exception as e:
                print(f"[진동] 예외: {e}")
                self._set_vibration_status("ERROR", "FAILED_EXCEPTION")
                self._log_ops_event("vibration_check_failed", reason="exception", error=str(e))
            finally:
                if self.vibration_process in self.child_processes:
                    self.child_processes.remove(self.vibration_process)
                self.vibration_process = None
                print(f"[진동] 상태 갱신: {self.vibration_status}")

        self._set_vibration_status("MEASURING", "MEASURING")
        print("[진동] 측정 시작 요청 수락: status=MEASURING")
        threading.Thread(target=run_vibration_check, daemon=True).start()

    def stop_vibration_check(self):
        if self.vibration_process is None:
            return
        stopped_pid = None
        try:
            stopped_pid = self.vibration_process.pid
        except Exception:
            stopped_pid = None
        try:
            self.vibration_process.terminate()
            self.vibration_process.wait(timeout=3)
        except Exception:
            try:
                self.vibration_process.kill()
                self.vibration_process.wait()
            except Exception:
                pass
        if self.vibration_process in self.child_processes:
            self.child_processes.remove(self.vibration_process)
        self.vibration_process = None
        self._set_vibration_status("IDLE", "STOPPED")
        self._log_ops_event("vibration_check_stopped", pid=stopped_pid, status=self.vibration_status)

    def _log_mqtt_message(self, topic: str, payload) -> None:
        try:
            raw = payload.decode("utf-8") if isinstance(payload, (bytes, bytearray)) else str(payload)
        except Exception:
            raw = str(payload)
        timestamp = datetime.now()
        self.mqtt_message_log.appendleft(
            {
                "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                "topic": topic,
                "payload": raw,
            }
        )

        try:
            os.makedirs(self.mqtt_log_dir, exist_ok=True)
            date_str = timestamp.strftime("%Y-%m-%d")
            log_file = os.path.join(self.mqtt_log_dir, f"mqtt_{date_str}.log")
            full_ts = timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"[{full_ts}] {topic}\n{raw}\n\n")
        except Exception as e:
            print(f"[MQTT 로그] 파일 저장 실패: {e}")

    def _log_ops_event(self, event: str, **data) -> None:
        ts = datetime.now()
        entry = {
            "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "event": event,
            **data,
        }
        try:
            os.makedirs(self.ops_log_dir, exist_ok=True)
            date_str = ts.strftime("%Y-%m-%d")
            path = os.path.join(self.ops_log_dir, f"ops_{date_str}.jsonl")
            with self._ops_log_lock:
                with open(path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            if self.debug_print:
                print(f"[OPS 로그] 저장 실패: {e}")

    def _log_relay_event(self, action: str, **data) -> None:
        ts = datetime.now()
        date_str = ts.strftime("%Y-%m-%d")
        full_ts = ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        extras = ", ".join(f"{k}={v}" for k, v in data.items()) if data else ""
        line = f"[{full_ts}] action={action}"
        if extras:
            line = f"{line}, {extras}"
        try:
            os.makedirs(self.relay_log_dir, exist_ok=True)
            path = os.path.join(self.relay_log_dir, f"relay_{date_str}.log")
            with self._relay_log_lock:
                with open(path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
        except Exception as e:
            if self.debug_print:
                print(f"[Relay 로그] 저장 실패: {e}")

    def _set_vibration_event(self, event: str, status: str) -> None:
        self.last_vibration_event = {
            "event": event,
            "status": status,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _cancel_vibration_abnormal_timer(self) -> None:
        if self.vibration_abnormal_timer is not None:
            try:
                self.vibration_abnormal_timer.cancel()
            except Exception:
                pass
            self.vibration_abnormal_timer = None

    def _schedule_vibration_abnormal_reset(self) -> None:
        self._cancel_vibration_abnormal_timer()
        delay = max(0.1, float(self.vibration_abnormal_hold_sec))

        def _reset_to_idle():
            self.vibration_abnormal_timer = None
            if self.vibration_status != "ABNORMAL":
                return
            self.vibration_status = "IDLE"
            self._set_vibration_event("ABNORMAL_AUTO_RESET", "IDLE")
            self._log_ops_event(
                "vibration_status_auto_reset",
                from_status="ABNORMAL",
                to_status="IDLE",
                delay_sec=delay,
            )

        self.vibration_abnormal_timer = threading.Timer(delay, _reset_to_idle)
        self.vibration_abnormal_timer.daemon = True
        self.vibration_abnormal_timer.start()

    def _set_vibration_status(self, status: str, event: Optional[str] = None) -> None:
        self.vibration_status = status
        if event:
            self._set_vibration_event(event, status)
        if status == "ABNORMAL":
            self._schedule_vibration_abnormal_reset()
        else:
            self._cancel_vibration_abnormal_timer()

    def _publish_mqtt_status(self) -> None:
        if not self.mqtt_client:
            return

        try:
            status_data = self._build_status_payload()
            payload = json.dumps(status_data, ensure_ascii=False)
            topic = self.config.get("mqtt_topic_status", "jetson2/status")
            self.mqtt_client.client.publish(topic, payload, qos=self.config.get("mqtt_qos", 1))
        except Exception as e:
            print(f"[MQTT] publish error: {e}")

    def _build_status_payload(self) -> dict:
        observe_left = self.observe_left_effective
        if observe_left is None:
            observe_left = self.observe_left_state
        if observe_left is None:
            observe_left = "UNKNOWN"

        observe_right = self.observe_right_effective
        if observe_right is None:
            observe_right = self.observe_right_state
        if observe_right is None:
            observe_right = "UNKNOWN"

        return {
            "device_id": self.config.get("device_id", "jetson2"),
            "device_name": self.config.get("device_name", "Jetson2_Web"),
            "ip_address": get_ip_address(),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ai_mode": self.ai_mode_enabled,
            "frying": {
                "left": self.pot1_status,
                "right": self.pot2_status,
            },
            "observe": {
                "left": observe_left,
                "right": observe_right,
            },
            "vibration": {
                "status": self.vibration_status,
                "last_event": self.last_vibration_event,
            },
            "system": self.system_info.get_dynamic_info() if self.system_info else {},
        }

    def _get_effective_observe_state(self, raw_status: str, oil_temp: float) -> str:
        """FILLED + 유온 170°C 이상이면 '투입', 아니면 raw_status 그대로 반환"""
        투입_temp = float(self.config.get("observe_투입_temp_threshold", 170.0))
        try:
            oil_temp_value = float(oil_temp)
        except (TypeError, ValueError):
            oil_temp_value = float("-inf")
        if raw_status == "FILLED" and oil_temp_value >= 투입_temp:
            return "투입"
        return raw_status

    def _sync_observe_state(self) -> None:
        if not self.observe_workers:
            return
        left_worker = self.observe_workers.get(2)
        right_worker = self.observe_workers.get(3)

        if left_worker:
            left_result = left_worker.get_result()
            left_status = left_result.get("status")
            if left_status is not None:
                if left_status != self.observe_left_state:
                    self.observe_left_state = left_status
                    self._log_ops_event(
                        "observe_state_sync",
                        side="left",
                        status=left_status,
                        top1=left_result.get("top1"),
                        prob=left_result.get("prob"),
                    )
                left_effective = self._get_effective_observe_state(
                    left_status, self.temps.get("pot1_oil", 0.0)
                )
                if left_effective != self.observe_left_effective:
                    self.observe_left_effective = left_effective
                    self._log_ops_event("observe_effective_changed", side="left", effective=left_effective)

        if right_worker:
            right_result = right_worker.get_result()
            right_status = right_result.get("status")
            if right_status is not None:
                if right_status != self.observe_right_state:
                    self.observe_right_state = right_status
                    self._log_ops_event(
                        "observe_state_sync",
                        side="right",
                        status=right_status,
                        top1=right_result.get("top1"),
                        prob=right_result.get("prob"),
                    )
                right_effective = self._get_effective_observe_state(
                    right_status, self.temps.get("pot2_oil", 0.0)
                )
                if right_effective != self.observe_right_effective:
                    self.observe_right_effective = right_effective
                    self._log_ops_event("observe_effective_changed", side="right", effective=right_effective)

    def start(self) -> None:
        print("=" * 60)
        print("Jetson2 Web (Headless) Starting...")
        print("=" * 60)

        self.init_gpio()

        if self.config.get("gmsl_init_enabled", True):
            run_gmsl_init_script(self.config)
        if self.config.get("quick_bring_up_enabled", False):
            run_quick_bring_up(self.config)

        for cam_id, cam in self.cameras.items():
            if cam is None:
                continue
            cam.set_overlay_enabled(self.overlay_enabled)
            cam.start()
            time.sleep(0.3)

        for worker in self.frying_workers.values():
            worker.start()
            worker.set_enabled(False)

        observe_autostart = bool(self.config.get("observe_autostart", False))
        for worker in self.observe_workers.values():
            worker.start()
            worker.set_enabled(observe_autostart)
        if observe_autostart:
            self.observe_running = True

        if self.config.get("web_enabled", True):
            host = self.config.get("web_host", "0.0.0.0")
            if host == "tailscale":
                host = get_tailscale_ip() or "0.0.0.0"
            port = int(self.config.get("web_port", 8000))
            app = create_app(
                self.cameras,
                self.frying_workers,
                self.observe_workers,
                self.mqtt_client,
                self.config,
                state=self,
            )
            self._start_web(app, host, port)
            print(f"[Web] Dashboard: http://{host}:{port}/")

        print(f"[IP] Local: {get_ip_address()}")
        tailscale_ip = get_tailscale_ip()
        if tailscale_ip:
            print(f"[IP] Tailscale: {tailscale_ip}")

        self.running = True
        self.camera_watchdog_start_ts = time.time()
        self.camera_watchdog_stop.clear()
        self.camera_watchdog_thread = threading.Thread(target=self._camera_watchdog_loop, daemon=True)
        self.camera_watchdog_thread.start()
        self.collection_thread = threading.Thread(target=self._collection_loop, daemon=True)
        self.collection_thread.start()
        self._main_loop()

    def _start_web(self, app, host: str, port: int) -> None:
        def _run():
            import uvicorn

            uvicorn.run(app, host=host, port=port, log_level="warning", access_log=False)

        self.web_thread = threading.Thread(target=_run, daemon=True)
        self.web_thread.start()

    def _main_loop(self) -> None:
        last_mqtt_publish = 0.0
        mqtt_interval = float(self.config.get("mqtt_publish_interval", 2))

        try:
            while self.running:
                now = time.time()
                self._sync_observe_state()
                self._sync_frying_completion_state()
                if self.mqtt_client and now - last_mqtt_publish >= mqtt_interval:
                    self._publish_mqtt_status()
                    last_mqtt_publish = now
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("[Main] Interrupted by user")
        finally:
            self.stop()

    def _sync_frying_completion_state(self) -> None:
        # Original completion criteria is handled inside LiftEventTracker and
        # exposed as completion_detected in frying worker result.
        left_worker = self.frying_workers.get(0)
        right_worker = self.frying_workers.get(1)

        if left_worker and self.pot1_collecting:
            left_result = left_worker.get_result()
            if bool(left_result.get("completion_detected", False)):
                self._set_discharge_with_idle_timer(1, reason="tracker_completion")

        if right_worker and self.pot2_collecting:
            right_result = right_worker.get_result()
            if bool(right_result.get("completion_detected", False)):
                self._set_discharge_with_idle_timer(2, reason="tracker_completion")

    def _camera_watchdog_loop(self) -> None:
        grace = float(self.config.get("camera_watch_grace_sec", 10))
        stall_sec = float(self.config.get("camera_stall_sec", 3))
        check_interval = float(self.config.get("camera_watch_interval_sec", 1.0))
        gmsl_reinit = bool(self.config.get("gmsl_reinit_on_recover", True))
        gmsl_after = int(self.config.get("gmsl_reinit_after_failures", 2))
        gmsl_cooldown = float(self.config.get("gmsl_reinit_cooldown_sec", 20))
        last_gmsl = 0.0

        while not self.camera_watchdog_stop.is_set():
            now = time.time()
            if now - self.camera_watchdog_start_ts < grace:
                time.sleep(check_interval)
                continue
            for cam_id, cam in self.cameras.items():
                if cam is None or not cam.running:
                    continue
                last_ts = cam.stats.get("last_frame_ts", 0) or 0
                if last_ts == 0:
                    continue
                if now - last_ts > stall_sec and not cam.is_recovering():
                    self.camera_fail_counts[cam_id] = self.camera_fail_counts.get(cam_id, 0) + 1
                    print(f"[CAM{cam_id}] Stall detected ({now - last_ts:.1f}s), recovering...")
                    if gmsl_reinit and self.camera_fail_counts[cam_id] >= gmsl_after:
                        if now - last_gmsl >= gmsl_cooldown:
                            print("[GMSL] Re-init before camera recover")
                            run_gmsl_init_script(self.config)
                            last_gmsl = now
                            self.camera_fail_counts[cam_id] = 0
                    cam.request_recover()
            time.sleep(check_interval)

    def stop(self) -> None:
        if not self.running:
            return
        print("[Main] Shutting down...")
        self.running = False
        self.stop_event.set()
        self.camera_watchdog_stop.set()

        for cam in self.cameras.values():
            if cam is not None:
                cam.stop()

        for worker in self.frying_workers.values():
            worker.stop()
        for worker in self.observe_workers.values():
            worker.stop()

        if self.mqtt_client:
            self.mqtt_client.disconnect()

        if self.pot1_timeout_timer:
            self.pot1_timeout_timer.cancel()
        if self.pot2_timeout_timer:
            self.pot2_timeout_timer.cancel()
        if self.pot1_discharge_timer:
            self.pot1_discharge_timer.cancel()
        if self.pot2_discharge_timer:
            self.pot2_discharge_timer.cancel()
        if self.pot1_taltal_timer:
            self.pot1_taltal_timer.cancel()
        if self.pot2_taltal_timer:
            self.pot2_taltal_timer.cancel()

        self.stop_vibration_check()
        try:
            stop_image_saver()
        except Exception:
            pass

        if _GPIO_AVAILABLE:
            try:
                GPIO.output(29, GPIO.LOW)
                GPIO.output(31, GPIO.LOW)
                GPIO.setup(29, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
                GPIO.setup(31, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
                GPIO.cleanup()
            except Exception:
                pass

        print("[Main] Shutdown complete")


def main() -> None:
    _acquire_single_instance("jetson2_web.lock")
    config = load_config()
    app = Jetson2Web(config)

    def signal_handler(sig, frame):
        print("[Signal] Received, stopping...")
        app.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    app.start()


if __name__ == "__main__":
    main()
