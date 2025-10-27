# 📹 Jetson Camera Monitor

> NVIDIA Jetson을 위한 실시간 카메라 모니터링 시스템

---

## ✨ 주요 기능

- 🎥 실시간 카메라 스트리밍 및 프레임 처리
- 📼 비디오 녹화 (자동 해상도 조정)
- 🔍 움직임 감지 및 자동 스크린샷
- ⚙️ JSON 기반 설정 관리
- 🌍 Timezone 설정 지원 (배포 환경별 시간대 관리)
- 🖥️ 헤드리스 모드 백그라운드 실행
- 🐳 Docker 환경 최적화

---

## 📋 시스템 요구사항

- NVIDIA Jetson (Orin, Xavier, Nano 등)
- Docker & Docker Compose
- Python 3.8+
- OpenCV
- 카메라 디바이스 (`/dev/video0`)

---

## 🚀 설치 및 실행

### Docker 환경 (권장)

```bash
# 저장소 클론
git clone https://github.com/yourusername/jetson-camera-monitor.git
cd jetson-camera-monitor

# X11 권한 설정 (GUI 사용 시)
xhost +local:docker

# Docker 이미지 빌드 및 실행
docker-compose build
docker-compose up -d

# 컨테이너 접속
docker exec -it my-dev-container bash

# 필수 패키지 설치
pip3 install pytz

# 모니터링 시스템 실행
python3 run_monitor.py
```

### 카메라 디바이스 추가 (필요 시)

카메라를 사용하려면 `docker-compose.camera.yml`을 함께 사용:

```bash
docker-compose -f docker-compose.yml -f docker-compose.camera.yml up -d
```

## ⚙️ 설정

### `camera_config.json`

모든 설정은 `camera_config.json` 파일에서 관리합니다:

```json
{
  "system": {
    "timezone": "Asia/Seoul",
    "log_timezone": true
  },
  "camera": {
    "index": 0,
    "resolution": {
      "width": 640,
      "height": 360
    },
    "fps": 120,
    "name": "Jetson Camera"
  },
  "recording": {
    "codec": "MJPG",
    "output_dir": "output/recordings",
    "auto_start": true
  },
  "motion_detection": {
    "enabled": true,
    "threshold": 1000,
    "min_area": 500
  },
  "screenshot": {
    "output_dir": "output/screenshots",
    "format": "jpg",
    "auto_capture_on_motion": true
  }
}
```

### 🌍 Timezone 설정

배포 환경에 따라 시간대를 변경할 수 있습니다:

```json
{
  "system": {
    "timezone": "Asia/Seoul"     // 한국
    // "timezone": "Asia/Tokyo"  // 일본
    // "timezone": "UTC"         // 표준시
    // "timezone": "America/New_York"  // 미국 동부
  }
}
```

> 💡 사용 가능한 timezone 목록은 [IANA Time Zone Database](https://www.iana.org/time-zones)를 참고하세요.

## 💻 사용법

### 기본 실행

```bash
# 헤드리스 모드 (백그라운드)
python3 run_monitor.py

# Ctrl+C로 종료
```

### GUI 모드

```bash
# 카메라 모듈 직접 사용
python3 camera_monitor/example.py

# 또는 monitor.py 직접 실행
python3 -c "from camera_monitor.monitor import quick_start; quick_start()"
```

### ⌨️ 키보드 조작 (GUI 모드)

| 키 | 기능 |
|---|---|
| `q` | 종료 |
| `s` | 스크린샷 촬영 |
| `r` | 녹화 시작/중지 |
| `m` | 움직임 감지 토글 |
| `i` | 상태 정보 표시 |
| `f` | FPS 표시 토글 |
| `t` | 타임스탬프 표시 토글 |
| `h` | 도움말 |

### 🐍 Python 코드에서 사용

```python
from camera_monitor import CameraMonitor

# 모니터 생성 및 실행
monitor = CameraMonitor(camera_index=0, resolution=(640, 480))

if monitor.initialize():
    monitor.motion_detector.enable()
    monitor.start_monitoring()
```

## 📂 프로젝트 구조

```
jetson-camera-monitor/
├── camera_monitor/          # 카메라 모니터링 패키지
│   ├── __init__.py
│   ├── camera_base.py       # 카메라 기본 조작
│   ├── recorder.py          # 녹화 및 스크린샷
│   ├── motion_detector.py   # 움직임 감지
│   ├── monitor.py           # 통합 모니터링
│   └── example.py           # 사용 예시
├── tests/                   # 테스트 스크립트
│   ├── test_camera.py
│   ├── test_motion.py
│   └── test_recording.py
├── config.py                # 설정 관리
├── utils.py                 # 시간 유틸리티
├── run_monitor.py           # 메인 실행 스크립트
├── camera_config.json       # 설정 파일
├── Dockerfile               # Docker 이미지 정의
├── docker-compose.yml       # Docker Compose 설정
├── docker-compose.camera.yml # 카메라 디바이스 추가
└── README.md
```

### 출력 디렉토리

```
project_root/
├── output/
│   ├── recordings/          # 녹화 파일 (.avi)
│   └── screenshots/         # 스크린샷 (.jpg)
```

## 🧪 테스트

```bash
# 카메라 기본 테스트
python3 tests/test_camera.py

# 움직임 감지 테스트
python3 tests/test_motion.py

# 녹화 테스트
python3 tests/test_recording.py

# Config 기반 통합 테스트
python3 tests/test_with_config.py
```

## 🔧 문제 해결

### 카메라를 열 수 없습니다

```bash
# 사용 가능한 카메라 확인
ls -l /dev/video*

# 권한 확인
sudo chmod 666 /dev/video0

# Docker에서 카메라 디바이스 마운트 확인
docker-compose -f docker-compose.yml -f docker-compose.camera.yml up -d
```

### GUI 창이 표시되지 않습니다

```bash
# X11 권한 설정
xhost +local:docker

# DISPLAY 환경변수 확인
echo $DISPLAY

# docker-compose.yml의 DISPLAY 설정 확인
```

### 시간대가 올바르지 않습니다

```bash
# Config 확인
cat camera_config.json | grep timezone

# utils.py에서 timezone 확인
python3 -c "from utils import get_timezone_name; print(get_timezone_name())"

# 시스템 시간 확인
date
```

### 녹화 파일 크기가 너무 작습니다

`camera_config.json`에서 해상도와 FPS 확인:

```json
{
  "camera": {
    "resolution": {
      "width": 640,
      "height": 360
    },
    "fps": 30  // 너무 높은 FPS는 문제를 일으킬 수 있음
  }
}
```

## 🛠️ 개발 환경

### 로컬 개발

```bash
# 컨테이너 없이 직접 실행 (테스트용)
pip3 install opencv-python numpy pytz

python3 run_monitor.py
```

### 새 기능 추가

`camera_monitor/` 패키지는 모듈화되어 있어 쉽게 확장 가능합니다:

- **새 감지 알고리즘**: `motion_detector.py` 수정
- **새 저장 포맷**: `recorder.py` 확장
- **사용자 정의 콜백**: `monitor.py`의 `set_frame_callback()` 사용

---

## 📝 라이선스

이 프로젝트는 MIT 라이선스로 제공됩니다.

## 🤝 기여하기

Issues와 Pull Requests를 환영합니다!

---

<div align="center">
Made with ❤️ for NVIDIA Jetson
</div>

