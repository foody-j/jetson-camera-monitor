# WitMotion WT-VB02-485 Vibration Sensor Issue

**Date:** 2025-12-18
**Status:** Open
**Location:** Jetson1 (현장 PC)

---

## Sensor Info

- **Model:** WitMotion WT-VB02-485
- **Quantity:** 3 units
- **Addresses:** 0x53, 0x54, 0x55 (Jetson1)
- **Connection:** RS485 Daisy Chain
- **Interface:** USB-RS485 Converter (CH340) → `/dev/ttyUSB0`
- **Baud Rate:** 115200
- **Power:** 24V (changed from 5V)
- **Voltage Spec:** 5V ~ 36V (within spec)

---

## Issue Summary

전압을 5V에서 24V로 변경한 후 VEL/DISP/FREQ 데이터가 출력되지 않음.

### Working
- USB-RS485 연결: OK
- Modbus 통신: OK
- ACC (가속도): OK
- GYRO (자이로): OK

### Not Working
- VEL (속도): Always 0
- DISP (변위): Always 0
- FREQ (주파수): Always 0

센서를 물리적으로 쳐도 VEL/DISP/FREQ 값이 변하지 않음.

---

## Diagnostic Results

### 1. Address Scan (All Baud Rates)
```bash
# 9600, 19200, 38400, 57600, 115200 모두 스캔
# 결과: 프로그램 실행 중에는 응답 없음 (포트 점유)
# 프로그램 종료 후에도 한동안 응답 없었음
```

### 2. Register Read (UID 0x53)

**Config Registers (0x00~0x0F):**
```
[0x0, 0x0, 0x3823, 0x6, 0x6, 0x4, 0x0, 0x2, 0x64, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0]
```

**Data Registers (0x34~0x46):**
```
[189, 1693, 1105, 17, 15, 21, 0, 0, 0, 0, 0, 0, 2209, 0, 0, 0, 0, 0, 0]
```

**Register Map:**
| Register | Parameter | Value | Status |
|----------|-----------|-------|--------|
| 0x34-0x36 | ACC (X,Y,Z) | 189, 1693, 1105 | Working |
| 0x37-0x39 | GYRO (X,Y,Z) | 17, 15, 21 | Working |
| 0x3A-0x3C | VEL (X,Y,Z) | 0, 0, 0 | NOT Working |
| 0x41-0x43 | DISP (X,Y,Z) | 0, 0, 0 | NOT Working |
| 0x44-0x46 | FREQ (X,Y,Z) | 0, 0, 0 | NOT Working |
| 0x40 | Unknown | 2209 | ? |

### 3. CSV Data Sample
```csv
time,ACC_X(g),ACC_Y(g),ACC_Z(g),VEL_X(mm/s),VEL_Y(mm/s),VEL_Z(mm/s),DISP_X(um),DISP_Y(um),DISP_Z(um),...
2025-12-18T21:32:24.533,0.092,0.827,0.539,0.0,0.0,0.0,0.0,0.0,0.0,...
```

ACC 값은 정상 (중력가속도 ~1g 분산), VEL/DISP는 모두 0.

---

## Possible Causes

1. **진동 분석 모드 비활성화** - 24V 전환 시 설정이 리셋됐을 수 있음
2. **센서 설정 문제** - 특정 레지스터에 활성화 명령 필요할 수 있음
3. **센서 부분 고장** - ACC/GYRO만 작동하고 진동 분석 회로 손상

---

## Email to WitMotion

### Email 1 (Sent)
```
Subject: WT-VB02-485 - Data Acquisition Issue After Voltage Change + Address Configuration Question

- 5V → 24V 전압 변경 후 문제 발생
- 주소 변경 방법 문의
```

### Email 2 (To Send)
```
Subject: RE: WT-VB02-485 - Additional Diagnostic Information (VEL/DISP/FREQ Output Issue)

- 레지스터 읽기 결과 첨부
- ACC/GYRO는 정상, VEL/DISP/FREQ는 0
- 진동 분석 모드 활성화 명령 문의
- Factory reset 명령 문의
```

---

## Questions for WitMotion

1. VEL/DISP/FREQ 출력을 활성화하는 레지스터/명령이 있는지?
2. 레지스터 0x40의 값 2209는 무엇을 의미하는지?
3. Config 레지스터 값(0x3823 등)이 정상인지?
4. Factory reset 명령이 있는지?
5. 주소 변경 방법 및 절차?

---

## Test Commands

```bash
# 센서 스캔 (모든 보드레이트)
cat << 'EOF' > /tmp/scan.py
from pymodbus.client import ModbusSerialClient
for baud in [9600, 19200, 38400, 57600, 115200]:
    print(f"=== {baud} bps ===")
    c = ModbusSerialClient(port="/dev/ttyUSB0", baudrate=baud, timeout=0.2, retries=0)
    c.connect()
    f = []
    for i in range(1, 128):
        try:
            r = c.read_holding_registers(address=0x34, count=1, device_id=i)
            if hasattr(r, "registers"):
                print(f"UID {i} (0x{i:02X}): OK")
                f.append(i)
        except:
            pass
    print("Found:", f if f else "None")
    c.close()
EOF
python3 /tmp/scan.py

# 레지스터 읽기
cat << 'EOF' > /tmp/read_config.py
from pymodbus.client import ModbusSerialClient
c = ModbusSerialClient(port="/dev/ttyUSB0", baudrate=115200, timeout=0.3, retries=1)
c.connect()
uid = 0x53
try:
    r = c.read_holding_registers(address=0x00, count=16, device_id=uid)
    if hasattr(r, "registers"):
        print(f"Config 0x00~0x0F: {[hex(x) for x in r.registers]}")
except Exception as e:
    print(f"Error: {e}")
try:
    r = c.read_holding_registers(address=0x34, count=19, device_id=uid)
    if hasattr(r, "registers"):
        print(f"Data 0x34~0x46: {r.registers}")
except Exception as e:
    print(f"Error: {e}")
c.close()
EOF
python3 /tmp/read_config.py
```

---

## Related Files

- `/home/yjk/jetson-food-ai/vibration_sensor_simple.py` - 진동센서 프로그램
- `/home/yjk/jetson-food-ai/vibration_config.json` - 설정 파일
- `/home/hr_dku_001/data/vibration_data/` - CSV 데이터 저장 위치

---

## Next Steps

1. WitMotion 답변 대기
2. 답변 받으면 진동 분석 모드 활성화 시도
3. Factory reset 시도
4. 그래도 안 되면 센서 교체 검토
