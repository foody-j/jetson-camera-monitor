#!/usr/bin/env python3
"""Continuous vibration collector with event-window capture for Jetson web apps."""

import csv
import json
import logging
import os
import threading
import time
from collections import deque
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusIOException
from pymodbus.logging import Log as PymodbusLog
from serial import SerialException

try:
    import torch
    import torch.nn as nn

    _TORCH_AVAILABLE = True
except Exception:
    _TORCH_AVAILABLE = False


# Hide noisy serial buffer cleanup warnings while keeping real errors visible.
logging.getLogger("pymodbus.logging").setLevel(logging.ERROR)
PymodbusLog.setLevel(logging.ERROR)


DEFAULT_VIB_PORT_BY_ID = "/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A9NF7ROC-if00-port0"
PARITY = "N"
STOPBITS = 1
BYTESIZE = 8
TIMEOUT_S = 0.08
POLL_HZ_TOTAL = 45
RETRY_READ = 1
RECONNECT_TIMEOUT = 3.0
WARMUP_SEC = 10.0
ZERO_EPS = 0.02
MISSING_PERSIST_SEC = 1.0
ACC_SCALE = 16.0 / 32768.0
FREQ_DIVISOR = 10.0

REG_AX = 0x34
REG_VX = 0x3A
REG_DX = 0x41
REG_HX = 0x44
READ_BLOCKS = {
    "acc": (REG_AX, 3),
    "vel": (REG_VX, 3),
    "disp": (REG_DX, 3),
    "freq": (REG_HX, 3),
}
REG_UNLOCK_ADDR = 0x0069
REG_SAVE = 0x00


class ContinuousVibrationMonitor:
    def __init__(
        self,
        unit_ids: List[int],
        *,
        baseline_path: Optional[str] = None,
        cnn_model_path: Optional[str] = None,
        cnn_threshold: Optional[float] = None,
        use_cnn_main: bool = True,
        event_root_dir: Optional[str] = None,
        pre_sec: float = 3.0,
        post_sec: float = 2.0,
        buffer_sec: float = 15.0,
        log_prefix: str = "[진동]",
    ) -> None:
        self.unit_ids = list(unit_ids)
        self.baseline_path = baseline_path
        self.cnn_model_path = cnn_model_path
        self.cnn_threshold = cnn_threshold
        self.use_cnn_main = use_cnn_main
        self.pre_sec = max(0.5, float(pre_sec))
        self.post_sec = max(0.5, float(post_sec))
        self.buffer_sec = max(self.pre_sec + self.post_sec + 1.0, float(buffer_sec))
        self.log_prefix = log_prefix

        home_dir = os.path.expanduser("~")
        self.event_root_dir = event_root_dir or os.path.join(home_dir, "data", "vibration_events")
        os.makedirs(self.event_root_dir, exist_ok=True)

        self.port = os.getenv(
            "VIB_PORT",
            DEFAULT_VIB_PORT_BY_ID if os.path.exists(DEFAULT_VIB_PORT_BY_ID) else "/dev/ttyUSB0",
        )
        self.baud = int(os.getenv("VIB_BAUD", "115200"))
        self.sample_rate_hint_per_unit = POLL_HZ_TOTAL / max(1, len(self.unit_ids))
        self.maxlen = max(200, int(self.buffer_sec * self.sample_rate_hint_per_unit))

        self.client: Optional[ModbusSerialClient] = None
        self.running = False
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self.buffer_lock = threading.Lock()
        self.capture_lock = threading.Lock()
        self.capture_thread: Optional[threading.Thread] = None
        self.capture_cancel_requested = False
        self.last_capture_result: Dict = {}

        self.rows: Dict[int, deque] = {uid: deque(maxlen=self.maxlen) for uid in self.unit_ids}
        self.last_ok = {uid: time.time() for uid in self.unit_ids}
        self.missing_since = {uid: None for uid in self.unit_ids}
        self.program_start_ts = 0.0

    def start(self) -> None:
        if self.running:
            return
        self.client = self._make_client()
        print(f"{self.log_prefix} 상시 수집 시작 unit_ids={','.join(f'0x{u:02X}' for u in self.unit_ids)}")
        print(f"{self.log_prefix} 연결 시도 {self.port} @ {self.baud}bps")
        if not self.client.connect():
            raise RuntimeError(f"vibration connect failed: {self.port}")
        print(f"{self.log_prefix} 연결 성공")
        self.program_start_ts = time.time()
        self.stop_event.clear()
        self.running = True
        self.thread = threading.Thread(target=self._collector_loop, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.capture_cancel_requested = True
        self.stop_event.set()
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3.0)
        if self.client is not None:
            try:
                self.client.close()
            except Exception:
                pass
        print(f"{self.log_prefix} 상시 수집 종료")

    def cancel_capture(self) -> None:
        self.capture_cancel_requested = True

    def is_capture_running(self) -> bool:
        return self.capture_thread is not None and self.capture_thread.is_alive()

    def trigger_capture(
        self,
        *,
        callback: Optional[Callable[[Dict], None]] = None,
        result_path: Optional[str] = None,
        event_tag: str = "trigger",
    ) -> Tuple[bool, str]:
        with self.capture_lock:
            if not self.running:
                return False, "monitor_not_running"
            if self.is_capture_running():
                return False, "capture_already_running"
            self.capture_cancel_requested = False
            event_ts = time.time()
            self.capture_thread = threading.Thread(
                target=self._capture_worker,
                kwargs={
                    "event_ts": event_ts,
                    "callback": callback,
                    "result_path": result_path,
                    "event_tag": event_tag,
                },
                daemon=True,
            )
            self.capture_thread.start()
        return True, "capture_started"

    def get_recent_summary(self, window_sec: float = 3.0) -> Dict:
        snapshot = self._snapshot(time.time() - max(0.5, float(window_sec)), time.time())
        total_samples, measured, measured_per_uid, _, _ = self._build_measured(snapshot)
        return {
            "window_sec": float(window_sec),
            "total_samples": total_samples,
            "unit_ids": [f"0x{u:02X}" for u in self.unit_ids],
            "measured": measured,
            "measured_per_uid": measured_per_uid,
        }

    def get_recent_snapshot(self, window_sec: float = 3.0) -> Dict[int, List[dict]]:
        return self._snapshot(time.time() - max(0.5, float(window_sec)), time.time())

    def save_recent_plot(self, out_path: str, window_sec: float = 5.0) -> str:
        snapshot = self._snapshot(time.time() - max(0.5, float(window_sec)), time.time())
        result = {"status": "LIVE", "decision_source": "live_recent"}
        return self._save_summary_plot(snapshot, result, out_path)

    def _capture_worker(
        self,
        *,
        event_ts: float,
        callback: Optional[Callable[[Dict], None]],
        result_path: Optional[str],
        event_tag: str,
    ) -> None:
        print(f"{self.log_prefix} 이벤트 캡처 시작 pre={self.pre_sec:.1f}s post={self.post_sec:.1f}s")
        time.sleep(self.post_sec)
        if self.capture_cancel_requested:
            print(f"{self.log_prefix} 캡처 취소됨")
            return
        snapshot = self._snapshot(event_ts - self.pre_sec, event_ts + self.post_sec)
        result = self._analyze_snapshot(snapshot, event_ts=event_ts, result_path=result_path, event_tag=event_tag)
        self.last_capture_result = result
        if callback:
            try:
                callback(result)
            except Exception as exc:
                print(f"{self.log_prefix} callback 오류: {exc}")

    def _make_client(self) -> ModbusSerialClient:
        return ModbusSerialClient(
            port=self.port,
            baudrate=self.baud,
            bytesize=BYTESIZE,
            parity=PARITY,
            stopbits=STOPBITS,
            timeout=TIMEOUT_S,
        )

    def _modbus_call(self, func, **kwargs):
        if "slave" in kwargs:
            uid = kwargs.pop("slave")
            for key in ("slave", "unit", "device_id"):
                try:
                    return func(**kwargs, **{key: uid})
                except TypeError:
                    continue
            return func(**kwargs)
        return func(**kwargs)

    @staticmethod
    def _ok(rr) -> bool:
        return (rr is not None) and hasattr(rr, "isError") and (not rr.isError()) and hasattr(rr, "registers")

    @staticmethod
    def _s16(v: int) -> int:
        return v - 0x10000 if v >= 0x8000 else v

    def _parse_map(self, regs_by_block):
        acc_regs = regs_by_block["acc"]
        vel_regs = regs_by_block["vel"]
        disp_regs = regs_by_block["disp"]
        freq_regs = regs_by_block["freq"]
        ax, ay, az = [self._s16(v) for v in acc_regs]
        vx, vy, vz = [self._s16(v) for v in vel_regs]
        dx, dy, dz = [self._s16(v) for v in disp_regs]
        hx, hy, hz = [self._s16(v) for v in freq_regs]
        acc = (ax * ACC_SCALE, ay * ACC_SCALE, az * ACC_SCALE)
        vel = (float(vx), float(vy), float(vz))
        disp = (float(dx), float(dy), float(dz))
        freq = (hx / FREQ_DIVISOR, hy / FREQ_DIVISOR, hz / FREQ_DIVISOR)
        return acc, vel, disp, freq

    def _axis_zero_mask(self, acc, vel, disp):
        return [
            (abs(acc[i]) <= ZERO_EPS) and (abs(vel[i]) <= ZERO_EPS) and (abs(disp[i]) <= ZERO_EPS)
            for i in range(3)
        ]

    @staticmethod
    def _axis_alive(acc, vel, disp, idx):
        return (abs(acc[idx]) > ZERO_EPS) or (abs(vel[idx]) > ZERO_EPS) or (abs(disp[idx]) > ZERO_EPS)

    def _unlock_sensor(self, uid: int) -> None:
        try:
            self._modbus_call(self.client.write_register, address=REG_UNLOCK_ADDR, value=0xB588, slave=uid)
        except Exception:
            pass

    def _restart_sensor(self, uid: int) -> None:
        try:
            self._unlock_sensor(uid)
            time.sleep(0.05)
            self._modbus_call(self.client.write_register, address=REG_SAVE, value=0x00FF, slave=uid)
        except Exception as exc:
            print(f"{self.log_prefix} UID 0x{uid:02X} 재시작 오류: {exc}")

    def _read_register_range(self, uid: int, start_addr: int, count: int, label: str):
        last_rr = None
        for attempt in range(1, RETRY_READ + 1):
            rr = self._modbus_call(self.client.read_holding_registers, address=start_addr, count=count, slave=uid)
            last_rr = rr
            if self._ok(rr):
                return rr.registers
            rr = self._modbus_call(self.client.read_input_registers, address=start_addr, count=count, slave=uid)
            last_rr = rr
            if self._ok(rr):
                return rr.registers
            if attempt < RETRY_READ:
                time.sleep(0.01)
        raise ModbusIOException(f"UID 0x{uid:02X} {label} read failed last={last_rr}")

    def _read_block_retry(self, uid: int):
        regs_by_block = {}
        for label, (start_addr, count) in READ_BLOCKS.items():
            regs_by_block[label] = self._read_register_range(uid, start_addr, count, label)
        return regs_by_block

    def _collector_loop(self) -> None:
        poll_dt = 1.0 / max(1.0, POLL_HZ_TOTAL)
        while not self.stop_event.is_set():
            warmup = (time.time() - self.program_start_ts) < WARMUP_SEC
            cycle_ts = time.time()
            try:
                if not getattr(self.client, "connected", False):
                    if not self.client.connect():
                        time.sleep(0.2)
                        continue
                for uid in self.unit_ids:
                    had_error = False
                    try:
                        regs = self._read_block_retry(uid)
                        acc, vel, disp, freq = self._parse_map(regs)
                        zmask = self._axis_zero_mask(acc, vel, disp)
                        dead_count = sum(1 for bit in zmask if bit)
                        alive_axes = [i for i in range(3) if (not zmask[i]) and self._axis_alive(acc, vel, disp, i)]
                        now = time.time()
                        real_missing = (dead_count == 1) and (len(alive_axes) == 2)
                        if real_missing:
                            if warmup:
                                self.missing_since[uid] = None
                            else:
                                if self.missing_since[uid] is None:
                                    self.missing_since[uid] = now
                                if (now - self.missing_since[uid]) >= MISSING_PERSIST_SEC:
                                    print(f"{self.log_prefix} UID 0x{uid:02X} 한 축 누락 지속")
                        else:
                            self.missing_since[uid] = None

                        row = {
                            "time": time.time(),
                            "acc": acc,
                            "vel": vel,
                            "disp": disp,
                            "freq": freq,
                        }
                        with self.buffer_lock:
                            self.rows[uid].append(row)
                        self.last_ok[uid] = row["time"]
                    except (ModbusIOException, SerialException, OSError) as exc:
                        had_error = True
                        self.missing_since[uid] = None
                        print(f"{self.log_prefix} UID 0x{uid:02X} 읽기 오류: {exc}")
                        try:
                            self.client.close()
                        except Exception:
                            pass
                        time.sleep(0.2)
                        self.client.connect()
                    except Exception as exc:
                        had_error = True
                        print(f"{self.log_prefix} UID 0x{uid:02X} 예외: {exc}")

                    if (not had_error) and (time.time() - self.last_ok[uid] > RECONNECT_TIMEOUT):
                        if not warmup:
                            print(f"{self.log_prefix} UID 0x{uid:02X} 타임아웃")
                        self.last_ok[uid] = time.time()
            finally:
                elapsed = time.time() - cycle_ts
                time.sleep(max(0.0, poll_dt - elapsed))

    def _snapshot(self, start_ts: float, end_ts: float) -> Dict[int, List[dict]]:
        out = {}
        with self.buffer_lock:
            for uid in self.unit_ids:
                out[uid] = [row for row in list(self.rows[uid]) if start_ts <= row["time"] <= end_ts]
        return out

    def _load_baseline(self) -> dict:
        if not self.baseline_path or not os.path.exists(self.baseline_path):
            return {}
        try:
            with open(self.baseline_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            print(f"{self.log_prefix} 베이스라인 로드 오류: {exc}")
            return {}

    def _fft_peak(self, series, t_series) -> float:
        if len(series) < 16 or len(t_series) < 2:
            return 0.0
        y = np.asarray(series, dtype=float)
        dt = (t_series[-1] - t_series[0]) / max(1, len(t_series) - 1)
        fs = 1.0 / dt if dt > 0 else self.sample_rate_hint_per_unit
        y = y - np.mean(y)
        y_fft = np.fft.rfft(np.hanning(len(y)) * y)
        freqs = np.fft.rfftfreq(len(y), d=1.0 / fs)
        mags = np.abs(y_fft)
        if len(mags) <= 1:
            return 0.0
        return float(freqs[np.argmax(mags[1:]) + 1])

    def _save_snapshot_csvs(self, snapshot: Dict[int, List[dict]], event_dir: str) -> List[str]:
        paths = []
        header = [
            "time",
            "ACC_X(g)",
            "ACC_Y(g)",
            "ACC_Z(g)",
            "VEL_X(mm/s)",
            "VEL_Y(mm/s)",
            "VEL_Z(mm/s)",
            "DISP_X(um)",
            "DISP_Y(um)",
            "DISP_Z(um)",
            "FREQ_X(Hz)",
            "FREQ_Y(Hz)",
            "FREQ_Z(Hz)",
            "FFT_PEAK_X(Hz)",
            "FFT_PEAK_Y(Hz)",
            "FFT_PEAK_Z(Hz)",
        ]
        for uid in self.unit_ids:
            rows = snapshot.get(uid, [])
            out_path = os.path.join(event_dir, f"UID{uid:02X}_vibration.csv")
            with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(header)
                t_hist: List[float] = []
                dx_hist: List[float] = []
                dy_hist: List[float] = []
                dz_hist: List[float] = []
                for row in rows:
                    t_hist.append(row["time"])
                    dx_hist.append(row["disp"][0])
                    dy_hist.append(row["disp"][1])
                    dz_hist.append(row["disp"][2])
                    writer.writerow(
                        [
                            datetime.fromtimestamp(row["time"]).isoformat(timespec="milliseconds"),
                            *row["acc"],
                            *row["vel"],
                            *row["disp"],
                            *row["freq"],
                            self._fft_peak(dx_hist, t_hist),
                            self._fft_peak(dy_hist, t_hist),
                            self._fft_peak(dz_hist, t_hist),
                        ]
                    )
            paths.append(out_path)
            print(f"{self.log_prefix} CSV 저장 {out_path}")
        return paths

    def _build_measured(self, snapshot: Dict[int, List[dict]]):
        all_vel = [[], [], []]
        all_freq = [[], [], []]
        per_uid_vel = {}
        per_uid_freq = {}
        measured_per_uid = {}
        total_samples = 0
        for uid in self.unit_ids:
            rows = snapshot.get(uid, [])
            x_vals = [abs(float(row["vel"][0])) for row in rows]
            y_vals = [abs(float(row["vel"][1])) for row in rows]
            z_vals = [abs(float(row["vel"][2])) for row in rows]
            fx_vals = [float(row["freq"][0]) for row in rows]
            fy_vals = [float(row["freq"][1]) for row in rows]
            fz_vals = [float(row["freq"][2]) for row in rows]
            total_samples += min(len(x_vals), len(y_vals), len(z_vals))
            per_uid_vel[uid] = (x_vals, y_vals, z_vals)
            per_uid_freq[uid] = (fx_vals, fy_vals, fz_vals)
            all_vel[0].extend(x_vals)
            all_vel[1].extend(y_vals)
            all_vel[2].extend(z_vals)
            all_freq[0].extend(fx_vals)
            all_freq[1].extend(fy_vals)
            all_freq[2].extend(fz_vals)
            if x_vals:
                mag = np.sqrt(np.asarray(x_vals) ** 2 + np.asarray(y_vals) ** 2 + np.asarray(z_vals) ** 2)
                measured_per_uid[f"0x{uid:02X}"] = {
                    "velocity_magnitude_p99": float(np.percentile(mag, 99)),
                    "vel_x_p99": float(np.percentile(x_vals, 99)),
                    "vel_y_p99": float(np.percentile(y_vals, 99)),
                    "vel_z_p99": float(np.percentile(z_vals, 99)),
                    "freq_x_p99": float(np.percentile(fx_vals, 99)) if fx_vals else 0.0,
                    "freq_y_p99": float(np.percentile(fy_vals, 99)) if fy_vals else 0.0,
                    "freq_z_p99": float(np.percentile(fz_vals, 99)) if fz_vals else 0.0,
                    "freq_x_max": float(np.max(fx_vals)) if fx_vals else 0.0,
                    "freq_y_max": float(np.max(fy_vals)) if fy_vals else 0.0,
                    "freq_z_max": float(np.max(fz_vals)) if fz_vals else 0.0,
                    "freq_x_min": float(np.min(fx_vals)) if fx_vals else 0.0,
                    "freq_y_min": float(np.min(fy_vals)) if fy_vals else 0.0,
                    "freq_z_min": float(np.min(fz_vals)) if fz_vals else 0.0,
                }
            else:
                measured_per_uid[f"0x{uid:02X}"] = {}
        mag = [
            float(np.sqrt(all_vel[0][i] ** 2 + all_vel[1][i] ** 2 + all_vel[2][i] ** 2))
            for i in range(min(len(all_vel[0]), len(all_vel[1]), len(all_vel[2])))
        ]
        measured = {
            "velocity_magnitude_mean": float(np.mean(mag)) if mag else 0.0,
            "velocity_magnitude_p99": float(np.percentile(mag, 99)) if len(mag) >= 3 else 0.0,
            "vel_x_p99": float(np.percentile(all_vel[0], 99)) if all_vel[0] else 0.0,
            "vel_y_p99": float(np.percentile(all_vel[1], 99)) if all_vel[1] else 0.0,
            "vel_z_p99": float(np.percentile(all_vel[2], 99)) if all_vel[2] else 0.0,
            "freq_x_p99": float(np.percentile(all_freq[0], 99)) if all_freq[0] else 0.0,
            "freq_y_p99": float(np.percentile(all_freq[1], 99)) if all_freq[1] else 0.0,
            "freq_z_p99": float(np.percentile(all_freq[2], 99)) if all_freq[2] else 0.0,
            "freq_x_max": float(np.max(all_freq[0])) if all_freq[0] else 0.0,
            "freq_y_max": float(np.max(all_freq[1])) if all_freq[1] else 0.0,
            "freq_z_max": float(np.max(all_freq[2])) if all_freq[2] else 0.0,
            "freq_x_min": float(np.min(all_freq[0])) if all_freq[0] else 0.0,
            "freq_y_min": float(np.min(all_freq[1])) if all_freq[1] else 0.0,
            "freq_z_min": float(np.min(all_freq[2])) if all_freq[2] else 0.0,
        }
        return total_samples, measured, measured_per_uid, per_uid_vel, per_uid_freq

    def _infer_cnn(self, per_uid_vel, per_uid_freq):
        if not self.cnn_model_path:
            return None
        if not _TORCH_AVAILABLE:
            return {"enabled": False, "error": "torch_unavailable"}
        if not os.path.exists(self.cnn_model_path):
            return {"enabled": False, "error": "model_missing", "model_path": self.cnn_model_path}

        class _SmallVibrationCNN(nn.Module):
            def __init__(self, in_ch):
                super().__init__()
                self.net = nn.Sequential(
                    nn.Conv1d(in_ch, 32, kernel_size=7, padding=3),
                    nn.BatchNorm1d(32),
                    nn.ReLU(inplace=True),
                    nn.Conv1d(32, 64, kernel_size=5, padding=2),
                    nn.BatchNorm1d(64),
                    nn.ReLU(inplace=True),
                    nn.MaxPool1d(2),
                    nn.Conv1d(64, 128, kernel_size=5, padding=2),
                    nn.BatchNorm1d(128),
                    nn.ReLU(inplace=True),
                    nn.AdaptiveAvgPool1d(1),
                )
                self.head = nn.Linear(128, 1)

            def forward(self, x):
                x = self.net(x).squeeze(-1)
                return self.head(x).squeeze(-1)

        def _resample_1d(arr, seq_len):
            arr = np.asarray(arr, dtype=np.float32)
            if arr.size == 0:
                return np.zeros(seq_len, dtype=np.float32)
            if arr.size == seq_len:
                return arr
            x_old = np.linspace(0.0, 1.0, num=arr.size, endpoint=True)
            x_new = np.linspace(0.0, 1.0, num=seq_len, endpoint=True)
            return np.interp(x_new, x_old, arr).astype(np.float32)

        try:
            ckpt = torch.load(self.cnn_model_path, map_location="cpu", weights_only=False)
            uid_list = [str(u).upper().replace("0X", "") for u in ckpt.get("uid_list", [])]
            feature_cols = ckpt.get("feature_cols", [])
            seq_len = int(ckpt.get("seq_len", 256))
            threshold = float(self.cnn_threshold) if self.cnn_threshold is not None else float(ckpt.get("threshold", 0.5))
            mean = np.asarray(ckpt.get("mean", []), dtype=np.float32)
            std = np.asarray(ckpt.get("std", []), dtype=np.float32)
            std[std < 1e-6] = 1.0
            if not uid_list or not feature_cols:
                return {"enabled": False, "error": "invalid_checkpoint", "model_path": self.cnn_model_path}
            channels = []
            for uid_hex in uid_list:
                uid = int(uid_hex, 16)
                x_vals, y_vals, z_vals = per_uid_vel.get(uid, ([], [], []))
                fx_vals, fy_vals, fz_vals = per_uid_freq.get(uid, ([], [], []))
                feature_map = {
                    "VEL_X(mm/s)": np.asarray(x_vals, dtype=np.float32),
                    "VEL_Y(mm/s)": np.asarray(y_vals, dtype=np.float32),
                    "VEL_Z(mm/s)": np.asarray(z_vals, dtype=np.float32),
                    "FREQ_X(Hz)": np.asarray(fx_vals, dtype=np.float32),
                    "FREQ_Y(Hz)": np.asarray(fy_vals, dtype=np.float32),
                    "FREQ_Z(Hz)": np.asarray(fz_vals, dtype=np.float32),
                }
                for col in feature_cols:
                    channels.append(_resample_1d(feature_map.get(col, np.zeros(0, dtype=np.float32)), seq_len))
            x = np.stack(channels, axis=0).astype(np.float32)
            if mean.size == x.shape[0] and std.size == x.shape[0]:
                x = (x - mean[:, None]) / std[:, None]
            model = _SmallVibrationCNN(in_ch=x.shape[0])
            model.load_state_dict(ckpt["model_state_dict"])
            model.eval()
            with torch.no_grad():
                xb = torch.from_numpy(x).unsqueeze(0)
                prob = torch.sigmoid(model(xb)).item()
            pred = "ABNORMAL" if prob >= threshold else "NORMAL"
            return {
                "enabled": True,
                "model_path": self.cnn_model_path,
                "threshold": threshold,
                "prob_abnormal": float(prob),
                "pred": pred,
            }
        except Exception as exc:
            return {"enabled": False, "error": str(exc), "model_path": self.cnn_model_path}

    def _apply_simple_rules(self, baseline: dict, measured: dict, measured_per_uid: dict):
        thresholds = baseline.get("thresholds", {}) if isinstance(baseline, dict) else {}
        alerts = []
        culprit_details = []
        metric_defs = [
            ("velocity_magnitude_3sigma", "velocity_magnitude_p99", "속도 크기(3σ)", ">"),
            ("vel_x_3sigma", "vel_x_p99", "X축 속도(3σ)", ">"),
            ("vel_y_3sigma", "vel_y_p99", "Y축 속도(3σ)", ">"),
            ("vel_z_3sigma", "vel_z_p99", "Z축 속도(3σ)", ">"),
            ("velocity_magnitude_low", "velocity_magnitude_p99", "속도 크기(low)", "<"),
            ("vel_x_low", "vel_x_p99", "X축 속도(low)", "<"),
            ("vel_y_low", "vel_y_p99", "Y축 속도(low)", "<"),
            ("vel_z_low", "vel_z_p99", "Z축 속도(low)", "<"),
            ("freq_x_high", "freq_x_p99", "FREQ_X high", ">"),
            ("freq_y_high", "freq_y_p99", "FREQ_Y high", ">"),
            ("freq_z_high", "freq_z_p99", "FREQ_Z high", ">"),
            ("freq_x_single_uid_high", "freq_x_p99", "FREQ_X single high", ">"),
            ("freq_y_single_uid_high", "freq_y_p99", "FREQ_Y single high", ">"),
            ("freq_z_single_uid_high", "freq_z_p99", "FREQ_Z single high", ">"),
            ("freq_x_high_burst", "freq_x_max", "FREQ_X high burst", ">"),
            ("freq_y_high_burst", "freq_y_max", "FREQ_Y high burst", ">"),
            ("freq_z_high_burst", "freq_z_max", "FREQ_Z high burst", ">"),
            ("freq_x_low", "freq_x_min", "FREQ_X low", "<"),
            ("freq_y_low", "freq_y_min", "FREQ_Y low", "<"),
            ("freq_z_low", "freq_z_min", "FREQ_Z low", "<"),
        ]
        for threshold_key, measured_key, label, operator in metric_defs:
            limit = thresholds.get(threshold_key)
            if limit is None:
                continue
            limit_f = float(limit)
            if threshold_key.endswith("_high_burst"):
                base_key = threshold_key.replace("_high_burst", "_high")
                base_limit = thresholds.get(base_key)
                if base_limit is None:
                    continue
                limit_f = float(base_limit) * 1.8
            value = float(measured.get(measured_key, 0.0))
            hit = value > limit_f if operator == ">" else value < limit_f
            if not hit:
                continue
            alerts.append(f"{label}: {value:.1f} {operator} {limit_f:.1f}")
            culprit_uid = None
            culprit_val = float("-inf") if operator == ">" else float("inf")
            for uid_key, uid_measured in measured_per_uid.items():
                uid_val = float(uid_measured.get(measured_key, 0.0))
                if operator == ">" and uid_val > culprit_val:
                    culprit_uid = uid_key
                    culprit_val = uid_val
                if operator == "<" and uid_val < culprit_val:
                    culprit_uid = uid_key
                    culprit_val = uid_val
            if culprit_uid is not None:
                culprit_details.append(
                    {
                        "metric": threshold_key,
                        "label": label,
                        "threshold": limit_f,
                        "value": float(culprit_val),
                        "culprit_uid": culprit_uid,
                        "operator": operator,
                    }
                )
        return alerts, culprit_details

    def _save_summary_plot(self, snapshot: Dict[int, List[dict]], result: dict, out_path: str) -> str:
        n_uid = max(1, len(self.unit_ids))
        fig, axes = plt.subplots(n_uid, 2, figsize=(14, max(4, 3 * n_uid)), squeeze=False)
        fig.suptitle("Vibration Event Summary", fontsize=13)
        for row_idx, uid in enumerate(self.unit_ids):
            rows = snapshot.get(uid, [])
            if rows:
                t = np.asarray([r["time"] for r in rows], dtype=float)
                t = t - t[0]
            else:
                t = np.asarray([0.0], dtype=float)
            ax_vel = axes[row_idx][0]
            ax_freq = axes[row_idx][1]
            ax_vel.set_title(f"UID 0x{uid:02X} Velocity")
            ax_freq.set_title(f"UID 0x{uid:02X} Frequency")
            ax_vel.grid(True, alpha=0.3)
            ax_freq.grid(True, alpha=0.3)
            for idx, label in enumerate(("X", "Y", "Z")):
                vel_vals = np.asarray([r["vel"][idx] for r in rows], dtype=float) if rows else np.asarray([])
                freq_vals = np.asarray([r["freq"][idx] for r in rows], dtype=float) if rows else np.asarray([])
                if vel_vals.size:
                    ax_vel.plot(t[: len(vel_vals)], vel_vals, label=label, linewidth=1.0)
                if freq_vals.size:
                    ax_freq.plot(t[: len(freq_vals)], freq_vals, label=label, linewidth=1.0)
            ax_vel.legend(loc="upper right", fontsize=8)
            ax_freq.legend(loc="upper right", fontsize=8)
        footer = f"status={result.get('status', 'UNKNOWN')} | source={result.get('decision_source', 'unknown')}"
        fig.text(0.01, 0.01, footer, fontsize=9, ha="left", va="bottom")
        fig.tight_layout(rect=[0, 0.03, 1, 0.95])
        fig.savefig(out_path, dpi=140)
        plt.close(fig)
        return out_path

    def _analyze_snapshot(self, snapshot: Dict[int, List[dict]], *, event_ts: float, result_path: Optional[str], event_tag: str) -> Dict:
        timestamp = datetime.fromtimestamp(event_ts)
        event_dir = os.path.join(self.event_root_dir, f"{timestamp.strftime('%Y%m%d_%H%M%S')}_{event_tag}")
        os.makedirs(event_dir, exist_ok=True)
        self._save_snapshot_csvs(snapshot, event_dir)
        total_samples, measured, measured_per_uid, per_uid_vel, per_uid_freq = self._build_measured(snapshot)
        baseline = self._load_baseline()
        alerts, culprit_details = self._apply_simple_rules(baseline, measured, measured_per_uid)
        status = "ABNORMAL" if alerts else "NORMAL"
        decision_source = "rule"
        cnn_result = self._infer_cnn(per_uid_vel, per_uid_freq)
        if isinstance(cnn_result, dict) and cnn_result.get("enabled"):
            print(
                f"{self.log_prefix}[CNN] prob={cnn_result.get('prob_abnormal', 0.0):.3f} "
                f"thr={cnn_result.get('threshold', 0.5):.2f} pred={cnn_result.get('pred', 'UNKNOWN')}"
            )
            if self.use_cnn_main:
                status = str(cnn_result.get("pred", status)).upper()
                decision_source = "cnn_main"
            else:
                decision_source = "rule_with_cnn_observer"
        elif self.use_cnn_main:
            decision_source = "rule_fallback_cnn_error"
        result = {
            "status": status,
            "decision_source": decision_source,
            "timestamp": datetime.now().isoformat(),
            "event_time": timestamp.isoformat(),
            "total_samples": total_samples,
            "unit_ids": [f"0x{u:02X}" for u in self.unit_ids],
            "measured": measured,
            "measured_per_uid": measured_per_uid,
            "alerts": alerts,
            "culprit_details": culprit_details,
            "event_dir": event_dir,
        }
        if cnn_result is not None:
            result["cnn"] = cnn_result
        plot_path = os.path.join(event_dir, "summary.png")
        result["summary_plot"] = self._save_summary_plot(snapshot, result, plot_path)
        out_path = result_path or os.path.join(event_dir, "result.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"{self.log_prefix} 결과 저장 {out_path}")
        if alerts:
            print(f"{self.log_prefix} alerts={len(alerts)} first={alerts[0]}")
        return result
