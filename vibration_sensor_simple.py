#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WitMotion WT-VB02-485 Vibration Sensor for Jetson
Adapted from Windows version for Linux/Jetson compatibility

Hardware:
- WitMotion WT-VB02-485 sensor (3 units: UID 0x50, 0x51, 0x52)
- USB-RS485 converter (CH340): /dev/ttyUSB0
- Baud rate: 115200

Changes from Windows version:
- Port: COM51 → /dev/ttyUSB0
- Font: Malgun Gothic → NanumGothic
- Save path: Desktop → /home/dkuyj/data/vibration_data
"""

import os, time, threading, csv, json
from datetime import datetime
from collections import deque

import numpy as np
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusIOException
from serial import SerialException

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# ========== 한글 폰트 설정 ==========
matplotlib.rc('font', family='Noto Sans CJK JP')
matplotlib.rcParams['axes.unicode_minus'] = False

# ========== 설정 파일 로드 ==========
config_file = "vibration_config.json"
config = {}
if os.path.exists(config_file):
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        print(f"[설정] {config_file} 로드 완료")
    except Exception as e:
        print(f"[경고] 설정 파일 로드 실패: {e}, 기본값 사용")

# ========== 사용자 설정 (Jetson용) ==========
PORT = config.get("port", "/dev/ttyUSB0")  # Linux/Jetson USB 시리얼 포트
BAUD = config.get("baud", 115200)
# Convert hex strings to integers
unit_ids_str = config.get("unit_ids", ["0x50", "0x51", "0x52"])
UNIT_IDS = [int(uid, 16) if isinstance(uid, str) else uid for uid in unit_ids_str]
PARITY = 'N'
STOPBITS = 1
BYTESIZE = 8
TIMEOUT_S = 0.15

# 폴링/버퍼
POLL_HZ_TOTAL = config.get("poll_hz_total", 45)  # 총 루프 속도(초당 45회 → 유닛당 약 15Hz)
RETRY_READ = 2
RECONNECT_TIMEOUT = 3.0
WINDOW_SEC = config.get("window_sec", 5.0)  # X축 시간 범위 (초)
SAMPLE_RATE_HINT_PER_UNIT = POLL_HZ_TOTAL / max(1, len(UNIT_IDS))
PLOT_INTERVAL_MS = 100

# 레지스터 맵
REG_AX = 0x34; REG_AY = 0x35; REG_AZ = 0x36
REG_GX = 0x37; REG_GY = 0x38; REG_GZ = 0x39
REG_VX = 0x3A; REG_VY = 0x3B; REG_VZ = 0x3C
REG_DX = 0x41; REG_DY = 0x42; REG_DZ = 0x43
REG_HX = 0x44; REG_HY = 0x45; REG_HZ = 0x46
REG_START = REG_AX
REG_COUNT = (REG_HZ - REG_AX + 1)  # 19
REG_UNLOCK_ADDR = 0x0069
REG_SAVE = 0x00  # 0x00FF → 재시작

# 스케일
ACC_SCALE   = 16.0   / 32768.0   # g
GYRO_SCALE  = 2000.0 / 32768.0   # deg/s (현재 미사용)
FREQ_DIVISOR = 10.0              # Hz

# ========== 저장 폴더 설정 (Linux용) ==========
# 하드코딩된 저장 경로
home_dir = os.path.expanduser("~")
save_dir = os.path.join(home_dir, "data", "vibration_data")
os.makedirs(save_dir, exist_ok=True)
print(f"[저장 폴더] {save_dir}")

# ========== 정상 데이터 베이스라인 설정 ==========
BASELINE_FILE = os.path.join(save_dir, "baseline_stats.json")
BASELINE_DURATION_SEC = config.get("baseline_duration_sec", 600)  # 10분간 정상 데이터 수집
ANOMALY_THRESHOLD_SIGMA = config.get("anomaly_threshold_sigma", 3.0)  # 평균 + 3*표준편차

# ========== Y축 범위 설정 ==========
Y_AXIS_LIMITS = config.get("y_axis_limits", {
    "acc": {"min": -20, "max": 20},
    "vel": {"min": -100, "max": 100},
    "disp": {"min": -500, "max": 500},
    "fft": {"min": 0, "max": 1000}
})
AUTO_SCALE = config.get("auto_scale", False)  # False = 고정 범위, True = 자동 범위

# ========== 고장 감지 설정 ==========
FAULT_DETECTION_CONFIG = config.get("fault_detection", {
    "enabled": True,
    "methods": {
        "threshold": {
            "enabled": True,
            "disp_max": 5000,
            "vel_max": 500,
            "acc_max": 10
        }
    },
    "alert": {
        "console_print": True,
        "save_event_log": False
    }
})

# 고장 이벤트 로그
fault_events = []
fault_event_log_path = None
if FAULT_DETECTION_CONFIG.get("alert", {}).get("save_event_log", False):
    fault_event_log_path = os.path.expanduser(
        FAULT_DETECTION_CONFIG["alert"].get("event_log_path", "~/data/vibration_data/fault_events.log")
    )

# 베이스라인 수집 모드
baseline_mode = False
baseline_data = {uid: {'disp_x': [], 'disp_y': [], 'disp_z': [],
                       'fft_x': [], 'fft_y': [], 'fft_z': []} for uid in UNIT_IDS}
baseline_start_time = None

# 베이스라인 통계 (로드 또는 초기화)
baseline_stats = {}
if os.path.exists(BASELINE_FILE):
    try:
        with open(BASELINE_FILE, 'r') as f:
            baseline_stats = json.load(f)
        print(f"[베이스라인] 기존 데이터 로드: {BASELINE_FILE}")
    except Exception as e:
        print(f"[베이스라인] 로드 실패: {e}")

# 이상 감지 상태
anomaly_detected = {uid: False for uid in UNIT_IDS}

def save_baseline_stats():
    """베이스라인 통계를 JSON 파일로 저장"""
    try:
        with open(BASELINE_FILE, 'w') as f:
            json.dump(baseline_stats, f, indent=2)
        print(f"[베이스라인] 저장 완료: {BASELINE_FILE}")
    except Exception as e:
        print(f"[베이스라인] 저장 실패: {e}")

def calculate_baseline_stats():
    """수집된 정상 데이터로부터 통계 계산"""
    global baseline_stats
    baseline_stats = {}

    for uid in UNIT_IDS:
        uid_key = f"0x{uid:02X}"
        stats = {}

        for axis in ['disp_x', 'disp_y', 'disp_z', 'fft_x', 'fft_y', 'fft_z']:
            data = np.array(baseline_data[uid][axis])
            if len(data) > 0:
                stats[axis] = {
                    'mean': float(np.mean(data)),
                    'std': float(np.std(data)),
                    'min': float(np.min(data)),
                    'max': float(np.max(data)),
                    'threshold': float(np.mean(data) + ANOMALY_THRESHOLD_SIGMA * np.std(data))
                }

        baseline_stats[uid_key] = stats

    save_baseline_stats()
    print(f"[베이스라인] 통계 계산 완료 (총 {len(baseline_data[UNIT_IDS[0]]['disp_x'])}개 샘플)")

def check_anomaly(uid, disp_x, disp_y, disp_z, fft_x, fft_y, fft_z):
    """현재 진동값이 정상 범위를 벗어났는지 확인"""
    uid_key = f"0x{uid:02X}"

    if uid_key not in baseline_stats:
        return False

    stats = baseline_stats[uid_key]

    # 각 축별 임계값 확인
    checks = [
        ('disp_x', abs(disp_x)),
        ('disp_y', abs(disp_y)),
        ('disp_z', abs(disp_z)),
        ('fft_x', fft_x),
        ('fft_y', fft_y),
        ('fft_z', fft_z)
    ]

    for metric, value in checks:
        if metric in stats:
            threshold = stats[metric]['threshold']
            if value > threshold:
                return True

    return False

def check_fault(uid, acc, vel, disp, freq, fft_peaks):
    """고장 감지: 여러 방법을 조합하여 고장 여부 판단"""
    if not FAULT_DETECTION_CONFIG.get("enabled", False):
        return False, None

    methods = FAULT_DETECTION_CONFIG.get("methods", {})
    fault_reasons = []

    # 1. 임계값 기반 감지
    if methods.get("threshold", {}).get("enabled", False):
        thresholds = methods["threshold"]

        # 변위 임계값
        max_disp = max(abs(disp[0]), abs(disp[1]), abs(disp[2]))
        if max_disp > thresholds.get("disp_max", 5000):
            fault_reasons.append(f"변위 초과: {max_disp:.1f} um > {thresholds['disp_max']} um")

        # 속도 임계값
        max_vel = max(abs(vel[0]), abs(vel[1]), abs(vel[2]))
        if max_vel > thresholds.get("vel_max", 500):
            fault_reasons.append(f"속도 초과: {max_vel:.1f} mm/s > {thresholds['vel_max']} mm/s")

        # 가속도 임계값
        max_acc = max(abs(acc[0]), abs(acc[1]), abs(acc[2]))
        if max_acc > thresholds.get("acc_max", 10):
            fault_reasons.append(f"가속도 초과: {max_acc:.2f} g > {thresholds['acc_max']} g")

    # 2. 베이스라인 기반 감지 (기존 anomaly 기능)
    if methods.get("baseline", {}).get("enabled", False):
        fx, fy, fz = fft_peaks
        is_anomaly = check_anomaly(uid, disp[0], disp[1], disp[2], fx, fy, fz)
        if is_anomaly:
            fault_reasons.append("베이스라인 대비 이상 진동 감지")

    # 3. 주파수 범위 기반 감지
    if methods.get("frequency", {}).get("enabled", False):
        abnormal_ranges = methods["frequency"].get("abnormal_ranges", [])
        fx, fy, fz = fft_peaks

        for freq_val, axis_name in [(fx, 'X'), (fy, 'Y'), (fz, 'Z')]:
            for freq_range in abnormal_ranges:
                if freq_range["min"] <= freq_val <= freq_range["max"]:
                    fault_reasons.append(
                        f"이상 주파수 감지 ({axis_name}축): {freq_val:.1f} Hz "
                        f"({freq_range['min']}-{freq_range['max']} Hz 범위)"
                    )

    # 고장 판정
    is_fault = len(fault_reasons) > 0

    # 로그 기록
    if is_fault:
        log_fault_event(uid, fault_reasons, acc, vel, disp, freq, fft_peaks)

    return is_fault, fault_reasons

def log_fault_event(uid, reasons, acc, vel, disp, freq, fft_peaks):
    """고장 이벤트 로그 기록"""
    alert_config = FAULT_DETECTION_CONFIG.get("alert", {})

    # 콘솔 출력
    if alert_config.get("console_print", True):
        print(f"\n{'='*60}")
        print(f"[고장 감지] UID 0x{uid:02X} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        for reason in reasons:
            print(f"  - {reason}")
        print(f"  현재값: ACC=({acc[0]:.2f}, {acc[1]:.2f}, {acc[2]:.2f}) g")
        print(f"         VEL=({vel[0]:.1f}, {vel[1]:.1f}, {vel[2]:.1f}) mm/s")
        print(f"         DISP=({disp[0]:.1f}, {disp[1]:.1f}, {disp[2]:.1f}) um")
        print(f"         FFT=({fft_peaks[0]:.1f}, {fft_peaks[1]:.1f}, {fft_peaks[2]:.1f}) Hz")
        print(f"{'='*60}\n")

    # 파일 로그 저장
    if alert_config.get("save_event_log", False) and fault_event_log_path:
        try:
            log_dir = os.path.dirname(fault_event_log_path)
            os.makedirs(log_dir, exist_ok=True)

            with open(fault_event_log_path, 'a', encoding='utf-8') as f:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"\n{timestamp} | UID 0x{uid:02X}\n")
                for reason in reasons:
                    f.write(f"  - {reason}\n")
                f.write(f"  ACC=({acc[0]:.2f}, {acc[1]:.2f}, {acc[2]:.2f}) g, ")
                f.write(f"VEL=({vel[0]:.1f}, {vel[1]:.1f}, {vel[2]:.1f}) mm/s, ")
                f.write(f"DISP=({disp[0]:.1f}, {disp[1]:.1f}, {disp[2]:.1f}) um, ")
                f.write(f"FFT=({fft_peaks[0]:.1f}, {fft_peaks[1]:.1f}, {fft_peaks[2]:.1f}) Hz\n")
        except Exception as e:
            print(f"[오류] 고장 로그 저장 실패: {e}")

# ========== CSV 핸들(센서별) ==========
def make_csv(uid):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(save_dir, f"{ts}_UID{uid:02X}_vibration.csv")
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

# ========== 버퍼(센서별) ==========
maxlen = int(WINDOW_SEC * SAMPLE_RATE_HINT_PER_UNIT)
buf_time = {uid: deque(maxlen=maxlen) for uid in UNIT_IDS}
buf_acc  = {uid: [deque(maxlen=maxlen) for _ in range(3)] for uid in UNIT_IDS}
buf_vel  = {uid: [deque(maxlen=maxlen) for _ in range(3)] for uid in UNIT_IDS}
buf_disp = {uid: [deque(maxlen=maxlen) for _ in range(3)] for uid in UNIT_IDS}
buf_freq = {uid: [deque(maxlen=maxlen) for _ in range(3)] for uid in UNIT_IDS}
last_ok  = {uid: time.time() for uid in UNIT_IDS}

# ========== Modbus ==========
def make_client():
    # pymodbus 3.x에서는 method 파라미터 불필요 (자동으로 RTU 사용)
    return ModbusSerialClient(
        port=PORT, baudrate=BAUD, bytesize=BYTESIZE,
        parity=PARITY, stopbits=STOPBITS, timeout=TIMEOUT_S
    )

client = make_client()
if not client.connect():
    print(f"[오류] {PORT} 연결 실패. USB-RS485 변환기를 확인하세요.")
    exit(1)

print(f"[연결] {PORT} @ {BAUD}bps")

def unlock_sensor(uid):
    try: client.write_register(address=REG_UNLOCK_ADDR, value=0xB588, device_id=uid)
    except Exception: pass

def restart_sensor(uid):
    try:
        unlock_sensor(uid); time.sleep(0.05)
        client.write_register(address=REG_SAVE, value=0x00FF, device_id=uid)
    except Exception as e:
        print(f"[UID 0x{uid:02X}] 재시작 오류: {e}")

def read_block_retry(uid):
    for _ in range(RETRY_READ):
        rr = client.read_holding_registers(address=REG_START, count=REG_COUNT, device_id=uid)
        if hasattr(rr, "isError") and not rr.isError(): return rr.registers
        time.sleep(0.01)
    raise ModbusIOException("read_holding_registers 실패")

def s16(v): return v-0x10000 if v>=0x8000 else v

def parse_map(regs):
    # regs: 0x34~0x46
    AX,AY,AZ = [s16(regs[i]) for i in [0,1,2]]
    VX,VY,VZ = [s16(regs[i]) for i in [6,7,8]]
    DX,DY,DZ = [s16(regs[i]) for i in [13,14,15]]
    HX,HY,HZ = [s16(regs[i]) for i in [16,17,18]]
    acc  = (AX*ACC_SCALE, AY*ACC_SCALE, AZ*ACC_SCALE)
    vel  = (float(VX), float(VY), float(VZ))            # mm/s
    disp = (float(DX), float(DY), float(DZ))            # um
    freq = (HX/FREQ_DIVISOR, HY/FREQ_DIVISOR, HZ/FREQ_DIVISOR)
    return acc, vel, disp, freq

def fft_peak(series, tbuf):
    """스펙트럼 피크(Hz): 동적 fs 추정 사용"""
    if len(series) < 16 or len(tbuf) < 2: return 0.0
    y = np.array(series, dtype=float)
    dt = (tbuf[-1] - tbuf[0]) / max(1, (len(tbuf)-1))
    fs = 1.0/dt if dt>0 else SAMPLE_RATE_HINT_PER_UNIT
    y = y - np.mean(y)
    Y = np.fft.rfft(np.hanning(len(y)) * y)
    f = np.fft.rfftfreq(len(y), d=1.0/fs)
    m = np.abs(Y)
    return float(f[np.argmax(m[1:])+1]) if len(f)>1 else 0.0

# ========== 수집 스레드 ==========
stop_event = threading.Event()

def collector_loop():
    poll_dt = 1.0 / POLL_HZ_TOTAL
    while not stop_event.is_set():
        t_cycle = time.time()
        try:
            if not getattr(client, "connected", False):
                client.connect()
            # 각 유닛 순차 폴링
            for uid in UNIT_IDS:
                try:
                    regs = read_block_retry(uid)
                    acc, vel, disp, freq = parse_map(regs)
                    t = time.time()
                    buf_time[uid].append(t)
                    for i in range(3):
                        buf_acc[uid][i].append(acc[i])
                        buf_vel[uid][i].append(vel[i])
                        buf_disp[uid][i].append(disp[i])
                        buf_freq[uid][i].append(freq[i])

                    # FFT 피크 (변위 기준)
                    fx = fft_peak(buf_disp[uid][0], buf_time[uid])
                    fy = fft_peak(buf_disp[uid][1], buf_time[uid])
                    fz = fft_peak(buf_disp[uid][2], buf_time[uid])

                    # 베이스라인 수집 모드
                    global baseline_mode, baseline_start_time, baseline_data
                    if baseline_mode:
                        if baseline_start_time is None:
                            baseline_start_time = t
                            print(f"[베이스라인] 정상 데이터 수집 시작 ({BASELINE_DURATION_SEC}초)")

                        elapsed = t - baseline_start_time
                        if elapsed < BASELINE_DURATION_SEC:
                            # 데이터 수집
                            baseline_data[uid]['disp_x'].append(abs(disp[0]))
                            baseline_data[uid]['disp_y'].append(abs(disp[1]))
                            baseline_data[uid]['disp_z'].append(abs(disp[2]))
                            baseline_data[uid]['fft_x'].append(fx)
                            baseline_data[uid]['fft_y'].append(fy)
                            baseline_data[uid]['fft_z'].append(fz)

                            # 진행률 표시 (10초마다)
                            if int(elapsed) % 10 == 0 and int(elapsed) > 0:
                                progress = (elapsed / BASELINE_DURATION_SEC) * 100
                                print(f"[베이스라인] 진행률: {progress:.1f}% ({int(elapsed)}초/{BASELINE_DURATION_SEC}초)")
                        else:
                            # 수집 완료
                            print(f"[베이스라인] 수집 완료! 통계 계산 중...")
                            calculate_baseline_stats()
                            baseline_mode = False
                            baseline_start_time = None

                    # 고장 감지
                    is_fault, fault_reasons = check_fault(uid, acc, vel, disp, freq, (fx, fy, fz))

                    # 기존 anomaly 감지도 유지 (베이스라인이 있을 때만)
                    if baseline_stats and not baseline_mode and not is_fault:
                        is_anomaly = check_anomaly(uid, disp[0], disp[1], disp[2], fx, fy, fz)
                        if is_anomaly and not anomaly_detected[uid]:
                            anomaly_detected[uid] = True
                            print(f"[경고] UID 0x{uid:02X} 이상 진동 감지! DISP:({disp[0]:.2f}, {disp[1]:.2f}, {disp[2]:.2f}) FFT:({fx:.2f}, {fy:.2f}, {fz:.2f})")
                        elif not is_anomaly and anomaly_detected[uid]:
                            anomaly_detected[uid] = False
                            print(f"[정상] UID 0x{uid:02X} 진동 정상 범위로 복귀")

                    # CSV
                    row = [
                        datetime.fromtimestamp(t).isoformat(timespec="milliseconds"),
                        *acc, *vel, *disp, *freq, fx, fy, fz
                    ]
                    try:
                        csv_writers[uid].writerow(row)
                        csv_files[uid].flush()
                    except Exception as e:
                        print(f"[UID 0x{uid:02X}] CSV 오류: {e}")
                    last_ok[uid] = t

                except (ModbusIOException, SerialException, OSError) as e:
                    print(f"[UID 0x{uid:02X}] 읽기 오류: {e} → 재시도/재연결")
                    try: client.close()
                    except: pass
                    time.sleep(0.2)
                    client.connect()
                except Exception as e:
                    print(f"[UID 0x{uid:02X}] 예외: {e}")

                # 유닛별 타임아웃 → 재부팅
                if time.time() - last_ok[uid] > RECONNECT_TIMEOUT:
                    print(f"[UID 0x{uid:02X}] 타임아웃 → 센서 재시작")
                    restart_sensor(uid)
                    time.sleep(1.0)
                    try: client.close()
                    except: pass
                    time.sleep(0.2)
                    client.connect()

        except Exception as e:
            print(f"[루프 예외] {e}")

        remain = poll_dt - (time.time() - t_cycle)
        if remain > 0: time.sleep(remain)

collector_thread = threading.Thread(target=collector_loop, daemon=True)
collector_thread.start()

# ========== 그래프 (3열×1행 - DISP만) ==========
fig = plt.figure(figsize=(18, 6))
gs = fig.add_gridspec(1, 3)  # rows: DISP only; cols: UID50, UID51, UID52

axes = {}
lines_disp = {}
for c, uid in enumerate(UNIT_IDS):
    # DISP
    ax_disp = fig.add_subplot(gs[0, c])
    ax_disp.set_title(f"UID 0x{uid:02X} - DISP (um)")
    ax_disp.set_xlabel("Time (s)")
    ax_disp.set_ylabel("Displacement (um)")
    ax_disp.grid(True, alpha=0.3)
    lines_disp[uid] = [ax_disp.plot([], [], label=lab, linewidth=2)[0] for lab in ["X","Y","Z"]]
    ax_disp.legend(loc="upper right")
    axes[uid] = ax_disp

def update(_):
    for uid in UNIT_IDS:
        if len(buf_time[uid]) < 2: continue
        t0 = buf_time[uid][0]
        t  = np.array(buf_time[uid]) - t0

        # DISP 라인 업데이트
        for i in range(3):
            lines_disp[uid][i].set_data(t, list(buf_disp[uid][i]))

        # 타이틀 업데이트 (베이스라인 모드 / 이상 감지 표시)
        ax_disp = axes[uid]
        status = ""
        if baseline_mode:
            status = " [베이스라인 수집중]"
        elif anomaly_detected[uid]:
            status = " [⚠ 이상 감지]"
        elif baseline_stats:
            status = " [정상]"

        ax_disp.set_title(f"UID 0x{uid:02X} - DISP (um){status}")

        # Y축 범위 설정 (고정 범위 또는 자동 스케일)
        if AUTO_SCALE:
            # 자동 스케일
            ax_disp.relim()
            ax_disp.autoscale_view()
        else:
            # 고정 범위 적용
            ax_disp.set_ylim(Y_AXIS_LIMITS["disp"]["min"], Y_AXIS_LIMITS["disp"]["max"])
            # x축은 항상 자동으로 조정
            ax_disp.set_xlim(0, WINDOW_SEC)

    return []

def on_key(event):
    """키보드 이벤트 핸들러"""
    global baseline_mode, baseline_start_time, baseline_data

    if event.key == 'b' and not baseline_mode:
        # 베이스라인 수집 시작
        baseline_mode = True
        baseline_start_time = None
        # 기존 데이터 초기화
        for uid in UNIT_IDS:
            for key in baseline_data[uid]:
                baseline_data[uid][key].clear()
        print("\n" + "="*60)
        print("[베이스라인] 'b' 키 입력 감지 - 정상 데이터 수집 모드 활성화")
        print(f"[베이스라인] {BASELINE_DURATION_SEC}초 동안 데이터를 수집합니다...")
        print("="*60 + "\n")
    elif event.key == 's' and baseline_stats:
        # 현재 베이스라인 통계 출력
        print("\n" + "="*60)
        print("[베이스라인] 현재 저장된 통계:")
        for uid_key, stats in baseline_stats.items():
            print(f"  {uid_key}:")
            for metric, values in stats.items():
                print(f"    {metric}: mean={values['mean']:.3f}, std={values['std']:.3f}, threshold={values['threshold']:.3f}")
        print("="*60 + "\n")

# 키보드 이벤트 연결
fig.canvas.mpl_connect('key_press_event', on_key)

ani = FuncAnimation(fig, update, interval=PLOT_INTERVAL_MS, blit=False)
plt.tight_layout()

# 사용법 출력
print("\n" + "="*60)
print("[사용법]")
print("  'b' 키: 베이스라인 수집 시작 (10분간 정상 데이터 수집)")
print("  's' 키: 현재 베이스라인 통계 출력")
print("  창 닫기: 프로그램 종료")
print("="*60 + "\n")

plt.show()

# ========== 종료 ==========
stop_event.set()
collector_thread.join(timeout=1.0)
try: client.close()
except: pass
for uid in UNIT_IDS:
    try: csv_files[uid].close()
    except: pass
print("[종료] 수집 스레드 및 CSV 핸들 닫음.")
