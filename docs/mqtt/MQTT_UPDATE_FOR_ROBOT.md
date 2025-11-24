# 젯슨 MQTT 토픽 변경 안내

## 변경 사유

기존에는 각 상태별로 토픽을 나눠서 발행했는데, 이렇게 하니까 메시지가 너무 많이 발행되고 타이밍도 맞지 않는 문제가 있었습니다.
그래서 하나의 통합 토픽으로 모든 상태를 묶어서 보내도록 변경했습니다.

## 변경 내용 요약

### 젯슨1 (볶음)
- **기존**: `jetson1/system/ai_mode`, `frying_ai/jetson1/robot/control`, `jetson1/relay/status` 등 개별 토픽
- **변경**: `jetson1/status` 하나로 통합

### 젯슨2 (튀김)
- **기존**: `jetson2/system/ai_mode`, `jetson2/observe/status` 등 개별 토픽
- **변경**: `jetson2/status` 하나로 통합
- **추가**: 솥 상태(pot status) 필드 포함 (향후 AI 연동 예정)

## 구독해야 할 토픽

```python
# 젯슨1 상태
client.subscribe("jetson1/status", qos=1)

# 젯슨2 상태
client.subscribe("jetson2/status", qos=1)
```

## 메시지 포맷

### 젯슨1 상태 메시지

```json
{
  "device_id": "jetson1",
  "device_name": "Jetson1_StirFry_Station",
  "device_location": "EV의장",
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

**주요 필드**:
- `person_detected`: 사람 감지됨 (기존 robot/control의 ON/OFF 대체)
- `relay_enabled`: 릴레이 상태 (로봇 PC 전원 제어)
- `recording.pot1`, `recording.pot2`: 각 솥 녹화 중 여부

### 젯슨2 상태 메시지

```json
{
  "device_id": "jetson2",
  "device_name": "Jetson2_Frying_Station",
  "device_location": "EV의장",
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

**주요 필드**:
- `basket.left`, `basket.right`: 바구니 상태
  - `"FILLED"`: 음식 들어옴
  - `"EMPTY"`: 음식 나감
  - `"NO_BASKET"`: 바구니 없음
  - `"UNKNOWN"`: 알 수 없음
- `pot.pot1`, `pot.pot2`: 솥 상태 (현재는 EMPTY 고정, 향후 AI 연동 시 업데이트)
  - `"HAS_FOOD"`: 음식 있음
  - `"EMPTY"`: 비어있음

## 파싱 예시 (Python)

```python
import json

def on_message(client, userdata, msg):
    if msg.topic == "jetson1/status":
        data = json.loads(msg.payload)

        # 사람 감지 확인
        if data["person_detected"]:
            print("젯슨1에서 사람 감지됨")
            # 로봇 PC 켜기 로직

        # POT1 녹화 중인지 확인
        if data["recording"]["pot1"]:
            print("POT1 조리 중")

    elif msg.topic == "jetson2/status":
        data = json.loads(msg.payload)

        # 왼쪽 바구니 상태 확인
        if data["basket"]["left"] == "FILLED":
            print("왼쪽 바구니에 음식 들어옴")
            # 조리 시작 로직

        # 솥 상태 확인 (향후)
        if data["pot"]["pot1"] == "HAS_FOOD":
            print("POT1에 음식 있음")
```

## 발행 주기

- 2초마다 발행 (기존과 동일)
- 네트워크 끊김 시 자동 재연결
- QoS 1 (최소 1회 전달 보장)


## 주의사항

1. **JSON 파싱 오류 처리 필수**
   - 메시지가 잘못된 형식일 수 있으니 try-catch 필수

2. **필드 존재 여부 확인**
   - 딕셔너리 접근 시 KeyError 방지

3. **타임스탬프 활용**
   - 상태 메시지의 timestamp로 최신 데이터인지 확인 가능

4. **system_metrics는 선택사항**
   - 모니터링 용도이므로 필수로 파싱하지 않아도 됨


---

업데이트 일자: 2025-11-24
문의: 김영진 (youngjin.kim@dankook.ac.kr)
