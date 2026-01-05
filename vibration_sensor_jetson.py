# -*- coding: utf-8 -*-
"""
WitMotion WT-VB02-485 (Jetson, /dev/ttyUSB0, 115200bps)
버스에 3개 센서(UID: 0x50, 0x51, 0x52) 동시 폴링
- 센서별 그래프 4종: ACC(g), VEL(mm/s), DISP(um), FFT(변위 기반, 동적 x축)
- 센서별 CSV 개별 저장
- 통신 안정화: 유닛별 재시도→재연결→재부팅

필요 패키지: pymodbus==2.5.3, pyserial, matplotlib, numpy
"""

import os, time, threading, csv
from datetime import datetime
from collections import deque

import numpy as np
from pymodbus.client.sync import ModbusSerialClient  # pymodbus 2.x
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

# ---------- 사용자 설정 ----------
PORT = "/dev/ttyUSB0"  # Jetson USB 시리얼 포트
BAUD = 115200
UNIT_IDS = [0x50, 0x51, 0x52]     # 요청: 50, 51, 52
PARITY = 'N'; STOPBITS = 1; BYTESIZE = 8
TIMEOUT_S = 0.15

# 폴링/버퍼
POLL_HZ_TOTAL = 45      # 총 루프 속도(초당 45회 → 유닛당 약 15Hz)
RETRY_READ = 2
RECONNECT_TIMEOUT = 3.0
WINDOW_SEC = 5.0
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

# ---------- 저장 폴더 설정 (Jetson용) ----------
home_dir = os.path.expanduser("~")
save_dir = os.path.join(home_dir, "data", "vibration_data")
os.makedirs(save_dir, exist_ok=True)
print(f"[저장 폴더] {save_dir}")

# ---------- CSV 핸들(센서별) ----------
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

# ---------- 버퍼(센서별) ----------
maxlen = int(WINDOW_SEC * SAMPLE_RATE_HINT_PER_UNIT)
buf_time = {uid: deque(maxlen=maxlen) for uid in UNIT_IDS}
buf_acc  = {uid: [deque(maxlen=maxlen) for _ in range(3)] for uid in UNIT_IDS}
buf_vel  = {uid: [deque(maxlen=maxlen) for _ in range(3)] for uid in UNIT_IDS}
buf_disp = {uid: [deque(maxlen=maxlen) for _ in range(3)] for uid in UNIT_IDS}
buf_freq = {uid: [deque(maxlen=maxlen) for _ in range(3)] for uid in UNIT_IDS}
last_ok  = {uid: time.time() for uid in UNIT_IDS}

# ---------- Modbus ----------
def make_client():
    return ModbusSerialClient(
        port=PORT, baudrate=BAUD, bytesize=BYTESIZE,
        parity=PARITY, stopbits=STOPBITS, timeout=TIMEOUT_S, method="rtu"
    )

client = make_client()
client.connect()

def unlock_sensor(uid):
    try: client.write_register(address=REG_UNLOCK_ADDR, value=0xB588, slave=uid)
    except Exception: pass

def restart_sensor(uid):
    try:
        unlock_sensor(uid); time.sleep(0.05)
        client.write_register(address=REG_SAVE, value=0x00FF, slave=uid)
    except Exception as e:
        print(f"[UID 0x{uid:02X}] 재시작 오류: {e}")

def read_block_retry(uid):
    for _ in range(RETRY_READ):
        rr = client.read_holding_registers(address=REG_START, count=REG_COUNT, slave=uid)
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

# ---------- 수집 스레드 ----------
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

# ---------- 그래프 (3열×4행) ----------
fig = plt.figure(figsize=(18, 12))
gs = fig.add_gridspec(4, 3)  # rows: ACC, VEL, DISP, FFT; cols: UID50, UID51, UID52

axes = {}
lines_acc = {}
lines_vel = {}
lines_disp = {}
axes_fft = {}
for c, uid in enumerate(UNIT_IDS):
    # ACC
    ax_acc = fig.add_subplot(gs[0, c]); ax_acc.set_title(f"UID 0x{uid:02X} - ACC (g)")
    ax_acc.grid(True, alpha=0.3); lines_acc[uid] = [ax_acc.plot([], [], label=lab)[0] for lab in ["X","Y","Z"]]
    ax_acc.legend(loc="upper right")
    # VEL
    ax_vel = fig.add_subplot(gs[1, c]); ax_vel.set_title(f"UID 0x{uid:02X} - VEL (mm/s)")
    ax_vel.grid(True, alpha=0.3); lines_vel[uid] = [ax_vel.plot([], [], label=lab)[0] for lab in ["X","Y","Z"]]
    ax_vel.legend(loc="upper right")
    # DISP
    ax_disp = fig.add_subplot(gs[2, c]); ax_disp.set_title(f"UID 0x{uid:02X} - DISP (um)")
    ax_disp.grid(True, alpha=0.3); lines_disp[uid] = [ax_disp.plot([], [], label=lab)[0] for lab in ["X","Y","Z"]]
    ax_disp.legend(loc="upper right")
    # FFT (동적 x축)
    ax_fft = fig.add_subplot(gs[3, c]); ax_fft.set_title(f"UID 0x{uid:02X} - FFT (from DISP)")
    ax_fft.grid(True, alpha=0.3); axes_fft[uid] = ax_fft
    axes[uid] = (ax_acc, ax_vel, ax_disp, ax_fft)

def update(_):
    for uid in UNIT_IDS:
        if len(buf_time[uid]) < 2: continue
        t0 = buf_time[uid][0]
        t  = np.array(buf_time[uid]) - t0

        # 시계열 라인 업데이트
        for i in range(3):
            lines_acc[uid][i].set_data(t, list(buf_acc[uid][i]))
            lines_vel[uid][i].set_data(t, list(buf_vel[uid][i]))
            lines_disp[uid][i].set_data(t, list(buf_disp[uid][i]))

        # 자동 스케일
        for ax in axes[uid][:3]:
            ax.relim(); ax.autoscale_view()

        # ---------- FFT 스펙트럼 (동적 x축) ----------
        axf = axes_fft[uid]
        axf.cla()
        axf.set_title(f"UID 0x{uid:02X} - FFT (from DISP)")
        axf.set_xlabel("Frequency (Hz)")
        axf.set_ylabel("Magnitude")
        axf.grid(True, alpha=0.3)

        labels = ["X","Y","Z"]
        # 현재 버퍼 시간 길이로부터 동적 fs 계산
        dt = (buf_time[uid][-1] - buf_time[uid][0]) / max(1, (len(buf_time[uid]) - 1))
        fs = 1.0/dt if dt > 0 else SAMPLE_RATE_HINT_PER_UNIT
        nyq = fs * 0.5

        for i in range(3):
            series = buf_disp[uid][i]
            if len(series) >= 16:
                y = np.array(series, dtype=float)
                y = y - np.mean(y)
                Y = np.fft.rfft(np.hanning(len(y)) * y)
                f = np.fft.rfftfreq(len(y), d=1.0/fs)
                axf.plot(f, np.abs(Y), label=labels[i])

        # x축을 매 프레임 fs에 맞춰 동적으로 설정
        axf.set_xlim(0, nyq if np.isfinite(nyq) and nyq > 0 else None)
        axf.legend(loc="upper right")

    return []

ani = FuncAnimation(fig, update, interval=PLOT_INTERVAL_MS, blit=False)
plt.tight_layout()
plt.show()

# ---------- 종료 ----------
stop_event.set()
collector_thread.join(timeout=1.0)
try: client.close()
except: pass
for uid in UNIT_IDS:
    try: csv_files[uid].close()
    except: pass
print("[종료] 수집 스레드 및 CSV 핸들 닫음.")
