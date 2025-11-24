# MQTT API 레퍼런스

**버전**: 2.1 (통합 상태 토픽)
**최종 업데이트**: 2025-11-24

## 목차

- [브로커 설정](#브로커-설정)
- [젯슨1 토픽](#젯슨1-토픽)
- [젯슨2 토픽](#젯슨2-토픽)
- [진동 센서 제어](#진동-센서-제어)
- [메시지 형식](#메시지-형식)
- [설정 파일](#설정-파일)

---

## 브로커 설정

- **호스트**: `localhost` (로봇 PC) 또는 로봇 PC IP 주소
- **포트**: `1883`
- **QoS**: `1` (최소 1회 전달 보장)
- **Keep-Alive**: `60`초

---

## 젯슨1 토픽

### 구독 토픽 (로봇 PC → 젯슨1)

#### 1. `stirfry/pot1/food_type`

**목적**: POT1 음식 종류 설정 및 자동 녹화 시작

**메시지 형식**: 일반 텍스트 문자열 (제한 없음)

**예시**:
```
"kimchi"
"bacon"
"볶음밥"
"mixed_vegetables"
```

**동작**:
- POT1이 녹화 중이 아닌 경우: 자동 녹화 시작
- POT1이 이미 녹화 중인 경우: 메타데이터 이벤트로 저장

**발행 예시**:
```bash
mosquitto_pub -h localhost -t "stirfry/pot1/food_type" -m "kimchi"
```

---

#### 2. `stirfry/pot1/control`

**목적**: POT1 녹화 제어 (중지만 가능)

**메시지 형식**: `"stop"`

**동작**:
- POT1이 녹화 중인 경우: 자동 녹화 중지 및 메타데이터 저장
- POT1이 녹화 중이 아닌 경우: 무시

**발행 예시**:
```bash
mosquitto_pub -h localhost -t "stirfry/pot1/control" -m "stop"
```

---

#### 3. `stirfry/pot2/food_type`

**목적**: POT2 음식 종류 설정 및 자동 녹화 시작

**메시지 형식**: 일반 텍스트 문자열 (제한 없음)

**예시**:
```
"kimchi"
"bacon"
"야채볶음"
```

**동작**: POT1과 동일 (POT2에 적용)

**발행 예시**:
```bash
mosquitto_pub -h localhost -t "stirfry/pot2/food_type" -m "bacon"
```

---

#### 4. `stirfry/pot2/control`

**목적**: POT2 녹화 제어 (중지만 가능)

**메시지 형식**: `"stop"`

**동작**: POT1 control과 동일 (POT2에 적용)

**발행 예시**:
```bash
mosquitto_pub -h localhost -t "stirfry/pot2/control" -m "stop"
```

---

### 발행 토픽 (젯슨1 → 로봇 PC)

#### 1. `jetson1/status` **(통합 상태 토픽 - 권장)**

**목적**: 젯슨1의 모든 상태 정보를 하나의 메시지로 발행

**메시지 형식**: JSON

```json
{
  "device_id": "jetson1",
  "device_name": "Jetson1_StirFry_Station",
  "device_location": "kitchen_stirfry",
  "ip_address": "192.168.0.15",
  "timestamp": "2025-11-24 14:00:00",
  "person_detected": true,
  "motion_detected": true,
  "relay_enabled": true,
  "ai_mode": false,
  "recording": {
    "pot1": false,
    "pot2": false
  },
  "system_metrics": {
    "cpu_usage": 45.2,
    "memory_usage": 62.1,
    "gpu_usage": 78.5,
    "disk_usage": 55.0,
    "temperature": 48.5
  }
}
```

**필드 설명**:
- `person_detected`: 사람 감지 여부 (YOLO, 신뢰도 > 0.7)
- `motion_detected`: 움직임 감지 여부
- `relay_enabled`: SSR 릴레이 상태 (true=ON, false=OFF)
- `ai_mode`: AI 시스템 준비 상태 (config: `ai_mode_enabled`)
- `recording.pot1`: POT1 녹화 중 여부
- `recording.pot2`: POT2 녹화 중 여부
- `system_metrics`: 시스템 리소스 사용량

**발행 주기**: 2초마다 (config: `mqtt_publish_interval`)

**구독 예시**:
```bash
mosquitto_sub -h localhost -t "jetson1/status" -v
```

---

#### 2. `jetson1/system/ai_mode` **(Legacy)**

> **참고**: 이 토픽은 하위 호환성을 위해 유지됩니다. 새로운 구현은 `jetson1/status` 통합 토픽 사용을 권장합니다.

**목적**: AI 모드 상태 발행

**메시지 형식**: JSON

```json
{
  "device_id": "jetson1",
  "device_name": "Jetson1_StirFry_Station",
  "message": "ON",
  "timestamp": "2025-11-24 14:00:00"
}
```

**message 값**:
- `"ON"`: AI 시스템 준비 완료 (config: `ai_mode_enabled=true`)
- `"OFF"`: AI 시스템 준비 안됨 (config: `ai_mode_enabled=false`)

**발행 주기**: MQTT 연결 시 단 1회

---

#### 3. `frying_ai/jetson1/robot/control` **(Legacy - 하위 호환)**

> **참고**: 이 토픽은 하위 호환성을 위해 계속 발행됩니다. 로봇 PC 전원 제어에 사용됩니다. 새로운 구현은 `jetson1/status`의 `person_detected` 필드 사용을 권장합니다.

**목적**: 사람 감지 상태 발행 (로봇 PC 전원 제어)

**메시지 형식**: JSON

**ON 메시지**:
```json
{
  "command": "ON",
  "source": "auto_start_system",
  "person_detected": true,
  "timestamp": "2025-11-24 14:00:00",
  "device_id": "jetson1",
  "device_name": "Jetson1_StirFry_Station",
  "location": "kitchen_stirfry"
}
```

**OFF 메시지**:
```json
{
  "command": "OFF",
  "source": "auto_start_system",
  "person_detected": false,
  "timestamp": "2025-11-24 14:30:00",
  "device_id": "jetson1",
  "device_name": "Jetson1_StirFry_Station",
  "location": "kitchen_stirfry"
}
```

**발행 조건**:
- ON: YOLO로 사람 감지 시 (신뢰도 > 0.7), 2초간 유지
- OFF: 30초 동안 사람 미감지 시

---

#### 4. `jetson1/relay/status` **(Legacy)**

> **참고**: 이 토픽은 하위 호환성을 위해 유지됩니다. 새로운 구현은 `jetson1/status`의 `relay_enabled` 필드 사용을 권장합니다.

**목적**: 릴레이 상태 발행 (젯슨2와 동기화)

**메시지 형식**: JSON

```json
{
  "device_id": "jetson1",
  "relay_status": "ON",
  "timestamp": "2025-11-24 14:00:00"
}
```

**relay_status 값**:
- `"ON"`: 릴레이 켜짐 (로봇 PC 전원 ON)
- `"OFF"`: 릴레이 꺼짐 (로봇 PC 전원 OFF)

---

## 젯슨2 토픽

### 구독 토픽 (로봇 PC → 젯슨2)

#### 1. `frying/pot1/food_type`

**목적**: POT1 음식 종류 설정 및 자동 데이터 수집 시작

**메시지 형식**: 일반 텍스트 문자열 (제한 없음)

**예시**:
```
"chicken"
"shrimp"
"potato"
"치킨"
"새우"
```

**동작**:
- POT1이 수집 중이 아닌 경우: 자동 수집 시작 (튀김 POT1 + 관찰 카메라 2개)
- POT1이 이미 수집 중인 경우: 메타데이터 이벤트로 저장

**카메라**:
- camera_0: 튀김 왼쪽 (POT1)
- camera_2: 관찰 왼쪽 (공유)
- camera_3: 관찰 오른쪽 (공유)

**발행 예시**:
```bash
mosquitto_pub -h localhost -t "frying/pot1/food_type" -m "chicken"
```

---

#### 2. `frying/pot1/control`

**목적**: POT1 데이터 수집 제어 (중지만 가능)

**메시지 형식**: `"stop"`

**동작**:
- POT1이 수집 중인 경우: 자동 수집 중지 및 메타데이터 저장
- POT1이 수집 중이 아닌 경우: 무시

**발행 예시**:
```bash
mosquitto_pub -h localhost -t "frying/pot1/control" -m "stop"
```

---

#### 3. `frying/pot2/food_type`

**목적**: POT2 음식 종류 설정 및 자동 데이터 수집 시작

**메시지 형식**: 일반 텍스트 문자열 (제한 없음)

**동작**: POT1과 동일 (POT2에 적용)

**카메라**:
- camera_1: 튀김 오른쪽 (POT2)
- camera_2: 관찰 왼쪽 (공유)
- camera_3: 관찰 오른쪽 (공유)

**발행 예시**:
```bash
mosquitto_pub -h localhost -t "frying/pot2/food_type" -m "shrimp"
```

---

#### 4. `frying/pot2/control`

**목적**: POT2 데이터 수집 제어 (중지만 가능)

**메시지 형식**: `"stop"`

**동작**: POT1 control과 동일 (POT2에 적용)

**발행 예시**:
```bash
mosquitto_pub -h localhost -t "frying/pot2/control" -m "stop"
```

---

#### 5. `frying/pot1/oil_temp`

**목적**: POT1 기름 온도 수신

**메시지 형식**: 실수 문자열 (섭씨)

**예시**: `"165.5"`, `"180.0"`

**동작**: POT1 수집 활성화 시 메타데이터에 저장

**발행 예시**:
```bash
mosquitto_pub -h localhost -t "frying/pot1/oil_temp" -m "180.5"
```

---

#### 6. `frying/pot1/probe_temp`

**목적**: POT1 탐침(음식 중심부) 온도 수신

**메시지 형식**: 실수 문자열 (섭씨)

**예시**: `"65.0"`, `"75.0"`

**동작**:
- POT1 수집 활성화 시 메타데이터에 저장
- **자동 완료**: 75.0°C 이상일 때 POT1 자동 완료 마킹

**발행 예시**:
```bash
mosquitto_pub -h localhost -t "frying/pot1/probe_temp" -m "75.0"
```

---

#### 7. `frying/pot2/oil_temp`

**목적**: POT2 기름 온도 수신

**메시지 형식**: 실수 문자열 (섭씨)

**동작**: POT2 수집 활성화 시 메타데이터에 저장

**발행 예시**:
```bash
mosquitto_pub -h localhost -t "frying/pot2/oil_temp" -m "182.0"
```

---

#### 8. `frying/pot2/probe_temp`

**목적**: POT2 탐침(음식 중심부) 온도 수신

**메시지 형식**: 실수 문자열 (섭씨)

**동작**:
- POT2 수집 활성화 시 메타데이터에 저장
- **자동 완료**: 75.0°C 이상일 때 POT2 자동 완료 마킹

**발행 예시**:
```bash
mosquitto_pub -h localhost -t "frying/pot2/probe_temp" -m "76.5"
```

---

#### 9. `jetson1/relay/status` (구독)

**목적**: 젯슨1 릴레이 상태 동기화

**메시지 형식**: JSON

```json
{
  "device_id": "jetson1",
  "relay_status": "ON",
  "timestamp": "2025-11-24 14:00:00"
}
```

**동작**: 젯슨2가 젯슨1의 릴레이 상태를 동기화

---

### 발행 토픽 (젯슨2 → 로봇 PC)

#### 1. `jetson2/status` **(통합 상태 토픽 - 권장)**

**목적**: 젯슨2의 모든 상태 정보를 하나의 메시지로 발행

**메시지 형식**: JSON

```json
{
  "device_id": "jetson2",
  "device_name": "Jetson2_Frying_Station",
  "device_location": "kitchen_frying",
  "ip_address": "192.168.0.16",
  "timestamp": "2025-11-24 14:00:00",
  "basket": {
    "left": "FILLED",
    "right": "EMPTY"
  },
  "pot": {
    "pot1": "EMPTY",
    "pot2": "EMPTY"
  },
  "ai_mode": false
}
```

**필드 설명**:
- `basket.left`: 왼쪽 바구니 상태
  - `"FILLED"`: 바구니에 음식 들어옴
  - `"EMPTY"`: 바구니에서 음식 나감
  - `"NO_BASKET"`: 바구니 없음
  - `"UNKNOWN"`: 상태 알 수 없음
- `basket.right`: 오른쪽 바구니 상태 (왼쪽과 동일)
- `pot.pot1`: POT1 솥 상태
  - `"HAS_FOOD"`: 솥에 음식 있음
  - `"EMPTY"`: 솥이 비어있음
  - *(현재는 placeholder 값, 향후 YOLO 모델로 자동 감지 예정)*
- `pot.pot2`: POT2 솥 상태 (POT1과 동일)
- `ai_mode`: AI 시스템 준비 상태 (config: `ai_mode_enabled`)

**발행 주기**: 2초마다 (config: `mqtt_publish_interval`)

**구독 예시**:
```bash
mosquitto_sub -h localhost -t "jetson2/status" -v
```

---

#### 2. `jetson2/system/ai_mode` **(Legacy)**

> **참고**: 이 토픽은 하위 호환성을 위해 유지됩니다. 새로운 구현은 `jetson2/status` 통합 토픽 사용을 권장합니다.

**목적**: AI 모드 상태 발행

**메시지 형식**: JSON

```json
{
  "device_id": "jetson2",
  "message": "ON",
  "timestamp": "2025-11-24 14:00:00"
}
```

**message 값**:
- `"ON"`: AI 시스템 준비 완료
- `"OFF"`: AI 시스템 준비 안됨

**발행 주기**: MQTT 연결 시 단 1회

---

#### 3. `jetson2/observe/status` **(Legacy)**

> **참고**: 이 토픽은 하위 호환성을 위해 유지됩니다. 새로운 구현은 `jetson2/status`의 `basket` 필드 사용을 권장합니다.

**목적**: 바구니(바스켓) 감지 상태 발행

**메시지 형식**: JSON

```json
{
  "device_id": "jetson2",
  "message": "LEFT:BASKET_IN",
  "timestamp": "2025-11-24 14:00:00"
}
```

**message 값**:
| 값 | 의미 |
|----|------|
| `LEFT:BASKET_IN` | 왼쪽 바구니에 음식 들어옴 |
| `LEFT:BASKET_OUT` | 왼쪽 바구니에서 음식 나감 |
| `LEFT:NO_BASKET` | 왼쪽에 바구니 없음 |
| `RIGHT:BASKET_IN` | 오른쪽 바구니에 음식 들어옴 |
| `RIGHT:BASKET_OUT` | 오른쪽 바구니에서 음식 나감 |
| `RIGHT:NO_BASKET` | 오른쪽에 바구니 없음 |

**발행 조건**: 7개 프레임 투표 결과가 변경될 때만 발행

---

## 진동 센서 제어

### `calibration/vibration/control`

**목적**: 젯슨1, 젯슨2의 진동 센서 원격 제어

**메시지 형식**: JSON 또는 단순 문자열

**JSON 형태 (권장)**:
```json
{
  "command": "START",
  "source": "robot_pc",
  "timestamp": "2025-11-24 15:00:00"
}
```

**단순 문자열 형태**:
```
START
STOP
```

**지원 키워드**:
- 시작: `START`, `BEGIN`, `ON`, `OPEN`, `RUN`
- 종료: `STOP`, `END`, `OFF`, `CLOSE`, `QUIT`

**동작**:
- START: `vibration_sensor_simple.py` 프로세스 시작, CSV 데이터 수집 시작
- STOP: 진동센서 프로세스 종료, CSV 파일 자동 저장

**발행 예시**:
```bash
# JSON 형태
mosquitto_pub -h localhost -t "calibration/vibration/control" \
  -m '{"command":"START","source":"robot_pc"}'

# 단순 문자열
mosquitto_pub -h localhost -t "calibration/vibration/control" -m "START"
```

---

## 메시지 형식

### 메타데이터 JSON (젯슨1 - metadata.json)

```json
{
  "pot": "pot1",
  "session_id": "session_20250124_143052",
  "food_type": "kimchi",
  "start_time": "2025-01-24 14:30:52",
  "end_time": "2025-01-24 14:35:20",
  "duration_seconds": 268.5,
  "frame_count": 250,
  "resolution": {
    "width": 1280,
    "height": 720
  },
  "jpeg_quality": 100,
  "frame_skip": 90,
  "device_id": "jetson1",
  "device_name": "Jetson1_StirFry_Station",
  "camera": "camera_0",
  "events": [
    {
      "timestamp": "2025-01-24 14:30:52.123",
      "type": "session_start",
      "session_id": "session_20250124_143052",
      "food_type": "kimchi"
    },
    {
      "timestamp": "2025-01-24 14:35:20.456",
      "type": "session_end",
      "duration_seconds": 268.5,
      "frame_count": 250
    }
  ]
}
```

---

### 메타데이터 JSON (젯슨2 - session_info.json)

```json
{
  "pot": "pot1",
  "session_id": "session_20250124_143052",
  "food_type": "chicken",
  "start_time": "2025-01-24 14:30:52",
  "end_time": "2025-01-24 14:35:20",
  "duration_sec": 268.5,
  "collection_interval": 3,
  "completion_marked": true,
  "completion_info": {
    "method": "auto (probe_temp >= 75.0°C)",
    "timestamp": "2025-01-24 14:34:15",
    "probe_temp": 75.5,
    "oil_temp": 180.0,
    "elapsed_time_sec": 203.2
  },
  "cameras_used": [0, 2, 3],
  "total_frames_saved": 350,
  "raw_metadata": [
    {
      "timestamp": "2025-01-24 14:30:55.123",
      "type": "oil_temperature",
      "position": "left",
      "value": 165.5,
      "unit": "celsius"
    },
    {
      "timestamp": "2025-01-24 14:31:00.456",
      "type": "probe_temperature",
      "position": "left",
      "value": 45.0,
      "unit": "celsius"
    }
  ],
  "metadata_count": 125
}
```

---

## 설정 파일

### 젯슨1 설정 (jetson1_monitoring/config.json)

```json
{
  "mqtt_enabled": true,
  "mqtt_broker": "192.168.x.x",
  "mqtt_port": 1883,
  "mqtt_topic_status": "status",
  "mqtt_topic_ai_mode": "jetson1/system/ai_mode",
  "mqtt_topic_stirfry_pot1_food_type": "stirfry/pot1/food_type",
  "mqtt_topic_stirfry_pot1_control": "stirfry/pot1/control",
  "mqtt_topic_stirfry_pot2_food_type": "stirfry/pot2/food_type",
  "mqtt_topic_stirfry_pot2_control": "stirfry/pot2/control",
  "mqtt_topic_vibration_control": "calibration/vibration/control",
  "mqtt_qos": 1,
  "mqtt_client_id": "jetson1_ai",
  "mqtt_publish_interval": 2,
  "stirfry_save_dir": "AI_Data/StirFryData",
  "stirfry_frame_skip": 90,
  "stirfry_jpeg_quality": 100,
  "ai_mode_enabled": false
}
```

**주요 필드**:
- `mqtt_enabled`: MQTT 활성화 여부
- `mqtt_broker`: MQTT 브로커 주소 (로봇 PC IP)
- `mqtt_client_id`: 클라이언트 고유 ID
- `mqtt_topic_status`: 통합 상태 토픽 (기본값: "status", 전체: "jetson1/status")
- `mqtt_publish_interval`: 상태 발행 주기 (초)
- `stirfry_frame_skip`: 프레임 스킵 (90 = 3초마다 1장, 30fps 기준)
- `ai_mode_enabled`: AI 완성 여부 (완성 시 true)

---

### 젯슨2 설정 (jetson2_frying_ai/config_jetson2.json)

```json
{
  "mqtt_enabled": true,
  "mqtt_broker": "192.168.x.x",
  "mqtt_port": 1883,
  "mqtt_topic_status": "status",
  "mqtt_topic_ai_mode": "jetson2/system/ai_mode",
  "mqtt_topic_frying_pot1_food_type": "frying/pot1/food_type",
  "mqtt_topic_frying_pot1_control": "frying/pot1/control",
  "mqtt_topic_frying_pot2_food_type": "frying/pot2/food_type",
  "mqtt_topic_frying_pot2_control": "frying/pot2/control",
  "mqtt_topic_pot1_oil_temp": "frying/pot1/oil_temp",
  "mqtt_topic_pot1_probe_temp": "frying/pot1/probe_temp",
  "mqtt_topic_pot2_oil_temp": "frying/pot2/oil_temp",
  "mqtt_topic_pot2_probe_temp": "frying/pot2/probe_temp",
  "mqtt_topic_vibration_control": "calibration/vibration/control",
  "mqtt_topic_jetson1_relay": "jetson1/relay/status",
  "mqtt_qos": 1,
  "mqtt_client_id": "jetson2_ai",
  "mqtt_publish_interval": 2,
  "data_collection_interval": 3,
  "jpeg_quality": 100,
  "target_probe_temp": 75.0,
  "ai_mode_enabled": false
}
```

**주요 필드**:
- `mqtt_topic_status`: 통합 상태 토픽 (기본값: "status", 전체: "jetson2/status")
- `mqtt_publish_interval`: 상태 발행 주기 (초)
- `data_collection_interval`: 데이터 수집 간격 (초)
- `target_probe_temp`: 목표 탐침 온도 (자동 완료 기준)

---

## 토픽 한눈에 보기

### 젯슨1 토픽 요약

| 방향 | 토픽 | 목적 | 형식 | 비고 |
|------|------|------|------|------|
| ← 구독 | `stirfry/pot1/food_type` | POT1 시작 | 문자열 | |
| ← 구독 | `stirfry/pot1/control` | POT1 중지 | `"stop"` | |
| ← 구독 | `stirfry/pot2/food_type` | POT2 시작 | 문자열 | |
| ← 구독 | `stirfry/pot2/control` | POT2 중지 | `"stop"` | |
| ← 구독 | `calibration/vibration/control` | 진동 제어 | JSON/문자열 | |
| → 발행 | **`jetson1/status`** | **통합 상태** | **JSON** | **권장** |
| → 발행 | `jetson1/system/ai_mode` | AI 모드 | JSON | Legacy |
| → 발행 | `frying_ai/jetson1/robot/control` | 사람 감지 | JSON | Legacy |
| → 발행 | `jetson1/relay/status` | 릴레이 상태 | JSON | Legacy |

### 젯슨2 토픽 요약

| 방향 | 토픽 | 목적 | 형식 | 비고 |
|------|------|------|------|------|
| ← 구독 | `frying/pot1/food_type` | POT1 시작 | 문자열 | |
| ← 구독 | `frying/pot1/control` | POT1 중지 | `"stop"` | |
| ← 구독 | `frying/pot2/food_type` | POT2 시작 | 문자열 | |
| ← 구독 | `frying/pot2/control` | POT2 중지 | `"stop"` | |
| ← 구독 | `frying/pot1/oil_temp` | POT1 기름 온도 | 실수 문자열 | |
| ← 구독 | `frying/pot1/probe_temp` | POT1 탐침 온도 | 실수 문자열 | |
| ← 구독 | `frying/pot2/oil_temp` | POT2 기름 온도 | 실수 문자열 | |
| ← 구독 | `frying/pot2/probe_temp` | POT2 탐침 온도 | 실수 문자열 | |
| ← 구독 | `calibration/vibration/control` | 진동 제어 | JSON/문자열 | |
| ← 구독 | `jetson1/relay/status` | 릴레이 동기화 | JSON | |
| → 발행 | **`jetson2/status`** | **통합 상태** | **JSON** | **권장** |
| → 발행 | `jetson2/system/ai_mode` | AI 모드 | JSON | Legacy |
| → 발행 | `jetson2/observe/status` | 바구니 상태 | JSON | Legacy |

---

## 버전 히스토리

### v2.1 (2025-11-24)
- **통합 상태 토픽 추가**: `jetson1/status`, `jetson2/status`
- 모든 상태 정보를 단일 JSON 메시지로 발행
- 솥 상태(pot status) 필드 추가 (젯슨2)
- 네트워크 효율성 향상 (메시지 수 감소)
- 기존 개별 토픽은 Legacy로 유지 (하위 호환성)

### v2.0 (2025-11-24)
- POT1/POT2 독립 제어
- 온도 기반 자동 완료
- 진동 센서 MQTT 제어
- 관찰 카메라 공유

---

**버전**: 2.1
**최종 업데이트**: 2025-11-24
**호환**: Jetson Software v2.0+ (POT1/POT2 분리, 통합 토픽)
