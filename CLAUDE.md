# Jetson Food AI - Claude Code 가이드

NVIDIA Jetson Orin Nano 기반 식당 모니터링 시스템

## 프로젝트 구조

```
jetson-food-ai/
├── jetson1_monitoring/          # Jetson #1: 사람 감지 + 볶음 모니터링
│   ├── JETSON1_INTEGRATED.py   # 메인 프로그램 (156KB)
│   ├── config.json             # 설정 파일
│   └── gst_camera.py           # GMSL 카메라 핸들러
├── jetson2_frying_ai/           # Jetson #2: 튀김 AI + 바켓 감지
│   ├── JETSON2_INTEGRATED.py   # 메인 프로그램 (171KB)
│   ├── config_jetson2.json     # 설정 파일
│   └── gst_camera.py           # GMSL 카메라 핸들러
└── SG4A-NONX-G2Y-A1.../         # GMSL 카메라 드라이버
```

## 주요 작업 파일

### Jetson #1 (사람 감지 + 볶음 모니터링)
- **메인**: `jetson1_monitoring/JETSON1_INTEGRATED.py`
- **설정**: `jetson1_monitoring/config.json`
- **카메라**: GMSL 3대 (사람감지, 볶음좌, 볶음우)
- **기능**:
  - YOLO 사람 감지 (GPU)
  - 주야간 자동 전환
  - 볶음 데이터 수집 (`~/AI_Data/StirFryData/`)
  - GPIO 릴레이 제어 (24V Omron)
  - MQTT 통신

### Jetson #2 (튀김 AI + 바켓 감지)
- **메인**: `jetson2_frying_ai/JETSON2_INTEGRATED.py`
- **설정**: `jetson2_frying_ai/config_jetson2.json`
- **카메라**: GMSL 4대 (튀김좌우, 바켓좌우)
- **기능**:
  - 튀김 상태 AI 분석 (Segmentation + Classification)
  - 바켓 감지 (observe_add 모델)
  - 데이터 수집 (`~/AI_Data/FryingData/`, `~/AI_Data/BucketData/`)
  - MQTT 통신
  - Jetson #1 릴레이 동기화

## 실행 및 디버깅

### 직접 실행
```bash
# Jetson #1
cd ~/jetson-food-ai/jetson1_monitoring
python3 JETSON1_INTEGRATED.py

# Jetson #2
cd ~/jetson-food-ai/jetson2_frying_ai
python3 JETSON2_INTEGRATED.py
```

### systemctl 서비스
```bash
# 상태 확인
sudo systemctl status jetson1-monitor
sudo systemctl status jetson2-monitor

# 실시간 로그 (가장 유용!)
sudo journalctl -u jetson1-monitor -f
sudo journalctl -u jetson2-monitor -f

# 재시작
sudo systemctl restart jetson1-monitor
sudo systemctl restart jetson2-monitor
```

### 카메라 확인
```bash
# GMSL 카메라 확인
ls -l /dev/video*

# GMSL 드라이버 수동 로드
cd ~/jetson-food-ai/SG4A-NONX-G2Y-A1_ORIN_NANO_YUV_JP6.2_L4TR36.4.3
sudo ./quick_bring_up.sh
```

## 하드웨어 설정

### GMSL 카메라
- **해상도**: 1920x1536 @ 30fps
- **포맷**: UYVY
- **드라이버**: `SG4A-NONX-G2Y-A1_ORIN_NANO_YUV_JP6.2_L4TR36.4.3/`

### GPIO 릴레이
- **타입**: 24V Omron Relay (자기유지형)
- **핀**: Pin 29 (GPIO07) + Pin 31 (GPIO416) 동시 사용
- **제어**: Pulse 모드 (200ms HIGH → LOW)
- **테스트**: `test_relay_pulse.py`, `test_both_pins.py`

### 진동 센서 (2026-01-08 추가)
- **연결**: CH340 USB-RS485 (WitMotion JY901B)
- **포트**: `/dev/ttyUSB0`
- **통신**: Modbus RTU
- **라이브러리**: pymodbus 3.x (`device_id` 파라미터 사용)
- **테스트 파일**: `test_vibration_pymodbus3_finalrev.py`
- **설정**: `vibration_config.json`

## 주요 설정 (config.json)

### Jetson #1
```json
{
  "yolo_model": "yolo12n.pt",
  "yolo_confidence": 0.7,
  "stirfry_save_dir": "AI_Data/StirFryData",
  "mqtt_broker": "192.168.0.100",
  "relay_mode": "pulse",
  "vibration_test_mode": true
}
```

### Jetson #2
```json
{
  "frying_seg_model": "frying_seg.pt",
  "frying_cls_model": "frying_cls.pt",
  "observe_seg_model": "observe_add/bestb.pt",
  "data_collection_interval": 1,
  "mqtt_broker": "192.168.0.100",
  "dynamic_camera_enabled": false
}
```

## 최근 변경사항

### 2026-01-08: 진동센서 통합
- CH340 USB-RS485 드라이버 설치
- WitMotion JY901B Modbus 통신 구현
- pymodbus 3.x 호환성 확보 (`device_id` 파라미터)

### 2025-12-11: MQTT 문제 해결
- systemctl 서비스에서 MQTT 연결 안 되는 문제 수정
- `After=network-online.target` 추가
- `install_autostart.sh` 업데이트

### 2025-12-08: 폰트 프리징 수정
- `tkfont.families()` 호출 제거
- 직접 폰트 객체 생성 방식으로 변경

### 2025-11-24: GPIO 릴레이 업그레이드
- 24V Omron Relay 적용
- Dual-pin setup (Pin 29, 31)

## 개발 규칙

- **주석/로그**: 한국어
- **커밋 메시지**: 영어
- **GUI**: tkinter, 흰색 테마, 768x1024 세로 모드
- **AI**: YOLO (ultralytics), PyTorch CUDA
- **금지 사항**: `tkfont.families()` 사용 금지 (프리징 유발)

## 문제 해결

### GPU 사용 안 됨
```bash
python3 -c "import torch; print(torch.cuda.is_available())"
# True가 나와야 함
```

### MQTT 연결 안 됨 (systemctl)
```bash
# 서비스 파일 수정
sudo vim /etc/systemd/system/jetson1-monitor.service

# [Unit] 섹션에 추가:
After=network-online.target

# 적용
sudo systemctl daemon-reload
sudo systemctl restart jetson1-monitor
```

### 진동센서 안 보임
```bash
# USB-RS485 확인
ls -l /dev/ttyUSB*

# CH340 드라이버 설치
sudo bash setup_ch340_complete.sh
```

## 참고 문서

- 상세 배포: `배포가이드.md`
- 데이터 저장: `docs/DATA_STORAGE_MAP.md`
- AI 학습: `docs/AI_TRAINING_STRATEGY.md`
