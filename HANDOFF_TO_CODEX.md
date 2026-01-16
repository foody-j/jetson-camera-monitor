# Codex 인계 문서 - Jetson2 Frying AI

## 현재 상태

### 최근 완료 작업 (2026-01-16)
1. ✅ GUI 온도 라벨을 color_diff 라벨로 교체
2. ✅ 청소 모드 데이터 수집 필터링 추가
3. ✅ GST preview window 제거 (GUI 카메라 정상화)

### 시스템 상태
- **Git Branch:** `main` (최신 커밋: `583fbc3`)
- **실행 환경:** Jetson Orin Nano (Jetson #2)
- **서비스:** `jetson2-monitor.service`
- **메인 파일:** `jetson2_frying_ai/JETSON2_INTEGRATED.py` (171KB)

---

## 핵심 변경사항

### 1. GUI Color Diff 표시
**파일:** `jetson2_frying_ai/JETSON2_INTEGRATED.py`

**변경 위치:**
- Line 1363-1366: `frying_left_color_diff_label` 생성
- Line 1402-1405: `frying_right_color_diff_label` 생성
- Line 1875: POT1 color_diff 업데이트
- Line 2008: POT2 color_diff 업데이트

**제거된 것:**
- `frying_left_temp_label` (기름 온도)
- `frying_left_probe_label` (탐침 온도)
- `frying_right_temp_label`
- `frying_right_probe_label`

**표시 형식:**
```python
self.frying_left_color_diff_label.config(text=f"색상변화: {color_diff:.1f}")
# 출력: "색상변화: 12.5"
```

---

### 2. 청소 모드 필터링
**파일:** `jetson2_frying_ai/JETSON2_INTEGRATED.py`

**핵심 로직 (Line 1075):**
```python
is_cleaning = "청소" in recipe if recipe else False
```

**적용 위치:**
- Line 1078: `if process_type in ["투입", "조리"] and not is_cleaning:`
- Line 1103: `if process_type in ["투입", "조리"] and not is_cleaning:`

**동작:**
- MQTT 메시지 `recipe: "0청소"` 수신 시 데이터 수집 안 함
- 로그 출력: `[로봇상태] POT1(왼쪽) 청소 모드 감지 - 데이터 수집 스킵`

---

### 3. GST Window 제거
**파일:** `jetson2_frying_ai/gst_camera.py`

**변경 (Line 26):**
```python
# Before
self.preview_sink = os.getenv("GMSL_PREVIEW_SINK", "autovideosink")

# After
self.preview_sink = os.getenv("GMSL_PREVIEW_SINK", "none")
```

**효과:**
- GStreamer가 별도 윈도우를 띄우지 않음
- tkinter GUI에만 카메라 프레임 표시
- `autovideosink` → `none` 변경으로 파이프라인 간소화

---

## 주의사항 (중요!)

### 데이터 수집 트리거
현재 데이터 수집은 다음 조건에서 시작됩니다:

```python
if process_type in ["투입", "조리"] and not is_cleaning:
    if not self.pot1_collecting:  # 중복 방지
        self.start_pot1_collection()
```

**가능한 시나리오:**
1. ✅ "투입" → 수집 시작
2. ✅ "조리" → 수집 시작 (프로그램 런타임 중에도)
3. ❌ "청소" → 수집 안 함
4. ✅ "배출" → 50초 후 수집 종료

**안전장치:**
- `if not self.pot1_collecting`: 중복 실행 방지
- `배출 타이머 취소`: 재투입 시 타이머 리셋
- 충돌 없음 확인됨

---

## 파일 구조

```
jetson2_frying_ai/
├── JETSON2_INTEGRATED.py        # 메인 프로그램 (수정됨)
├── config_jetson2.json           # 설정 파일
├── gst_camera.py                 # GMSL 카메라 (수정됨)
├── simple_checker/               # SimpleColorChecker (WSL2 전용)
│   ├── color_checker.py
│   └── color_utils.py
└── observe_add/                  # Basket AI 모델
    ├── best_io.pt                # 바스켓 세그멘테이션
    └── best_fe.pt                # Filled/Empty 분류
```

**수정 금지:**
- `simple_checker/`: WSL2에서 `sync_to_jetson.sh`로 덮어씌워짐
- Jetson에서 수정 시 다음 sync 때 날아감!

**수정 가능:**
- `JETSON2_INTEGRATED.py`: 자유롭게 수정 OK
- `config_jetson2.json`: 설정 변경 OK
- `gst_camera.py`: 필요 시 수정 OK

---

## 테스트 방법

### 로컬 실행
```bash
cd ~/jetson-food-ai/jetson2_frying_ai
python3 JETSON2_INTEGRATED.py
```

### 서비스 재시작
```bash
sudo systemctl restart jetson2-monitor
sudo journalctl -u jetson2-monitor -f
```

### 확인할 로그
```bash
# GST 윈도우 안 뜨는지 확인
[GstCamera] Creating camera for /dev/video0 @ 1920x1536
# "autovideosink" 문자열이 없어야 함

# 청소 모드 필터링 확인
[로봇상태] 튀김솥 PT0 | 조리 | 0청소 | 온도:34.0°C | 30분 51초
[로봇상태] POT1(왼쪽) 청소 모드 감지 - 데이터 수집 스킵

# 정상 수집 확인
[로봇상태] 튀김솥 PT0 | 조리 | chicken | 온도:170.0°C | 05분 30초
[로봇상태] POT1(왼쪽) 데이터 수집 시작 (조리) - chicken
[DEBUG] POT1 데이터 저장: ~/AI_Data/FryingData/.../frame_001.jpg
```

### GUI 확인 사항
1. ✅ GST 윈도우가 안 뜨고 tkinter GUI만 표시
2. ✅ POT1, POT2 패널에 "색상변화: XX.X" 표시
3. ✅ 카메라 프레임이 GUI에 정상 표시

---

## 알려진 이슈

### 없음 (현재)
모든 변경사항이 테스트되고 커밋됨.

---

## 다음 작업 제안

### Optional: MQTT 상태 발행
현재 config에 `mqtt_topic_frying: "frying/status"`가 있지만 사용 안 함.

**구현 시:**
```python
def publish_frying_status(self):
    """1초마다 MQTT로 튀김 상태 발행"""
    payload = {
        "pot1": {
            "status": self.pot1_pot_status,  # IDLE, COOKING, DISCHARGE
            "color_diff": self.pot1_color_diff,
            "food_type": self.pot1_food_type,
            "collecting": self.pot1_collecting
        },
        "pot2": {
            "status": self.pot2_pot_status,
            "color_diff": self.pot2_color_diff,
            "food_type": self.pot2_food_type,
            "collecting": self.pot2_collecting
        }
    }
    self.send_mqtt_message("frying/status", json.dumps(payload))
```

**장점:**
- 로봇 PC에서 실시간 튀김 상태 모니터링 가능
- 대시보드 구현 시 유용

**단점:**
- MQTT 트래픽 증가 (1초마다 발행)

---

## 관련 문서

- **프로젝트 가이드:** `CLAUDE.md`
- **작업 로그:** `WORK_LOG_20260116.md`
- **데이터 저장 구조:** `docs/DATA_STORAGE_MAP.md`
- **AI 학습 전략:** `docs/AI_TRAINING_STRATEGY.md`

---

## Git 커밋 히스토리

```bash
583fbc3 - Disable GST preview window by default (2026-01-16)
7e21581 - Skip data collection when recipe contains '청소' keyword (2026-01-16)
31ccf45 - Replace temperature labels with color_diff in GUI (2026-01-16)
c6ee0cc - Fix main thread error in MQTT callback (이전)
```

---

## 코드 참고

### Color Diff 업데이트 위치
```python
# jetson2_frying_ai/JETSON2_INTEGRATED.py

# POT1 (Line 1865-1895)
color_result = self.color_checker_left.measure(frame)
if "error" not in color_result:
    color_diff = color_result['color_diff']
    self.frying_left_color_diff_label.config(text=f"색상변화: {color_diff:.1f}")

    # DISCHARGE 조건
    if self._compare_time(running_time, target_time) and color_diff >= 25.0:
        self.pot1_pot_status = "DISCHARGE"

# POT2 (Line 1997-2029)
# 동일 구조
```

### 청소 필터링 위치
```python
# jetson2_frying_ai/JETSON2_INTEGRATED.py

# Line 1075
is_cleaning = "청소" in recipe if recipe else False

# POT1 (Line 1078-1094)
if process_type in ["투입", "조리"] and not is_cleaning:
    if not self.pot1_collecting:
        self.pot1_food_type = recipe if recipe else "unknown"
        self.start_frying_camera("0")
        self.start_pot1_collection()
elif is_cleaning:
    print(f"[로봇상태] POT1(왼쪽) 청소 모드 감지 - 데이터 수집 스킵")

# POT2 (Line 1103-1120)
# 동일 구조
```

### GST Preview 제거
```python
# jetson2_frying_ai/gst_camera.py

# Line 26
self.preview_sink = os.getenv("GMSL_PREVIEW_SINK", "none")

# Line 53-57
if self.preview_sink.lower() != "none":
    gst_cmd += [
        "t.", "!", "queue", "!", "videoconvert", "!",
        self.preview_sink, "sync=false"
    ]
# "none"이면 이 블록 실행 안 됨 → GST 윈도우 안 뜸
```

---

## 환경 정보

- **OS:** JetPack 6.2 (L4T R36.4.3)
- **Python:** 3.10+
- **CUDA:** 12.x
- **PyTorch:** 2.x (CUDA 지원)
- **GStreamer:** 1.20+
- **MQTT Broker:** 192.168.0.100:1883

---

## 긴급 연락

문제 발생 시:
1. 로그 확인: `sudo journalctl -u jetson2-monitor -f`
2. Git 되돌리기: `git reset --hard <commit-hash>`
3. 서비스 재시작: `sudo systemctl restart jetson2-monitor`

**안전한 커밋:**
- `583fbc3` (최신) ✅
- `7e21581` ✅
- `31ccf45` ✅
- `c6ee0cc` ✅

---

**작성일:** 2026-01-16
**인계자:** Claude
**인수자:** Codex
**프로젝트:** jetson-food-ai
**대상:** Jetson #2 (Frying AI System)
