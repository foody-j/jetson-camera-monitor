# 로봇 PC MQTT 메시지 형식

## 개요
로봇 PC에서 Jetson으로 전송하는 JSON 메시지 구조 정리

## MQTT 토픽

**로봇 PC → Jetson (구독)**
| 토픽 | 설명 |
|------|------|
| `HR/Status` | 로봇 PC 상태 (전체) |

**Jetson → 로봇 PC (발행)**
| 토픽 | 발행자 | 설명 |
|------|--------|------|
| `jetson1/system/ai_mode` | Jetson1 | AI 모드 상태 |
| `jetson1/relay/status` | Jetson1 | 릴레이 상태 |
| `jetson2/system/ai_mode` | Jetson2 | AI 모드 상태 |
| `frying/status` | Jetson2 | 튀김 AI 상태 |
| `observe/status` | Jetson2 | 관찰 AI 상태 |

## JSON 구조

```json
{
  "Status": [
    {
      "DeviceNum": "0",
      "PTNum": "0",
      "Potstatus": {
        "PT_Power": "True",
        "PT_Level": 6,
        "PT_Mode": 1,
        "PT_Temp": 0.0,
        "PT_Sensor": "True",
        "RT_Speed": 0,
        "RT_Dir": 0,
        "RT_Run": 0
      },
      "RBstatus": "연결상태(구동중)",
      "TotalTime": "00:14:39",
      "TargetTime": "5분",
      "RunningTime": "0분 8초",
      "Mode": "시간설정",
      "ProcessType": "조리",
      "NowRecipe": "제육볶음"
    },
    {
      "DeviceNum": "0",
      "PTNum": "1",
      "Potstatus": { ... },
      "RBstatus": "연결상태(구동중)",
      "TotalTime": "00:09:74",
      "TargetTime": "",
      "RunningTime": "",
      "Mode": "온도설정",
      "ProcessType": "조리",
      "NowRecipe": "고구마튀김"
    }
  ],
  "RBMotion": 1
}
```

## 필드 설명

### 최상위 필드

| 필드 | 타입 | 설명 |
|------|------|------|
| `Status` | Array | 솥 정보 배열 ([0]: 튀김솥/Jetson2, [1]: 볶음솥/Jetson1) |
| `RBMotion` | Number | 쉐이킹 상태 (1: 1번솥 쉐이킹, 2: 2번솥 쉐이킹) |

### Status 배열 항목

| 필드 | 타입 | 설명 | 값 예시 |
|------|------|------|---------|
| `DeviceNum` | String | 솥 위치 | "0": 왼쪽, "1": 오른쪽 |
| `PTNum` | String | 솥 번호 | "0": 0번솥, "1": 1번솥 |
| `RBstatus` | String | 로봇 연결 상태 | "연결상태(구동중)" |
| `TotalTime` | String | 총 시간 | "00:14:39" |
| `TargetTime` | String | 목표 시간 | "5분" |
| `RunningTime` | String | 경과 시간 | "0분 8초" |
| `Mode` | String | 조리 모드 | "시간설정", "온도설정" |
| `ProcessType` | String | 현재 프로세스 | "투입", "조리", "배출" |
| `NowRecipe` | String | 현재 레시피 | "제육볶음", "고구마튀김" |

### Potstatus 객체

| 필드 | 타입 | 설명 |
|------|------|------|
| `PT_Power` | String | 전원 상태 ("True"/"False") |
| `PT_Level` | Number | 화력 레벨 |
| `PT_Mode` | Number | 솥 모드 |
| `PT_Temp` | Number | 솥 온도 |
| `PT_Sensor` | String | 센서 상태 ("True"/"False") |
| `RT_Speed` | Number | 회전 속도 |
| `RT_Dir` | Number | 회전 방향 |
| `RT_Run` | Number | 회전 동작 상태 |

## Jetson 활용 계획

### 트리거 조건
- `ProcessType: "투입"` → AI 데이터 수집 시작
- `ProcessType: "배출"` → AI 데이터 수집 종료

### 수집할 정보
- `NowRecipe`: 음식 종류 (데이터 라벨링용)
- `PT_Temp`: 온도 모니터링
- `RunningTime`: 조리 시간 기록
- `RBMotion`: 쉐이킹 판단 (로봇팔 가림 회피)

## TODO
- [x] 로봇 PC에서 사용하는 MQTT 토픽 확인 → `HR/Status`
- [x] 현장에서 실제 토픽 검증
- [x] Jetson 파서 구현
