#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Jetson1 Web Refactor - Headless + FastAPI Dashboard."""

import json
import os
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime, time as dtime, timedelta
from typing import Dict, Optional
import atexit
import errno
import fcntl

import cv2
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
_LOCK_FD = None

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gst_camera import GstCamera
from src.communication.mqtt_client import MQTTClient
from src.core.system_info import SystemInfo
from web.app import create_app

try:
    from ultralytics import YOLO
    import torch
    _YOLO_AVAILABLE = True
except Exception:
    _YOLO_AVAILABLE = False

try:
    import Jetson.GPIO as GPIO
    _GPIO_AVAILABLE = True
except Exception:
    GPIO = None
    _GPIO_AVAILABLE = False


def load_config(config_path: str = "config_jetson1_web.json") -> dict:
    with open(os.path.join(SCRIPT_DIR, config_path), "r", encoding="utf-8") as f:
        return json.load(f)


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


def ensure_gmsl_initialized(config: dict) -> bool:
    if not config.get("gmsl_init_enabled", True):
        return True
    init_script = os.path.join(REPO_ROOT, "init_gmsl_cameras.sh")
    if not os.path.exists(init_script):
        print(f"[GMSL] 초기화 스크립트 없음: {init_script}")
        return False
    use_sudo = bool(config.get("gmsl_init_use_sudo", False))
    cmd = ["bash", init_script]
    if use_sudo:
        cmd = ["sudo", "-n", "bash", init_script]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
    except Exception as e:
        print(f"[GMSL] 초기화 오류: {e}")
        return False
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip())
    if result.returncode != 0:
        if use_sudo:
            print("[GMSL] sudo 실패 (비밀번호 필요 가능). 수동으로 실행하세요.")
        return False
    print("[GMSL] 초기화 완료")
    return True


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
        self.latest_frame = None
        self.latest_lock = threading.Lock()
        self.web_frame = None
        self.web_lock = threading.Lock()
        self.person_boxes = []
        self.person_boxes_lock = threading.Lock()
        self.ready_event = threading.Event()

        self.stats = {
            "fps": 0,
            "frame_count": 0,
            "last_frame_ts": 0,
            "drop_count": 0,
            "start_ts": 0,
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
            print(f"[CAM{self.cam_id}] Failed to start")
            self.running = False
            return
        self.ready_event.set()
        self.stats["start_ts"] = time.time()

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

            with self.latest_lock:
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
        retry_count = int(self.config.get("camera_retry_count", 3))
        retry_interval = float(self.config.get("camera_retry_interval_sec", 1.0))
        started = False
        for attempt in range(1, retry_count + 1):
            if self.camera.start():
                started = True
                break
            print(f"[CAM{self.cam_id}] Start failed (attempt {attempt}/{retry_count})")
            time.sleep(retry_interval)
        return started

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
            with self.latest_lock:
                self.latest_frame = None
            with self.web_lock:
                self.web_frame = None
            self.stats["fps"] = 0
            self.stats["last_frame_ts"] = 0
            self.stats["start_ts"] = 0
            self.ready_event.clear()

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
                self.stats["start_ts"] = time.time()
                self.ready_event.set()
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

        draw_frame = frame.copy()
        with self.person_boxes_lock:
            boxes = list(self.person_boxes)
        for x1, y1, x2, y2, conf in boxes:
            cv2.rectangle(draw_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            label = f"Person {conf:.2f}"
            cv2.putText(
                draw_frame,
                label,
                (x1, max(20, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )

        h, w = draw_frame.shape[:2]
        target_w = int(self.config.get("web_preview_width", 640))
        target_h = int(h * target_w / max(w, 1))
        small = cv2.resize(draw_frame, (target_w, target_h))

        ret, jpg = cv2.imencode(
            ".jpg",
            small,
            [cv2.IMWRITE_JPEG_QUALITY, int(self.config.get("web_preview_quality", 70))],
        )
        if ret:
            with self.web_lock:
                self.web_frame = jpg.tobytes()
        self._last_web_update = now

    def get_frame_for_ai(self):
        try:
            return self.frame_queue.popleft()
        except IndexError:
            return None

    def get_latest_frame(self):
        with self.latest_lock:
            return None if self.latest_frame is None else self.latest_frame.copy()

    def get_web_frame(self):
        with self.web_lock:
            return self.web_frame

    def set_person_boxes(self, boxes):
        with self.person_boxes_lock:
            self.person_boxes = boxes

    def stop(self):
        self.running = False

    def wait_ready(self, timeout: float) -> bool:
        return self.ready_event.wait(timeout=timeout)


class PersonDetectionWorker(threading.Thread):
    """YOLO person detection + night motion detection."""

    def __init__(self, camera_worker: CameraWorker, config: dict, parent):
        super().__init__(daemon=True)
        self.camera = camera_worker
        self.config = config
        self.parent = parent

        self.mode = config.get("mode", "auto")
        self.day_start = config.get("day_start", "04:00")
        self.day_end = config.get("day_end", "21:00")
        self.detection_hold_sec = float(config.get("detection_hold_sec", 2))

        self.yolo_conf = float(config.get("yolo_confidence", 0.7))
        self.yolo_imgsz = int(config.get("yolo_imgsz", 416))
        self.motion_min_area = int(config.get("motion_min_area", 2500))
        self.binary_thresh = int(config.get("binary_thresh", 220))
        self.mog2_varthresh = int(config.get("mog2_varthresh", 24))
        self.warmup_frames = int(config.get("snapshot_warmup_frames", 30))
        self.snapshot_cooldown_sec = float(config.get("snapshot_cooldown_sec", 15))
        self.snapshot_dir = str(config.get("snapshot_dir", "Detection"))

        self.periodic_off_enabled = bool(config.get("periodic_off_pulse_enabled", True))
        self.periodic_off_interval_min = float(config.get("periodic_off_pulse_interval_min", 0.05))
        self.periodic_off_test_mode = bool(config.get("periodic_off_test_mode", False))

        self.night_check_minutes = int(config.get("night_check_minutes", 0))
        self.night_check_active = False
        self.night_no_person_deadline = None
        self.off_triggered_once = False
        self.periodic_off_active = False
        self.last_off_pulse = None

        self.person_detected = False
        self.motion_detected = False
        self.last_confidence = 0.0
        self.detection_count = 0
        self.night_detected_once = False
        self.night_snapshot_saved_once = False
        self.last_night_detected_result = False

        self.last_person_detected_time = None
        self.det_hold_start = None
        self.on_triggered = False
        self._last_daytime = None

        self.running = False
        self.frame_idx = 0
        self.yolo_frame_skip = 0
        self.motion_frame_skip = 0
        self._night_person_state = None
        self._night_motion_state = None
        self.snapshot_count = 0
        self.last_snapshot_path = None
        self.last_snapshot_time = None
        self.last_snapshot_tick = None

        self.bg = cv2.createBackgroundSubtractorMOG2(
            history=500, varThreshold=self.mog2_varthresh, detectShadows=True
        )
        self.kernel = np.ones((5, 5), np.uint8)

        if _YOLO_AVAILABLE:
            model_path = os.path.join(SCRIPT_DIR, config.get("yolo_model", "yolo12n.pt"))
            self.yolo_model = YOLO(model_path)
            if torch.cuda.is_available():
                self.yolo_model.to("cuda")
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.yolo_model = None
            self.device = "cpu"

    def run(self):
        self.running = True
        while self.running:
            frame = self.camera.get_frame_for_ai()
            if frame is None:
                time.sleep(0.01)
                continue
            now = datetime.now()
            self._update_mode(now)

            if self._is_daytime(now):
                self._process_day(frame, now)
                self.periodic_off_active = False
            else:
                self._process_night(frame, now)
                self._check_periodic_off(now)

            time.sleep(0.01)

    def _is_daytime(self, now: datetime) -> bool:
        if self.mode == "day":
            return True
        if self.mode == "night":
            return False
        day_start = dtime.fromisoformat(self.day_start)
        day_end = dtime.fromisoformat(self.day_end)
        return day_start <= now.time() <= day_end

    def _update_mode(self, now: datetime) -> None:
        daytime = self._is_daytime(now)
        if self._last_daytime is None:
            self._last_daytime = daytime
            if not daytime:
                self.night_detected_once = False
                self.night_snapshot_saved_once = False
        elif self._last_daytime and not daytime:
            self.night_detected_once = False
            self.night_snapshot_saved_once = False
            self._night_person_state = None
            self.parent._log_ops_event("night_summary_reset")
        elif (not self._last_daytime) and daytime:
            self.last_night_detected_result = bool(self.night_detected_once or self.night_snapshot_saved_once)
            self.parent._log_ops_event(
                "night_summary_finalized",
                detected=self.last_night_detected_result,
            )
            self.night_detected_once = False
            self.night_snapshot_saved_once = False
        self._last_daytime = daytime

        if daytime:
            if self.off_triggered_once or self.periodic_off_active:
                self.off_triggered_once = False
                self.periodic_off_active = False
                self.night_check_active = False
                self.night_no_person_deadline = None
                self.on_triggered = False
                self.parent._log_ops_event("night_mode_reset", mode=self.mode)
            if self.parent.auto_relay_enabled and not self.on_triggered and self.parent.startup_on_pulse_enabled:
                self.parent.relay_turn_on(publish_to_jetson2=True)
                self.parent.publish_robot_control("ON")
                self.on_triggered = True
        else:
            if not self.night_check_active:
                self.night_check_active = True
                self.night_no_person_deadline = now + timedelta(minutes=self.night_check_minutes)
                self.det_hold_start = None
                self.off_triggered_once = False
                self.parent._log_ops_event(
                    "night_mode_enter",
                    mode=self.mode,
                    night_check_minutes=self.night_check_minutes,
                    deadline=self.night_no_person_deadline.strftime("%Y-%m-%d %H:%M:%S"),
                )

    def _process_day(self, frame: np.ndarray, now: datetime) -> None:
        if not self.yolo_model:
            self.camera.set_person_boxes([])
            return
        self.yolo_frame_skip += 1
        if self.yolo_frame_skip < 3:
            return
        self.yolo_frame_skip = 0

        results = self.yolo_model.predict(frame, conf=self.yolo_conf, imgsz=self.yolo_imgsz, verbose=False, device=self.device)
        r = results[0]

        detected = False
        max_conf = 0.0
        person_boxes = []
        if r.boxes is not None and r.boxes.cls is not None and len(r.boxes.cls) > 0:
            for i, cls in enumerate(r.boxes.cls):
                if r.names.get(int(cls), "") == "person":
                    detected = True
                    conf = float(r.boxes.conf[i]) if hasattr(r.boxes, "conf") else 0.0
                    max_conf = max(max_conf, conf)
                    box = r.boxes.xyxy[i].cpu().numpy().astype(int).tolist()
                    person_boxes.append((box[0], box[1], box[2], box[3], conf))
        self.camera.set_person_boxes(person_boxes)

        if detected:
            self.person_detected = True
            self.last_person_detected_time = now
            self.last_confidence = max_conf
            if self.det_hold_start is None:
                self.det_hold_start = now
            else:
                hold = (now - self.det_hold_start).total_seconds()
                if hold >= self.detection_hold_sec and not self.on_triggered:
                    if self.parent.auto_relay_enabled:
                        self.parent.relay_turn_on(publish_to_jetson2=False)
                        self.parent.publish_relay_status("ON")
                        self.parent.publish_robot_control("ON")
                    self.on_triggered = True
        else:
            self.person_detected = False
            self.det_hold_start = None

    def _process_night(self, frame: np.ndarray, now: datetime) -> None:
        if self.night_check_active:
            if self.yolo_model:
                self.yolo_frame_skip += 1
                if self.yolo_frame_skip < 3:
                    return
                self.yolo_frame_skip = 0
                results = self.yolo_model.predict(frame, conf=self.yolo_conf, imgsz=self.yolo_imgsz, verbose=False, device=self.device)
                r = results[0]
                detected = False
                person_boxes = []
                if r.boxes is not None and r.boxes.cls is not None and len(r.boxes.cls) > 0:
                    for i, cls in enumerate(r.boxes.cls):
                        if r.names.get(int(cls), "") == "person":
                            detected = True
                            conf = float(r.boxes.conf[i]) if hasattr(r.boxes, "conf") else 0.0
                            box = r.boxes.xyxy[i].cpu().numpy().astype(int).tolist()
                            person_boxes.append((box[0], box[1], box[2], box[3], conf))
                self.camera.set_person_boxes(person_boxes)
                if detected:
                    self.person_detected = True
                    self.night_detected_once = True
                    self.last_person_detected_time = now
                    self.night_no_person_deadline = now + timedelta(minutes=self.night_check_minutes)
                    if self._night_person_state is not True:
                        self.parent._log_ops_event(
                            "night_person_detected",
                            deadline=self.night_no_person_deadline.strftime("%Y-%m-%d %H:%M:%S"),
                        )
                    self._night_person_state = True
                else:
                    self.person_detected = False
                    if self._night_person_state is not False:
                        self.parent._log_ops_event("night_person_not_detected")
                    self._night_person_state = False
                if self.night_no_person_deadline is not None and now >= self.night_no_person_deadline:
                    if not self.off_triggered_once:
                        self.parent.send_off_pulse()
                        self.parent._log_ops_event(
                            "night_off_triggered",
                            reason="no_person_timeout",
                            night_check_minutes=self.night_check_minutes,
                        )
                        self.off_triggered_once = True
                        if self.periodic_off_enabled:
                            self.periodic_off_active = True
                    self.night_check_active = False
            return

        self.camera.set_person_boxes([])

        # motion detection stage
        self.motion_frame_skip += 1
        if self.motion_frame_skip < 3:
            return
        self.motion_frame_skip = 0

        fg = self.bg.apply(frame)
        _, thr = cv2.threshold(fg, self.binary_thresh, 255, cv2.THRESH_BINARY)
        clean = cv2.morphologyEx(thr, cv2.MORPH_OPEN, self.kernel, iterations=1)
        contours, _ = cv2.findContours(clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        motion = False
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area >= self.motion_min_area:
                motion = True
                break
        self.motion_detected = motion
        if motion and self.frame_idx > self.warmup_frames:
            now_tick = time.monotonic()
            can_save = (
                self.last_snapshot_tick is None
                or ((now_tick - self.last_snapshot_tick) >= self.snapshot_cooldown_sec)
            )
            if can_save:
                self._save_snapshot(frame, now)
                self.last_snapshot_tick = now_tick
        if self._night_motion_state != motion:
            self.parent._log_ops_event("night_motion_changed", motion=motion)
            self._night_motion_state = motion

    def _check_periodic_off(self, now: datetime) -> None:
        if not self.periodic_off_enabled:
            return
        if not self.periodic_off_active and not self.periodic_off_test_mode:
            return
        if self.last_off_pulse is None:
            self.last_off_pulse = now
            return
        elapsed = (now - self.last_off_pulse).total_seconds()
        if elapsed >= self.periodic_off_interval_min * 60:
            self.parent.send_off_pulse()
            self.last_off_pulse = now

    def _save_snapshot(self, frame: np.ndarray, timestamp: datetime) -> None:
        try:
            day_dir = timestamp.strftime("%Y%m%d")
            ts_name = timestamp.strftime("%H%M%S_%f")[:-3]
            expanded = os.path.expanduser(self.snapshot_dir)
            if os.path.isabs(expanded):
                base_dir = expanded
            else:
                base_dir = os.path.join(os.path.expanduser("~"), expanded)
            out_dir = os.path.join(base_dir, day_dir)
            os.makedirs(out_dir, mode=0o755, exist_ok=True)
            out_path = os.path.join(out_dir, f"{ts_name}.jpg")
            cv2.imwrite(out_path, frame)

            self.snapshot_count += 1
            self.last_snapshot_path = out_path
            self.last_snapshot_time = timestamp
            self.night_snapshot_saved_once = True
            self.parent._log_ops_event(
                "night_snapshot_saved",
                image_path=out_path,
                count=self.snapshot_count,
            )
        except Exception as e:
            if self.parent.debug_print:
                print(f"[Night Snapshot] save failed: {e}")


class PersonDataCollectionWorker(threading.Thread):
    """Scheduled person data collection (weekday, time window)."""

    def __init__(self, camera_worker: CameraWorker, config: dict, stop_event: threading.Event, parent=None):
        super().__init__(daemon=True)
        self.camera = camera_worker
        self.config = config
        self.stop_event = stop_event
        self.parent = parent
        self.enabled = bool(config.get("person_data_collection_enabled", False))

        self.start_time = config.get("person_collection_start_time", "08:30")
        self.end_time = config.get("person_collection_end_time", "12:00")
        self.interval_sec = float(config.get("person_collection_interval_sec", 5))
        self.save_dir = config.get("person_collection_save_dir", "AI_Data/PersonData")
        self.save_resolution = config.get(
            "person_collection_save_resolution", {"width": 640, "height": 512}
        )
        self.jpeg_quality = int(config.get("person_collection_jpeg_quality", 50))

        self.last_saved = None
        self.saved_count = 0

    def run(self):
        while not self.stop_event.is_set():
            if not self.enabled:
                time.sleep(0.5)
                continue

            now = datetime.now()
            if now.weekday() >= 5:
                time.sleep(1.0)
                continue

            start = dtime.fromisoformat(self.start_time)
            end = dtime.fromisoformat(self.end_time)
            if not (start <= now.time() <= end):
                time.sleep(1.0)
                continue

            frame = self.camera.get_latest_frame()
            if frame is not None:
                self._save_frame(frame, now)

            time.sleep(self.interval_sec)

    def _save_frame(self, frame: np.ndarray, now: datetime) -> None:
        base_dir = os.path.expanduser(f"~/{self.save_dir}")
        date_dir = now.strftime("%Y%m%d")
        out_dir = os.path.join(base_dir, date_dir)
        os.makedirs(out_dir, mode=0o755, exist_ok=True)

        ts_name = now.strftime("%H%M%S_%f")[:-3]
        out_path = os.path.join(out_dir, f"person_{ts_name}.jpg")

        save_w = int(self.save_resolution.get("width", 640))
        save_h = int(self.save_resolution.get("height", 512))
        resized = cv2.resize(frame, (save_w, save_h), interpolation=cv2.INTER_AREA)
        cv2.imwrite(out_path, resized, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])

        self.last_saved = now
        self.saved_count += 1
        if self.parent:
            self.parent._log_ops_event(
                "person_snapshot_saved",
                path=out_path,
                width=save_w,
                height=save_h,
                count=self.saved_count,
            )


class Jetson1Web:
    """Main controller for headless + web dashboard."""

    def __init__(self, config: dict):
        self.config = config
        self.running = False

        self.debug_print = bool(config.get("debug_print_enabled", False))

        self.system_info = SystemInfo(
            device_name=config.get("device_name", "Jetson1_Web"),
            location=config.get("device_location", "unknown"),
        )

        self.relay_enabled = False
        self.relay_mode = config.get("relay_mode", "pulse")
        self.auto_relay_enabled = bool(config.get("auto_relay_enabled", True))
        self.startup_on_pulse_enabled = bool(config.get("startup_on_pulse_enabled", False))

        self.vibration_process = None
        self.vibration_status = "IDLE"
        self.child_processes = []

        self.mqtt_message_log = deque(maxlen=int(config.get("mqtt_log_maxlen", 200)))
        self.mqtt_log_dir = os.path.join(SCRIPT_DIR, "mqtt_logs")
        self.ops_log_dir = os.path.join(SCRIPT_DIR, "ops_logs")
        self._ops_log_lock = threading.Lock()

        self.cameras: Dict[int, Optional[CameraWorker]] = {}
        self._init_cameras()

        self.person_worker: Optional[PersonDetectionWorker] = None
        self._init_person_worker()

        self.mqtt_client: Optional[MQTTClient] = None
        self._init_mqtt()

        self.web_thread: Optional[threading.Thread] = None
        self.collection_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.camera_watchdog_thread: Optional[threading.Thread] = None
        self.camera_watchdog_stop = threading.Event()
        self.camera_watchdog_start_ts = time.time()
        self.camera_fail_counts = {}
        self.camera_watch_enabled = bool(self.config.get("camera_watch_enabled", False))
        self.camera_init_delay_sec = float(self.config.get("camera_init_delay_sec", 4.0))
        self.camera_init_timeout_sec = float(self.config.get("camera_init_timeout_sec", 8.0))

        # Stirfry recording state
        self.stirfry_save_enabled = bool(config.get("stirfry_save_enabled", False))
        self.stirfry_save_dir = config.get("stirfry_save_dir", "AI_Data/StirFryData")
        self.stirfry_save_resolution = config.get("stirfry_save_resolution", {"width": 1920, "height": 1536})
        self.stirfry_jpeg_quality = int(config.get("stirfry_jpeg_quality", 100))
        self.stirfry_frame_skip = int(config.get("stirfry_frame_skip", 90))
        self.recording_delay_after_discharge = int(config.get("recording_delay_after_discharge", 20))

        self.stirfry_pot1_recording = False
        self.stirfry_pot2_recording = False
        self.stirfry_pot1_food_type = "unknown"
        self.stirfry_pot2_food_type = "unknown"
        self.stirfry_pot1_session_id = None
        self.stirfry_pot2_session_id = None
        self.stirfry_pot1_session_start_time = None
        self.stirfry_pot2_session_start_time = None
        self.stirfry_pot1_frame_count = 0
        self.stirfry_pot2_frame_count = 0
        self.stirfry_pot1_metadata = []
        self.stirfry_pot2_metadata = []
        self.stirfry_pot1_robot_status = {}
        self.stirfry_pot2_robot_status = {}
        self.stirfry_pot1_skip_counter = 0
        self.stirfry_pot2_skip_counter = 0
        self.pot1_discharge_timer = None
        self.pot2_discharge_timer = None
        self.forced_person_detected: Optional[bool] = None

        self.person_collection_worker: Optional[PersonDataCollectionWorker] = None
        self._init_person_collection_worker()

    def _init_cameras(self) -> None:
        person_index = int(self.config.get("person_camera_index", 2))
        stirfry_left_index = int(self.config.get("stirfry_left_camera_index", 0))
        stirfry_right_index = int(self.config.get("stirfry_right_camera_index", 1))

        if self.config.get("camera_person_enabled", True):
            self.cameras[0] = CameraWorker(0, person_index, self.config)
        else:
            self.cameras[0] = None

        if self.config.get("stirfry_left_enabled", True):
            self.cameras[1] = CameraWorker(1, stirfry_left_index, self.config)
        else:
            self.cameras[1] = None

        if self.config.get("stirfry_right_enabled", True):
            self.cameras[2] = CameraWorker(2, stirfry_right_index, self.config)
        else:
            self.cameras[2] = None

    def _init_person_worker(self) -> None:
        cam = self.cameras.get(0)
        if cam is None:
            return
        if not self.config.get("person_detection_enabled", True):
            return
        self.person_worker = PersonDetectionWorker(cam, self.config, self)

    def _init_person_collection_worker(self) -> None:
        cam = self.cameras.get(0)
        if cam is None:
            return
        if not self.config.get("person_data_collection_enabled", False):
            return
        self.person_collection_worker = PersonDataCollectionWorker(cam, self.config, self.stop_event, self)

    def _init_mqtt(self) -> None:
        if not self.config.get("mqtt_enabled", False):
            return

        self.mqtt_client = MQTTClient(
            broker=self.config.get("mqtt_broker", "localhost"),
            port=self.config.get("mqtt_port", 1883),
            client_id=self.config.get("mqtt_client_id", "jetson1_web"),
        )
        self.mqtt_client.connect(blocking=True, timeout=5.0)

        qos = self.config.get("mqtt_qos", 1)
        self.mqtt_client.subscribe(self.config.get("mqtt_topic_stirfry_pot1_food_type", "stirfry/pot1/food_type"), self.on_stirfry_pot1_food_type, qos=qos)
        self.mqtt_client.subscribe(self.config.get("mqtt_topic_stirfry_pot1_control", "stirfry/pot1/control"), self.on_stirfry_pot1_control, qos=qos)
        self.mqtt_client.subscribe(self.config.get("mqtt_topic_stirfry_pot2_food_type", "stirfry/pot2/food_type"), self.on_stirfry_pot2_food_type, qos=qos)
        self.mqtt_client.subscribe(self.config.get("mqtt_topic_stirfry_pot2_control", "stirfry/pot2/control"), self.on_stirfry_pot2_control, qos=qos)
        self.mqtt_client.subscribe(self.config.get("mqtt_topic_robot_status", "HR/Status"), self.on_robot_status, qos=qos)
        self.mqtt_client.subscribe(self.config.get("mqtt_topic_vibration_control", "calibration/vibration/control"), self.on_vibration_control, qos=qos)

    def init_gpio(self) -> None:
        if not _GPIO_AVAILABLE:
            print("[GPIO] Jetson.GPIO not available")
            return
        try:
            GPIO.setmode(GPIO.BOARD)
            GPIO.setup(29, GPIO.OUT, initial=GPIO.LOW)
            GPIO.setup(31, GPIO.OUT, initial=GPIO.LOW)
            print("[GPIO] Pin 29, 31 initialized for Relay control (OFF)")
        except Exception as e:
            print(f"[GPIO] 초기화 실패: {e}")

    def relay_turn_on(self, publish_to_jetson2: bool = True) -> None:
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
            else:
                GPIO.output(31, GPIO.HIGH)
            self.relay_enabled = True
            if publish_to_jetson2:
                self.publish_relay_status("ON")
            self._log_ops_event("relay_on", mode=self.relay_mode, publish_to_jetson2=publish_to_jetson2)
        except Exception as e:
            print(f"[GPIO] Relay ON 실패: {e}")
            self._log_ops_event("relay_on_error", error=str(e))

    def relay_turn_off(self) -> None:
        if not _GPIO_AVAILABLE:
            self._log_ops_event("relay_off_skipped", reason="gpio_unavailable")
            return
        if not self.relay_enabled:
            self._log_ops_event("relay_off_skipped", reason="already_off")
            return
        try:
            if self.relay_mode == "pulse":
                GPIO.output(29, GPIO.HIGH)
                time.sleep(0.2)
                GPIO.output(29, GPIO.LOW)
            else:
                GPIO.output(29, GPIO.LOW)
            self.relay_enabled = False
            self.publish_relay_status("OFF")
            self._log_ops_event("relay_off", mode=self.relay_mode)
        except Exception as e:
            print(f"[GPIO] Relay OFF 실패: {e}")
            self._log_ops_event("relay_off_error", error=str(e))

    def send_off_pulse(self) -> None:
        if not _GPIO_AVAILABLE:
            self._log_ops_event("relay_off_pulse_skipped", reason="gpio_unavailable")
            return
        try:
            GPIO.output(29, GPIO.HIGH)
            time.sleep(0.2)
            GPIO.output(29, GPIO.LOW)
            self.relay_enabled = False
            self.publish_relay_status("OFF")
            self.publish_robot_control("OFF")
            self._log_ops_event("relay_off_pulse", mode=self.relay_mode)
        except Exception as e:
            print(f"[GPIO] OFF 펄스 실패: {e}")
            self._log_ops_event("relay_off_pulse_error", error=str(e))

    def publish_relay_status(self, status: str) -> None:
        if not self.mqtt_client:
            return
        topic = self.config.get("mqtt_topic_jetson1_relay", "jetson1/relay/status")
        payload = {
            "relay_status": status.upper(),
            "source": "jetson1",
            "timestamp": datetime.now().isoformat(),
        }
        try:
            self.mqtt_client.client.publish(topic, json.dumps(payload), qos=self.config.get("mqtt_qos", 1))
        except Exception:
            pass

    def publish_robot_control(self, command: str) -> None:
        if not self.mqtt_client:
            return
        topic = self.config.get("mqtt_topic", "robot/control")
        payload = {
            "command": command,
            "device_id": self.config.get("device_id", "jetson1"),
            "timestamp": datetime.now().isoformat(),
        }
        try:
            self.mqtt_client.client.publish(topic, json.dumps(payload), qos=self.config.get("mqtt_qos", 1))
        except Exception:
            pass

    def on_stirfry_pot1_food_type(self, client, userdata, message):
        self._log_mqtt_message(message.topic, message.payload)
        self.stirfry_pot1_food_type = message.payload.decode().strip()
        if not self.stirfry_pot1_recording:
            self.start_stirfry_pot1_recording()
        else:
            self.stirfry_pot1_metadata.append({
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                "type": "food_type_change",
                "value": self.stirfry_pot1_food_type,
            })

    def on_stirfry_pot2_food_type(self, client, userdata, message):
        self._log_mqtt_message(message.topic, message.payload)
        self.stirfry_pot2_food_type = message.payload.decode().strip()
        if not self.stirfry_pot2_recording:
            self.start_stirfry_pot2_recording()
        else:
            self.stirfry_pot2_metadata.append({
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                "type": "food_type_change",
                "value": self.stirfry_pot2_food_type,
            })

    def on_stirfry_pot1_control(self, client, userdata, message):
        self._log_mqtt_message(message.topic, message.payload)
        cmd = message.payload.decode().strip().lower()
        if cmd in ["stop", "discharge"]:
            if self.stirfry_pot1_recording:
                threading.Timer(self.recording_delay_after_discharge, self.stop_stirfry_pot1_recording).start()

    def on_stirfry_pot2_control(self, client, userdata, message):
        self._log_mqtt_message(message.topic, message.payload)
        cmd = message.payload.decode().strip().lower()
        if cmd in ["stop", "discharge"]:
            if self.stirfry_pot2_recording:
                threading.Timer(self.recording_delay_after_discharge, self.stop_stirfry_pot2_recording).start()

    def on_robot_status(self, client, userdata, message):
        self._log_mqtt_message(message.topic, message.payload)
        try:
            data = json.loads(message.payload.decode())
        except Exception:
            return
        status_list = data.get("Status", [])
        vibration_request = data.get("VibrationRequest", False)
        chk_vibration = False
        seen_device = False
        for pot_data in status_list:
            if str(pot_data.get("DeviceNum", "")) != "1":
                continue
            seen_device = True
            chk_val = pot_data.get("ChkVibration", False)
            if isinstance(chk_val, str):
                chk_val = chk_val.strip().lower() == "true"
            if chk_val:
                chk_vibration = True
                break

        if seen_device and chk_vibration:
            if self.config.get("vibration_test_mode", False):
                self.vibration_status = "NORMAL"
            else:
                self.start_vibration_check()
        elif vibration_request:
            if self.config.get("vibration_test_mode", False):
                self.vibration_status = "NORMAL"
            else:
                self.start_vibration_check()

        for pot_data in status_list:
            if str(pot_data.get("DeviceNum", "")) != "1":
                continue
            pot_num = str(pot_data.get("PTNum", ""))
            recipe = pot_data.get("NowRecipe", "")
            process_type = pot_data.get("ProcessType", "")
            robot_meta = {
                "recipe": recipe,
                "process_type": process_type,
                "running_time": pot_data.get("RunningTime", ""),
                "target_time": pot_data.get("TargetTime", ""),
                "rb_status": pot_data.get("RBstatus", ""),
            }
            if pot_num == "0":
                self.stirfry_pot1_robot_status = robot_meta
                if process_type in ["투입", "조리"]:
                    if not self.stirfry_pot1_recording:
                        self.stirfry_pot1_food_type = recipe or "unknown"
                        self.start_stirfry_pot1_recording()
                elif process_type == "배출":
                    if self.stirfry_pot1_recording:
                        if self.pot1_discharge_timer:
                            self.pot1_discharge_timer.cancel()
                        self.pot1_discharge_timer = threading.Timer(self.recording_delay_after_discharge, self.stop_stirfry_pot1_recording)
                        self.pot1_discharge_timer.start()
            elif pot_num == "1":
                self.stirfry_pot2_robot_status = robot_meta
                if process_type in ["투입", "조리"]:
                    if not self.stirfry_pot2_recording:
                        self.stirfry_pot2_food_type = recipe or "unknown"
                        self.start_stirfry_pot2_recording()
                elif process_type == "배출":
                    if self.stirfry_pot2_recording:
                        if self.pot2_discharge_timer:
                            self.pot2_discharge_timer.cancel()
                        self.pot2_discharge_timer = threading.Timer(self.recording_delay_after_discharge, self.stop_stirfry_pot2_recording)
                        self.pot2_discharge_timer.start()

    def on_vibration_control(self, client, userdata, message):
        self._log_mqtt_message(message.topic, message.payload)
        cmd = message.payload.decode().strip().lower()
        if cmd == "start":
            self.start_vibration_check()
        elif cmd == "stop":
            self.stop_vibration_check()

    def start_vibration_check(self):
        if self.vibration_process is not None:
            return
        base_dir = REPO_ROOT
        vibration_script = os.path.join(base_dir, "test_vibration_pymodbus3_finalrev.py")
        baseline_file = os.path.join(base_dir, "vibration_baseline_jetson1.json")
        result_file = os.path.join(base_dir, "vibration_result.json")

        if not os.path.exists(vibration_script):
            print(f"[진동] 오류: {vibration_script} 파일이 없습니다")
            self.vibration_status = "ERROR"
            return

        def run_vibration_check():
            try:
                env = os.environ.copy()
                env["VIB_UNIT_IDS"] = "0x53,0x54,0x55"
                cmd = ["python3", vibration_script, "--headless", "--check", "--duration", "10"]
                if os.path.exists(baseline_file):
                    cmd.extend(["--baseline", baseline_file])
                self.vibration_process = subprocess.Popen(
                    cmd,
                    cwd=base_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    env=env,
                    text=True,
                )
                self.child_processes.append(self.vibration_process)
                stdout, _ = self.vibration_process.communicate(timeout=30)
                if stdout:
                    print(stdout)
                if os.path.exists(result_file):
                    with open(result_file, "r", encoding="utf-8") as f:
                        result = json.load(f)
                    self.vibration_status = result.get("status", "ERROR")
                else:
                    self.vibration_status = "ERROR"
            except Exception:
                self.vibration_status = "ERROR"
            finally:
                if self.vibration_process in self.child_processes:
                    self.child_processes.remove(self.vibration_process)
                self.vibration_process = None

        self.vibration_status = "MEASURING"
        threading.Thread(target=run_vibration_check, daemon=True).start()

    def stop_vibration_check(self):
        if self.vibration_process is None:
            return
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
        self.vibration_status = "IDLE"

    def start_stirfry_pot1_recording(self):
        if not self.stirfry_save_enabled:
            return
        self.stirfry_pot1_recording = True
        self.stirfry_pot1_frame_count = 0
        self.stirfry_pot1_skip_counter = 0
        self.stirfry_pot1_session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.stirfry_pot1_session_start_time = datetime.now()
        self.stirfry_pot1_metadata = []
        self.stirfry_pot1_metadata.append({
            "timestamp": self.stirfry_pot1_session_start_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "session_id": self.stirfry_pot1_session_id,
            "food_type": self.stirfry_pot1_food_type,
        })
        self._log_ops_event(
            "stirfry_recording_start",
            pot="pot1",
            session_id=self.stirfry_pot1_session_id,
            food_type=self.stirfry_pot1_food_type,
        )

    def stop_stirfry_pot1_recording(self):
        if not self.stirfry_pot1_recording:
            return
        self.stirfry_pot1_recording = False
        self.stirfry_pot1_skip_counter = 0
        self._log_ops_event(
            "stirfry_recording_stop",
            pot="pot1",
            session_id=self.stirfry_pot1_session_id,
            frame_count=self.stirfry_pot1_frame_count,
        )

    def start_stirfry_pot2_recording(self):
        if not self.stirfry_save_enabled:
            return
        self.stirfry_pot2_recording = True
        self.stirfry_pot2_frame_count = 0
        self.stirfry_pot2_skip_counter = 0
        self.stirfry_pot2_session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.stirfry_pot2_session_start_time = datetime.now()
        self.stirfry_pot2_metadata = []
        self.stirfry_pot2_metadata.append({
            "timestamp": self.stirfry_pot2_session_start_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "session_id": self.stirfry_pot2_session_id,
            "food_type": self.stirfry_pot2_food_type,
        })
        self._log_ops_event(
            "stirfry_recording_start",
            pot="pot2",
            session_id=self.stirfry_pot2_session_id,
            food_type=self.stirfry_pot2_food_type,
        )

    def stop_stirfry_pot2_recording(self):
        if not self.stirfry_pot2_recording:
            return
        self.stirfry_pot2_recording = False
        self.stirfry_pot2_skip_counter = 0
        self._log_ops_event(
            "stirfry_recording_stop",
            pot="pot2",
            session_id=self.stirfry_pot2_session_id,
            frame_count=self.stirfry_pot2_frame_count,
        )

    def _save_stirfry_frame(self, frame: np.ndarray, pot: str):
        if not self.stirfry_save_enabled or frame is None:
            return
        now = datetime.now()
        ts_name = now.strftime("%H%M%S_%f")[:-3]
        full_timestamp = now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        base_dir = os.path.expanduser(f"~/{self.stirfry_save_dir}")
        if pot == "pot1":
            session_dir = os.path.join(base_dir, "pot1", self.stirfry_pot1_session_id, self.stirfry_pot1_food_type)
            cam_dir = "camera_0"
        else:
            session_dir = os.path.join(base_dir, "pot2", self.stirfry_pot2_session_id, self.stirfry_pot2_food_type)
            cam_dir = "camera_1"

        out_dir = os.path.join(session_dir, cam_dir)
        os.makedirs(out_dir, mode=0o755, exist_ok=True)
        save_width = self.stirfry_save_resolution["width"]
        save_height = self.stirfry_save_resolution["height"]
        resized = cv2.resize(frame, (save_width, save_height), interpolation=cv2.INTER_AREA)
        out_path = os.path.join(out_dir, f"{cam_dir}_{ts_name}.jpg")
        cv2.imwrite(out_path, resized, [cv2.IMWRITE_JPEG_QUALITY, self.stirfry_jpeg_quality])

        meta_dir = os.path.join(session_dir, "meta")
        os.makedirs(meta_dir, mode=0o755, exist_ok=True)
        meta_path = os.path.join(meta_dir, f"meta_{ts_name}.json")
        meta_data = {
            "timestamp": full_timestamp,
            "frame_id": ts_name,
            "pot": pot,
            **(self.stirfry_pot1_robot_status if pot == "pot1" else self.stirfry_pot2_robot_status),
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta_data, f, ensure_ascii=False)
        self._log_ops_event(
            "stirfry_snapshot_saved",
            pot=pot,
            image_path=out_path,
            meta_path=meta_path,
            frame_id=ts_name,
        )

    def _collection_loop(self):
        while not self.stop_event.is_set():
            if self.stirfry_pot1_recording:
                self.stirfry_pot1_skip_counter += 1
                if self.stirfry_pot1_skip_counter >= self.stirfry_frame_skip:
                    self.stirfry_pot1_skip_counter = 0
                    cam = self.cameras.get(1)
                    frame = cam.get_latest_frame() if cam else None
                    if frame is not None:
                        self._save_stirfry_frame(frame, "pot1")
                        self.stirfry_pot1_frame_count += 1
            if self.stirfry_pot2_recording:
                self.stirfry_pot2_skip_counter += 1
                if self.stirfry_pot2_skip_counter >= self.stirfry_frame_skip:
                    self.stirfry_pot2_skip_counter = 0
                    cam = self.cameras.get(2)
                    frame = cam.get_latest_frame() if cam else None
                    if frame is not None:
                        self._save_stirfry_frame(frame, "pot2")
                        self.stirfry_pot2_frame_count += 1
            time.sleep(0.05)

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
        except Exception:
            pass

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

    def build_status(self, person_detected_override: Optional[bool] = None) -> dict:
        person = self.person_worker
        mqtt_connected = False
        if self.mqtt_client:
            try:
                mqtt_connected = self.mqtt_client.is_connected()
            except Exception:
                mqtt_connected = False
        if person_detected_override is not None:
            person_detected_value = bool(person_detected_override)
        elif self.forced_person_detected is not None:
            person_detected_value = bool(self.forced_person_detected)
        elif person:
            is_daytime = person._is_daytime(datetime.now())
            person_detected_value = (
                bool(person.last_night_detected_result) if is_daytime else bool(person.person_detected)
            )
        else:
            person_detected_value = False
        person_collection = {
            "enabled": bool(self.person_collection_worker and self.person_collection_worker.enabled),
            "count": self.person_collection_worker.saved_count if self.person_collection_worker else 0,
            "last_saved": (
                self.person_collection_worker.last_saved.strftime("%Y-%m-%d %H:%M:%S")
                if self.person_collection_worker and self.person_collection_worker.last_saved
                else None
            ),
        }
        night_snapshot = {
            "count": person.snapshot_count if person else 0,
            "last_saved": (
                person.last_snapshot_time.strftime("%Y-%m-%d %H:%M:%S")
                if person and person.last_snapshot_time
                else None
            ),
            "last_path": person.last_snapshot_path if person else None,
        }
        return {
            "device_id": self.config.get("device_id", "jetson1"),
            "device_name": self.config.get("device_name", "Jetson1_Web"),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mode": person.mode if person else "unknown",
            "person_detected": person_detected_value,
            "person_detected_forced": self.forced_person_detected,
            "motion_detected": person.motion_detected if person else False,
            "yolo_confidence": person.last_confidence if person else 0.0,
            "relay_enabled": self.relay_enabled,
            "vibration": {"status": self.vibration_status},
            "recording": {
                "pot1": self.stirfry_pot1_recording,
                "pot2": self.stirfry_pot2_recording,
                "pot1_frames": self.stirfry_pot1_frame_count,
                "pot2_frames": self.stirfry_pot2_frame_count,
            },
            "person_collection": person_collection,
            "night_snapshot": night_snapshot,
            "mqtt": {"connected": mqtt_connected},
            "system": self.system_info.get_dynamic_info(),
        }

    def set_mode(self, mode: str) -> None:
        mode = mode.lower()
        if mode not in ("day", "night", "auto"):
            return
        self.config["mode"] = mode
        if self.person_worker:
            self.person_worker.mode = mode

    def _publish_mqtt_status(self, person_detected_override: Optional[bool] = None) -> None:
        if not self.mqtt_client:
            return
        topic = self.config.get("mqtt_topic_jetson1_status", "jetson1/status")
        try:
            status_data = self.build_status(person_detected_override=person_detected_override)
            status_data["person_detected"] = "TRUE" if bool(status_data.get("person_detected", False)) else "FALSE"
            payload = json.dumps(status_data, ensure_ascii=False)
            self.mqtt_client.client.publish(topic, payload, qos=self.config.get("mqtt_qos", 1))
        except Exception:
            pass

    def force_publish_next_day_night_result(self) -> bool:
        if not self.person_worker:
            return False
        result = bool(
            self.person_worker.night_detected_once
            or self.person_worker.night_snapshot_saved_once
        )
        self.person_worker.last_night_detected_result = result
        # Keep current cycle flags for repeated test clicks during the same night.
        self.person_worker.person_detected = result
        self._log_ops_event("night_summary_force_publish", detected=result)
        self._publish_mqtt_status(person_detected_override=result)
        return result

    def set_forced_person_detected(self, value: Optional[bool]) -> None:
        self.forced_person_detected = None if value is None else bool(value)

    def start(self) -> None:
        print("=" * 60)
        print("Jetson1 Web (Headless) Starting...")
        print("=" * 60)

        self.init_gpio()
        ensure_gmsl_initialized(self.config)

        # Sequential camera init (Jetson2 style, with delay)
        for cam_id in sorted(self.cameras.keys()):
            cam = self.cameras[cam_id]
            if cam is not None:
                print(f"[CAM{cam_id}] Starting...")
                cam.start()
                if not cam.wait_ready(self.camera_init_timeout_sec):
                    print(f"[CAM{cam_id}] Start timeout")
                time.sleep(self.camera_init_delay_sec)

        if self.person_worker:
            self.person_worker.start()

        if self.person_collection_worker:
            self.person_collection_worker.start()

        if self.config.get("web_enabled", True):
            host = self.config.get("web_host", "0.0.0.0")
            port = int(self.config.get("web_port", 7000))
            app = create_app(self.cameras, self, self.config)
            self._start_web(app, host, port)
            print(f"[Web] Dashboard: http://{host}:{port}/")

        self.collection_thread = threading.Thread(target=self._collection_loop, daemon=True)
        self.collection_thread.start()

        if self.camera_watch_enabled:
            self.camera_watchdog_start_ts = time.time()
            self.camera_watchdog_stop.clear()
            self.camera_watchdog_thread = threading.Thread(target=self._camera_watchdog_loop, daemon=True)
            self.camera_watchdog_thread.start()

        self.running = True
        self._main_loop()

    def _start_web(self, app, host: str, port: int) -> None:
        def _run():
            import uvicorn
            uvicorn.run(app, host=host, port=port, log_level="warning", access_log=False)
        self.web_thread = threading.Thread(target=_run, daemon=True)
        self.web_thread.start()

    def _main_loop(self) -> None:
        last_publish = 0.0
        interval = float(self.config.get("mqtt_publish_interval", 2))
        try:
            while self.running:
                now = time.time()
                if self.mqtt_client and now - last_publish >= interval:
                    self._publish_mqtt_status()
                    last_publish = now
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

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
                            ensure_gmsl_initialized(self.config)
                            last_gmsl = now
                            self.camera_fail_counts[cam_id] = 0
                    cam.request_recover()
            time.sleep(check_interval)

    def stop(self) -> None:
        if not self.running:
            return
        self.running = False
        self.stop_event.set()
        self.camera_watchdog_stop.set()

        if self.person_worker:
            self.person_worker.running = False

        if self.person_collection_worker:
            self.person_collection_worker.enabled = False

        for cam in self.cameras.values():
            if cam is not None:
                cam.stop()

        if self.mqtt_client:
            self.mqtt_client.disconnect()

        self.stop_vibration_check()

        if _GPIO_AVAILABLE:
            try:
                GPIO.output(29, GPIO.LOW)
                GPIO.output(31, GPIO.LOW)
                GPIO.cleanup()
            except Exception:
                pass


def main():
    _acquire_single_instance("jetson1_web.lock")
    config = load_config()
    app = Jetson1Web(config)

    def signal_handler(sig, frame):
        app.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    app.start()


if __name__ == "__main__":
    main()
