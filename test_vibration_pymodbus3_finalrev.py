#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WitMotion WT-VB02-485 멀티센서 수집 + 그래프 + CSV (Ubuntu 22.04 / Jetson Orin Nano)
- pymodbus 3.x 기준 (RTU)
- "최종수정본" 로직(리부트 오탐 방지 + FC3 실패시 FC4 fallback)을 반영한 리눅스 변환판

필요:
  pip3 install pymodbus==3.6.9 pyserial matplotlib numpy
"""

import os, time, threading, csv
from datetime import datetime
from collections import deque

import numpy as np
from pymodbus.client import ModbusSerialClient  # pymodbus 3.x
from pymodbus.exceptions import ModbusIOException
from serial import SerialException

import matplotlib
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
PORT = "/dev/ttyUSB0"
BAUD = 115200
UNIT_IDS = [0x53, 0x54, 0x55]   # 환경에 맞게 수정
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
home_dir = os.path.expanduser("~")
save_dir = os.path.join(home_dir, "data", "vibration_data")
os.makedirs(save_dir, exist_ok=True)
print(f"[저장 폴더] {save_dir}")


# =========================
# CSV 핸들(센서별)
# =========================
def make_csv(uid: int):
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


# =========================
# 버퍼(센서별)
# =========================
buf_time = {uid: deque(maxlen=maxlen) for uid in UNIT_IDS}
buf_acc  = {uid: [deque(maxlen=maxlen) for _ in range(3)] for uid in UNIT_IDS}
buf_vel  = {uid: [deque(maxlen=maxlen) for _ in range(3)] for uid in UNIT_IDS}
buf_disp = {uid: [deque(maxlen=maxlen) for _ in range(3)] for uid in UNIT_IDS}
buf_freq = {uid: [deque(maxlen=maxlen) for _ in range(3)] for uid in UNIT_IDS}

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
# 그래프
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

        # 현재 버퍼 시간 길이로부터 동적 fs 계산
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
# 종료 처리
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
