# MQTT 토픽 정리 (로봇팀용)

## 브로커 정보
- 브로커: (현장 브로커 IP)
- 포트: 1883

---

## 1. 로봇PC → Jetson (로봇팀이 발행)

| 토픽 | 설명 |
|------|------|
| `HR/Status` | 로봇 PC 상태 |

### HR/Status 메시지 형식
```json
{
  "Status": [
    {
      "DeviceNum": "0",
      "PTNum": "0",
      "ProcessType": "조리",
      "NowRecipe": "제육볶음",
      "Potstatus": {
        "PT_Temp": 180.5,
        "PT_Power": "True",
        "PT_Level": 6
      },
      "RunningTime": "0분 8초"
    }
  ],
  "RBMotion": 1
}
```

---

## 2. Jetson → 로봇PC (Jetson이 발행, 로봇팀이 구독)

### jetson1/status (볶음 스테이션)
```json
{
  "device_id": "jetson1",
  "device_name": "Jetson1_StirFry_Station",
  "ip_address": "192.168.x.x",
  "timestamp": "2025-12-11 11:30:00",
  "ai_mode": false,
  "person_detected": true,
  "relay_enabled": true,
  "recording": {
    "left": false,
    "right": false
  },
  "system": {
    "cpu_percent": 45.2,
    "memory_percent": 60.1,
    "gpu_temp": 52.0
  }
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `device_id` | string | 장치 ID ("jetson1") |
| `timestamp` | string | 발행 시간 |
| `ai_mode` | bool | AI 모드 활성화 여부 |
| `person_detected` | bool | 사람 감지 여부 |
| `relay_enabled` | bool | 릴레이 활성화 상태 |
| `recording.left` | bool | 왼쪽 볶음솥 녹화 중 |
| `recording.right` | bool | 오른쪽 볶음솥 녹화 중 |

---

### jetson2/status (튀김 스테이션)
```json
{
  "device_id": "jetson2",
  "device_name": "Jetson2_Frying_Station",
  "ip_address": "192.168.x.x",
  "timestamp": "2025-12-11 11:30:00",
  "ai_mode": false,
  "frying": {
    "left": "IDLE",
    "right": "IDLE"
  },
  "observe": {
    "left": "EMPTY",
    "right": "FILLED"
  },
  "system": {
    "cpu_percent": 50.1,
    "memory_percent": 65.3,
    "gpu_temp": 55.0
  }
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `device_id` | string | 장치 ID ("jetson2") |
| `timestamp` | string | 발행 시간 |
| `ai_mode` | bool | AI 모드 활성화 여부 |
| `frying.left` | string | 왼쪽 튀김솥 AI 상태 |
| `frying.right` | string | 오른쪽 튀김솥 AI 상태 |
| `observe.left` | string | 왼쪽 관찰 AI 상태 |
| `observe.right` | string | 오른쪽 관찰 AI 상태 |

#### frying 상태값
| 값 | 설명 |
|----|------|
| `IDLE` | 대기 중 |
| `COOKING` | 조리 중 |

#### observe 상태값
| 값 | 설명 |
|----|------|
| `EMPTY` | 바구니 비어있음 |
| `FILLED` | 바구니에 음식 있음 |
| `UNKNOWN` | AI 판단 불가 |

---

## 3. 발행 주기
- Jetson → 로봇PC: **2초** 간격 (config에서 변경 가능)

---

## 4. 토픽 요약

| 방향 | 토픽 | 발행자 | 구독자 |
|------|------|--------|--------|
| 로봇→Jetson | `HR/Status` | 로봇PC | Jetson1, Jetson2 |
| Jetson→로봇 | `jetson1/status` | Jetson1 | 로봇PC |
| Jetson→로봇 | `jetson2/status` | Jetson2 | 로봇PC |

---

## 5. 테스트 방법

### Jetson 상태 구독 테스트
```bash
mosquitto_sub -h 브로커IP -t "jetson1/status" -t "jetson2/status"
```

### 로봇 상태 발행 테스트
```bash
mosquitto_pub -h 브로커IP -t "HR/Status" -m '{"Status":[{"DeviceNum":"0","PTNum":"0","ProcessType":"조리","NowRecipe":"테스트"}]}'
```
