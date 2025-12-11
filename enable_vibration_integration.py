#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WT-VB02-485 진동센서 적분 모드 활성화 스크립트

문제: ACC만 나오고 VEL/DISP/FREQ가 0인 경우
원인: 센서 내부 적분 기능이 비활성화됨

이 스크립트는 센서 설정을 시도합니다.
"""

import time
import glob
from pymodbus.client import ModbusSerialClient

# USB 포트 자동 탐지
usb_ports = glob.glob('/dev/ttyUSB*')
if usb_ports:
    PORT = usb_ports[0]
    print(f"[포트] {PORT}")
else:
    print("[오류] USB 포트 없음!")
    exit(1)

BAUD = 115200
UNIT_IDS = [0x50, 0x51, 0x52]

# 레지스터 주소
REG_UNLOCK = 0x69      # 잠금 해제
REG_SAVE = 0x00        # 설정 저장
REG_RATE = 0x03        # 출력 속도
REG_BANDWIDTH = 0x1F   # 대역폭
REG_ALG = 0x24         # 알고리즘 선택

# 알려진 설정 값들
UNLOCK_VALUE = 0xB588  # 잠금 해제 키
SAVE_VALUE = 0x00FF    # 설정 저장 후 재시작

client = ModbusSerialClient(
    port=PORT,
    baudrate=BAUD,
    timeout=0.3,
    parity='N',
    stopbits=1,
    bytesize=8
)

if not client.connect():
    print(f"[오류] 연결 실패: {PORT}")
    exit(1)

print(f"[연결] {PORT} @ {BAUD}bps")
print()

def unlock(uid):
    """센서 잠금 해제"""
    try:
        client.write_register(address=REG_UNLOCK, value=UNLOCK_VALUE, slave=uid)
        print(f"  [0x{uid:02X}] 잠금 해제 완료")
        return True
    except Exception as e:
        print(f"  [0x{uid:02X}] 잠금 해제 실패: {e}")
        return False

def save_and_restart(uid):
    """설정 저장 및 재시작"""
    try:
        client.write_register(address=REG_SAVE, value=SAVE_VALUE, slave=uid)
        print(f"  [0x{uid:02X}] 저장 및 재시작...")
        return True
    except Exception as e:
        print(f"  [0x{uid:02X}] 저장 실패: {e}")
        return False

def read_config(uid):
    """현재 설정 읽기"""
    print(f"\n[0x{uid:02X}] 현재 설정 읽기:")

    # 주요 설정 레지스터들
    regs_to_read = [
        (0x02, "RSW (출력 선택)"),
        (0x03, "RATE (출력 속도)"),
        (0x1F, "BANDWIDTH"),
        (0x24, "ALG (알고리즘)"),
        (0x25, "GYRO 자동교정"),
        (0x27, "가속도 필터"),
    ]

    for addr, name in regs_to_read:
        try:
            result = client.read_holding_registers(address=addr, count=1, slave=uid)
            if hasattr(result, 'registers'):
                val = result.registers[0]
                print(f"  0x{addr:02X} {name}: 0x{val:04X} ({val})")
            else:
                print(f"  0x{addr:02X} {name}: 읽기 실패")
        except Exception as e:
            print(f"  0x{addr:02X} {name}: 예외 - {e}")
        time.sleep(0.05)

def try_enable_integration(uid):
    """적분 모드 활성화 시도"""
    print(f"\n[0x{uid:02X}] 적분 모드 활성화 시도:")

    # 1. 잠금 해제
    if not unlock(uid):
        return False
    time.sleep(0.1)

    # 2. RSW 레지스터 설정 (모든 출력 활성화)
    #    비트: 가속도, 자이로, 각도, 속도, 변위 등
    try:
        # 0x3F = 모든 기본 출력 활성화
        client.write_register(address=0x02, value=0x3F, slave=uid)
        print(f"  [0x{uid:02X}] RSW = 0x3F (모든 출력 활성화)")
    except Exception as e:
        print(f"  [0x{uid:02X}] RSW 설정 실패: {e}")
    time.sleep(0.1)

    # 3. 출력 속도 설정 (0x06 = 10Hz, 0x07 = 50Hz, 0x08 = 100Hz)
    try:
        client.write_register(address=0x03, value=0x06, slave=uid)
        print(f"  [0x{uid:02X}] RATE = 0x06 (10Hz)")
    except Exception as e:
        print(f"  [0x{uid:02X}] RATE 설정 실패: {e}")
    time.sleep(0.1)

    # 4. 저장
    if not save_and_restart(uid):
        return False

    return True

# ============ 메인 ============
print("=" * 60)
print("WT-VB02-485 진동센서 설정 스크립트")
print("=" * 60)

# 1. 현재 설정 확인
print("\n[1단계] 현재 설정 확인")
for uid in UNIT_IDS:
    read_config(uid)
    time.sleep(0.2)

# 2. 적분 모드 활성화 시도
print("\n" + "=" * 60)
print("[2단계] 적분 모드 활성화 시도")
print("=" * 60)

for uid in UNIT_IDS:
    try_enable_integration(uid)
    time.sleep(1.0)  # 센서 재시작 대기

# 3. 재연결 후 확인
print("\n" + "=" * 60)
print("[3단계] 재연결 후 설정 확인")
print("=" * 60)

client.close()
time.sleep(2.0)  # 센서 재시작 대기

client = ModbusSerialClient(
    port=PORT,
    baudrate=BAUD,
    timeout=0.3,
    parity='N',
    stopbits=1,
    bytesize=8
)

if client.connect():
    for uid in UNIT_IDS:
        read_config(uid)
        time.sleep(0.2)

    # 데이터 읽기 테스트
    print("\n" + "=" * 60)
    print("[4단계] 데이터 읽기 테스트")
    print("=" * 60)

    REG_START = 0x34
    REG_COUNT = 19

    for uid in UNIT_IDS:
        try:
            result = client.read_holding_registers(address=REG_START, count=REG_COUNT, slave=uid)
            if hasattr(result, 'registers'):
                regs = result.registers
                print(f"\n[0x{uid:02X}] Raw 레지스터:")
                print(f"  ACC (0-2):  {regs[0]:5d} {regs[1]:5d} {regs[2]:5d}")
                print(f"  VEL (6-8):  {regs[6]:5d} {regs[7]:5d} {regs[8]:5d}")
                print(f"  DISP(13-15):{regs[13]:5d} {regs[14]:5d} {regs[15]:5d}")
                print(f"  FREQ(16-18):{regs[16]:5d} {regs[17]:5d} {regs[18]:5d}")

                # 0 체크
                vel_zero = all(regs[i] == 0 for i in [6, 7, 8])
                disp_zero = all(regs[i] == 0 for i in [13, 14, 15])
                if vel_zero and disp_zero:
                    print(f"  ⚠ VEL/DISP 여전히 0 - 센서 펌웨어 문제일 수 있음")
                else:
                    print(f"  ✓ 데이터 출력 확인됨!")
        except Exception as e:
            print(f"[0x{uid:02X}] 읽기 실패: {e}")
        time.sleep(0.2)

client.close()
print("\n[완료]")
