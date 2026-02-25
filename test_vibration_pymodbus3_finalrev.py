#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WitMotion WT-VB02-485 멀티센서 수집 + 그래프 + CSV (Ubuntu 22.04 / Jetson Orin Nano)
- pymodbus 3.x 기준 (RTU)
- "최종수정본" 로직(리부트 오탐 방지 + FC3 실패시 FC4 fallback)을 반영한 리눅스 변환판

필요:
  pip3 install pymodbus==3.6.9 pyserial matplotlib numpy
"""

import os, time, threading, csv, json, argparse
from datetime import datetime
from collections import deque

import numpy as np
from pymodbus.client import ModbusSerialClient  # pymodbus 3.x
from pymodbus.exceptions import ModbusIOException
from serial import SerialException


# =========================
# 인수 파싱 (matplotlib 임포트 전에 먼저)
# =========================
parser = argparse.ArgumentParser(description="WitMotion 진동센서 수집기")
parser.add_argument("--headless", action="store_true",
                    help="GUI 없이 실행 (서버/systemctl 환경)")
parser.add_argument("--check", action="store_true",
                    help="측정 후 베이스라인과 비교하여 result JSON 저장")
parser.add_argument("--duration", type=float, default=10.0,
                    help="headless 모드 수집 시간(초), 기본 10")
parser.add_argument("--baseline", type=str, default=None,
                    help="베이스라인 JSON 파일 경로")
parser.add_argument("--result", type=str, default=None,
                    help="결과 JSON 저장 경로 (기본: 실행 디렉토리/vibration_result.json)")
parser.add_argument("--summary-plot", type=str, default=None,
                    help="요약 그래프 PNG 저장 경로 (기본: ~/data/vibration_data/<timestamp>_summary.png)")
args = parser.parse_args()

import matplotlib
if args.headless:
    matplotlib.use('Agg')  # 디스플레이 없이 렌더링
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# ---------- 한글 폰트 ----------
try:
    matplotlib.rc('font', family='NanumGothic')
    matplotlib.rcParams['axes.unicode_minus'] = False
except Exception:
    pass


# =========================
# 사용자 설정
# =========================
DEFAULT_VIB_PORT_BY_ID = "/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A9NF7ROC-if00-port0"
PORT = os.getenv(
    "VIB_PORT",
    DEFAULT_VIB_PORT_BY_ID if os.path.exists(DEFAULT_VIB_PORT_BY_ID) else "/dev/ttyUSB0",
)
BAUD = int(os.getenv("VIB_BAUD", "115200"))

def _parse_unit_ids(env_val: str):
    if not env_val:
        return None
    ids = []
    for part in env_val.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part, 0))  # supports 0x.. or decimal
        except ValueError:
            pass
    return ids or None

UNIT_IDS = _parse_unit_ids(os.getenv("VIB_UNIT_IDS")) or [0x53, 0x54]  # 0x55 Y축 고장으로 제외
PARITY = 'N'
STOPBITS = 1
BYTESIZE = 8
TIMEOUT_S = 0.15

# 폴링/버퍼
POLL_HZ_TOTAL = 45             # 총 루프 속도(초당 45회 → 유닛당 약 15Hz)
RETRY_READ = 2
RECONNECT_TIMEOUT = 3.0
WINDOW_SEC = 5.0
PLOT_INTERVAL_MS = 100

SAMPLE_RATE_HINT_PER_UNIT = POLL_HZ_TOTAL / max(1, len(UNIT_IDS))
MAXLEN_MIN = 50
maxlen = max(MAXLEN_MIN, int(WINDOW_SEC * SAMPLE_RATE_HINT_PER_UNIT))

# (최종수정본 로직) 리부트 오탐 방지 파라미터
WARMUP_SEC = 10.0              # 시작 후 N초 동안은 reboot 금지
ZERO_EPS = 0.02                # 0 근처를 0으로 볼 범위(필요하면 0.01~0.1로)
MISSING_PERSIST_SEC = 1.0      # 누락이 연속 N초 이상일 때만 reboot
REBOOT_SLEEP_SEC = 1.5         # reboot 후 대기
REBOOT_COOLDOWN_SEC = 5.0      # reboot 쿨다운(연타 방지)

# 로그 토글
PRINT_EVENT_LOG = True
DEBUG_READ_LOG = False
DEBUG_REG_PREVIEW = False


# =========================
# 레지스터 맵 (WT-VB02-485)
# =========================
REG_AX = 0x34; REG_AY = 0x35; REG_AZ = 0x36
REG_GX = 0x37; REG_GY = 0x38; REG_GZ = 0x39
REG_VX = 0x3A; REG_VY = 0x3B; REG_VZ = 0x3C
REG_DX = 0x41; REG_DY = 0x42; REG_DZ = 0x43
REG_HX = 0x44; REG_HY = 0x45; REG_HZ = 0x46

REG_START = REG_AX
REG_COUNT = (REG_HZ - REG_AX + 1)   # 19

REG_UNLOCK_ADDR = 0x0069
REG_SAVE = 0x00                      # 0x00FF → 재시작 (기기 펌웨어/모델에 따라 다를 수 있음)

# 스케일
ACC_SCALE = 16.0 / 32768.0          # g
FREQ_DIVISOR = 10.0                 # Hz


# =========================
# 저장 폴더
# =========================
RUN_TS = datetime.now().strftime("%Y%m%d_%H%M%S")
home_dir = os.path.expanduser("~")
save_dir = os.path.join(home_dir, "data", "vibration_data")
os.makedirs(save_dir, exist_ok=True)
print(f"[저장 폴더] {save_dir}")


# =========================
# CSV 핸들(센서별)
# =========================
def make_csv(uid: int):
    path = os.path.join(save_dir, f"{RUN_TS}_UID{uid:02X}_vibration.csv")
    f = open(path, "w", newline="", encoding="utf-8-sig")
    w = csv.writer(f)
    w.writerow([
        "time",
        "ACC_X(g)","ACC_Y(g)","ACC_Z(g)",
        "VEL_X(mm/s)","VEL_Y(mm/s)","VEL_Z(mm/s)",
        "DISP_X(um)","DISP_Y(um)","DISP_Z(um)",
        "FREQ_X(Hz)","FREQ_Y(Hz)","FREQ_Z(Hz)",
        "FFT_PEAK_X(Hz)","FFT_PEAK_Y(Hz)","FFT_PEAK_Z(Hz)"
    ])
    f.flush()
    print(f"[UID 0x{uid:02X}] CSV → {path}")
    return f, w

csv_files = {}
csv_writers = {}
for uid in UNIT_IDS:
    f, w = make_csv(uid)
    csv_files[uid] = f
    csv_writers[uid] = w


# =========================
# 버퍼(센서별)
# =========================
# headless check 모드에서는 전체 수집 샘플을 쌓기 위해 maxlen 무제한
_buf_maxlen = None if (args.headless and args.check) else maxlen

buf_time = {uid: deque(maxlen=_buf_maxlen) for uid in UNIT_IDS}
buf_acc  = {uid: [deque(maxlen=_buf_maxlen) for _ in range(3)] for uid in UNIT_IDS}
buf_vel  = {uid: [deque(maxlen=_buf_maxlen) for _ in range(3)] for uid in UNIT_IDS}
buf_disp = {uid: [deque(maxlen=_buf_maxlen) for _ in range(3)] for uid in UNIT_IDS}
buf_freq = {uid: [deque(maxlen=_buf_maxlen) for _ in range(3)] for uid in UNIT_IDS}

last_ok = {uid: time.time() for uid in UNIT_IDS}
missing_since = {uid: None for uid in UNIT_IDS}
last_reboot = {uid: 0.0 for uid in UNIT_IDS}
PROGRAM_START_TS = time.time()


# =========================
# Modbus (pymodbus 3.x)
# =========================
def make_client():
    return ModbusSerialClient(
        port=PORT,
        baudrate=BAUD,
        bytesize=BYTESIZE,
        parity=PARITY,
        stopbits=STOPBITS,
        timeout=TIMEOUT_S
    )

print("[초기화] pymodbus 클라이언트 생성")
client = make_client()

print(f"[연결 시도] {PORT} @ {BAUD}bps")
if not client.connect():
    print("[오류] 연결 실패")
    raise SystemExit(1)
print("[연결 성공]")


# ---- pymodbus 2.x/3.x 호환 래퍼 (Ubuntu에서 튼튼하게) ----
def _modbus_call(func, **kwargs):
    """
    pymodbus 버전차로 slave/unit/device_id 키가 달라서 자동으로 맞춤.
    (지금 스크립트는 3.x를 전제로 하지만, 환경 섞였을 때도 덜 터지게 해둠)
    """
    if 'slave' in kwargs:
        uid = kwargs.pop('slave')
        for key in ('slave', 'unit', 'device_id'):
            try:
                return func(**kwargs, **{key: uid})
            except TypeError:
                continue
        # 최후의 수단
        return func(**kwargs)
    return func(**kwargs)

def _ok(rr):
    return (rr is not None) and hasattr(rr, "isError") and (not rr.isError()) and hasattr(rr, "registers")


# =========================
# reboot 시퀀스
# =========================
def unlock_sensor(uid: int):
    try:
        _modbus_call(client.write_register, address=REG_UNLOCK_ADDR, value=0xB588, slave=uid)
    except Exception:
        pass

def restart_sensor(uid: int):
    try:
        unlock_sensor(uid)
        time.sleep(0.05)
        _modbus_call(client.write_register, address=REG_SAVE, value=0x00FF, slave=uid)
    except Exception as e:
        if PRINT_EVENT_LOG:
            print(f"[UID 0x{uid:02X}] 재시작 오류: {e}")


# =========================
# 파싱/유틸
# =========================
def s16(v: int) -> int:
    return v - 0x10000 if v >= 0x8000 else v

def parse_map(regs):
    # regs: 0x34~0x46 (19개)
    AX, AY, AZ = [s16(regs[i]) for i in (0, 1, 2)]
    VX, VY, VZ = [s16(regs[i]) for i in (6, 7, 8)]
    DX, DY, DZ = [s16(regs[i]) for i in (13, 14, 15)]
    HX, HY, HZ = [s16(regs[i]) for i in (16, 17, 18)]

    acc = (AX * ACC_SCALE, AY * ACC_SCALE, AZ * ACC_SCALE)
    vel = (float(VX), float(VY), float(VZ))     # mm/s
    disp = (float(DX), float(DY), float(DZ))    # um
    freq = (HX / FREQ_DIVISOR, HY / FREQ_DIVISOR, HZ / FREQ_DIVISOR)
    return acc, vel, disp, freq

def axis_zero_mask_one_axis(acc, vel, disp, eps=0.0):
    """
    축별로 (acc, vel, disp)가 모두 0이면 True.
    return: [x_zero, y_zero, z_zero]
    """
    return [
        (abs(acc[i]) <= eps) and (abs(vel[i]) <= eps) and (abs(disp[i]) <= eps)
        for i in range(3)
    ]

def axis_alive(acc, vel, disp, i, eps=0.0):
    """해당 축 i가 '살아있다' = acc/vel/disp 중 하나라도 0이 아님"""
    return (abs(acc[i]) > eps) or (abs(vel[i]) > eps) or (abs(disp[i]) > eps)

def mask_to_axes(mask):
    axes = []
    if mask[0]: axes.append("X")
    if mask[1]: axes.append("Y")
    if mask[2]: axes.append("Z")
    return ",".join(axes) if axes else "-"

def fft_peak(series, tbuf):
    """스펙트럼 피크(Hz): 동적 fs 추정 사용"""
    if len(series) < 16 or len(tbuf) < 2:
        return 0.0
    y = np.array(series, dtype=float)
    dt = (tbuf[-1] - tbuf[0]) / max(1, (len(tbuf) - 1))
    fs = 1.0 / dt if dt > 0 else SAMPLE_RATE_HINT_PER_UNIT

    y = y - np.mean(y)
    Y = np.fft.rfft(np.hanning(len(y)) * y)
    f = np.fft.rfftfreq(len(y), d=1.0 / fs)
    m = np.abs(Y)
    if len(m) <= 1:
        return 0.0
    return float(f[np.argmax(m[1:]) + 1])


# =========================
# 읽기(재시도 + FC4 fallback)
# =========================
def read_block_retry(uid: int):
    last_rr = None
    for attempt in range(1, RETRY_READ + 1):
        rr = _modbus_call(client.read_holding_registers, address=REG_START, count=REG_COUNT, slave=uid)
        last_rr = rr
        if _ok(rr):
            if DEBUG_READ_LOG:
                if DEBUG_REG_PREVIEW:
                    print(f"[UID 0x{uid:02X}] HOLD OK regs[0:6]={rr.registers[:6]}")
                else:
                    print(f"[UID 0x{uid:02X}] HOLD OK")
            return rr.registers

        if DEBUG_READ_LOG:
            print(f"[UID 0x{uid:02X}] HOLD fail (attempt {attempt}) -> {rr}")
        time.sleep(0.01)

        rr2 = _modbus_call(client.read_input_registers, address=REG_START, count=REG_COUNT, slave=uid)
        last_rr = rr2
        if _ok(rr2):
            if DEBUG_READ_LOG:
                if DEBUG_REG_PREVIEW:
                    print(f"[UID 0x{uid:02X}] INPT OK regs[0:6]={rr2.registers[:6]}")
                else:
                    print(f"[UID 0x{uid:02X}] INPT OK")
            return rr2.registers

        if DEBUG_READ_LOG:
            print(f"[UID 0x{uid:02X}] INPT fail (attempt {attempt}) -> {rr2}")
        time.sleep(0.02)

    raise ModbusIOException(f"[UID 0x{uid:02X}] read 실패 last={last_rr}")


# =========================
# 수집 스레드
# =========================
stop_event = threading.Event()

def collector_loop():
    poll_dt = 1.0 / max(1.0, POLL_HZ_TOTAL)

    while not stop_event.is_set():
        warmup = (time.time() - PROGRAM_START_TS) < WARMUP_SEC
        t_cycle = time.time()

        try:
            if not getattr(client, "connected", False):
                if not client.connect():
                    time.sleep(0.2)
                    continue

            for uid in UNIT_IDS:
                had_error = False
                try:
                    regs = read_block_retry(uid)
                    acc, vel, disp, freq = parse_map(regs)

                    # ✅ "진짜 한 축만 죽음" 판단
                    zmask = axis_zero_mask_one_axis(acc, vel, disp, eps=ZERO_EPS)
                    dead_count = sum(1 for b in zmask if b)

                    alive_axes = [
                        i for i in range(3)
                        if (not zmask[i]) and axis_alive(acc, vel, disp, i, eps=ZERO_EPS)
                    ]
                    alive_count = len(alive_axes)

                    real_missing = (dead_count == 1) and (alive_count == 2)

                    now = time.time()
                    cooldown = (now - last_reboot[uid]) < REBOOT_COOLDOWN_SEC

                    if real_missing and (not cooldown):
                        if warmup:
                            missing_since[uid] = None
                        else:
                            if missing_since[uid] is None:
                                missing_since[uid] = now

                            if (now - missing_since[uid]) >= MISSING_PERSIST_SEC:
                                if PRINT_EVENT_LOG:
                                    print(f"[UID 0x{uid:02X}] 한 축 누락({mask_to_axes(zmask)}) "
                                          f"{MISSING_PERSIST_SEC}s 지속 → reboot")
                                restart_sensor(uid)
                                last_reboot[uid] = time.time()
                                missing_since[uid] = None

                                time.sleep(REBOOT_SLEEP_SEC)
                                try:
                                    client.close()
                                except Exception:
                                    pass
                                time.sleep(0.2)
                                client.connect()

                                last_ok[uid] = time.time()
                                continue
                    else:
                        # 누락 아니면 타이머 리셋
                        missing_since[uid] = None

                    # 정상 저장/버퍼 업데이트
                    t = time.time()
                    buf_time[uid].append(t)
                    for i in range(3):
                        buf_acc[uid][i].append(acc[i])
                        buf_vel[uid][i].append(vel[i])
                        buf_disp[uid][i].append(disp[i])
                        buf_freq[uid][i].append(freq[i])

                    fx = fft_peak(buf_disp[uid][0], buf_time[uid])
                    fy = fft_peak(buf_disp[uid][1], buf_time[uid])
                    fz = fft_peak(buf_disp[uid][2], buf_time[uid])

                    row = [
                        datetime.fromtimestamp(t).isoformat(timespec="milliseconds"),
                        *acc, *vel, *disp, *freq, fx, fy, fz
                    ]
                    try:
                        csv_writers[uid].writerow(row)
                        csv_files[uid].flush()
                    except Exception as e:
                        if PRINT_EVENT_LOG:
                            print(f"[UID 0x{uid:02X}] CSV 오류: {e}")

                    last_ok[uid] = t

                except (ModbusIOException, SerialException, OSError) as e:
                    if PRINT_EVENT_LOG:
                        print(f"[UID 0x{uid:02X}] 읽기 오류: {e} → 재연결")
                    missing_since[uid] = None
                    had_error = True
                    try:
                        client.close()
                    except Exception:
                        pass
                    time.sleep(0.2)
                    client.connect()

                except Exception as e:
                    if PRINT_EVENT_LOG:
                        print(f"[UID 0x{uid:02X}] 예외: {e}")
                    had_error = True

                # uid별 타임아웃 → reboot (워밍업 동안 스킵)
                if (not had_error) and (time.time() - last_ok[uid] > RECONNECT_TIMEOUT):
                    if warmup:
                        last_ok[uid] = time.time()
                    else:
                        if PRINT_EVENT_LOG:
                            print(f"[UID 0x{uid:02X}] 타임아웃 → reboot")
                        restart_sensor(uid)
                        last_reboot[uid] = time.time()
                        missing_since[uid] = None

                        time.sleep(REBOOT_SLEEP_SEC)
                        try:
                            client.close()
                        except Exception:
                            pass
                        time.sleep(0.2)
                        client.connect()

                        last_ok[uid] = time.time()

        except Exception as e:
            if PRINT_EVENT_LOG:
                print(f"[루프 예외] {e}")

        remain = poll_dt - (time.time() - t_cycle)
        if remain > 0:
            time.sleep(remain)

print("[시작] 수집 스레드 시작")
collector_thread = threading.Thread(target=collector_loop, daemon=True)
collector_thread.start()


# =========================
# 베이스라인 비교 및 결과 저장
# =========================
def _check_against_baseline(baseline: dict) -> dict:
    """수집된 버퍼를 베이스라인 threshold와 비교하여 결과 dict 반환"""
    thresholds_default = baseline.get("thresholds", {})
    thresholds = dict(thresholds_default)
    threshold_profiles = baseline.get("threshold_profiles", [])
    active_threshold_profile = "default"
    min_exceed_duration_sec = float(thresholds.get("min_exceed_duration_sec", 0.5))
    sample_rate = max(1.0, float(SAMPLE_RATE_HINT_PER_UNIT))

    def _longest_run_sec(values, threshold, op):
        run = 0
        best = 0
        for v in values:
            ok = (v > threshold) if op == ">" else (v < threshold)
            if ok:
                run += 1
                if run > best:
                    best = run
            else:
                run = 0
        return best / sample_rate
    single_uid_ignore_raw = thresholds.get("single_uid_ignore_uids", [])
    single_uid_ignore = set()
    if isinstance(single_uid_ignore_raw, list):
        for x in single_uid_ignore_raw:
            try:
                s = str(x).strip().upper()
                if s.startswith("0X"):
                    single_uid_ignore.add(s)
                elif s:
                    single_uid_ignore.add(f"0X{int(s):02X}")
            except Exception:
                continue

    def _normalize_uid_set(raw_uids, default_uids):
        if not isinstance(raw_uids, list) or not raw_uids:
            return set(default_uids)
        parsed = set()
        for x in raw_uids:
            try:
                s = str(x).strip()
                if not s:
                    continue
                parsed.add(int(s, 0))
            except Exception:
                continue
        return parsed or set(default_uids)

    velocity_include_uids = _normalize_uid_set(
        thresholds.get("velocity_include_uids", []), UNIT_IDS
    )
    velocity_ignore_uid_axes_raw = thresholds.get("velocity_ignore_uid_axes", {})
    velocity_ignore_uid_axes = {}
    if isinstance(velocity_ignore_uid_axes_raw, dict):
        for uid_key, axes in velocity_ignore_uid_axes_raw.items():
            try:
                uid_int = int(str(uid_key).strip(), 0)
            except Exception:
                continue
            axes_set = set()
            if isinstance(axes, list):
                for a in axes:
                    a_norm = str(a).strip().lower()
                    if a_norm in ("x", "y", "z"):
                        axes_set.add(a_norm)
            velocity_ignore_uid_axes[uid_int] = axes_set
    velocity_combo_min_triggers = int(thresholds.get("velocity_combo_min_triggers", 1))
    velocity_combo_min_triggers = max(1, velocity_combo_min_triggers)
    freq_checks_enabled = bool(thresholds.get("freq_checks_enabled", True))
    # freq high 판정:
    # - p99는 단일 센서 노이즈 오탐 방지를 위해 2개 이상 UID 동시 초과일 때만 경보
    # - burst(max)는 짧은 충격(툭툭) 복원을 위해 유지하되 비율을 높여 오탐 완화
    freq_high_min_uid_count = 2
    freq_high_burst_ratio = 1.8
    alerts = []
    triggered_metrics = {}
    metric_operators = {}
    total_samples = 0

    # 전체 센서 velocity/frequency 합산 + 센서별 저장
    all_vel = [[], [], []]
    all_freq = [[], [], []]
    per_uid_vel = {}
    per_uid_freq = {}
    for uid in UNIT_IDS:
        x_vals = list(buf_vel[uid][0])
        y_vals = list(buf_vel[uid][1])
        z_vals = list(buf_vel[uid][2])
        fx_vals = list(buf_freq[uid][0])
        fy_vals = list(buf_freq[uid][1])
        fz_vals = list(buf_freq[uid][2])
        n = min(len(x_vals), len(y_vals), len(z_vals))
        total_samples += n
        x_vals = x_vals[:n]
        y_vals = y_vals[:n]
        z_vals = z_vals[:n]
        fx_vals = fx_vals[:n]
        fy_vals = fy_vals[:n]
        fz_vals = fz_vals[:n]
        per_uid_vel[uid] = (x_vals, y_vals, z_vals)
        per_uid_freq[uid] = (fx_vals, fy_vals, fz_vals)
        all_vel[0].extend(x_vals)
        all_vel[1].extend(y_vals)
        all_vel[2].extend(z_vals)
        all_freq[0].extend(fx_vals)
        all_freq[1].extend(fy_vals)
        all_freq[2].extend(fz_vals)

    if total_samples == 0:
        return {"status": "ERROR", "reason": "수집된 샘플 없음", "timestamp": datetime.now().isoformat()}

    # velocity magnitude 계산
    mag = [
        np.sqrt(all_vel[0][i]**2 + all_vel[1][i]**2 + all_vel[2][i]**2)
        for i in range(len(all_vel[0]))
    ]

    measured = {
        "velocity_magnitude_mean": float(np.mean(mag)),
        "velocity_magnitude_p99": float(np.percentile(mag, 99)) if len(mag) >= 10 else 0.0,
        "vel_x_p99": float(np.percentile(np.abs(all_vel[0]), 99)) if all_vel[0] else 0.0,
        "vel_y_p99": float(np.percentile(np.abs(all_vel[1]), 99)) if all_vel[1] else 0.0,
        "vel_z_p99": float(np.percentile(np.abs(all_vel[2]), 99)) if all_vel[2] else 0.0,
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

    # Profile-based threshold selection (optional)
    if isinstance(threshold_profiles, list):
        fx_p99 = float(measured.get("freq_x_p99", 0.0))
        for profile in threshold_profiles:
            if not isinstance(profile, dict):
                continue
            selector = profile.get("selector", {})
            if not isinstance(selector, dict):
                continue
            min_v = selector.get("freq_x_p99_min", None)
            max_v = selector.get("freq_x_p99_max", None)
            matched = True
            if min_v is not None and fx_p99 < float(min_v):
                matched = False
            if max_v is not None and fx_p99 > float(max_v):
                matched = False
            if not matched:
                continue
            prof_th = profile.get("thresholds", {})
            if isinstance(prof_th, dict):
                merged = dict(thresholds_default)
                merged.update(prof_th)
                thresholds = merged
                active_threshold_profile = str(profile.get("name", "profile"))
                print(f"[진동 체크] threshold profile={active_threshold_profile} (freq_x_p99={fx_p99:.1f})")
            break
    measured_per_uid = {}
    for uid in UNIT_IDS:
        x_vals, y_vals, z_vals = per_uid_vel.get(uid, ([], [], []))
        if not x_vals:
            measured_per_uid[f"0x{uid:02X}"] = {
                "velocity_magnitude_p99": 0.0,
                "vel_x_p99": 0.0,
                "vel_y_p99": 0.0,
                "vel_z_p99": 0.0,
            }
            continue
        x_arr = np.array(x_vals)
        y_arr = np.array(y_vals)
        z_arr = np.array(z_vals)
        mag_uid = np.sqrt(x_arr**2 + y_arr**2 + z_arr**2)
        measured_per_uid[f"0x{uid:02X}"] = {
            "velocity_magnitude_p99": float(np.percentile(np.abs(mag_uid), 99)),
            "vel_x_p99": float(np.percentile(np.abs(x_arr), 99)),
            "vel_y_p99": float(np.percentile(np.abs(y_arr), 99)),
            "vel_z_p99": float(np.percentile(np.abs(z_arr), 99)),
        }
        fx_vals, fy_vals, fz_vals = per_uid_freq.get(uid, ([], [], []))
        if fx_vals:
            measured_per_uid[f"0x{uid:02X}"].update(
                {
                    "freq_x_p99": float(np.percentile(fx_vals, 99)),
                    "freq_y_p99": float(np.percentile(fy_vals, 99)),
                    "freq_z_p99": float(np.percentile(fz_vals, 99)),
                    "freq_x_max": float(np.max(fx_vals)),
                    "freq_y_max": float(np.max(fy_vals)),
                    "freq_z_max": float(np.max(fz_vals)),
                    "freq_x_min": float(np.min(fx_vals)),
                    "freq_y_min": float(np.min(fy_vals)),
                    "freq_z_min": float(np.min(fz_vals)),
                }
            )
        else:
            measured_per_uid[f"0x{uid:02X}"].update(
                {
                    "freq_x_p99": 0.0,
                    "freq_y_p99": 0.0,
                    "freq_z_p99": 0.0,
                    "freq_x_max": 0.0,
                    "freq_y_max": 0.0,
                    "freq_z_max": 0.0,
                    "freq_x_min": 0.0,
                    "freq_y_min": 0.0,
                    "freq_z_min": 0.0,
                }
            )

    def _uid_axis_enabled(uid, axis_name):
        if uid not in velocity_include_uids:
            return False
        ignored = velocity_ignore_uid_axes.get(uid, set())
        return axis_name not in ignored

    def _series_for_metric(uid, metric_key, x_vals, y_vals, z_vals):
        if metric_key == "vel_x_3sigma":
            return [abs(v) for v in x_vals] if _uid_axis_enabled(uid, "x") else []
        if metric_key == "vel_y_3sigma":
            return [abs(v) for v in y_vals] if _uid_axis_enabled(uid, "y") else []
        if metric_key == "vel_z_3sigma":
            return [abs(v) for v in z_vals] if _uid_axis_enabled(uid, "z") else []
        n = min(len(x_vals), len(y_vals), len(z_vals))
        if n <= 0:
            return []
        use_x = _uid_axis_enabled(uid, "x")
        use_y = _uid_axis_enabled(uid, "y")
        use_z = _uid_axis_enabled(uid, "z")
        if not (use_x or use_y or use_z):
            return []
        out = []
        for i in range(n):
            vx = x_vals[i] if use_x else 0.0
            vy = y_vals[i] if use_y else 0.0
            vz = z_vals[i] if use_z else 0.0
            out.append(float(np.sqrt(vx * vx + vy * vy + vz * vz)))
        return out

    # UID/축 필터 적용된 velocity 요약값
    vel_selected = {"x": [], "y": [], "z": [], "mag": []}
    for uid in UNIT_IDS:
        x_vals, y_vals, z_vals = per_uid_vel.get(uid, ([], [], []))
        if not x_vals:
            continue
        if _uid_axis_enabled(uid, "x"):
            vel_selected["x"].extend([abs(v) for v in x_vals])
        if _uid_axis_enabled(uid, "y"):
            vel_selected["y"].extend([abs(v) for v in y_vals])
        if _uid_axis_enabled(uid, "z"):
            vel_selected["z"].extend([abs(v) for v in z_vals])
        vel_selected["mag"].extend(_series_for_metric(uid, "velocity_magnitude_3sigma", x_vals, y_vals, z_vals))

    velocity_measured = {
        "velocity_magnitude_p99": float(np.percentile(vel_selected["mag"], 99)) if vel_selected["mag"] else 0.0,
        "vel_x_p99": float(np.percentile(vel_selected["x"], 99)) if vel_selected["x"] else 0.0,
        "vel_y_p99": float(np.percentile(vel_selected["y"], 99)) if vel_selected["y"] else 0.0,
        "vel_z_p99": float(np.percentile(vel_selected["z"], 99)) if vel_selected["z"] else 0.0,
    }
    measured["velocity_magnitude_p99"] = velocity_measured["velocity_magnitude_p99"]
    measured["vel_x_p99"] = velocity_measured["vel_x_p99"]
    measured["vel_y_p99"] = velocity_measured["vel_y_p99"]
    measured["vel_z_p99"] = velocity_measured["vel_z_p99"]

    # 3sigma threshold 비교 (velocity combo)
    checks = [
        ("velocity_magnitude_3sigma", measured["velocity_magnitude_p99"], "속도 크기(3σ)"),
        ("vel_x_3sigma", measured["vel_x_p99"], "X축 속도(3σ)"),
        ("vel_y_3sigma", measured["vel_y_p99"], "Y축 속도(3σ)"),
        ("vel_z_3sigma", measured["vel_z_p99"], "Z축 속도(3σ)"),
    ]
    velocity_alert_candidates = []
    velocity_triggered = {}
    velocity_ops = {}
    for key, val, label in checks:
        limit = thresholds.get(key)
        if limit is None or val <= limit:
            continue
        hit_uids = []
        for uid in UNIT_IDS:
            x_vals, y_vals, z_vals = per_uid_vel.get(uid, ([], [], []))
            series = _series_for_metric(uid, key, x_vals, y_vals, z_vals)
            if not series:
                continue
            if _longest_run_sec(series, float(limit), ">") >= min_exceed_duration_sec:
                hit_uids.append(f"0x{uid:02X}")
        if hit_uids:
            velocity_alert_candidates.append(
                f"{label} 초과: {val:.1f} > {limit:.1f} (uids={','.join(hit_uids)}, 연속 {min_exceed_duration_sec:.1f}s)"
            )
            velocity_triggered[key] = float(limit)
            velocity_ops[key] = ">"

    if len(velocity_alert_candidates) >= velocity_combo_min_triggers:
        alerts.extend(velocity_alert_candidates)
        triggered_metrics.update(velocity_triggered)
        metric_operators.update(velocity_ops)

    # velocity 하한 판정 (저신호/접촉불량/비정상 저진동)
    velocity_low_checks = [
        ("velocity_magnitude_low", measured["velocity_magnitude_p99"], "속도 크기(low)"),
        ("vel_x_low", measured["vel_x_p99"], "X축 속도(low)"),
        ("vel_y_low", measured["vel_y_p99"], "Y축 속도(low)"),
        ("vel_z_low", measured["vel_z_p99"], "Z축 속도(low)"),
    ]
    for key, val, label in velocity_low_checks:
        limit = thresholds.get(key)
        if limit is None or val >= limit:
            continue
        hit_uids = []
        for uid in UNIT_IDS:
            x_vals, y_vals, z_vals = per_uid_vel.get(uid, ([], [], []))
            if key == "vel_x_low":
                series = _series_for_metric(uid, "vel_x_3sigma", x_vals, y_vals, z_vals)
            elif key == "vel_y_low":
                series = _series_for_metric(uid, "vel_y_3sigma", x_vals, y_vals, z_vals)
            elif key == "vel_z_low":
                series = _series_for_metric(uid, "vel_z_3sigma", x_vals, y_vals, z_vals)
            else:
                series = _series_for_metric(uid, "velocity_magnitude_3sigma", x_vals, y_vals, z_vals)
            if not series:
                continue
            if _longest_run_sec(series, float(limit), "<") >= min_exceed_duration_sec:
                hit_uids.append(f"0x{uid:02X}")
        if hit_uids:
            alerts.append(
                f"{label} 미만: {val:.1f} < {float(limit):.1f} "
                f"(uids={','.join(hit_uids)}, 연속 {min_exceed_duration_sec:.1f}s)"
            )
            triggered_metrics[key] = float(limit)
            metric_operators[key] = "<"

    # 주파수 임계값 비교 (high/low)
    # high는 p99 기반 + burst(max) 보조 판정
    if freq_checks_enabled:
        freq_checks = [
            ("freq_x_high", "freq_x_p99", "FREQ_X high"),
            ("freq_y_high", "freq_y_p99", "FREQ_Y high"),
            ("freq_z_high", "freq_z_p99", "FREQ_Z high"),
        ]
        for key, measured_key, label in freq_checks:
            limit = thresholds.get(key)
            if limit is None:
                continue
            min_uid_count = int(thresholds.get(f"{key}_min_uid_count", freq_high_min_uid_count))
            min_uid_count = max(1, min_uid_count)
            exceed_uids = []
            for uid_key, uid_measured in measured_per_uid.items():
                uid_val = float(uid_measured.get(measured_key, 0.0))
                uid_int = int(uid_key, 16)
                _, _, _ = per_uid_vel.get(uid_int, ([], [], []))
                fx_vals, fy_vals, fz_vals = per_uid_freq.get(uid_int, ([], [], []))
                if measured_key == "freq_x_p99":
                    series = fx_vals
                elif measured_key == "freq_y_p99":
                    series = fy_vals
                else:
                    series = fz_vals
                if uid_val > float(limit) and _longest_run_sec(series, float(limit), ">") >= min_exceed_duration_sec:
                    exceed_uids.append(uid_key)
            if len(exceed_uids) >= min_uid_count:
                val = float(measured.get(measured_key, 0.0))
                alerts.append(
                    f"{label} 초과({len(exceed_uids)}UID): {val:.1f} > {float(limit):.1f} "
                    f"(uids={','.join(exceed_uids)}, 연속 {min_exceed_duration_sec:.1f}s)"
                )
                triggered_metrics[key] = float(limit)
                metric_operators[key] = ">"

    # 단일 UID 강한 초과 예외: 한 센서만 강하게 튀는 경우(예: UID 0x51)도 검출
        single_uid_overrides = [
            ("freq_x_single_uid_high", "freq_x_p99", "FREQ_X single high"),
            ("freq_y_single_uid_high", "freq_y_p99", "FREQ_Y single high"),
            ("freq_z_single_uid_high", "freq_z_p99", "FREQ_Z single high"),
        ]
        for key, measured_key, label in single_uid_overrides:
            limit = thresholds.get(key)
            if limit is None:
                continue
            exceed_uids = []
            max_uid_val = 0.0
            for uid_key, uid_measured in measured_per_uid.items():
                if uid_key.upper() in single_uid_ignore:
                    continue
                uid_val = float(uid_measured.get(measured_key, 0.0))
                if uid_val > max_uid_val:
                    max_uid_val = uid_val
                uid_int = int(uid_key, 16)
                fx_vals, fy_vals, fz_vals = per_uid_freq.get(uid_int, ([], [], []))
                if measured_key == "freq_x_p99":
                    series = fx_vals
                elif measured_key == "freq_y_p99":
                    series = fy_vals
                else:
                    series = fz_vals
                if uid_val > float(limit) and _longest_run_sec(series, float(limit), ">") >= min_exceed_duration_sec:
                    exceed_uids.append(uid_key)
            if exceed_uids:
                alerts.append(
                    f"{label} 초과({len(exceed_uids)}UID): {max_uid_val:.1f} > {float(limit):.1f} "
                    f"(uids={','.join(exceed_uids)}, 연속 {min_exceed_duration_sec:.1f}s)"
                )
                triggered_metrics[key] = float(limit)
                metric_operators[key] = ">"
        # burst(max) 보조 판정: p99에서 안 걸려도 짧고 강한 충격은 감지
        burst_checks = [
            ("freq_x_high_burst", "freq_x_max", thresholds.get("freq_x_high"), "FREQ_X high burst"),
            ("freq_y_high_burst", "freq_y_max", thresholds.get("freq_y_high"), "FREQ_Y high burst"),
            ("freq_z_high_burst", "freq_z_max", thresholds.get("freq_z_high"), "FREQ_Z high burst"),
        ]
        for metric_key, measured_key, base_limit, label in burst_checks:
            if base_limit is None:
                continue
            burst_limit = float(base_limit) * float(freq_high_burst_ratio)
            exceed_uids = []
            max_uid_val = 0.0
            for uid_key, uid_measured in measured_per_uid.items():
                uid_val = float(uid_measured.get(measured_key, 0.0))
                if uid_val > max_uid_val:
                    max_uid_val = uid_val
                uid_int = int(uid_key, 16)
                fx_vals, fy_vals, fz_vals = per_uid_freq.get(uid_int, ([], [], []))
                if measured_key == "freq_x_max":
                    series = fx_vals
                elif measured_key == "freq_y_max":
                    series = fy_vals
                else:
                    series = fz_vals
                if uid_val > burst_limit and _longest_run_sec(series, burst_limit, ">") >= min_exceed_duration_sec:
                    exceed_uids.append(uid_key)
            if exceed_uids:
                alerts.append(
                    f"{label} 초과({len(exceed_uids)}UID): {float(max_uid_val):.1f} > {burst_limit:.1f} "
                    f"(uids={','.join(exceed_uids)}, 연속 {min_exceed_duration_sec:.1f}s)"
                )
                triggered_metrics[metric_key] = float(burst_limit)
                metric_operators[metric_key] = ">"

        freq_low_checks = [
            ("freq_x_low", measured["freq_x_min"], "FREQ_X low"),
            ("freq_y_low", measured["freq_y_min"], "FREQ_Y low"),
            ("freq_z_low", measured["freq_z_min"], "FREQ_Z low"),
        ]
        for key, val, label in freq_low_checks:
            limit = thresholds.get(key)
            if limit is None or val >= limit:
                continue
            duration_hit = False
            for uid in UNIT_IDS:
                fx_vals, fy_vals, fz_vals = per_uid_freq.get(uid, ([], [], []))
                if key == "freq_x_low":
                    series = fx_vals
                elif key == "freq_y_low":
                    series = fy_vals
                else:
                    series = fz_vals
                if _longest_run_sec(series, float(limit), "<") >= min_exceed_duration_sec:
                    duration_hit = True
                    break
            if duration_hit:
                alerts.append(f"{label} 미만: {val:.1f} < {limit:.1f} (연속 {min_exceed_duration_sec:.1f}s)")
                triggered_metrics[key] = float(limit)
                metric_operators[key] = "<"

    metric_to_label = {
        "velocity_magnitude_3sigma": "속도 크기(3σ)",
        "velocity_magnitude_low": "속도 크기(low)",
        "vel_x_3sigma": "X축 속도(3σ)",
        "vel_x_low": "X축 속도(low)",
        "vel_y_3sigma": "Y축 속도(3σ)",
        "vel_y_low": "Y축 속도(low)",
        "vel_z_3sigma": "Z축 속도(3σ)",
        "vel_z_low": "Z축 속도(low)",
        "freq_x_high": "FREQ_X high",
        "freq_y_high": "FREQ_Y high",
        "freq_z_high": "FREQ_Z high",
        "freq_x_low": "FREQ_X low",
        "freq_y_low": "FREQ_Y low",
        "freq_z_low": "FREQ_Z low",
        "freq_x_high_burst": "FREQ_X high burst",
        "freq_y_high_burst": "FREQ_Y high burst",
        "freq_z_high_burst": "FREQ_Z high burst",
        "freq_x_single_uid_high": "FREQ_X single high",
        "freq_y_single_uid_high": "FREQ_Y single high",
        "freq_z_single_uid_high": "FREQ_Z single high",
    }
    metric_to_measured_key = {
        "velocity_magnitude_3sigma": "velocity_magnitude_p99",
        "velocity_magnitude_low": "velocity_magnitude_p99",
        "vel_x_3sigma": "vel_x_p99",
        "vel_x_low": "vel_x_p99",
        "vel_y_3sigma": "vel_y_p99",
        "vel_y_low": "vel_y_p99",
        "vel_z_3sigma": "vel_z_p99",
        "vel_z_low": "vel_z_p99",
        "freq_x_high": "freq_x_p99",
        "freq_y_high": "freq_y_p99",
        "freq_z_high": "freq_z_p99",
        "freq_x_low": "freq_x_min",
        "freq_y_low": "freq_y_min",
        "freq_z_low": "freq_z_min",
        "freq_x_high_burst": "freq_x_max",
        "freq_y_high_burst": "freq_y_max",
        "freq_z_high_burst": "freq_z_max",
        "freq_x_single_uid_high": "freq_x_p99",
        "freq_y_single_uid_high": "freq_y_p99",
        "freq_z_single_uid_high": "freq_z_p99",
    }
    culprit_details = []
    for metric_key, measured_key in metric_to_measured_key.items():
        if metric_key not in triggered_metrics:
            continue
        limit = triggered_metrics.get(metric_key)
        if limit is None:
            continue
        measured_val = float(measured.get(measured_key, 0.0))
        operator = metric_operators.get(metric_key, ">")
        is_low_metric = operator == "<"
        is_burst_metric = metric_key.endswith("_high_burst")
        if is_burst_metric:
            base_key = metric_key.replace("_high_burst", "_high")
            base_limit = thresholds.get(base_key)
            if base_limit is None:
                continue
            limit = float(base_limit) * float(freq_high_burst_ratio)
        is_violation = measured_val < float(limit) if is_low_metric else measured_val > float(limit)
        if not is_violation:
            continue
        culprit_uid = None
        culprit_val = float("inf") if is_low_metric else -1.0
        for uid_key, uid_measured in measured_per_uid.items():
            uid_val = float(uid_measured.get(measured_key, 0.0))
            if (not is_low_metric and uid_val > culprit_val) or (is_low_metric and uid_val < culprit_val):
                culprit_val = uid_val
                culprit_uid = uid_key
        if culprit_uid is None:
            continue
        culprit_details.append(
            {
                "metric": metric_key,
                "label": metric_to_label.get(metric_key, metric_key),
                "threshold": float(limit),
                "value": float(culprit_val),
                "culprit_uid": culprit_uid,
                "operator": operator,
            }
        )

    # Combo rule (UID-specific velocity thresholds - upper and lower bounds)
    combo_rule_enabled = thresholds.get("combo_rule_enabled", False)
    if combo_rule_enabled:
        # Upper bounds (진동 과다)
        uid53_max = float(thresholds.get("uid53_vel_mag_max", thresholds.get("uid53_vel_mag_thresh", 8000)))
        uid54_max = float(thresholds.get("uid54_vel_mag_max", thresholds.get("uid54_vel_mag_thresh", 37000)))
        uid55_max = float(thresholds.get("uid55_vel_mag_max", thresholds.get("uid55_vel_mag_thresh", 30500)))  # 미사용 (Y축 고장)

        # Lower bounds (센서 고장/접촉불량)
        uid53_min = float(thresholds.get("uid53_vel_mag_min", 5000))
        uid54_min = float(thresholds.get("uid54_vel_mag_min", 25000))
        uid55_min = float(thresholds.get("uid55_vel_mag_min", 12000))  # 미사용 (Y축 고장)

        combo_alerts = []
        for uid in UNIT_IDS:
            uid_key = f"0x{uid:02X}"
            if uid_key not in measured_per_uid:
                continue

            vel_mag = float(measured_per_uid[uid_key].get("velocity_magnitude_p99", 0.0))

            # UID별 상한/하한 체크
            max_thresh = None
            min_thresh = None
            if uid == 0x53:
                max_thresh = uid53_max
                min_thresh = uid53_min
            elif uid == 0x54:
                max_thresh = uid54_max
                min_thresh = uid54_min
            elif uid == 0x55:
                max_thresh = uid55_max
                min_thresh = uid55_min

            if max_thresh and vel_mag > max_thresh:
                combo_alerts.append(
                    f"{uid_key} velocity 과다: {vel_mag:.0f} > {max_thresh:.0f} mm/s"
                )
            elif min_thresh and vel_mag < min_thresh:
                combo_alerts.append(
                    f"{uid_key} velocity 부족(센서이상): {vel_mag:.0f} < {min_thresh:.0f} mm/s"
                )

        if combo_alerts:
            alerts.extend(combo_alerts)

    status = "ABNORMAL" if alerts else "NORMAL"
    result = {
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "total_samples": total_samples,
        "unit_ids": [f"0x{u:02X}" for u in UNIT_IDS],
        "active_threshold_profile": active_threshold_profile,
        "measured": measured,
        "measured_per_uid": measured_per_uid,
        "alerts": alerts,
        "culprit_details": culprit_details,
    }
    print(f"[진동 체크] 결과: {status}")
    for a in alerts:
        print(f"  ⚠ {a}")
    for detail in culprit_details:
        print(
            "  [원인] "
            f"{detail['label']} UID {detail['culprit_uid']}: "
            f"{detail['value']:.1f} {detail.get('operator', '>')} {detail['threshold']:.1f}"
        )
    return result


def _save_result(result: dict):
    result_path = args.result or os.path.join(os.getcwd(), "vibration_result.json")
    try:
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"[결과 저장] {result_path}")
    except Exception as e:
        print(f"[결과 저장 오류] {e}")


def _default_summary_plot_path() -> str:
    if args.summary_plot:
        return args.summary_plot
    return os.path.join(save_dir, f"{RUN_TS}_summary.png")


def _save_summary_plot(result: dict = None) -> str:
    out_path = _default_summary_plot_path()
    try:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
    except Exception:
        pass

    n_uid = max(1, len(UNIT_IDS))
    fig, axes = plt.subplots(n_uid, 2, figsize=(14, max(4, 3 * n_uid)), squeeze=False)
    fig.suptitle("Vibration Check Summary", fontsize=13)

    for r, uid in enumerate(UNIT_IDS):
        tbuf = np.array(buf_time[uid], dtype=float)
        if tbuf.size > 0:
            tbuf = tbuf - tbuf[0]
        else:
            tbuf = np.array([0.0], dtype=float)

        ax_vel = axes[r][0]
        ax_vel.set_title(f"UID 0x{uid:02X} Velocity (mm/s)")
        ax_vel.set_xlabel("Time (s)")
        ax_vel.set_ylabel("Vel")
        ax_vel.grid(True, alpha=0.3)
        labels = ("X", "Y", "Z")
        for i in range(3):
            vals = np.array(buf_vel[uid][i], dtype=float)
            if vals.size == 0:
                continue
            n = min(len(tbuf), len(vals))
            ax_vel.plot(tbuf[:n], vals[:n], label=labels[i], linewidth=1.0)
        ax_vel.legend(loc="upper right", fontsize=8)

        ax_freq = axes[r][1]
        ax_freq.set_title(f"UID 0x{uid:02X} Frequency (Hz)")
        ax_freq.set_xlabel("Time (s)")
        ax_freq.set_ylabel("Freq")
        ax_freq.grid(True, alpha=0.3)
        for i in range(3):
            vals = np.array(buf_freq[uid][i], dtype=float)
            if vals.size == 0:
                continue
            n = min(len(tbuf), len(vals))
            ax_freq.plot(tbuf[:n], vals[:n], label=labels[i], linewidth=1.0)
        ax_freq.legend(loc="upper right", fontsize=8)

    if isinstance(result, dict):
        status = result.get("status", "UNKNOWN")
        alerts = result.get("alerts", [])
        first_alert = alerts[0] if isinstance(alerts, list) and alerts else "-"
        footer = f"status={status} | alerts={len(alerts) if isinstance(alerts, list) else 0} | first={first_alert}"
        fig.text(0.01, 0.01, footer, fontsize=9, ha="left", va="bottom")

    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    print(f"[그래프 저장] {out_path}")
    return out_path


# =========================
# 헤드리스 모드: duration 후 자동 종료
# =========================
if args.headless:
    duration = max(1.0, args.duration)
    print(f"[헤드리스] {duration}초 수집 후 종료")
    time.sleep(duration)
    stop_event.set()
    collector_thread.join(timeout=5.0)

    if args.check:
        baseline = None
        if args.baseline and os.path.exists(args.baseline):
            try:
                with open(args.baseline, "r", encoding="utf-8") as f:
                    baseline = json.load(f)
                print(f"[베이스라인] {args.baseline} 로드")
            except Exception as e:
                print(f"[베이스라인 로드 오류] {e}")

        if baseline:
            result = _check_against_baseline(baseline)
        else:
            # 베이스라인 없으면 샘플 수만 확인하고 NORMAL 처리
            total = sum(len(buf_time[u]) for u in UNIT_IDS)
            result = {
                "status": "NORMAL" if total > 0 else "ERROR",
                "reason": "베이스라인 없음 - 샘플 수만 확인" if total > 0 else "수집 샘플 없음",
                "timestamp": datetime.now().isoformat(),
                "total_samples": total,
            }
            print(f"[진동 체크] 베이스라인 없음, 샘플 수={total}, 상태={result['status']}")
        try:
            summary_plot = _save_summary_plot(result)
            if isinstance(result, dict):
                result["summary_plot"] = summary_plot
        except Exception as e:
            print(f"[그래프 저장 오류] {e}")
        _save_result(result)

    # CSV 닫기
    for uid in UNIT_IDS:
        try:
            csv_files[uid].close()
        except Exception:
            pass

    try:
        client.close()
    except Exception:
        pass

    print("[헤드리스] 완료")

else:
    # =========================
    # GUI 모드: 그래프
    # =========================
    print("[초기화] matplotlib 그래프 생성")
    ncol = max(1, len(UNIT_IDS))
    fig = plt.figure(figsize=(6 * ncol, 12))
    gs = fig.add_gridspec(4, ncol)  # rows: ACC, VEL, DISP, FFT

    axes = {}
    lines_acc = {}
    lines_vel = {}
    lines_disp = {}
    axes_fft = {}

    for c, uid in enumerate(UNIT_IDS):
        # ACC
        ax_acc = fig.add_subplot(gs[0, c])
        ax_acc.set_title(f"UID 0x{uid:02X} - ACC (g)")
        ax_acc.grid(True, alpha=0.3)
        lines_acc[uid] = [ax_acc.plot([], [], label=lab)[0] for lab in ("X", "Y", "Z")]
        ax_acc.legend(loc="upper right")

        # VEL
        ax_vel = fig.add_subplot(gs[1, c])
        ax_vel.set_title(f"UID 0x{uid:02X} - VEL (mm/s)")
        ax_vel.grid(True, alpha=0.3)
        lines_vel[uid] = [ax_vel.plot([], [], label=lab)[0] for lab in ("X", "Y", "Z")]
        ax_vel.legend(loc="upper right")

        # DISP
        ax_disp = fig.add_subplot(gs[2, c])
        ax_disp.set_title(f"UID 0x{uid:02X} - DISP (um)")
        ax_disp.grid(True, alpha=0.3)
        lines_disp[uid] = [ax_disp.plot([], [], label=lab)[0] for lab in ("X", "Y", "Z")]
        ax_disp.legend(loc="upper right")

        # FFT
        ax_fft = fig.add_subplot(gs[3, c])
        ax_fft.set_title(f"UID 0x{uid:02X} - FFT (from DISP)")
        ax_fft.grid(True, alpha=0.3)
        axes_fft[uid] = ax_fft

        axes[uid] = (ax_acc, ax_vel, ax_disp, ax_fft)

    def update(_):
        for uid in UNIT_IDS:
            if len(buf_time[uid]) < 2:
                continue

            t0 = buf_time[uid][0]
            t = np.array(buf_time[uid]) - t0

            # 시계열 라인 업데이트
            for i in range(3):
                lines_acc[uid][i].set_data(t, list(buf_acc[uid][i]))
                lines_vel[uid][i].set_data(t, list(buf_vel[uid][i]))
                lines_disp[uid][i].set_data(t, list(buf_disp[uid][i]))

            # 자동 스케일
            for ax in axes[uid][:3]:
                ax.relim()
                ax.autoscale_view()

            # FFT 스펙트럼 (동적 x축)
            axf = axes_fft[uid]
            axf.cla()
            axf.set_title(f"UID 0x{uid:02X} - FFT (from DISP)")
            axf.set_xlabel("Frequency (Hz)")
            axf.set_ylabel("Magnitude")
            axf.grid(True, alpha=0.3)

            dt = (buf_time[uid][-1] - buf_time[uid][0]) / max(1, (len(buf_time[uid]) - 1))
            fs = 1.0 / dt if dt > 0 else SAMPLE_RATE_HINT_PER_UNIT
            nyq = fs * 0.5

            labels = ("X", "Y", "Z")
            for i in range(3):
                series = buf_disp[uid][i]
                if len(series) >= 16:
                    y = np.array(series, dtype=float)
                    y = y - np.mean(y)
                    Y = np.fft.rfft(np.hanning(len(y)) * y)
                    f = np.fft.rfftfreq(len(y), d=1.0 / fs)
                    axf.plot(f, np.abs(Y), label=labels[i])

            if np.isfinite(nyq) and nyq > 0:
                axf.set_xlim(0, nyq)
            axf.legend(loc="upper right")

        return []

    print("[그래프] 애니메이션 시작")
    ani = FuncAnimation(fig, update, interval=PLOT_INTERVAL_MS, blit=False, cache_frame_data=False)
    plt.tight_layout()
    plt.show()

    # =========================
    # GUI 종료 처리
    # =========================
    print("[종료] 프로그램 종료 중...")
    stop_event.set()
    collector_thread.join(timeout=1.0)
    try:
        client.close()
    except Exception:
        pass

    for uid in UNIT_IDS:
        try:
            csv_files[uid].close()
        except Exception:
            pass

    print("[종료] 완료")
