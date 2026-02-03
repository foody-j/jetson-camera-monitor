# 🎬 과제보고서 GUI 캡쳐 - MQTT 실제 데이터 방식

## ✅ 완성!

**원본 코드 수정 없이** 실제 MQTT 데이터를 전송하여 Jetson GUI가 실제로 반응하도록 만들었습니다!

---

## 🚀 사용 방법

### 1단계: Jetson #1 GUI 실행

```bash
# 터미널 1
cd ~/jetson-food-ai/jetson1_monitoring
python3 JETSON1_INTEGRATED.py
```

### 2단계: MQTT 테스트 스크립트 실행

```bash
# 터미널 2 (새 터미널)
cd ~/jetson-food-ai
python3 test_mqtt_real_events.py
```

### 3단계: 이벤트 발생 & 캡쳐

1. **테스트 GUI에서 원하는 버튼 클릭**
   - 📳 진동 측정 시작/종료
   - 🍳 POT1 투입 (짜장/짬뽕/볶음밥/우동)
   - 🍳 POT2 투입 (짜장/짬뽕/볶음밥/우동)

2. **Jetson GUI에 실제 토스트 표시됨!**
   - "진동 측정 시작"
   - "볶음 POT1: 짜장"
   - 등등...

3. **즉시 스크린샷 캡쳐!** (1.5초 후 사라짐)

---

## 💡 작동 원리

### 실제 시스템과 100% 동일

```
테스트 스크립트                Jetson #1 GUI
     │                              │
     │   MQTT 메시지 전송            │
     ├──────────────────────────────>│
     │   Topic: HR/Status            │
     │   DeviceNum: "1"              │
     │   ChkVibration: true          │
     │                               │
     │                          [MQTT 수신]
     │                               │
     │                          on_robot_status()
     │                               │
     │                          show_toast("진동 측정 시작")
     │                               │
     │                          [화면에 토스트 표시!]
```

### 실제 데이터 구조

#### 진동 측정 시작
```json
{
  "Status": [
    {
      "DeviceNum": "1",
      "ChkVibration": true
    }
  ]
}
```

#### 볶음 POT1 짜장 투입
```json
{
  "Status": [
    {
      "DeviceNum": "1",
      "PTNum": "0",
      "ProcessType": "투입",
      "NowRecipe": "짜장"
    }
  ]
}
```

---

## 📸 캡쳐 체크리스트

### Jetson #1
- [ ] 진동 측정 시작 토스트
- [ ] 진동 측정 종료 토스트
- [ ] POT1 짜장 투입 토스트
- [ ] POT1 짬뽕 투입 토스트
- [ ] POT2 볶음밥 투입 토스트
- [ ] POT2 우동 투입 토스트

---

## 💪 장점

### ✅ 원본 코드 수정 없음
- JETSON1_INTEGRATED.py 전혀 건드리지 않음
- 깔끔하고 안전함

### ✅ 실제 시스템과 100% 동일
- 실제 HR/Status 토픽 사용
- 실제 on_robot_status() 핸들러가 처리
- 실제 show_toast() 함수 호출

### ✅ 다양한 레시피 테스트 가능
- 짜장, 짬뽕, 볶음밥, 우동
- 원하는 레시피 추가 가능

### ✅ 로그 확인 가능
- 전송한 MQTT 메시지 전체 내용 확인
- JSON 포맷으로 예쁘게 출력

---

## 🔧 커스터마이징

### 레시피 추가하기

`test_mqtt_real_events.py` 파일에서:

```python
recipes = ["짜장", "짬뽕", "볶음밥", "우동", "짜장밥", "탕수육"]  # ← 여기에 추가
```

### MQTT 브로커 변경

```python
MQTT_BROKER = "192.168.0.100"  # ← 브로커 주소
MQTT_PORT = 1883               # ← 포트
```

---

## ⚠️ 주의사항

### 1. MQTT 브로커 실행 확인

```bash
# 브로커가 192.168.0.100에서 실행 중이어야 함
# 또는 config.json의 mqtt_broker 주소와 일치해야 함
```

### 2. Jetson GUI가 먼저 실행되어야 함

```bash
# 순서 중요!
# 1. JETSON1_INTEGRATED.py 실행
# 2. test_mqtt_real_events.py 실행
```

### 3. systemctl 서비스 중지

```bash
# 서비스가 실행 중이면 중지
sudo systemctl stop jetson1-monitor

# 직접 실행
python3 JETSON1_INTEGRATED.py
```

### 4. 토스트는 1.5초만 표시

- 버튼 클릭 후 즉시 캡쳐 준비!
- 필요하면 여러 번 클릭 가능

---

## 📚 파일 구조

```
jetson-food-ai/
├── test_mqtt_real_events.py          ← 이 테스트 스크립트 (추천!)
├── demo_event_simulator.py           ← 이전 버전 (단순 MQTT)
├── demo_toast_overlay.py             ← 이전 버전 (오버레이)
├── 과제보고서_MQTT_테스트_가이드.md   ← 이 파일
│
└── jetson1_monitoring/
    ├── JETSON1_INTEGRATED.py         ← 원본 (수정 없음!)
    └── config.json

```

---

## 🎯 비교표

| 방법 | 원본 수정 | 실제 동작 | 난이도 |
|------|-----------|-----------|--------|
| **test_mqtt_real_events.py** | ❌ 없음 | ✅ 100% | ⭐ 쉬움 |
| demo_event_simulator.py | ❌ 없음 | ⚠️ 부분 | ⭐⭐ 보통 |
| demo_toast_overlay.py | ❌ 없음 | ❌ 가짜 | ⭐ 쉬움 |
| 개발자 모드 버튼 추가 | ✅ 있음 | ✅ 100% | ⭐⭐⭐ 어려움 |

---

## 🎥 사용 예시

### 콘솔 출력 예시

```
[10:30:15] ✅ MQTT 브로커 연결 성공: 192.168.0.100
[10:30:20] 📳 진동 측정 시작 이벤트 발송
[10:30:20] 📤 Topic: HR/Status
[10:30:20] 📦 Payload:
{
  "timestamp": "2026-02-03T10:30:20.123456",
  "Status": [
    {
      "DeviceNum": "1",
      "ChkVibration": true
    }
  ]
}
[10:30:20] ------------------------------------------------------------
[10:30:25] 🍳 POT1(왼쪽) '짜장' 투입 이벤트 발송
[10:30:25] 📤 Topic: HR/Status
[10:30:25] 📦 Payload:
{
  "timestamp": "2026-02-03T10:30:25.654321",
  "Status": [
    {
      "DeviceNum": "1",
      "PTNum": "0",
      "ProcessType": "투입",
      "NowRecipe": "짜장",
      ...
    }
  ]
}
[10:30:25] ------------------------------------------------------------
```

### Jetson GUI 반응

```
[JETSON1 GUI 화면]
┌──────────────────────────────────────────┐
│ [헤더: MQTT, 시간, SFLAB...]             │
├──────────────────────────────────────────┤
│                                          │
│    ┌──────────────────────────────┐     │
│    │ 진동 측정 시작               │ ← 토스트!
│    └──────────────────────────────┘     │
│                                          │
│  [사람감지 카메라]  [볶음 카메라]        │
│                                          │
└──────────────────────────────────────────┘
```

---

## 🏆 결론

**이 방법이 가장 좋습니다!**

✅ 원본 코드 깔끔
✅ 실제 시스템 100% 재현
✅ 쉽고 빠름
✅ 여러 번 테스트 가능

---

**만든 날짜:** 2026-02-03
**목적:** 캡스톤 과제보고서 GUI 스크린샷 (실제 MQTT 데이터)
**방법:** 별도 테스트 스크립트로 실제 HR/Status 메시지 전송

**과제보고서 화이팅! 🚀**
