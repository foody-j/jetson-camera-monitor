# Jetson Food AI

NVIDIA Jetson Orin Nano 기반 식당 모니터링 시스템 (GMSL 카메라 + AI)

## 시스템 구성

### Jetson #1 - 사람 감지 + 볶음 모니터링
- **디렉토리**: `jetson1_monitoring/`
- **메인 프로그램**: `JETSON1_INTEGRATED.py`
- **설정 파일**: `config.json`
- **카메라**: GMSL 3대 (사람감지 1대, 볶음좌우 2대)
- **주요 기능**:
  - YOLO 사람 감지 (GPU 가속)
  - 주야간 자동 전환
  - 볶음 데이터 수집 (`~/AI_Data/StirFryData/`)
  - GPIO 릴레이 제어 (24V Omron)
  - MQTT 통신

### Jetson #2 - 튀김 AI + 바켓 감지
- **디렉토리**: `jetson2_frying_ai/`
- **메인 프로그램**: `JETSON2_INTEGRATED.py`
- **설정 파일**: `config_jetson2.json`
- **카메라**: GMSL 4대 (튀김좌우 2대, 바켓좌우 2대)
- **주요 기능**:
  - 튀김 상태 AI 분석 (Segmentation + Classification)
  - 바켓 감지 (observe_add 모델)
  - 데이터 수집 (`~/AI_Data/FryingData/`, `~/AI_Data/BucketData/`)
  - MQTT 통신
  - Jetson #1 릴레이 동기화

## 빠른 시작

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

### 자동 시작 설정
```bash
# Jetson #1
cd ~/jetson-food-ai/jetson1_monitoring
./install_autostart.sh

# Jetson #2
cd ~/jetson-food-ai/jetson2_frying_ai
./install_autostart.sh
```

## 하드웨어

### GMSL 카메라
- **해상도**: 1920x1536 @ 30fps
- **포맷**: UYVY
- **드라이버**: `SG4A-NONX-G2Y-A1_ORIN_NANO_YUV_JP6.2_L4TR36.4.3/`
- **확인**: `ls -l /dev/video*`

### GPIO 릴레이
- **타입**: 24V Omron Relay (자기유지형)
- **핀**: Pin 29 (GPIO07) + Pin 31 (GPIO416)
- **제어**: Pulse 모드 (200ms HIGH → LOW)
- **테스트**: `test_relay_pulse.py`, `test_both_pins.py`

### 진동 센서 (2026-01 추가)
- **연결**: CH340 USB-RS485 (WitMotion JY901B)
- **포트**: `/dev/ttyUSB0`
- **통신**: Modbus RTU (pymodbus 3.x)
- **테스트**: `test_vibration_pymodbus3_finalrev.py`
- **설정**: `vibration_config.json`

## 주요 설정

### jetson1_monitoring/config.json
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

### jetson2_frying_ai/config_jetson2.json
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

## 문제 해결

### GPU 사용 확인
```bash
python3 -c "import torch; print(torch.cuda.is_available())"
# True가 나와야 함
```

### 카메라 확인
```bash
ls -l /dev/video*

# GMSL 드라이버 수동 로드
cd ~/jetson-food-ai/SG4A-NONX-G2Y-A1_ORIN_NANO_YUV_JP6.2_L4TR36.4.3
sudo ./quick_bring_up.sh

# 드라이버 서비스 확인
sudo systemctl status gmsl-driver-load
sudo journalctl -u gmsl-driver-load -f
```

### 진동 센서 확인
```bash
ls -l /dev/ttyUSB*

# CH340 드라이버 설치
sudo bash setup_ch340_complete.sh
```

### 성능 모드 확인
```bash
sudo nvpmodel -q
# NV Power Mode: MAXN_SUPER (2) 확인

# MAXN 모드 설정
./set_maxn_mode.sh
```

### MQTT 연결 문제 (systemctl)
```bash
# 서비스 파일 수정
sudo vim /etc/systemd/system/jetson1-monitor.service

# [Unit] 섹션에 추가:
After=network-online.target

# 적용
sudo systemctl daemon-reload
sudo systemctl restart jetson1-monitor
```

## 최근 업데이트

### 2026-01-08
- 진동센서 통합 (CH340 USB-RS485, WitMotion JY901B)
- pymodbus 3.x 호환 (`device_id` 파라미터)

### 2025-12-11
- systemctl MQTT 연결 문제 해결 (`network-online.target` 추가)

### 2025-12-08
- tkinter 폰트 프리징 수정 (`tkfont.families()` 제거)

### 2025-11-24
- GPIO 릴레이 업그레이드 (24V Omron, Dual-pin)
- Jetson1-Jetson2 릴레이 동기화

## 개발 규칙

- **주석/로그**: 한국어
- **커밋 메시지**: 영어
- **GUI**: tkinter, 768x1024 세로 모드
- **AI**: YOLO (ultralytics), PyTorch CUDA
- **금지**: `tkfont.families()` 사용 금지 (프리징)

## 참고 문서

- **Claude Code용**: `CLAUDE.md` - 프로젝트 구조 및 개발 가이드
- **상세 배포**: `배포가이드.md`
- **데이터 저장**: `docs/DATA_STORAGE_MAP.md`
- **AI 학습**: `docs/AI_TRAINING_STRATEGY.md`
