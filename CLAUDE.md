# Jetson Food AI 프로젝트

NVIDIA Jetson Orin Nano 기반 식당 모니터링 시스템 (GMSL 카메라 + AI)

## 시스템 구성

### Jetson #1 (jetson1_monitoring/)
- **역할**: 사람 감지 + 볶음 모니터링
- **카메라**: GMSL 3대 (카메라0: 사람감시, 카메라1: 볶음 왼쪽, 카메라2: 볶음 오른쪽)
- **메인 파일**: `JETSON1_INTEGRATED.py`
- **설정**: `config.json`
- **기능**: YOLO 사람 감지 (GPU), 주야간 자동 전환, GPIO 릴레이 제어

### Jetson #2 (jetson2_frying_ai/)
- **역할**: 튀김 AI 분석 + 바켓 감지
- **카메라**: GMSL 4대
- **메인 파일**: `JETSON2_INTEGRATED.py`
- **설정**: `config_jetson2.json`
- **기능**: 튀김 상태 AI 분석, 데이터 수집, MQTT 통신

## 핵심 파일

| 파일 | 설명 |
|------|------|
| `jetson1_monitoring/JETSON1_INTEGRATED.py` | Jetson1 메인 (127KB) |
| `jetson2_frying_ai/JETSON2_INTEGRATED.py` | Jetson2 메인 (132KB) |
| `jetson1_monitoring/config.json` | Jetson1 설정 |
| `jetson2_frying_ai/config_jetson2.json` | Jetson2 설정 |

## 하드웨어 설정

### GPIO 릴레이
- **릴레이**: 24V Omron Relay
- **핀 구성**: PIN 7 (GPIO07) + PIN 11 (GPIO416) 동시 사용
- **제어 방식**: 펄스 (200ms HIGH → LOW)

### 카메라
- **타입**: GMSL 카메라 (SerDes)
- **해상도**: 1920x1536 @ 30fps
- **포맷**: UYVY
- **드라이버**: `SG4A-NONX-G2Y-A1_ORIN_NANO_YUV_JP6.2_L4TR36.4.3/`

## 최근 변경사항

### 2025-12-08
- `tkfont.families()` 프리징 이슈 수정 (Jetson1, Jetson2 모두)
  - 폰트 초기화 시 시스템 프리징 발생
  - 직접 폰트 객체 생성 방식으로 변경

### 2025-12-04
- Segfault on startup 수정
- Manual data collection 활성화

### 2025-11-24
- GPIO relay 24V Omron Relay 업그레이드
- Dual-pin setup (PIN 7 + PIN 11)

## 알려진 이슈

- Jetson 2 카메라 초기화 문제 조사 필요
- 폰트 캐시 관련 프리징 (수정 완료)

## 개발 규칙

- 한국어 주석/로그 사용
- 커밋 메시지는 영어
- GUI: tkinter 사용, 흰색 테마
- AI: YOLO (ultralytics), PyTorch CUDA

## 실행 방법

```bash
# Jetson #1
cd ~/jetson-food-ai/jetson1_monitoring
python3 JETSON1_INTEGRATED.py

# Jetson #2
cd ~/jetson-food-ai/jetson2_frying_ai
python3 JETSON2_INTEGRATED.py
```

## 서비스 관리

```bash
# 상태 확인
sudo systemctl status jetson1-monitor
sudo systemctl status jetson2-monitor

# 로그 확인
sudo journalctl -u jetson1-monitor -f
sudo journalctl -u jetson2-monitor -f
```

## 디버깅 팁

- `tkfont.families()` 사용 금지 (프리징 유발)
- GMSL 카메라는 `/dev/video*`로 확인
- GPIO 테스트: `test_relay_pulse.py`, `test_both_pins.py`
