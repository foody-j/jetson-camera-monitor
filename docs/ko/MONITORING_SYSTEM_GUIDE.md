# 모니터링 시스템 가이드

## 개요

이것은 튀김 AI 자동화 프로젝트를 위한 종합 모니터링 시스템입니다. 여러 서비스를 모니터링하고 제어하는 중앙 집중식 웹 기반 대시보드를 제공합니다:

- **카메라 모니터링**: 동작 감지 기능이 있는 실시간 비디오 감시
- **진동 모니터링**: 경고 기능이 있는 RS485 기반 진동 센서 모니터링
- **튀김 AI**: 컴퓨터 비전 분석을 사용한 튀김 자동화
- **작업 스케줄러**: 구성 가능한 작업 시간을 기반으로 한 자동 시작/중지

## 기능

### 🎛️ 중앙 집중식 대시보드
- 모든 모니터링 서비스를 제어하는 단일 웹 인터페이스
- 실시간 상태 업데이트 (1초 폴링)
- 서비스 시작/중지 제어
- 시스템 상태 모니터링

### ⏰ 작업 스케줄러
- **오전 8:30** 자동 서비스 시작
- **오후 7:00** 자동 종료
- 구성 가능한 요일
- 수동 재정의 지원
- 안전한 종료를 위한 유예 기간

### 📊 진동 모니터링
- RS485/Modbus 센서 지원 (USB to RS485 어댑터)
- 실시간 3축 가속도 모니터링
- 구성 가능한 경고 임계값 (낮음, 중간, 높음, 위험)
- 통계 분석 (평균, 최대, RMS, 추세)
- CSV 파일로 데이터 로깅
- 경고 알림

### 📷 카메라 모니터링
- 동작 감지
- 자동 녹화
- 스크린샷 캡처
- 구성 가능한 해상도 및 FPS

### 🍟 튀김 AI
- 실시간 색상 분석
- 온도 센서 통합
- 세션 기반 데이터 수집
- 식품 분할

## 파일 구조

```
my_ai_project/
├── src/                          # 모든 소스 코드
│   ├── core/                     # 핵심 모듈
│   │   ├── config.py             # 구성 관리
│   │   └── utils.py              # 유틸리티 함수
│   │
│   ├── monitoring/               # 모니터링 모듈
│   │   ├── camera/               # 카메라 모니터링
│   │   │   ├── camera_base.py
│   │   │   ├── motion_detector.py
│   │   │   ├── recorder.py
│   │   │   └── monitor.py
│   │   │
│   │   ├── vibration/            # 진동 모니터링
│   │   │   ├── __init__.py
│   │   │   ├── rs485_sensor.py   # RS485 센서 인터페이스
│   │   │   ├── vibration_analyzer.py  # 데이터 분석
│   │   │   └── vibration_detector.py  # 메인 탐지기
│   │   │
│   │   └── frying/               # 튀김 AI
│   │       ├── frying_data_collector.py
│   │       ├── food_segmentation.py
│   │       └── sensor_simulator.py
│   │
│   ├── gui/                      # 웹 대시보드
│   │   ├── main_app.py           # Flask 애플리케이션
│   │   ├── templates/
│   │   │   └── dashboard.html    # 메인 대시보드 UI
│   │   └── static/
│   │       ├── css/
│   │       │   └── dashboard.css
│   │       └── js/
│   │           └── dashboard.js
│   │
│   └── scheduler/                # 작업 스케줄러
│       ├── work_scheduler.py     # 스케줄 관리
│       └── service_manager.py    # 서비스 수명주기
│
├── config/                       # 구성 파일
│   └── system_config.json        # 메인 시스템 구성
│
├── data/                         # 데이터 저장소
│   ├── vibration_logs/           # 진동 데이터 로그
│   ├── recordings/               # 카메라 녹화
│   ├── screenshots/              # 카메라 스크린샷
│   └── frying_dataset/           # 튀김 AI 데이터
│
├── scripts/                      # 진입점 스크립트
│   └── run_monitoring_dashboard.py  # 대시보드 실행
│
└── docs/                         # 문서
    └── MONITORING_SYSTEM_GUIDE.md
```

## 빠른 시작

### 1. 의존성 설치

```bash
pip install flask pyserial numpy
```

### 2. 하드웨어 구성

하드웨어에 맞게 `config/system_config.json`을 편집하세요:

```json
{
  "vibration": {
    "sensor": {
      "port": "/dev/ttyUSB0",    # RS485 어댑터 경로
      "baudrate": 9600,           # 센서 보드레이트와 일치
      "protocol": "modbus",       # 또는 "ascii"
      "slave_address": 1          # Modbus 슬레이브 주소
    }
  }
}
```

### 3. 대시보드 실행

```bash
# 방법 1: Python 사용
python scripts/run_monitoring_dashboard.py

# 방법 2: 직접 실행
./scripts/run_monitoring_dashboard.py
```

### 4. 대시보드 접속

브라우저를 열고 다음 주소로 이동하세요:
- **로컬**: http://localhost:5000
- **원격**: http://<jetson-ip>:5000

Docker/SSH 접속의 경우 포트 포워딩을 설정하세요:
```bash
ssh -L 5000:localhost:5000 user@jetson-ip
```

## 구성

### 시스템 구성 (`config/system_config.json`)

#### 진동 모니터링
```json
{
  "vibration": {
    "enabled": true,
    "sensor": {
      "port": "/dev/ttyUSB0",
      "baudrate": 9600,
      "protocol": "modbus",        // "modbus" 또는 "ascii"
      "slave_address": 1,
      "timeout": 1.0
    },
    "analyzer": {
      "window_size": 100,          // 분석할 샘플 수
      "alert_thresholds": {
        "low": 2.0,                // m/s²
        "medium": 5.0,
        "high": 10.0,
        "critical": 20.0
      }
    },
    "sampling_rate": 10.0          // Hz (초당 샘플)
  }
}
```

#### 작업 스케줄러
```json
{
  "scheduler": {
    "enabled": true,
    "work_hours": {
      "start": "08:30",            // HH:MM 형식
      "end": "19:00",
      "enabled_days": [0, 1, 2, 3, 4, 5, 6]  // 0=월, 6=일
    },
    "auto_start_enabled": true,
    "auto_stop_enabled": true
  }
}
```

#### 웹 서버
```json
{
  "web_server": {
    "host": "0.0.0.0",             // 모든 인터페이스에서 수신
    "port": 5000,
    "debug": false
  }
}
```

## 대시보드 사용법

### 서비스 제어

**개별 서비스 시작**:
1. 서비스 카드의 "시작" 버튼 클릭
2. 실행 중일 때 서비스 상태 표시등이 녹색으로 변경됨

**개별 서비스 중지**:
1. 서비스 카드의 "중지" 버튼 클릭
2. 중지되면 서비스 상태 표시등이 회색으로 변경됨

**일괄 제어**:
- "모든 서비스 시작": 모든 구성된 서비스 시작
- "모든 서비스 중지": 실행 중인 모든 서비스 중지

### 작업 스케줄러

**자동 모드**:
- 구성된 시작 시간에 서비스가 자동으로 시작됨
- 구성된 종료 시간에 서비스가 자동으로 중지됨
- 활성화된 요일에만 작동함

**수동 재정의**:
1. "수동 재정의" 버튼 클릭
2. 자동 스케줄링이 비활성화됨
3. 필요에 따라 서비스를 수동으로 제어
4. 자동 스케줄링을 다시 활성화하려면 버튼을 다시 클릭

**스케줄 편집**:
1. "스케줄 편집" 버튼 클릭
2. 시작 시간, 종료 시간 및 활성화된 요일 수정
3. "변경사항 저장" 클릭
4. 새 스케줄이 즉시 적용됨

### 진동 모니터링

**표시되는 지표**:
- **현재 크기**: 실시간 진동 수준 (m/s²)
- **평균 크기**: 윈도우에 대한 평균
- **최대 크기**: 윈도우의 최대값
- **RMS 값**: 제곱 평균 제곱근 (에너지 수준)
- **추세**: 증가, 감소 또는 안정
- **샘플 수**: 수집된 총 샘플 수

**축 시각화**:
- X, Y, Z축 값이 색상으로 구분된 막대로 표시됨
- 녹색: 정상 (<2 m/s²)
- 노란색: 상승 (2-5 m/s²)
- 빨간색: 높음 (5-10 m/s²)
- 보라색: 위험 (>10 m/s²)

**경고**:
- "최근 경고" 패널에 실시간으로 표시됨
- 심각도에 따라 색상으로 구분됨
- 타임스탬프 및 설명 포함

### 경고 임계값

| 수준 | 기본값 (m/s²) | 설명 |
|-------|----------------|-------------|
| 낮음 | 2.0 | 약한 진동 감지 |
| 중간 | 5.0 | 중간 진동 - 모니터링 |
| 높음 | 10.0 | 높은 진동 - 조사 필요 |
| 위험 | 20.0 | 위험한 진동 - 작업 중지 |

## 하드웨어 설정

### RS485 진동 센서

**연결**:
1. USB to RS485 어댑터를 Jetson에 연결
2. 센서를 RS485 단자에 연결 (A, B, GND)
3. 사양에 따라 센서에 전원 공급
4. 장치가 `/dev/ttyUSB0` (또는 유사)로 표시되는지 확인

**장치 확인**:
```bash
ls -l /dev/ttyUSB*
dmesg | grep tty
```

**Modbus 구성**:
- 기본 슬레이브 주소: 1
- 보드레이트: 9600 (센서 매뉴얼 확인)
- 패리티: 없음
- 정지 비트: 1

**지원되는 프로토콜**:
- **Modbus RTU**: 산업 표준 (권장)
- **ASCII**: 간단한 텍스트 기반 프로토콜

### 센서 테스트

센서 연결 테스트:
```python
from src.monitoring.vibration import RS485VibrationSensor

config = {
    'port': '/dev/ttyUSB0',
    'baudrate': 9600,
    'protocol': 'modbus',
    'slave_address': 1
}

with RS485VibrationSensor(config) as sensor:
    if sensor.is_connected():
        reading = sensor.read()
        if reading:
            print(f"X: {reading.x_axis:.2f} m/s²")
            print(f"Y: {reading.y_axis:.2f} m/s²")
            print(f"Z: {reading.z_axis:.2f} m/s²")
            print(f"크기: {reading.magnitude:.2f} m/s²")
```

## 데이터 로깅

### 진동 데이터

**CSV 형식** (`data/vibration_logs/session_name.csv`):
```
timestamp,elapsed_time,x_axis,y_axis,z_axis,magnitude,temperature,frequency
1635000000.123,0.100,1.23,0.45,0.67,1.48,25.3,10.5
1635000000.223,0.200,1.25,0.47,0.69,1.52,25.4,10.6
...
```

**JSON 요약** (`data/vibration_logs/session_name_summary.json`):
- 세션 메타데이터
- 통계 요약
- 경고 이력
- 센서 구성

### 카메라 데이터

**녹화**: `data/recordings/recording_YYYYMMDD_HHMMSS.avi`

**스크린샷**: `data/screenshots/screenshot_YYYYMMDD_HHMMSS.jpg`

### 튀김 AI 데이터

**데이터셋**: `data/frying_dataset/foodtype_YYYYMMDD_HHMMSS/`
- `images/`: 타임스탬프가 있는 프레임
- `session_data.json`: 세션 메타데이터
- `sensor_log.csv`: 시계열 데이터

## 문제 해결

### 대시보드가 시작되지 않음

**Python 경로 확인**:
```bash
python3 --version  # Python 3.6+ 이상이어야 함
```

**누락된 의존성 설치**:
```bash
pip install flask pyserial numpy
```

**구성 파일 확인**:
```bash
cat config/system_config.json | python -m json.tool
```

### 진동 센서가 연결되지 않음

**장치 존재 확인**:
```bash
ls -l /dev/ttyUSB*
```

**권한 확인**:
```bash
sudo chmod 666 /dev/ttyUSB0
# 또는 사용자를 dialout 그룹에 추가:
sudo usermod -a -G dialout $USER
# 로그아웃 후 다시 로그인
```

**minicom으로 테스트**:
```bash
sudo apt install minicom
minicom -D /dev/ttyUSB0 -b 9600
```

### 서비스가 시작되지 않음

**로그 확인**:
- 콘솔 출력에 오류 표시
- 서비스 상태에 메시지와 함께 "오류" 표시

**일반적인 문제**:
- 카메라를 사용할 수 없음 (`/dev/video0` 확인)
- RS485 장치 사용 중 (다른 프로그램 종료)
- 권한 부족

### 스케줄러가 작동하지 않음

**시간 설정 확인**:
```bash
date
timedatectl
```

**활성화된 요일 확인**:
- 0 = 월요일, 6 = 일요일
- 현재 요일이 enabled_days에 있는지 확인

**수동 재정의 활성 상태**:
- "재정의 비활성화" 버튼 클릭

## Docker 배포

대시보드는 Docker 컨테이너에서 완벽하게 작동합니다.

**docker-compose.yml**:
```yaml
services:
  monitoring:
    build: .
    ports:
      - "5000:5000"
    devices:
      - /dev/video0:/dev/video0      # 카메라
      - /dev/ttyUSB0:/dev/ttyUSB0    # RS485
    volumes:
      - ./config:/app/config
      - ./data:/app/data
    environment:
      - TZ=Asia/Seoul
    command: python scripts/run_monitoring_dashboard.py
```

**실행**:
```bash
docker-compose up -d
docker-compose logs -f
```

## API 참조

### GET /api/status
전체 시스템 상태 가져오기 (프론트엔드에서 매 1초마다 호출)

**응답**:
```json
{
  "initialized": true,
  "timestamp": 1635000000.123,
  "services": [...],
  "scheduler": {...},
  "vibration": {...},
  "alerts": [...]
}
```

### POST /api/service/<service_id>/start
서비스 시작 (camera, vibration, frying)

### POST /api/service/<service_id>/stop
서비스 중지

### POST /api/services/start_all
모든 서비스 시작

### POST /api/services/stop_all
모든 서비스 중지

### POST /api/scheduler/override
수동 재정의 활성화/비활성화

**본문**:
```json
{"enable": true}
```

### POST /api/scheduler/update
작업 스케줄 업데이트

**본문**:
```json
{
  "start_time": "08:30",
  "end_time": "19:00",
  "enabled_days": [0, 1, 2, 3, 4, 5, 6]
}
```

### GET /api/vibration/latest
최신 진동 판독값 가져오기

## 모범 사례

1. **모니터링을 시작하기 전에 항상 센서 연결을 테스트**
2. **장비 기준선에 따라 경고 임계값 구성**
3. **서비스를 수동으로 제어해야 할 때 수동 재정의 사용**
4. **비정상적인 진동에 대한 경고 패널 모니터링**
5. **과거 분석을 위해 정기적으로 데이터 로그 확인**
6. **리소스를 절약하기 위해 적절한 작업 시간 설정**
7. **안정적인 배포를 위해 Docker 사용**

## 지원

문제 또는 질문이 있는 경우:
- 문제 해결 섹션 확인
- 콘솔 출력의 로그 검토
- 하드웨어 연결 확인
- 구성 파일 구문 확인

## 버전
1.0.0 - 초기 릴리스
