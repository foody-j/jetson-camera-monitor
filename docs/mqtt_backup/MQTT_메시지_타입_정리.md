# MQTT 메시지 타입 정리 (Jetson ↔ 로봇 PC)

## 📋 개요

이 문서는 Jetson1, Jetson2와 로봇 PC 간 주고받는 MQTT 메시지 타입을 정리한 문서입니다.

**MQTT Broker 위치**: 로봇 PC (192.168.x.x:1883)

---

## 🤖 Jetson1 → 로봇 PC (발행)

### 1. 사람 감지 메시지
**토픽**: `frying_ai/jetson1/robot/control`
**발행 시점**: 사람 감지 시 ON, 일정 시간 후 OFF

#### ON 메시지 (사람 감지됨):
```json
{
  "command": "ON",
  "source": "auto_start_system",
  "person_detected": true,
  "timestamp": "2025-11-10 17:00:00",
  "device_id": "jetson1",
  "device_name": "Jetson1_StirFry_Station",
  "location": "kitchen_stirfry"
}
```

#### OFF 메시지 (사람 사라짐):
```json
{
  "command": "OFF",
  "source": "auto_start_system",
  "person_detected": false,
  "timestamp": "2025-11-10 17:30:00",
  "device_id": "jetson1",
  "device_name": "Jetson1_StirFry_Station",
  "location": "kitchen_stirfry"
}
```

**발행 조건**:
- ON: YOLO로 사람 감지 시 (신뢰도 > 0.7)
- OFF: 30초 동안 사람 미감지 시 (config: detection_hold_sec)

---

### 2. AI 모드 상태
**토픽**: `jetson1/system/ai_mode`
**발행 시점**: MQTT 연결 시 단 1회

```json
{
  "device_id": "jetson1",
  "device_name": "Jetson1_StirFry_Station",
  "message": "ON",  // 또는 "OFF"
  "timestamp": "2025-11-10 17:00:00"
}
```

**message 값**:
- `"ON"`: AI 완성됨 (config: ai_mode_enabled=true)
- `"OFF"`: AI 미완성 (config: ai_mode_enabled=false)

**용도**: 로봇 PC가 "이 Jetson에 AI가 장착되었는지" 파악

---

## 🍤 Jetson2 → 로봇 PC (발행)

### 1. 바구니(바켓) 감지 상태
**토픽**: `jetson2/observe/status`
**발행 시점**: 바구니 상태 변경 시 (filled/empty 변화)

#### 왼쪽 바구니 상태:
```json
{
  "device_id": "jetson2",
  "message": "LEFT:BASKET_IN",  // 또는 "LEFT:BASKET_OUT", "LEFT:NO_BASKET"
  "timestamp": "2025-11-10 17:00:00"
}
```

#### 오른쪽 바구니 상태:
```json
{
  "device_id": "jetson2",
  "message": "RIGHT:BASKET_IN",  // 또는 "RIGHT:BASKET_OUT", "RIGHT:NO_BASKET"
  "timestamp": "2025-11-10 17:00:00"
}
```

**message 값 종류**:
| 값 | 의미 |
|----|------|
| `LEFT:BASKET_IN` | 왼쪽 바구니에 음식 들어옴 (filled) |
| `LEFT:BASKET_OUT` | 왼쪽 바구니에서 음식 나감 (empty) |
| `LEFT:NO_BASKET` | 왼쪽에 바구니 없음 |
| `RIGHT:BASKET_IN` | 오른쪽 바구니에 음식 들어옴 |
| `RIGHT:BASKET_OUT` | 오른쪽 바구니에서 음식 나감 |
| `RIGHT:NO_BASKET` | 오른쪽에 바구니 없음 |

**발행 조건**:
- 7개 프레임 투표(voting) 결과가 변경될 때만 발행
- 상태 변화가 없으면 발행하지 않음

---

### 2. 튀김 상태 (현재 미사용)
**토픽**: `jetson2/frying/status`
**발행 시점**: (아직 구현 안 됨)

```json
{
  "device_id": "jetson2",
  "message": "FRYING_STATUS",
  "timestamp": "2025-11-10 17:00:00"
}
```

**참고**: 튀김 AI는 현재 데이터 수집 단계이며, 아직 실시간 상태 발행 기능 없음

---

### 3. AI 모드 상태
**토픽**: `jetson2/system/ai_mode`
**발행 시점**: MQTT 연결 시 단 1회

```json
{
  "device_id": "jetson2",
  "message": "ON",  // 또는 "OFF"
  "timestamp": "2025-11-10 17:00:00"
}
```

**message 값**:
- `"ON"`: AI 완성됨 (config: ai_mode_enabled=true)
- `"OFF"`: AI 미완성 (config: ai_mode_enabled=false)

**용도**: 로봇 PC가 "이 Jetson에 AI가 장착되었는지" 파악

---

## 📨 로봇 PC → Jetson2 (발행)

### 1. 왼쪽 기름 온도
**토픽**: `frying/oil_temp/left`
**Payload**: `"180.5"` (문자열, 단위: °C)

Jetson2가 수신 → 화면에 표시 + 데이터 수집 시 메타데이터 저장

---

### 2. 오른쪽 기름 온도
**토픽**: `frying/oil_temp/right`
**Payload**: `"182.0"` (문자열, 단위: °C)

Jetson2가 수신 → 화면에 표시 + 데이터 수집 시 메타데이터 저장

---

### 3. 왼쪽 탐침 온도
**토픽**: `frying/probe_temp/left`
**Payload**: `"75.0"` (문자열, 단위: °C)

Jetson2가 수신 → 화면에 표시 + 데이터 수집 시 메타데이터 저장

**특수 기능**:
- 탐침 온도가 목표 온도(75°C) 도달 시 자동으로 "완료 시점" 마킹
- 메타데이터에 completion 정보 저장

---

### 4. 오른쪽 탐침 온도
**토픽**: `frying/probe_temp/right`
**Payload**: `"76.5"` (문자열, 단위: °C)

Jetson2가 수신 → 화면에 표시 + 데이터 수집 시 메타데이터 저장

---

### 5. 튀김 음식 종류 - 자동 시작 (Jetson2용)
**토픽**: `frying/food_type`
**Payload**: `"chicken"` (문자열)
**방향**: 로봇 PC → Jetson2

**제한 없음**: 로봇 PC에서 보내는 **아무 문자열이나 가능**
- 예시: `"chicken"`, `"새우튀김"`, `"french_fries"`, `"custom_food_123"` 등

**동작**:
- Jetson2가 수신 → **자동으로 수집 시작** (튀김솥 2개 + 바스켓 2개, 총 4대 카메라)
- 3초마다 1장씩 저장 (4대 카메라 동시)
- 폴더 구조:
  - `~/AI_Data/FryingData/SESSION_ID/camera_0|1/`
  - `~/AI_Data/BucketData/SESSION_ID/camera_2|3/`

---

### 6. 볶음 음식 종류 - 자동 시작 (Jetson1용)
**토픽**: `stirfry/food_type`
**Payload**: `"볶음밥"` (문자열)
**방향**: 로봇 PC → Jetson1

**제한 없음**: 로봇 PC에서 보내는 **아무 문자열이나 가능**
- 예시: `"볶음밥"`, `"짜장"`, `"짬뽕"`, `"야채볶음"` 등

**동작**:
- Jetson1이 수신 → **자동으로 녹화 시작**
- 3초마다 1장씩 저장 (왼쪽/오른쪽 카메라)
- 폴더 구조: `~/StirFry_Data/SESSION_ID/FOOD_TYPE/left|right/`

### 7. 볶음 종료 신호 (Jetson1용)
**토픽**: `stirfry/control`
**Payload**: `"stop"` (문자열)
**방향**: 로봇 PC → Jetson1

**동작**:
- Jetson1이 수신 → **자동으로 녹화 중지**
- metadata.json 파일 생성
- 세션 정보 (시작/종료 시간, 프레임 수, 음식 종류 등) 저장

### 8. 튀김 종료 신호 (Jetson2용)
**토픽**: `frying/control`
**Payload**: `"stop"` (문자열)
**방향**: 로봇 PC → Jetson2

**동작**:
- Jetson2가 수신 → **자동으로 수집 중지** (튀김솥 + 바스켓 모두)
- metadata.json 파일 생성
- 세션 정보 저장

---

**Note**: 튀김 음식 종류 (`frying/food_type`)는 위의 **섹션 4**에 이미 정의됨 (자동 시작 포함)

---

## 📊 메시지 흐름도

```
┌─────────────┐                    ┌─────────────┐
│   Jetson1   │                    │  로봇 PC     │
│  (볶음감지)  │                    │ (MQTT Broker)│
└─────────────┘                    └─────────────┘
       │                                  ▲
       │  사람 감지 ON/OFF                │
       └──────────────────────────────────┘
         frying_ai/jetson1/robot/control

       │  AI 모드 상태 (1회)             │
       └──────────────────────────────────┘
         jetson1/system/ai_mode


┌─────────────┐                    ┌─────────────┐
│   Jetson2   │◄───────────────────┤  로봇 PC     │
│  (튀김 AI)   │   온도 센서 데이터    │ (MQTT Broker)│
└─────────────┘                    └─────────────┘
       │                                  ▲
       │  바구니 상태 변화                 │
       └──────────────────────────────────┘
         jetson2/observe/status

       │  AI 모드 상태 (1회)             │
       └──────────────────────────────────┘
         jetson2/system/ai_mode

       ▼
    로봇 PC → Jetson2:
    - frying/oil_temp/left
    - frying/oil_temp/right
    - frying/probe_temp/left
    - frying/probe_temp/right
    - frying/food_type
```

---

## 🔧 로봇 PC에서 구독 방법

### Python (paho-mqtt) 예시:

```python
import paho.mqtt.client as mqtt
import json

def on_connect(client, userdata, flags, rc):
    print(f"MQTT Broker 연결됨: {rc}")

    # Jetson1 사람 감지 구독
    client.subscribe("frying_ai/jetson1/robot/control")

    # Jetson2 바구니 상태 구독
    client.subscribe("jetson2/observe/status")

    # 모든 Jetson AI 모드 구독 (wildcard)
    client.subscribe("+/system/ai_mode")

def on_message(client, userdata, msg):
    print(f"토픽: {msg.topic}")

    try:
        # JSON 메시지 파싱
        data = json.loads(msg.payload.decode())
        print(f"메시지: {data}")

        # 토픽별 처리
        if msg.topic == "frying_ai/jetson1/robot/control":
            # 사람 감지 처리
            if data.get("command") == "ON":
                print("✅ 사람 감지됨 - 로봇 시작")
            else:
                print("⏸️ 사람 사라짐 - 로봇 대기")

        elif msg.topic == "jetson2/observe/status":
            # 바구니 상태 처리
            message = data.get("message", "")
            if "BASKET_IN" in message:
                print("🥘 바구니에 음식 들어옴")
            elif "BASKET_OUT" in message:
                print("✅ 바구니에서 음식 나감")

        elif "/system/ai_mode" in msg.topic:
            # AI 모드 확인
            device_id = data.get("device_id")
            status = data.get("message")
            print(f"🤖 {device_id} AI 상태: {status}")

    except json.JSONDecodeError:
        # JSON이 아닌 단순 문자열
        print(f"메시지: {msg.payload.decode()}")

# MQTT 클라이언트 설정
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

# Broker 연결
client.connect("192.168.0.14", 1883, 60)
client.loop_forever()
```

---

### 온도/음식 정보 발행 (로봇 PC):

```python
import paho.mqtt.client as mqtt
import time

client = mqtt.Client()
client.connect("localhost", 1883, 60)  # 로봇 PC는 localhost

# 온도 정보 발행
while True:
    # 왼쪽 기름 온도
    client.publish("frying/oil_temp/left", "180.5", qos=1)

    # 왼쪽 탐침 온도
    client.publish("frying/probe_temp/left", "75.0", qos=1)

    # 오른쪽 기름 온도
    client.publish("frying/oil_temp/right", "182.0", qos=1)

    # 오른쪽 탐침 온도
    client.publish("frying/probe_temp/right", "76.5", qos=1)

    # 음식 종류
    client.publish("frying/food_type", "chicken", qos=1)

    time.sleep(1)  # 1초마다 발행
```

---

## 🧪 테스트 방법

### 방법 1: Python 테스트 툴 사용 (추천)

```bash
cd ~/jetson-food-ai
python3 test_mqtt_publish.py

# 대화형 메뉴:
# 1. Broker IP 입력 (예: 192.168.0.14)
# 2. 메시지 타입 선택
# 3. 자동으로 올바른 형식의 JSON 발행
```

**테스트 가능한 메시지**:
- Jetson1 AI Mode
- Jetson2 AI Mode
- Jetson2 Basket Status (LEFT/RIGHT)
- Custom Topic (자유 입력)

---

### 방법 2: mosquitto_pub 사용

```bash
# Jetson1 사람 감지 ON 테스트
mosquitto_pub -h 192.168.0.14 -t "frying_ai/jetson1/robot/control" \
  -m '{"command":"ON","source":"auto_start_system","person_detected":true,"timestamp":"2025-11-10 21:00:00","device_id":"jetson1"}'

# Jetson2 AI 모드 ON 테스트
mosquitto_pub -h 192.168.0.14 -t "jetson2/system/ai_mode" \
  -m '{"device_id":"jetson2","message":"ON","timestamp":"2025-11-10 21:00:00"}'

# Jetson2 바구니 상태 테스트
mosquitto_pub -h 192.168.0.14 -t "jetson2/observe/status" \
  -m '{"device_id":"jetson2","message":"LEFT:BASKET_IN","timestamp":"2025-11-10 21:00:00"}'
```

---

### 방법 3: mosquitto_sub로 구독 (로봇 PC에서)

```bash
# 모든 Jetson 메시지 보기 (wildcard)
mosquitto_sub -h localhost -t "#" -v

# Jetson1 메시지만 보기
mosquitto_sub -h localhost -t "frying_ai/jetson1/#" -v

# Jetson2 메시지만 보기
mosquitto_sub -h localhost -t "jetson2/#" -v

# AI 모드만 보기
mosquitto_sub -h localhost -t "+/system/ai_mode" -v
```

---

## 📋 설정 파일 위치

### Jetson1 설정:
```bash
~/jetson-food-ai/jetson1_monitoring/config.json

{
  "mqtt_enabled": true,
  "mqtt_broker": "192.168.x.x",  # 로봇 PC IP
  "mqtt_port": 1883,
  "mqtt_topic": "robot/control",
  "mqtt_topic_ai_mode": "jetson1/system/ai_mode",
  "ai_mode_enabled": false  # AI 완성 시 true로 변경
}
```

### Jetson2 설정:
```bash
~/jetson-food-ai/jetson2_frying_ai/config_jetson2.json

{
  "mqtt_enabled": true,
  "mqtt_broker": "192.168.x.x",  # 로봇 PC IP
  "mqtt_port": 1883,
  "mqtt_topic_frying": "frying/status",
  "mqtt_topic_observe": "observe/status",
  "mqtt_topic_ai_mode": "jetson2/system/ai_mode",
  "mqtt_topic_oil_temp_left": "frying/oil_temp/left",
  "mqtt_topic_oil_temp_right": "frying/oil_temp/right",
  "mqtt_topic_probe_temp_left": "frying/probe_temp/left",
  "mqtt_topic_probe_temp_right": "frying/probe_temp/right",
  "mqtt_topic_food_type": "frying/food_type",
  "ai_mode_enabled": false  # AI 완성 시 true로 변경
}
```

---

## ⚠️ 주의사항

### 1. AI 모드 (ai_mode_enabled)
- **용도**: AI 완성/미완성 여부 (시스템 구성 정보)
- **발행 횟수**: MQTT 연결 시 단 1회
- **변경 방법**: config 파일 수동 편집
- **런타임 상태와 무관**: AI 시작/중지 버튼과는 별개

### 2. 메시지 형식
- Jetson → 로봇: 대부분 **JSON 형식**
- 로봇 → Jetson: 온도는 **문자열** (예: "180.5")

### 3. QoS (Quality of Service)
- 기본값: QoS 1 (최소 1회 전달 보장)
- 중요한 메시지는 반드시 수신 확인 필요

### 4. Timestamp
- 형식: `"YYYY-MM-DD HH:MM:SS"`
- 예: `"2025-11-10 17:00:00"`

---

## 🔗 관련 문서
- `배포가이드.md` - MQTT 설정 방법
- `test_mqtt_publish.py` - MQTT 테스트 도구
- `jetson1_monitoring/config.json` - Jetson1 MQTT 설정
- `jetson2_frying_ai/config_jetson2.json` - Jetson2 MQTT 설정

---

## 📝 업데이트 히스토리
- **2025-11-10**: 초기 문서 작성
  - Jetson1 사람 감지 메시지
  - Jetson2 바구니 감지 메시지
  - AI 모드 설정 방식
  - 로봇 PC → Jetson2 온도/음식 정보
