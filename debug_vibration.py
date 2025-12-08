#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
진동센서 디버깅 스크립트 v3
- USB 포트 자동 탐지
- 3가지 파라미터 (device_id, slave, unit) 모두 테스트
- raw 레지스터 값 vs 파싱된 값 비교
"""

import time
import glob
import os
from pymodbus.client import ModbusSerialClient

# pymodbus 버전 확인
import pymodbus
print(f"[정보] pymodbus 버전: {pymodbus.__version__}")

# ========== USB 포트 자동 탐지 ==========
print("\n[USB 포트 탐지]")
usb_ports = glob.glob('/dev/ttyUSB*')
if usb_ports:
    print(f"  발견된 포트: {usb_ports}")
    PORT = usb_ports[0]  # 첫 번째 사용
    print(f"  → 사용할 포트: {PORT}")
else:
    print("  ⚠ USB 포트가 없습니다! USB-RS485 연결 확인하세요.")
    # 혹시 모르니 ACM도 확인
    acm_ports = glob.glob('/dev/ttyACM*')
    if acm_ports:
        print(f"  ACM 포트 발견: {acm_ports}")
        PORT = acm_ports[0]
    else:
        print("  종료합니다.")
        exit(1)

BAUD = 115200
TIMEOUT = 0.3  # 타임아웃 늘림

# 레지스터 맵 (WT-VB02-485)
REG_START = 0x34  # ACC_X 시작
REG_COUNT = 19    # ACC ~ FFT까지

# 스케일 (vibration_sensor_simple.py와 동일)
ACC_SCALE = 16.0 / 32768.0
FREQ_DIVISOR = 10.0

def s16(v):
    """unsigned to signed 16-bit"""
    return v - 0x10000 if v >= 0x8000 else v

def parse_registers(regs):
    """레지스터 파싱 (vibration_sensor_simple.py와 동일)"""
    # regs: 0x34~0x46 (19개)
    AX, AY, AZ = [s16(regs[i]) for i in [0, 1, 2]]
    VX, VY, VZ = [s16(regs[i]) for i in [6, 7, 8]]
    DX, DY, DZ = [s16(regs[i]) for i in [13, 14, 15]]
    HX, HY, HZ = [s16(regs[i]) for i in [16, 17, 18]]

    acc = (AX * ACC_SCALE, AY * ACC_SCALE, AZ * ACC_SCALE)
    vel = (float(VX), float(VY), float(VZ))
    disp = (float(DX), float(DY), float(DZ))
    freq = (HX / FREQ_DIVISOR, HY / FREQ_DIVISOR, HZ / FREQ_DIVISOR)

    return acc, vel, disp, freq

print("=" * 60)
print("진동센서 디버깅 스크립트 v2")
print("=" * 60)

# 클라이언트 생성
client = ModbusSerialClient(
    port=PORT,
    baudrate=BAUD,
    timeout=TIMEOUT,
    parity='N',
    stopbits=1,
    bytesize=8
)

if not client.connect():
    print(f"[오류] {PORT} 연결 실패!")
    exit(1)

print(f"[연결] {PORT} @ {BAUD}bps")
print()

# pymodbus 버전 확인
import pymodbus
print(f"[정보] pymodbus 버전: {pymodbus.__version__}")
print()

# ========== 테스트 0: 3가지 파라미터 비교 ==========
print("=" * 60)
print("[테스트 0] 파라미터 비교 (device_id vs slave vs unit)")
print("=" * 60)

uid = 0x50  # 첫 번째 센서만 테스트

# device_id
print("\n[device_id 파라미터]")
try:
    result = client.read_holding_registers(address=REG_START, count=3, device_id=uid)
    if hasattr(result, 'registers'):
        print(f"  ✓ 성공: {result.registers}")
    else:
        print(f"  ✗ 응답 없음: {result}")
except Exception as e:
    print(f"  ✗ 예외: {e}")

time.sleep(0.2)

# slave
print("\n[slave 파라미터]")
try:
    result = client.read_holding_registers(address=REG_START, count=3, slave=uid)
    if hasattr(result, 'registers'):
        print(f"  ✓ 성공: {result.registers}")
    else:
        print(f"  ✗ 응답 없음: {result}")
except Exception as e:
    print(f"  ✗ 예외: {e}")

time.sleep(0.2)

# unit
print("\n[unit 파라미터]")
try:
    result = client.read_holding_registers(address=REG_START, count=3, unit=uid)
    if hasattr(result, 'registers'):
        print(f"  ✓ 성공: {result.registers}")
    else:
        print(f"  ✗ 응답 없음: {result}")
except Exception as e:
    print(f"  ✗ 예외: {e}")

print()

# ========== 테스트 1: Raw 레지스터 전체 출력 ==========
print("=" * 60)
print("[테스트 1] Raw 레지스터 전체 출력 (19개)")
print("          (device_id 사용)")
print("=" * 60)

for uid in [0x50, 0x51, 0x52]:
    try:
        result = client.read_holding_registers(address=REG_START, count=REG_COUNT, device_id=uid)
        if hasattr(result, 'registers'):
            regs = result.registers
            print(f"\n[UID 0x{uid:02X}] 전체 Raw 레지스터:")
            print(f"  [0-2]   ACC raw:  {regs[0]:5d} {regs[1]:5d} {regs[2]:5d}")
            print(f"  [3-5]   GYRO raw: {regs[3]:5d} {regs[4]:5d} {regs[5]:5d}")
            print(f"  [6-8]   VEL raw:  {regs[6]:5d} {regs[7]:5d} {regs[8]:5d}")
            print(f"  [9-12]  ???:      {regs[9]:5d} {regs[10]:5d} {regs[11]:5d} {regs[12]:5d}")
            print(f"  [13-15] DISP raw: {regs[13]:5d} {regs[14]:5d} {regs[15]:5d}")
            print(f"  [16-18] FREQ raw: {regs[16]:5d} {regs[17]:5d} {regs[18]:5d}")

            # 0인지 체크
            all_zero = all(v == 0 for v in regs)
            disp_zero = all(regs[i] == 0 for i in [13, 14, 15])
            print(f"\n  → 전체 0? {all_zero} / DISP 0? {disp_zero}")
        else:
            print(f"[UID 0x{uid:02X}] 응답 없음: {result}")
    except Exception as e:
        print(f"[UID 0x{uid:02X}] 예외: {e}")
    time.sleep(0.1)

print()

# ========== 테스트 2: 파싱 결과 확인 ==========
print("=" * 60)
print("[테스트 2] 파싱된 값 (vibration_sensor_simple.py 로직)")
print("=" * 60)

for uid in [0x50, 0x51, 0x52]:
    try:
        result = client.read_holding_registers(address=REG_START, count=REG_COUNT, device_id=uid)
        if hasattr(result, 'registers'):
            acc, vel, disp, freq = parse_registers(result.registers)
            print(f"\n[UID 0x{uid:02X}] 파싱 결과:")
            print(f"  ACC:  X={acc[0]:8.4f} Y={acc[1]:8.4f} Z={acc[2]:8.4f} g")
            print(f"  VEL:  X={vel[0]:8.1f} Y={vel[1]:8.1f} Z={vel[2]:8.1f} mm/s")
            print(f"  DISP: X={disp[0]:8.1f} Y={disp[1]:8.1f} Z={disp[2]:8.1f} um")
            print(f"  FREQ: X={freq[0]:8.1f} Y={freq[1]:8.1f} Z={freq[2]:8.1f} Hz")
    except Exception as e:
        print(f"[UID 0x{uid:02X}] 예외: {e}")
    time.sleep(0.1)

print()

# ========== 테스트 3: 실시간 모니터링 (60초 - 워밍업 확인) ==========
print("=" * 60)
print("[테스트 3] 실시간 모니터링 (60초 - 워밍업 확인)")
print("          ★ 센서를 흔들어보세요! ★")
print("          ★ 시간이 지나면서 값이 올라오는지 확인 ★")
print("          (Ctrl+C로 중단 가능)")
print("=" * 60)
print()

start = time.time()
sample_count = 0

try:
  while time.time() - start < 60:
    sample_count += 1
    print(f"--- 샘플 #{sample_count} (t={time.time()-start:.1f}s) ---")

    for uid in [0x50, 0x51, 0x52]:
        try:
            result = client.read_holding_registers(address=REG_START, count=REG_COUNT, device_id=uid)
            if hasattr(result, 'registers'):
                regs = result.registers
                acc, vel, disp, freq = parse_registers(regs)

                # DISP raw vs parsed
                disp_raw = [regs[13], regs[14], regs[15]]
                print(f"  [0x{uid:02X}] DISP raw={disp_raw} → parsed=({disp[0]:.1f}, {disp[1]:.1f}, {disp[2]:.1f})")
        except Exception as e:
            print(f"  [0x{uid:02X}] 오류: {e}")

    print()
    time.sleep(0.5)

except KeyboardInterrupt:
  print("\n[중단됨] Ctrl+C")

client.close()
print("=" * 60)
print("[완료] 디버깅 종료")
print("=" * 60)
