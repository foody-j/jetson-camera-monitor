# MQTT 진동 제어 가이드

## 개요

Jetson 1 및 Jetson 2에서 MQTT 메시지로 진동센서 프로그램을 원격 제어할 수 있습니다.

## MQTT 토픽

**제어 토픽:**
```
calibration/vibration/control
```

## 메시지 형식 (유연한 파싱)

### 1. JSON 형태 (권장)

**시작 명령:**
```json
{
  "command": "START",
  "source": "robot_pc",
  "timestamp": "2025-11-13 15:00:00"
}
```

**종료 명령:**
```json
{
  "command": "STOP",
  "source": "robot_pc",
  "timestamp": "2025-11-13 15:10:00"
}
```

**지원되는 키:**
- `command` (권장)
- `cmd`
- `action`
- `control`
- `status`

### 2. 단순 문자열 형태

**시작:**
```
START
```

**종료:**
```
STOP
```

### 3. 지원되는 키워드

**시작 키워드:** START, BEGIN, ON, OPEN, RUN
**종료 키워드:** STOP, END, OFF, CLOSE, QUIT

---

## 동작 방식

### Jetson 1 & 2 공통:

1. **MQTT 메시지 수신**
   - 토픽: `calibration/vibration/control` 구독
   - 메시지 파싱 (JSON or 단순 문자열)
   - 키워드 인식 (대소문자 무관)

2. **START 명령 수신 시**
   - `vibration_sensor_simple.py` 프로세스 시작
   - 자동으로 데이터 수집 시작 (CSV 저장)
   - 프로세스 PID 추적

3. **STOP 명령 수신 시**
   - 진동센서 프로세스 종료 (SIGTERM)
   - 3초 타임아웃 후 강제 종료 (SIGKILL)
   - CSV 파일 자동 저장됨

4. **데이터 저장 위치**
   ```
   ~/data/vibration_data/
   ├── 20251113_150000_UID50_vibration.csv
   ├── 20251113_150000_UID51_vibration.csv
   └── 20251113_150000_UID52_vibration.csv
   ```

---

## 테스트 방법

### 로봇 PC에서 테스트

**1. JSON 형태로 시작 명령 발행:**
```bash
mosquitto_pub -h localhost -t "calibration/vibration/control" \
  -m '{"command":"START","source":"robot_pc","timestamp":"2025-11-13 15:00:00"}'
```

**2. 10분 후 종료 명령 발행:**
```bash
mosquitto_pub -h localhost -t "calibration/vibration/control" \
  -m '{"command":"STOP","source":"robot_pc","timestamp":"2025-11-13 15:10:00"}'
```

**3. 단순 문자열로 테스트:**
```bash
# 시작
mosquitto_pub -h localhost -t "calibration/vibration/control" -m "START"

# 종료
mosquitto_pub -h localhost -t "calibration/vibration/control" -m "STOP"
```

### Jetson에서 로그 확인

```bash
# 실시간 로그 모니터링
sudo journalctl -u jetson1-monitor -f  # Jetson1
sudo journalctl -u jetson2-monitor -f  # Jetson2

# 진동 관련 로그만 필터링
sudo journalctl -u jetson1-monitor -f | grep "진동"
```

**정상 동작 시 로그 예시:**
```
============================================================
[진동 MQTT] 수신 메시지 (topic: calibration/vibration/control):
  Raw: {"command":"START","source":"robot_pc","timestamp":"2025-11-13 15:00:00"}
  Parsed JSON: {'command': 'START', 'source': 'robot_pc', 'timestamp': '2025-11-13 15:00:00'}
  Command key 'command': START
[진동 MQTT] ✓ 시작 명령 인식
[진동] 프로세스 시작 (PID: 12345)
============================================================
```

---

## 에러 처리

### 1. 중복 시작 시도
```
[진동] 이미 실행 중입니다
```
→ 정상 동작, 무시됨

### 2. 프로세스 없이 종료 시도
```
[진동] 실행 중인 프로세스 없음
```
→ 정상 동작, 무시됨

### 3. 알 수 없는 명령
```
[진동 MQTT] ⚠ 알 수 없는 명령: PAUSE
```
→ 무시됨, 프로그램 정상 동작

### 4. 파싱 오류
```
[진동 MQTT] 파싱 오류: ...
```
→ 에러 로그 출력 후 무시, 프로그램 크래시 안 함

---

## 프로세스 확인

```bash
# 진동센서 프로세스 확인
ps aux | grep vibration_sensor

# 출력 예시
hr_dku_002  12345  vibration_sensor_simple.py
```

---

## GUI 버튼과의 관계

- GUI "진동 체크" 버튼: 여전히 작동 (수동 실행)
- MQTT 제어: 자동 실행/종료
- 둘 다 동일한 메서드 (`start_vibration_check`, `stop_vibration_check`) 사용
- 중복 실행 방지 로직 있음

---

## 주의사항

1. **MQTT 연결 필수**
   - `config.json`에서 `mqtt_enabled: true`
   - 로봇 PC MQTT Broker 실행 중

2. **진동센서 하드웨어 필수**
   - USB-RS485 변환기 연결 (`/dev/ttyUSB0`)
   - 진동센서 3개 (UID 0x50, 0x51, 0x52)

3. **데이터 손실 방지**
   - STOP 명령 시 자동으로 CSV 파일 저장됨
   - 강제 종료 시에도 flush 처리됨

4. **디버깅**
   - 모든 MQTT 메시지가 로그로 출력됨
   - 파싱 과정이 상세히 기록됨
   - 에러 발생 시 traceback 출력

---

## 통합 시나리오

### 캘리브레이션 프로세스

```
1. 로봇 PC → Jetson: "calibration/vibration/control" {"command":"START"}
   → Jetson1, Jetson2 동시에 진동 체크 시작

2. 10분간 캘리브레이션 작업 수행
   → 진동 데이터 자동 수집 및 CSV 저장

3. 로봇 PC → Jetson: "calibration/vibration/control" {"command":"STOP"}
   → Jetson1, Jetson2 동시에 진동 체크 종료
   → 데이터 자동 저장 완료
```

---

## 설정 파일

**config.json (Jetson1):**
```json
{
  "mqtt_enabled": true,
  "mqtt_broker": "192.168.0.14",
  "mqtt_port": 1883
}
```

**config_jetson2.json (Jetson2):**
```json
{
  "mqtt_enabled": true,
  "mqtt_broker": "192.168.0.14",
  "mqtt_port": 1883
}
```

---

## 문제 해결

### MQTT 메시지가 안 받아짐
```bash
# Broker 확인
sudo systemctl status mosquitto

# 토픽 수신 테스트
mosquitto_sub -h localhost -t "calibration/vibration/control" -v
```

### 프로세스가 안 시작됨
```bash
# 파일 존재 확인
ls -l ~/jetson-food-ai/vibration_sensor_simple.py

# 수동 실행 테스트
cd ~/jetson-food-ai
python3 vibration_sensor_simple.py
```

### 프로세스가 안 종료됨
```bash
# 강제 종료
pkill -9 -f vibration_sensor_simple.py
```
