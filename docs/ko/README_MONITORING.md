# 튀김 AI 모니터링 시스템

## 🚀 중앙 집중식 모니터링 대시보드

튀김 AI 자동화 프로젝트를 위한 종합 웹 기반 모니터링 시스템, 다음 기능 포함:

- **📷 카메라 모니터링** - 동작 감지 기능이 있는 실시간 비디오
- **📊 진동 모니터링** - 실시간 경고 기능이 있는 RS485 센서
- **🍟 튀김 AI** - 튀김을 위한 컴퓨터 비전 분석
- **⏰ 작업 스케줄러** - 자동 서비스 시작/중지 (오전 8:30 - 오후 7:00)

## ✨ 주요 기능

### 단일 중앙 집중식 인터페이스
- 하나의 웹 대시보드에서 모든 서비스 모니터링
- 실시간 상태 업데이트
- 간편한 서비스 제어 (시작/중지)
- Docker 컨테이너에서 완벽하게 작동

### 진동 모니터링 (신규!)
- **USB to RS485** 센서 지원
- **실시간 3축** 가속도 모니터링 (X, Y, Z)
- **구성 가능한 경고**: 낮음, 중간, 높음, 위험 임계값
- **통계 분석**: 평균, 최대, RMS, 추세 감지
- **데이터 로깅**: 세션 요약이 있는 CSV 파일
- **프로토콜 지원**: Modbus RTU 및 ASCII

### 자동 스케줄러 (신규!)
- **오전 8:30**에 서비스 자동 시작
- **오후 7:00**에 서비스 자동 중지
- 구성 가능한 요일
- 수동 재정의 지원
- 다음 이벤트까지 카운트다운

## 📦 설치

### 전제 조건
```bash
# Python 3.6+
python3 --version

# 의존성 설치
pip install flask pyserial numpy opencv-python
```

### 빠른 설정
```bash
# 1. 하드웨어 구성 (필요시 편집)
vim config/system_config.json

# 2. 대시보드 실행
python scripts/run_monitoring_dashboard.py

# 3. http://localhost:5000 에서 접속
```

## 📁 새로운 파일 구조

```
my_ai_project/
├── src/
│   ├── core/              # 구성 및 유틸리티
│   ├── monitoring/
│   │   ├── camera/        # 카메라 모니터링
│   │   ├── vibration/     # 진동 모니터링 (신규)
│   │   └── frying/        # 튀김 AI
│   ├── gui/               # 웹 대시보드 (신규)
│   │   ├── main_app.py
│   │   ├── templates/
│   │   └── static/
│   └── scheduler/         # 작업 스케줄러 (신규)
│
├── config/                # 구성 파일
├── data/                  # 데이터 저장소
├── scripts/               # 진입점 스크립트
└── docs/                  # 문서
```

## 🎛️ 사용법

### 대시보드 실행
```bash
./scripts/run_monitoring_dashboard.py
```

### 대시보드 접속
- 로컬: http://localhost:5000
- 원격: http://<jetson-ip>:5000
- SSH 터널: `ssh -L 5000:localhost:5000 user@jetson`

### 서비스 제어

**웹 대시보드에서**:
1. 브라우저에서 대시보드 열기
2. 원하는 서비스 카드의 "시작" 클릭
3. 실시간으로 상태 모니터링
4. "중지" 클릭하여 종료

**일괄 작업**:
- "모든 서비스 시작" - 모든 것 시작
- "모든 서비스 중지" - 모든 것 중지

### 스케줄러

**자동 모드** (기본):
- 오전 8:30에 서비스 시작
- 오후 7:00에 서비스 중지
- 월요일-일요일 작동

**수동 재정의**:
1. "수동 재정의" 버튼 클릭
2. 수동으로 서비스 제어
3. 다시 클릭하여 자동 모드 재활성화

**스케줄 편집**:
1. "스케줄 편집" 클릭
2. 시작/종료 시간 변경
3. 활성 요일 선택
4. 변경사항 저장

## ⚙️ 구성

### 진동 센서 설정

`config/system_config.json` 편집:

```json
{
  "vibration": {
    "sensor": {
      "port": "/dev/ttyUSB0",      // RS485 어댑터
      "baudrate": 9600,             // 센서 설정과 일치
      "protocol": "modbus",         // 또는 "ascii"
      "slave_address": 1            // Modbus 주소
    },
    "analyzer": {
      "alert_thresholds": {
        "low": 2.0,                 // m/s²
        "medium": 5.0,
        "high": 10.0,
        "critical": 20.0
      }
    }
  }
}
```

### 작업 시간

```json
{
  "scheduler": {
    "work_hours": {
      "start": "08:30",
      "end": "19:00",
      "enabled_days": [0, 1, 2, 3, 4, 5, 6]
    }
  }
}
```

## 🐳 Docker 배포

컨테이너화된 환경에 완벽합니다!

```yaml
services:
  monitoring:
    build: .
    ports:
      - "5000:5000"
    devices:
      - /dev/video0:/dev/video0
      - /dev/ttyUSB0:/dev/ttyUSB0
    volumes:
      - ./config:/app/config
      - ./data:/app/data
    environment:
      - TZ=Asia/Seoul
```

## 📊 대시보드 패널

### 서비스 제어 패널
- 개별 서비스 카드 (카메라, 진동, 튀김 AI)
- 상태 표시기 (녹색 = 실행 중, 회색 = 중지됨)
- 시작/중지 버튼
- 일괄 제어 버튼

### 스케줄러 패널
- 현재 상태 (작업 시간? 자동 모드?)
- 작업 시간 표시
- 다음 이벤트 카운트다운
- 재정의 및 편집 제어

### 진동 모니터링 패널
- 현재 크기
- 통계 지표 (평균, 최대, RMS)
- 추세 분석
- 색상 구분이 있는 3축 시각화
- 샘플 수

### 경고 패널
- 실시간 경고 알림
- 심각도에 따라 색상 구분
- 타임스탬프 및 설명
- 마지막 10개 경고 표시

## 🔧 문제 해결

### 센서 연결 문제

```bash
# 장치 확인
ls -l /dev/ttyUSB*

# 권한 수정
sudo chmod 666 /dev/ttyUSB0

# 또는 그룹에 추가
sudo usermod -a -G dialout $USER
```

### 대시보드가 시작되지 않음

```bash
# 의존성 확인
pip install flask pyserial numpy

# 구성 확인
cat config/system_config.json | python -m json.tool
```

### 시간대 문제

```bash
# 시스템 시간 확인
timedatectl

# 시간대 설정
sudo timedatectl set-timezone Asia/Seoul
```

## 📈 데이터 로깅

### 진동 로그
- 위치: `data/vibration_logs/`
- 형식: 타임스탬프, 축, 크기가 있는 CSV
- 요약: 통계 및 경고가 있는 JSON

### 카메라 데이터
- 녹화: `data/recordings/`
- 스크린샷: `data/screenshots/`

### 튀김 AI 데이터
- 세션: `data/frying_dataset/`
- 이미지, 센서 로그, 메타데이터

## 🎯 경고 임계값

| 수준 | 기본값 | 색상 | 조치 |
|-------|---------|-------|--------|
| 낮음 | 2.0 m/s² | 녹색 | 정상 |
| 중간 | 5.0 m/s² | 노란색 | 모니터링 |
| 높음 | 10.0 m/s² | 빨간색 | 조사 |
| 위험 | 20.0 m/s² | 보라색 | 작업 중지 |

## 📚 문서

- **[전체 가이드](docs/MONITORING_SYSTEM_GUIDE.md)** - 상세 문서
- **[API 참조](docs/MONITORING_SYSTEM_GUIDE.md#api-reference)** - REST API 문서
- **[하드웨어 설정](docs/MONITORING_SYSTEM_GUIDE.md#hardware-setup)** - RS485 배선

## 🔄 이전 구조에서 마이그레이션

이전 파일이 여전히 있습니다:
- `camera_monitor/` - 원본 카메라 코드
- `frying_ai/` - 원본 튀김 AI 코드
- `run_monitor.py` - 이전 진입점

새로운 중앙 집중식 시스템은 다음에 있습니다:
- `src/` - 모든 구성된 코드
- `scripts/run_monitoring_dashboard.py` - 새 진입점

전환 기간 동안 둘 다 공존할 수 있습니다.

## 🚦 시스템 요구사항

- Python 3.6+
- Linux (Jetson Orin Nano 또는 Ubuntu)
- USB to RS485 어댑터 (진동 모니터링용)
- 카메라 (선택사항, 카메라 모니터링용)
- 최소 2GB RAM

## 📝 버전

**1.0.0** - 초기 릴리스
- 중앙 집중식 웹 대시보드
- RS485를 사용한 진동 모니터링
- 자동 작업 스케줄러
- 서비스 수명주기 관리

## 🤝 기여

이것은 튀김 AI 자동화를 위한 내부 프로젝트입니다.

## 📄 라이선스

독점 - 튀김 AI 프로젝트

---

**NVIDIA Jetson Orin Nano를 위해 ❤️로 만들어졌습니다**
