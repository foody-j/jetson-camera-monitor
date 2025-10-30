# ROBOTCAM - Auto Start/Down System

자동 시작/종료 시스템 - YOLO 사람 감지 및 모션 스냅샷

---

## 📋 개요

이 시스템은 시간대에 따라 자동으로 주간/야간 모드를 전환하며, 사람 감지(YOLO) 및 모션 감지(배경차분)를 수행합니다.

### 주요 기능

- **주간 모드 (Day)**: YOLO로 사람을 30초 연속 감지 시 "ON!!!" 1회 출력
- **야간 모드 (Night)**:
  - **1단계**: 10분간 사람 미감지 확인 → "OFF!!!" 1회 출력
  - **2단계**: 배경차분 기반 모션 감지 → 스냅샷 자동 저장
- **자동/강제 모드**: 시간 기반 자동 전환 또는 주간/야간 강제 설정

---

## 📦 파일 구성

```
autostart_autodown/
├── ROBOTCAM_UI.py              # 원본 (Tkinter GUI 버전)
├── ROBOTCAM_HEADLESS.py        # Headless 버전 (Docker/서버용) ⭐
├── config.json                 # 설정 파일 ⭐
├── yolo12n.pt                  # YOLO 모델 가중치
├── install_dependencies.sh     # 의존성 설치 스크립트
├── setup_x11.sh               # X11 디스플레이 설정 (HOST용)
├── run_with_display.sh        # 디스플레이와 함께 실행
├── test_camera.py             # 카메라 테스트
├── test_basic.py              # 기본 모션 감지 테스트
└── README.md                  # 이 파일
```

---

## 🚀 빠른 시작

### 1단계: 의존성 설치 (최초 1회)

```bash
cd /home/dkutest/my_ai_project/autostart_autodown
bash install_dependencies.sh
```

설치되는 패키지:
- `python3-pip`
- `ultralytics` (YOLOv8/v12)
- `paho-mqtt` (MQTT 통신용)

### 2단계: 카메라 테스트 (선택사항)

```bash
# 카메라 장치 확인
python3 test_camera.py

# 기본 모션 감지 테스트
python3 test_basic.py
```

### 3단계: 실행

#### Headless 모드 (권장)
```bash
python3 ROBOTCAM_HEADLESS.py
```

#### GUI 모드
```bash
# config.json에서 display_window를 true로 설정
./run_with_display.sh
```

---

## ⚙️ 설정 가이드

### 설정 파일: `config.json`

| 파라미터 | 라인 | 기본값 | 설명 |
|---------|------|--------|------|
| `mode` | 2 | `"auto"` | 모드: `"auto"`, `"day"`, `"night"` |
| `day_start` | 3 | `"07:30"` | 주간 시작 시각 (HH:MM) |
| `day_end` | 4 | `"19:30"` | 주간 종료 시각 (HH:MM) |
| `camera_index` | 5 | `1` | 카메라 장치 번호 |
| `yolo_model` | 6 | `"yolo12n.pt"` | YOLO 모델 경로 |
| `yolo_confidence` | 7 | `0.7` | YOLO 신뢰도 임계값 (0.0-1.0) |
| `detection_hold_sec` | 8 | `30` | 사람 연속 감지 시간 (초) |
| `night_check_minutes` | 9 | `10` | 야간 사람 미감지 확인 시간 (분) |
| `motion_min_area` | 10 | `1500` | 모션 감지 최소 면적 (낮을수록 민감) |
| `snapshot_dir` | 11 | `"Detection"` | 스냅샷 저장 폴더 |
| `snapshot_cooldown_sec` | 12 | `10` | 스냅샷 저장 최소 간격 (초) |
| **`display_window`** | 13 | `false` | **GUI 창 표시** (`true`/`false`) ⭐ |
| `window_width` | 14 | `1280` | 창 너비 |
| `window_height` | 15 | `720` | 창 높이 |
| **`mqtt_enabled`** | 16 | `false` | **MQTT 통신 활성화** (`true`/`false`) ⭐ |
| `mqtt_broker` | 17 | `"localhost"` | MQTT 브로커 주소 |
| `mqtt_port` | 18 | `1883` | MQTT 브로커 포트 |
| `mqtt_topic` | 19 | `"robot/control"` | MQTT 토픽 이름 |
| `mqtt_qos` | 20 | `1` | MQTT QoS 레벨 (0, 1, 2) |
| `mqtt_client_id` | 21 | `"robotcam_jetson"` | MQTT 클라이언트 ID |

### 주요 설정 변경 예시

#### 1. GUI 창 켜기/끄기
```json
"display_window": true,    // GUI 창 표시
"display_window": false,   // Headless (콘솔만)
```

#### 2. 빠른 사람 감지 (30초 → 10초)
```json
"detection_hold_sec": 10,
```

#### 3. 모션 감지 민감도 높이기
```json
"motion_min_area": 500,    // 기본값 1500에서 낮춤
```

#### 4. 주간/야간 강제 모드
```json
"mode": "day",     // 항상 주간 모드
"mode": "night",   // 항상 야간 모드
"mode": "auto",    // 시간 기반 자동 전환
```

#### 5. MQTT 통신 활성화
```json
"mqtt_enabled": true,
"mqtt_broker": "192.168.1.100",  // 제어 PC IP
"mqtt_topic": "robot/control",
```

---

## 🎛️ 실행 옵션

### 기본 실행
```bash
python3 ROBOTCAM_HEADLESS.py
```

### 커맨드라인 옵션
```bash
# 강제 주간 모드 (테스트용)
python3 ROBOTCAM_HEADLESS.py --mode day

# 강제 야간 모드 (테스트용)
python3 ROBOTCAM_HEADLESS.py --mode night

# 다른 설정 파일 사용
python3 ROBOTCAM_HEADLESS.py --config my_config.json
```

### 종료 방법
- **GUI 모드**: 창에서 `q` 키 누르기
- **Headless 모드**: `Ctrl+C`

---

## 🐳 Docker 환경 설정

### Docker에서 GUI 표시하려면

**1. HOST에서 X11 설정 (최초 1회)**
```bash
# 컨테이너 밖에서 실행
cd /home/dkutest/my_ai_project
./setup_x11.sh
```

**2. Docker 재시작**
```bash
docker-compose down
docker-compose up -d
docker-compose exec ai-dev bash
```

**3. 컨테이너 내부에서 실행**
```bash
cd /project/autostart_autodown
python3 ROBOTCAM_HEADLESS.py
```

### Headless 모드 (GUI 불필요)
```bash
# config.json에서 display_window를 false로 설정
cd /project/autostart_autodown
python3 ROBOTCAM_HEADLESS.py
```

---

## 📊 출력 형식

### 콘솔 출력

#### 주간 모드
```
[CONFIG] mode=auto | day=07:30~19:30
[CONFIG] camera=1 | display=false
[INIT] Loading YOLO model: yolo12n.pt
[INIT] Opening camera 1...
[INIT] Camera OK - Resolution: 640x360
[INIT] Initialization complete. Starting main loop...
[MODE] Switched to DAY mode.

==================================================
ON !!!
==================================================
```

#### 야간 모드
```
[MODE] Switched to NIGHT mode. Checking for no-person for 10 minutes...

==================================================
OFF !!!
==================================================

[MODE] Entering snapshot mode...
[SNAPSHOT] 2025-01-30 23:15:42 -> Detection/20250130/231542.jpg
[SNAPSHOT] 2025-01-30 23:15:55 -> Detection/20250130/231555.jpg
```

### 스냅샷 저장 구조
```
Detection/
├── 20250130/              # 날짜별 폴더
│   ├── 231542.jpg         # 시간_밀리초.jpg
│   ├── 231555.jpg
│   └── 232103.jpg
└── 20250131/
    ├── 003021.jpg
    └── 010545.jpg
```

---

## 🔧 문제 해결

### 1. 카메라 열기 실패
```
[ERROR] Failed to open camera 1
```

**해결:**
```bash
# 카메라 장치 확인
ls -l /dev/video*

# config.json에서 camera_index 변경
"camera_index": 0,  # 또는 1, 2 등
```

### 2. YOLO 모델 로드 실패
```
ModuleNotFoundError: No module named 'ultralytics'
```

**해결:**
```bash
bash install_dependencies.sh
# 또는
pip3 install ultralytics
```

### 3. GUI 창이 표시되지 않음 (Docker)
```
qt.qpa.xcb: could not connect to display
```

**해결:**
```bash
# HOST에서 실행
./setup_x11.sh
docker-compose down
docker-compose up -d
```

**또는 Headless 모드 사용:**
```json
"display_window": false,
```

### 4. 모션 감지가 너무 민감함
```json
// config.json
"motion_min_area": 3000,  // 기본값 1500에서 증가
```

### 5. 사람 감지가 너무 느림
```json
// config.json
"detection_hold_sec": 10,    // 기본값 30에서 감소
"yolo_confidence": 0.5,      // 기본값 0.7에서 감소
```

---

## 📡 MQTT 통신

MQTT를 통해 ON/OFF 신호를 제어 PC로 전송할 수 있습니다.

### MQTT 설정

#### 1. MQTT 활성화
```json
// config.json
"mqtt_enabled": true,
"mqtt_broker": "192.168.1.100",  // 제어 PC IP 주소
"mqtt_port": 1883,
"mqtt_topic": "robot/control",
"mqtt_qos": 1,
"mqtt_client_id": "robotcam_jetson"
```

#### 2. 전송 메시지
- **주간 모드**: 사람 30초 연속 감지 시 → `"ON"` 메시지 전송
- **야간 모드**: 10분간 사람 미감지 시 → `"OFF"` 메시지 전송

#### 3. 출력 예시
```
[CONFIG] MQTT=True | broker=192.168.1.100:1883 | topic=robot/control
[MQTT] Connecting to 192.168.1.100:1883...
[MQTT] Connected successfully

==================================================
ON !!!
==================================================
[MQTT] Published: ON
```

### MQTT 테스트

#### 브로커 없이 테스트 (MQTT 비활성화)
```json
"mqtt_enabled": false,
```

#### 로컬 브로커로 테스트
```bash
# 다른 터미널에서 mosquitto 구독
mosquitto_sub -h localhost -t robot/control

# ROBOTCAM 실행
python3 ROBOTCAM_HEADLESS.py --mode day
```

### MQTT 문제 해결

**연결 실패:**
```
[MQTT] Connection failed with code 1
```
→ 브로커 IP 주소와 포트 확인

**연결 거부:**
```
[MQTT] Failed to initialize: [Errno 111] Connection refused
```
→ 브로커가 실행 중인지 확인, 방화벽 설정 확인

---

## 🎯 시나리오 예시

### 시나리오 1: 자동 운영 (공장/매장) + MQTT

**설정:**
```json
{
  "mode": "auto",
  "day_start": "08:00",
  "day_end": "20:00",
  "detection_hold_sec": 30,
  "night_check_minutes": 10,
  "display_window": false,
  "mqtt_enabled": true,
  "mqtt_broker": "192.168.1.100",
  "mqtt_topic": "robot/control"
}
```

**동작:**
- 08:00 자동 주간 모드 → 사람 30초 감지 시 ON → **MQTT로 "ON" 전송**
- 20:00 자동 야간 모드 → 10분간 사람 없으면 OFF → **MQTT로 "OFF" 전송**
- 야간 모션 감지로 침입자 스냅샷
- 제어 PC(192.168.1.100)로 신호 자동 전송

### 시나리오 2: 테스트 (개발)

**설정:**
```json
{
  "mode": "day",              // 강제 주간 모드
  "detection_hold_sec": 5,    // 빠른 테스트
  "display_window": true      // 결과 확인
}
```

**실행:**
```bash
python3 ROBOTCAM_HEADLESS.py --mode day
# 5초만 사람 앞에 서면 ON 출력
```

### 시나리오 3: 야간 감시

**설정:**
```json
{
  "mode": "night",
  "motion_min_area": 800,     // 높은 민감도
  "snapshot_cooldown_sec": 5, // 빠른 저장
  "display_window": false
}
```

---

## 📖 참고 자료

### YOLO 모델
- YOLOv12n (nano): 빠르고 경량
- Confidence 0.7: 높은 정확도

### 배경차분 (Background Subtraction)
- MOG2 알고리즘 사용
- History: 500 프레임
- VarThreshold: 16 (낮을수록 민감)

### 권장 환경
- **개발**: Docker 컨테이너 (Headless)
- **배포**: Jetson Orin Nano (GUI 가능)
- **카메라**: USB 웹캠 (640x360 이상)

---

## 🔄 버전 히스토리

### v1.0 (2025-01-30)
- ✅ 초기 릴리스
- ✅ YOLO 사람 감지 (주간)
- ✅ 모션 감지 스냅샷 (야간)
- ✅ Headless 모드 지원
- ✅ JSON 설정 파일
- ✅ Docker 환경 지원
- ✅ MQTT 통신 (ON/OFF 신호 전송)
- ✅ 설정 기반 MQTT 활성화/비활성화

### v1.1 (예정)
- ⏳ 메인 GUI 통합
- ⏳ 웹 대시보드
- ⏳ 원격 설정 변경
- ⏳ MQTT 양방향 통신 (명령 수신)

---

## 📞 지원

문제가 발생하면:
1. `test_camera.py`로 카메라 확인
2. `config.json` 설정 확인
3. 콘솔 오류 메시지 확인
4. README 문제 해결 섹션 참조

---

**제작**: Jetson Orin Nano 자동화 시스템
**날짜**: 2025-01-30
**상태**: ✅ 프로덕션 준비 완료
