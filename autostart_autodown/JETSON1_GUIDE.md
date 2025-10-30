# Jetson Orin #1 - 통합 모니터링 시스템

주방용 대형 화면 통합 모니터링 시스템 (40-50대 조리사 대상)

---

## 📋 개요

Jetson Orin #1은 세 가지 기능을 하나의 GUI로 통합한 시스템입니다:

1. **자동 ON/OFF** - YOLO 사람 감지 + MQTT 신호 전송
2. **볶음 모니터링** - 볶음 데이터 수집용 카메라
3. **진동 감지** - USB2RS485 진동 센서 모니터링 (향후 구현)

### 대상 사용자
- 40-50대 주방 조리사
- 큰 글씨, 명확한 색상, 간단한 조작

---

## 🚀 실행 방법

### 1단계: 의존성 확인

```bash
cd /home/dkutest/my_ai_project/autostart_autodown
bash install_dependencies.sh  # 최초 1회
```

### 2단계: 설정 확인

`config.json` 파일에서 다음 항목 확인:

```json
{
  "camera_index": 1,              // 자동 ON/OFF 카메라
  "stirfry_camera_index": 2,      // 볶음 모니터링 카메라
  "mqtt_enabled": true,           // MQTT 활성화
  "mqtt_broker": "192.168.1.100"  // 제어 PC IP
}
```

### 3단계: 실행

```bash
# Docker 외부 (HOST)에서 X11 설정 (최초 1회)
cd /home/dkutest/my_ai_project
./setup_x11.sh

# Docker 재시작
docker-compose down
docker-compose up -d
docker-compose exec ai-dev bash

# 컨테이너 내부에서 실행
cd /project/autostart_autodown
python3 JETSON1_INTEGRATED.py
```

---

## 🎨 GUI 구성

### 화면 레이아웃

```
┌────────────────────────────────────────────────────────────┐
│  🤖 ROBOTCAM 통합 시스템         시간: 14:23:45  2025-10-30 │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ 📡 자동 ON/OFF│  │ 🍳 볶음 모니터링│  │ 📊 진동 감지  │    │
│  │              │  │              │  │              │    │
│  │ 모드: 주간    │  │ [카메라 화면] │  │   🔧         │    │
│  │ 감지: 대기    │  │              │  │   준비 중     │    │
│  │ 상태: 정상    │  │ 녹화: ⚫ OFF  │  │ 센서: 미연결  │    │
│  │ MQTT: 연결됨  │  │ 저장: 0장     │  │ USB2RS485    │    │
│  │              │  │              │  │              │    │
│  │ [작은 화면]   │  │ [▶ 시작]     │  │              │    │
│  │              │  │ [⏹ 중지]     │  │              │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
│                                                            │
│  [⚙️ 설정]  [🚪 종료]                    시스템 정상 ✓     │
└────────────────────────────────────────────────────────────┘
```

### 패널 1: 📡 자동 ON/OFF

**기능:**
- YOLO로 사람 감지 (주간 모드)
- 10분 미감지 확인 (야간 모드)
- MQTT로 ON/OFF 신호 전송
- 야간 모션 스냅샷 저장

**상태 표시:**
- **모드: 주간/야간** - 현재 동작 모드
- **감지: 대기/사람 확인/N초 남음** - 감지 상태
- **상태: 정상/오류** - 시스템 상태
- **MQTT: 연결됨/연결 끊김** - MQTT 연결 상태

**색상 코드:**
- 🟢 녹색 = 정상
- 🟡 노란색 = 경고
- 🔴 빨간색 = 오류
- 🔵 파란색 = 정보

### 패널 2: 🍳 볶음 모니터링

**기능:**
- 실시간 카메라 화면 표시
- 수동 녹화 시작/중지
- 프레임별 이미지 저장

**조작 방법:**
1. **[▶ 시작]** 버튼 클릭 → 녹화 시작
   - 녹화 표시: 🔴 ON (빨간색)
   - 저장 개수 실시간 표시
2. **[⏹ 중지]** 버튼 클릭 → 녹화 중지
   - 총 저장 개수 확인 창 표시

**저장 경로:**
```
StirFry_Data/
├── 20251030/              # 날짜별 폴더
│   ├── 142345_123.jpg     # HH:MM:SS_밀리초.jpg
│   ├── 142345_156.jpg
│   └── 142345_189.jpg
└── 20251031/
```

### 패널 3: 📊 진동 감지

**현재 상태: 준비 중**

향후 구현 예정:
- USB2RS485 진동 센서 연결
- 초기 시동 시 진동 체크
- 로봇 캘리브레이션 후 검증
- 이상 진동 감지 시 알림

---

## ⚙️ 설정 가이드

### config.json 주요 파라미터

| 파라미터 | 라인 | 기본값 | 설명 |
|---------|------|--------|------|
| `camera_index` | 5 | `1` | 자동 ON/OFF 카메라 번호 |
| `stirfry_camera_index` | 22 | `2` | 볶음 모니터링 카메라 번호 |
| `stirfry_save_dir` | 23 | `"StirFry_Data"` | 볶음 데이터 저장 폴더 |
| `mqtt_enabled` | 16 | `false` | MQTT 통신 활성화 |
| `mqtt_broker` | 17 | `"localhost"` | MQTT 브로커 IP |

### 설정 변경 예시

#### 1. 카메라 번호 변경
```bash
# 사용 가능한 카메라 확인
ls -l /dev/video*

# config.json 수정
"camera_index": 0,          # 자동 ON/OFF용
"stirfry_camera_index": 1,  # 볶음 모니터링용
```

#### 2. MQTT 활성화
```json
"mqtt_enabled": true,
"mqtt_broker": "192.168.1.100",  // 제어 PC IP
"mqtt_topic": "robot/control",
```

---

## 🎯 사용 시나리오

### 시나리오 1: 일반 운영 (자동 모드)

**시간대:**
- 07:30 - 19:30: 주간 모드 (사람 감지)
- 19:30 - 07:30: 야간 모드 (미감지 확인 + 모션 스냅샷)

**동작:**
1. 아침 07:30 자동 주간 모드 전환
2. 조리사 출근 → 30초 감지 → "ON" 신호 전송
3. 저녁 19:30 자동 야간 모드 전환
4. 10분간 사람 없음 → "OFF" 신호 전송
5. 이후 모션 감지 시 스냅샷 저장

### 시나리오 2: 볶음 데이터 수집

**준비:**
1. 프로그램 실행 후 중간 패널(🍳 볶음 모니터링) 확인
2. 카메라 화면에 볶음 과정이 잘 보이는지 확인

**녹화:**
1. 볶음 시작 직전 **[▶ 시작]** 버튼 클릭
2. 녹화 중 표시: "녹화: 🔴 ON" (빨간색)
3. 저장 개수 실시간 확인: "저장: 1234장"
4. 볶음 완료 후 **[⏹ 중지]** 버튼 클릭
5. 완료 메시지 확인

**데이터 확인:**
```bash
cd /project/autostart_autodown/StirFry_Data
ls -lh 20251030/  # 오늘 날짜 폴더
```

---

## 🔧 문제 해결

### 1. GUI 창이 표시되지 않음

**증상:**
```
qt.qpa.xcb: could not connect to display
```

**해결:**
```bash
# HOST에서 실행 (Docker 외부)
cd /home/dkutest/my_ai_project
./setup_x11.sh

# Docker 재시작
docker-compose down
docker-compose up -d
docker-compose exec ai-dev bash

# 컨테이너 내부에서 재실행
cd /project/autostart_autodown
python3 JETSON1_INTEGRATED.py
```

### 2. 카메라 열기 실패

**증상:**
```
[ERROR] Failed to open camera 1
[ERROR] Failed to open stir-fry camera 2
```

**해결:**
```bash
# 카메라 장치 확인
ls -l /dev/video*

# config.json에서 카메라 번호 수정
# 예: video0만 있으면 둘 다 0으로 설정 (같은 카메라 공유)
"camera_index": 0,
"stirfry_camera_index": 0,
```

### 3. MQTT 연결 실패

**증상:**
- "MQTT: 오류" 빨간색 표시

**해결:**
```bash
# 브로커 IP 확인
ping 192.168.1.100

# config.json 수정
"mqtt_broker": "정확한_IP_주소",

# 또는 테스트 시 MQTT 비활성화
"mqtt_enabled": false,
```

### 4. 볶음 녹화 버튼 클릭 안 됨

**원인:**
- 볶음 카메라(camera 2)가 열리지 않음

**해결:**
```bash
# 카메라 2 확인
ls -l /dev/video2

# 없으면 카메라 1과 공유
"stirfry_camera_index": 1,
```

### 5. 글씨가 너무 작음

**해결:**
`JETSON1_INTEGRATED.py` 파일 수정 (라인 74-76):
```python
LARGE_FONT = ("맑은 고딕", 32, "bold")    # 24 → 32
MEDIUM_FONT = ("맑은 고딕", 22)          # 18 → 22
NORMAL_FONT = ("맑은 고딕", 18)          # 14 → 18
```

---

## 🔄 업데이트 히스토리

### v1.0 (2025-10-30)
- ✅ 3패널 통합 GUI 구현
- ✅ 자동 ON/OFF 시스템 통합
- ✅ 볶음 모니터링 카메라 구현
- ✅ 진동 센서 플레이스홀더
- ✅ MQTT 통신 지원
- ✅ 대형 화면 UI (주방 조리사용)
- ✅ Docker 환경 지원

### v1.1 (예정)
- ⏳ USB2RS485 진동 센서 통합
- ⏳ 진동 이상 감지 알고리즘
- ⏳ 설정 UI (GUI 내 설정 변경)
- ⏳ 원격 모니터링 웹 대시보드

---

## 📚 관련 파일

| 파일 | 용도 |
|------|------|
| `JETSON1_INTEGRATED.py` | Jetson #1 통합 GUI (메인 프로그램) |
| `ROBOTCAM_HEADLESS.py` | Headless 버전 (테스트용) |
| `ROBOTCAM_UI.py` | 원본 Tkinter 버전 |
| `config.json` | 설정 파일 |
| `JETSON1_GUIDE.md` | 이 문서 |
| `README.md` | 일반 사용자 가이드 |

---

## 📞 지원

문제 발생 시:
1. 콘솔 출력 메시지 확인
2. `config.json` 설정 확인
3. 이 문서의 문제 해결 섹션 참조
4. Docker 로그 확인: `docker-compose logs -f ai-dev`

---

**제작**: Jetson Orin Nano #1 통합 시스템
**날짜**: 2025-10-30
**상태**: ✅ 프로덕션 준비 완료 (진동 센서 제외)
