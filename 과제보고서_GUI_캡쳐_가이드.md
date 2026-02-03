# 🎬 과제보고서용 GUI 캡쳐 가이드

## 📋 목적
Jetson #1, #2 GUI에서 야간 감시, 진동센서 등 이벤트가 발생한 순간을 캡쳐하기 위한 테스트 도구

---

## 🛠️ 준비한 도구

### 1️⃣ `demo_toast_overlay.py` (추천 ⭐)
**화면에 직접 토스트 알림을 띄우는 독립 GUI**

- ✅ 가장 간단하고 확실한 방법
- ✅ 실제 Jetson GUI 위에 토스트가 오버레이됨
- ✅ MQTT 연결 불필요
- ⚠️ 실제 시스템 동작은 아님 (시각적 데모용)

### 2️⃣ `demo_event_simulator.py`
**MQTT로 실제 이벤트를 트리거하는 시뮬레이터**

- ✅ 실제 시스템 동작을 테스트
- ✅ MQTT 브로커 연결 필요
- ⚠️ 일부 이벤트는 MQTT만으로 GUI에 직접 표시 안 될 수 있음

---

## 🚀 사용 방법

### 방법 1: 토스트 오버레이 (가장 쉬움)

```bash
# 1. Jetson GUI 실행 (systemctl 또는 직접 실행)
cd ~/jetson-food-ai/jetson1_monitoring
python3 JETSON1_INTEGRATED.py

# 또는 Jetson #2
cd ~/jetson-food-ai/jetson2_frying_ai
python3 JETSON2_INTEGRATED.py

# 2. 새 터미널에서 토스트 오버레이 실행
cd ~/jetson-food-ai
python3 demo_toast_overlay.py
```

**캡쳐 순서:**
1. Jetson GUI를 전체 화면으로 띄움
2. `demo_toast_overlay.py` 창에서 원하는 버튼 클릭
3. 화면에 토스트가 표시되면 **즉시 스크린샷** (1.5초 후 사라짐!)
4. 여러 이벤트를 반복해서 캡쳐

**💡 팁:**
- 토스트 위치를 "상단 중앙" / "중앙" / "하단 중앙" 선택 가능
- 커스텀 메시지 입력 가능
- 창을 항상 최상위에 고정하여 쉽게 접근

---

### 방법 2: MQTT 이벤트 시뮬레이터 (실제 동작 테스트)

```bash
# 1. MQTT 브로커가 실행 중인지 확인
# (보통 192.168.0.100에서 실행 중)

# 2. Jetson GUI 실행
cd ~/jetson-food-ai/jetson1_monitoring
python3 JETSON1_INTEGRATED.py

# 3. 이벤트 시뮬레이터 실행
cd ~/jetson-food-ai
python3 demo_event_simulator.py
```

**사용법:**
- MQTT 연결 상태 확인 (녹색 체크 표시)
- 원하는 이벤트 버튼 클릭
- 실행 로그에서 전송 확인
- Jetson GUI에서 반응 확인 후 캡쳐

---

## 📸 캡쳐할 이벤트 목록

### Jetson #1
- ✅ 야간 모션 감지 스냅샷
- ✅ 진동 측정 시작
- ✅ 진동 정상 (녹색)
- ✅ 진동 이상! (빨간색)
- ✅ 볶음 POT1 투입
- ✅ 볶음 POT2 투입

### Jetson #2
- ✅ 튀김 완료 알림
- ✅ 과조리 경고

---

## 🎨 스크린샷 예시

### 진동 이상 알림
```
┌─────────────────────────────────────┐
│  [GUI 헤더]                         │
├─────────────────────────────────────┤
│                                     │
│     ┌─────────────────────────┐    │
│     │ 진동 이상! (150/100)    │ ← 빨간 토스트
│     └─────────────────────────┘    │
│                                     │
│  [카메라 프리뷰]                    │
│                                     │
└─────────────────────────────────────┘
```

### 야간 모션 감지
```
GUI 상단에 "야간 감지: 3장" 카운트 표시
+ 개발자 모드에서 스냅샷 썸네일 확인 가능
```

---

## 🔧 고급 팁

### 실제 야간 모션 감지 테스트
```bash
# 개발자 모드 활성화 후
# GUI 내 "야간 리뷰 보기" 버튼 클릭
# 또는 실제로 카메라 앞에서 움직이기
```

### 진동센서 실제 테스트
```bash
# config.json 수정
{
  "vibration_test_mode": false  # 실제 센서 사용
}

# 진동센서가 /dev/ttyUSB0에 연결되어 있어야 함
ls -l /dev/ttyUSB*
```

### 커스텀 토스트 메시지
```python
# demo_toast_overlay.py에서 커스텀 메시지 입력
"튀김 온도 180°C 도달!"
"바켓 교체 필요"
```

---

## ⚠️ 주의사항

1. **토스트는 1.5초만 표시됩니다**
   - 버튼 클릭 후 즉시 스크린샷 준비!
   - 필요하면 `demo_toast_overlay.py` 내 `duration_ms` 수정

2. **MQTT 브로커 연결 확인**
   - `demo_event_simulator.py` 사용 시 필수
   - 브로커 주소: `192.168.0.100:1883`

3. **systemctl 서비스 실행 중일 때**
   ```bash
   # 서비스 중지 후 직접 실행 권장
   sudo systemctl stop jetson1-monitor
   python3 JETSON1_INTEGRATED.py
   ```

---

## 📚 파일 구조

```
jetson-food-ai/
├── demo_toast_overlay.py       ← 토스트 오버레이 (추천)
├── demo_event_simulator.py     ← MQTT 이벤트 시뮬레이터
├── 과제보고서_GUI_캡쳐_가이드.md  ← 이 파일
│
├── jetson1_monitoring/
│   └── JETSON1_INTEGRATED.py   ← Jetson #1 메인 GUI
│
└── jetson2_frying_ai/
    └── JETSON2_INTEGRATED.py   ← Jetson #2 메인 GUI
```

---

## ✅ 체크리스트

과제보고서용 캡쳐 완료 체크:

- [ ] Jetson #1 - 야간 모션 감지 화면
- [ ] Jetson #1 - 진동 정상 알림
- [ ] Jetson #1 - 진동 이상 알림
- [ ] Jetson #1 - 볶음 투입 알림
- [ ] Jetson #2 - 튀김 완료 알림
- [ ] Jetson #2 - 과조리 경고

---

**만든 날짜:** 2026-02-03
**목적:** 캡스톤 과제보고서 GUI 스크린샷 준비
**작성자:** Claude Code
