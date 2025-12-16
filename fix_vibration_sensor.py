#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WT-VB02-485 진동센서 설정 복구 스크립트

문제: ACC만 나오고 VEL/DISP/FREQ가 0
원인: 검출 주기(0x65)가 0으로 리셋됨

이 스크립트가 하는 일:
1. 현재 설정 레지스터 읽기
2. 검출 주기(0x65)를 50Hz로 설정
3. 저장 후 데이터 확인
"""

import time
import glob
from pymodbus.client import ModbusSerialClient

# ========== 설정 ==========
usb_ports = glob.glob('/dev/ttyUSB*')
PORT = usb_ports[0] if usb_ports else None
BAUD = 115200
UNIT_IDS = [0x50, 0x51, 0x52]

# 레지스터 주소 (SDK 기준)
REG_SAVE = 0x00        # 저장/재시작
REG_UNLOCK = 0x69      # 잠금 해제
REG_DETECT_PERIOD = 0x65  # 검출 주기 ← 핵심!
REG_CUTOFF_FREQ1 = 0x63   # 차단 주파수 1
REG_CUTOFF_FREQ2 = 0x64   # 차단 주파수 2

# 데이터 레지스터
REG_VEL_START = 0x3A   # 진동속도 X,Y,Z (0x3A~0x3C)
REG_DISP_START = 0x41  # 진동변위 X,Y,Z (0x41~0x43)
REG_FREQ_START = 0x44  # 진동주파수 X,Y,Z (0x44~0x46)

UNLOCK_VALUE = 0xB588
SAVE_VALUE = 0x0000    # SDK 기준 (0x0000으로 저장)

if not PORT:
    print("[오류] USB 포트 없음!")
    exit(1)

print(f"[포트] {PORT} @ {BAUD}bps")
print(f"[센서] {[hex(x) for x in UNIT_IDS]}")
print()

# ========== Modbus 연결 ==========
client = ModbusSerialClient(
    port=PORT,
    baudrate=BAUD,
    timeout=0.3,
    parity='N',
    stopbits=1,
    bytesize=8
)

if not client.connect():
    print(f"[오류] 연결 실패!")
    exit(1)

# ========== 함수 ==========
def read_reg(uid, addr, name=""):
    """레지스터 1개 읽기"""
    try:
        result = client.read_holding_registers(address=addr, count=1, device_id=uid)
        if hasattr(result, 'registers'):
            val = result.registers[0]
            print(f"  [0x{uid:02X}] 0x{addr:02X} {name}: {val} (0x{val:04X})")
            return val
        else:
            print(f"  [0x{uid:02X}] 0x{addr:02X} {name}: 읽기 실패")
            return None
    except Exception as e:
        print(f"  [0x{uid:02X}] 0x{addr:02X} {name}: 예외 - {e}")
        return None

def read_regs(uid, addr, count):
    """레지스터 여러개 읽기"""
    try:
        result = client.read_holding_registers(address=addr, count=count, device_id=uid)
        if hasattr(result, 'registers'):
            return result.registers
        return None
    except:
        return None

def write_reg(uid, addr, value, name=""):
    """레지스터 쓰기 (잠금해제 → 쓰기 → 저장)"""
    try:
        # 1. 잠금 해제
        client.write_register(address=REG_UNLOCK, value=UNLOCK_VALUE, device_id=uid)
        time.sleep(0.1)

        # 2. 값 쓰기
        client.write_register(address=addr, value=value, device_id=uid)
        print(f"  [0x{uid:02X}] 0x{addr:02X} {name} = {value} 설정 완료")
        time.sleep(0.1)

        # 3. 저장
        client.write_register(address=REG_SAVE, value=SAVE_VALUE, device_id=uid)
        print(f"  [0x{uid:02X}] 설정 저장됨")
        return True
    except Exception as e:
        print(f"  [0x{uid:02X}] 쓰기 실패: {e}")
        return False

# ========== 1단계: 현재 설정 확인 ==========
print("=" * 60)
print("[1단계] 현재 설정 레지스터 확인")
print("=" * 60)

for uid in UNIT_IDS:
    print(f"\n센서 0x{uid:02X}:")
    read_reg(uid, REG_CUTOFF_FREQ1, "차단주파수1")
    read_reg(uid, REG_CUTOFF_FREQ2, "차단주파수2")
    val = read_reg(uid, REG_DETECT_PERIOD, "검출주기 ★")
    if val == 0:
        print(f"  ⚠️  검출주기가 0입니다! VEL/DISP 출력 안 됨!")
    time.sleep(0.1)

# ========== 2단계: 현재 데이터 확인 ==========
print("\n" + "=" * 60)
print("[2단계] 현재 데이터 확인")
print("=" * 60)

for uid in UNIT_IDS:
    print(f"\n센서 0x{uid:02X}:")

    # VEL (0x3A~0x3C)
    vel = read_regs(uid, REG_VEL_START, 3)
    if vel:
        print(f"  VEL: X={vel[0]} Y={vel[1]} Z={vel[2]}")

    # DISP (0x41~0x43)
    disp = read_regs(uid, REG_DISP_START, 3)
    if disp:
        print(f"  DISP: X={disp[0]} Y={disp[1]} Z={disp[2]}")

    # FREQ (0x44~0x46)
    freq = read_regs(uid, REG_FREQ_START, 3)
    if freq:
        print(f"  FREQ: X={freq[0]} Y={freq[1]} Z={freq[2]}")

    # 0인지 체크
    if vel and disp and all(v == 0 for v in vel + disp):
        print(f"  ⚠️  VEL/DISP 전부 0! 설정 필요!")

    time.sleep(0.1)

# ========== 3단계: 설정 복구 ==========
print("\n" + "=" * 60)
print("[3단계] 검출주기 설정 (50Hz)")
print("=" * 60)

input("\n엔터를 누르면 검출주기를 50Hz로 설정합니다... (Ctrl+C로 취소)")

for uid in UNIT_IDS:
    print(f"\n센서 0x{uid:02X} 설정 중...")
    write_reg(uid, REG_DETECT_PERIOD, 50, "검출주기")
    time.sleep(1.0)  # 센서 재시작 대기

# ========== 4단계: 설정 확인 ==========
print("\n" + "=" * 60)
print("[4단계] 설정 후 확인")
print("=" * 60)

time.sleep(2.0)  # 센서 안정화 대기

for uid in UNIT_IDS:
    print(f"\n센서 0x{uid:02X}:")
    read_reg(uid, REG_DETECT_PERIOD, "검출주기")

    # 데이터 다시 확인
    vel = read_regs(uid, REG_VEL_START, 3)
    disp = read_regs(uid, REG_DISP_START, 3)

    if vel:
        print(f"  VEL: X={vel[0]} Y={vel[1]} Z={vel[2]}")
    if disp:
        print(f"  DISP: X={disp[0]} Y={disp[1]} Z={disp[2]}")

    if vel and disp:
        if all(v == 0 for v in vel + disp):
            print(f"  ❌ 여전히 0 - 센서 문제일 수 있음")
        else:
            print(f"  ✅ 데이터 출력 확인!")

    time.sleep(0.1)

client.close()
print("\n" + "=" * 60)
print("[완료]")
print("=" * 60)
